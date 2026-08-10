# API reference

Base URL `http://localhost:8000` by default. Interactive OpenAPI docs at `/docs`, machine-readable
schema at `/openapi.json`.

| Method | Path | Tag | Purpose |
|---|---|---|---|
| `GET` | [`/health`](#get-health) | system | Liveness and model status |
| `GET` | [`/models`](#get-models) | system | List available checkpoints |
| `POST` | [`/predict/audio`](#post-predictaudio) | prediction | Predict from an uploaded file |
| `POST` | [`/predict/switch`](#post-predictswitch) | system | Hot-swap the active checkpoint |
| `WS` | [`/ws/stream`](#ws-wsstream) | — | Real-time streaming — see [websocket-protocol.md](websocket-protocol.md) |

There is **no authentication on any endpoint**. See [deployment.md](deployment.md#security).

---

## `GET /health`

Liveness check and model status. Never fails — a running server always returns 200, and the
`model_loaded` flag carries the actual state.

### Response `200`

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_name": "audio_cnn_lstm",
  "device": "cuda",
  "sample_rate": 22050
}
```

With no checkpoint loaded:

```json
{
  "status": "ok",
  "model_loaded": false,
  "model_name": null,
  "device": "n/a",
  "sample_rate": 0
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `str` | Always `"ok"` — it is a liveness signal, not model status |
| `model_loaded` | `bool` | **The field that matters.** `false` means prediction endpoints return 503 |
| `model_name` | `str \| null` | Architecture name from the checkpoint |
| `device` | `str` | `"cuda"`, `"cpu"`, or `"n/a"` |
| `sample_rate` | `int` | The model's expected rate; `0` when unloaded |

`status` being unconditionally `"ok"` is intentional: it separates *is the process alive* from *is the
model ready*, which is what lets a container orchestrator use this as a liveness probe while the front
end uses `model_loaded` for a readiness signal.

### Example

```bash
curl -s localhost:8000/health | python3 -m json.tool
```

The front end polls this every 10 seconds ([`App.jsx`](../../frontend/src/App.jsx#L26)) and renders the
result as the header status dot. A fetch failure is mapped to
`{status: 'offline', model_loaded: false}` client-side, so an unreachable backend and a model-less
backend are visually distinguishable.

---

## `GET /models`

List checkpoint files discoverable under `models/`.

### Response `200`

```json
{
  "checkpoints": [
    "models/attention_best.pt",
    "models/audio_cnn_lstm_best.pt",
    "models/decision_level_best.pt"
  ],
  "active": "audio_cnn_lstm"
}
```

Empty directory:

```json
{"checkpoints": [], "active": null}
```

Missing directory:

```json
{"checkpoints": []}
```

| Field | Type | Notes |
|---|---|---|
| `checkpoints` | `list[str]` | Sorted paths matching `models/*.pt` |
| `active` | `str \| null` | The **model name**, not a path — cannot be compared directly to a `checkpoints` entry |

Two quirks worth knowing:

- **The response shape varies.** When `models/` does not exist, `active` is omitted entirely rather than
  being `null`. A client must handle the key being absent.
- **`active` is a model name, not a path.** `"audio_cnn_lstm"` versus
  `"models/audio_cnn_lstm_best.pt"`. Matching them requires string manipulation on the client. Returning
  the loaded path as well would be a small, worthwhile change.

The endpoint hard-codes `Path("models")` rather than reading `output.model_dir` from the config
([`main.py`](../../backend/main.py#L116)), so a non-default `model_dir` will not be reflected here.

### Example

```bash
curl -s localhost:8000/models | python3 -m json.tool
```

---

## `POST /predict/audio`

Upload an audio file and receive an emotion prediction.

### Request

`multipart/form-data` with one field:

| Field | Type | Notes |
|---|---|---|
| `file` | binary | Any format readable by libsndfile: wav, flac, ogg. mp3 needs ffmpeg + pydub |

Stereo files are averaged to mono. Files at a rate other than the model's are resampled with librosa.
Files longer than 3 seconds are centre-cropped; shorter ones symmetrically zero-padded.

There is **no file-size limit** and the entire body is read into memory before processing
(`raw = await file.read()`). See [deployment.md](deployment.md#security).

### Response `200`

```json
{
  "emotion": "happy",
  "confidence": 0.8734,
  "probabilities": {
    "neutral": 0.0412,
    "happy":   0.8734,
    "sad":     0.0201,
    "angry":   0.0310,
    "fearful": 0.0221,
    "disgust": 0.0122
  },
  "latency_ms": 12.47,
  "model_name": "audio_cnn_lstm"
}
```

| Field | Type | Notes |
|---|---|---|
| `emotion` | `str` | `argmax` over `probabilities` |
| `confidence` | `float` | The max probability, 4 dp. **Uncalibrated** — see below |
| `probabilities` | `dict[str, float]` | All six classes, 4 dp, sums to ~1.0 (rounding) |
| `latency_ms` | `float` | pad/crop + feature extraction + forward + softmax. Excludes decode and HTTP |
| `model_name` | `str` | Architecture that produced this prediction |

**`confidence` is a raw softmax output and is not calibrated.** Neural networks are typically
overconfident; 0.87 does not mean "87% likely correct". Do not present it to a user as a probability of
correctness without temperature scaling on a validation set first. See
[evaluation.md](../evaluation.md#what-is-not-measured).

`probabilities` always contains all six keys in `UNIFIED` order, so a client can render a fixed set of
bars without reflow — which is exactly what
[`ProbabilityBars.jsx`](../../frontend/src/components/ProbabilityBars.jsx) relies on.

### Errors

| Code | Detail | Cause |
|---|---|---|
| `503` | "Model not loaded. Train a model first and set MODEL_CHECKPOINT." | No checkpoint |
| `422` | "Empty file." | Zero-byte upload |
| `422` | "Could not process audio: `<exception>`" | Undecodable, corrupt, or unsupported format |

The 422 detail embeds the raw exception message, which is helpful in development and leaks internal
detail in production.

### Examples

```bash
curl -X POST localhost:8000/predict/audio -F "file=@sample.wav"
```

```python
import requests
r = requests.post("http://localhost:8000/predict/audio",
                  files={"file": open("sample.wav", "rb")})
print(r.json()["emotion"], r.json()["confidence"])
```

```javascript
const form = new FormData();
form.append('file', file);
const res  = await fetch(`${API_URL}/predict/audio`, { method: 'POST', body: form });
const data = await res.json();
if (!res.ok) throw new Error(data.detail ?? 'Upload failed');
```

---

## `POST /predict/switch`

Replace the active checkpoint without restarting the server.

### Request

Query parameter, not a body:

| Parameter | Type | Notes |
|---|---|---|
| `checkpoint` | `str` | Path to a `.pt` file, relative to the working directory or absolute |

```bash
curl -X POST "localhost:8000/predict/switch?checkpoint=models/attention_best.pt"
```

### Response `200`

```json
{"status": "ok", "model": "attention", "device": "cuda"}
```

The new engine is loaded **before** the old one is discarded, so a failed load leaves the previous model
serving:

```python
new_engine = _load_engine(checkpoint, cfg)
if new_engine is None:
    raise HTTPException(404, f"Checkpoint not found: {checkpoint!r}")
engine = new_engine          # only reached on success
```

### Errors

| Code | Detail | Cause |
|---|---|---|
| `404` | "Checkpoint not found: `<path>`" | File missing **or** load failed for any reason |

The 404 conflates "does not exist" with "exists but is corrupt / incompatible / not a checkpoint",
because `_load_engine` returns `None` for all of them. The real reason is printed to the server's stdout
but not returned. A 404 for missing and 422 for unloadable would be more useful.

### Two cautions

**This endpoint is unauthenticated and takes an arbitrary filesystem path.** `InferenceEngine` calls
`torch.load(..., weights_only=False)`, which unpickles arbitrary Python objects — a code-execution
primitive if an attacker can place a file on the filesystem and name it here. Never expose this beyond
localhost without blocking it at a reverse proxy.

**It affects every connected client.** The engine is module-global. An in-flight WebSocket stream will
begin receiving predictions from the new model mid-session, distinguishable only by the `model_name`
field changing.

---

## `WS /ws/stream`

Real-time emotion recognition over a WebSocket. Full protocol specification:
[websocket-protocol.md](websocket-protocol.md).

Summary:

1. Connect.
2. Send JSON `{"sample_rate": 16000}`.
3. Receive `{"type": "ready", "payload": {...}}`.
4. Send raw float32 PCM as binary frames, any chunk size.
5. Receive `{"type": "prediction", "payload": {...}}` roughly twice per second once the buffer fills.
6. Optionally send `{"type": "reset"}` or `{"type": "ping"}`.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/stream');
ws.binaryType = 'arraybuffer';
ws.onopen = () => ws.send(JSON.stringify({ sample_rate: 16000 }));
ws.onmessage = (evt) => {
  const { type, payload } = JSON.parse(evt.data);
  if (type === 'prediction') console.log(payload.emotion, payload.confidence);
};
```

---

## Status code summary

| Code | Meaning in this API |
|---|---|
| `200` | Success |
| `404` | Checkpoint not found or unloadable (`/predict/switch` only) |
| `422` | Unprocessable audio — empty file or decode failure |
| `503` | No model loaded; the request is valid but cannot be served yet |
| `1011` | WebSocket close code — internal error, sent when no model is loaded |

FastAPI's own `422` for request-validation failures (a missing `file` field, a missing `checkpoint`
query parameter) uses the standard Pydantic error envelope, which differs from this API's
`{"detail": "…"}` shape.

---

## Client implementation notes

**Poll `/health`, do not assume.** The model can appear (someone finished training and restarted) or
change (`/predict/switch`) at any time. The front end polls every 10 s.

**Handle 503 as a normal state, not an error.** On a fresh deployment it is the expected response until
a model exists. Render it as "no model loaded", not as a crash.

**Read `model_name` from every prediction.** It is the only way to know which model produced a result,
and it can change mid-session.

**Do not trust `confidence` as a probability of correctness.** Uncalibrated.

**Expect the `/models` response shape to vary.** `active` may be absent, not just null.

**Prefer the WebSocket for continuous audio.** Repeated `POST /predict/audio` calls re-decode and
re-establish a request per window; the WebSocket amortises all of that and lets the server manage
windowing.
