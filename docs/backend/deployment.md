# Deployment

Running the backend beyond `uvicorn --reload`. This is a research codebase, so read
[Security](#security) before exposing it to anything other than localhost.

- [Development](#development)
- [Environment variables](#environment-variables)
- [Production server](#production-server)
- [CORS](#cors)
- [Reverse proxy](#reverse-proxy)
- [Containers](#containers)
- [Serving the front end](#serving-the-front-end)
- [Security](#security)
- [Monitoring and health checks](#monitoring-and-health-checks)
- [Resource planning](#resource-planning)
- [Pre-deployment checklist](#pre-deployment-checklist)

---

## Development

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Run from the **repository root** — the default checkpoint and config paths are relative, and `/models`
resolves `Path("models")` against the working directory.

`--reload` watches for file changes and restarts, which means the checkpoint is reloaded on every save.
With a large model on GPU that adds a noticeable pause per edit; drop `--reload` when working on the
front end against a stable backend.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_CHECKPOINT` | `models/audio_cnn_lstm_best.pt` | Checkpoint loaded at startup |
| `CONFIG_PATH` | `config/settings.yaml` | Config passed to `InferenceEngine` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

```bash
MODEL_CHECKPOINT=/opt/ser/models/attention_best.pt \
CONFIG_PATH=/opt/ser/config/settings.yaml \
CORS_ORIGINS=https://ser.example.org \
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

All three are read at startup only. `MODEL_CHECKPOINT` can be superseded at runtime by
`POST /predict/switch`, but that does not persist across a restart.

There is no `.env` file support — `os.getenv` reads the process environment directly. Use a systemd unit,
a container environment, or a shell wrapper.

---

## Production server

`--reload` is for development. For anything else:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Why `--workers 1`

The temptation is to raise it for throughput. Don't, without thinking it through:

- **Each worker is a separate process and loads its own copy of the model.** Four workers means four
  copies of a 6.5M-parameter model in GPU memory, and on a single GPU they contend for it.
- **`engine` is module-global per process.** `POST /predict/switch` reaches whichever worker handles that
  request, leaving the others on the old model. Clients then get predictions from different models with no
  way to tell which, beyond the `model_name` field.
- **WebSocket connections are sticky to a worker**, so streaming works, but the model-consistency problem
  above applies to any client that reconnects.

If you need throughput, the right answers in order are: move inference off the event loop with
`run_in_executor`; batch across connections; then scale to multiple *machines* behind a load balancer,
each with one worker.

For process supervision use systemd, not `gunicorn` with uvicorn workers — the multi-worker caveats above
apply either way.

### systemd unit

```ini
# /etc/systemd/system/ser-backend.service
[Unit]
Description=SER System backend
After=network.target

[Service]
Type=simple
User=ser
WorkingDirectory=/opt/ser
Environment="MODEL_CHECKPOINT=/opt/ser/models/audio_cnn_lstm_best.pt"
Environment="CONFIG_PATH=/opt/ser/config/settings.yaml"
Environment="CORS_ORIGINS=https://ser.example.org"
ExecStart=/opt/ser/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Binding to `127.0.0.1` and putting a reverse proxy in front is the right shape — it lets the proxy own
TLS, rate limiting, and endpoint blocking.

---

## CORS

```python
_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The default `*` is right for local development and wrong for anything public. Set it explicitly:

```bash
CORS_ORIGINS=https://ser.example.org,https://staging.ser.example.org
```

> **`allow_origins=["*"]` with `allow_credentials=True` is an invalid combination** per the CORS
> specification. Browsers reject credentialed requests to a wildcard origin, so credentialed
> cross-origin requests will fail in a way that looks like a server bug. Since this API uses no cookies
> or auth headers, nothing currently breaks — but if you add authentication, you must set explicit
> origins or drop `allow_credentials`.

**CORS does not protect the WebSocket.** The WebSocket handshake is not subject to CORS, and this
implementation does not validate the `Origin` header. Any page on the internet can open a WebSocket to a
reachable instance and stream audio to it. Restrict at the network or proxy layer.

---

## Reverse proxy

The WebSocket needs explicit upgrade handling — this is the most common deployment failure.

### nginx

```nginx
upstream ser_backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name ser.example.org;

    ssl_certificate     /etc/letsencrypt/live/ser.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ser.example.org/privkey.pem;

    # Block the unauthenticated model-switch endpoint
    location = /predict/switch {
        return 403;
    }

    # WebSocket — upgrade headers are mandatory
    location /ws/ {
        proxy_pass         http://ser_backend;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host       $host;
        proxy_read_timeout 3600s;      # streams are long-lived
        proxy_send_timeout 3600s;
        proxy_buffering    off;        # do not buffer real-time frames
    }

    location / {
        proxy_pass       http://ser_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        client_max_body_size 25M;      # cap uploads — the app does not
    }
}
```

Four settings that matter:

- **`proxy_read_timeout` / `proxy_send_timeout`** — nginx's 60-second default kills an idle stream.
  A stream that is quiet between predictions counts as idle.
- **`proxy_buffering off`** on the WebSocket path — buffering adds latency to a real-time stream.
- **`client_max_body_size`** — the application reads the entire upload into memory with no size limit,
  so the proxy must impose one.
- **`return 403` on `/predict/switch`** — it is unauthenticated and takes an arbitrary filesystem path.

### Caddy

```
ser.example.org {
    @switch path /predict/switch
    respond @switch 403

    reverse_proxy 127.0.0.1:8000 {
        transport http {
            read_timeout 3600s
        }
    }
}
```

Caddy handles WebSocket upgrades and TLS automatically.

### Verifying

```bash
curl -s https://ser.example.org/health

# WebSocket upgrade — expect 101 Switching Protocols
curl -i -N \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  https://ser.example.org/ws/stream
```

A 200 or 400 instead of 101 means the upgrade headers are not being forwarded.

---

## Containers

No Dockerfile ships with the repository. A working starting point:

```dockerfile
FROM python:3.11-slim

# libsndfile is required by soundfile; libgl/libglib by opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY src/     ./src/
COPY backend/ ./backend/
COPY config/  ./config/

ENV MODEL_CHECKPOINT=/app/models/audio_cnn_lstm_best.pt \
    CONFIG_PATH=/app/config/settings.yaml \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t ser-backend .
docker run -p 8000:8000 -v "$PWD/models:/app/models:ro" ser-backend
```

Notes:

- **`libsndfile1` is required** — `soundfile` is a binding to it and fails at import without it.
- **Mount models as a read-only volume.** Baking a checkpoint into the image bloats it and couples model
  releases to image releases.
- **The image is large** — PyTorch alone is ~2.5 GB. `torch --index-url .../whl/cpu` gives a much smaller
  CPU-only wheel if you do not need GPU.
- **Do not copy `scripts/` or `tests/`** into a serving image; they are not needed and `scripts/` pulls
  in matplotlib and seaborn.
- **`PYTHONUNBUFFERED=1`** so the startup `print()` lines reach the container log immediately.

For GPU, base on `nvidia/cuda:12.1-runtime-ubuntu22.04`, install Python, and run with `--gpus all`.

---

## Serving the front end

Build produces static files:

```bash
cd frontend
VITE_API_URL=https://ser.example.org npm run build      # → frontend/dist/
```

`VITE_API_URL` is baked in **at build time**, not read at runtime — the built bundle contains the literal
URL. A different backend means a rebuild.

Serve `dist/` from nginx alongside the API:

```nginx
server {
    listen 443 ssl http2;
    server_name ser.example.org;

    root /opt/ser/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~ ^/(health|models|predict|docs|openapi.json) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /ws/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 3600s;
    }
}
```

Same-origin serving means CORS stops mattering — set `VITE_API_URL` to the empty string or the same
origin and the browser makes ordinary same-origin requests.

**TLS is not optional for the front end.** `getUserMedia` requires a secure context, so microphone
capture fails over plain HTTP on anything other than `localhost`.

---

## Security

This backend has **no authentication, no authorisation, and no rate limiting on any endpoint**. Treat it
as an internal service behind a proxy, not as an internet-facing API.

### `POST /predict/switch` is the sharpest edge

It is unauthenticated, accepts an arbitrary filesystem path, and leads to
`torch.load(..., weights_only=False)` — which unpickles arbitrary Python objects and is therefore a
code-execution primitive. Anyone who can reach the port and place or reference a file can potentially run
code as the service user.

**Block it at the proxy** (`return 403`, as above) unless you specifically need runtime model switching,
and if you do, put authentication in front of it.

### Unbounded upload size

```python
raw = await file.read()      # entire body into memory, no limit
```

A large upload is a trivial memory-exhaustion vector. Cap it at the proxy with `client_max_body_size`.

### The WebSocket is unauthenticated and unvalidated

No `Origin` check, no token, no per-connection limits. Any page on the internet can open a stream to a
reachable instance and consume CPU or GPU. Restrict by network, or add an auth token to the handshake.

### Internal detail in error messages

`422` responses embed the raw exception text, and WebSocket `error` frames send `str(exc)` verbatim.
Useful in development; in production it reveals library versions, file paths, and internal structure.

### Checkpoint provenance

`weights_only=False` is required because checkpoints embed a config dict. Only load checkpoints you
produced or trust — a malicious `.pt` file executes code on load.

### Hardening checklist

- [ ] Bind uvicorn to `127.0.0.1`; expose only through a reverse proxy
- [ ] Set `CORS_ORIGINS` explicitly; never `*` in production
- [ ] Block or authenticate `/predict/switch`
- [ ] Set `client_max_body_size`
- [ ] Terminate TLS at the proxy (required for `getUserMedia` anyway)
- [ ] Add rate limiting (`limit_req` in nginx) on `/predict/audio`
- [ ] Validate the WebSocket `Origin` header, or restrict by network
- [ ] Run as an unprivileged user with no write access to `models/`
- [ ] Consider whether `/docs` and `/openapi.json` should be public

### If you ever handle patient audio

Everything above is table stakes; none of it is sufficient. Clinical or patient speech is
human-subjects data:

- Ethics approval and documented informed consent **before** any recording.
- Encryption in transit and at rest; a defined retention and deletion policy.
- Audit logging of access.
- Consideration of whether audio should leave the device at all — client-side inference avoids the entire
  question.
- Applicable data-protection law (Nigeria's NDPA, GDPR if EU subjects are involved, HIPAA in a US
  clinical context).

The current implementation logs nothing, encrypts nothing at rest, retains nothing — which is
accidentally privacy-preserving but by omission rather than design. Do not mistake that for compliance.

---

## Monitoring and health checks

```bash
curl -sf localhost:8000/health || echo "backend down"
```

| Signal | Meaning |
|---|---|
| Connection refused | Process down |
| `200` with `model_loaded: false` | Process up, model missing — prediction endpoints will 503 |
| `200` with `model_loaded: true` | Fully operational |

`status` is unconditionally `"ok"`, which makes `/health` a good **liveness** probe. Use `model_loaded`
for **readiness**:

```yaml
livenessProbe:
  httpGet: { path: /health, port: 8000 }
  initialDelaySeconds: 30
  periodSeconds: 10
readinessProbe:
  exec:
    command: ["sh", "-c", "curl -sf localhost:8000/health | grep -q '\"model_loaded\":true'"]
  periodSeconds: 10
```

`initialDelaySeconds` needs to cover model loading — a fusion model on GPU can take several seconds.

### What is not instrumented

Two `print()` calls at startup and nothing else. No request logs, no error aggregation, no latency
histogram, no structured logging, no metrics endpoint. For a research demo that is acceptable; for
anything with users, add:

- `logging` instead of `print`, at INFO with a formatter
- Request/response middleware logging method, path, status, and duration
- A `/metrics` endpoint (`prometheus-fastapi-instrumentator` is a two-line addition)
- Error aggregation for the exception paths, which currently vanish into stdout

---

## Resource planning

### Memory

| Component | Approximate |
|---|---|
| Python + PyTorch import | ~400 MB RSS |
| `audio_cnn_lstm` weights (fp32) | ~26 MB |
| `attention` weights (fp32) | ~48 MB |
| Per-connection `AudioStreamBuffer` | ~384 KB |
| Per-request feature extraction | a few MB, transient |

A single-model CPU instance is comfortable in 1 GB. GPU adds CUDA context (~300–600 MB device memory)
plus weights.

### CPU and latency

The dominant cost at serve time is **feature extraction**, not the forward pass —
`librosa.feature.melspectrogram` on a 3-second clip is commonly tens of milliseconds on CPU, potentially
several times the model's own ~4 ms. Watch the `latency_ms` field in prediction responses; it includes
both.

Each streaming client generates up to 2 inferences per second. Since inference runs synchronously on the
event loop, the practical concurrency limit is roughly `1 / (2 × latency_seconds)` clients before
predictions start falling behind real time. At 30 ms end-to-end that is around 15 clients; at 150 ms on a
slower CPU with a fusion model, around 3.

Raising that limit means moving inference off the event loop (`run_in_executor`), then batching, then
caching feature extraction across overlapping windows — see
[inference-engine.md](inference-engine.md#reducing-latency).

### Bandwidth

Float32 mono at 16 kHz is 64 KB/s per client upstream — 512 kbit/s. Not trivial for many concurrent
clients on a constrained link. Int16 would halve it at negligible quality cost, but would require a
format field in the handshake and a conversion server-side.

---

## Pre-deployment checklist

**Correctness**

- [ ] A checkpoint exists and `MODEL_CHECKPOINT` points at it
- [ ] `/health` reports `model_loaded: true`
- [ ] `POST /predict/audio` returns a sensible prediction for a known file
- [ ] A WebSocket client receives predictions after ~3 seconds
- [ ] If serving a fusion model, either a webcam client is streaming landmarks, or you have accepted
      that it runs audio-only on a zero visual tensor
      ([why](inference-engine.md#internal-helpers))
- [ ] `frontend/public/mediapipe/` populated if the front end needs face tracking
      (`npm run setup:mediapipe`)

**Configuration**

- [ ] `CORS_ORIGINS` set explicitly
- [ ] `CONFIG_PATH` points at the intended config
- [ ] Working directory is correct for relative paths
- [ ] Front end built with the right `VITE_API_URL`

**Security**

- [ ] uvicorn bound to `127.0.0.1`, proxy in front
- [ ] `/predict/switch` blocked or authenticated
- [ ] `client_max_body_size` set
- [ ] TLS terminated (required for microphone access)
- [ ] Rate limiting on `/predict/audio`
- [ ] Running as an unprivileged user

**Operations**

- [ ] Process supervision (systemd or container restart policy)
- [ ] WebSocket timeouts raised above the default 60 s
- [ ] Health checks configured
- [ ] Logs going somewhere durable
- [ ] Model files backed up outside the deployment
