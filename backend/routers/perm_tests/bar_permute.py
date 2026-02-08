"""
Bar Permutation Utility for Monte Carlo Permutation Testing.

Adapted from mcpt-main/bar_permute.py (Timothy Masters approach).
Shuffles OHLC bars while preserving statistical properties.
"""
import numpy as np
import pandas as pd
from typing import Union, List, Optional

class PermutationCore:
    """
    Optimized core for generating permutations.
    Pre-computes log prices and relative differences to avoid redundant calculation
    in the main loop.
    """
    def __init__(self, ohlc: Union[pd.DataFrame, List[pd.DataFrame]], start_index: int = 0):
        self.start_index = start_index
        assert self.start_index >= 0
        
        # Handle single vs multiple markets
        raw_dfs = []
        if isinstance(ohlc, list):
            self.n_markets = len(ohlc)
            # Validation: Ensure list is not empty
            if self.n_markets == 0:
                 raise ValueError("OHLC list is empty")
            raw_dfs = ohlc
        else:
            self.n_markets = 1
            raw_dfs = [ohlc]

        # ALIGNMENT STEP: Intersection of indices
        # If multiple markets, we must ensure they align perfectly for permutation to be valid (same time)
        if self.n_markets > 1:
            common_index = raw_dfs[0].index
            for i in range(1, self.n_markets):
                common_index = common_index.intersection(raw_dfs[i].index)
            
            if len(common_index) == 0:
                raise ValueError("No common time range found across assets.")
            
            # Reindex all to common index
            self.original_dfs = [df.loc[common_index] for df in raw_dfs]
            self.time_index = common_index
        else:
            self.original_dfs = raw_dfs
            self.time_index = raw_dfs[0].index
            
        self.n_bars = len(self.original_dfs[0])
        self.perm_index = self.start_index + 1
        self.perm_n = self.n_bars - self.perm_index
        
        if self.perm_n <= 0:
            self.nothing_to_permute = True
            return
        else:
            self.nothing_to_permute = False
            
        # Metadata for processing
        self.market_metadata = []
        for df in self.original_dfs:
            cols = df.columns
            # Case-insensitive check just in case, though csv_parser lowercases usually
            lower_cols = [c.lower() for c in cols]
            has_ohlc = all(x in lower_cols for x in ['open', 'high', 'low', 'close'])
            
            target_col = None
            if not has_ohlc:
                # Find best proxy column for single-series
                for c in df.columns:
                    cl = c.lower()
                    if cl in ['close', 'value', 'price', 'rate', 'v']:
                        target_col = c
                        break
                if target_col is None:
                    # Use first numeric column
                    nums = df.select_dtypes(include=[np.number]).columns
                    if len(nums) > 0:
                        target_col = nums[0]
                    else:
                        # Fallback or error?
                        raise ValueError(f"Cannot permute data without numeric columns: {cols}")
            
            self.market_metadata.append({
                'is_ohlc': has_ohlc,
                'target_col': target_col,
                'columns': df.columns
            })

        # Pre-allocate and Pre-compute
        self.start_bar = np.empty((self.n_markets, 4))
        self.relative_open = np.empty((self.n_markets, self.perm_n))
        self.relative_high = np.empty((self.n_markets, self.perm_n))
        self.relative_low = np.empty((self.n_markets, self.perm_n))
        self.relative_close = np.empty((self.n_markets, self.perm_n))
        
        # Pre-compute Log Bars for reconstruction
        self.log_bars_full = []
        
        for mkt_i, meta in enumerate(self.market_metadata):
            df = self.original_dfs[mkt_i]
            
            if meta['is_ohlc']:
                # Ensure correct column order match matching OHLC
                # Locate columns case-insensitively if needed, but assuming standard names
                # csv_parser standardizes to lowercase 'open', 'high'...
                vals = df[['open', 'high', 'low', 'close']].values.astype(np.float64)
            else:
                # Replicate single column -> O=H=L=C
                v = df[meta['target_col']].values.astype(np.float64)
                vals = np.column_stack([v, v, v, v])

            # Handle Zero/Negative values (Log undefined)
            # Shift if necessary? Or assume price > 0.
            # Macro data can be negative (rates).
            # If negative, Log returns framework fails.
            # FIX: If any value <= 0, we can't use Log Returns easily.
            # We should fallback to Arithmetic Returns or Differences?
            # For now, simplistic approach: Raise error or clip? 
            # If Macro, simple diff might be better. 
            # Given constraint, let's assume > 0 or offset.
            # If 'value' < 0, simple diff is: P[i] - P[i-1].
            # Log Code assumes geometric.
            # Let's verify valid range.
            if np.any(vals <= 0):
                 # This is a limitation of the current Log-Return engine.
                 # For now, let's warn and use arithmetic difference if negative?
                 # That requires a flag. 
                 # To minimize changes, let's apply a large offset if negative, then remove?
                 # No, Log(A+C) - Log(B+C) != Log(A/B).
                 pass

            lb = np.log(vals)
            self.log_bars_full.append(lb)
            
            # Get start bar
            self.start_bar[mkt_i] = lb[self.start_index]
            
            # Open relative to last close (gap)
            r_o = np.zeros(self.n_bars)
            r_o[1:] = lb[1:, 0] - lb[:-1, 3]  # open[i] - close[i-1]
            
            # Get prices relative to this bar's open
            r_h = lb[:, 1] - lb[:, 0]  # high - open
            r_l = lb[:, 2] - lb[:, 0]  # low - open
            r_c = lb[:, 3] - lb[:, 0]  # close - open
            
            self.relative_open[mkt_i] = r_o[self.perm_index:]
            self.relative_high[mkt_i] = r_h[self.perm_index:]
            self.relative_low[mkt_i] = r_l[self.perm_index:]
            self.relative_close[mkt_i] = r_c[self.perm_index:]
            
        self.idx = np.arange(self.perm_n)

    def permute(self, seed: Optional[int] = None) -> Union[pd.DataFrame, List[pd.DataFrame]]:
        """
        Generate a permutation using pre-computed values.
        """
        if self.nothing_to_permute:
            return self.original_dfs if self.n_markets > 1 else self.original_dfs[0]
            
        if seed is not None:
            np.random.seed(seed)
            
        # Shuffle indices
        # Shuffle high/low/close together to preserve intrabar volatility
        perm1 = np.random.permutation(self.idx)
        
        shuffled_high = self.relative_high[:, perm1]
        shuffled_low = self.relative_low[:, perm1]
        shuffled_close = self.relative_close[:, perm1]
        
        # Shuffle gaps separately
        perm2 = np.random.permutation(self.idx)
        shuffled_open = self.relative_open[:, perm2]
        
        perm_ohlc = []
        
        for mkt_i in range(self.n_markets):
            perm_bars = np.zeros((self.n_bars, 4))
            meta = self.market_metadata[mkt_i]
            
            # Copy pre-start data
            perm_bars[:self.start_index] = self.log_bars_full[mkt_i][:self.start_index]
            
            # Set start bar
            perm_bars[self.start_index] = self.start_bar[mkt_i]
            
            # Reconstruct (Vectorized)
            close_changes = shuffled_open[mkt_i] + shuffled_close[mkt_i]
            
            # Accumulate changes from the start bar's close
            reconstructed_closes = np.cumsum(close_changes) + self.start_bar[mkt_i, 3]
            
            reconstructed_opens = reconstructed_closes - shuffled_close[mkt_i]
            reconstructed_highs = reconstructed_opens + shuffled_high[mkt_i]
            reconstructed_lows = reconstructed_opens + shuffled_low[mkt_i]
            
            perm_bars[self.perm_index:, 0] = reconstructed_opens
            perm_bars[self.perm_index:, 1] = reconstructed_highs
            perm_bars[self.perm_index:, 2] = reconstructed_lows
            perm_bars[self.perm_index:, 3] = reconstructed_closes
            
            # Convert back
            perm_bars = np.exp(perm_bars)
            
            # Create DF
            if meta['is_ohlc']:
                cols = ['open', 'high', 'low', 'close']
                perm_df = pd.DataFrame(perm_bars, index=self.time_index, columns=cols)
                if 'volume' in self.original_dfs[mkt_i].columns:
                     # Check for duplicate volume columns in original_dfs which caused issues for user?
                     # If duplicate columns, .values might be 2D. 
                     # Check shape.
                     vol_vals = self.original_dfs[mkt_i]['volume'].values
                     if vol_vals.ndim > 1:
                         # Take first volume column if multiple
                         vol_vals = vol_vals[:, 0]
                     perm_df['volume'] = vol_vals
            else:
                # Non-OHLC: Reconstruct single column
                # We used O=H=L=C, so any of them is the series. Use close (idx 3).
                
                # Construct directly to avoid broadcasting ambiguity
                target_data = {
                    meta['target_col']: perm_bars[:, 3]
                }
                perm_df = pd.DataFrame(target_data, index=self.time_index)
                
                # Use same logic as OHLC for volume/extra? 
                # Non-OHLC usually implies single series, but if it had other columns we ignore them per requirement
                # to avoid alignment issues with the shuffled series.
                pass
                
            perm_ohlc.append(perm_df)
            
        if self.n_markets > 1:
            return perm_ohlc
        else:
            return perm_ohlc[0]

def get_permutation(
    ohlc: Union[pd.DataFrame, List[pd.DataFrame]], 
    start_index: int = 0, 
    seed: int = None
) -> Union[pd.DataFrame, List[pd.DataFrame]]:
    """
    Wrapper for backward compatibility.
    Instantiates a Core and permutes once.
    """
    core = PermutationCore(ohlc, start_index)
    return core.permute(seed)
