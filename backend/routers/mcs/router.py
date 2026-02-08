"""
FastAPI Backend for AlphaVerify Monte Carlo Simulation
Exposes REST API for file upload and simulation orchestration.
"""
import logging
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
import time
import os
from pathlib import Path
import subprocess
import shutil
import json

from .report_generator import generate_pdf_report
from .email_sender import send_monte_carlo_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/mcs",
    tags=["mcs"]
)

# Directories
UPLOAD_DIR = os.path.join(os.getcwd(), "temp_mcs_upload")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class SimulationResponse(BaseModel):
    """Response model for simulation results."""
    status: str
    message: str
    email_sent: bool
    metrics: dict

class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")

@router.post("/simulate", response_model=SimulationResponse)
async def run_simulation(
    file: UploadFile = File(..., description="CSV file with trade data"),
    email: str = Form(..., description="Email address to send report"),
    n_simulations: int = Form(default=4500, description="Number of simulations"),
    initial_capital: float = Form(default=10000.0, description="Initial capital")
):
    """
    Run Monte Carlo simulation using the High-Performance Rust backend.
    """
    start_time = time.time()
    
    # Save Uploaded File to Disk for Rust Binary
    temp_dir = Path(UPLOAD_DIR)
    file_path = temp_dir / file.filename
    
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        
        # --- Python NumPy Execution ---
        from .python_logic import PythonMCSEngine
        
        logger.info(f"Starting MCS (Python/NumPy) with {n_simulations} sims...")
        
        engine = PythonMCSEngine(initial_capital=initial_capital, n_simulations=n_simulations)
        
        # Offload blocking Simulation to ThreadPool to avoid freezing FastAPI
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, engine.run, str(file_path))
        
        if "error" in result:
             raise RuntimeError(result["error"])
             
        result["processing_time_seconds"] = round(time.time() - start_time, 2)
        
        # Report & Email Logic
        email_sent = False
        try:
            # Generate PDF 
            pdf_bytes = generate_pdf_report(result)
            
            # Send Email
            if email:
                send_monte_carlo_report(
                    recipient_email=email,
                    pdf_bytes=pdf_bytes,
                    mean_return=result["mean_return"],
                    max_drawdown_95=result["max_drawdown_95"],
                    risk_of_ruin=result["risk_of_ruin"],
                    n_simulations=result["n_simulations"],
                    n_trades=result.get("n_trades", 0)
                )
                email_sent = True
        except Exception as e:
            logger.error(f"Failed to generate/send report: {e}")
            # Don't fail the request, just log
        
        return SimulationResponse(
            status="success",
            message=f"Simulation completed in {result['processing_time_seconds']}s (Python NumPy). Report sent: {email_sent}",
            email_sent=email_sent,
            metrics=result
        )
        
    finally:
        # Cleanup
        if file_path.exists():
            try:
                file_path.unlink()
            except:
                pass
