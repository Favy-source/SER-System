# Backend

FastAPI inference service. Loads a trained checkpoint, exposes REST endpoints for file-based
prediction, and streams real-time predictions over a WebSocket.

- [Module map](#module-map)
- [Request lifecycle](#request-lifecycle)
- [Startup and graceful degradation](#startup-and-graceful-degradation)
- [The three layers](#the-three-layers)
- [Running it](#running-it)
- [Response contract](#response-contract)
- [Error handling](#error-handling)
- [Known limitations](#known-limitations)
- [Further reading](#further-reading)

---

## Module map

| File | Lines | Responsibility |
|---|---:|---|
| [`main.py`](../../backend/main.py) | 238 | App construction, CORS, lifespan, all routes, WebSocket handler |
| [`inference.py`](../../backend/inference.py) | 127 | `InferenceEngine` — checkpoint loading, feature extraction, prediction |
| [`stream.py`](../../backend/stream.py) | 77 | `AudioStreamBuffer` — sliding-window accumulation over a live PCM stream |
| [`schemas.py`](../../backend/schemas.py) | 23 | Pydantic response models |
| [`requirements.txt`](../../backend/requirements.txt) | 20 | Python dependencies for the whole project, not just the backend |
| `__init__.py` | 0 | Package marker |

Roughly 465 lines of Python for the entire service. The brevity is possible because all the modelling
logic lives in [`src/`](../../src/), which the backend imports rather than duplicates:

```python
from src.datasets import UNIFIED, IDX2LABEL
from src.features import mel_spectrogram, mfcc_features
from src.models.builder import build_model, is_multimodal
```

That import list is the single most important design decision in the backend. Feature extraction at
serve time uses the *same functions* that produced the training features, so train/serve skew — a
mismatch between how features are computed during training and during inference — is structurally
impossible rather than merely avoided by discipline. It is one of the most common and hardest-to-diagnose
failure modes in deployed ML systems.

---

## Request lifecycle

### File upload

```
POST /predict/audio (multipart)
  │
  ├─ _engine()                      503 if no model loaded
  ├─ await file.read()              422 if empty
  ├─ engine.predict_from_bytes()
  │    ├─ soundfile.read()          decode wav/flac/ogg
  │    ├─ mean across channels      if stereo
  │    ├─ librosa.resample()        if the file's rate ≠ model's rate
  │    └─ predict()
  │         ├─ _pad_or_crop()       centre-crop or symmetric zero-pad to 3 s
  │         ├─ _to_tensor()         mel or mfcc, per the checkpoint's "feature"
  │         ├─ model(...)           forward, no_grad
  │         └─ softmax → dict       + latency_ms measured around the whole block
  └─ PredictionResult               422 if anything above raised
```

### WebSocket stream

```
WS /ws/stream
  │
  ├─ accept()
  ├─ if engine is None → error frame, close 1011
  ├─ receive_text()                 handshake: {"sample_rate": 16000}
  ├─ AudioStreamBuffer(engine, input_sr)
  ├─ send ready frame               {model, window_sec, hop_sec}
  │
  └─ loop: receive()
       ├─ bytes → buf.push()
       │     ├─ None                 window not full, or hop not elapsed → no message
       │     ├─ {"_error": …}        → error frame
       │     └─ prediction dict      → prediction frame
       └─ text → control
             ├─ {"type":"reset"}     → buf.reset(), info frame
             └─ {"type":"ping"}      → info frame "pong"
```

---

## Startup and graceful degradation

```python
engine: InferenceEngine | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    ckpt = os.getenv("MODEL_CHECKPOINT", "models/audio_cnn_lstm_best.pt")
    cfg  = os.getenv("CONFIG_PATH",      "config/settings.yaml")
    engine = _load_engine(ckpt, cfg)
    yield
    engine = None
```

The checkpoint loads **once** at startup, not per request. Loading a 6.5M-parameter model and moving it
to the GPU takes hundreds of milliseconds — per-request loading would make the API useless.

`_load_engine` never raises:

```python
def _load_engine(ckpt_path, cfg_path):
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
```

### Why the server boots without a model

This looks like sloppy error handling and is in fact the point. Three reasons it earns its place:

1. **Front-end development can begin before the first model exists.** On a fresh clone there is no
   checkpoint — `models/` is empty. A crash-on-startup server would block all front-end work until
   training completed.
2. **"No model" becomes a testable state rather than a boot failure.** Six of the 20 API tests exercise
   this path, so the degraded behaviour is a guarantee rather than an accident.
3. **`/health` stays informative.** A server that crashed tells you nothing; a server reporting
   `model_loaded: false` tells you exactly what is wrong, and the front end renders that as a red status
   dot with the label "No model loaded".

The gate is one helper, used by every prediction endpoint:

```python
def _engine() -> InferenceEngine:
    if engine is None:
        raise HTTPException(503, "Model not loaded. Train a model first and set MODEL_CHECKPOINT.")
    return engine
```

503 (Service Unavailable) is the correct code: the request is well-formed, the service is temporarily
incapable of fulfilling it, and the condition is expected to be transient.

### Hot-swapping

`POST /predict/switch?checkpoint=models/attention_best.pt` reassigns the module-level `engine` through
the same `_load_engine`. Useful for A/B-ing architectures in a live demo without a restart.

It is unauthenticated and takes an arbitrary filesystem path — see
[deployment.md](deployment.md#security) before exposing this beyond localhost.

---

## The three layers

### `InferenceEngine` — one prediction

Loads a checkpoint, rebuilds the architecture from the config embedded in it, and predicts from a numpy
array, raw bytes, or a file path. Three entry points share one `predict()` core.

Full detail: [inference-engine.md](inference-engine.md).

### `AudioStreamBuffer` — many predictions over time

Accumulates float32 PCM chunks of arbitrary size, fires inference when a full window has accumulated and
a hop interval has elapsed, bounds its own memory, and resamples to the model's rate.

```python
AudioStreamBuffer(engine, input_sr=16000, window_sec=3.0, hop_sec=0.5)
```

| Parameter | Default | Purpose |
|---|---|---|
| `input_sr` | 16000 | Client's rate, taken from the handshake |
| `window_sec` | 3.0 | Inference window — should match `audio.duration` |
| `hop_sec` | 0.5 | Minimum gap between inferences → ≤2 predictions/second |

**All windowing lives here, not on the client.** The browser sends whatever block size its audio graph
produces (typically 128 frames per render quantum), and the server decides when a window is complete.
That keeps the client trivial, puts the window size where knowledge of the model's training duration
actually lives, and means a second client implementation only has to send bytes.

Note that `window_sec` defaults to 3.0 in the constructor rather than being read from
`config.audio.duration`. If you change the training duration you must change this too — they are coupled
by convention, not by code.

### `main.py` — the HTTP and WebSocket surface

Routes, CORS, lifespan, and the streaming loop. See [api-reference.md](api-reference.md) and
[websocket-protocol.md](websocket-protocol.md).

CORS is permissive by default:

```python
_origins = os.getenv("CORS_ORIGINS", "*").split(",")
```

Right for local development, wrong for anything public — see
[deployment.md](deployment.md#cors).

---

## Running it

```bash
# development — auto-reload on file changes
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# with a checkpoint
MODEL_CHECKPOINT=models/audio_cnn_lstm_best.pt uvicorn backend.main:app --port 8000
```

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_CHECKPOINT` | `models/audio_cnn_lstm_best.pt` | Checkpoint loaded at startup |
| `CONFIG_PATH` | `config/settings.yaml` | Config for `InferenceEngine` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

Interactive OpenAPI docs at <http://localhost:8000/docs>, generated from the route signatures and
Pydantic models. Endpoints are tagged `system` and `prediction`.

Run from the **repository root** — the default config and checkpoint paths are relative, and `/models`
resolves `Path("models")` against the working directory.

---

## Response contract

[`schemas.py`](../../backend/schemas.py):

```python
class PredictionResult(BaseModel):
    emotion:       str              # one of the six unified labels
    confidence:    float            # max probability, 4 dp
    probabilities: Dict[str, float] # all six, 4 dp, sums to ~1.0
    latency_ms:    float            # end-to-end: pad/crop + features + forward + softmax
    model_name:    str              # e.g. "audio_cnn_lstm"

class HealthResponse(BaseModel):
    status:       str               # "ok"
    model_loaded: bool
    model_name:   Optional[str]
    device:       str               # "cuda" | "cpu" | "n/a"
    sample_rate:  int               # 0 when no model

class StreamMessage(BaseModel):
    type:    str                    # "prediction" | "error" | "info" | "ready"
    payload: dict
```

The same `PredictionResult` shape is returned by `/predict/audio` and carried in the `payload` of a
WebSocket `prediction` frame, so a client needs one parser for both paths.

`StreamMessage` documents the WebSocket envelope but is **not used for validation** — the handler calls
`ws.send_json({...})` with literal dicts. It is documentation in code form; the schema and the wire
format could drift.

`latency_ms` is measured inside `InferenceEngine.predict`, around pad/crop, feature extraction, forward,
and softmax. It excludes HTTP overhead, file decoding, and resampling. It is a much better guide to
real-time feasibility than the model-only benchmark in `evaluate.py` — see
[evaluation.md](../evaluation.md#what-this-number-is-and-is-not).

---

## Error handling

| Condition | Response |
|---|---|
| No model loaded (REST) | `503` — "Model not loaded. Train a model first and set `MODEL_CHECKPOINT`." |
| No model loaded (WS) | `error` frame, then close with code `1011` |
| Empty file upload | `422` — "Empty file." |
| Undecodable audio | `422` — "Could not process audio: `<exception>`" |
| Checkpoint not found on switch | `404` — "Checkpoint not found: `<path>`" |
| Malformed WS handshake | Silently defaults to `sample_rate = 16000` |
| Malformed WS control JSON | Silently ignored (`continue`) |
| Inference failure mid-stream | `error` frame; **connection stays open** |
| Client disconnect | `WebSocketDisconnect` caught, handler returns cleanly |

Two deliberate asymmetries:

**The stream is forgiving where REST is strict.** A single bad window sends an `error` frame and the loop
continues; malformed control frames are ignored rather than closing the connection. A live audio stream
will produce occasional bad windows, and tearing down the connection each time would make the demo
unusable. REST requests, by contrast, are discrete and a caller benefits from a clear failure.

**A failed handshake falls back rather than failing.** If the client's first text frame is not valid JSON
or lacks `sample_rate`, the server assumes 16000 rather than rejecting the connection:

```python
try:
    config = json.loads(await ws.receive_text())
    input_sr = int(config.get("sample_rate", 16000))
except Exception:
    input_sr = 16000
```

Forgiving, and it can mask a genuine client bug — a client sending 44100 audio while failing to declare
it will be resampled as if it were 16 kHz, producing pitch-shifted garbage with no error anywhere.
Logging the fallback would be worth adding.

---

## Known limitations

### Multimodal checkpoints are served effectively audio-only

There is no video ingestion path. [`_zero_visual`](../../backend/inference.py#L79) feeds a zero tensor to
the visual branch of any fusion model:

```python
def _zero_visual(self):
    return torch.zeros(1, self.cfg["visual"]["max_frames"], 1404, device=self.device)
```

Fusion checkpoints load and predict, but their visual half contributes nothing at inference time. **A
fusion model's reported evaluation accuracy therefore does not describe its served accuracy.** For
`decision_level` the degradation is graceful and quantifiable — the visual logits are whatever the
visual model outputs for an all-zero input, weighted by the learned `w₁`. For `feature_level` and
`attention` the model is operating well outside its training distribution.

If you serve a fusion model, evaluate it with the visual input zeroed to get the honest number.

### `window_sec` is not tied to the config

`AudioStreamBuffer` defaults to `window_sec=3.0` independently of `config.audio.duration`. Train a
2-second model and the stream will feed it 3-second windows — `_pad_or_crop` will centre-crop them to
2 seconds, so it will not crash, but a third of every window is silently discarded. Coupled by
convention only.

### The stream is single-connection-per-buffer but single-model-global

Each WebSocket connection gets its own `AudioStreamBuffer`, so concurrent clients do not corrupt each
other's audio. But they share one `engine` and therefore one model, and `POST /predict/switch` swaps it
for **all** connected clients mid-stream. Predictions before and after a switch come from different
models with no indication in the payload beyond `model_name`.

### No authentication on any endpoint

Including `/predict/switch`, which accepts an arbitrary filesystem path and calls `torch.load` with
`weights_only=False` — arbitrary unpickling. Do not expose this beyond localhost without a reverse proxy
that blocks it. See [deployment.md](deployment.md#security).

### No concurrency control on inference

`predict()` is synchronous and runs on the event loop thread for the WebSocket path. A slow forward pass
blocks all other connections. At 4 ms per inference on GPU this is fine; on CPU with several clients and
a fusion model it will not be. A thread pool (`run_in_executor`) or a batching queue would be the fix.

### No request logging or metrics

Startup prints two lines via `print()`; nothing else is logged. No request logs, no error aggregation, no
latency histogram, no structured logging. Adequate for a research demo, insufficient for anything with
users.

---

## Further reading

| Page | Contents |
|---|---|
| [api-reference.md](api-reference.md) | Every endpoint: request, response, status codes, examples |
| [websocket-protocol.md](websocket-protocol.md) | Message-by-message protocol specification |
| [inference-engine.md](inference-engine.md) | `InferenceEngine` and `AudioStreamBuffer` internals |
| [deployment.md](deployment.md) | Production concerns: CORS, reverse proxy, containers, security |
| [../architecture.md](../architecture.md) | How the backend fits the whole system |
| [../testing.md](../testing.md#test_apipy--20-tests) | The 20 API tests and their mocking strategy |
