import os
import pandas as pd
import numpy as np
import importlib.util
import sys
import logging
import asyncio
import itertools
from numba import njit
from .email_sender import send_sensitivity_email

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
    # Handle the first value of the window
    sma[period-1] = cs[period-1] / period 
    sma[period:] = cs_period / period
    return sma

@njit
def calculate_sharpe(returns):
    if len(returns) < 2:
        return 0.0
    mean_ret = np.mean(returns)
    std_ret = np.std(returns)
    if std_ret == 0:
        return 0.0
    # Annualized Sharpe (assuming daily)
    return np.sqrt(252) * mean_ret / std_ret

class SensitivityEngine:
    def __init__(self, upload_dir, data_filename, strategy_filename, initial_cash, parameters, class_name, mode='grid', distribution='uniform', iterations=1000, email=None):
        self.upload_dir = upload_dir
        self.data_path = os.path.join(upload_dir, data_filename)
        self.strategy_filename = strategy_filename
        self.strategy_path = os.path.join(upload_dir, strategy_filename) if strategy_filename else None
        self.initial_cash = initial_cash
        self.parameters = parameters
        self.class_name = class_name
        self.mode = mode
        self.distribution = distribution
        self.iterations = iterations
        self.email = email

    
    def load_data(self):
        # Local import to avoid circular dep if needed, or rely on top level
        from utils.csv_parser import load_market_data
        data_dict = load_market_data(self.data_path)
        
        # If single asset 'MAIN', unwrap for backwards compatibility checks
        # But for consistency, we return (data, is_multi)
        
        if len(data_dict) == 1 and 'MAIN' in data_dict:
             df = data_dict['MAIN']
             # Standard checks
             required = {'close'}
             if not required.issubset(df.columns):
                 raise ValueError(f"CSV must contain {required} columns")
             if 'open' not in df.columns: df['open'] = df['close']
             if 'high' not in df.columns: df['high'] = df['close']
             if 'low' not in df.columns: df['low'] = df['close']
             if 'volume' not in df.columns: df['volume'] = 0.0
             return df, False
             
        # Multi-Asset
        return data_dict, True

    def generate_parameter_grid(self):
        # parameters: {'p1': {'min': 10, 'max': 30, 'step': 10}, ...}
        keys = list(self.parameters.keys())
        
        if self.mode == 'grid':
            values_list = []
            for p in keys:
                config = self.parameters[p]
                # Add tiny epsilon to include max
                vals = np.arange(config['min'], config['max'] + (config['step'] / 1000.0), config['step'])
                values_list.append(vals)
            grid = list(itertools.product(*values_list))
            
        else: # mode == 'random'
            grid = []
            for _ in range(self.iterations):
                row = []
                for p in keys:
                    config = self.parameters[p]
                    
                    param_dist = config.get('distribution', self.distribution)
                    
                    if param_dist == 'normal':
                        # Normal Distribution
                        # Mean = (Max + Min) / 2
                        # Default Sigma = (Max - Min) / 6  (99.7% of values within range)
                        mean = (config['max'] + config['min']) / 2
                        default_sigma = (config['max'] - config['min']) / 6
                        sigma = config.get('sigma', default_sigma) # User specified noise
                        
                        val = np.random.normal(mean, sigma)
                    else:
                        # Uniform Distribution (Default)
                        val = np.random.uniform(config['min'], config['max'])
                    
                    # Quantize to step if step > 0 provided, else continuous
                    step = config.get('step', 0)
                    if step > 0:
                        val = round(val / step) * step
                        # Clamp to min/max just in case rounding pushes out
                        val = max(config['min'], min(config['max'], val))
                    
                    # If step suggests integer (e.g. 1.0, 5.0), cast to int? 
                    # Numba/Strategy might expect float, but usually safer to keep float
                    # unless we are sure. Let's keep as float, strategy can int() if needed.
                    row.append(val)
                grid.append(tuple(row))
                
        return keys, grid

    async def run(self, websocket):
        try:
            data_obj, is_multi_asset = self.load_data()
            
            # Setup Arrays for Loop
            if is_multi_asset:
                first_asset = list(data_obj.values())[0]
                dates = first_asset.index
                closes = np.zeros(len(dates)) # Dummy for loop length
                opens = np.zeros(len(dates))
                highs = np.zeros(len(dates))
                lows = np.zeros(len(dates))
                volumes = np.zeros(len(dates))
                # For checks requiring single series
            else:
                df = data_obj
                closes = df['close'].values.astype(np.float64)
                opens = df['open'].values.astype(np.float64)
                highs = df['high'].values.astype(np.float64)
                lows = df['low'].values.astype(np.float64)
                volumes = df['volume'].values.astype(np.float64)
                dates = df['date'].values if 'date' in df.columns else np.arange(len(closes))

            param_names, grid = self.generate_parameter_grid()
            total_runs = len(grid)
            
            # Dynamic Strategy Loading
            strategy_module = None
            if self.strategy_path and os.path.exists(self.strategy_path):
                spec = importlib.util.spec_from_file_location("user_strategy", self.strategy_path)
                strategy_module = importlib.util.module_from_spec(spec)
                sys.modules["user_strategy"] = strategy_module
                spec.loader.exec_module(strategy_module)

            # Precompute Indicators
            precomputed_data = None
            StrategyConfig = None
            if strategy_module and hasattr(strategy_module, '_prepare_vectorized_data'):
                try:
                    if is_multi_asset:
                        precomputed_data = strategy_module._prepare_vectorized_data(data_obj)
                    else:
                        precomputed_data = strategy_module._prepare_vectorized_data(
                            opens, highs, lows, closes, volumes
                        )
                    
                    if hasattr(strategy_module, 'StrategyConfig'):
                         StrategyConfig = strategy_module.StrategyConfig
                except Exception as e:
                     logger.warning(f"Failed to precompute indicators: {e}")

            # Send initial progress
            await websocket.send_json({
                "type": "progress", 
                "completed": 0, 
                "total": total_runs,
                "message": "Starting simulation..."
            })
            
            # Offload heavy computation to thread pool
            # NOTE: We lose real-time progress updates in this simple offload unless we use a queue/callback.
            # For now, let's just await the whole result to fix blocking. 
            # Ideally: pass a queue to _run_computation_grid and consume it here.
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, 
                self._run_computation_grid, 
                closes, opens, highs, lows, volumes,
                param_names, grid, strategy_module, StrategyConfig, precomputed_data,
                is_multi_asset
            )

            # The instruction provided a progress update block here, but it's syntactically incorrect
            # and functionally impossible to await from a separate thread.
            # The original comment about losing real-time updates is still valid for this structure.
            # To implement real-time progress, _run_computation_grid would need to send updates
            # via a queue that the main async loop monitors.
            # For now, we'll assume the progress update is meant for the final result.
            
            # Final result
            best_result_entry = None
            if results:
                 best_result_entry = max(results, key=lambda x: x['metrics']['sharpe'])

            await websocket.send_json({
                "type": "result",
                "data": {
                    "status": "success",
                    "results": results,
                    "best": best_result_entry,
                    "total_runs": len(results),
                    "param_names": param_names
                }
            })
            
            # Send Email
            if self.email and results:
                try:
                    best_result = max(results, key=lambda x: x['metrics']['sharpe'])
                    send_sensitivity_email(
                        recipient_email=self.email,
                        results=results,
                        param_names=param_names,
                        best_result=best_result,
                        total_runs=total_runs
                    )
                except Exception as e:
                    logger.error(f"Failed to send email: {e}")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "message": str(e)})

    def _run_computation_grid(self, closes, opens, highs, lows, volumes, param_names, grid, strategy_module, StrategyConfig, precomputed_data, is_multi_asset):
        results = []
        total_runs = len(grid)
        
        for idx, params_values in enumerate(grid):
            current_params = dict(zip(param_names, params_values))
            
            # Execute Strategy
            daily_returns = np.zeros(len(closes))
            
            if strategy_module:
                # Case 1: Optimized Precomputed Execution
                if precomputed_data is not None and hasattr(strategy_module, '_evaluate_vectorized_logic'):
                    try:
                        # Handle both namedtuple (_fields is tuple) and dataclass (@property _fields)
                        if hasattr(StrategyConfig, '__dataclass_fields__'):
                            valid_fields = tuple(StrategyConfig.__dataclass_fields__.keys())
                        elif hasattr(StrategyConfig, '_fields') and not isinstance(getattr(StrategyConfig, '_fields'), property):
                            valid_fields = StrategyConfig._fields
                        else:
                            # Fallback: try instantiating with defaults to get _fields
                            try:
                                valid_fields = StrategyConfig()._fields
                            except:
                                valid_fields = tuple(current_params.keys())
                        filtered_params = {k: v for k, v in current_params.items() if k in valid_fields}
                        cfg = StrategyConfig(**filtered_params)
                        
                        strat_ret = strategy_module._evaluate_vectorized_logic(precomputed_data, cfg)
                        
                        if isinstance(strat_ret, tuple):
                            daily_returns = strat_ret[1]
                        elif isinstance(strat_ret, np.ndarray):
                            # If it returns 'signal/position', we need to compute returns
                            positions = strat_ret
                            # Convert position signals to returns
                            price_returns = np.diff(closes) / closes[:-1]
                            price_returns = np.insert(price_returns, 0, 0) # 0 at start
                            
                            effective_pos = np.roll(positions, 1)
                            effective_pos[0] = 0
                            daily_returns = effective_pos * price_returns
                            
                    except Exception as e:
                        logger.error(f"Vectorized logic failed: {e}", exc_info=True)
                        pass

                # Case 2: Legacy Vectorized Function (_run_vectorized_backtest)
                elif hasattr(strategy_module, '_run_vectorized_backtest') and hasattr(strategy_module, 'StrategyConfig'):
                    try:
                        StrategyConfig = strategy_module.StrategyConfig
                        # Handle both namedtuple and dataclass with @property _fields
                        if hasattr(StrategyConfig, '__dataclass_fields__'):
                            valid_fields = tuple(StrategyConfig.__dataclass_fields__.keys())
                        elif hasattr(StrategyConfig, '_fields') and not isinstance(getattr(StrategyConfig, '_fields'), property):
                            valid_fields = StrategyConfig._fields
                        else:
                            try:
                                valid_fields = StrategyConfig()._fields
                            except:
                                valid_fields = tuple(current_params.keys())
                        filtered_params = {k: v for k, v in current_params.items() if k in valid_fields}
                        cfg = StrategyConfig(**filtered_params)
                        
                        strat_ret = strategy_module._run_vectorized_backtest(
                            opens, highs, lows, closes, volumes, cfg
                        )
                        
                        if isinstance(strat_ret, tuple):
                            daily_returns = strat_ret[1]
                        elif isinstance(strat_ret, np.ndarray):
                            positions = strat_ret
                            price_returns = np.diff(closes) / closes[:-1]
                            price_returns = np.insert(price_returns, 0, 0)
                            effective_pos = np.roll(positions, 1)
                            effective_pos[0] = 0
                            daily_returns = effective_pos * price_returns
                        
                    except Exception as e:
                        logger.error(f"Legacy vectorized logic failed: {e}", exc_info=True)
                        pass

                # Case 2: Standard run_strategy
                elif hasattr(strategy_module, 'run_strategy'):
                    try:
                        strategy_ret = strategy_module.run_strategy(closes, **current_params)
                        if isinstance(strategy_ret, (list, np.ndarray)):
                            daily_returns = strategy_ret
                    except Exception:
                        pass
            
            # Default (if no strategy matched or failed)
            if np.all(daily_returns == 0) and not strategy_module:
                if not is_multi_asset:
                    # Default Vectorized SMA Crossover (e.g. Fast vs Slow or Price vs SMA)
                    period = int(current_params.get('sma_period', 20))
                    sma = fast_sma(closes, period)
                    signals = np.where(closes > sma, 1.0, 0.0)
                    signals = np.roll(signals, 1) # Shift to avoid lookahead
                    signals[0] = 0
                    
                    # Calculate returns
                    # NOTE: Ensure price_returns are calculated same way as in strategy block
                    price_returns = np.diff(closes) / closes[:-1]
                    price_returns = np.insert(price_returns, 0, 0)
                    daily_returns = signals * price_returns
                else:
                    # No fallback for multi-asset
                    pass

            # Compute Metrics
            sharpe = calculate_sharpe(daily_returns)
            # Profit Factor? Total Return?
            total_return = np.prod(1 + daily_returns) - 1
            
            result_entry = {
                "id": idx,
                "params": current_params,
                "metrics": {
                    "sharpe": float(sharpe),
                    "total_return": float(total_return)
                }
            }
            results.append(result_entry)
            
        return results
