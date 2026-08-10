# Evaluation

[`scripts/evaluate.py`](../scripts/evaluate.py) — test-set metrics, confusion matrices, and latency
benchmarking.

- [Usage](#usage)
- [What it does](#what-it-does)
- [Metrics](#metrics)
- [Reading a confusion matrix](#reading-a-confusion-matrix)
- [Latency benchmarking](#latency-benchmarking)
- [Results format](#results-format)
- [Comparing architectures](#comparing-architectures)
- [What is not measured](#what-is-not-measured)

---

## Usage

```bash
python3 scripts/evaluate.py --checkpoint models/audio_cnn_lstm_best.pt
python3 scripts/evaluate.py --checkpoint models/attention_best.pt --latency_runs 200
```

| Flag | Default | Purpose |
|---|---|---|
| `--checkpoint` | *required* | Path to a `.pt` produced by `train.py` |
| `--config` | `config/settings.yaml` | Used for data paths and the latency dummy shapes |
| `--latency_runs` | 100 | Timed iterations after warm-up |

Requires `datasets/processed/test_split.csv`, written by `train.py` at the end of training.

Expected output shape (numbers illustrative — no run has been performed on real data):

```
Model: audio_cnn_lstm | Parameters: 6,458,982 | Device: cuda
Evaluating: 100%|██████████| 41/41

Accuracy:      0.6142
Weighted F1:   0.6087
Macro F1:      0.5734

              precision    recall  f1-score   support
     neutral       0.68      0.74      0.71       312
       happy       0.61      0.58      0.59       241
         sad       0.59      0.62      0.60       238
       angry       0.71      0.69      0.70       244
     fearful       0.52      0.47      0.49       132
     disgust       0.48      0.44      0.46       122
    accuracy                           0.61      1289

Confusion matrix: results/audio_cnn_lstm_confusion.png

Latency benchmark (200 runs)...
Mean: 4.31 ms | p50: 4.12 ms | p95: 5.87 ms | p99: 7.02 ms
Results: results/audio_cnn_lstm_results.json
```

---

## What it does

1. **Load the checkpoint** and read `model_name`, `cfg`, and `feature` from it.
2. **Rebuild the architecture** from the checkpoint's embedded config, not the config on disk:
   ```python
   model = build_model(model_name, ckpt.get("cfg", cfg), len(UNIFIED))
   model.load_state_dict(ckpt["model"])
   model.eval()
   ```
3. **Load the pinned test split** from `datasets/processed/test_split.csv`.
4. **Select modality** from the model name, exactly as `train.py` does.
5. **Predict** over the test set with `no_grad`.
6. **Compute** accuracy, weighted F1, macro F1, and a per-class report.
7. **Render** a confusion-matrix heatmap to `results/<model>_confusion.png`.
8. **Benchmark latency** on synthetic tensors with warm-up and CUDA synchronisation.
9. **Write** everything machine-readable to `results/<model>_results.json`.

Step 2 is why old checkpoints remain evaluable after `settings.yaml` changes — architecture always comes
from the checkpoint. The `--config` file is still used, but only for data paths and the latency dummy
shapes.

Step 3 uses the split file rather than recomputing the split, so evaluation cannot drift from training
even if `seed` or the split fractions are edited afterwards.

---

## Metrics

Three headline numbers, and they answer different questions.

### Accuracy

```python
acc = accuracy_score(labels, preds)
```

Fraction of correct predictions. Intuitive, and the wrong primary metric for this problem: with
imbalanced classes it rewards being right about the majority. A model that always predicts `neutral` on
a manifest where `neutral` is 30% of samples scores 0.30 — nearly double the 0.167 chance level — while
being completely useless.

### Weighted F1

```python
f1_w = f1_score(labels, preds, average="weighted")
```

Per-class F1, averaged with weights proportional to class support. Closer to accuracy in spirit but
accounts for the precision/recall trade-off within each class. Usually tracks accuracy fairly closely.

### Macro F1 — the one to report

```python
f1_m = f1_score(labels, preds, average="macro")
```

Per-class F1, **unweighted** average. Every class counts equally regardless of how many samples it has,
so a model that ignores `fearful` and `disgust` — the two smallest classes, present in only two of the
three corpora — is penalised in proportion to how much those classes matter conceptually, not
statistically.

**This is the metric that matches the application.** For a clinical screening use case, missing a
fearful or distressed patient is the failure mode that matters; being reliably right about `neutral`
does not compensate for it. A large gap between weighted and macro F1 is the diagnostic signal that the
model is coasting on the majority classes.

### Per-class report

```python
classification_report(labels, preds, target_names=UNIFIED)
```

Precision, recall, F1, and support for each of the six classes. This is where the actual diagnosis
happens — the headline numbers tell you *whether* something is wrong, this tells you *where*.

| Pattern | Reading |
|---|---|
| High precision, low recall on class X | The model is conservative about X — when it says X it is right, but it misses many |
| Low precision, high recall on X | The model over-predicts X; it is becoming a dumping ground for uncertainty |
| Both low on X | X is not being learned. Check support — it may simply be too rare |
| Support far from expectations | The speaker split gave the test set an unrepresentative class mix |

That last row is worth checking first. With a speaker-level split and no class stratification, a test
set drawn from a handful of speakers can badly under-represent a class — see
[datasets.md](datasets.md#properties).

---

## Reading a confusion matrix

```python
cm = confusion_matrix(labels, preds)
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=UNIFIED, yticklabels=UNIFIED)
```

Rows are true labels, columns are predictions; the diagonal is correct. Written to
`results/<model>_confusion.png` at 150 dpi with the test-set size in the title.

Counts are raw, not row-normalised, so with imbalanced support the visual weight of a cell reflects
class size as much as error rate. When comparing across classes, normalise mentally by the row's support
— or divide `cm` by `cm.sum(axis=1, keepdims=True)` if you want to inspect it interactively.

Confusions to expect in this taxonomy, and what each would tell you:

| Confusion | Interpretation |
|---|---|
| `neutral` ↔ `sad` | Both are low-arousal. The classic SER confusion, and worsened here because `neutral` absorbs RAVDESS `calm` |
| `angry` ↔ `happy` | Both high-arousal with raised pitch and volume. The model has learned arousal but not valence — a very common and diagnostic failure |
| `fearful` → `sad` | Fear is under-represented and shares low-valence acoustics with sadness |
| `disgust` → anything | Smallest class, weakest acoustic signature. Often the worst-performing class in six-class SER |
| Everything → `neutral` | The model has collapsed to the majority class. Check that the class weights were actually applied |

The `angry`/`happy` pattern is the most informative single thing to look for. Arousal (activation) is
acoustically salient — loudness, pitch range, speech rate — while valence (pleasantness) is much subtler
in the audio channel and is where the visual modality is theorised to help most. If a fusion model
reduces `angry`/`happy` confusion relative to its audio-only baseline, that is direct evidence the
visual stream is contributing something the audio cannot supply. If it does not, the multimodal
hypothesis is not being borne out — which is a result worth reporting.

---

## Latency benchmarking

```python
dummy_a = torch.randn(1, 1, n_mels, 130).to(device)
dummy_v = torch.zeros(1, cfg["visual"]["max_frames"], LANDMARK_DIM).to(device)

model.eval()
with torch.no_grad():
    for _ in range(10):       # warm-up
        infer()
    for _ in range(n_runs):
        if device.type == "cuda": torch.cuda.synchronize()
        t0 = time.perf_counter()
        infer()
        if device.type == "cuda": torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000)
```

Three details make this a real measurement rather than a plausible-looking one:

**Warm-up (10 iterations).** The first forward pass on CUDA includes context initialisation, kernel
compilation, cuDNN algorithm selection, and memory-pool allocation — often 10–100× the steady-state
cost. On CPU the first pass warms caches and triggers lazy MKL initialisation. Without warm-up the mean
is dominated by one-off setup.

**`torch.cuda.synchronize()` on both sides.** CUDA kernel launches are asynchronous: without
synchronisation, `perf_counter()` measures the time to *queue* the work, not to complete it, and you
get impressively fast numbers that mean nothing. Synchronising before starts the clock from a quiet
GPU; synchronising after waits for actual completion.

**Percentiles, not just the mean.** p95 and p99 are what a real-time system lives or dies by. A mean of
4 ms with a p99 of 40 ms means one prediction in a hundred arrives ten times late — invisible in the
mean, very visible to a user watching a live display.

`batch_size=1` is deliberate: it is the serving condition. Throughput numbers from a large batch are
irrelevant to a system classifying one window at a time.

### What this number is and is not

It measures **the model forward pass only**. Not included: audio decoding, resampling, mel or MFCC
extraction, tensor construction, host↔device transfer, HTTP or WebSocket overhead, JSON serialisation.

Feature extraction is typically the larger cost. `librosa.feature.melspectrogram` on a 3-second clip is
commonly in the tens of milliseconds on CPU — potentially several times the model forward pass itself.
So this benchmark is the right number for **comparing architectures** and the wrong number for
**predicting end-to-end responsiveness**.

For the end-to-end figure, use the `latency_ms` field in an API prediction response
([`inference.py`](../backend/inference.py#L102)), which covers pad/crop + feature extraction + forward +
softmax:

```python
t0 = time.perf_counter()
audio = self._pad_or_crop(...)
tensor = self._to_tensor(audio)      # ← feature extraction included
...
latency = (time.perf_counter() - t0) * 1000
```

That is the number displayed in the front-end UI, and the one to quote when discussing real-time
feasibility.

The dummy shapes are derived rather than literal: `feature_height(cfg, feature)` and `n_frames(cfg)`
for audio, `LANDMARK_DIM` for visual. They previously hard-coded `n_mels`, 130 frames, and 1404, and
were built from the `--config` file while the model came from the checkpoint's config — so an mfcc
checkpoint got a mel-shaped dummy. Both now read the checkpoint's config.

---

## Results format

`results/<model_name>_results.json`:

```json
{
  "model":           "audio_cnn_lstm",
  "n_params":        6458982,
  "n_test":          1289,
  "accuracy":        0.6142,
  "f1_weighted":     0.6087,
  "f1_macro":        0.5734,
  "latency_mean_ms": 4.312,
  "latency_p50_ms":  4.118,
  "latency_p95_ms":  5.874,
  "latency_p99_ms":  7.021,
  "device":          "cuda"
}
```

One file per architecture, so a comparison table is a directory read. `results/` is gitignored.

Note the JSON does **not** include the per-class report or the confusion matrix — only the PNG and the
stdout carry those. If you want per-class numbers in machine-readable form, add
`classification_report(..., output_dict=True)` to the results dict.

---

## Comparing architectures

Train each model under identical conditions, then evaluate each:

```bash
for m in audio_cnn audio_cnn_lstm visual_lstm feature_level decision_level attention; do
  python3 scripts/train.py    --model "$m" --feature mel
  python3 scripts/evaluate.py --checkpoint "models/${m}_best.pt" --latency_runs 200
done
```

Collect the results:

```python
import json, glob, pandas as pd
rows = [json.load(open(p)) for p in sorted(glob.glob("results/*_results.json"))]
df = pd.DataFrame(rows)[["model", "n_params", "accuracy", "f1_macro", "latency_p95_ms"]]
print(df.sort_values("f1_macro", ascending=False).to_string(index=False))
```

The comparison is valid because the seed fixes the speaker split, so every architecture sees exactly the
same train/val/test partition. That is the property that makes these numbers comparable at all.

Questions the table should be read against:

- **Does `audio_cnn_lstm` beat `audio_cnn`?** If not, temporal modelling is not earning its 4.5× parameter cost.
- **Does any fusion model beat the best unimodal one?** This is the project's central question. If not, the multimodal hypothesis is not supported on this data — a legitimate and publishable finding.
- **What did `decision_level` learn?** Load the checkpoint and inspect `softmax(model.weights)`. If `w₁ ≈ 0`, the visual stream contributed nothing — likely because the manifest was full of zero-filled visual inputs.
- **Does macro F1 rank differently from accuracy?** If so, some models are trading minority-class performance for majority-class performance, and accuracy is hiding it.
- **Is p95 latency within budget?** A fusion model that wins on F1 but costs 3× the latency may still lose on deployability.

Inspecting the decision weights:

```python
import torch
from src.models.builder import build_model
from src.datasets import UNIFIED
ckpt = torch.load("models/decision_level_best.pt", map_location="cpu", weights_only=False)
m = build_model("decision_level", ckpt["cfg"], len(UNIFIED))
m.load_state_dict(ckpt["model"])
print(torch.softmax(m.weights, dim=0))   # [audio_weight, visual_weight]
```

---

## What is not measured

Gaps worth knowing about before quoting any number from this script.

**Confidence calibration.** The reported `confidence` is a raw softmax output. Neural networks are
typically overconfident, so 0.9 does not mean 90% correct. For a system meant to inform a clinician,
calibration matters more than accuracy — an uncalibrated confidence score is worse than none, because it
invites misplaced trust. Expected Calibration Error and a reliability diagram should be added; temperature
scaling on the validation set is the standard remedy.

**Per-corpus breakdown.** The `dataset` column exists in the manifest but evaluation ignores it. Pooled
metrics cannot distinguish "generalises across corpora" from "does well on the easy corpus that happens
to dominate the test set". Grouping the report by `dataset` would answer whether cross-corpus training
helps or merely averages.

**Cross-corpus transfer.** Train on RAVDESS + CREMA-D, test on MSP-IMPROV — the harder and more
informative protocol for a generalisation claim. Currently all corpora are pooled before splitting.

**Statistical significance.** Single-run point estimates with no confidence intervals. With a test set of
a few hundred speaker-disjoint samples, a 2-point accuracy difference between architectures is well within
noise. Multiple seeds with mean ± std, or bootstrap CIs over the test set, would be needed before claiming
one architecture beats another.

**Streaming behaviour.** Evaluation scores isolated 3-second windows. The live system produces
overlapping predictions every 0.5 s, whose stability — how often the label flips between adjacent windows
— is a distinct property that offline evaluation cannot see. Temporal smoothing is on the
[roadmap](../README.md#roadmap) partly for this reason.

**Noise and channel robustness.** No evaluation under additive noise, reverberation, or codec
degradation. For a system intended for real rooms, this is the most consequential omission — studio-clean
test performance is a weak predictor of ward performance.

**Fairness across demographics.** CREMA-D provides speaker demographics; nothing in the pipeline uses
them. Per-group error rates are a basic requirement for a clinical system and are not currently computed.

**Fusion models as actually served.** A fusion model is evaluated with real landmark inputs but *served*
with a zero visual tensor ([`_zero_visual`](../backend/inference.py#L79)). Its reported accuracy therefore
does not describe its deployed accuracy. Evaluating a fusion model with the visual input zeroed would give
the honest served number — and the gap between the two is itself the measure of how much the visual stream
contributes.
