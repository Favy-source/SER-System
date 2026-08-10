# Testing

127 tests across five modules, all passing in ~32 s on CPU with no corpora, no checkpoints, and no GPU.

- [Running the suite](#running-the-suite)
- [Design principles](#design-principles)
- [Fixtures](#fixtures)
- [test_features.py](#test_featurespy--16-tests)
- [test_datasets.py](#test_datasetspy--22-tests)
- [test_model.py](#test_modelpy--29-tests)
- [test_api.py](#test_apipy--20-tests)
- [Coverage gaps](#coverage-gaps)
- [Adding tests](#adding-tests)

---

## Running the suite

```bash
python3 -m pytest                          # all 127
python3 -m pytest tests/test_model.py      # one module
python3 -m pytest -k websocket             # by name substring
python3 -m pytest -k "not api"             # exclude
python3 -m pytest -x                       # stop at first failure
python3 -m pytest --tb=long                # full tracebacks
```

`pytest` is not in `backend/requirements.txt` — `pip install pytest`.

[`pytest.ini`](../pytest.ini):

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::UserWarning
    ignore::FutureWarning
```

`-v` is on by default so every test name prints, and `--tb=short` keeps failures readable. The three
warning filters suppress a large volume of noise from librosa, torch, and mediapipe — convenient, but it
also means genuine deprecation warnings in *this* codebase are hidden. Run with `-W default`
periodically to see them (that is how the `torch.cuda.amp.GradScaler` deprecation surfaces).

Expected:

```
collected 127 items
tests/test_api.py ....................                   [ 15%]
tests/test_datasets.py .................................  [ 41%]
tests/test_features.py ................                   [ 54%]
tests/test_integration.py .............................   [ 77%]
tests/test_model.py .............................         [100%]
============ 127 passed in 32.66s ============
```

---

## Design principles

Three constraints shape the whole suite, and they are worth preserving:

**1. No external data.** No test requires a corpus, a checkpoint, or a network connection. Audio is
synthesised from sine waves; dataset parsers are fed `touch()`ed empty files; the inference engine is
`MagicMock`ed. This is what makes the suite runnable in CI, on a fresh clone, and on a machine that has
never had access to the licensed corpora.

**2. Fast enough to run constantly.** ~19 s total. Small batch size (`B = 4`), CPU-only, no training
loops. A suite you run before every commit has to be a suite you do not mind waiting for.

**3. Properties, not values.** The tests assert structural and invariant properties — shapes, disjointness,
determinism, absence of NaN, gradient reachability — rather than specific numeric outputs. Nothing here
asserts "accuracy > 0.6", because that would require training. The suite verifies the pipeline is
*correct*, not that the models are *good*.

Every test module prepends the repo root to `sys.path`, so `src.` and `backend.` imports resolve without
an installed package.

---

## Fixtures

[`tests/conftest.py`](../tests/conftest.py) provides four shared fixtures at
`SR = 22050, DURATION = 3.0, N = 66150`:

| Fixture | Type | Purpose |
|---|---|---|
| `audio_cfg` | `dict` | The `audio:` config block, so tests do not read `settings.yaml` |
| `sine_audio` | `np.ndarray` | 3 s, 440 Hz sine at amplitude 0.5, float32 |
| `sine_wav_path` | `str` | The sine written to a `tmp_path` `.wav`; returns the path |
| `sine_wav_bytes` | `bytes` | The sine as in-memory WAV bytes |

A 440 Hz sine is the right test signal: deterministic, with known spectral content (one peak plus
harmonics from the finite window), non-degenerate — so a real mel spectrogram results — and trivially
reproducible. It is not speech, which is exactly the point: these tests check the transform, not the
model's opinion about it.

`audio_cfg` being a literal dict rather than a config read means the tests do not break when
`settings.yaml` is edited for an experiment. Deliberate decoupling.

---

## test_features.py — 16 tests

Audio loading and feature extraction. [`tests/test_features.py`](../tests/test_features.py)

### Loading, padding, cropping (5)

| Test | Asserts |
|---|---|
| `test_load_audio_short_is_padded` | A 1 s clip becomes exactly `N` samples |
| `test_load_audio_long_is_cropped` | A 5 s clip becomes exactly `N` samples |
| `test_load_audio_exact_length_unchanged` | A 3 s clip is untouched |
| `test_load_audio_crop_is_centered` | **The crop is taken from the middle, not the start** |
| `test_load_audio_resamples` | A 44.1 kHz file loads to the 22.05 kHz target length |

`test_load_audio_crop_is_centered` is the one that matters most. Length-only assertions would pass for a
head crop, a tail crop, or a centre crop equally — and the choice of centre crop is a substantive
modelling decision (the emotional peak sits mid-utterance in acted corpora). Testing the *position*
pins the behaviour, not just the shape.

### Mel spectrogram (4)

| Test | Asserts |
|---|---|
| `test_mel_spectrogram_shape` | `(128, 130)` exactly |
| `test_mel_spectrogram_normalized_mean_near_zero` | Normalisation produces ~0 mean, ~1 std |
| `test_mel_spectrogram_no_nan_on_silence` | **All-zero input yields no NaN** |
| `test_mel_spectrogram_without_normalization` | `normalize=False` leaves dB values unstandardised |

### MFCC (3)

`test_mfcc_shape_with_delta` → `(120, 130)`; `test_mfcc_shape_without_delta` → `(40, 130)`;
`test_mfcc_no_nan`.

### Combined extraction (4)

`test_extract_returns_mel_and_mfcc`, `test_extract_mel_shape`, `test_extract_mfcc_shape`,
`test_extract_silence_no_nan` — verifying `extract_audio_features` returns both keys with the right
shapes and survives silence.

### Why the silence tests are the most important in this module

`librosa.power_to_db` computes `10 · log₁₀(S / ref)` with `ref = np.max(S)`. On digital silence both are
zero, which is a textbook `-inf` → NaN source. NaNs then propagate through the network and silently ruin
a training run — the loss becomes `nan` and every gradient with it.

This is not a hypothetical edge case. A live microphone stream contains silent windows constantly:
before speech begins, during pauses, after it ends. `AudioStreamBuffer` will hand every one of them to
the model. Three separate tests cover it because it is the failure most likely to occur in production
and the hardest to diagnose after the fact.

---

## test_datasets.py — 22 tests

Corpus parsing, splitting, and the torch Dataset. [`tests/test_datasets.py`](../tests/test_datasets.py)

### Label mapping (4)

`test_label2idx_invertible`, `test_idx2label_invertible`, `test_unified_matches_label2idx`,
`test_unified_has_six_classes` — verifying `LABEL2IDX` and `IDX2LABEL` are consistent inverses and the
class count is 6.

Cheap tests guarding an expensive mistake: a mismatch between these mappings would mean predictions are
decoded to the wrong label names, producing a model that appears to work while systematically
mislabelling its output.

### RAVDESS parsing (4)

| Test | Asserts |
|---|---|
| `test_parse_ravdess_labels` | Emotion codes map correctly |
| `test_parse_ravdess_drops_null_labels` | `"08"` (surprised) → `null` → row dropped |
| `test_parse_ravdess_speaker_prefix` | Speaker is `ravdess_…` |
| `test_parse_ravdess_dataset_column` | `dataset == "ravdess"` |

### CREMA-D parsing (2)

`test_parse_cremad_labels`, `test_parse_cremad_speaker_prefix`.

### MSP-IMPROV parsing (3)

| Test | Asserts |
|---|---|
| `test_parse_msp_improv_labels` | `Evalution.txt` parsing, comment lines skipped |
| `test_parse_msp_improv_skips_missing_files` | Labels with no audio on disk are dropped |
| `test_parse_msp_improv_missing_label_file` | Missing `Evalution.txt` → empty DataFrame, no exception |

All parser tests build synthetic corpora with `tmp_path` and `touch()`:

```python
def test_parse_ravdess_labels(tmp_path):
    (tmp_path / "03-01-05-01-02-01-12.wav").touch()
    df = parse_ravdess(str(tmp_path), RAVDESS_MAP)
    assert df.iloc[0]["label"] == "angry"
```

The files are empty. Parsers read filenames and label files, never audio content, so this is sufficient —
and it keeps the tests instant and dependency-free.

**Note:** no test asserts on MSP-IMPROV speaker *values*, only that parsing succeeds. That is why
[the speaker-collapse bug](datasets.md#known-issues) — `fname[:6]` yielding `"MSP-IM"` for every real
file — survives the suite. A test asserting distinct speakers for distinct actors would have caught it,
and should be added with the fix.

### Speaker-independent split (4)

| Test | Asserts |
|---|---|
| `test_split_speakers_are_disjoint` | **train ∩ val = val ∩ test = train ∩ test = ∅** |
| `test_split_covers_all_samples` | Every sample lands in exactly one split |
| `test_split_is_reproducible` | Same seed → identical partition |
| `test_split_respects_fractions` | Split sizes within loose bounds |

`test_split_speakers_are_disjoint` is the single most consequential assertion in the suite. Every claim
this project can make about generalisation rests on the splits being speaker-disjoint; if that silently
broke, every reported number would be inflated and nothing else in the pipeline would notice. Asserted,
not assumed.

`test_split_respects_fractions` checks bounds rather than exact sizes, correctly: speakers contribute
unequal sample counts, so 15% of speakers is only approximately 15% of samples.

### EmotionDataset (5)

| Test | Asserts |
|---|---|
| `test_dataset_len` | `__len__` matches the DataFrame |
| `test_dataset_audio_mel_shape` | Mel items are `(1, 128, 130)` — channel dim present |
| `test_dataset_label_correct` | Labels are the right `LABEL2IDX` index |
| `test_dataset_all_labels_reachable` | All six classes can be produced |
| `test_dataset_missing_video_returns_zeros` | Null `video_path` → zero visual tensor |

`test_dataset_missing_video_returns_zeros` pins the behaviour that makes audio-only corpora usable in
multimodal training. Without the zero-fill, MSP-IMPROV could not participate at all.

Note that no test loads an item with `feature="mfcc"` — which is precisely the gap that lets
[known issue #1](../README.md#1---feature-mfcc-crashes-the-cnn-models--confirmed) through. The MFCC
*extraction* is tested in `test_features.py`, and the mel *loading* is tested here, but the MFCC loading
path is covered by neither.

---

## test_model.py — 29 tests

All six architectures and the factory. [`tests/test_model.py`](../tests/test_model.py)

Constants: `B = 4`, `MEL = (4, 1, 128, 130)`, `VISUAL = (4, 75, 1404)`, and a minimal `CFG` dict
sufficient for `build_model`.

### Forward shapes (6)

One test per architecture, each asserting `(B, 6)` output. Trivial-looking, and it catches the most
common class of error when modifying an architecture: a reshape, permute, or pooling change that
silently alters the output dimension.

### Embedding dimensions (4)

| Test | Asserts |
|---|---|
| `test_audio_cnn_embed_dim` | `embed()` returns `(B, 4096)` |
| `test_audio_cnn_lstm_embed_dim` | `(B, 512)` |
| `test_visual_lstm_embed_dim` | `(B, 512)` |
| `test_audio_visual_embed_dims_match` | **`AudioCNNLSTM._embed_dim == VisualLSTM._embed_dim`** |

The last one guards the precondition for cross-attention fusion using `nn.Identity` instead of a
projection. If someone changes `lstm_hidden` without changing `hidden_dim`, this test explains why that
matters before the fusion model quietly gains a layer.

### Gradient flow (1 parametrised → 6 cases)

```python
@pytest.mark.parametrize("model_name", [...all six...])
def test_backward_pass(model_name):
    # forward → loss → backward → assert every parameter has a non-None,
    # finite gradient
```

The most valuable test in the module. A forward-shape test passes even when part of the network is
disconnected from the loss — a detached tensor, a `no_grad` block left in, a branch whose output is
discarded. Asserting that **every** parameter receives a finite gradient catches exactly that class of
silent bug, which otherwise manifests only as "this model trains worse than it should".

Parametrised, so a new architecture added to the list gets gradient coverage for free.

### Numerical stability (2)

`test_eval_mode_no_dropout_variance` — two forward passes in `eval()` produce identical output, verifying
dropout and BatchNorm are actually disabled. Non-determinism in eval mode would make serving
unpredictable and evaluation unrepeatable.

`test_no_nan_in_outputs` — no NaN in the logits.

### Factory (4)

`test_builder_returns_nn_module` (parametrised over all six), `test_builder_unknown_name_raises`
(`ValueError`), `test_is_multimodal_correct` (`FUSION` → `True`, `UNIMODAL` → `False`).

### Fusion-specific (3)

| Test | Asserts |
|---|---|
| `test_decision_weights_are_learnable` | `model.weights.requires_grad` |
| `test_decision_weights_softmax_sums_to_one` | `softmax(weights).sum() == 1` |
| `test_audio_cnn_lstm_has_fewer_params_than_fusion` | Fusion models are larger than their backbone |

The softmax test matters because interpretability depends on it: `decision_level`'s learned weights are
only readable as "modality contribution" if they are normalised. If someone replaced the softmax with a
raw parameter, the weights would still train but would no longer mean what the documentation says they
mean.

---

## test_api.py — 20 tests

HTTP endpoints and WebSocket streaming. [`tests/test_api.py`](../tests/test_api.py)

### The mocking strategy

```python
MOCK_PRED = {
    "emotion": "happy", "confidence": 0.87,
    "probabilities": {e: (0.87 if e == "happy" else round(0.13 / 5, 4)) for e in UNIFIED},
    "latency_ms": 11.5, "model_name": "audio_cnn_lstm",
}

@pytest.fixture
def client():         # engine = None → the degraded path
    with patch("backend.main._load_engine", return_value=None):
        with TestClient(app) as c: yield c

@pytest.fixture
def client_m():       # MagicMock engine → the happy path
    with patch("backend.main._load_engine", return_value=_make_engine()):
        with TestClient(app) as c: yield c
```

Patching `_load_engine` rather than `InferenceEngine` is the right seam: it is the single function the
lifespan handler calls, so one patch controls both the loaded and unloaded states without touching torch
at all. The API tests therefore run in milliseconds and require no checkpoint.

`TestClient` as a context manager is required — that is what triggers FastAPI's lifespan events, and
without it `engine` would never be set.

The two fixtures give first-class coverage of **both** states. Six tests exercise the no-model path,
which is what makes graceful degradation a tested guarantee rather than an accident.

### `GET /health` (4)

200 status; `model_loaded: false` with no engine; `model_loaded: true` plus model name and device with
one; full response schema.

### `GET /models` (2)

200 status; `checkpoints` key present.

### `POST /predict/audio` (5)

| Test | Asserts |
|---|---|
| `test_predict_audio_503_when_no_model` | 503 with no engine |
| `test_predict_audio_422_on_empty_file` | 422 on a zero-byte upload |
| `test_predict_audio_200_on_valid_wav` | 200 for a valid WAV |
| `test_predict_audio_response_shape` | All five response fields present |
| `test_predict_audio_probabilities_sum_to_one` | Probabilities sum to 1.0 |
| `test_predict_audio_calls_engine` | The engine method was actually invoked |

`test_predict_audio_calls_engine` guards against a passing test that never reached the model — an
endpoint returning a hard-coded or cached response would satisfy the shape assertions.

### `POST /predict/switch` (2)

404 for a missing checkpoint; success for one that exists, with the global engine actually replaced.

### `WS /ws/stream` (5)

| Test | Asserts |
|---|---|
| `test_ws_no_model_sends_error` | An `error` frame before close when no engine |
| `test_ws_handshake_returns_ready` | Handshake yields `{"type": "ready"}` |
| `test_ws_ready_contains_window_info` | `ready` carries `window_sec` and `hop_sec` |
| `test_ws_prediction_after_window_fills` | **A prediction arrives once ≥3 s of PCM has been sent** |
| `test_ws_reset_clears_buffer` | `{"type":"reset"}` → `info` frame |
| `test_ws_ping_returns_pong` | `{"type":"ping"}` → `pong` |

`test_ws_prediction_after_window_fills` is the most substantial test in the suite. It sends real binary
float32 frames until the buffer accumulates a full window, then asserts a `prediction` frame arrives —
covering the handshake, binary framing, `AudioStreamBuffer` accumulation, the hop gate, the engine call,
and the response envelope in one path. It is the closest thing here to an integration test.

The mocked engine has `sr = 22050` while the handshake declares 16000, so the resampling branch in
`AudioStreamBuffer.push` is exercised too.

---

## Coverage gaps

Honest inventory of what is not tested.

### Closed by test_integration.py

Three bugs shipped because every stage was tested against inputs it constructed itself. That verified
each consumer but never the *contract between producer and consumer* — which is exactly where the bugs
lived:

| Was invisible because | Now covered by |
|---|---|
| MFCC extraction was tested, and mel dataset loading was tested, but MFCC loading feeding a model was tested by neither | `test_audio_chain_forward`, `test_dataset_item_has_channel_axis`, `test_multimodal_chain_forward` |
| `test_model.py` built `VISUAL = (B, 75, 1404)` by hand, so models were tested against the *assumed* landmark width, not the extractor's | `test_landmark_constants_consistent`, `test_builder_visual_input_dim_is_the_constant`, `test_zero_fill_shape_follows_config` |
| No test asserted that a model built for one feature could reload its own weights | `test_state_dict_round_trip` |
| `InferenceEngine` was mocked in all 20 API tests, so real checkpoint loading and serving-side extraction never ran | `test_inference_engine_real_checkpoint`, `test_inference_engine_mfcc_checkpoint`, `test_inference_engine_zero_visual_width` |
| MSP-IMPROV fixtures used `MSP-ABC-01` and never asserted on the speaker value | `test_parse_msp_improv_speakers_are_distinct`, `test_msp_speakers_survive_the_split` (in `test_datasets.py`) |

The last hard-coded `1404`s were in the tests themselves. They now import `LANDMARK_DIM`, which is what
makes flipping `REFINE_LANDMARKS` a one-line change that leaves the suite green — the actual test of
whether a constant is a single source of truth.

### Still not tested

| Area | Consequence |
|---|---|
| `scripts/train.py` | The training loop, class weighting, AMP ordering, early stopping, and checkpoint writing are entirely untested |
| `scripts/evaluate.py` | Metrics computation, confusion-matrix rendering, latency benchmarking |
| `scripts/preprocess.py` | Idempotent skipping, error collection, manifest writing |
| `extract_visual_features` | Requires mediapipe and a video fixture. The `_MEDIAPIPE` guard makes it return `None` when absent, so it has never run against a real video. The landmark count is now validated at runtime, but the extraction itself is unexercised |
| Front end | No JS test runner installed. Zero automated coverage |
| `AudioStreamBuffer` in isolation | Exercised only through `test_ws_prediction_after_window_fills`; the hop gate, memory cap, and resampling branch have no direct tests |

### Highest-value additions

1. **A real landmark fixture** — one small video committed as a test asset (or generated with OpenCV),
   extracted through the real MediaPipe path, asserting the dimension the models expect. The only
   remaining gap of the kind that produced the original three bugs.
2. **A `train.py` smoke test** — 2 epochs, 20 synthetic samples, asserting a checkpoint is written with
   the right keys and that the recorded `feature` round-trips into `build_model`. Covers the largest
   untested surface in the repository.
3. **`AudioStreamBuffer` unit tests** — that `push` returns `None` until a full window, that the hop gate
   throttles to the expected rate, that the buffer stays capped at two windows, and that resampling
   triggers only on a rate mismatch.
4. **`preprocess.py` idempotency** — run twice, assert the second run writes nothing and that a corrupt
   file lands in `errors_audio.txt` rather than aborting.
5. **Front-end tests** — Vitest plus React Testing Library for the components, and a mocked WebSocket for
   `useStream`. The stale-`status` closure bug documented in
   [frontend/state-management.md](frontend/state-management.md#the-stale-status-closure) would be caught
   by a test that errors a connection and then closes it.

---

## Adding tests

Follow the existing patterns.

### A parser test

```python
def test_parse_mycorpus_labels(tmp_path):
    (tmp_path / "spk1_joy_01.wav").touch()          # empty file is enough
    df = parse_mycorpus(str(tmp_path), {"joy": "happy"})
    assert len(df) == 1
    assert df.iloc[0]["label"] == "happy"
    assert df.iloc[0]["speaker"].startswith("mycorpus_")
```

### A model test

Add the architecture name to the `parametrize` lists and it inherits gradient-flow and factory coverage
automatically:

```python
@pytest.mark.parametrize("model_name", [
    "audio_cnn", "audio_cnn_lstm", "visual_lstm",
    "feature_level", "decision_level", "attention",
    "my_new_model",          # ← add here
])
def test_backward_pass(model_name): ...
```

### An API test

```python
def test_my_endpoint(client_m):
    r = client_m.get("/my/endpoint")
    assert r.status_code == 200
    assert r.json()["field"] == "expected"
```

Use `client` (no engine) to test the degraded path and `client_m` (mocked engine) for the happy path.
Test both — the no-model path is a real state this system spends time in.

### Guidelines

- **Keep the suite data-free.** Synthesise inputs; do not add fixtures that require a corpus.
- **Assert properties, not learned values.** Shapes, invariants, determinism, finiteness. Never accuracy.
- **Test both success and failure paths**, especially for API endpoints.
- **Prefer connecting two real stages** over constructing a synthetic input for one — that is where the
  bugs actually live.
- **Keep it fast.** If a test takes more than a second, ask whether a smaller input would prove the same
  thing.
