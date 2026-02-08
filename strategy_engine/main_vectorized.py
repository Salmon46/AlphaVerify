import logging
import pandas as pd
import numpy as np
from collections import namedtuple
try:
    from dataclasses import dataclass
except ImportError:
    pass

logger = logging.getLogger(__name__)

# 1. Define Config matching the Event-Driven one
# We use a class or extend namedtuple to support defaults safely across WFA
try:
    @dataclass
    class StrategyConfig:
        sma_fast: int = 10
        sma_slow: int = 20
        risk_per_trade: float = 0.01
        sizing_stop_loss_pct: float = 0.02
        
        # Helper to behave like namedtuple for legacy code if needed
        @property
        def _fields(self):
            return ('sma_fast', 'sma_slow', 'risk_per_trade', 'sizing_stop_loss_pct')
            
except ImportError:
    StrategyConfig = namedtuple('StrategyConfig', ['sma_fast', 'sma_slow', 'risk_per_trade', 'sizing_stop_loss_pct'])

# 2. Vectorized Logic Container
class StrategyEngine:
    def __init__(self):
        # Default config matching main.py
        # We need to handle potential namedtuple instantiation if dataclass failed (unlikely in modern python but safety first)
        try:
            self.config = StrategyConfig(sma_fast=10, sma_slow=20, risk_per_trade=0.01, sizing_stop_loss_pct=0.02)
        except TypeError:
             # Fallback if namedtuple without defaults
             self.config = StrategyConfig(10, 20, 0.01, 0.02)

    def generate_signal(self, data):
        """
        Instance method required by the Permutation Testing Router.
        
        Args:
            data: DataFrame or Dict of DataFrames (Multi-Asset)
            
        Returns:
            signals (np.array) OR returns (np.array) depending on strategy type.
            For this simple strategy, we return the STRATEGY RETURNS directly 
            because the router expects to calculate metrics on returns.
        """
        # 1. Prepare Data
        prep_data = self._prepare_vectorized_data(data)
        
        # 2. Run Logic
        # Returns tuple (signals, strategy_returns)
        _, strategy_returns = self._evaluate_vectorized_logic(prep_data, self.config)
        
        return strategy_returns

    @staticmethod
    def _prepare_vectorized_data(data_obj):
        """
        Precompute indicators if possible (or just return raw data).
        For multi-asset, data_obj is {symbol: DataFrame}.
        For single-asset, it might be tuple (opens, highs, lows, closes, volumes).
        
        Here we handle the Multi-Asset Dictionary case which is standard for AlphaVerify.
        """
        # If tuple (Single Asset Mode from legacy logic)
        if isinstance(data_obj, tuple):
             opens, highs, lows, closes, volumes = data_obj
             return {
                 'closes': closes,
                 'type': 'single'
             }
        
        return data_obj

    @staticmethod
    def _evaluate_vectorized_logic(precomputed_data, config):
        """
        The Core Logic: SMA Crossover.
        Returns: Tuple (signals, daly_returns) or just daly_returns
        """
        
        # Config Parsing with Defaults for Safety (WFA might pass 0s)
        try:
            sma_fast = int(config.sma_fast) if config.sma_fast > 0 else 10
            sma_slow = int(config.sma_slow) if config.sma_slow > 0 else 20
            risk = float(config.risk_per_trade)
            stop = float(config.sizing_stop_loss_pct)
        except AttributeError:
            # Fallback for namedtuple access
            try:
                sma_fast = int(config[0])
                sma_slow = int(config[1])
                risk = float(config[2]) if len(config) > 2 else 0.01
                stop = float(config[3]) if len(config) > 3 else 0.02
            except:
                sma_fast = 10
                sma_slow = 20
                risk = 0.01
                stop = 0.02

        # Handle 0.0 from WFA/Sensitivity
        if risk <= 0: risk = 0.01
        if stop <= 0: stop = 0.02
        
        # Normalize
        leverage = risk / stop 
        
        # Multi-Asset Portfolio Logic
        total_strategy_returns = None
        asset_count = 0
        
        # Helper for convolution
        def fast_sma(data, period):
            return np.convolve(data, np.ones(period)/period, mode='full')[:len(data)]

        # If it's the single-asset tuple wrapper from logic.py
        if isinstance(precomputed_data, dict) and precomputed_data.get('type') == 'single':
            data_map = {'MAIN': {'close': pd.Series(precomputed_data['closes'])}} # Wrap to uniform dict
        else:
            data_map = precomputed_data

        logger.info(f"Vectorized Strategy Running. Assets: {len(data_map)}. Leverage: {leverage:.2f}")

        for symbol, df in data_map.items():
            if 'close' not in df: 
                logger.warning(f"Skipping {symbol}, no close column. Cols: {df.columns}")
                continue
            
            # Ensure proper type
            closes = df['close'].values.astype(np.float64)
            # logger.info(f"Processing {symbol}, Length: {len(closes)}")
            
            # --- 1. Indicator Calculation ---
            sma_fast_arr = fast_sma(closes, sma_fast)
            sma_slow_arr = fast_sma(closes, sma_slow)
            
            # --- 2. Signal Logic ---
            # Fast > Slow = Bullish
            signals = np.where(sma_fast_arr > sma_slow_arr, 1.0, 0.0)
            
            # Shift to trade on Next Open
            signals = np.roll(signals, 1)
            signals[0] = 0.0
            
            # --- 3. Asset Return ---
            # Handle potential zeros in closes for division
            with np.errstate(divide='ignore', invalid='ignore'):
                 price_returns = np.diff(closes) / closes[:-1]
            
            price_returns = np.insert(price_returns, 0, 0.0)
            price_returns = np.nan_to_num(price_returns) # Fix potential NaNs/Infs
            
            # Apply Leverage to Returns
            asset_returns = signals * price_returns * leverage
            
            # Add to Portfolio
            if total_strategy_returns is None:
                total_strategy_returns = np.zeros_like(asset_returns)
            
            # Accumulate
            total_strategy_returns += asset_returns
            asset_count += 1
            
        # Normalize returns by asset count (Equal Weight assumption for portfolio)
        if asset_count > 0:
            total_strategy_returns /= asset_count
            
        return (None, total_strategy_returns if total_strategy_returns is not None else np.array([]))


# --- Module-Level Aliases ---
_prepare_vectorized_data = StrategyEngine._prepare_vectorized_data
_evaluate_vectorized_logic = StrategyEngine._evaluate_vectorized_logic
