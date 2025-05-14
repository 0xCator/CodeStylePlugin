from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from CodeStyle import CodeStyle
from CodeSmell import CodeSmell
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FormatRequest(BaseModel):
    code: str
    settings: dict

class SmellRequest(BaseModel):
    code: str
    websocket_id: str

class CancelRequest(BaseModel):
    websocket_ids: list[str]

active_connections = {}

main_event_loop = None

analysis_tasks: dict[str, bool] = {}

@app.on_event("startup")
async def startup_event():
    global main_event_loop
    main_event_loop = asyncio.get_event_loop()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    analysis_tasks[client_id] = False  # Initialize as not cancelled
    logger.info(f"WebSocket connection established for client {client_id}")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        if client_id in active_connections:
            del active_connections[client_id]
        if client_id in analysis_tasks:
            del analysis_tasks[client_id]
        logger.info(f"Removed WebSocket connection for client {client_id}")

@app.post("/format")
async def format_code(request: FormatRequest):
    try:
        formatted_code, errors = CodeStyle.start_formatting(request.code, request.settings)
        return {"formatted_code": formatted_code, "errors": errors}
    except Exception as e:
        logger.error(f"Format error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def send_progress_update(websocket: WebSocket, percentage: int):
    try:
        await websocket.send_text(json.dumps({
            "type": "progress",
            "percentage": percentage
        }))
    except Exception as e:
        logger.error(f"Error sending progress update: {e}")

@app.post("/analyze")
async def analyze_smells(request: SmellRequest):
    try:
        if request.websocket_id not in active_connections:
            raise HTTPException(status_code=400, detail="WebSocket connection not found")

        def progress_callback(percentage):
            # Check if analysis was cancelled
            if analysis_tasks.get(request.websocket_id, True):
                raise Exception("Analysis cancelled")
                
            if request.websocket_id in active_connections:
                websocket = active_connections[request.websocket_id]
                asyncio.run_coroutine_threadsafe(
                    send_progress_update(websocket, percentage),
                    main_event_loop
                )
            
        logger.info(f"Starting analysis for client {request.websocket_id}")
        smells = await asyncio.to_thread(
            CodeSmell.start_analysis,
            request.code,
            progress_callback
        )
        logger.info(f"Analysis completed for client {request.websocket_id}")
        return {"smells": smells}
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        if str(e) == "Analysis cancelled":
            raise HTTPException(status_code=499, detail="Analysis cancelled")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cancel")
async def cancel_analysis(request: CancelRequest):
    try:
        for websocket_id in request.websocket_ids:
            # Mark the analysis as cancelled
            analysis_tasks[websocket_id] = True
            
            # Close the WebSocket connection if it exists
            if websocket_id in active_connections:
                websocket = active_connections[websocket_id]
                await websocket.close(code=1000, reason="Analysis cancelled")
                logger.info(f"Cancelled analysis for client {websocket_id}")
        
        return {"status": "success", "message": "Analysis cancelled"}
    except Exception as e:
        logger.error(f"Error cancelling analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webserver:app", host="0.0.0.0", port=8000, ws_ping_interval=20, ws_ping_timeout=20, reload=True) 
