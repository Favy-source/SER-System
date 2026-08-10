# InferenceEngine and AudioStreamBuffer

The two classes that turn a checkpoint into predictions.
[`backend/inference.py`](../../backend/inference.py) · [`backend/stream.py`](../../backend/stream.py)

- [InferenceEngine](#inferenceengine)
  - [Construction](#construction)
  - [Why the checkpoint's config wins](#why-the-checkpoints-config-wins)
  - [Prediction entry points](#prediction-entry-points)
  - [The prediction core](#the-prediction-core)
  - [Internal helpers](#internal-helpers)
  - [Latency measurement](#latency-measurement)
- [AudioStreamBuffer](#audiostreambuffer)
- [Known issues](#known-issues)
- [Extending](#extending)

---

## InferenceEngine

Loads a trained checkpoint and predicts from a numpy array, raw bytes, or a file path.

```python
engine = InferenceEngine("models/audio_cnn_lstm_best.pt", "config/settings.yaml")
result = engine.predict_from_file("sample.wav")
```

### Construction

```python
def __init__(self, checkpoint_path, config_path="config/settings.yaml"):
    with open(config_path) as f:
        self.cfg = yaml.safe_load(f)

    self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    ckpt = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
    self.model_name = ckpt["model_name"]
    self.feature    = ckpt.get("feature", "mel")
    self.multimodal = is_multimodal(self.model_name)

    model = build_model(self.model_name, ckpt["cfg"], len(UNIFIED))   # ← checkpoint's cfg
    model.load_state_dict(ckpt["model"])
    model.eval()
    self.model = model.to(self.device)

    acfg = self.cfg["audio"]                                          # ← file's cfg
    self.sr         = acfg["sample_rate"]
    self._duration  = acfg["duration"]
    self._audio_cfg = acfg
```

Three things happen that are worth naming:

**`model.eval()` before `.to(device)`.** Order does not matter functionally, but eval mode must be set —
it disables dropout and switches BatchNorm to its running statistics. Forgetting it makes inference
non-deterministic and systematically worse. `test_eval_mode_no_dropout_variance` guards the property at
the model level.

**`weights_only=False` is required.** The checkpoint contains a config dict, not only tensors. This
permits arbitrary unpickling, so **only load checkpoints you trust** — and note that
`POST /predict/switch` accepts an arbitrary path from an unauthenticated caller, which makes this a real
security consideration rather than a theoretical one. See [deployment.md](deployment.md#security).

**`ckpt.get("feature", "mel")`** defaults for checkpoints predating the field. Cheap
backwards-compatibility.

### Why the checkpoint's config wins

Note the deliberate asymmetry in what each config is used for:

| Source | Used for |
|---|---|
| `ckpt["cfg"]` | **Architecture** — layer sizes, channel counts, hidden dimensions |
| `self.cfg` (the file) | **Runtime** — sample rate, duration, feature extraction parameters |

Architecture comes from the checkpoint because the weights only fit the architecture that produced them.
If `settings.yaml` has since changed `lstm_hidden` from 256 to 128, rebuilding from the file would
produce a model whose `state_dict` does not match, and the error would point at the tensor shapes rather
than at the config edit that caused it. Reading `ckpt["cfg"]` makes every historical checkpoint loadable
forever.

Feature parameters come from the file, which is a subtler trade: it means you *can* change the sample
rate or `n_mels` post-training and the engine will happily extract mismatched features and feed them to
a model expecting the old shape. That would surface as a shape error for `n_mels` (loud, fine) but as
silent quality degradation for `sample_rate` or `f_max` (quiet, bad). Reading feature parameters from
`ckpt["cfg"]` too would be safer, with the small cost of losing the ability to deliberately override
them.

### Prediction entry points

Three public methods forming a chain, each layer adding one concern:

```python
predict_from_file(path)     # open the file → bytes
    └─ predict_from_bytes(raw)   # decode, downmix, resample → numpy
        └─ predict(audio)             # pad/crop, features, forward, softmax
```

**`predict(audio: np.ndarray) -> dict`** — the core. Takes a float32 mono array of any length at the
model's expected sample rate.

**`predict_from_bytes(audio_bytes: bytes) -> dict`** — handles any format libsndfile can read:

```python
import soundfile as sf
audio, sr = sf.read(io.BytesIO(audio_bytes), always_2d=False, dtype="float32")
if audio.ndim > 1:
    audio = audio.mean(axis=1)                              # stereo → mono
if sr != self.sr:
    import librosa
    audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sr)
return self.predict(audio)
```

Averaging channels is the right downmix for emotion recognition — both channels carry the same voice,
and averaging improves the signal-to-noise ratio slightly. `soundfile` and `librosa` are imported lazily
inside the methods, so the resample path costs nothing when rates already agree.

**`predict_from_file(path: str) -> dict`** — reads the file and delegates. Convenience for scripts and
notebooks; the API uses `predict_from_bytes` directly on the upload body.

### The prediction core

```python
def predict(self, audio: np.ndarray) -> dict:
    t0 = time.perf_counter()

    audio  = self._pad_or_crop(audio.astype(np.float32))
    tensor = self._to_tensor(audio)

    with torch.no_grad():
        if self.multimodal:
            logits = self.model(tensor, self._zero_visual())
        else:
            logits = self.model(tensor)
        probs = F.softmax(logits, dim=1)[0].cpu().numpy()

    idx     = int(probs.argmax())
    latency = (time.perf_counter() - t0) * 1000

    return {
        "emotion":       IDX2LABEL[idx],
        "confidence":    round(float(probs[idx]), 4),
        "probabilities": {e: round(float(probs[i]), 4) for i, e in enumerate(UNIFIED)},
        "latency_ms":    round(latency, 2),
        "model_name":    self.model_name,
    }
```

- **`no_grad()`** — no autograd graph, less memory, faster.
- **`softmax(logits, dim=1)[0]`** — batch of one, so index 0 extracts the single result.
- **`round(..., 4)`** — keeps the JSON compact; means `probabilities` sums to ~1.0 rather than exactly 1.0.
- **`IDX2LABEL`** and the `enumerate(UNIFIED)` comprehension both come from
  [`src/datasets.py`](../../src/datasets.py), so serving decodes class indices with the exact mapping
  training used. A divergence here would produce a model that appears to work while systematically
  mislabelling — worth the shared import.

### Internal helpers

**`_pad_or_crop`** — forces the array to exactly `sr × duration` samples:

```python
n = int(self.sr * self._duration)
if len(audio) >= n:
    start = (len(audio) - n) // 2
    return audio[start : start + n]          # centre crop
pad = n - len(audio)
return np.pad(audio, (pad // 2, pad - pad // 2))   # symmetric zero-pad
```

Identical in behaviour to [`load_audio`](../../src/features.py#L17) in the training path, which is
essential — a different crop position at serve time than at train time would be a textbook train/serve
skew. It is duplicated rather than shared because `load_audio` takes a path and this takes an array;
extracting a common `pad_or_crop(audio, n)` helper would remove the risk of them drifting apart.

**`_to_tensor`** — extracts features and shapes them for the model:

```python
if self.feature == "mel":
    feat = mel_spectrogram(audio, self.sr, acfg["n_mels"], acfg["n_fft"],
                           acfg["hop_length"], acfg["f_min"], acfg["f_max"], acfg["normalize"])
    return torch.from_numpy(feat).float().unsqueeze(0).unsqueeze(0).to(self.device)
# mfcc
feat = mfcc_features(audio, self.sr, acfg["n_mfcc"], acfg["n_fft"],
                     acfg["hop_length"], acfg["use_delta"], acfg["normalize"])
return torch.from_numpy(feat).float().unsqueeze(0).unsqueeze(0).to(self.device)
```

Both branches double-unsqueeze to `(batch, channel, freq, time)` — `(1, 1, 128, 130)` for mel,
`(1, 1, 120, 130)` for MFCC. The MFCC branch used to unsqueeze once, producing 3-D `(1, 120, 130)`,
which `Conv2d` cannot accept. See [Fixed issues](#fixed-issues).

`mel_spectrogram` and `mfcc_features` are imported from `src.features` — the same functions
`preprocess.py` calls. This is the single most important line in the file for correctness.

**`_zero_visual`** — a placeholder visual input for fusion models:

```python
def _zero_visual(self):
    vcfg = self.cfg["visual"]
    return torch.zeros(1, vcfg["max_frames"], LANDMARK_DIM, device=self.device)
```

`LANDMARK_DIM` is imported from [`src/constants.py`](../../src/constants.py) — the same constant
`VisualLSTM` and `EmotionDataset` use, so the placeholder cannot drift from the model's input width.
It was previously a literal `1404` here, in `builder.py`, and in `datasets.py`.

There is no video ingestion path in the backend, so any fusion model is served with an all-zero visual
tensor. **A fusion checkpoint therefore runs effectively audio-only at serve time**, and its evaluation
accuracy does not describe its served accuracy. For `decision_level` the degradation is at least
interpretable — the visual branch's output for zero input, scaled by the learned `w₁`. For
`feature_level` and `attention` the model is operating outside its training distribution.

If you serve a fusion model, evaluate it with the visual input zeroed to get the honest figure. See
[evaluation.md](../evaluation.md#what-is-not-measured).

### Latency measurement

The timer spans `_pad_or_crop`, `_to_tensor` (including feature extraction), the forward pass, and
softmax. It excludes file decoding, resampling, HTTP overhead, and JSON serialisation.

That makes `latency_ms` a **much better guide to real-time feasibility** than the model-only benchmark in
[`evaluate.py`](../../scripts/evaluate.py), because feature extraction is typically the dominant cost —
`librosa.feature.melspectrogram` on a 3-second clip is commonly tens of milliseconds on CPU, potentially
several times the forward pass itself.

Two numbers, two purposes: `evaluate.py`'s benchmark compares architectures; `latency_ms` tells you
whether the live demo will feel responsive.

Note there is no CUDA synchronisation here, unlike in `evaluate.py`. The `.cpu()` call on the softmax
output forces a synchronisation implicitly, so the measurement is valid — but by accident rather than by
design.

---

## AudioStreamBuffer

Sliding-window inference over a live PCM stream. [`backend/stream.py`](../../backend/stream.py)

```python
buf = AudioStreamBuffer(engine, input_sr=16000, window_sec=3.0, hop_sec=0.5)
result = buf.push(pcm_bytes)     # dict, or None
```

### State

| Attribute | Purpose |
|---|---|
| `window_samples` | `input_sr × window_sec` — 48,000 at the defaults |
| `hop_samples` | `input_sr × hop_sec` — 8,000 |
| `target_sr` | `engine.sr` — the model's rate |
| `_buf` | Accumulated float32 samples |
| `_since_last` | Samples received since the last inference |

Note that window and hop are computed in the **client's** sample space, so the buffer holds
`window_sec` seconds of client audio regardless of the model's rate. Resampling happens after windowing.

### `push`

```python
pcm = np.frombuffer(chunk, dtype=np.float32)
self._buf = np.concatenate([self._buf, pcm])
self._since_last += len(pcm)

max_buf = self.window_samples * 2
if len(self._buf) > max_buf:
    self._buf = self._buf[-max_buf:]                 # bound memory

if len(self._buf) >= self.window_samples and self._since_last >= self.hop_samples:
    self._since_last = 0
    window = self._buf[-self.window_samples:].copy()  # most recent window
    if self.input_sr != self.target_sr:
        import librosa
        window = librosa.resample(window, orig_sr=self.input_sr, target_sr=self.target_sr)
    try:
        return self.engine.predict(window)
    except Exception as exc:
        return {"_error": str(exc)}
return None
```

Design points:

**Two gates, not one.** A full window *and* an elapsed hop. The hop gate is what makes arbitrary client
frame sizes safe — a client sending 128-sample blocks at 16 kHz produces 125 frames per second, and
without the gate every frame past the first window would trigger a forward pass. With it, inference
fires at most twice per second regardless.

**Memory is bounded at two windows.** 384 KB at 16 kHz. A connection open for hours uses constant
memory. Older audio is discarded because only the most recent window is ever used.

**`[-window_samples:]` takes the newest audio**, not the oldest. A live system should classify what was
just said.

**`.copy()`** detaches the window from the buffer before resampling, so `librosa` cannot mutate a view
of live state.

**Resample after windowing.** One resample per inference rather than one per frame. `librosa` is imported
lazily inside the branch, so the import never happens when rates agree.

**Exceptions become a sentinel, not a raise.** `{"_error": str(exc)}` lets the WebSocket handler send an
`error` frame and keep the connection open. A slightly awkward in-band signal, but `_error` cannot
collide with a real `PredictionResult` key.

### `reset`

```python
def reset(self):
    self._buf = np.zeros(0, dtype=np.float32)
    self._since_last = 0
```

Clears both buffer and counter, so the next prediction waits for a fresh full window. Triggered by the
`{"type": "reset"}` control frame — useful when the speaker changes, to stop a window straddling two
unrelated utterances.

### Window overlap

Successive windows overlap by `window_sec - hop_sec` = 2.5 s, or 83%. Consecutive predictions are
therefore highly correlated and single-window label flicker is visible in the UI. It also means each
prediction's effective "new information" is only 0.5 s. Temporal smoothing across predictions is on the
[roadmap](../../README.md#roadmap).

### Not tied to the config

`window_sec` defaults to 3.0 in the constructor, independently of `config.audio.duration`. Train a
2-second model and the stream will feed it 3-second windows — `_pad_or_crop` centre-crops them so it will
not crash, but a third of every window is silently discarded. Coupled by convention only; reading the
config here would be a small, worthwhile fix.

---

## Fixed issues

### MFCC tensors were 3-D and crashed the CNN models

`_to_tensor`'s mfcc branch applied one `unsqueeze(0)`, producing `(1, 120, 130)`, which `Conv2d` cannot
accept. The training path had the same defect
([`EmotionDataset._load_audio`](../../src/datasets.py)), so such a checkpoint could not be produced
either — the bug was self-consistent, which is why nothing failed loudly.

Both sides now unsqueeze twice. And because `AudioCNNLSTM` sizes its LSTM from the feature's frequency
height, `build_model` now takes the `feature` argument and `InferenceEngine` passes `self.feature` when
rebuilding — otherwise an mfcc checkpoint's state dict would not match the model built to receive it.

Covered by `test_inference_engine_mfcc_checkpoint` in
[`tests/test_integration.py`](../../tests/test_integration.py), which saves a real mfcc checkpoint,
loads it through `InferenceEngine`, asserts the tensor rank, and predicts.

### The landmark constant was hard-coded here too

`_zero_visual` used a literal `1404`, matching `builder.py` and `datasets.py` — all three assuming
`FaceMesh(refine_landmarks=True)` yields 468 landmarks when it yields 478. Now derived from
`LANDMARK_DIM` in [`src/constants.py`](../../src/constants.py). See
[features.md](../features.md#fixed-the-landmark-width-was-hard-coded-three-times).

---

## Known issues

### Pad/crop is duplicated

`_pad_or_crop` and `load_audio` implement identical logic in two places. They agree today; nothing
enforces that they continue to, and a divergence would be train/serve skew — the subtlest and most
damaging class of bug in a deployed model.

### No batching

`predict` handles one sample. With several concurrent WebSocket clients, inference is serialised on the
event loop thread. On GPU at ~4 ms per forward pass that is fine; on CPU with a fusion model it will not
be. A batching queue that accumulates windows across connections for a few milliseconds would improve
throughput substantially.

### Inference is synchronous on the event loop

`engine.predict` is a blocking call inside an `async` handler, so one client's slow forward pass delays
every other connection. `await loop.run_in_executor(None, engine.predict, window)` would fix it.

---

## Extending

### Adding a feature type

1. Implement the extractor in [`src/features.py`](../../src/features.py).
2. Add a branch to `_to_tensor` — **with the correct number of unsqueezes for the model's expected
   rank**, which is exactly what the mfcc branch got wrong. If the new feature has a different
   frequency height, extend [`feature_height`](../../src/models/builder.py) too.
3. Handle it in [`EmotionDataset._load_audio`](../../src/datasets.py#L166) too, so training and serving
   agree.
4. Add a test that feeds the new feature through a real model forward pass, not just the extractor.

### Adding real visual input

The largest gap in the serving path. A working implementation needs:

1. **Frame ingestion** — a tagged binary envelope on the WebSocket, or a second connection.
2. **Landmark extraction** — run MediaPipe FaceMesh server-side, or have the client send landmarks
   directly (cheaper and more private, since the video never leaves the browser).
3. **A `VisualStreamBuffer`** mirroring the audio one, accumulating `max_frames` of landmarks.
4. **Temporal alignment** between the audio and visual windows.
5. **`predict_multimodal(audio, visual)`** on the engine, replacing `_zero_visual`.

Client-side landmark extraction is worth serious consideration: MediaPipe has a JavaScript build, the
bandwidth is a few kilobytes per second instead of a video stream, and no video ever crosses the network
— a meaningful privacy property for anything clinical.

### Reducing latency

In rough order of expected benefit:

1. **Cache feature extraction across overlapping windows.** Successive windows share 83% of their audio,
   so most spectrogram frames are recomputed identically every 0.5 s. Computing only the new frames and
   shifting a rolling spectrogram would cut the dominant cost substantially.
2. **Move inference off the event loop** with `run_in_executor`, so concurrent clients do not queue.
3. **Batch across connections** for a few milliseconds.
4. **Quantise or export to ONNX** — `torch.quantization` dynamic quantisation on the LSTM layers, or
   ONNX Runtime, both give meaningful CPU speedups.
5. **Shorten the window** — `duration: 2.0` cuts both feature extraction and forward-pass cost, at the
   price of less temporal context. Requires retraining and updating `window_sec`.
