"""
SER System — FastAPI backend.

Run:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Environment variables:
    MODEL_CHECKPOINT   path to .pt checkpoint  (default: models/audio_cnn_lstm_best.pt)
    CONFIG_PATH        path to settings.yaml   (default: config/settings.yaml)
    CORS_ORIGINS       comma-separated origins (default: *)

Endpoints:
    GET  /health                    liveness + model status
    GET  /models                    list available checkpoints
    POST /predict/audio             upload audio file → emotion label
    POST /predict/switch            hot-swap to a different checkpoint
    WS   /ws/stream                 real-time PCM streaming
"""
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import (
    FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from .inference import InferenceEngine
from .schemas import HealthResponse, PredictionResult
from .stream import AudioStreamBuffer


# ---------------------------------------------------------------------------
# Global engine — loaded once at startup, swappable at runtime
# ---------------------------------------------------------------------------

engine: InferenceEngine | None = None


def _load_engine(ckpt_path: str, cfg_path: str) -> InferenceEngine | None:
    if not Path(ckpt_path).exists():
        print(f"[SER] No checkpoint at {ckpt_path!r} — prediction endpoints will return 503")
        return None
    try:
        eng = InferenceEngine(ckpt_path, cfg_path)
        print(f"[SER] Loaded {eng.model_name!r} on {eng.device}")
        return eng
    except Exception as exc:
        print(f"[SER] Failed to load checkpoint: {exc}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    ckpt = os.getenv("MODEL_CHECKPOINT", "models/audio_cnn_lstm_best.pt")
    cfg  = os.getenv("CONFIG_PATH",      "config/settings.yaml")
    engine = _load_engine(ckpt, cfg)
    yield
    engine = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_origins = os.getenv("CORS_ORIGINS", "*").split(",")

app = FastAPI(
    title="SER System",
    description="Multimodal Speech Emotion Recognition — real-time inference API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _engine() -> InferenceEngine:
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Train a model first and set MODEL_CHECKPOINT.",
        )
    return engine


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """Liveness check and model status."""
    return HealthResponse(
        status="ok",
        model_loaded=engine is not None,
        model_name=engine.model_name if engine else None,
        device=str(engine.device) if engine else "n/a",
        sample_rate=engine.sr if engine else 0,
    )


@app.get("/models", tags=["system"])
def list_models():
    """List checkpoint files available under models/."""
    model_dir = Path("models")
    if not model_dir.exists():
        return {"checkpoints": []}
    ckpts = sorted(str(p) for p in model_dir.glob("*.pt"))
    return {
        "checkpoints": ckpts,
        "active": (
            engine.model_name if engine else None
        ),
    }


@app.post("/predict/audio", response_model=PredictionResult, tags=["prediction"])
async def predict_audio(file: UploadFile = File(..., description="Audio file (wav, flac, ogg, mp3)")):
    """
    Upload an audio file and receive an emotion prediction.

    Accepts any format readable by libsndfile (wav, flac, ogg).
    For mp3 support, install ffmpeg and pydub.
    """
    eng = _engine()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file.")
    try:
        result = eng.predict_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not process audio: {exc}")
    return PredictionResult(**result)


@app.post("/predict/switch", tags=["system"])
def switch_model(checkpoint: str):
    """
    Hot-swap to a different checkpoint without restarting the server.

    Example: POST /predict/switch?checkpoint=models/attention_best.pt
    """
    global engine
    cfg = os.getenv("CONFIG_PATH", "config/settings.yaml")
    new_engine = _load_engine(checkpoint, cfg)
    if new_engine is None:
        raise HTTPException(status_code=404, detail=f"Checkpoint not found: {checkpoint!r}")
    engine = new_engine
    return {"status": "ok", "model": engine.model_name, "device": str(engine.device)}


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """
    Real-time emotion recognition over a WebSocket.

    Protocol:
      1. Connect.
      2. Client sends JSON text:   {"sample_rate": 16000}
      3. Server responds:          {"type": "ready", "payload": {...}}
      4. Client sends PCM chunks:  raw float32 bytes (any chunk size)
      5. Server sends predictions: {"type": "prediction", "payload": {...}}
         whenever a full inference window has accumulated.
      6. Client can send text:     {"type": "reset"} to clear the buffer.
    """
    await ws.accept()

    if engine is None:
        await ws.send_json({"type": "error", "payload": {"message": "Model not loaded."}})
        await ws.close(code=1011)
        return

    # --- handshake ---
    try:
        raw = await ws.receive_text()
        config = json.loads(raw)
        input_sr = int(config.get("sample_rate", 16000))
    except Exception:
        input_sr = 16000

    buf = AudioStreamBuffer(engine, input_sr=input_sr)
    await ws.send_json({
        "type": "ready",
        "payload": {
            "sample_rate": input_sr,
            "model": engine.model_name,
            "window_sec": 3.0,
            "hop_sec": 0.5,
        },
    })

    # --- stream loop ---
    try:
        while True:
            msg = await ws.receive()

            if "bytes" in msg and msg["bytes"]:
                result = buf.push(msg["bytes"])
                if result is None:
                    continue
                if "_error" in result:
                    await ws.send_json({"type": "error", "payload": {"message": result["_error"]}})
                else:
                    await ws.send_json({"type": "prediction", "payload": result})

            elif "text" in msg and msg["text"]:
                try:
                    ctrl = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                if ctrl.get("type") == "reset":
                    buf.reset()
                    await ws.send_json({"type": "info", "payload": {"message": "buffer cleared"}})
                elif ctrl.get("type") == "ping":
                    await ws.send_json({"type": "info", "payload": {"message": "pong"}})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "payload": {"message": str(exc)}})
        except Exception:
            pass
