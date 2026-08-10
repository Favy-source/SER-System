# Feature extraction

What the models actually see. All three feature types come from
[`src/features.py`](../src/features.py) and are shared between training and serving — the same
functions run in `preprocess.py` and in `InferenceEngine`, which is what structurally prevents
train/serve skew.

- [The fixed 3-second window](#the-fixed-3-second-window)
- [Log-mel spectrogram](#log-mel-spectrogram)
- [MFCC + Δ + ΔΔ](#mfcc--δ--δδ)
- [Facial landmarks](#facial-landmarks)
- [Normalisation strategies](#normalisation-strategies)
- [Storage and caching](#storage-and-caching)
- [Numerical robustness](#numerical-robustness)
- [Known issues](#known-issues)

---

## The fixed 3-second window

Every model expects a fixed-size input, so [`load_audio`](../src/features.py#L17) forces every clip to
exactly `sample_rate × duration` samples — 66,150 at the defaults:

```python
audio, _ = librosa.load(path, sr=sr, mono=True)
n = int(sr * duration)
if len(audio) >= n:
    start = (len(audio) - n) // 2
    audio = audio[start : start + n]        # centre crop
else:
    pad = n - len(audio)
    audio = np.pad(audio, (pad // 2, pad - pad // 2))   # symmetric zero-pad
```

**Centre-cropping, not head-cropping.** In acted corpora the emotional peak sits mid-utterance and the
edges are lead-in silence and trailing decay. Taking the first 3 seconds would systematically capture
onset; centre-cropping captures the part carrying the affect. `test_load_audio_crop_is_centered`
asserts the crop position rather than just the length.

**Symmetric padding.** `(pad // 2, pad - pad // 2)` splits the deficit across both ends, with the odd
sample going to the tail. Keeps short clips centred so the model does not learn "content on the left"
as a feature of short utterances.

`librosa.load(sr=sr)` resamples on load, so mixed-rate corpora need no separate step —
`test_load_audio_resamples` writes a 44.1 kHz file and asserts the loaded length matches the 22.05 kHz
target.

The same pad/crop logic is reimplemented in
[`InferenceEngine._pad_or_crop`](../backend/inference.py#L56), because at serve time the audio arrives
as an array rather than a path. The two are duplicated but identical; worth unifying.

---

## Log-mel spectrogram

The default feature. `(128, 130)` — **measured**.

```python
mel = librosa.feature.melspectrogram(
    y=audio, sr=sr, n_mels=128, n_fft=2048, hop_length=512, fmin=20.0, fmax=8000.0,
)
log_mel = librosa.power_to_db(mel, ref=np.max)
if normalize:
    log_mel = (log_mel - log_mel.mean()) / (log_mel.std() + 1e-8)
```

### Three steps, three reasons

**1. Mel filterbank.** An STFT is projected onto 128 triangular filters spaced on the mel scale, which
is approximately linear below 1 kHz and logarithmic above — matching human pitch perception. Two
consequences: the low-frequency region where speech formants live gets more resolution, and 1025 FFT
bins collapse to 128, an 8× reduction with little perceptual loss.

`fmin=20` discards DC offset and inaudible rumble; `fmax=8000` caps the band above which speech
carries little emotional information while removing the sparse, noisy top octave.

**2. Power → decibels.** `power_to_db` applies `10 · log₁₀(S / ref)` with `ref=np.max`, so the loudest
component becomes 0 dB and everything else is negative. Two things this buys: perceptual loudness is
logarithmic, so dB matches how humans hear intensity differences; and per-clip max referencing gives
free amplitude normalisation, so recording gain does not become a feature.

**3. Global standardisation.** Zero mean, unit variance across the whole spectrogram. The `1e-8`
denominator guard is what makes a silent (constant) input safe.

### Shape derivation

```
n_frames = floor(sample_rate × duration / hop_length) + 1
         = floor(22050 × 3.0 / 512) + 1
         = floor(129.199…) + 1 = 130
```

`n_fft=2048` is a ~93 ms analysis window; `hop_length=512` gives ~23 ms frame stride and 75% overlap.
Both are standard for speech: long enough to resolve pitch harmonics, short enough to track formant
transitions.

[`_n_frames`](../src/models/builder.py#L19) computes the same value for model construction, so the
dummy forward pass that sizes `AudioCNNLSTM`'s LSTM input uses the true frame count.

### Why mel over raw waveform or STFT

Raw waveform needs far more data and much larger models to learn a time–frequency decomposition the
mel transform gives for free. A linear STFT wastes resolution on high frequencies that carry little
emotional content. On corpora of a few thousand clips, the mel spectrogram's inductive bias is worth
more than the flexibility a learned front end would offer.

---

## MFCC + Δ + ΔΔ

Alternative audio feature: `(120, 130)` — **measured**.

```python
mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=40, n_fft=2048, hop_length=512)
if use_delta:
    d1 = librosa.feature.delta(mfcc)              # first derivative
    d2 = librosa.feature.delta(mfcc, order=2)     # second derivative
    mfcc = np.vstack([mfcc, d1, d2])              # (120, 130)
if normalize:
    mfcc = (mfcc - mfcc.mean(1, keepdims=True)) / (mfcc.std(1, keepdims=True) + 1e-8)
```

MFCCs apply a discrete cosine transform to the log-mel spectrum, decorrelating the mel bands. The
first ~13 coefficients capture spectral envelope — vocal tract shape, which is what distinguishes
phonemes; 40 retains finer structure that correlates with voice quality and therefore with affect.

**Δ and ΔΔ** are the first and second temporal derivatives, computed by `librosa.feature.delta` using
a Savitzky–Golay filter. They encode *rate of change* rather than instantaneous value — how quickly
the spectrum is moving. Emotion is substantially carried in dynamics: an angry utterance and a neutral
one may share a spectral envelope while differing sharply in how abruptly it changes. Stacking them
triples the row count to 120.

**Per-coefficient normalisation** — `mean(1)` and `std(1)` reduce over time, giving each of the 120
rows its own statistics. This differs from the mel path's global normalisation, and deliberately:
low-order cepstral coefficients are orders of magnitude larger than high-order ones, and a global
statistic would leave the high-order rows effectively at zero.

> **`--feature mfcc` currently crashes the CNN models.** The extraction above is correct and tested;
> the feeding path omits the channel dimension. See [Known issues](#known-issues).

### Mel or MFCC?

| | Log-mel | MFCC + Δ + ΔΔ |
|---|---|---|
| Rows | 128 | 120 |
| Correlated dimensions | Yes — adjacent bands overlap | No — DCT decorrelates |
| Suits | 2-D CNNs (local structure is meaningful) | Dense/recurrent models, small data |
| Explicit dynamics | No — the model must learn them | Yes — Δ, ΔΔ supplied directly |
| Compactness | Lower | Higher |

Mel is the default because both CNN architectures treat the spectrogram as an image, where the local
2-D correlation MFCC removes is exactly what convolution exploits. MFCC is retained as a
lower-dimensional, more classical baseline — useful for comparison and for smaller models.

---

## Facial landmarks

`(75, 1404)` per clip — sequence length × flattened landmark coordinates.

```python
mp_face = mp.solutions.face_mesh
with mp_face.FaceMesh(static_image_mode=False, max_num_faces=1,
                      refine_landmarks=True, min_detection_confidence=0.5) as mesh:
    while cap.isOpened() and len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok: break
        frame = cv2.resize(frame, frame_size)
        result = mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if result.multi_face_landmarks:
            lm = result.multi_face_landmarks[0].landmark
            coords = np.array([[l.x, l.y, l.z] for l in lm], dtype=np.float32)
            coords -= coords.mean(0)                          # centre
            coords /= np.linalg.norm(coords, axis=1).max() + 1e-8   # scale
            frames.append(coords.flatten())
```

### Why landmarks rather than pixels

A landmark sequence is a ~1400-dimensional geometric description of the face; a video is millions of
pixels. Three advantages that matter here:

- **Sample efficiency.** MediaPipe has already solved face detection and landmark localisation on
  vastly more data than these corpora contain. Learning that from scratch on a few thousand clips is
  not realistic.
- **Invariance.** Lighting, skin tone, background, and camera characteristics are discarded. For a
  system intended to work across demographics and in uncontrolled rooms, that is a substantial
  robustness gain rather than a mere convenience.
- **Privacy.** Landmark coordinates are far less identifying than video frames. For clinical
  deployment that is a meaningful property — a landmark stream is much easier to justify to an ethics
  board than a video feed.

The cost is real: gaze, blushing, tears, and skin texture are all discarded. Whether that loses
clinically relevant signal is an open question this design does not answer.

### Per-frame normalisation

```python
coords -= coords.mean(0)                             # translation invariance
coords /= np.linalg.norm(coords, axis=1).max() + 1e-8   # scale invariance
```

Centroid subtraction removes head position within the frame; dividing by the maximum radius removes
apparent face size, which varies with distance from the camera. What survives is the *shape* of the
face — which is where expression lives. Without both steps the network could achieve low training loss
by tracking head movement, which correlates with emotion in acted data but will not generalise.

Applied **per frame**, so head motion across the sequence is also normalised away. That is a
deliberate trade: it discards gesture information (nodding, head shaking) in exchange for robustness.

MediaPipe's `z` coordinate is a relative depth estimate, roughly in the same units as `x` and `y`. It
is included; its reliability is much lower than the in-plane coordinates.

### Sequence handling

| Condition | Behaviour |
|---|---|
| More than 75 frames | Truncated to the first 75 — the loop stops reading |
| Fewer than 75 frames | Zero-padded at the end |
| No face detected in a frame | Frame skipped entirely, not zero-filled |
| No face in any frame | Returns `None`; `preprocess.py` writes no file |
| Video unreadable | Returns `None` |
| MediaPipe not installed | Returns `None` immediately (`_MEDIAPIPE` guard) |

At 25 fps, 75 frames is 3 seconds — matching the audio window. The correspondence is by configuration,
not enforced: a 30 fps video yields 2.5 seconds of visual context against 3 seconds of audio. There is
no explicit temporal alignment between the modalities beyond both being anchored to the same clip.

Frames with no detected face are **dropped rather than zero-filled**, which compresses the timeline —
75 frames may span more than 75 frames of wall-clock video. For a fixed-window classifier this matters
little; for anything doing temporal reasoning it would need addressing.

The optional import guard means the whole audio pipeline works without `mediapipe` or `opencv-python`
installed:

```python
try:
    import cv2, mediapipe as mp
    _MEDIAPIPE = True
except ImportError:
    _MEDIAPIPE = False
```

---

## Normalisation strategies

Three different schemes, each matched to its feature's structure:

| Feature | Scheme | Reduction axis | Rationale |
|---|---|---|---|
| Log-mel | Global mean/std | Both axes | Homogeneous time–frequency image; one statistic is appropriate |
| MFCC | Per-coefficient mean/std | Time only | Coefficients differ in scale by orders of magnitude |
| Landmarks | Centroid + max-radius, per frame | Per frame | Removes translation and scale; preserves shape |

All three add `1e-8` to the denominator. Not decoration — it is what keeps a constant input (digital
silence, a static face) from producing division by zero, and it is tested directly.

Note what is *not* done: no per-speaker normalisation (e.g. cepstral mean subtraction over a
speaker's whole recording set). Standard in speech recognition, and it would likely help here, but it
requires speaker-level statistics at inference time — unavailable when a stranger speaks into a
microphone for the first time. The current scheme is per-clip, which is what a live system can
actually compute.

---

## Storage and caching

[`preprocess.py`](../scripts/preprocess.py) writes one `.npy` per sample per feature type:

```
datasets/processed/
├── mel/<stem>.npy          (128, 130)   float32
├── mfcc/<stem>.npy         (120, 130)   float32
├── landmarks/<stem>.npy    (75, 1404)   float32
├── manifest.csv
├── errors_audio.txt        only if failures occurred
└── errors_visual.txt
```

Approximate sizes per sample: mel ~66 KB, mfcc ~62 KB, landmarks ~421 KB. A 9,000-sample audio-only
corpus is roughly 1.2 GB across both audio feature types.

**Idempotent** — existing files are skipped, so an interrupted run resumes:

```python
if (proc / "mel" / f"{stem}.npy").exists():
    continue
```

**Fault-tolerant** — per-file exceptions are collected and written to `errors_audio.txt` /
`errors_visual.txt`, and the run continues. On corpora of thousands of files, one corrupt header should
not cost the whole job.

**The cache is not config-aware.** This is the significant caveat: the skip check tests only for file
existence, not for whether the file was produced by the current settings. Changing `n_mels` and
re-running silently yields a mixed cache. Always `rm -rf datasets/processed/` after touching anything
under `audio:` or `visual:`. A config hash in the output path would fix this properly.

---

## Numerical robustness

The single most important property tested here: **silence must not produce NaNs**.

`power_to_db` computes `10 · log₁₀(S / ref)`. On an all-zero signal, `S = 0` and `ref = np.max(S) = 0`,
so the expression is `log₁₀(0/0)` — a classic `-inf` → NaN source. NaNs then propagate through the
network and silently destroy a training run.

This is not hypothetical. A live microphone stream contains silent windows constantly: before speech
starts, during pauses, after it ends. `AudioStreamBuffer` will hand those windows to the model.

Tested at three levels:

```python
def test_mel_spectrogram_no_nan_on_silence():
    silent = np.zeros(N, dtype=np.float32)
    mel = mel_spectrogram(silent, SR)
    assert not np.isnan(mel).any()

def test_mfcc_no_nan(sine_audio): ...
def test_extract_silence_no_nan(tmp_path, audio_cfg): ...
```

librosa's internal clamping plus the `1e-8` normalisation guard together keep the output finite.
`test_mel_spectrogram_normalized_mean_near_zero` additionally asserts the normalisation actually
produces zero mean and unit variance, rather than merely running without error.

---

## Known issues

### 1. MFCC tensors lack a channel dimension — confirmed

[`EmotionDataset._load_audio`](../src/datasets.py#L169) adds the channel axis only for mel:

```python
if self.feature == "mel":
    t = t.unsqueeze(0)
```

MFCC tensors therefore reach the model as `(B, 120, 130)`, and `Conv2d` interprets the batch dimension
as channels:

```
RuntimeError: Given groups=1, weight of size [32, 1, 3, 3],
expected input[1, 4, 120, 130] to have 1 channels, but got 4 channels instead
```

Verified by direct execution against both `audio_cnn` and `audio_cnn_lstm`.
[`InferenceEngine._to_tensor`](../backend/inference.py#L73) has the same defect on the serving side —
it applies a single `unsqueeze(0)` where the mel branch applies two.

**Fix:** unsqueeze unconditionally in `_load_audio`, and use `.unsqueeze(0).unsqueeze(0)` for the MFCC
branch in `_to_tensor`. Add a test that runs a full forward pass with `feature="mfcc"` — the current
tests exercise extraction but never feed the result to a model, which is precisely the gap.

**Workaround:** use `--feature mel`.

### 2. Landmark dimensionality is probably 1434, not 1404 — needs verification

`FaceMesh(refine_landmarks=True)` adds 10 iris landmarks to the base 468, giving **478 landmarks →
1434 values**. But three places assume 1404:

| Location | Assumption |
|---|---|
| [`builder.py`](../src/models/builder.py#L33) | `VisualLSTM(1404, …)` |
| [`datasets.py`](../src/datasets.py#L178) | `torch.zeros(75, 1404)` |
| [`inference.py`](../backend/inference.py#L81) | `torch.zeros(1, max_frames, 1404)` |

If MediaPipe behaves as documented, real landmark files will be `(75, 1434)` and will not load into a
model expecting 1404. The test suite cannot catch it — it feeds synthetic `zeros(75, 1404)`.

`mediapipe` is not installed in the environment where this was written, so this is reasoned from the
library's documented behaviour rather than observed. **Verify first:**

```python
import mediapipe as mp, numpy as np, cv2
with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True) as m:
    r = m.process(cv2.cvtColor(cv2.imread("face.jpg"), cv2.COLOR_BGR2RGB))
    print(len(r.multi_face_landmarks[0].landmark))   # 468 or 478?
```

**Fix:** either set `refine_landmarks=False` (keeps 1404 and drops iris tracking, which contributes
little to expression) or set the dimension to 1434 everywhere. Either way, define it once as a module
constant instead of hard-coding it in three files.

### 3. Landmark `normalize` config key is ignored

`visual.normalize` is read into `vis_cfg` but never consulted —
`extract_visual_features` always normalises. Harmless (normalisation is always what you want here) but
misleading. Either honour the flag or remove it.

### 4. Pad/crop logic is duplicated

[`load_audio`](../src/features.py#L17) and
[`InferenceEngine._pad_or_crop`](../backend/inference.py#L56) implement identical logic separately —
one takes a path, the other an array. They agree today; nothing enforces that they continue to. Extract
a shared `pad_or_crop(audio, n)` helper and have both call it.
