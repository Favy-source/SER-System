from typing import Dict, Optional
from pydantic import BaseModel


class PredictionResult(BaseModel):
    emotion: str
    confidence: float
    probabilities: Dict[str, float]
    latency_ms: float
    model_name: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: Optional[str] = None
    device: str
    sample_rate: int


class StreamMessage(BaseModel):
    type: str   # "prediction" | "error" | "info" | "ready"
    payload: dict
