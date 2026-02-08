"""
Metrics for Permutation Testing.

Calculates objective functions from strategy signals.
"""
import numpy as np
import pandas as pd


def calc_profit_factor(signal: np.ndarray, returns: np.ndarray) -> float:
    """
    Calculate profit factor from signal and returns.
    
    Args:
        signal: Array of positions [-1, 0, 1] for each bar OR None if returns is already strategy returns
        returns: Log returns of close prices (already shifted forward by 1) OR Strategy Returns
        
    Returns:
        Profit factor (gross profit / gross loss)
    """
    # If signal is None, assume 'returns' is already the strategy returns
    if signal is None:
        strat_returns = returns
    else:
        # Strategy returns = position * bar return
        strat_returns = signal * returns
    
    # Remove NaN values
    strat_returns = strat_returns[~np.isnan(strat_returns)]
    
    if len(strat_returns) == 0:
        return 1.0
    
    gross_profit = strat_returns[strat_returns > 0].sum()
    gross_loss = abs(strat_returns[strat_returns < 0].sum())
    
    if gross_loss == 0:
        return 10.0 if gross_profit > 0 else 1.0
    
    return gross_profit / gross_loss


def calc_sharpe_ratio(signal: np.ndarray, returns: np.ndarray, periods_per_year: float = 252.0) -> float:
    """
    Calculate Sharpe ratio from signal and returns.
    
    Args:
        signal: Array of positions [-1, 0, 1] for each bar OR None
        returns: Log returns of close prices (already shifted forward by 1) OR Strategy Returns
        periods_per_year: Annualization factor (Default 252 for daily).
                          For 1-minute data: 252 * 6.5 * 60 ~= 98280 (Stock Market) or 365*24*60 = 525600 (Crypto 24/7)
                          Use 252 as safe default if unknown, but recommend passing correct value.
        
    Returns:
        Sharpe ratio (mean return / std return) * sqrt(periods)
    """
    if signal is None:
        strat_returns = returns
    else:
        strat_returns = signal * returns

    strat_returns = strat_returns[~np.isnan(strat_returns)]
    
    if len(strat_returns) < 2:
        return 0.0
    
    std = np.std(strat_returns)
    if std == 0:
        return 0.0
    
    # Use dynamic annualization
    return np.sqrt(periods_per_year) * np.mean(strat_returns) / std


def prepare_returns(df: pd.DataFrame) -> np.ndarray:
    """
    Prepare log returns from OHLC DataFrame.
    
    Returns are shifted forward by 1 bar so that:
    - signal[i] = position after bar i closes
    - returns[i] = return from bar i to bar i+1
    
    signal[i] * returns[i] = profit from holding position signal[i]
    
    Args:
        df: DataFrame with 'close' column or generic numeric column
        
    Returns:
        Array of forward-shifted log returns
    """
    # Determine column to use for returns
    target_col = 'close'
    if 'close' not in df.columns:
        # Try generic names
        for c in ['value', 'price', 'rate', 'v']:
            if c in df.columns:
                target_col = c
                break
        else:
             # Fallback: Use first numeric column
             nums = df.select_dtypes(include=[np.number]).columns
             if len(nums) > 0:
                 target_col = nums[0]
             else:
                 # If no numeric columns, return zeros (or raise?)
                 # Returning zeros is safer to avoid crashing the whole loop 
                 # for a non-tradable asset
                 return np.zeros(len(df))

    # Calculate Log Returns
    # Handle zeros/negatives for generic data?
    prices = df[target_col].values.astype(float)
    
    # Simple check for validity
    if len(prices) < 2:
        return np.zeros(len(prices))

    # Log returns require strictly positive values
    # If generic data has <= 0, fallback to pct_change (arithmetic) or diff?
    # For consistency with current logic, try log, else simple return
    if np.any(prices <= 0):
        # Fallback to simple percentage change: (p[i] - p[i-1]) / p[i-1] ?
        # Or simple diff? 
        # Strategy expects returns approx log returns. 
        # Let's use simple returns: (P[t+1]/P[t]) - 1 ~= log(P[t+1]/P[t])
        # But if P[t] is 0 or negative, this is also undefined/problematic.
        # If it's an indicator (like Volume or Sentiment), "returns" might mean "change"
        # Let's simple diff: prices[1:] - prices[:-1]
        # But that changes units.
        # Let's return Zeros if we can't compute valid returns, usually non-price assets don't generate PnL directly.
        # So returning 0s means "Neutral PnL from this asset".
        return np.zeros(len(prices))

    log_returns = np.log(prices[1:] / prices[:-1])
    
    # Shift forward: return[i] is the return AFTER bar i
    # We append NaN at the end since we don't know the future
    # Actually, we use 0.0 or NaN. The original code used np.empty + nan.
    returns = np.zeros(len(prices))
    returns[:-1] = log_returns
    returns[-1] = 0.0 # Use 0 instead of NaN to avoid issues? Original was NaN in memory, but code below handles NaNs?
    # Original: returns = np.empty... returns[-1] = np.nan
    # calc_sharpe_ratio: strat_returns = strat_returns[~np.isnan(strat_returns)]
    # So NaN is fine.
    
    returns[-1] = np.nan
    
    return returns
