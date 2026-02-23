from pydantic import BaseModel, Field


class GameEvent(BaseModel):
    event_type: str
    ts_ms: int
    session_id: str
    armed: bool = False
    context: dict = Field(default_factory=dict)
