# from pydantic import BaseModel

# class ChatRequest(BaseModel):
#     conversation_id: str
#     message: str

# class ChatResponse(BaseModel):
#     conversation_id: str
#     message: str

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class ImageRequest(BaseModel):
    conversation_id: str
    image_url: str

class ImageRequestPrompt(BaseModel):
    conversation_id: str
    image_url: str
    include_items: str

# class ImageResponse(BaseModel):
#     conversation_id: str
#     json_data: dict
#     status: str = "completed"

class ImageResponse:
    def __init__(self, conversation_id: str, json_data: Any, status: str = "completed"):
        self.conversation_id = conversation_id
        self.json_data = json_data  # 接受任何类型
        self.status = status