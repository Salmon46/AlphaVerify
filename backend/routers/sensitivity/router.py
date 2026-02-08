import os
import shutil
import json
import logging
import asyncio
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .logic import SensitivityEngine
from .parser import extract_strategy_parameters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/sensitivity",
    tags=["sensitivity"]
)

# Directories
UPLOAD_DIR = os.path.join(os.getcwd(), "temp_sensitivity_upload")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class SensitivityConfig(BaseModel):
    data_filename: str
    strategy_filename: str = None
    email: str
    initial_cash: float
    parameters: dict  # e.g., {'sma_period': {'min': 10, 'max': 50, 'step': 10}}
    class_name: str = "StrategyEngine"
    mode: str = "grid" # 'grid' or 'random'
    distribution: str = "uniform" # 'uniform' or 'normal' (only for random mode)
    iterations: int = 1000 # Only used if mode='random'

@router.post("/upload-files")
async def upload_files(
    data_file: UploadFile = File(None),
    strategy_file: UploadFile = File(None)
):
    try:
        # Save Data File if provided
        if data_file:
            data_path = os.path.join(UPLOAD_DIR, data_file.filename)
            with open(data_path, "wb") as buffer:
                shutil.copyfileobj(data_file.file, buffer)
        
        # Save Strategy File if provided
        strategy_filename = None
        parameters = {}
        if strategy_file:
            strategy_path = os.path.join(UPLOAD_DIR, strategy_file.filename)
            with open(strategy_path, "wb") as buffer:
                shutil.copyfileobj(strategy_file.file, buffer)
            strategy_filename = strategy_file.filename
            
            # Extract Parameters
            parameters = extract_strategy_parameters(strategy_path)
            
        return JSONResponse({
            "status": "success",
            "data_filename": data_file.filename if data_file else None,
            "strategy_filename": strategy_filename,
            "detected_parameters": parameters
        })
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@router.websocket("/ws/run-sensitivity")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        config_dict = json.loads(data)
        config = SensitivityConfig(**config_dict)
        
        engine = SensitivityEngine(
            upload_dir=UPLOAD_DIR,
            data_filename=config.data_filename,
            strategy_filename=config.strategy_filename,
            initial_cash=config.initial_cash,
            parameters=config.parameters,

            class_name=config.class_name,
            mode=config.mode,
            distribution=config.distribution,
            iterations=config.iterations,
            email=config.email
        )
        
        await engine.run(websocket)
        
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})

@router.get("/health")
def health_check():
    return {"status": "ok"}
