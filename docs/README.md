# SER System — Documentation

Complete documentation for the multimodal speech emotion recognition system. Start with the
[project README](../README.md) for the high-level picture; these pages go into the detail that would
overwhelm it.

## Suggested reading order

**If you are setting the project up for the first time**

1. [setup.md](setup.md) — install Python and Node dependencies, verify the test suite
2. [configuration.md](configuration.md) — understand `settings.yaml` before you change anything
3. [datasets.md](datasets.md) — acquire corpora and place them where the parsers expect
4. [training.md](training.md) — run your first training job

**If you are trying to understand how the system works**

1. [architecture.md](architecture.md) — layers, boundaries, and the shape of data at every stage
2. [features.md](features.md) — what the model actually sees
3. [models.md](models.md) — the six architectures, layer by layer
4. [backend/README.md](backend/README.md) — how a trained model becomes a live service

**If you are working on the front end**

1. [frontend/README.md](frontend/README.md) — stack and file map
2. [frontend/audio-pipeline.md](frontend/audio-pipeline.md) — microphone to WebSocket
3. [backend/websocket-protocol.md](backend/websocket-protocol.md) — the wire format you must honour
4. [frontend/components.md](frontend/components.md) — component contracts

**If you are extending the models**

1. [models.md](models.md) — the `embed()` / `_embed_dim` contract fusion depends on
2. [training.md](training.md) — where a new architecture must be registered
3. [testing.md](testing.md) — the parametrised tests a new model is automatically pulled into

## Page index

### Core

| Page | Contents |
|---|---|
| [architecture.md](architecture.md) | System layers, data flow, tensor shapes end to end, design rationale |
| [setup.md](setup.md) | Prerequisites, installation, GPU setup, troubleshooting |
| [configuration.md](configuration.md) | Every `settings.yaml` key, valid ranges, cache-invalidation rules |
| [datasets.md](datasets.md) | Corpus acquisition, filename grammars, label mapping, split algorithm |
| [features.md](features.md) | Log-mel, MFCC + Δ + ΔΔ, and FaceMesh landmark extraction |
| [models.md](models.md) | All six architectures with layer-by-layer tensor traces |
| [training.md](training.md) | Training loop, hyperparameters, checkpoint format, monitoring |
| [evaluation.md](evaluation.md) | Metrics, confusion matrices, latency benchmark methodology |
| [testing.md](testing.md) | All 127 tests explained, fixtures, how to add more |

Landmark geometry and the audio feature height are defined once in
[`src/constants.py`](../src/constants.py) and [`feature_height`](../src/models/builder.py); every
consumer imports them rather than hard-coding a number.

### Backend

| Page | Contents |
|---|---|
| [backend/README.md](backend/README.md) | Service overview, module map, request lifecycle |
| [backend/api-reference.md](backend/api-reference.md) | Endpoint reference with status codes and failure modes |
| [backend/websocket-protocol.md](backend/websocket-protocol.md) | Full streaming protocol specification |
| [backend/inference-engine.md](backend/inference-engine.md) | `InferenceEngine` and `AudioStreamBuffer` internals |
| [backend/deployment.md](backend/deployment.md) | uvicorn, environment variables, CORS, reverse proxy, containers |

### Front end

| Page | Contents |
|---|---|
| [frontend/README.md](frontend/README.md) | Stack, file map, dev workflow, production build |
| [frontend/components.md](frontend/components.md) | Props, state, and rendering logic for every component |
| [frontend/audio-pipeline.md](frontend/audio-pipeline.md) | getUserMedia → AudioWorklet → WebSocket, plus the fallback |
| [frontend/state-management.md](frontend/state-management.md) | `useStream` state machine, refs, cleanup, caveats |
| [frontend/styling.md](frontend/styling.md) | Design tokens, layout, animations, theming |

## Conventions used in these docs

- Tensor shapes are written `(B, C, F, T)` — batch, channel, frequency, time.
- Default values are those in [`config/settings.yaml`](../config/settings.yaml) unless stated.
- Numbers marked **measured** were obtained by running the code in this repository; anything marked
  **expected** is derived from the config and has not been observed on real data.
- Code references link to the file and line, e.g. [`build_model`](../src/models/builder.py#L36).

## Status of the documented system

The pipeline is fully implemented and unit-tested but has **not** been run on real corpora. No trained
checkpoints exist, so no accuracy, F1, or latency results are reported anywhere in these docs. Where
a page would normally show results, it shows the command that will produce them.

Three defects that had been sitting on those untraversed paths — the MFCC channel dimension (and the
LSTM width that depended on it), the FaceMesh landmark count, and MSP-IMPROV speaker parsing — have
been fixed, and each is now covered by a test verified to fail without its fix. See
[Known issues and limitations](../README.md#known-issues-and-limitations) for what changed and what
remains. The pages here describe the current behaviour; where a fix reshaped an interface, the page
says what it was and why.

The one path still without end-to-end coverage is visual feature extraction itself: `mediapipe` is
not installed in the development environment, so `extract_visual_features` has never run against a
real video. The landmark dimension is now validated at runtime rather than assumed, but the
extraction remains unexercised.
