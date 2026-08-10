# Configuration

[`config/settings.yaml`](../config/settings.yaml) is the single source of truth for data paths,
feature parameters, emotion mappings, model hyperparameters, training settings, and output
directories. Every script accepts `--config` so alternative files can be swapped in per experiment.

- [Two rules before you edit anything](#two-rules-before-you-edit-anything)
- [`data`](#data)
- [`audio`](#audio)
- [`visual`](#visual)
- [`emotions`](#emotions)
- [`model`](#model)
- [`training`](#training)
- [`output`](#output)
- [Environment variable overrides](#environment-variable-overrides)
- [Experiment recipes](#experiment-recipes)
- [What is not configurable](#what-is-not-configurable)

---

## Two rules before you edit anything

**1. Changing anything under `audio:` or `visual:` invalidates `datasets/processed/`.**

[`preprocess.py`](../scripts/preprocess.py#L54) skips files that already exist and does not record
which config produced them. Change `n_mels` from 128 to 64 and re-run, and you will silently end up
with a mix of 128-band and 64-band spectrograms — which fails at collation time with a confusing shape
error, or worse, does not fail at all. Always:

```bash
rm -rf datasets/processed/
python3 scripts/preprocess.py
```

**2. `emotions.unified` order defines the class indices.**

[`LABEL2IDX`](../src/datasets.py#L10) is built by enumerating `UNIFIED`, so position *is* the class
index. Reordering the list changes the meaning of every existing checkpoint's output layer — silently,
with no error. If you reorder it, retrain everything and update
[`frontend/src/constants.js`](../frontend/src/constants.js) to match.

Note also that `UNIFIED` is a **module-level constant in Python**, not read from the YAML. The
`emotions.unified` key documents the same list but does not drive it. Change both together.

---

## `data`

Dataset locations, relative to the repository root.

```yaml
data:
  ravdess_path:    "datasets/RAVDESS"
  cremad_path:     "datasets/CREMA-D"
  msp_improv_path: "datasets/MSP-IMPROV"
  processed_path:  "datasets/processed"
```

| Key | Purpose |
|---|---|
| `ravdess_path` | RAVDESS root; parser recurses for `*.wav` |
| `cremad_path` | CREMA-D root; parser expects `AudioWAV/` and `VideoFlash/` subdirectories |
| `msp_improv_path` | MSP-IMPROV root; parser expects `Audio/` and `Evalution.txt` |
| `processed_path` | Output root for `mel/`, `mfcc/`, `landmarks/`, `manifest.csv` |

Missing directories are skipped with a log line. Only if all three are absent does `load_datasets`
raise. Absolute paths work too.

---

## `audio`

Audio feature extraction. **Changing any of these invalidates the processed cache.**

```yaml
audio:
  sample_rate: 22050
  duration:    3.0
  n_mfcc:      40
  n_mels:      128
  n_fft:       2048
  hop_length:  512
  f_min:       20.0
  f_max:       8000.0
  use_delta:   true
  normalize:   true
```

| Key | Default | Effect | Notes |
|---|---|---|---|
| `sample_rate` | 22050 | Resample target for all audio | Half of CD rate; retains content to 11 kHz — ample for speech. Also the rate the browser's 16 kHz stream is resampled *up* to at serve time |
| `duration` | 3.0 | Fixed analysis window in seconds | Longer clips centre-cropped, shorter symmetrically zero-padded. **Must match `window_sec` in `AudioStreamBuffer`** |
| `n_mfcc` | 40 | Cepstral coefficients | With `use_delta: true`, feature rows = `3 × 40 = 120` |
| `n_mels` | 128 | Mel filterbank bands | Frequency axis of the mel spectrogram; sets `AudioCNNLSTM`'s derived LSTM input size |
| `n_fft` | 2048 | FFT window (~93 ms at 22.05 kHz) | Larger = finer frequency, coarser time |
| `hop_length` | 512 | Frame stride (~23 ms) | Sets the time axis: `floor(sr × duration / hop) + 1 = 130` frames |
| `f_min` | 20.0 | Lowest mel band edge (Hz) | Discards DC and inaudible rumble |
| `f_max` | 8000.0 | Highest mel band edge (Hz) | Above the speech-relevant band; caps the sparse top octave |
| `use_delta` | true | Append Δ and ΔΔ to MFCC | Adds temporal dynamics; triples the row count |
| `normalize` | true | Normalise features | Mel: global mean/std. MFCC: **per-coefficient** mean/std |

### Derived shapes

```
n_frames = floor(sample_rate × duration / hop_length) + 1
         = floor(22050 × 3.0 / 512) + 1 = 130

mel  → (n_mels, n_frames)            = (128, 130)
mfcc → (3 × n_mfcc, n_frames)        = (120, 130)
```

Both **measured**. [`_n_frames`](../src/models/builder.py#L19) computes the same value for model
construction.

The mel and MFCC normalisations differ deliberately: a mel spectrogram is a homogeneous
time–frequency image where a single global statistic is appropriate, whereas MFCC coefficients differ
in scale by orders of magnitude between low and high cepstral order, so each needs its own statistics.

---

## `visual`

```yaml
visual:
  max_frames: 75
  frame_size: [112, 112]
  normalize:  true
```

| Key | Default | Effect |
|---|---|---|
| `max_frames` | 75 | Landmark sequence length. At 25 fps this is 3 s, matching the audio window. Shorter sequences zero-padded at the end; longer truncated |
| `frame_size` | `[112, 112]` | Frames resized before FaceMesh. Smaller is faster; too small hurts landmark accuracy |
| `normalize` | true | Read from config but **not currently used** — `extract_visual_features` always normalises (centroid subtraction + max-radius scaling) |

`max_frames` is honoured throughout: `EmotionDataset` takes it as a constructor argument and
`train.py` / `evaluate.py` pass `cfg["visual"]["max_frames"]`. It used to be hard-coded as
`torch.zeros(75, 1404)` in `_load_visual`, so raising `max_frames` broke batch collation for samples
without video.

The landmark width itself is **not** a config key — it is derived from `REFINE_LANDMARKS` in
[`src/constants.py`](../src/constants.py), because it must match what MediaPipe actually returns rather
than whatever a config file claims. See
[features.md](features.md#fixed-the-landmark-width-was-hard-coded-three-times).

---

## `emotions`

The unified taxonomy and per-corpus mappings into it.

```yaml
emotions:
  unified: ["neutral", "happy", "sad", "angry", "fearful", "disgust"]

  ravdess_map:
    "01": "neutral"
    "02": "neutral"   # calm -> neutral
    "03": "happy"
    "04": "sad"
    "05": "angry"
    "06": "fearful"
    "07": "disgust"
    "08": null        # surprised — dropped

  cremad_map:
    "ANG": "angry"
    "DIS": "disgust"
    "FEA": "fearful"
    "HAP": "happy"
    "NEU": "neutral"
    "SAD": "sad"

  msp_improv_map:
    "A": "angry"
    "H": "happy"
    "S": "sad"
    "N": "neutral"
```

A `null` value drops those samples entirely — the parsers skip any row whose mapped label is `None`
(`if label is None: continue`). An emotion code absent from a map is dropped the same way.

Two mapping decisions with consequences for every reported number:

- **`calm` → `neutral`** because the two are acoustically close and no other corpus distinguishes
  them. Keeps the taxonomy shared; makes `neutral` over-represented and internally heterogeneous.
- **`surprised` → dropped** because only RAVDESS has it. A class present in one corpus alone is
  learnable from corpus-specific artefacts rather than affect.

MSP-IMPROV supplies only four of six classes, which shifts the class balance whenever it is included —
exactly what the class-weighted loss compensates for.

### Adding a corpus

```yaml
data:
  mycorpus_path: "datasets/MyCorpus"
emotions:
  mycorpus_map:
    "joy":      "happy"
    "rage":     "angry"
    "contempt": null      # outside the unified six
```

Then write the parser and register it — see
[architecture.md](architecture.md#adding-a-corpus).

---

## `model`

Per-architecture hyperparameters. Only the block for the architecture you are training is read.

```yaml
model:
  audio_cnn:
    channels: [32, 64, 128, 256]
    dropout:  0.3
  audio_cnn_lstm:
    cnn_channels: [32, 64, 128]
    lstm_hidden:  256
    lstm_layers:  2
    dropout:      0.3
  visual_lstm:
    hidden_dim:  256
    num_layers:  2
    dropout:     0.3
  fusion:
    strategy: "attention"
    n_heads:  8
    dropout:  0.3
```

### `audio_cnn`

| Key | Effect |
|---|---|
| `channels` | One `_ConvBlock` per entry; every block after the first is followed by `MaxPool2d(2)` + `Dropout2d`. Embedding dim = `channels[-1] × 16` (after `AdaptiveAvgPool2d((4,4))`) — so `256 → 4096` |
| `dropout` | `Dropout2d(dropout/2)` between conv blocks, `Dropout(dropout)` in the head |

### `audio_cnn_lstm`

| Key | Effect |
|---|---|
| `cnn_channels` | Conv blocks, each followed by `MaxPool2d(2)`. Three blocks → mel downsampled 8× on both axes: `(128, 130) → (16, 16)` |
| `lstm_hidden` | Per-direction hidden size. **Embedding dim = `2 × lstm_hidden` = 512** |
| `lstm_layers` | Stacked LSTM layers. Inter-layer dropout applies only when > 1 |
| `dropout` | LSTM inter-layer dropout and head dropout |

The LSTM input size is derived at construction from a dummy forward pass
([`audio.py`](../src/models/audio.py#L78)) — `C × F` after the CNN, `128 × 16 = 2048` by default. You
never compute it by hand, and changing `n_mels` or `cnn_channels` is safe.

### `visual_lstm`

| Key | Effect |
|---|---|
| `hidden_dim` | Per-direction hidden size. **Embedding dim = `2 × hidden_dim` = 512** |
| `num_layers` | Stacked layers |
| `dropout` | Inter-layer and head dropout |

Input dim comes from `LANDMARK_DIM` in [`src/constants.py`](../src/constants.py), not from this
config block — it is a property of the extractor, not a tunable.

**Keep `visual_lstm.hidden_dim` equal to `audio_cnn_lstm.lstm_hidden`.** When the two embedding dims
match, `CrossModalAttentionFusion` skips its projection layer (`nn.Identity` instead of `nn.Linear`).
It still works when they differ — the guard is there — but you gain a projection you did not intend.

### `fusion`

| Key | Effect |
|---|---|
| `strategy` | Read from config but **not used** — the strategy comes from `--model` on the command line. Vestigial |
| `n_heads` | `MultiheadAttention` heads for `attention`. **Must divide the embedding dim**: 512 / 8 = 64 per head. Ignored by the other two strategies |
| `dropout` | Attention dropout and head dropout |

### Measured parameter counts

Default config, `num_classes=6`:

| Model | Parameters |
|---|---:|
| `audio_cnn` | 1,438,694 |
| `audio_cnn_lstm` | 6,458,982 |
| `visual_lstm` | 3,055,750 |
| `feature_level` | 10,042,610 |
| `decision_level` | 9,514,734 |
| `attention` | 11,881,970 |

---

## `training`

```yaml
training:
  batch_size:              32
  epochs:                  100
  learning_rate:           1.0e-4
  weight_decay:            1.0e-4
  scheduler:               "cosine"
  early_stopping_patience: 15
  val_split:               0.15
  test_split:              0.15
  seed:                    42
  num_workers:             4
  pin_memory:              true
  amp:                     true
```

| Key | Default | Notes |
|---|---|---|
| `batch_size` | 32 | Fits ~8 GB for fusion models. Halve on OOM |
| `epochs` | 100 | Also `T_max` for cosine annealing — **changing it changes the LR schedule shape**, not just the cap |
| `learning_rate` | 1e-4 | AdamW initial LR; conservative, appropriate for small corpora |
| `weight_decay` | 1e-4 | AdamW decoupled decay |
| `scheduler` | `"cosine"` | Read but **not used** — `CosineAnnealingLR` is hard-coded. Vestigial |
| `early_stopping_patience` | 15 | Epochs without validation-loss improvement before stopping. The real terminator; `epochs` rarely binds |
| `val_split` | 0.15 | Fraction of **speakers**, not samples |
| `test_split` | 0.15 | Same. Train gets the remaining ~70% |
| `seed` | 42 | Seeds `torch`, `numpy`, and the split RNG. Same seed → same split → comparable runs |
| `num_workers` | 4 | DataLoader workers. Set to 0 when debugging to get readable tracebacks |
| `pin_memory` | true | Faster host→device copies; irrelevant on CPU |
| `amp` | true | Mixed precision. Gated on CUDA availability, so harmless on CPU |

`val_split` and `test_split` partition *speakers*, so the resulting sample fractions only approximate
0.15 — speakers contribute unequal numbers of clips. Each split gets at least one speaker
(`max(1, int(n × frac))`).

---

## `output`

```yaml
output:
  model_dir:   "models"
  log_dir:     "runs"
  results_dir: "results"
```

| Key | Written by | Contents |
|---|---|---|
| `model_dir` | `train.py` | `<model_name>_best.pt`. Also where `/models` looks for `*.pt` |
| `log_dir` | `train.py` | TensorBoard event files under `<log_dir>/<model_name>/` |
| `results_dir` | `evaluate.py` | `<model>_results.json`, `<model>_confusion.png` |

All three are gitignored (`models/*.pt`, `runs/`, `results/`).

> Note: the `/models` endpoint hard-codes `Path("models")` rather than reading `output.model_dir`
> ([`main.py`](../backend/main.py#L116)). Change `model_dir` and the endpoint will look in the wrong
> place.

---

## Environment variable overrides

The backend reads three variables; nothing else in the system uses environment configuration.

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_CHECKPOINT` | `models/audio_cnn_lstm_best.pt` | Checkpoint loaded at startup |
| `CONFIG_PATH` | `config/settings.yaml` | Config passed to `InferenceEngine` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

```bash
MODEL_CHECKPOINT=models/attention_best.pt \
CORS_ORIGINS=https://ser.example.org \
uvicorn backend.main:app --port 8000
```

The front end reads `VITE_API_URL` at build time (default `http://localhost:8000`). The WebSocket URL
is derived from it by protocol substitution, so `https://` correctly yields `wss://`.

---

## Experiment recipes

### Shorter window for lower latency

```yaml
audio:
  duration: 2.0     # → floor(22050 × 2 / 512) + 1 = 87 frames
```

Also update `window_sec` in [`AudioStreamBuffer`](../backend/stream.py#L32) — it defaults to 3.0
independently of the config and will otherwise feed 3-second windows to a 2-second model. And
re-run preprocessing.

### Finer temporal resolution

```yaml
audio:
  hop_length: 256   # → 259 frames instead of 130
```

Doubles the time axis and roughly doubles training cost. Re-run preprocessing.

### Smaller, faster model

```yaml
model:
  audio_cnn_lstm:
    cnn_channels: [16, 32, 64]
    lstm_hidden:  128           # → embed dim 256
    lstm_layers:  1
```

If you also want cross-attention fusion, set `visual_lstm.hidden_dim: 128` so the embedding dims still
match.

### Stronger regularisation for a small dataset

```yaml
model:
  audio_cnn_lstm:
    dropout: 0.5
training:
  weight_decay:            1.0e-3
  early_stopping_patience: 10
```

### Multiple configs side by side

```bash
cp config/settings.yaml config/experiment_short_window.yaml
# edit, then:
python3 scripts/preprocess.py --config config/experiment_short_window.yaml
python3 scripts/train.py      --config config/experiment_short_window.yaml --model audio_cnn_lstm
```

Point `processed_path` and `model_dir` at experiment-specific directories too, or the runs will
overwrite each other's caches and checkpoints.

---

## What is not configurable

Hard-coded values you would have to edit code to change:

| Value | Location | Notes |
|---|---|---|
| `UNIFIED` class list | [`src/datasets.py`](../src/datasets.py#L9) | The YAML `emotions.unified` key mirrors but does not drive it |
| Landmark dim (`LANDMARK_DIM`) | [`src/constants.py`](../src/constants.py) | Derived from the `REFINE_LANDMARKS` switch; every consumer imports it |
| Audio feature height | [`feature_height`](../src/models/builder.py) | Derived from `n_mels` or `n_mfcc * 3`, per the `--feature` flag |
| `window_sec` 3.0, `hop_sec` 0.5 | [`stream.py`](../backend/stream.py#L32) | Defaults in the constructor, not read from config |
| Optimiser (AdamW) | [`train.py`](../scripts/train.py#L126) | `scheduler` key is ignored; cosine is hard-coded |
| Gradient clip 1.0 | [`train.py`](../scripts/train.py#L67) | — |
| Model selection metric | [`train.py`](../scripts/train.py#L155) | Validation loss, not accuracy |
| Evaluation batch size 32 | [`evaluate.py`](../scripts/evaluate.py#L110) | Independent of `training.batch_size` |
| History cap 60 entries | [`useStream.js`](../frontend/src/hooks/useStream.js#L88) | `prev.slice(-59)` |
| Health poll interval 10 s | [`App.jsx`](../frontend/src/App.jsx#L26) | — |
| `/models` directory | [`main.py`](../backend/main.py#L116) | Hard-codes `"models"` |
