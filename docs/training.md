# Training

[`scripts/train.py`](../scripts/train.py) — the training loop, its hyperparameters, and the checkpoint
format.

- [Usage](#usage)
- [What happens, in order](#what-happens-in-order)
- [The training loop](#the-training-loop)
- [Class-weighted loss](#class-weighted-loss)
- [Optimisation](#optimisation)
- [Mixed precision](#mixed-precision)
- [Model selection and early stopping](#model-selection-and-early-stopping)
- [Checkpoint format](#checkpoint-format)
- [Monitoring](#monitoring)
- [Reproducibility](#reproducibility)
- [Troubleshooting](#troubleshooting)

---

## Usage

```bash
python3 scripts/train.py --model audio_cnn_lstm --feature mel
```

| Flag | Default | Choices |
|---|---|---|
| `--model` | `audio_cnn_lstm` | `audio_cnn`, `audio_cnn_lstm`, `visual_lstm`, `feature_level`, `decision_level`, `attention` |
| `--feature` | `mel` | `mel`, `mfcc` |
| `--config` | `config/settings.yaml` | any YAML path |

> **Use `--feature mel`.** `--feature mfcc` currently raises a `RuntimeError` on the CNN models — see
> [known issue #1](../README.md#1---feature-mfcc-crashes-the-cnn-models--confirmed).

Prerequisite: `python3 scripts/preprocess.py` must have produced
`datasets/processed/manifest.csv` and the corresponding `.npy` files.

Expected output:

```
Device: cuda | Model: audio_cnn_lstm | Feature: mel
Split: 6021 train / 1284 val / 1289 test (speaker-independent)
Parameters: 6,458,982
Epoch   1 | train loss 1.7284 acc 0.241 | val loss 1.6903 acc 0.268
  [saved] val_acc=0.268
Epoch   2 | train loss 1.6120 acc 0.312 | val loss 1.5847 acc 0.334
  [saved] val_acc=0.334
...
Early stopping at epoch 47

Best val accuracy: 0.6142 | Checkpoint: models/audio_cnn_lstm_best.pt
```

Split sizes and accuracies above are illustrative — no training run has been performed on real data.

---

## What happens, in order

1. **Load config** and seed `torch` and `numpy` from `training.seed`.
2. **Select device** — `cuda` if available, else `cpu`.
3. **Read the manifest** `datasets/processed/manifest.csv`.
4. **Split by speaker** via [`speaker_independent_split`](../src/datasets.py#L124) using
   `val_split`, `test_split`, and `seed`.
5. **Determine modality** from the model name:
   ```python
   modality = "multimodal" if multi else ("visual" if args.model == "visual_lstm" else "audio")
   ```
6. **Build DataLoaders** over `EmotionDataset`, shuffling train only.
7. **Construct the model** with `build_model` and print its parameter count.
8. **Compute class weights** from the training split and build a weighted `CrossEntropyLoss`.
9. **Set up** AdamW, `CosineAnnealingLR`, and a `GradScaler` if AMP is enabled on CUDA.
10. **Open a TensorBoard writer** at `runs/<model_name>/`.
11. **Loop** over epochs: train, validate, step the scheduler, log, checkpoint or increment patience.
12. **On completion** reload the best checkpoint, print its validation accuracy, and write
    `datasets/processed/test_split.csv` for evaluation.

Step 12 is what guarantees that `evaluate.py` scores exactly the speakers this run held out, even if
the seed or split fractions change afterwards.

---

## The training loop

One function handles both training and validation, distinguished by a boolean —
[`run_epoch`](../scripts/train.py#L46):

```python
def run_epoch(model, loader, criterion, optimizer, scaler, device, train, multimodal):
    model.train(train)                        # sets train/eval mode from the flag
    total_loss = correct = total = 0

    for batch in loader:
        if multimodal:
            xa, xv, y = batch[0].to(device), batch[1].to(device), batch[2].to(device)
        else:
            xa, y = batch[0].to(device), batch[1].to(device)
            xv = None

        amp_ctx = torch.autocast("cuda") if scaler else nullcontext()
        with torch.set_grad_enabled(train), amp_ctx:
            logits = model(xa, xv) if multimodal else model(xa)
            loss = criterion(logits, y)

        if train:
            optimizer.zero_grad()
            if scaler:
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

        bs = y.size(0)
        total_loss += loss.item() * bs
        correct += (logits.argmax(1) == y).sum().item()
        total += bs

    return total_loss / total, correct / total
```

Details that matter:

- **`model.train(train)`** sets train or eval mode from the same flag, so dropout and BatchNorm
  statistics behave correctly in both passes without a separate code path.
- **`torch.set_grad_enabled(train)`** disables the autograd graph during validation, cutting memory and
  time. Equivalent to wrapping in `no_grad()` but expressible as one flag.
- **`nullcontext()`** stands in for `autocast` when AMP is off, so there is a single `with` statement
  rather than duplicated branches.
- **Loss is weighted by batch size** (`loss.item() * bs`) and divided by the true total, so a final
  partial batch does not skew the epoch average. Common bug avoided.
- **The unified batch unpacking** is what lets the same loop serve unimodal and fusion models — the
  arity difference comes from `EmotionDataset`'s modality dispatch and is absorbed here.

---

## Class-weighted loss

```python
labels = train_df["label"].map(LABEL2IDX).values
weights = compute_class_weight("balanced", classes=np.arange(num_classes), y=labels)
criterion = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32).to(device))
```

scikit-learn's `"balanced"` mode computes `n_samples / (n_classes × n_samples_for_class)`, so rare
classes receive proportionally larger weights.

**Why this is necessary here.** Merging three corpora produces substantial imbalance. `neutral` absorbs
RAVDESS's `calm` in addition to its own neutral samples; `fearful` and `disgust` come only from RAVDESS
and CREMA-D, so adding MSP-IMPROV dilutes them relative to the other four. Unweighted, the model can
minimise loss by favouring the majority classes and still look respectable on accuracy — while being
useless on exactly the classes a distress-detection application cares about.

**Why weighting rather than resampling.** Over-sampling minority classes repeats the same clips
multiple times per epoch, and on corpora of a few thousand samples that invites memorisation.
Under-sampling discards data these corpora cannot spare. Weighting sees every sample exactly once per
epoch and only changes its contribution to the gradient.

Weights are computed from the **training split only** — computing them over the full manifest would
leak validation and test class distributions into training.

---

## Optimisation

| Component | Setting | Rationale |
|---|---|---|
| Optimiser | `AdamW(lr=1e-4, weight_decay=1e-4)` | Decoupled weight decay applies regularisation correctly under adaptive learning rates, unlike Adam's L2-in-gradient formulation |
| Scheduler | `CosineAnnealingLR(T_max=epochs)` | Smooth decay from `lr` to ~0 with no step-size or milestone tuning |
| Gradient clipping | max-norm 1.0 | LSTM training is prone to gradient spikes; clipping bounds the update without changing its direction |
| Batch size | 32 | Fits ~8 GB for the fusion models |

`lr=1e-4` is conservative for AdamW (whose typical range is 1e-4 to 1e-3), chosen because the corpora
are small and the models moderately sized — a higher rate risks overfitting before the scheduler has
decayed.

**`T_max=epochs` couples the schedule to the epoch cap.** Change `epochs` from 100 to 50 and you do not
just halve the budget — you halve the annealing period, so the learning rate decays twice as fast. Not
a bug, but a coupling worth remembering when comparing runs with different `epochs`.

Because early stopping usually fires well before epoch 100, most runs only traverse the first portion of
the cosine curve, where the rate is still relatively high. If you want the full anneal to actually
happen, set `epochs` closer to the epoch count you expect to reach.

`weight_decay=1e-4` applies to **all** parameters, including BatchNorm weights and biases. Common
practice is to exclude those; the effect here is small but it is a deviation from best practice.

---

## Mixed precision

```python
scaler = torch.cuda.amp.GradScaler() if tc["amp"] and device.type == "cuda" else None
```

Gated on both the config flag and actual CUDA availability, so `amp: true` is harmless on a CPU
machine.

The ordering inside the AMP branch is the part that is easy to get wrong:

```python
scaler.scale(loss).backward()      # 1. scale loss up, backprop
scaler.unscale_(optimizer)         # 2. unscale gradients BEFORE clipping
nn.utils.clip_grad_norm_(model.parameters(), 1.0)
scaler.step(optimizer)             # 3. step (skipped if inf/nan detected)
scaler.update()                    # 4. adjust the scale factor
```

Step 2 is essential. Gradient clipping compares a norm against a threshold; if the gradients are still
scaled by the loss scaler's factor (often 2¹⁶), the norm is inflated by that factor and **every** batch
appears to exceed the clip threshold, so every update gets scaled down by an arbitrary amount. The
result is a model that trains far more slowly for no visible reason. `unscale_` restores true gradient
magnitudes first, so the clip threshold means what it says.

FP16 forward and backward passes roughly double throughput on tensor-core GPUs and halve activation
memory.

> `torch.cuda.amp.GradScaler()` is the deprecated spelling on recent PyTorch and emits a warning. The
> modern form is `torch.amp.GradScaler("cuda")`. Functionally identical.

---

## Model selection and early stopping

```python
if vl_loss < best_val_loss:
    best_val_loss = vl_loss
    patience_ctr = 0
    torch.save({...}, ckpt_path)
    print(f"  [saved] val_acc={vl_acc:.3f}")
else:
    patience_ctr += 1
    if patience_ctr >= tc["early_stopping_patience"]:
        print(f"Early stopping at epoch {epoch}")
        break
```

**Selection is on validation loss, not validation accuracy.** With a speaker-disjoint validation set of
a few hundred samples, accuracy is a step function — it changes only when a prediction flips class, so
its argmax over epochs is largely noise, and many epochs tie. Cross-entropy is continuous: it
distinguishes a confident correct prediction from a marginal one, and it discriminates between two
models with identical accuracy. It is also the quantity being optimised, so selecting on it is
internally consistent.

Note that the printed `val_acc` is from the same epoch as the saved checkpoint, so the final "Best val
accuracy" line reports the accuracy *at the best-loss epoch* — which is not necessarily the highest
accuracy the run ever reached. That is intentional.

Patience 15 is generous, which suits small noisy validation sets where loss can plateau for several
epochs before improving again. Only the best checkpoint is retained — each improvement overwrites
`models/<model_name>_best.pt`. No per-epoch checkpoints, no `last.pt`; an interrupted run resumes from
scratch.

---

## Checkpoint format

```python
torch.save({
    "epoch":      epoch,
    "model":      model.state_dict(),
    "val_loss":   vl_loss,
    "val_acc":    vl_acc,
    "model_name": args.model,     # e.g. "audio_cnn_lstm"
    "feature":    args.feature,   # "mel" | "mfcc"
    "cfg":        cfg,            # the FULL settings.yaml as a dict
}, ckpt_path)
```

Written to `models/<model_name>_best.pt`.

**Embedding the entire config is the key design decision.** It makes checkpoints
self-describing, and both `evaluate.py` and `InferenceEngine` rebuild the architecture from
`ckpt["cfg"]` rather than from the config on disk:

```python
model = build_model(ckpt["model_name"], ckpt["cfg"], len(UNIFIED))
model.load_state_dict(ckpt["model"])
```

Without it, editing `lstm_hidden` in `settings.yaml` would break every previously trained checkpoint
with a shape-mismatch error at load time — and the error would point at the state dict rather than at
the config change that caused it. A few kilobytes buys immunity to that entire class of problem.

`"feature"` is stored because the serving path must extract the same feature type the model was trained
on. `InferenceEngine` reads it and branches accordingly
([`inference.py`](../backend/inference.py#L39)).

Inspecting a checkpoint:

```python
import torch
ckpt = torch.load("models/audio_cnn_lstm_best.pt", map_location="cpu", weights_only=False)
print(ckpt["model_name"], ckpt["feature"], ckpt["epoch"], ckpt["val_acc"])
print(ckpt["cfg"]["model"]["audio_cnn_lstm"])
```

`weights_only=False` is required — the checkpoint contains a config dict, not only tensors. This is
also why `InferenceEngine` passes that flag explicitly. Only load checkpoints you trust; the flag
permits arbitrary unpickling.

---

## Monitoring

```python
writer.add_scalars("loss", {"train": tr_loss, "val": vl_loss}, epoch)
writer.add_scalars("acc",  {"train": tr_acc,  "val": vl_acc},  epoch)
```

```bash
tensorboard --logdir runs/
```

`add_scalars` (plural) puts train and validation curves on the same axes, which is what makes the
train/validation gap directly readable — the primary thing to watch on corpora this size.

Comparing architectures is a matter of pointing TensorBoard at the parent directory; each run writes to
`runs/<model_name>/`.

What to look for:

| Pattern | Reading |
|---|---|
| Train loss falls, validation loss rises | Overfitting. Raise `dropout` or `weight_decay`, or lower `epochs` |
| Both plateau high | Underfitting. More capacity, higher LR, or more data |
| Validation loss oscillates wildly | LR too high, or the validation set is too small to be stable |
| Accuracy stuck near 1/6 ≈ 0.167 | Chance level — the model is not learning at all. Check labels, check for NaNs |
| Validation accuracy ≫ train accuracy | Suspicious. Usually a split bug or a dropout artefact |

Only scalars are logged. No histograms, no confusion matrices during training, no learning-rate curve,
no sample audio. The learning rate in particular is worth adding — it makes the cosine schedule's
interaction with early stopping visible.

---

## Reproducibility

```python
torch.manual_seed(tc["seed"])
np.random.seed(tc["seed"])
```

plus the split's own `np.random.default_rng(seed)`.

| Element | Deterministic? |
|---|---|
| Speaker split | **Yes** — same seed, same partition. Asserted by `test_split_is_reproducible` |
| Weight initialisation | Yes |
| Dropout masks | Yes on CPU; effectively yes on GPU for a fixed configuration |
| DataLoader shuffle order | Yes for the main process; worker seeding is not explicitly controlled |
| cuDNN kernel selection | **No** — `torch.backends.cudnn.deterministic` is not set |
| Reduction order on GPU | **No** — floating-point non-associativity means small run-to-run differences |

So two runs with the same seed on the same GPU will be very close but not bit-identical. For strict
determinism you would need:

```python
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
torch.use_deterministic_algorithms(True)
```

at a meaningful throughput cost. For comparing architectures, the current level is adequate — the split
is identical, which is what matters most, since split variance dominates run-to-run variance on corpora
this size.

Note that `random.seed()` (Python's stdlib module) is not seeded. Nothing in the pipeline currently uses
it, but a future augmentation implementation might.

---

## Troubleshooting

### `FileNotFoundError: datasets/processed/manifest.csv`

Run `python3 scripts/preprocess.py` first.

### `RuntimeError: Given groups=1, weight of size [32, 1, 3, 3], expected input[...] to have 1 channels`

`--feature mfcc`. Known bug; use `--feature mel`.

### `CUDA out of memory`

Halve `training.batch_size`. Fusion models need roughly twice what unimodal ones do. Consider lowering
the LR slightly to compensate for the noisier gradient at smaller batch size.

### Accuracy stuck at ~0.167

Chance level for six classes. Check that labels are non-constant
(`df["label"].value_counts()`), that the features are not all NaN or all zero, and that the learning
rate is not so high that the model diverged in the first epoch.

### Validation loss immediately rising

The model is overfitting from epoch 1, usually because the training split is very small. Check the
printed split sizes — if MSP-IMPROV collapsed into a single speaker
([known issue](datasets.md#known-issues)) and that speaker went to train, the effective split may be far
from 70/15/15.

### Training extremely slow on GPU

Check that `nvidia-smi` shows utilisation. If the GPU is idle between batches, the DataLoader is the
bottleneck — raise `num_workers`. If `pin_memory: true` and workers are already high, the `.npy` files
may be on slow storage.

### `RuntimeError: DataLoader worker (pid …) is killed by signal`

Usually out of shared memory with several workers. Lower `num_workers`, or set it to 0 while debugging
— it also produces far more readable tracebacks.
