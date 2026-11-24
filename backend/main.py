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
from starlette.concurrency import run_in_threadpool

from src.constants import N_FACE_LANDMARKS

from .inference import InferenceEngine
from .schemas import HealthResponse, PredictionResult
from .stream import AudioStreamBuffer, VisualStreamBuffer

# Binary frame tags, used only when the client sets "tagged_binary": true in the
# handshake. Legacy clients send untagged PCM and keep working unchanged.
TAG_AUDIO     = 0
TAG_LANDMARKS = 1
TAG_HEADER    = 4          # 1 tag byte + 3 reserved, so float32 stays 4-aligned


def websocket_support() -> bool:
    """Is a WebSocket implementation available to the ASGI server?

    uvicorn needs `websockets` or `wsproto` to accept an upgrade. Without one it
    answers every WS route with **404**, which looks exactly like a routing bug
    and is nothing of the sort. requirements.txt asks for uvicorn[standard],
    but a partial install (plain `pip install uvicorn`) silently loses it — and
    Starlette's TestClient does not use uvicorn's WS implementation at all, so
    the entire test suite passes while live streaming is dead.

    Reported by /health so the front end can say something accurate instead of
    "cannot reach backend".
    """
    try:
        import websockets  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import wsproto  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Global engine — loaded once at startup, swappable at runtime
# ---------------------------------------------------------------------------

engine: InferenceEngine | None = None


def _load_engine(ckpt_path: str, cfg_path: str) -> InferenceEngine | None:
    if not Path(ckpt_path).exists():
        print(f"[SER] No checkpoint at {ckpt_path!r} — prediction endpoints will return 503", flush=True)
        return None
    try:
        eng = InferenceEngine(ckpt_path, cfg_path)
        print(f"[SER] Loaded {eng.model_name!r} on {eng.device}", flush=True)
        if eng.untrained:
            print("[SER] " + "!" * 62, flush=True)
            print("[SER] UNTRAINED CHECKPOINT — weights are random, predictions are NOISE.", flush=True)
            print("[SER] Fine for exercising the pipeline; meaningless as a result.", flush=True)
            print("[SER] " + "!" * 62, flush=True)
        return eng
    except Exception as exc:
        print(f"[SER] Failed to load checkpoint: {exc}", flush=True)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    if not websocket_support():
        # flush=True throughout: uvicorn buffers stdout, so without it these
        # lines never reach the terminal and the operator sees only a 404.
        print("[SER] " + "!" * 66, flush=True)
        print("[SER] No WebSocket library installed — /ws/stream will return 404 and", flush=True)
        print("[SER] ALL live streaming (voice AND webcam) will fail. File upload still works.", flush=True)
        print("[SER] Fix:  pip install 'uvicorn[standard]'   (or: pip install websockets)", flush=True)
        print("[SER] " + "!" * 66, flush=True)
    ckpt = os.getenv("MODEL_CHECKPOINT", "models/audio_cnn_lstm_best.pt")
    cfg  = os.getenv("CONFIG_PATH",      "config/settings.yaml")
    engine = _load_engine(ckpt, cfg)
    yield
    engine = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(
    title="SER System",
    description="Multimodal Speech Emotion Recognition — real-time inference API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Wildcard '*' + credentials violates the Fetch/CORS spec.
    allow_credentials=("*" not in _origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # 50 MB guard against accidental/abusive uploads
MIN_SAMPLE_RATE  = 8000
MAX_SAMPLE_RATE  = 192000


def _resolve_checkpoint_path(checkpoint: str) -> Path:
    """Confine hot-swap checkpoint paths strictly to the configured models/ directory."""
    model_dir = Path(os.getenv("MODEL_DIR", "models")).resolve()
    req = Path(checkpoint)
    if req.is_absolute():
        candidate = req.resolve()
    else:
        # Accept either "models/foo.pt" or bare "foo.pt" inside model_dir.
        candidate = (Path.cwd() / req).resolve()
        if not candidate.is_relative_to(model_dir):
            candidate = (model_dir / req).resolve()
    if not candidate.is_relative_to(model_dir) or candidate.suffix != ".pt":
        raise HTTPException(
            status_code=400,
            detail="Checkpoint must be a .pt file inside the models/ directory.",
        )
    return candidate


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
        untrained=bool(getattr(engine, "untrained", False)) if engine else False,
        multimodal=bool(getattr(engine, "multimodal", False)) if engine else False,
        websocket_available=websocket_support(),
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
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds 50 MB limit.")
    try:
        result = await run_in_threadpool(eng.predict_from_bytes, raw)
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
    safe_path = _resolve_checkpoint_path(checkpoint)
    cfg = os.getenv("CONFIG_PATH", "config/settings.yaml")
    new_engine = _load_engine(str(safe_path), cfg)
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
      2. Client sends JSON text:   {"sample_rate": 16000,
                                    "tagged_binary": true,   (optional)
                                    "visual": true}          (optional)
      3. Server responds:          {"type": "ready", "payload": {...}}
      4. Client sends PCM chunks:  raw float32 bytes (any chunk size)
      5. Server sends predictions: {"type": "prediction", "payload": {...}}
         whenever a full inference window has accumulated.
      6. Client can send text:     {"type": "reset"} to clear the buffer.

    Visual streaming (opt-in via "tagged_binary" + "visual"):
      Every binary frame gains a 4-byte header — byte 0 is the channel tag
      (0 = audio PCM, 1 = face landmarks), bytes 1-3 reserved so the float32
      payload stays 4-byte aligned. Landmark frames carry raw
      n_landmarks * 3 float32 coordinates straight from the client's
      FaceLandmarker; the server normalises them with the same
      src.features.normalize_landmarks that the training pipeline uses, so no
      normalisation logic is duplicated in JavaScript.

      Clients that omit "tagged_binary" keep sending untagged PCM and are
      unaffected.
    """
    await ws.accept()

    if engine is None:
        await ws.send_json({"type": "error", "payload": {"message": "Model not loaded."}})
        await ws.close(code=1011)
        return

    # --- handshake ---
    tagged = False
    want_visual = False
    try:
        raw = await ws.receive_text()
        config = json.loads(raw)
        input_sr = int(config.get("sample_rate", 16000))
        tagged = bool(config.get("tagged_binary", False))
        want_visual = bool(config.get("visual", False))
    except Exception:
        input_sr = 16000

    if not (MIN_SAMPLE_RATE <= input_sr <= MAX_SAMPLE_RATE):
        await ws.send_json({
            "type": "error",
            "payload": {"message": f"Unsupported sample_rate {input_sr} (expected {MIN_SAMPLE_RATE}..{MAX_SAMPLE_RATE})"},
        })
        await ws.close(code=1008)
        return

    # Visual is only meaningful for a fusion checkpoint, and only reachable when
    # the client opted into tagged frames — otherwise there is no way to tell a
    # landmark frame from PCM.
    visual_enabled = tagged and want_visual and engine.multimodal
    window_sec = float(getattr(engine, "_duration", 3.0))
    vbuf = (
        VisualStreamBuffer(max_frames=engine.cfg["visual"]["max_frames"])
        if visual_enabled else None
    )
    buf = AudioStreamBuffer(engine, input_sr=input_sr, window_sec=window_sec, visual=vbuf)

    await ws.send_json({
        "type": "ready",
        "payload": {
            "sample_rate": input_sr,
            "model": engine.model_name,
            "window_sec": window_sec,
            "hop_sec": 0.5,
            "tagged_binary": tagged,
            # what the server will actually do, not what was asked for
            "visual_enabled": visual_enabled,
            "multimodal_model": engine.multimodal,
            "max_frames": engine.cfg["visual"]["max_frames"],
            "expected_landmarks": N_FACE_LANDMARKS,
        },
    })

    # --- stream loop ---
    try:
        while True:
            msg = await ws.receive()

            if "bytes" in msg and msg["bytes"]:
                payload = msg["bytes"]
                tag = TAG_AUDIO

                if tagged:
                    if len(payload) < TAG_HEADER:
                        continue
                    tag, payload = payload[0], payload[TAG_HEADER:]

                if tag == TAG_LANDMARKS:
                    if vbuf is None:
                        continue          # client sent visual we did not enable
                    try:
                        vbuf.push_bytes(payload)
                    except Exception as exc:
                        await ws.send_json({
                            "type": "error",
                            "payload": {"message": f"bad landmark frame: {exc}"},
                        })
                    continue              # landmarks never trigger inference

                result = await run_in_threadpool(buf.push, payload)
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
                ctype = ctrl.get("type")
                if ctype == "reset":
                    buf.reset()
                    if vbuf is not None:
                        vbuf.reset()
                    await ws.send_json({"type": "info", "payload": {"message": "buffer cleared"}})
                elif ctype == "ping":
                    await ws.send_json({"type": "info", "payload": {"message": "pong"}})
                elif ctype == "stats":
                    await ws.send_json({
                        "type": "info",
                        "payload": {
                            "message": "stats",
                            "visual": vbuf.stats() if vbuf else None,
                        },
                    })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "payload": {"message": str(exc)}})
        except Exception:
            pass
