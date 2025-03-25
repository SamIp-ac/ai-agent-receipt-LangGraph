import base64
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.rabbitmq import RabbitMQClient
import threading
import uvicorn
import logging
import os
from typing import AsyncIterator
from fastapi import BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
import uuid
import json
from app.models import ImageRequest, ImageResponse
from redis import Redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler for startup and shutdown events"""
    # Startup logic
    app.state.rabbitmq_client = RabbitMQClient()
    app.state.rabbitmq_client.connect(host=os.getenv("RABBITMQ_HOST", "rabbitmq"))
    app.state.redis = Redis(host="redis", port=6379)
    
    # Start consumer in a separate thread
    thread = threading.Thread(
        target=app.state.rabbitmq_client.start_consuming,
        daemon=True
    )
    thread.start()
    logging.info("RabbitMQ consumer started in background")
    
    yield  # Application runs here
    app.state.redis.close()
    # Shutdown logic
    if hasattr(app.state, "rabbitmq_client"):
        app.state.rabbitmq_client.close()
    logging.info("RabbitMQ connection closed")

app = FastAPI(lifespan=lifespan)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/process-image")
async def process_image(
    file: UploadFile = File(...),
    request: Request = None
):
    conversation_id = str(uuid.uuid4())
    contents = await file.read()
    encoded_image = base64.b64encode(contents).decode('utf-8')
    
    # Always queue through RabbitMQ for consistency
    try:
        task = ImageRequest(
            conversation_id=conversation_id,
            image_url=encoded_image
        )
        request.app.state.rabbitmq_client.publish_image_task(task)
        return {
            "status": "queued",
            "conversation_id": conversation_id,
            "poll_url": f"/result/{conversation_id}"
        }
    except Exception as e:
        logging.error(f"Queueing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/process-image")
# async def process_image(
#     file: UploadFile = File(...),
#     background_tasks: BackgroundTasks = None,
#     request: Request = None 
# ):
#     """Hybrid endpoint for direct or queued processing"""
#     conversation_id = str(uuid.uuid4())
    
#     # Read image
#     contents = await file.read()
#     encoded_image = base64.b64encode(contents).decode('utf-8')
    
#     if file.size < 1_000:  # Small files (<1MB) process immediately
#         try:
#             json_data = request.app.state.rabbitmq_client.agent.process_image(  # Now 'request' is defined
#                 encoded_image
#             )
#             return JSONResponse(content=json.loads(json_data))
#         except Exception as e:
#             return {"error": str(e)}
#     else:  # Large file (RabbitMQ path)
#         try:
#             # 1. Create and publish task
#             task = ImageRequest(
#                 conversation_id=conversation_id,
#                 image_url=encoded_image,
#             )
#             request.app.state.rabbitmq_client.publish_image_task(task)
            
#             # 2. Return tracking ID
#             return {
#                 "status": "queued",
#                 "conversation_id": conversation_id,
#                 "poll_url": f"/result/{conversation_id}"  # Client polls this
#             }
#         except Exception as e:
#             return {"error": f"Failed to queue task: {str(e)}"}

@app.get("/result/{conversation_id}")
async def get_result(conversation_id: str):
    if result := app.state.redis.get(conversation_id):
        return json.loads(result)
    raise HTTPException(status_code=404, detail="Result not ready")

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)