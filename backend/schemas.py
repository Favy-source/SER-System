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

    # True when the loaded checkpoint has randomly initialised weights
    # (scripts/make_demo_checkpoint.py). Predictions are noise; the UI shows a
    # standing warning so a demo cannot be mistaken for a result.
    untrained: bool = False
    multimodal: bool = False


class StreamMessage(BaseModel):
    type: str   # "prediction" | "error" | "info" | "ready"
    payload: dict
