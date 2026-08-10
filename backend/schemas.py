from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PredictionResult(BaseModel):
    emotion: str
    confidence: float
    probabilities: Dict[str, float]
    latency_ms: float
    model_name: str

    # Which modalities actually contributed to THIS prediction. A fusion model
    # served without a live face track still predicts, but on a zero visual
    # tensor — so its accuracy is not the accuracy it was evaluated at. These
    # two fields make that visible instead of silent.
    modalities: List[str] = Field(default_factory=lambda: ["audio"])
    visual_active: bool = False


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: Optional[str] = None
    device: str
    sample_rate: int


class StreamMessage(BaseModel):
    type: str   # "prediction" | "error" | "info" | "ready"
    payload: dict
