from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.rabbitmq import RabbitMQClient
from app.models import ChatRequest, ChatResponse
import threading
import uvicorn
import logging
import os
from typing import AsyncIterator

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler for startup and shutdown events"""
    # Startup logic
    app.state.rabbitmq_client = RabbitMQClient()
    app.state.rabbitmq_client.connect(host=os.getenv("RABBITMQ_HOST", "rabbitmq"))
    
    # Start consumer in a separate thread
    thread = threading.Thread(
        target=app.state.rabbitmq_client.start_consuming,
        daemon=True
    )
    thread.start()
    logging.info("RabbitMQ consumer started in background")
    
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

@app.post("/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest, request: Request):  # Add Request parameter
    try:
        # Access rabbitmq_client from the app state
        response = request.app.state.rabbitmq_client.agent.process_message(chat_request.message)
        return ChatResponse(
            conversation_id=chat_request.conversation_id,
            message=response
        )
    except Exception as e:
        logging.error(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/chat/completions", response_model=ChatResponse)
async def chat_completion(chat_request: ChatRequest, request: Request):
    """Simplified single-response endpoint"""
    try:
        response = request.app.state.rabbitmq_client.agent.get_single_response(
            chat_request.message
        )
        return ChatResponse(
            conversation_id=chat_request.conversation_id,
            message=response
        )
    except Exception as e:
        logging.error(f"Error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)