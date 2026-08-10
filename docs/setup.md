# Setup

Getting the system running from a fresh clone.

- [Prerequisites](#prerequisites)
- [Backend installation](#backend-installation)
- [Front-end installation](#front-end-installation)
- [GPU setup](#gpu-setup)
- [Verifying the installation](#verifying-the-installation)
- [Running the system](#running-the-system)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| Python | 3.10 | `InferenceEngine \| None` union syntax in `backend/main.py` requires 3.10+ |
| Node.js | 18 | Vite 4 requirement |
| pip | 23 | Older pip struggles with PyTorch wheel resolution |
| ffmpeg | any | **Optional** — only needed for mp3 input |
| CUDA | 11.8 / 12.x | **Optional** — mixed precision activates automatically when present |
| Disk | ~15 GB | PyTorch (~2.5 GB) + corpora + extracted features |
| RAM | 8 GB | 16 GB is comfortable for preprocessing large corpora |

Verify:

```bash
python3 --version    # 3.10+
node --version       # v18+
nvidia-smi           # optional; shows driver and CUDA version
```

The system runs entirely on CPU. Training the fusion models on CPU is slow but not impossible; the
serving path is comfortable on CPU — inference is a single forward pass over a `(1, 1, 128, 130)`
tensor.

---

## Backend installation

```bash
git clone <your-repo-url> SER-System
cd SER-System

python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r backend/requirements.txt
```

`.venv/` and `venv/` are both gitignored.

### What gets installed

| Package | Role |
|---|---|
| `torch`, `torchaudio`, `torchvision` | Model definitions, training, inference |
| `librosa`, `soundfile` | Audio loading, resampling, mel/MFCC extraction |
| `mediapipe`, `opencv-python` | FaceMesh landmark extraction, video decoding |
| `scikit-learn` | Class weights, accuracy/F1, confusion matrix, classification report |
| `numpy`, `pandas` | Arrays and the manifest DataFrame |
| `pyyaml` | Config loading |
| `matplotlib`, `seaborn` | Confusion-matrix heatmaps |
| `tensorboard` | Training curves |
| `tqdm` | Progress bars |
| `einops` | Listed in requirements; not currently imported anywhere |
| `fastapi`, `uvicorn[standard]`, `websockets`, `python-multipart` | The service layer |

`pytest` is **not** in `requirements.txt` — install it separately to run the suite:

```bash
pip install pytest
```

### Minimal installs

For serving only (no training, no visual features), these suffice:

```bash
pip install torch librosa soundfile numpy pyyaml fastapi "uvicorn[standard]" python-multipart
```

`mediapipe` and `opencv-python` are the heaviest optional dependencies. `src/features.py` guards their
import ([`features.py`](../src/features.py#L9)) and sets `_MEDIAPIPE = False` when unavailable —
`extract_visual_features` then returns `None` instead of raising, and audio-only work proceeds
normally.

---

## Front-end installation

```bash
cd frontend
npm install
```

Only four packages: `react`, `react-dom`, `vite`, `@vitejs/plugin-react`. No UI framework, no state
library, no test runner.

---

## GPU setup

If `nvidia-smi` works but `torch.cuda.is_available()` is `False`, the CPU-only wheel was installed.
Reinstall from the CUDA index:

```bash
pip uninstall torch torchaudio torchvision
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu121
```

Verify:

```bash
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
```

No code changes are needed either way. Device selection is
`torch.device("cuda" if torch.cuda.is_available() else "cpu")` in every entry point, and mixed
precision is gated on `tc["amp"] and device.type == "cuda"`
([`train.py`](../scripts/train.py#L128)) — so `amp: true` in the config is harmless on a CPU machine.

Approximate GPU memory at `batch_size: 32`:

| Model | Peak (mel input) |
|---|---|
| `audio_cnn` | ~1.5 GB |
| `audio_cnn_lstm` | ~2.5 GB |
| `visual_lstm` | ~1.5 GB |
| fusion variants | ~4–5 GB |

Halve `batch_size` if you hit OOM; consider lowering the learning rate slightly to compensate for the
noisier gradient.

---

## Verifying the installation

```bash
python3 -m pytest
```

Expected:

```
collected 127 items
tests/test_api.py ....................            [ 15%]
tests/test_datasets.py .................................  [ 41%]
tests/test_features.py ................            [ 54%]
tests/test_integration.py .............................   [ 77%]
tests/test_model.py .............................  [100%]
======== 127 passed in 32.66s ========
```

The suite needs no corpora, no checkpoints, and no GPU — it uses synthetic sine waves and a mocked
inference engine. If it passes, the library and service layers are correctly installed.

Check optional dependencies:

```bash
python3 -c "import mediapipe, cv2; print('visual features available')"
python3 -c "from src.features import _MEDIAPIPE; print('_MEDIAPIPE =', _MEDIAPIPE)"
```

---

## Running the system

### Backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

On a fresh clone you will see:

```
[SER] No checkpoint at 'models/audio_cnn_lstm_best.pt' — prediction endpoints will return 503
```

That is correct behaviour, not an error — see
[backend/README.md](backend/README.md#startup-and-graceful-degradation). Once a checkpoint exists:

```bash
MODEL_CHECKPOINT=models/audio_cnn_lstm_best.pt uvicorn backend.main:app --port 8000
```

```
[SER] Loaded 'audio_cnn_lstm' on cuda
```

Interactive OpenAPI docs: <http://localhost:8000/docs>.

### Front end

```bash
cd frontend
npm run dev        # http://localhost:3000
```

Vite is configured with a `/api` → `localhost:8000` proxy
([`vite.config.js`](../frontend/vite.config.js)), though the app currently talks to the backend
directly via `VITE_API_URL` and relies on the backend's permissive CORS instead.

To point at a non-default backend:

```bash
VITE_API_URL=http://192.168.1.50:8000 npm run dev
```

The WebSocket URL is derived from it — `API_URL.replace(/^http/, 'ws') + '/ws/stream'` — so `https`
correctly becomes `wss`.

### Production build

```bash
npm run build      # → frontend/dist/
npm run preview    # serve the build locally
```

`frontend/dist/` is gitignored.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'src'`

Run from the repository root. `backend/` and `scripts/` insert the project root into `sys.path`
themselves, but that resolves relative to the file, and the working directory still matters for
relative config and data paths.

```bash
cd /path/to/SER-System
python3 scripts/train.py --model audio_cnn_lstm
```

### `ModuleNotFoundError: No module named 'mediapipe'`

Expected if you skipped the optional visual dependencies. Audio-only work is unaffected;
`extract_visual_features` returns `None`. Install with `pip install mediapipe opencv-python` if you
need the visual path. Note that mediapipe wheels are unavailable for some Python/platform
combinations — check PyPI for your version.

### `RuntimeError: No datasets found. Check paths in config/settings.yaml.`

`load_datasets` raised because none of the three dataset directories exist. It only needs *one*.
Confirm the paths in the config match your layout — see [datasets.md](datasets.md) for the exact
expected structure.

### `FileNotFoundError: datasets/processed/manifest.csv`

`train.py` was run before `preprocess.py`. Run feature extraction first.

### `RuntimeError: Given groups=1, weight of size [32, 1, 3, 3], expected input[...] to have 1 channels`

This was a bug in the MFCC path — a missing channel axis, and an LSTM width derived from `n_mels`
regardless of the feature in use. Both are fixed; see
[known issues](../README.md#known-issues-and-limitations). If it recurs, check that `build_model` is
being passed the `feature` argument.

### `HTTP 503: Model not loaded`

No checkpoint. Either train one, or point `MODEL_CHECKPOINT` at an existing `.pt`. Verify with
`curl -s localhost:8000/health`.

### Microphone permission denied in the browser

`getUserMedia` requires a **secure context**: `https://`, or `http://localhost` (which browsers treat
as secure). Accessing the dev server via a LAN IP over plain HTTP will fail. Either use `localhost`, or
put the dev server behind TLS.

### `Cannot reach backend. Is it running on port 8000?`

The WebSocket `onerror` handler surfaced a connection failure. Check the backend is running, that
`VITE_API_URL` points at it, and that no proxy is stripping the WebSocket upgrade — see
[backend/deployment.md](backend/deployment.md#reverse-proxy).

### CUDA out of memory

Lower `training.batch_size` in the config. Fusion models need roughly twice what the unimodal ones do.

### AMP-related warnings on recent PyTorch

`torch.cuda.amp.GradScaler()` ([`train.py`](../scripts/train.py#L128)) is the deprecated spelling. It
still works; the modern form is `torch.amp.GradScaler("cuda")`. Harmless for now.
