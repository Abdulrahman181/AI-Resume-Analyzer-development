"""Career Advisor chat schemas."""

from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    resume_id: int | None = None
    job_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []
    resume_used: bool = False
    agent_used: str | None = None                                               


class ChatHistoryItem(BaseModel):
    id: int
    user_id: int
    role: str                        
    content: str
    resume_id: int | None = None
    job_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True
