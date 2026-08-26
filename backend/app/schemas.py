from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class ConversationCreated(BaseModel):
    conversation_id: str


class TranscriptionResponse(BaseModel):
    text: str


class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


class ChatResponse(BaseModel):
    text: str


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class VoiceTurnResponse(BaseModel):
    conversation_id: str
    user_text: str
    assistant_text: str
    audio_base64: str
    audio_mime_type: str = "audio/mpeg"
