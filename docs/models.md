# Model architectures

Six architectures — three unimodal, three fusion strategies — all reachable by name through
[`build_model`](../src/models/builder.py#L36). Parameter counts and tensor shapes below are
**measured** from the default [`config/settings.yaml`](../config/settings.yaml) with `num_classes=6`.

- [Overview](#overview)
- [The backbone contract](#the-backbone-contract)
- [AudioCNN](#audiocnn)
- [AudioCNNLSTM](#audiocnnlstm)
- [VisualLSTM](#visuallstm)
- [Attention pooling](#attention-pooling)
- [Fusion strategies](#fusion-strategies)
- [The builder](#the-builder)
- [Adding an architecture](#adding-an-architecture)

---

## Overview

| `--model` | Type | Params | Input(s) | Embed dim |
|---|---|---:|---|---|
| `audio_cnn` | unimodal audio | 1,438,694 | `(B,1,128,130)` | 4096 |
| `audio_cnn_lstm` | unimodal audio | 6,458,982 | `(B,1,128,130)` | 512 |
| `visual_lstm` | unimodal visual | 3,055,750 | `(B,75,LANDMARK_DIM)` | 512 |
| `feature_level` | fusion | 10,042,610 | both | — |
| `decision_level` | fusion | 9,514,734 | both | — |
| `attention` | fusion | 11,881,970 | both | — |

Shared design choices across all six:

- **BatchNorm before ReLU** in every conv block, with `bias=False` on the convolution — the BatchNorm
  β parameter makes the conv bias redundant.
- **Dropout only in heads and between LSTM layers.** Never on the final feature representation, which
  fusion modules consume.
- **Attention pooling instead of last hidden state** in both recurrent models — zero extra parameters.
- **Every backbone exposes `embed()` and `_embed_dim`**, which is what makes fusion composable.

---

## The backbone contract

Every unimodal model implements the same three-part interface:

```python
class Backbone(nn.Module):
    _embed_dim: int                              # set in __init__

    def embed(self, x) -> Tensor:  ...           # (B, _embed_dim)
    def forward(self, x) -> Tensor:              # (B, num_classes)
        return self.head(self.embed(x))
```

The split matters because fusion needs both halves independently:

| Fusion strategy | Uses |
|---|---|
| `feature_level` | `embed()` on both, then its own head |
| `attention` | `embed()` on both, cross-attention, then its own head |
| `decision_level` | `forward()` on both — it fuses *logits*, not features |

And `_embed_dim` lets fusion modules size their layers without knowing which backbone they hold:

```python
nn.Linear(audio_model._embed_dim + visual_model._embed_dim, hidden)
```

The leading underscore signals "internal, but read by fusion" — not truly private. Any new backbone
honouring this contract is immediately usable as a fusion component with no changes to `fusion.py`.

`test_audio_visual_embed_dims_match` asserts that `AudioCNNLSTM` and `VisualLSTM` agree at 512, which
is the precondition for cross-attention skipping its projection.

---

## AudioCNN

Lightweight 2-D CNN over the mel spectrogram — the simplest baseline.
[`src/models/audio.py`](../src/models/audio.py#L20)

```
Input (B, 1, 128, 130)
  │
  ├─ ConvBlock(1→32)                      (B,  32, 128, 130)
  ├─ ConvBlock(32→64) → MaxPool → Drop2d  (B,  64,  64,  65)
  ├─ ConvBlock(64→128) → MaxPool → Drop2d (B, 128,  32,  32)
  ├─ ConvBlock(128→256) → MaxPool → Drop2d(B, 256,  16,  16)   ← measured
  │
  ├─ AdaptiveAvgPool2d((4,4))             (B, 256,   4,   4)
  ├─ Flatten                              (B, 4096)             ← _embed_dim
  ├─ Linear(4096→256) → ReLU → Dropout    (B, 256)
  └─ Linear(256→6)                        (B, 6)
```

`_ConvBlock` is `Conv2d(3×3, padding=1, bias=False) → BatchNorm2d → ReLU`. Padding preserves spatial
dimensions, so only the explicit `MaxPool2d(2)` layers downsample — three of them, giving 8× reduction
on both axes.

Two decisions worth noting:

**`AdaptiveAvgPool2d((4,4))` rather than a fixed flatten.** Any input spectrogram size collapses to
`channels[-1] × 4 × 4`, so the head's input dimension is `256 × 16 = 4096` regardless of `n_mels` or
frame count. Change `duration` or `hop_length` and this model still constructs.

**`Dropout2d`, not `Dropout`, between conv blocks.** `Dropout2d` zeroes entire channels rather than
individual activations. Because neighbouring spectrogram pixels are highly correlated, element-wise
dropout is weak regularisation — the network reconstructs a dropped value from its neighbours. Dropping
a whole feature map forces genuine redundancy across channels. It runs at `dropout/2` (0.15 by default),
half the head's rate, because conv layers are already regularised by BatchNorm.

The 4096-dim embedding is large relative to the other backbones' 512 — the price of a flatten-based
head, and the reason this model is *not* the default fusion backbone despite having the fewest
parameters.

---

## AudioCNNLSTM

The default audio model: CNN feature extraction followed by a bidirectional LSTM with attention
pooling. [`src/models/audio.py`](../src/models/audio.py#L57)

```
Input (B, 1, 128, 130)
  │
  ├─ ConvBlock(1→32)  → MaxPool           (B,  32, 64, 65)
  ├─ ConvBlock(32→64) → MaxPool           (B,  64, 32, 32)
  ├─ ConvBlock(64→128)→ MaxPool           (B, 128, 16, 16)   ← measured
  │
  ├─ permute(0,3,1,2).reshape(B, T', C×F) (B,  16, 2048)     ← T'=16, C×F=128×16
  ├─ LSTM(2048→256, 2 layers, bidir)      (B,  16, 512)
  ├─ attention pooling over time          (B, 512)            ← _embed_dim
  ├─ Linear(512→128) → ReLU → Dropout     (B, 128)
  └─ Linear(128→6)                        (B, 6)
```

### The reshape

```python
feat = self.cnn(x)                                    # (B, C, F, T')
feat = feat.permute(0, 3, 1, 2).reshape(B, T2, C * F)  # (B, T', C×F)
```

The CNN output is treated as a **sequence over time**, where each timestep's feature vector is the
flattened channel × frequency slice at that frame. The CNN learns local spectro-temporal patterns
(formant transitions, onsets); the LSTM then models how those patterns evolve across the utterance.
That division of labour is the architecture's whole point — emotion in speech is substantially about
temporal contour (prosody, rate of change), which a pure CNN with global pooling discards.

### The dummy forward pass

```python
with torch.no_grad():
    dummy = torch.zeros(1, 1, n_mels, 130)
    out = self.cnn(dummy)
    _, C, F, _ = out.shape
    lstm_in = C * F              # 128 × 16 = 2048
```

The LSTM input size depends on how much the CNN downsamples the frequency axis — a function of
`n_mels` and the number of pooling layers. Rather than requiring the user to compute
`n_mels / 2^n_pools × channels[-1]` by hand, the model runs one throwaway forward pass at construction
and reads the shape. Change `n_mels` from 128 to 64, or drop a channel from `cnn_channels`, and the
model still builds correctly.

Note that the dummy's time dimension is hard-coded to 130. Harmless — `lstm_in` depends only on `C` and
`F`, and the LSTM handles variable sequence length — but it is a latent assumption if the time axis
ever starts mattering to construction.

### Bidirectionality

`bidirectional=True` doubles the output width to `2 × 256 = 512`, which is `_embed_dim`. Processing the
window in both directions is legitimate here because inference operates on complete 3-second windows,
not causally — there is no streaming-latency penalty for looking ahead within a window that has already
been buffered.

Inter-layer dropout is gated on depth (`dropout if lstm_layers > 1 else 0.0`), since PyTorch warns when
`dropout` is set on a single-layer LSTM where it would have no effect.

---

## VisualLSTM

Bidirectional LSTM with attention pooling over facial landmark sequences.
[`src/models/visual.py`](../src/models/visual.py)

```
Input (B, 75, 1404)
  │
  ├─ Linear(1404→256) → ReLU              (B, 75, 256)
  ├─ LSTM(256→256, 2 layers, bidir)       (B, 75, 512)
  ├─ attention pooling over time          (B, 512)   ← _embed_dim
  ├─ Linear(512→128) → ReLU → Dropout     (B, 128)
  └─ Linear(128→6)                        (B, 6)
```

The `Linear(1404→256)` projection is a 5.5× compression applied before the recurrence. Feeding 1404
dimensions straight into an LSTM would make the input-hidden weight matrix enormous
(`1404 × 4 × 256 ≈ 1.4M` parameters per direction per layer) for input dimensions that are highly
redundant — adjacent facial landmarks move together. The projection learns a compact expression
descriptor first; the LSTM then models its temporal evolution.

`hidden_dim=256` with `bidirectional=True` gives `_embed_dim = 512`, deliberately matching
`AudioCNNLSTM`. That match is what lets `CrossModalAttentionFusion` use `nn.Identity` instead of a
projection layer.

Input dim comes from `LANDMARK_DIM` in [`src/constants.py`](../src/constants.py), imported by both
`VisualLSTM` and [`builder.py`](../src/models/builder.py). It used to be hard-coded as 1404 in three
separate files while the extractor produced 1434 — see
[known issue #2](../README.md#2-landmark-dimensionality-is-probably-1434-not-1404--needs-verification-with-mediapipe-installed).

---

## Attention pooling

Shared by `AudioCNNLSTM` and `VisualLSTM`, and worth its own section because it is the least obvious
piece of the design:

```python
out, _ = self.lstm(x)                          # (B, T, 2H)
attn = torch.softmax(out.mean(-1, keepdim=True), dim=1)   # (B, T, 1)
return (out * attn).sum(1)                     # (B, 2H)
```

The alternatives it replaces:

| Approach | Problem |
|---|---|
| Last hidden state `out[:, -1]` | For a bidirectional LSTM, the "last" state is arbitrary; and a fixed window's final frame is usually trailing silence |
| Mean pooling `out.mean(1)` | Weights every frame equally, including silence and non-speech |
| Learned attention (`Linear(2H→1)`) | Works well, but adds parameters and needs tuning |

This variant scores each timestep by the **mean of its own hidden activations** and softmaxes those
scores over time. Timesteps where the LSTM is more strongly activated get more weight. It costs zero
parameters and needs no tuning, while still letting the model concentrate on the emotionally salient
portion of the window rather than whatever happened at the end of it.

The mechanism is crude — it has no learned notion of what "salient" means, only "high activation" — but
for 3-second windows on corpora of a few thousand clips, the parameter saving is likely worth more than
the extra expressiveness a learned attention would provide. Replacing it with
`nn.Linear(2*hidden, 1)` scoring would be a reasonable ablation.

---

## Fusion strategies

Three strategies forming a deliberate ladder of increasing cross-modal coupling. The point of keeping
all three is that **which one wins is itself a finding**: it says how much modality interaction the
task actually requires.

### FeatureLevelFusion — earliest interaction

[`src/models/fusion.py`](../src/models/fusion.py#L5) · 10,042,610 params

```
audio  ──▶ AudioCNNLSTM.embed()  ──▶ (B, 512) ─┐
                                                ├─ cat ─▶ (B, 1024)
visual ──▶ VisualLSTM.embed()    ──▶ (B, 512) ─┘
                                                   │
                       Linear(1024→512) → ReLU → Dropout → Linear(512→6)
```

Both modalities are encoded independently, then concatenated and classified jointly. The head can learn
arbitrary interactions between audio and visual features.

Most expressive of the three, and most prone to letting the stronger modality dominate: if audio is
more informative, gradient descent can drive the visual half of the concatenated vector towards
irrelevance and the model looks multimodal while behaving audio-only.

Note the `hidden: int = 512` default is a constructor argument that
[`build_fusion_model`](../src/models/fusion.py#L102) does not pass through, so it is not reachable from
the config.

### DecisionLevelFusion — latest interaction

[`src/models/fusion.py`](../src/models/fusion.py#L32) · 9,514,734 params

```
audio  ──▶ AudioCNNLSTM.forward() ──▶ logits_a (B, 6) ─┐
                                                        ├─ w₀·logits_a + w₁·logits_v ─▶ (B, 6)
visual ──▶ VisualLSTM.forward()   ──▶ logits_v (B, 6) ─┘
                    w = softmax(self.weights)   # 2 learnable scalars
```

Each modality classifies independently; a single learnable 2-vector, softmax-normalised so the weights
sum to 1, mixes the logits. **Just two fusion parameters** — the entire rest of the count is the two
backbones.

Two properties make it the most useful of the three for this project:

- **Directly interpretable.** After training, `softmax(model.weights)` *is* the answer to "which
  modality mattered?" No attribution method needed. `test_decision_weights_softmax_sums_to_one`
  asserts the normalisation.
- **Robust to a missing modality.** If the visual stream is unreliable — and given the zero-fill for
  samples without video, it often is — the model can learn `w₁ ≈ 0` and degrade to audio-only cleanly
  rather than being confused by noise.

The limitation is that the modalities never interact before the decision. If audio and visual cues are
individually ambiguous but jointly decisive, this architecture cannot exploit that.

**Check the learned weights after training.** If `w₁ ≈ 0` on a manifest with many zero-filled visual
inputs, that is the model correctly reporting that the visual stream carried no information — an
important negative result, not a bug.

### CrossModalAttentionFusion — bidirectional interaction

[`src/models/fusion.py`](../src/models/fusion.py#L51) · 11,881,970 params

```
audio  ──▶ embed() ──▶ (B, 512) ──▶ unsqueeze(1) ──▶ a (B, 1, 512)
visual ──▶ embed() ──▶ (B, 512) ──▶ v_proj ──▶ unsqueeze(1) ──▶ v (B, 1, 512)

a_ctx, _ = MultiheadAttention(a, v, v)      # audio queries visual
v_ctx, _ = MultiheadAttention(v, a, a)      # visual queries audio

a_out = LayerNorm(a + a_ctx).squeeze(1)     # residual
v_out = LayerNorm(v + v_ctx).squeeze(1)

head(cat([a_out, v_out]))  →  Linear(1024→256) → ReLU → Dropout → Linear(256→6)
```

Two `MultiheadAttention` blocks (8 heads, 64 dims per head) let each modality query the other.
Residual connections plus LayerNorm follow the standard transformer block pattern, so the model can
learn to ignore cross-modal context if it is unhelpful — the residual path preserves the unimodal
signal.

The projection guard:

```python
self.v_proj = (nn.Linear(visual_model._embed_dim, dim)
               if visual_model._embed_dim != dim else nn.Identity())
```

With the default config both embeddings are 512, so this is `nn.Identity` and costs nothing. Change
`visual_lstm.hidden_dim` and a projection appears automatically rather than the model failing.

**One caveat about the sequence length.** Attention operates on sequences of length **1** — both
embeddings are already pooled to a single vector before `unsqueeze(1)`. With `T=1`, the attention
softmax over a single key is exactly 1, so `a_ctx` reduces to a linear transformation of `v` and no
actual *selection* over time occurs. It is still a learned, gated cross-modal projection with residual
mixing, and it will train — but it is not the frame-level cross-modal alignment the name suggests.

Genuine temporal cross-attention would require attending over the pre-pooled LSTM outputs — `(B, 16,
512)` for audio and `(B, 75, 512)` for visual — which is a worthwhile future experiment and would
justify the parameter count better than the current formulation does.

### Choosing between them

| | `feature_level` | `decision_level` | `attention` |
|---|---|---|---|
| Interaction point | Embeddings | Logits | Embeddings, bidirectional |
| Fusion parameters | ~525k | 2 | ~2.4M |
| Interpretability | Low | **High** | Low |
| Robust to a dead modality | Poor | **Good** | Moderate (residual helps) |
| Data hunger | Moderate | Low | High |

On corpora of this size, `decision_level` is the sensible first experiment: fewest fusion parameters,
most interpretable result, and its learned weights answer the project's actual research question about
modality contribution.

---

## The builder

[`src/models/builder.py`](../src/models/builder.py) is the single point where a name becomes a module.

```python
UNIMODAL = {"audio_cnn", "audio_cnn_lstm", "visual_lstm"}
FUSION   = {"feature_level", "decision_level", "attention"}

def is_multimodal(name: str) -> bool:
    return name in FUSION

def build_model(name: str, cfg: dict, num_classes: int) -> nn.Module: ...
```

Everything downstream refers to architectures by name only:

- `train.py` — `--model` choices, then `build_model(...)`
- `evaluate.py` — reads `ckpt["model_name"]`, rebuilds
- `inference.py` — same, from the checkpoint's embedded config
- `is_multimodal(name)` decides one-tensor versus two-tensor forward calls in all three

Fusion models always use `AudioCNNLSTM` and `VisualLSTM` as backbones —
[`_audio_backbone`](../src/models/builder.py#L26) and
[`_visual_backbone`](../src/models/builder.py#L33) — never `AudioCNN`, whose 4096-dim embedding would
dominate the concatenation and require an asymmetric projection.

Unknown names raise with the valid set included, which is what
`test_builder_unknown_name_raises` checks:

```python
raise ValueError(f"Unknown model: {name!r}. Choose from {UNIMODAL | FUSION}")
```

[`n_frames(cfg)`](../src/models/builder.py) computes `floor(sr × duration / hop) + 1`. `build_model`
does not need it (`AudioCNNLSTM` derives its own shapes), but `evaluate.py` uses it to size the latency
benchmark's dummy tensors, which previously hard-coded 130 frames.

---

## Adding an architecture

**1. Implement it** in `src/models/`, honouring the backbone contract:

```python
class AudioTransformer(nn.Module):
    def __init__(self, num_classes=6, d_model=256, n_layers=4, dropout=0.3, n_mels=128):
        super().__init__()
        # ...
        self._embed_dim = d_model          # required for fusion compatibility
        self.head = nn.Sequential(
            nn.Linear(d_model, 128), nn.ReLU(inplace=True),
            nn.Dropout(dropout), nn.Linear(128, num_classes),
        )

    def embed(self, x):    ...             # → (B, self._embed_dim)
    def forward(self, x):  return self.head(self.embed(x))
```

**2. Register it** in `build_model` and add the name to `UNIMODAL` or `FUSION`:

```python
if name == "audio_transformer":
    c = mc["audio_transformer"]
    return AudioTransformer(num_classes, c["d_model"], c["n_layers"],
                            c["dropout"], cfg["audio"]["n_mels"])
```

**3. Add config** under `model:` in `settings.yaml`.

**4. Add to CLI choices** in [`train.py`](../scripts/train.py#L38).

**5. Export it** from [`src/models/__init__.py`](../src/models/__init__.py).

The parametrised tests in `test_model.py` pick it up automatically once it is in the choices list —
`test_backward_pass` and `test_builder_returns_nn_module` are parametrised over model names, so a new
architecture gets gradient-flow and factory coverage for free.

**To make it usable as a fusion backbone**, match `_embed_dim` to the counterpart modality (512 by
default) so cross-attention skips its projection, and keep `embed()` free of dropout — fusion consumes
the representation directly and dropout there would inject noise into the fusion head at training time
in a way the unimodal head does not experience.
