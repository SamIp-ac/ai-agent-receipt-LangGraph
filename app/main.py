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
from app.models import ImageRequest, ImageRequestPrompt


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler for startup and shutdown events"""
    # Startup logic
    app.state.rabbitmq_client = RabbitMQClient()
    app.state.rabbitmq_client.connect(host=os.getenv("RABBITMQ_HOST", "rabbitmq"))
    
    yield  # Application runs here
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
    request: Request = None,
    include_items: str = "price, item_name, company"
):
    """convert receipt (with/without hand writting) image to json"""
    conversation_id = str(uuid.uuid4())
    contents = await file.read()
    encoded_image = base64.b64encode(contents).decode('utf-8')
    
    # Always queue through RabbitMQ for consistency
    try:
        task = ImageRequestPrompt(
            conversation_id=conversation_id,
            image_url=encoded_image,
            include_items=include_items
        )
        request.app.state.rabbitmq_client.publish_image_task(task.model_dump_json())
        return {
            "status": "queued",
            "conversation_id": conversation_id,
            "poll_url": f"/result/{conversation_id}"
        }
    except Exception as e:
        logging.error(f"Queueing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))