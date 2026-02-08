"""
Performance Metrics Calculator for Backtesting
"""
import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    """Container for backtest performance metrics."""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    final_equity: float
    initial_equity: float


def calculate_metrics(
    equity_curve: List[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    initial_cash: float,
    periods_per_year: float = 252.0
) -> BacktestMetrics:
    """
    Calculate comprehensive performance metrics from backtest results.
    
    Args:
        equity_curve: List of {'time': str, 'value': float}
        trades: List of {'side': str, 'price': float, 'quantity': float, 'pnl': float, ...}
        initial_cash: Starting capital
        periods_per_year: For annualization (252 for daily, 252*6.5*60 for minute data)
    
    Returns:
        BacktestMetrics dataclass with all calculated metrics
    """
    # Extract equity values
    equity_values = np.array([pt['value'] for pt in equity_curve]) if equity_curve else np.array([initial_cash])
    
    # Total Return
    final_equity = equity_values[-1] if len(equity_values) > 0 else initial_cash
    total_return = ((final_equity - initial_cash) / initial_cash) * 100 if initial_cash > 0 else 0.0
    
    # Sharpe Ratio
    if len(equity_values) > 1:
        returns = np.diff(equity_values) / equity_values[:-1]
        returns = np.nan_to_num(returns)
        
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(periods_per_year)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0
    
    # Max Drawdown
    if len(equity_values) > 0:
        peak = np.maximum.accumulate(equity_values)
        drawdown = (peak - equity_values) / peak
        max_drawdown = np.max(drawdown) * 100 if len(drawdown) > 0 else 0.0
    else:
        max_drawdown = 0.0
    
    # Trade-based metrics
    sell_trades = [t for t in trades if t.get('side') == 'SELL']
    
    if sell_trades:
        pnls = [t.get('pnl', 0.0) for t in sell_trades]
        
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        total_trades = len(sell_trades)
        
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0
        
        gross_profit = sum(winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 0.0
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (100.0 if gross_profit > 0 else 0.0)
        
        avg_win = np.mean(winning_trades) if winning_trades else 0.0
        avg_loss = np.mean(losing_trades) if losing_trades else 0.0
    else:
        win_count = 0
        loss_count = 0
        total_trades = 0
        win_rate = 0.0
        profit_factor = 0.0
        avg_win = 0.0
        avg_loss = 0.0
    
    return BacktestMetrics(
        total_return=round(total_return, 2),
        sharpe_ratio=round(sharpe_ratio, 3),
        max_drawdown=round(max_drawdown, 2),
        profit_factor=round(profit_factor, 2),
        win_rate=round(win_rate, 2),
        total_trades=total_trades,
        winning_trades=win_count,
        losing_trades=loss_count,
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        final_equity=round(final_equity, 2),
        initial_equity=initial_cash
    )
