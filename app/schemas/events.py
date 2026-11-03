from typing import Literal, Optional
from pydantic import BaseModel, Field


# ==========================================
# HTTP API Schemas
# ==========================================

class HealthResponse(BaseModel):
    status: str = Field(default="ok", example="ok")
    service: str = Field(default="mission-ssb-voice-api")
    active_sessions: int = Field(default=0, example=2)
    max_concurrent_sessions: int = Field(default=50)
    model: str = Field(default="gemini-2.5-flash-native-audio-preview-09-2025")
    uptime_seconds: float = Field(default=0.0)


# ==========================================
# WebSocket Protocol Schemas
# ==========================================

class ReadyEvent(BaseModel):
    type: Literal["ready"] = "ready"


class InterruptedEvent(BaseModel):
    type: Literal["interrupted"] = "interrupted"


class TurnCompleteEvent(BaseModel):
    type: Literal["turnComplete"] = "turnComplete"


class TranscriptEvent(BaseModel):
    type: Literal["transcript"] = "transcript"
    role: Literal["user", "assistant"]
    text: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class ClientControlMessage(BaseModel):
    type: Optional[str] = None

