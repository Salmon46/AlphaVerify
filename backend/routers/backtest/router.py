"""
FastAPI Router for Backtest API

Provides endpoints for running backtests with uploaded strategy and data files.
"""
import os
import sys
import time
import shutil
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.csv_parser import load_market_data
from .engine import BacktestEngine
from .metrics import calculate_metrics
from .report_generator import generate_pdf_report
from .email_sender import send_backtest_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/backtest",
    tags=["backtest"]
)

# Upload directory
UPLOAD_DIR = Path(os.getcwd()) / "temp_backtest_upload"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@router.post("/run")
async def run_backtest(
    data: UploadFile = File(...),
    strategy: UploadFile = File(...),
    cash: float = Form(10000.0),
    commission: float = Form(0.001),
    email: Optional[str] = Form(None),
    class_name: str = Form("StrategyEngine")
):
    """
    Run a backtest with uploaded strategy and data files.
    
    Args:
        data: CSV file with market data (supports layered multi-asset format)
        strategy: Python file containing the strategy class
        cash: Initial cash amount
        commission: Commission rate per trade (e.g., 0.001 = 0.1%)
        email: Optional email to send PDF report
        class_name: Name of the strategy class in the Python file
        
    Returns:
        JSON with metrics, trades, and equity_curve
    """
    job_id = f"bt_{int(time.time())}"
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save uploaded files
        data_path = job_dir / "data.csv"
        strategy_path = job_dir / "strategy.py"
        
        with open(data_path, "wb") as f:
            shutil.copyfileobj(data.file, f)
            
        with open(strategy_path, "wb") as f:
            shutil.copyfileobj(strategy.file, f)
        
        logger.info(f"Job {job_id}: Files saved. Running backtest...")
        
        # Load market data
        market_data = load_market_data(str(data_path))
        logger.info(f"Job {job_id}: Loaded {len(market_data)} assets")
        
        # Detect data frequency for annualization
        periods_per_year = 252.0
        try:
            sample_df = list(market_data.values())[0]
            if len(sample_df) > 5:
                diffs = sample_df.index[:100].to_series().diff().dropna()
                if len(diffs) > 0:
                    import pandas as pd
                    median_diff = diffs.median()
                    if median_diff < pd.Timedelta(minutes=15):
                        periods_per_year = 98280.0  # Intraday
                    elif median_diff < pd.Timedelta(hours=4):
                        periods_per_year = 252.0 * 6.5  # Hourly
        except Exception:
            pass
        
        # Initialize and run backtest engine
        engine = BacktestEngine(
            initial_cash=cash,
            commission_rate=commission
        )
        
        result = engine.run(
            data=market_data,
            strategy_path=str(strategy_path),
            class_name=class_name
        )
        
        # Convert results to serializable format
        trades_list = [t.to_dict() for t in result.trades]
        equity_list = [e.to_dict() for e in result.equity_curve]
        
        # Calculate metrics
        metrics = calculate_metrics(
            equity_curve=equity_list,
            trades=trades_list,
            initial_cash=cash,
            periods_per_year=periods_per_year
        )
        
        logger.info(f"Job {job_id}: Backtest complete. Return: {metrics.total_return}%")
        
        # Build response
        response = {
            "status": "success",
            "metrics": {
                "total_return": metrics.total_return,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown,
                "profit_factor": metrics.profit_factor,
                "win_rate": metrics.win_rate,
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "avg_win": metrics.avg_win,
                "avg_loss": metrics.avg_loss,
                "final_equity": metrics.final_equity,
                "initial_equity": metrics.initial_equity
            },
            "trades": trades_list[-100:],  # Limit to last 100 trades
            "equity_curve": equity_list
        }
        
        # Send email report if requested
        if email:
            try:
                logger.info(f"Job {job_id}: Generating PDF report for {email}")
                pdf_bytes = generate_pdf_report(
                    metrics=response['metrics'],
                    equity_curve=equity_list,
                    trades=trades_list
                )
                
                email_sent = send_backtest_report(
                    recipient_email=email,
                    pdf_bytes=pdf_bytes,
                    metrics=response['metrics'],
                    trades=trades_list  # Full trade list for CSV attachment
                )
                
                if email_sent:
                    response["email_status"] = "sent"
                    logger.info(f"Job {job_id}: Email sent to {email}")
                else:
                    response["email_status"] = "failed"
                    logger.warning(f"Job {job_id}: Email failed (check BREVO credentials)")
            except Exception as e:
                logger.error(f"Job {job_id}: Email error: {e}")
                response["email_status"] = "error"
        
        return response
        
    except Exception as e:
        logger.exception(f"Job {job_id}: Backtest failed")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup
        try:
            if job_dir.exists():
                shutil.rmtree(job_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup {job_dir}: {e}")
