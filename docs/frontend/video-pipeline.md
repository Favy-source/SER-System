# Video capture pipeline

How webcam frames become face landmarks on the wire. Implemented in
[`useFaceTracking.js`](../../frontend/src/hooks/useFaceTracking.js) and
[`VideoCapture.jsx`](../../frontend/src/components/VideoCapture.jsx).

- [Why landmarks and not pixels](#why-landmarks-and-not-pixels)
- [The chain](#the-chain)
- [Vendored MediaPipe assets](#vendored-mediapipe-assets)
- [The 478 vs 468 problem](#the-478-vs-468-problem)
- [Frame rate](#frame-rate)
- [Where normalisation happens, and why](#where-normalisation-happens-and-why)
- [Status reporting](#status-reporting)
- [Teardown](#teardown)
- [Troubleshooting](#troubleshooting)

---

## Why landmarks and not pixels

The browser runs MediaPipe FaceLandmarker locally and sends only coordinates.
**No video ever leaves the machine.**

| | landmarks | video frames |
|---|---|---|
| Bandwidth @10 fps | ~56 KB/s | 0.5–5 MB/s |
| Server CPU per client | negligible | a full FaceMesh inference |
| Privacy | coordinates only | identifiable imagery |
| Needs mediapipe server-side | no | yes |

The privacy property is the one that matters for the clinical framing: a
landmark stream is far easier to justify to an ethics board than a video feed,
and it removes an entire category of data-handling obligation. It also means the
backend does not need `mediapipe` installed to serve multimodal predictions —
which is just as well, since it currently is not installed in most environments.

---

## The chain

```
navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
        │
        ▼
  <video> element  (preview, mirrored, muted, playsInline)
        │
        ▼
  FaceLandmarker.detectForVideo(video, timestamp)      ← WASM, GPU delegate
        │
        ▼
  478 landmarks × {x, y, z}   →  flatten to Float32Array(1434)   ← RAW
        │
        ▼
  ws.send(tagFrame(TAG_LANDMARKS, flat.buffer))        ← 4-byte tagged frame
        │
        ▼
  VisualStreamBuffer.push_bytes()
        ├─ reshape (-1, 3)
        ├─ normalize_landmarks()   ← the SAME function training used
        └─ rolling window of max_frames
        │
        ▼
  AudioStreamBuffer fires  →  engine.predict(audio, visual_window)
```

Audio drives the clock. Landmark frames only update state — they never trigger
inference. When an audio window closes, it asks the visual buffer for whatever
it currently holds. Both windows are anchored to "now", which matches how
training paired one clip with one label.

The MediaPipe import is dynamic:

```javascript
const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');
```

so Vite code-splits it into its own chunk and the 34 MB WASM runtime is never
fetched unless the user actually switches the camera on. Verified in the build
output — `vision_bundle-*.js` is a separate 155 KB chunk.

---

## Vendored MediaPipe assets

Two runtime assets are needed and neither belongs in git:

| asset | size | source |
|---|---|---|
| WASM runtime | ~34 MB | ships inside `node_modules/@mediapipe/tasks-vision/wasm` |
| `face_landmarker.task` | ~3.6 MB | downloaded from Google's model CDN |

[`scripts/setup-mediapipe.mjs`](../../frontend/scripts/setup-mediapipe.mjs) copies
the first and downloads the second into `public/mediapipe/`, which is
gitignored. It runs automatically via `predev` and `prebuild`, is idempotent, and
skips work already done:

```bash
cd frontend
npm run setup:mediapipe        # or just npm run dev / npm run build
```

```
[mediapipe] wasm: 6 copied, 0 already present -> public/mediapipe/wasm
[mediapipe] model saved (3.6 MB)
```

**A failed model download is not fatal.** The script warns and continues; face
tracking is then unavailable and the app runs audio-only. Failing a build over
an optional asset would be worse than degrading.

For an air-gapped install, fetch `face_landmarker.task` elsewhere and drop it at
`frontend/public/mediapipe/models/face_landmarker.task`. The WASM copy needs no
network at all.

Both paths are overridable at build time:

| variable | default |
|---|---|
| `VITE_MEDIAPIPE_WASM` | `/mediapipe/wasm` |
| `VITE_FACE_MODEL_URL` | `/mediapipe/models/face_landmarker.task` |

Point them at a CDN if you would rather not vendor.

---

## The 478 vs 468 problem

The JS `FaceLandmarker` returns **478** landmarks — the 468-point base mesh plus
10 iris points. The Python training path uses `FaceMesh(refine_landmarks=False)`,
which returns **468**, so `LANDMARK_DIM` is 1404.

Rather than forcing the two to agree, the client sends whatever it has and
[`normalize_landmarks`](../../src/features.py) keeps the leading
`N_FACE_LANDMARKS`:

```python
if len(coords) < N_FACE_LANDMARKS:
    raise ValueError(...)
coords = coords[:N_FACE_LANDMARKS]
```

This is well-defined because MediaPipe **appends** the iris points after the base
mesh, so the base mesh is always the leading block. Consequences:

- A 478-point browser feeds a 468-point model correctly.
- Flipping `REFINE_LANDMARKS` in [`src/constants.py`](../../src/constants.py) to
  `True` (1434) also works, with no client change.
- A truncated or wrong-size frame is rejected with an `error` frame rather than
  silently producing garbage.

`test_ws_extra_landmarks_accepted` and `test_visual_buffer_truncates_extra_landmarks`
pin this.

---

## Frame rate

Throttled to ~10 fps:

```javascript
const TARGET_FPS = 10;
if (now - lastSentRef.current < FRAME_MS) return;
```

The loop runs on `requestAnimationFrame` (typically 60 Hz) but only detects and
sends on the throttle boundary. 10 fps is chosen deliberately:

- The server buffers `max_frames = 75`, so 10 fps covers 7.5 s — comfortably more
  than the 3 s audio window.
- Audio drives inference at 2 Hz, so extra visual frames are discarded anyway.
- `detectForVideo` is the expensive call; running it at 60 Hz would burn battery
  and main-thread time for no accuracy gain.

Measured throughput is surfaced in the UI as an `N fps` chip, so a browser that
cannot keep up is visible rather than silently degrading.

---

## Where normalisation happens, and why

**The client sends raw coordinates. The server normalises.** This is the single
most important decision in this pipeline.

The training path normalises each frame by subtracting the centroid and dividing
by the maximum radius ([features.md](../features.md#facial-landmarks)). The
obvious implementation would repeat that in JavaScript — and it would work, until
someone changed the epsilon, or the axis of the mean, or the norm order on one
side only. That is textbook train/serve skew: two implementations that agree
today and drift silently later, producing a model that degrades for reasons
nobody can locate.

So `normalize_landmarks` was extracted as a shared function and is called by
both [`extract_visual_features`](../../src/features.py) (offline) and
[`VisualStreamBuffer.push`](../../backend/stream.py) (live). There is exactly one
implementation, in Python, and the browser does no maths at all beyond flattening
an array.

Four tests pin its invariants — translation invariance, scale invariance, output
width, and NaN-freedom on a degenerate all-identical frame.

---

## Status reporting

`useFaceTracking` exposes a status the UI maps to a traffic light:

| status | meaning | dot |
|---|---|---|
| `idle` | camera off | grey |
| `loading` | fetching WASM + model | amber, blinking |
| `tracking` | face detected and streaming | green |
| `no-face` | camera live, no face in frame | amber |
| `error` | permission denied, no camera | red |
| `unsupported` | model or WASM failed to load | red |

`no-face` is distinct from `error` on purpose: the camera is working and the user
simply moved out of frame, which is recoverable and self-explanatory.

The UI additionally states, in words, when a fusion model is streaming **without**
a live visual contribution:

> Predictions are audio-only — the server did not enable the visual stream.

and the status bar shows the actual modality list from each prediction
(`audio` or `audio + visual`), highlighted green when both fired. That honesty is
the whole point of the `modalities` / `visual_active` fields — see
[backend/api-reference.md](../backend/api-reference.md#post-predictaudio).

---

## Teardown

```javascript
const _cleanup = () => {
  runningRef.current = false;
  if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
  streamRef.current?.getTracks().forEach((t) => t.stop());   // camera light OFF
  streamRef.current = null;
  if (videoRef.current) { videoRef.current.pause(); videoRef.current.srcObject = null; }
  onFrameRef.current = null;
};
```

Order: stop the loop, then release the camera, then detach the element. Stopping
the tracks is what turns off the camera indicator light — the most user-visible
cleanup obligation there is.

**The FaceLandmarker is deliberately retained** across start/stop. It holds no
per-session state and reloading 34 MB of WASM per toggle would make the switch
feel broken.

`App.jsx` also stops face tracking whenever the audio stream leaves `streaming`,
so a socket error or a backend restart releases the camera rather than leaving it
lit with nowhere to send frames.

---

## Troubleshooting

### "Face model not found. Run npm run setup:mediapipe"

`face_landmarker.task` is missing from `public/mediapipe/models/`. The setup
script's download failed — most likely no network at install time. Re-run
`npm run setup:mediapipe`, or fetch the file manually.

### Camera permission denied

Same secure-context rule as the microphone: `https://` or `http://localhost`.
Over plain HTTP to a LAN IP, `navigator.mediaDevices` is undefined.

### Status stays on `loading`

The WASM fetch is stalling. Check the Network tab for
`/mediapipe/wasm/vision_wasm_internal.wasm` — a 404 means the assets were not
copied into `public/`; run the setup script. Note the first load genuinely
transfers ~11 MB, so it is slow once and cached after.

### Status is `tracking` but predictions stay `audio`

The server declined the visual stream. Check the `ready` payload:

- `multimodal_model: false` — the loaded checkpoint is unimodal. Vision cannot
  contribute to an audio-only architecture; load a fusion checkpoint.
- `visual_enabled: false` with `multimodal_model: true` — the handshake did not
  request it, or `tagged_binary` was not set.

### Predictions flip between `audio` and `audio + visual`

The face track is going stale between windows — `stale_after` defaults to 2 s and
the client is not sustaining 10 fps. Check the fps chip. Note that server-side
compute no longer causes this: the visual window is sampled at window-close time,
before resampling and inference, specifically so a slow forward pass cannot age a
live track. That was a real bug; see
[testing.md](../testing.md) for the regression test.

### Camera light stays on after stopping

`getTracks().forEach(t => t.stop())` did not run. Note there is still no unmount
cleanup on `useFaceTracking`, so unmounting the component mid-track leaks the
camera — harmless in this single-screen app, a bug the moment a router appears.
