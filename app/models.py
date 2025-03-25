# from pydantic import BaseModel

# class ChatRequest(BaseModel):
#     conversation_id: str
#     message: str

# class ChatResponse(BaseModel):
#     conversation_id: str
#     message: str

from pydantic import BaseModel
from typing import Optional

class ImageRequest(BaseModel):
    conversation_id: str
    image_url: str

class ImageResponse(BaseModel):
    conversation_id: str
    json_data: dict  # The extracted JSON
    status: str = "completed"