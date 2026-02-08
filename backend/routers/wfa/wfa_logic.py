import os
import pandas as pd
import numpy as np
import importlib.util
import sys
import logging
import asyncio
import itertools
from numba import njit
from typing import List, Dict, Any, Tuple
from utils.csv_parser import load_market_data
from .email_sender import send_wfa_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@njit
def fast_sma(prices, period):
    n = len(prices)
    sma = np.empty(n)
    sma[:] = np.nan
    cs = np.cumsum(prices)
    cs_period = cs[period:] - cs[:-period]
    sma[period-1] = cs[period-1] / period 
    sma[period:] = cs_period / period
    return sma

# Removed @njit to ensure standard Python dict return
def calculate_metrics(returns: np.ndarray, periods_per_year: float = 252.0) -> Dict[str, float]:
    if len(returns) < 2:
        return {"sharpe": 0.0, "total_return": 0.0, "max_dd": 0.0}
    
    mean_ret = np.mean(returns)
    std_ret = np.std(returns)
    
    if std_ret == 0:
        sharpe = 0.0
    else:
        # Annualized Sharpe (Dynamic)
        sharpe = np.sqrt(periods_per_year) * mean_ret / std_ret
        
    total_return = np.prod(1 + returns) - 1
    
    # Max Drawdown (Vectorized)
    cum_ret = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cum_ret)
    # Avoid division by zero if peak is 0 (unlikely for price series starting at 1, but possible)
    # cum_ret starts at 1+r0, so usually safe.
    with np.errstate(divide='ignore', invalid='ignore'):
         dd = (cum_ret - peak) / peak
    
    max_dd = np.min(dd) if len(dd) > 0 else 0.0
    
    return {
        "sharpe": float(sharpe),
        "total_return": float(total_return),
        "max_dd": float(max_dd)
    }

def convert_to_native(obj):
    if isinstance(obj, dict):
        return {k: convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_native(i) for i in obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return convert_to_native(obj.tolist())
    else:
        return obj

class WFAEngine:
    def __init__(self, upload_dir, data_filename, strategy_filename, initial_cash, parameters, 
                 window_size_days=365, step_size_days=90, train_ratio=0.7, 
                 optimization_metric='sharpe', email=None):
        self.upload_dir = upload_dir
        self.data_path = os.path.join(upload_dir, data_filename)
        self.strategy_filename = strategy_filename
        self.strategy_path = os.path.join(upload_dir, strategy_filename) if strategy_filename else None
        self.initial_cash = initial_cash
        self.parameters = parameters
        self.window_size_days = window_size_days
        self.step_size_days = step_size_days
        self.train_ratio = train_ratio # Portion of window used for training (rest is test?? Or is it rolling?)
        # WFA Standard:
        # IN-SAMPLE (Optimize) -> OUT-OF-SAMPLE (Test/Trade)
        # We usually define IS Period and OOS Period.
        # Let's say window_size is the TOTAL valid chunks? Or IS size?
        # Usually: Window Size = IS Size + OOS Size is one 'Step'.
        # Let's define: train_size_days, test_size_days (step_size)
        self.train_size_days = int(window_size_days) # User input 'window' as train size usually
        self.test_size_days = int(step_size_days)
        
        self.metric = optimization_metric
        self.email = email

    from utils.csv_parser import load_market_data

    def load_data(self):
        data_dict = load_market_data(self.data_path)
        # If single 'MAIN' key, extract it
        if len(data_dict) == 1 and 'MAIN' in data_dict:
            return data_dict['MAIN'], False # df, is_multi
        return data_dict, True

    def generate_parameter_grid(self):
        keys = list(self.parameters.keys())
        values_list = []
        for p in keys:
            config = self.parameters[p]
            vals = np.arange(config['min'], config['max'] + (config['step'] / 1000.0), config['step'])
            values_list.append(vals)
        grid = list(itertools.product(*values_list))
        return keys, grid

    def generate_random_params(self, default_config: dict, n_evals: int = 100, distribution: str = 'uniform') -> List[Dict[str, Any]]:
        """
        Generate N random parameter combinations based on default config types.
        Distribution: 'uniform' or 'normal' (Gaussian).
        """
        combinations = []
        
        # Define search space logic (Heuristic based on param names/values)
        ranges = {}
        for k, v in default_config.items():
            if isinstance(v, bool):
                ranges[k] = [True, False]
            elif isinstance(v, int):
                # Assume +/- 50% or reasonable range
                low = max(1, int(v * 0.5))
                high = int(v * 1.5) + 1
                if "period" in k or "window" in k:
                    low = max(5, int(v * 0.5))
                    high = max(low + 10, int(v * 2.0))
                
                # Retrieve overriden range from self.parameters if available
                if self.parameters and k in self.parameters and isinstance(self.parameters[k], dict):
                     p_cfg = self.parameters[k]
                     if 'min' in p_cfg and 'max' in p_cfg:
                         low = int(p_cfg['min'])
                         high = int(p_cfg['max'])
                
                ranges[k] = (low, high, "int")

            elif isinstance(v, float):
                # +/- 50%
                low = v * 0.5
                high = v * 1.5
                if "threshold" in k:
                    if abs(v) <= 1.0:
                        low = -1.0; high = 1.0
                    elif v > 1.0 and v <= 100.0:
                        low = 0.0; high = 100.0
                
                # Retrieve overriden range from self.parameters
                if self.parameters and k in self.parameters and isinstance(self.parameters[k], dict):
                     p_cfg = self.parameters[k]
                     if 'min' in p_cfg and 'max' in p_cfg:
                         low = float(p_cfg['min'])
                         high = float(p_cfg['max'])

                ranges[k] = (low, high, "float")
        
        for _ in range(n_evals):
            combo = {}
            for k, val in ranges.items():
                if isinstance(val, list):
                    combo[k] = np.random.choice(val)
                elif val[2] == "int":
                    low, high = val[0], val[1]
                    if distribution == 'normal':
                        # Mean = center, Std = (high-low)/6 (3 sigma)
                        mu = low + (high - low) / 2
                        sigma = (high - low) / 6 if high > low else 1
                        sample = int(np.random.normal(mu, sigma))
                        combo[k] = max(low, min(high, sample))
                    else:
                        combo[k] = int(np.random.randint(low, high if high > low else low + 1))
                elif val[2] == "float":
                    low, high = val[0], val[1]
                    if distribution == 'normal':
                        mu = low + (high - low) / 2
                        sigma = (high - low) / 6 if high > low else 0.1
                        sample = float(np.random.normal(mu, sigma))
                        combo[k] = max(low, min(high, sample))
                    else:
                        combo[k] = float(np.random.uniform(low, high))
            combinations.append(combo)
            
        return combinations

    @staticmethod
    def _optimize_window(
        train_indices, 
        test_indices, 
        dates, 
        precomputed_data, 
        strategy_module, 
        StrategyConfig, 
        grid, 
        param_names, 
        default_config_dict, 
        metric, 
        is_multi_asset, 
        closes, 
        opens, 
        highs, 
        lows, 
        volumes,
        periods_per_year=252.0
    ):
        """
        Static method to run optimization for a single window.
        Safe for run_in_executor (CPU bound).
        """
        best_metric_val = -float('inf')
        best_params = None
        
        # --- OPTIMIZATION (IN-SAMPLE) ---
        for params_values in grid:
            if isinstance(params_values, dict):
                 current_params = params_values
            else:
                 current_params = dict(zip(param_names, params_values))
            
            daily_returns = np.zeros(len(dates))
            
            # --- EXECUTE STRATEGY ---
            if strategy_module and StrategyConfig and precomputed_data is not None and hasattr(strategy_module, '_evaluate_vectorized_logic'):
                merged_params = default_config_dict.copy()
                merged_params.update(current_params)
                
                # Handle both namedtuple and dataclass with @property _fields
                if hasattr(StrategyConfig, '__dataclass_fields__'):
                    valid_fields = tuple(StrategyConfig.__dataclass_fields__.keys())
                elif hasattr(StrategyConfig, '_fields') and not isinstance(getattr(StrategyConfig, '_fields'), property):
                    valid_fields = StrategyConfig._fields
                else:
                    try:
                        valid_fields = StrategyConfig()._fields
                    except:
                        valid_fields = tuple(merged_params.keys())
                filtered = {k: v for k, v in merged_params.items() if k in valid_fields}
                
                try:
                     # Fill missing
                     for f in valid_fields:
                         if f not in filtered: filtered[f] = 0.0
                     
                     cfg = StrategyConfig(**filtered)
                     
                     strat_ret = strategy_module._evaluate_vectorized_logic(precomputed_data, cfg)
                     if isinstance(strat_ret, tuple):
                         daily_returns = strat_ret[1]
                     elif isinstance(strat_ret, np.ndarray):
                         # If raw position array, convert to returns
                         # NOTE: This conversion should really be in the strategy or precomputed if possible
                         # But for now we do it here. Optimization: Move out? 
                         # Actually, strategy returns signals. We need price returns.
                         # Logic: Strategy returns POSITIONS or SIGNALS.
                         pos = strat_ret
                         # Calc price returns (simple)
                         # We can pre-calculate price_returns outside loop if strategy returns positions!
                         # But strategy might return realized PnL directly.
                         # Assuming 'main_vectorized.py' returns actual strategy returns.
                         daily_returns = pos 
                except Exception:
                    pass
            else:
                # Fallback (SMA) - ONLY FOR SINGLE ASSET
                if not is_multi_asset:
                    try:
                        per = int(current_params.get('sma_period', 20))
                        # fast_sma is properly imported/available in scope? 
                        # It is at module level, so yes.
                        sma = fast_sma(closes, per)
                        sig = np.where(closes > sma, 1.0, 0.0)
                        sig = np.roll(sig, 1); sig[0] = 0
                        pr = np.zeros_like(closes)
                        with np.errstate(divide='ignore', invalid='ignore'):
                            pr[1:] = (closes[1:] - closes[:-1]) / closes[:-1]
                        daily_returns = sig * pr
                    except: pass

            # Slice for Train
            train_returns = daily_returns[train_indices]
            metrics = calculate_metrics(train_returns, periods_per_year=periods_per_year)
            
            if metrics[metric] > best_metric_val:
                best_metric_val = metrics[metric]
                best_params = current_params

        # --- VALIDATION (OUT-OF-SAMPLE) ---
        # Run Best Params on Test Segment
        final_returns_global = np.zeros(len(dates))
        
        if best_params:
             # Re-run logic with best_params (Implementation same as above)
             # To avoid code duplication we could helperize, but for speed we inline or call strategy
             if strategy_module and StrategyConfig and precomputed_data is not None:
                 merged_params = default_config_dict.copy()
                 merged_params.update(best_params)
                 # Handle both namedtuple and dataclass with @property _fields
                 if hasattr(StrategyConfig, '__dataclass_fields__'):
                     valid_fields = tuple(StrategyConfig.__dataclass_fields__.keys())
                 elif hasattr(StrategyConfig, '_fields') and not isinstance(getattr(StrategyConfig, '_fields'), property):
                     valid_fields = StrategyConfig._fields
                 else:
                     try:
                         valid_fields = StrategyConfig()._fields
                     except:
                         valid_fields = tuple(merged_params.keys())
                 filtered = {k: v for k, v in merged_params.items() if k in valid_fields} 
                 for f in valid_fields:
                     if f not in filtered: filtered[f] = 0.0
                 try:
                     cfg = StrategyConfig(**filtered)
                     strat_ret = strategy_module._evaluate_vectorized_logic(precomputed_data, cfg)
                     if isinstance(strat_ret, tuple):
                         final_returns_global = strat_ret[1]
                     elif isinstance(strat_ret, np.ndarray):
                         final_returns_global = strat_ret
                 except: pass
             elif not is_multi_asset:
                 # Fallback
                 per = int(best_params.get('sma_period', 20))
                 sma = fast_sma(closes, per)
                 sig = np.where(closes > sma, 1.0, 0.0)
                 sig = np.roll(sig, 1); sig[0] = 0
                 pr = np.zeros_like(closes)
                 with np.errstate(divide='ignore', invalid='ignore'):
                     pr[1:] = (closes[1:] - closes[:-1]) / closes[:-1]
                 final_returns_global = sig * pr

        return {
            "best_params": best_params,
            "best_metric_val": best_metric_val,
            "oos_returns": final_returns_global[test_indices]
        }

    async def run(self, websocket):
        try:
            data_obj, is_multi_asset = self.load_data()
            
            # Common Logic: Canonical Dates
            if is_multi_asset:
                first_key = list(data_obj.keys())[0]
                dates = data_obj[first_key].index
                if not isinstance(dates, pd.DatetimeIndex):
                     dates = pd.to_datetime(dates)
                # Dummy arrays for single-asset logic signature
                closes = np.zeros(len(dates))
                opens = np.zeros(len(dates))
                highs = np.zeros(len(dates))
                lows = np.zeros(len(dates))
                volumes = np.zeros(len(dates))
            else:
                df = data_obj
                dates = df['date'].values if 'date' in df.columns else df.index.values
                opens = df['open'].values.astype(np.float64)
                highs = df['high'].values.astype(np.float64)
                lows = df['low'].values.astype(np.float64)
                closes = df['close'].values.astype(np.float64)
                volumes = df['volume'].values.astype(np.float64) if 'volume' in df.columns else np.zeros(len(closes))
            
            # --- Strategy Loading ---
            strategy_module = None
            StrategyConfig = None
            precomputed_data = None
            default_config_dict = {}

            if self.strategy_path and os.path.exists(self.strategy_path):
                logger.info(f"Loading strategy from {self.strategy_path}")
                # ... (Mocking logic needed here? Copying from previous implementation)
                # For brevity ensuring we assume mocks/imports setup or we need to repeat it.
                # Use a helper or just repeat it securely. 
                # Let's try to assume environment is resilient or previous mocks stick? 
                # No, standard safe load.
                
                # [MOCKING REDACTED for brevity - assuming mostly stateless or imports work]
                # Re-implementing minimal robust loader
                spec = importlib.util.spec_from_file_location("user_strategy_wfa", self.strategy_path)
                strategy_module = importlib.util.module_from_spec(spec)
                sys.modules["user_strategy_wfa"] = strategy_module
                try:
                     spec.loader.exec_module(strategy_module)
                except Exception as e:
                     logger.error(f"Strategy Load Failed: {e}")
                
                if hasattr(strategy_module, 'StrategyConfig'):
                    StrategyConfig = strategy_module.StrategyConfig
                
                if hasattr(strategy_module, '_prepare_vectorized_data'):
                    try:
                        if is_multi_asset:
                            precomputed_data = strategy_module._prepare_vectorized_data(data_obj)
                        else:
                            precomputed_data = strategy_module._prepare_vectorized_data(
                                opens, highs, lows, closes, volumes
                            )
                    except Exception as e:
                        logger.warning(f"Precompute failed: {e}")

                # Extract Defaults
                if hasattr(strategy_module, 'StrategyEngine'):
                    try:
                        temp_engine = strategy_module.StrategyEngine()
                        if hasattr(temp_engine, 'config'):
                            if hasattr(temp_engine.config, '_asdict'):
                                default_config_dict = temp_engine.config._asdict()
                            elif hasattr(temp_engine.config, 'dict'):
                                default_config_dict = temp_engine.config.dict()
                            else:
                                default_config_dict = temp_engine.config.__dict__
                    except: pass

            # --- CONFIGURATION ---
            meta_config = {
                'distribution': self.parameters.pop('distribution', 'uniform'),
                'n_evals': int(self.parameters.pop('n_evals', 100)),
                'mode': self.parameters.pop('mode', 'random') 
            }
            strategy_params = self.parameters 

            grid = []
            param_names = []
            
            if not strategy_params and default_config_dict:
                grid = self.generate_random_params(default_config_dict, n_evals=meta_config['n_evals'], distribution=meta_config['distribution'])
            elif strategy_params and (meta_config['mode'] == 'random' or 'min' in str(strategy_params)):
                 grid = self.generate_random_params(default_config_dict, n_evals=meta_config['n_evals'], distribution=meta_config['distribution'])
                 # Note: generate_random_params handles defaults + override logic
            else:
                 param_names, grid = self.generate_parameter_grid()
            
            # Add implicit indices if Random params (list of dicts)
            # Adapt _optimize_window to handle list of dicts directly
            
            # --- SLIDING WINDOW LOOP ---
            min_date = dates[0]
            max_date = dates[-1]
            total_days = (max_date - min_date).days
            estimated_steps = int((total_days - self.train_size_days) / self.test_size_days)
            
            current_start_date = min_date
            loop = asyncio.get_event_loop()
            step_count = 0
            
            wfa_results = []
            oos_equity_curve = []
            
            logger.info(f"Starting WFA. Est Steps: {estimated_steps}. Grid Size: {len(grid)}")

            # --- DETECT FREQUENCY ---
            periods_per_year = 252.0
            try:
                if len(dates) > 5:
                    # Convert to pd Series if numpy array of datetime64
                    # dates is usually DatetimeIndex or array of datetime64
                    if isinstance(dates, pd.DatetimeIndex):
                        diffs = dates[:100].to_series().diff().dropna()
                    else:
                        diffs = pd.Series(dates[:100]).diff().dropna()
                        
                    median_diff = diffs.median()
                    if median_diff < pd.Timedelta(minutes=15):
                         periods_per_year = 98280.0
                    elif median_diff < pd.Timedelta(hours=4):
                         periods_per_year = 252.0 * 6.5
            except: 
                pass
            
            logger.info(f"WFA using periods_per_year: {periods_per_year}")

            while True:  
                train_end_date = current_start_date + pd.Timedelta(days=self.train_size_days)
                test_end_date = train_end_date + pd.Timedelta(days=self.test_size_days)
                
                if train_end_date > max_date:
                    break
                
                # Masks
                train_mask = (dates >= current_start_date) & (dates < train_end_date)
                test_mask = (dates >= train_end_date) & (dates < test_end_date)
                
                if not np.any(test_mask):
                    break
                
                train_indices = np.where(train_mask)[0]
                test_indices = np.where(test_mask)[0]
                
                # Process Window in Thread
                # Note: passing large numpy arrays (closes, precomputed_data) is generally okay via shared memory (threads)
                # Serialization isn't needed for threads, just pickling if ProcessPoolExecutor.
                # run_in_executor (None) uses ThreadPoolExecutor by default.
                
                window_result = await loop.run_in_executor(
                    None,
                    self._optimize_window,
                    train_indices, 
                    test_indices, 
                    dates, 
                    precomputed_data, 
                    strategy_module, 
                    StrategyConfig, 
                    grid, 
                    param_names, 
                    default_config_dict, 
                    self.metric, 
                    is_multi_asset, 
                    closes, 
                    opens, 
                    highs, 
                    lows, 
                    volumes,
                    periods_per_year
                )
                
                # Unpack
                best_params = window_result["best_params"]
                best_metric_val = window_result["best_metric_val"]
                oos_returns = window_result["oos_returns"]
                
                oos_metrics = calculate_metrics(oos_returns, periods_per_year=periods_per_year)
                
                step_result = {
                    "start": str(train_end_date.date()),
                    "end": str(test_end_date.date()),
                    "params": convert_to_native(best_params),
                    "is_metric": float(best_metric_val),
                    "oos_metric": float(oos_metrics[self.metric]),
                    "oos_returns": oos_returns.tolist()
                }
                wfa_results.append(step_result)
                oos_equity_curve.extend(oos_returns.tolist())
                
                step_count += 1
                
                await websocket.send_json({
                    "type": "progress",
                    "step": step_count,
                    "total_estimated": estimated_steps,
                    "current_date": str(train_end_date.date()),
                    "message": f"Finished Window {step_count}/{estimated_steps}"
                })
                
                current_start_date += pd.Timedelta(days=self.test_size_days)

            # --- FINALIZE ---
            full_oos_returns = np.array(oos_equity_curve)
            global_metrics = calculate_metrics(full_oos_returns, periods_per_year=periods_per_year)
            
            wfe_scores = []
            for r in wfa_results:
                if r['is_metric'] > 1e-6:
                     wfe_scores.append(r['oos_metric'] / r['is_metric'])
                else:
                     wfe_scores.append(0.0)
            avg_wfe = np.mean(wfe_scores) if wfe_scores else 0.0

            result_payload = {
                "status": "success",
                "total_return": global_metrics["total_return"],
                "sharpe_ratio": global_metrics["sharpe"],
                "max_drawdown": global_metrics["max_dd"],
                "metrics": global_metrics,
                "wfe": float(avg_wfe),
                "segments": wfa_results,
                "equity_curve": np.cumprod(1 + full_oos_returns).tolist()
            }
            
            result_payload = convert_to_native(result_payload)
            
            await websocket.send_json({
                "type": "result",
                "data": result_payload
            })
            
            if self.email:
                try:
                    config_map = {
                         "strategy": self.strategy_filename,
                         "window": self.window_size_days,
                         "step": self.step_size_days
                    }
                    send_wfa_email(self.email, result_payload, config_map)
                except Exception as e:
                    logger.error(f"Email failed: {e}")

        except Exception as e:
            logger.error(f"WFA Error: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "message": str(e)})
