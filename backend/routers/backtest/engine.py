"""
Backtest Engine for Production Strategy

This module provides a backtesting environment that simulates the production
StrategyEngine by providing mock Redis infrastructure and feeding historical
market data tick-by-tick.
"""
import sys
import os
import time
import logging
import importlib.util
from collections import defaultdict
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _get_scalar(value, default=0.0):
    """
    Safely extract a scalar value from a potentially Series value.
    This handles the case where DataFrame has duplicate column names.
    """
    if value is None:
        return default
    if isinstance(value, pd.Series):
        # Take the first value if it's a Series
        return float(value.iloc[0]) if len(value) > 0 else default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class Trade:
    """Represents a single trade."""
    timestamp: str
    side: str  # BUY or SELL
    symbol: str
    price: float
    quantity: float
    pnl: float = 0.0  # Only populated for SELL trades
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'side': self.side,
            'symbol': self.symbol,
            'price': self.price,
            'quantity': self.quantity,
            'pnl': self.pnl
        }


@dataclass 
class EquityPoint:
    """Represents a point on the equity curve."""
    time: str
    value: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {'time': self.time, 'value': self.value}


@dataclass
class BacktestResult:
    """Container for backtest results."""
    trades: List[Trade]
    equity_curve: List[EquityPoint]
    final_cash: float
    final_positions: Dict[str, float]
    

class MockRedisClient:
    """
    Mock Redis client that intercepts published signals and simulates fills.
    """
    
    def __init__(self, engine: 'BacktestEngine'):
        self.engine = engine
        self.pending_signals: List[Dict[str, Any]] = []
        self._subscriptions = {}
        
    def publish(self, channel: str, data: bytes):
        """Intercept signal publications."""
        if channel == 'trade_signals':
            # Parse the signal
            try:
                import json
                if isinstance(data, bytes):
                    signal = json.loads(data.decode('utf-8'))
                else:
                    signal = json.loads(data)
                self.pending_signals.append(signal)
                logger.debug(f"MockRedis captured signal: {signal.get('action')} {signal.get('symbol')}")
            except Exception as e:
                logger.error(f"Failed to parse signal: {e}")
                
    def pubsub(self):
        """Return a mock pubsub object."""
        return MockPubSub()
    
    def ping(self):
        """Mock ping."""
        return True
    
    def get_pending_signals(self) -> List[Dict[str, Any]]:
        """Get and clear pending signals."""
        signals = self.pending_signals[:]
        self.pending_signals = []
        return signals


class MockPubSub:
    """Mock Redis PubSub."""
    
    def __init__(self):
        self._patterns = []
        self._channels = []
        
    def psubscribe(self, *patterns):
        self._patterns.extend(patterns)
        
    def subscribe(self, *channels):
        self._channels.extend(channels)
        
    def get_message(self, timeout=None):
        return None
    
    def close(self):
        pass


class MockMetrics:
    """Mock Prometheus metrics module."""
    
    class MockCounter:
        def labels(self, **kwargs):
            return self
        def inc(self, amount=1):
            pass
        def set(self, value):
            pass
            
    class MockHistogram:
        def labels(self, **kwargs):
            return self
        def observe(self, value):
            pass
    
    TICKS_RECEIVED = MockCounter()
    MARKET_PRICE = MockCounter()
    SIGNALS_GENERATED = MockCounter()
    SIGNAL_LATENCY = MockHistogram()
    INDICATOR_VALUE = MockCounter()
    CURRENT_POSITION = MockCounter()
    UNREALIZED_PNL = MockCounter()
    REALIZED_PNL = MockCounter()
    PORTFOLIO_VALUE = MockCounter()
    SERVICE_STATUS = MockCounter()
    
    @staticmethod
    def record_error(service, error_type):
        pass
    
    @staticmethod
    def start_metrics_server(port):
        pass


class BacktestEngine:
    """
    Event-driven backtest engine for production strategies.
    
    Feeds historical data tick-by-tick to the strategy, intercepts signals,
    simulates fills, and tracks portfolio state.
    """
    
    def __init__(
        self,
        initial_cash: float = 10000.0,
        commission_rate: float = 0.001  # 0.1% per trade
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        
        # Portfolio state
        self.positions: Dict[str, float] = defaultdict(float)  # symbol -> quantity
        self.avg_entry_prices: Dict[str, float] = defaultdict(float)  # symbol -> avg price
        
        # Results tracking
        self.trades: List[Trade] = []
        self.equity_curve: List[EquityPoint] = []
        
        # Current market state for fill simulation
        self.current_prices: Dict[str, float] = {}
        self.current_timestamp: str = ""
        
        # Mock Redis
        self.mock_redis = MockRedisClient(self)
        
        # Strategy instance (set during run)
        self.strategy = None
        
    def _load_strategy(self, strategy_path: str, class_name: str = 'StrategyEngine'):
        """
        Dynamically load the strategy module with mocked dependencies.
        """
        # Inject mock modules before importing strategy
        self._setup_mock_modules(strategy_path)
        
        # Load the strategy module
        spec = importlib.util.spec_from_file_location("backtest_strategy", strategy_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load strategy from {strategy_path}")
            
        strategy_module = importlib.util.module_from_spec(spec)
        strategy_module.__package__ = "backtest_strategy"
        
        try:
            spec.loader.exec_module(strategy_module)
        except Exception as e:
            logger.error(f"Failed to load strategy: {e}")
            raise
            
        # Get the strategy class
        if not hasattr(strategy_module, class_name):
            raise ValueError(f"Strategy class '{class_name}' not found in module")
            
        StrategyClass = getattr(strategy_module, class_name)
        
        # Instantiate with mock Redis
        self.strategy = StrategyClass(
            redis_client=self.mock_redis,
            initial_cash=self.initial_cash
        )
        
        return self.strategy
    
    def _setup_mock_modules(self, strategy_path: str):
        """Setup mock modules for strategy dependencies."""
        # Mock the metrics module
        mock_metrics = MockMetrics()
        
        # Create mock common.python package
        strategy_dir = os.path.dirname(strategy_path)
        common_path = os.path.join(strategy_dir, 'common', 'python')
        
        # Create a mock module for common.python.metrics
        class MockCommonPython:
            metrics = mock_metrics
            
        # Register in sys.modules
        sys.modules['common'] = type(sys)('common')
        sys.modules['common.python'] = MockCommonPython()
        sys.modules['common.python.metrics'] = mock_metrics
        
        # Add strategy directory to path
        if strategy_dir not in sys.path:
            sys.path.insert(0, strategy_dir)
    
    def _execute_signal(self, signal: Dict[str, Any]):
        """
        Execute a trade signal at the current market price.
        """
        action = signal.get('action', 'HOLD')
        symbol = signal.get('symbol', '')
        quantity = float(signal.get('quantity', 0))
        
        if action == 'HOLD' or quantity <= 0 or not symbol:
            return
            
        price = self.current_prices.get(symbol, 0)
        if price <= 0:
            logger.warning(f"No price for {symbol}, skipping signal")
            return
            
        commission = price * quantity * self.commission_rate
        
        if action == 'BUY':
            cost = price * quantity + commission
            
            if cost > self.cash:
                # Reduce quantity to what we can afford
                max_qty = (self.cash - commission) / price
                if max_qty <= 0:
                    logger.warning(f"Insufficient funds for BUY {symbol}")
                    return
                quantity = max_qty
                cost = price * quantity + commission
            
            self.cash -= cost
            
            # Update position (weighted average)
            current_qty = self.positions[symbol]
            current_avg = self.avg_entry_prices[symbol]
            total_qty = current_qty + quantity
            
            if total_qty > 0:
                self.avg_entry_prices[symbol] = (
                    (current_qty * current_avg) + (quantity * price)
                ) / total_qty
            
            self.positions[symbol] = total_qty
            
            trade = Trade(
                timestamp=self.current_timestamp,
                side='BUY',
                symbol=symbol,
                price=price,
                quantity=quantity,
                pnl=0.0
            )
            self.trades.append(trade)
            
            logger.info(f"EXECUTED BUY: {quantity:.4f} {symbol} @ {price:.2f}")
            
            # Send execution report to strategy
            self._send_execution_report(symbol, 'BUY', quantity, price)
            
        elif action == 'SELL':
            current_qty = self.positions.get(symbol, 0)
            
            if current_qty <= 0:
                logger.warning(f"No position to sell for {symbol}")
                return
                
            # Sell min of requested qty and held qty
            sell_qty = min(quantity, current_qty)
            revenue = price * sell_qty - commission
            
            # Calculate P&L
            entry_price = self.avg_entry_prices.get(symbol, 0)
            pnl = (price - entry_price) * sell_qty - commission
            
            self.cash += revenue
            self.positions[symbol] = current_qty - sell_qty
            
            if self.positions[symbol] <= 0:
                self.avg_entry_prices[symbol] = 0
            
            trade = Trade(
                timestamp=self.current_timestamp,
                side='SELL',
                symbol=symbol,
                price=price,
                quantity=sell_qty,
                pnl=pnl
            )
            self.trades.append(trade)
            
            logger.info(f"EXECUTED SELL: {sell_qty:.4f} {symbol} @ {price:.2f} PnL: {pnl:.2f}")
            
            # Send execution report to strategy
            self._send_execution_report(symbol, 'SELL', sell_qty, price)
    
    def _send_execution_report(self, symbol: str, side: str, quantity: float, price: float):
        """Send execution report back to strategy for position tracking."""
        if self.strategy is None:
            return
            
        # Update strategy's internal position tracking
        exec_report = {
            'symbol': symbol,
            'status': 'FILLED',
            'filled_quantity': quantity,
            'average_fill_price': price,
            'side': side
        }
        
        # Call _handle_execution_report directly
        self.strategy._handle_execution_report(exec_report)
    
    def _calculate_equity(self) -> float:
        """Calculate current portfolio equity."""
        positions_value = sum(
            qty * self.current_prices.get(sym, 0) 
            for sym, qty in self.positions.items()
        )
        return self.cash + positions_value
    
    def _record_equity(self):
        """Record current equity to the curve."""
        equity = self._calculate_equity()
        self.equity_curve.append(EquityPoint(
            time=self.current_timestamp,
            value=equity
        ))
    
    def run(
        self,
        data: Dict[str, pd.DataFrame],
        strategy_path: str,
        class_name: str = 'StrategyEngine'
    ) -> BacktestResult:
        """
        Run the backtest.
        
        Args:
            data: Dict of {symbol: DataFrame} with OHLCV data
            strategy_path: Path to the strategy Python file
            class_name: Name of the strategy class to instantiate
            
        Returns:
            BacktestResult with trades, equity curve, and final state
        """
        # Load strategy
        self._load_strategy(strategy_path, class_name)
        
        # Add symbols to watchlist
        symbols = list(data.keys())
        # Normalize symbols (strategy expects 'BTC/USD' format)
        normalized_symbols = []
        for s in symbols:
            # Handle various formats
            norm = s.replace('-', '/').replace('_', '/')
            normalized_symbols.append(norm)
            
        self.strategy.add_to_watchlist(normalized_symbols)
        
        # Prepare tick iterator
        # Combine all DataFrames into a single timeline
        all_ticks = []
        
        for symbol, df in data.items():
            normalized_symbol = symbol.replace('-', '/').replace('_', '/')
            
            for idx, row in df.iterrows():
                # Get timestamp
                if isinstance(idx, pd.Timestamp):
                    ts = int(idx.timestamp() * 1000)
                    ts_str = idx.isoformat()
                else:
                    ts = int(time.time() * 1000)
                    ts_str = str(idx)
                
                # Create tick - use _get_scalar to handle potential Series values
                price_val = row.get('close') if 'close' in row.index else row.get('Close', 0)
                vol_val = row.get('volume') if 'volume' in row.index else row.get('Volume', 1)
                
                tick = {
                    'type': 'TRADE',
                    'symbol': normalized_symbol,
                    'price': _get_scalar(price_val, 0.0),
                    'volume': _get_scalar(vol_val, 1.0),
                    'timestamp': ts,
                    'source': 'backtest',
                    '_ts_str': ts_str  # For equity curve timestamps
                }
                all_ticks.append((ts, tick))
        
        # Sort by timestamp
        all_ticks.sort(key=lambda x: x[0])
        
        if not all_ticks:
            logger.warning("No data to backtest")
            return BacktestResult(
                trades=[],
                equity_curve=[],
                final_cash=self.cash,
                final_positions=dict(self.positions)
            )
        
        # Record initial equity
        self.current_timestamp = all_ticks[0][1]['_ts_str']
        self._record_equity()
        
        # Sampling for equity curve (avoid too many points)
        total_ticks = len(all_ticks)
        sample_interval = max(1, total_ticks // 500)  # ~500 points max
        
        # Run simulation
        logger.info(f"Starting backtest with {total_ticks} ticks across {len(data)} symbols")
        
        for i, (ts, tick) in enumerate(all_ticks):
            symbol = tick['symbol']
            price = tick['price']
            
            # Update current state
            self.current_prices[symbol] = price
            self.current_timestamp = tick['_ts_str']
            
            # Feed to strategy
            self.strategy._handle_market_data(tick)
            
            # Process any signals generated
            for signal in self.mock_redis.get_pending_signals():
                self._execute_signal(signal)
            
            # Sample equity curve
            if i % sample_interval == 0:
                self._record_equity()
            
            # Progress logging
            if i > 0 and i % (total_ticks // 10) == 0:
                pct = (i / total_ticks) * 100
                logger.info(f"Backtest progress: {pct:.0f}%")
        
        # Final equity record
        self._record_equity()
        
        logger.info(f"Backtest complete. Trades: {len(self.trades)}, Final Equity: {self._calculate_equity():.2f}")
        
        return BacktestResult(
            trades=self.trades,
            equity_curve=self.equity_curve,
            final_cash=self.cash,
            final_positions=dict(self.positions)
        )
