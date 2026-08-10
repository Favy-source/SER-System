# Audio capture pipeline

How microphone audio becomes float32 bytes on a WebSocket. Implemented in
[`useStream.js`](../../frontend/src/hooks/useStream.js) and
[`pcm-processor.js`](../../frontend/public/worklets/pcm-processor.js).

- [The chain](#the-chain)
- [Step 1 — getUserMedia](#step-1--getusermedia)
- [Step 2 — AudioContext](#step-2--audiocontext)
- [Step 3 — WebSocket and handshake](#step-3--websocket-and-handshake)
- [Step 4 — the AudioWorklet](#step-4--the-audioworklet)
- [Step 5 — sending](#step-5--sending)
- [The ScriptProcessorNode fallback](#the-scriptprocessornode-fallback)
- [Why raw PCM](#why-raw-pcm)
- [Latency budget](#latency-budget)
- [Teardown](#teardown)
- [Troubleshooting](#troubleshooting)

---

## The chain

```
navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })
        │
        ▼
  MediaStream
        │
        ▼
  AudioContext({ sampleRate: 16000 })
        │
        ├─ createMediaStreamSource(mediaStream)   →  MediaStreamAudioSourceNode
        │           │
        │           ▼
        └─ AudioWorkletNode('pcm-processor')      →  taps each 128-sample render quantum
                    │
                    │  port.postMessage(buffer, [buffer])   ← ownership transfer, zero-copy
                    ▼
              main thread
                    │
                    ▼
          ws.send(ArrayBuffer)                    →  binary frame, raw float32 PCM
                    │
                    ▼
              backend AudioStreamBuffer           →  accumulate · window · resample · predict
```

The client does no buffering, no windowing, and no encoding. It taps the audio graph and forwards blocks
as they arrive, roughly 125 times per second. All timing lives on the server — see
[backend/websocket-protocol.md](../backend/websocket-protocol.md#timing-and-buffering).

---

## Step 1 — getUserMedia

```javascript
const mediaStream = await navigator.mediaDevices.getUserMedia({
  audio: {
    sampleRate:       16000,
    channelCount:     1,
    echoCancellation: true,
    noiseSuppression: true,
  },
});
```

| Constraint | Reason |
|---|---|
| `sampleRate: 16000` | Common hardware-native rate; half the bandwidth of 32 kHz. The server resamples to the model's 22.05 kHz |
| `channelCount: 1` | The model is mono. Requesting one channel avoids a client-side downmix |
| `echoCancellation: true` | Suppresses speaker bleed — important because the `ScriptProcessorNode` fallback routes mic to speakers |
| `noiseSuppression: true` | Removes steady background noise |

**These are requests, not guarantees.** `getUserMedia` constraints without `exact:` are advisory; a device
that cannot deliver 16 kHz mono will return something else and the promise still resolves. The code does
not verify what it got:

```javascript
// not done, but worth doing:
const settings = mediaStream.getAudioTracks()[0].getSettings();
console.log(settings.sampleRate, settings.channelCount);
```

In practice the `AudioContext` rate (next step) is what determines the samples the worklet sees, and the
browser resamples the track into the context — so a mismatch here is absorbed rather than corrupting the
stream. But the handshake declares 16000 unconditionally, so if the context could not be created at 16 kHz
the server would be told the wrong rate. See [Troubleshooting](#troubleshooting).

**`noiseSuppression` is a research caveat, not just a convenience.** It is a proprietary, non-linear,
undocumented transform applied before the model sees the audio — and it was not applied to the studio
corpora the model was trained on. It changes the spectral character of the input in ways that could
plausibly affect emotion-relevant features (breathiness, low-level tremor). For a demo it improves the
experience; for anything being measured, it is an uncontrolled variable that should be disabled.

### Secure context requirement

`getUserMedia` is only available in a secure context: `https://`, or `http://localhost` (which browsers
treat as secure). Over plain HTTP to a LAN IP, `navigator.mediaDevices` is `undefined` and the call throws
`TypeError`. This is the single most common deployment surprise — see
[backend/deployment.md](../backend/deployment.md#serving-the-front-end).

---

## Step 2 — AudioContext

```javascript
const ctx = new AudioContext({ sampleRate: 16000 });
```

Creating the context at 16 kHz means the whole graph — including what the worklet receives — runs at that
rate, so no client-side resampling occurs. If the hardware runs at 48 kHz, the browser resamples the
microphone track into the context, using a well-implemented resampler.

Requesting a specific `sampleRate` is supported in current Chrome, Firefox, and Safari. Where it is not
honoured, the context falls back to the hardware rate and the audio the server receives will not match the
declared 16000 — producing pitch- and duration-distorted windows with no error anywhere. Reading
`ctx.sampleRate` after construction and sending *that* in the handshake would make the pipeline robust:

```javascript
const ctx = new AudioContext({ sampleRate: 16000 });
ws.onopen = () => ws.send(JSON.stringify({ sample_rate: ctx.sampleRate }));   // ← not what the code does
```

An `AudioContext` may start in a `suspended` state if created without a user gesture. Here it is created
inside the mic button's click handler, so autoplay policy is satisfied and no `ctx.resume()` is needed.

---

## Step 3 — WebSocket and handshake

```javascript
const ws = new WebSocket(WS_URL);
ws.binaryType = 'arraybuffer';
ws.onopen = () => ws.send(JSON.stringify({ sample_rate: 16000 }));
```

`binaryType = 'arraybuffer'` matters. The default is `'blob'`, and a `Blob` requires an async read before
its bytes are accessible — pointless overhead for data the code already holds as an `ArrayBuffer`. It only
affects *received* binary, and this server sends only text, so it is defensive rather than necessary. Still
correct to set.

**Audio capture does not begin until the server acknowledges the handshake.** The `AudioWorklet` is created
inside the `ready` branch of `onmessage`:

```javascript
ws.onmessage = async (evt) => {
  const msg = JSON.parse(evt.data);
  if (msg.type === 'ready') {
    // ← only now start capturing
    await ctx.audioWorklet.addModule('/worklets/pcm-processor.js');
    …
    setStatus('streaming');
    return;
  }
  …
};
```

This is the correct sequencing. The server constructs its `AudioStreamBuffer` from the handshake, so bytes
arriving before `ready` would be consumed by the blocking `receive_text()` as the handshake itself, fail
JSON parsing, and land in the server's silent 16000 fallback.

`status` becomes `'streaming'` only after the graph is connected, so the UI's red pulsing mic button
accurately means "audio is flowing".

The WebSocket URL is derived from the API URL by protocol substitution:

```javascript
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/stream';
```

Anchored at the start, so `https://…` → `wss://…` correctly.

---

## Step 4 — the AudioWorklet

[`public/worklets/pcm-processor.js`](../../frontend/public/worklets/pcm-processor.js) — 15 lines, and every
one of them matters:

```javascript
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) {
      const copy = new Float32Array(channel);
      this.port.postMessage(copy.buffer, [copy.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
```

### Why it runs on a separate thread

`AudioWorkletProcessor` executes on the browser's dedicated audio rendering thread, isolated from the main
thread. React re-renders, layout, garbage collection, and JavaScript execution on the main thread cannot
delay it. Audio capture that glitches when the UI is busy is exactly the failure the AudioWorklet API
exists to eliminate — and it is why the deprecated `ScriptProcessorNode` (which runs on the main thread) is
only a fallback.

### Why the copy is mandatory

```javascript
const copy = new Float32Array(channel);
```

`inputs[0][0]` is a `Float32Array` that Web Audio **reuses on the next render quantum**. Transferring it
directly would hand ownership away, leaving the audio graph with a detached buffer — corrupting subsequent
audio or throwing. Copying is 128 floats, 512 bytes, roughly free.

### Why the transfer list

```javascript
this.port.postMessage(copy.buffer, [copy.buffer]);
```

The second argument is a transfer list. Without it, `postMessage` **structured-clones** the buffer —
allocating and copying 512 bytes on both sides, 125 times per second. With it, ownership moves to the main
thread with no copy at all; the worklet's reference becomes detached, which is fine since a fresh copy is
made each call.

At 125 messages per second the saving is small in absolute terms, but it also avoids 125 allocations per
second of garbage-collectable buffers on the audio thread — where a GC pause is precisely what you cannot
afford.

### Why `return true`

Returning `false` tells the browser the processor is finished and it may be garbage-collected. `true` keeps
it alive indefinitely, which is what a continuous tap needs.

### Why it lives in `public/`

`ctx.audioWorklet.addModule('/worklets/pcm-processor.js')` fetches the file **by URL at runtime**. It must
be served verbatim as a static asset, not bundled — Vite copies `public/` to `dist/` unchanged. Putting it
in `src/` would let Vite transform and hash it, and the hard-coded path would 404.

The path is absolute (`/worklets/…`), so deploying the front end under a sub-path (e.g.
`https://example.org/ser/`) would break the fetch. Vite's `import.meta.env.BASE_URL` would make it
relocatable.

### Node graph

```javascript
const source  = ctx.createMediaStreamSource(mediaStream);
const worklet = new AudioWorkletNode(ctx, 'pcm-processor');
worklet.port.onmessage = (e) => { … };
source.connect(worklet);
```

Note the worklet is **not** connected to `ctx.destination`. An `AudioWorkletNode` is pulled by the graph
whether or not its output is connected, so nothing needs to route to the speakers — which is what avoids
feedback. The `ScriptProcessorNode` fallback does not share this property.

---

## Step 5 — sending

```javascript
worklet.port.onmessage = (e) => {
  if (ws.readyState === WebSocket.OPEN) ws.send(e.data);
};
```

`e.data` is the transferred `ArrayBuffer` — raw float32 samples, no header, native byte order. The server
reads it with `np.frombuffer(chunk, dtype=np.float32)`.

The `readyState` guard prevents `InvalidStateError` when a message arrives after the socket has begun
closing. There is a window between the socket closing and the worklet being disconnected during teardown
where this fires.

**No backpressure handling.** If the socket cannot keep up, `ws.bufferedAmount` grows unboundedly and
predictions fall further behind real time with no signal to the user. On a LAN at 64 KB/s this does not
arise; on a constrained mobile link it could. Checking `bufferedAmount` and dropping blocks would be the
mitigation:

```javascript
if (ws.readyState === WebSocket.OPEN && ws.bufferedAmount < 256_000) ws.send(e.data);
```

### Bandwidth

| Quantity | Value |
|---|---|
| Sample rate | 16,000 Hz |
| Bytes per sample | 4 (float32) |
| Upstream | **64 KB/s = 512 kbit/s** |
| Messages per second | ~125 (128-sample render quantum) |
| Bytes per message | 512 |

Int16 would halve the bandwidth at negligible quality cost for speech, but would require a format field in
the handshake and conversion server-side — the protocol currently assumes float32 unconditionally.

---

## The ScriptProcessorNode fallback

```javascript
try {
  await ctx.audioWorklet.addModule('/worklets/pcm-processor.js');
  // … AudioWorkletNode path
} catch {
  const source = ctx.createMediaStreamSource(mediaStream);
  const proc   = ctx.createScriptProcessor(4096, 1, 1);
  workletRef.current = proc;
  proc.onaudioprocess = (e) => {
    if (ws.readyState === WebSocket.OPEN) {
      const pcm = new Float32Array(e.inputBuffer.getChannelData(0));
      ws.send(pcm.buffer);
    }
  };
  source.connect(proc);
  proc.connect(ctx.destination);     // ← required for it to run at all
}
```

| | AudioWorklet | ScriptProcessorNode |
|---|---|---|
| Thread | Audio rendering thread | **Main thread** |
| Block size | 128 samples (~8 ms at 16 kHz) | 4096 samples (~256 ms) |
| Glitches under UI load | No | **Yes** |
| Status | Standard | **Deprecated** |
| Needs a sink connection | No | **Yes** |

Three real problems with the fallback path:

**It runs on the main thread.** React renders, garbage collection, or any long task delays audio callbacks
and drops samples.

**It must connect to `ctx.destination` to execute.** That routes the microphone to the speakers, so without
headphones the user hears themselves and can create feedback — partly mitigated by `echoCancellation`, but
not eliminated. Routing through a zero-gain `GainNode` would fix it:

```javascript
const mute = ctx.createGain();
mute.gain.value = 0;
proc.connect(mute);
mute.connect(ctx.destination);
```

**The bare `catch {}` cannot distinguish two very different failures.** `addModule` throws both when the
API is genuinely absent *and* when the fetch for `pcm-processor.js` fails — a wrong base path, a 404 behind
a proxy, a misconfigured static mount. So a deployment error silently degrades to the deprecated path
instead of reporting a missing asset. Logging inside the catch would surface it:

```javascript
} catch (err) {
  console.warn('AudioWorklet unavailable, falling back to ScriptProcessorNode:', err);
  …
}
```

The 4096-sample block also means the server receives audio in ~256 ms chunks rather than ~8 ms, which
coarsens when window boundaries land — a minor effect given the 0.5 s hop.

---

## Why raw PCM

Alternatives and why they were not used:

| Approach | Why not |
|---|---|
| `MediaRecorder` + Opus/WebM | Encoding adds 20–100 ms latency; the server would need to decode; container framing complicates streaming |
| WAV framing | Pointless — a header per block, for data whose format is already agreed |
| Base64 over text frames | 33% bandwidth overhead plus encode/decode cost, to avoid binary frames the WebSocket supports natively |
| Int16 PCM | Halves bandwidth, but needs a format field and server-side conversion. A reasonable future optimisation |

Raw float32 is what Web Audio produces and what NumPy consumes:

```javascript
worklet.port.postMessage(copy.buffer, [copy.buffer]);   // Float32Array → ArrayBuffer
```
```python
pcm = np.frombuffer(chunk, dtype=np.float32)            # ArrayBuffer → np.float32
```

Zero conversion on either side. The cost is 64 KB/s upstream and no format validation — sending int16
would be silently reinterpreted as float32 garbage, with no error anywhere. See
[websocket-protocol.md](../backend/websocket-protocol.md#audio-frames).

---

## Latency budget

From spoken word to displayed prediction:

| Stage | Approximate |
|---|---|
| Microphone hardware + OS buffer | 10–30 ms |
| `getUserMedia` → AudioContext | ~10 ms |
| AudioWorklet render quantum | ~8 ms (128 samples @ 16 kHz) |
| `postMessage` to main thread | <1 ms |
| WebSocket transmission (LAN) | 1–5 ms |
| **Server-side window wait** | **up to 500 ms** (hop gate) |
| Resampling 16 k → 22.05 k | ~1–3 ms |
| Feature extraction | 10–40 ms (CPU, the dominant compute cost) |
| Model forward pass | 4–15 ms |
| Response + React render | ~5 ms |
| **Total** | **~40 ms compute + up to 500 ms hop** |

**The hop gate dominates everything else.** Compute is tens of milliseconds; the wait for the next
inference slot is up to 500 ms. Reducing `hop_sec` is therefore the single most effective latency lever —
and it is a server-side change, not a client one.

There is a second, larger latency the table does not show: the model classifies a **3-second window**, so a
prediction always describes the last 3 seconds rather than the present instant. Emotion that began 200 ms
ago is diluted by 2.8 seconds of prior audio. That is inherent to the fixed-window design, and shortening
`duration` (with retraining) is the only way to reduce it.

---

## Teardown

```javascript
const _cleanup = () => {
  try { workletRef.current?.port.close(); } catch {}
  try { workletRef.current?.disconnect(); } catch {}
  workletRef.current = null;

  ctxRef.current?.close();
  ctxRef.current = null;

  streamRef.current?.getTracks().forEach(t => t.stop());
  streamRef.current = null;

  if (wsRef.current && wsRef.current.readyState < 2) {
    wsRef.current.close();
  }
  wsRef.current = null;
};
```

Order matters — stop producing before stopping consuming:

1. **Close the worklet port and disconnect the node** — stops messages reaching the main thread.
2. **Close the AudioContext** — releases the audio device and the rendering thread.
3. **Stop the MediaStream tracks** — **this is what turns off the browser's recording indicator.** Users
   notice a microphone that stays on; forgetting this is the most user-visible cleanup bug possible.
4. **Close the WebSocket** if not already closing (`readyState < 2` excludes CLOSING and CLOSED).

The `try/catch` wrappers around the worklet calls handle the `ScriptProcessorNode` fallback, which has no
`.port`, and the case where the node was never created because `getUserMedia` threw first. Swallowing the
errors is right — cleanup must never throw and prevent later steps from running.

`_cleanup` is called from three places: `stop()`, the `ws.onerror` handler, and the `catch` in `start()`.
Every failure path releases the microphone.

**There is no unmount cleanup.** `useStream` has no `useEffect(() => () => _cleanup(), [])`, so unmounting
the component mid-stream leaks the audio context, the media stream, and the socket — leaving the recording
indicator lit. In a single-screen app that never unmounts this is invisible; it would matter the moment a
router is added. See
[state-management.md](state-management.md#no-unmount-cleanup).

---

## Troubleshooting

### `TypeError: Cannot read properties of undefined (reading 'getUserMedia')`

Not a secure context. `navigator.mediaDevices` is undefined over plain HTTP on a non-localhost host. Use
`localhost` or serve over HTTPS.

### `NotAllowedError: Permission denied`

The user declined the microphone prompt, or the browser has a stored denial for the origin. Reset it in the
site settings (the padlock icon in the address bar).

### `NotFoundError` / `NotReadableError`

No microphone available, or another application holds exclusive access. Check OS-level input settings.

### Audio flows but predictions are nonsense

Most likely a sample-rate mismatch. The handshake hard-codes 16000, so if the `AudioContext` could not be
created at that rate the server is being told the wrong number and resampling with wrong parameters. Check:

```javascript
console.log('context rate:', ctx.sampleRate);
console.log('track settings:', mediaStream.getAudioTracks()[0].getSettings());
```

and compare against the `sample_rate` echoed in the server's `ready` payload.

### The recording indicator stays on after stopping

`streamRef.current.getTracks().forEach(t => t.stop())` did not run. Either `_cleanup` was not called, or
`streamRef` was already null. Check that `stop()` is reached — and note that unmounting the component does
not trigger cleanup at all.

### Falls back to `ScriptProcessorNode` on a modern browser

`addModule` failed to *fetch* `/worklets/pcm-processor.js`, not because the API is missing. Check the
Network tab for a 404. Common when deploying under a sub-path, since the worklet path is absolute. Add a
`console.warn` in the catch to see the real error.

### Audio glitches or drops out

If you are on the `ScriptProcessorNode` path, it runs on the main thread and is sensitive to UI load — fix
the worklet fetch. On the AudioWorklet path, check `ws.bufferedAmount`; if it is growing, the network cannot
keep up with 64 KB/s and there is no backpressure handling.

### Hearing yourself through the speakers

You are on the `ScriptProcessorNode` fallback, which connects to `ctx.destination` to run. Use headphones,
or fix the worklet fetch so the fallback is not used.
