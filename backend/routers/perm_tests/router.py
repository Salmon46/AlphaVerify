"""
FastAPI Backend for AlphaVerify Permutation Testing.
Exposes REST API for file upload, strategy configuration, and permutation test execution.
Uses vectorized signal generation for fast permutation testing.
"""
import logging
import time
import os
import numpy as np
import io
import shutil
import json
import asyncio
import importlib.util
import sys
import pandas as pd
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from .stats import analyze_permutation_results, PermutationTestResult
from .report_generator import generate_pdf_report
from .email_sender import send_permutation_report
from .bar_permute import get_permutation, PermutationCore
from .metrics import calc_profit_factor, calc_sharpe_ratio, prepare_returns
from utils.csv_parser import load_market_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/perm-tests",
    tags=["perm-tests"]
)

# Directories
UPLOAD_DIR = os.path.join(os.getcwd(), "temp_perm_upload")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Thread pool for CPU-bound tasks
executor = ThreadPoolExecutor(max_workers=4)

class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="2.0.0")

@router.post("/upload-files")
async def upload_files(
    data_file: UploadFile = File(...),
    strategy_file: UploadFile = File(...),
):
    """Upload files and return their temp paths for the subsequent WebSocket run."""
    
    # Save uploaded files to temp dir
    timestamp = int(time.time())
    data_filename = f"{timestamp}_{data_file.filename}"
    strat_filename = f"{timestamp}_{strategy_file.filename}"
    
    data_path = Path(UPLOAD_DIR) / data_filename
    strat_path = Path(UPLOAD_DIR) / strat_filename
    
    with open(data_path, "wb") as f:
        shutil.copyfileobj(data_file.file, f)
    
    with open(strat_path, "wb") as f:
        shutil.copyfileobj(strategy_file.file, f)
        
    return {
        "data_filename": data_filename,
        "strategy_filename": strat_filename
    }

# --- Helper Logic moved outside to run in Executor ---

def run_permutation_loop(
    n_permutations: int,
    original_score: float,
    metric: str,
    strategy_instance: Any,
    permutation_core: PermutationCore,
    is_multi_asset: bool,
    data_obj_reference: Any, # Needed to reconstruct dict structure for strategy
    periods_per_year: float = 252.0
):
    """
    CPU-bound permutation loop.
    Returns (permuted_scores, perm_better_count).
    """
    permuted_scores = []
    perm_better_count = 0
    
    for i in range(n_permutations):
        # 1. Generate Permutation (Fast)
        perm_result = permutation_core.permute(seed=i)
        
        # 2. Reconstruct Input for Strategy
        if is_multi_asset:
             # perm_result is a list of DFs. We need to map it back to dict keys.
             # Assumes PermutationCore maintained order of sorted keys or logic below matches
             # PermutationCore stores original_dfs list.
             # We need to know the keys.
             keys = sorted(data_obj_reference.keys())
             perm_input = {k: v for k, v in zip(keys, perm_result)}
             
             # Calculate Returns for Metric
             perm_returns = {k: prepare_returns(v) for k, v in perm_input.items()}
             
        else:
             perm_input = perm_result # Single DF
             perm_returns = prepare_returns(perm_input)
        
        # 3. Get Signal/Returns from Strategy
        # Strategy now returns 'strategy_returns' directly in recent update
        # OR returns signal. We need to handle both if we claim backward compat, 
        # but realistically we expect the new interface.
        
        perm_output = strategy_instance.generate_signal(perm_input)
        
        # 4. Calculate Metric
        perm_score = 0.0
        
        # Unified Metric Logic
        # If perm_output is already returns (1D array), we use it. 
        # If it's signals, we need perm_returns.
        
        if isinstance(perm_output, tuple):
             # (signals, returns)
             sig, ret = perm_output
             # if ret is not empty, use it
             if ret is not None and len(ret) > 0:
                 target_returns = ret
             else:
                 # Calculate from signal? Complex. Assumes strategy handles it.
                 # Fallback: Strategy MUST return strategy returns for multi-asset
                 target_returns = np.array([])
        else:
             # Just returns or just signal?
             # SMA Vectorized now returns STRATEGY RETURNS.
             target_returns = perm_output
             
        # Checking validity
        if len(target_returns) == 0:
             # Skip or error?
             permuted_scores.append(0.0) # Penalty
             continue
             
        if metric == 'profit_factor':
            # This needs raw trades ideally, but approx via returns
            # PF = Sum(Pos Returns) / Sum(Neg Returns)
            # Strategy returns are per-bar PnL % essentially (or log returns)
            # This is an approximation.
            gains = target_returns[target_returns > 0].sum()
            losses = abs(target_returns[target_returns < 0].sum())
            if losses == 0:
                perm_score = 100.0 if gains > 0 else 0.0
            else:
                perm_score = gains / losses
                
        else: # Sharpe
            perm_score = calc_sharpe_ratio(None, target_returns, periods_per_year=periods_per_year)
            
        permuted_scores.append(perm_score)
        
        if perm_score >= original_score:
            perm_better_count += 1
            
    return permuted_scores, perm_better_count


@router.websocket("/ws/run-permutation-test")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for running vectorized permutation tests.
    """
    await websocket.accept()
    
    temp_dir = Path(UPLOAD_DIR)
    
    try:
        # 1. Receive Configuration
        config_msg = await websocket.receive_text()
        config = json.loads(config_msg)
        
        data_filename = config['data_filename']
        strategy_filename = config['strategy_filename']
        email = config['email']
        n_permutations = int(config['n_permutations'])
        metric = config.get('metric', 'sharpe')
        
        data_path = temp_dir / data_filename
        strat_path = temp_dir / strategy_filename
        
        if not data_path.exists() or not strat_path.exists():
            await websocket.send_json({"type": "error", "message": "Uploaded files not found."})
            await websocket.close()
            return
        
        # 2. Load Data
        logger.info(f"Loading data from {data_path}")
        # 2. Load Data
        logger.info(f"Loading data from {data_path}")
        data_obj = load_market_data(str(data_path))
        is_multi_asset = len(data_obj) > 1 or 'MAIN' not in data_obj
        
        # Prepare for PermutationCore & Align Data
        if is_multi_asset:
             # Sort keys to ensure deterministic order
             keys = sorted(data_obj.keys())
             
             # AUTO-ALIGNMENT LOGIC
             # Identify "Anchor" asset (highest frequency/most rows) to prevent shrinking to sparse macro data
             # IF we have > 10x difference in row counts, assume sparse data needs padding.
             
             # Find asset with max rows
             max_len = 0
             anchor_key = None
             for k in keys:
                 if len(data_obj[k]) > max_len:
                     max_len = len(data_obj[k])
                     anchor_key = k
                     
             if anchor_key:
                 anchor_df = data_obj[anchor_key]
                 # Realign others to anchor
                 for k in keys:
                     if k == anchor_key: continue
                     
                     df = data_obj[k]
                     # If significant length mismatch (e.g. macro data is 3 rows, market is 18k)
                     if len(df) < max_len * 0.5: # Heuristic: < 50% size
                         logger.info(f"Aligning sparse asset {k} to anchor {anchor_key}...")
                         # Reindex with ffill (forward fill last known value)
                         # bfill initial values so we don't start with NaNs
                         # Pandas 2.0/3.0 deprecation fix: use ffill() and bfill() directly
                         aligned_df = df.reindex(anchor_df.index, method='ffill').bfill()
                         data_obj[k] = aligned_df
             
             data_list_for_core = [data_obj[k] for k in keys]
             core_input = data_list_for_core
        else:
             df = data_obj['MAIN']
             if 'volume' not in df.columns: df['volume'] = 1.0
             core_input = df
             
        # Initialize Core (Fast)
        perm_core = PermutationCore(core_input)
        
        # 3. DETECT DATA FREQUENCY
        periods_per_year = 252.0
        try:
            # Check Time Delta
            if is_multi_asset:
                 # Use anchor or first
                 sample_df = data_obj[list(data_obj.keys())[0]]
            else:
                 sample_df = data_obj['MAIN']
            
            if len(sample_df) > 5:
                # Calculate median time diff of first 100 rows
                diffs = sample_df.index[:100].to_series().diff().dropna()
                median_diff = diffs.median()
                
                # Heuristics
                if median_diff < pd.Timedelta(minutes=15):
                    # Intraday (1-min or similar)
                    # Use standard US Equity minutes per year: 252 * 6.5 * 60 = 98280
                    # Or Crypto: 365 * 24 * 60 = 525600
                    # We'll use 252 * 390 = 98280 as a conservative baseline for intraday
                    periods_per_year = 98280.0
                    logger.info(f"Detected INTRADAY data (median diff {median_diff}). Using Annualization Factor: {periods_per_year}")
                elif median_diff < pd.Timedelta(hours=4):
                    # Hourly
                    periods_per_year = 252.0 * 6.5
                    logger.info(f"Detected HOURLY data. Using Annualization Factor: {periods_per_year}")
                else:
                    # Daily
                    periods_per_year = 252.0
                    logger.info(f"Detected DAILY data. Using Annualization Factor: {periods_per_year}")
                    
        except Exception as e:
            logger.warning(f"Failed to detect frequency: {e}. Defaulting to 252.0")
            
        
                 
        # 3. Load Strategy Module Dynamically
        logger.info(f"Loading strategy from {strat_path}")
        # ... Mocking Setup (kept same) ...
        class MockRedisBus:
            def __init__(self, *args, **kwargs): pass
            async def is_locked(self, key): return False
            async def acquire_lock(self, key, ttl): return True
            async def release_lock(self, key): pass
            async def publish_stream(self, *args, **kwargs): pass
            async def publish_channel(self, *args, **kwargs): pass
        
        class MockSettings:
            redis_host = "localhost"
            redis_port = 6379
            db_pool = None
            REDIS_HOST = "localhost"
            REDIS_PORT = 6379
            DB_POOL = None
            DATABASE_URL = ""
        
        mock_common = type(sys)('user_strategies.common')
        mock_common.messaging = type(sys)('user_strategies.common.messaging')
        mock_common.messaging.RedisBus = MockRedisBus
        mock_common.models = type(sys)('user_strategies.common.models')
        mock_common.models.MarketTick = dict
        mock_common.models.TradeSignal = dict
        mock_config = type(sys)('user_strategies.config')
        mock_config.settings = MockSettings()
        
        sys.modules['user_strategies'] = type(sys)('user_strategies')
        sys.modules['user_strategies.common'] = mock_common
        sys.modules['user_strategies.common.messaging'] = mock_common.messaging
        sys.modules['user_strategies.common.models'] = mock_common.models
        sys.modules['user_strategies.config'] = mock_config
        
        spec = importlib.util.spec_from_file_location("user_strategies.strategies.strategy_module", str(strat_path))
        strategy_module = importlib.util.module_from_spec(spec)
        strategy_module.__package__ = "user_strategies.strategies"
        try:
            spec.loader.exec_module(strategy_module)
        except Exception as e:
            logger.exception("Strategy load failed")
            await websocket.send_json({"type": "error", "message": f"Strategy load error: {e}"})
            return
            
        class_name = config.get('class_name', 'StrategyEngine')
        if not hasattr(strategy_module, class_name):
            await websocket.send_json({"type": "error", "message": f"Class '{class_name}' not found."})
            return
        
        StrategyClass = getattr(strategy_module, class_name)
        strategy_instance = StrategyClass()
        
        if not hasattr(strategy_instance, 'generate_signal'):
             await websocket.send_json({"type": "error", "message": "Strategy must implement generate_signal(df)."})
             return
             
        # 4. Calculate Original Score
        logger.info("Computing original score...")
        await websocket.send_json({"type": "progress", "completed": 0, "total": n_permutations, "status": "Computing original signal..."})

        # Run logic on Original Data
        orig_output = strategy_instance.generate_signal(data_obj if is_multi_asset else data_obj['MAIN'])
        
        # Extract Returns
        if isinstance(orig_output, tuple):
             _, orig_returns = orig_output
        else:
             orig_returns = orig_output
             
        if orig_returns is None or len(orig_returns) == 0:
             await websocket.send_json({"type": "error", "message": "Strategy returned no returns data."})
             return

        # Metric Logic
        if metric == 'profit_factor':
            gains = orig_returns[orig_returns > 0].sum()
            losses = abs(orig_returns[orig_returns < 0].sum())
            original_score = (gains / losses) if losses != 0 else (100.0 if gains > 0 else 0.0)
        else:
            original_score = calc_sharpe_ratio(None, orig_returns, periods_per_year=periods_per_year)
            
        logger.info(f"Original {metric}: {original_score:.4f}")
        await websocket.send_json({"type": "progress", "completed": 0, "total": n_permutations, "status": f"Original {metric}: {original_score:.4f}"})
        
        # 5. Run Permutation Loop (Async)
        # We break the loop into chunks to report progress, OR runs it all in thread and report at end?
        # For responsiveness, let's run in chunks of 50 or 100.
        
        chunk_size = 100
        total_permuted_scores = []
        total_better = 0
        
        start_time = time.time()
        
        # Prepare Data Reference for Multi-Asset reconstruction inside thread
        data_ref = data_obj if is_multi_asset else None
        
        for i in range(0, n_permutations, chunk_size):
            size = min(chunk_size, n_permutations - i)
            
            # Run chunk in thread pool
            loop = asyncio.get_event_loop()
            chunk_scores, chunk_better = await loop.run_in_executor(
                executor,
                run_permutation_loop,
                size,
                original_score,
                metric,
                strategy_instance,
                perm_core,
                is_multi_asset,
                data_ref,
                periods_per_year 
            )
            
            total_permuted_scores.extend(chunk_scores)
            total_better += chunk_better
            
            # Progress update
            completed = i + size
            await websocket.send_json({
                "type": "progress", 
                "completed": completed, 
                "total": n_permutations
            })
            
        elapsed = time.time() - start_time
        logger.info(f"Permutations complete. Time: {elapsed:.2f}s")
        
        # 6. Analyze Results
        analysis_result = analyze_permutation_results(
            original_score=original_score,
            permuted_scores=total_permuted_scores,
            metric_name=metric,
            alpha=0.05
        )
        
        # 7. Generate PDF
        pdf_bytes = None
        try:
             # Run heavy PDF gen in thread too
             loop = asyncio.get_event_loop()
             pdf_bytes = await loop.run_in_executor(executor, generate_pdf_report, analysis_result)
        except Exception as e:
            logger.error(f"PDF gen failed: {e}")
            
        # 8. Send Email
        email_sent = False
        if pdf_bytes:
            try:
                email_sent = send_permutation_report(
                    recipient_email=email,
                    pdf_bytes=pdf_bytes,
                    original_score=analysis_result.original_score,
                    p_value=analysis_result.p_value,
                    is_significant=analysis_result.is_significant,
                    percentile=analysis_result.percentile,
                    n_permutations=analysis_result.n_permutations,
                    metric=metric
                )
            except Exception as e:
                logger.error(f"Email failed: {e}")
                
        # 9. Send Final Response
        response = {
            "type": "result",
            "data": {
                "status": "success",
                "message": "Permutation Test Completed.",
                "email_sent": bool(email_sent),
                "original_score": float(analysis_result.original_score),
                "p_value": float(analysis_result.p_value),
                "is_significant": bool(analysis_result.is_significant),
                "percentile": float(analysis_result.percentile),
                "permuted_mean": float(analysis_result.permuted_mean),
                "permuted_std": float(analysis_result.permuted_std),
                "n_permutations": int(analysis_result.n_permutations),
                "metric": metric,
                "processing_time_seconds": float(elapsed)
            }
        }
        await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception(f"WS Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
