# State management

All streaming state lives in one custom hook. No Redux, no Zustand, no Context.
[`useStream.js`](../../frontend/src/hooks/useStream.js) · 126 lines

- [The hook's contract](#the-hooks-contract)
- [State versus refs](#state-versus-refs)
- [The status state machine](#the-status-state-machine)
- [start()](#start)
- [Message handling](#message-handling)
- [stop() and reset()](#stop-and-reset)
- [Cleanup](#cleanup)
- [History management](#history-management)
- [App-level state](#app-level-state)
- [Known bugs](#known-bugs)
- [Why no state library](#why-no-state-library)

---

## The hook's contract

```javascript
const { status, prediction, history, error, start, stop, reset } = useStream();
```

| Returned | Type | Meaning |
|---|---|---|
| `status` | `'idle' \| 'connecting' \| 'streaming' \| 'error'` | Stream lifecycle |
| `prediction` | `object \| null` | Most recent live prediction |
| `history` | `array` | Predictions with an added `ts`, capped at 60 |
| `error` | `string \| null` | Human-readable error message |
| `start` | `() => Promise<void>` | Request mic, connect, begin streaming |
| `stop` | `() => void` | Tear down everything, return to idle |
| `reset` | `() => void` | Clear prediction, history, and error — does not stop the stream |

One hook encapsulates the microphone, the audio graph, the WebSocket, and all derived UI state. `App.jsx`
consumes it and passes values down as props; no component below `App` knows a WebSocket exists.

---

## State versus refs

The split is the most important design decision in the hook.

**`useState` — values that drive rendering:**

```javascript
const [status,     setStatus]     = useState('idle');
const [prediction, setPrediction] = useState(null);
const [history,    setHistory]    = useState([]);
const [error,      setError]      = useState(null);
```

**`useRef` — mutable objects that must survive re-renders without triggering them:**

```javascript
const wsRef      = useRef(null);   // WebSocket
const ctxRef     = useRef(null);   // AudioContext
const workletRef = useRef(null);   // AudioWorkletNode | ScriptProcessorNode
const streamRef  = useRef(null);   // MediaStream
```

Refs are correct for all four because:

- **They are not rendered.** Nothing displays the `AudioContext`; putting it in state would trigger a
  pointless re-render on assignment.
- **They must be reachable from `_cleanup`.** Teardown needs the *current* objects. A state variable
  captured in a closure would be stale; `ref.current` always reads the latest value.
- **Assigning must not re-render.** A re-render during audio setup would be at best wasted work.

`workletRef` holds either an `AudioWorkletNode` or a `ScriptProcessorNode` depending on which path ran,
which is why `_cleanup` wraps `.port.close()` in a `try/catch` — only one of the two has a `.port`.

---

## The status state machine

```
                 start()
    ┌──────────┐ ──────▶ ┌──────────────┐
    │   idle   │         │  connecting  │
    └──────────┘         └──────────────┘
         ▲                  │        │
         │                  │ ready  │ getUserMedia throws
         │ stop()           ▼        │ or ws.onerror
         │            ┌───────────┐  │
         └────────────│ streaming │  │
                      └───────────┘  ▼
                            │   ┌─────────┐
                            └──▶│  error  │
                       ws.onerror└─────────┘
                                     │ start()
                                     ▼
                                (connecting)
```

| Transition | Trigger |
|---|---|
| `idle` → `connecting` | `start()` called |
| `connecting` → `streaming` | Server sends `ready` **and** the audio graph connects |
| `connecting` → `error` | `getUserMedia` rejects, or `ws.onerror` fires |
| `streaming` → `error` | `ws.onerror` fires |
| `streaming` → `idle` | `stop()` called |
| `error` → `connecting` | `start()` called again |

`connecting` → `streaming` happens **after** the audio graph is wired, not when the socket opens:

```javascript
if (msg.type === 'ready') {
  await ctx.audioWorklet.addModule('/worklets/pcm-processor.js');
  // … connect source → worklet
  setStatus('streaming');
  return;
}
```

So `'streaming'` accurately means "audio is flowing", and the UI's red pulsing mic button never lies. If it
said `'streaming'` on socket open, there would be a window where the button claimed to be recording while
no audio was being captured.

Note that `error` is not a terminal state — `start()` from `error` is the retry path, and the mic button
remains clickable because `disabled={busy && !isStreaming}` only disables while `connecting` or
`uploading`.

---

## start()

```javascript
const start = useCallback(async () => {
  setStatus('connecting');
  setError(null);

  try {
    const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: {…} });
    streamRef.current = mediaStream;

    const ctx = new AudioContext({ sampleRate: 16000 });
    ctxRef.current = ctx;

    const ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen    = () => ws.send(JSON.stringify({ sample_rate: 16000 }));
    ws.onmessage = async (evt) => { /* see below */ };
    ws.onerror   = () => { setError('Cannot reach backend. Is it running on port 8000?'); setStatus('error'); _cleanup(); };
    ws.onclose   = () => { if (status !== 'error') setStatus('idle'); };

  } catch (e) {
    setError(e.message);
    setStatus('error');
    _cleanup();
  }
}, []);   // eslint-disable-line react-hooks/exhaustive-deps
```

Ordering is deliberate: **microphone permission first**, then the audio context, then the socket. If the
user denies the mic, no socket is ever opened — no pointless connection to tear down.

`setError(null)` at the top clears a previous failure, so retrying does not leave a stale banner.

The `catch` covers `getUserMedia` rejection (permission denied, no device, insecure context) and
`AudioContext` construction failure, and always calls `_cleanup()` — so a partially constructed pipeline
never leaks. Note it does *not* cover the async `onmessage` handler, where `addModule` failures are handled
by their own inner try/catch.

`useCallback(…, [])` with the exhaustive-deps rule disabled gives a stable function identity, which is what
lets `App` pass it as a prop without re-triggering effects. It is also the source of the
[stale-closure bug](#the-stale-status-closure) below.

---

## Message handling

```javascript
ws.onmessage = async (evt) => {
  const msg = JSON.parse(evt.data);

  if (msg.type === 'ready') {
    try {
      await ctx.audioWorklet.addModule('/worklets/pcm-processor.js');
      const source  = ctx.createMediaStreamSource(mediaStream);
      const worklet = new AudioWorkletNode(ctx, 'pcm-processor');
      workletRef.current = worklet;
      worklet.port.onmessage = (e) => {
        if (ws.readyState === WebSocket.OPEN) ws.send(e.data);
      };
      source.connect(worklet);
    } catch {
      // ScriptProcessorNode fallback — see audio-pipeline.md
    }
    setStatus('streaming');
    return;
  }

  if (msg.type === 'prediction') {
    const p = msg.payload;
    setPrediction(p);
    setHistory(prev => [...prev.slice(-59), { ...p, ts: Date.now() }]);
    return;
  }

  if (msg.type === 'error') {
    setError(msg.payload.message);
  }
};
```

Three of the server's four message types are handled. `info` — the acknowledgement for `reset` and `ping` —
falls through and is ignored, which is fine since neither needs a UI response.

Two things worth noting:

**An `error` frame sets `error` but does not change `status`.** So a mid-stream inference failure shows the
banner while the mic keeps recording — correct, because the server keeps the connection open for recoverable
errors and the next window may well succeed. Tearing down the stream on a single bad window would make the
demo unusable.

**The handler is `async`** solely for `await addModule`. WebSocket message handlers do not await each other,
so a burst of messages could theoretically interleave — but only the `ready` branch awaits, and `ready`
arrives exactly once, before any prediction. Safe in practice.

---

## stop() and reset()

```javascript
const stop = useCallback(() => {
  _cleanup();
  setStatus('idle');
}, []);

const reset = useCallback(() => {
  setHistory([]);
  setPrediction(null);
  setError(null);
}, []);
```

Two different operations, deliberately separated:

| | `stop()` | `reset()` |
|---|---|---|
| Releases the microphone | Yes | No |
| Closes the WebSocket | Yes | No |
| Clears history | No | Yes |
| Clears current prediction | No | Yes |
| Status after | `idle` | unchanged |

`stop()` deliberately **preserves** history and the last prediction, so the user can review what was
detected after stopping. `reset()` clears the display without interrupting an active stream — wired to the
Timeline's "Clear" button.

Note that `reset()` clears only client-side state; it does **not** send the server's
`{"type": "reset"}` control frame, so the server's `AudioStreamBuffer` keeps its accumulated audio and the
next prediction still reflects a window that spans the "cleared" moment. Sending the control frame too
would make the reset genuinely complete:

```javascript
const reset = useCallback(() => {
  wsRef.current?.send(JSON.stringify({ type: 'reset' }));   // ← not done
  setHistory([]); setPrediction(null); setError(null);
}, []);
```

---

## Cleanup

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

Called from three places — `stop()`, `ws.onerror`, and `start()`'s `catch` — so every failure path releases
the microphone.

Ordering: stop producing before stopping consuming. Worklet, then context, then media stream, then socket.

**Step 3 is the one users notice.** `streamRef.current.getTracks().forEach(t => t.stop())` is what turns off
the browser's recording indicator. Closing the `AudioContext` alone leaves the tracks live and the indicator
lit, which reads as spyware.

Optional chaining plus `try/catch` on the worklet calls handles three cases: the fallback
`ScriptProcessorNode` has no `.port`; `getUserMedia` may have thrown before any node was created; and a node
may already be disconnected. Cleanup must never throw part-way and skip the remaining steps — hence the
swallowed errors.

`readyState < 2` skips `CLOSING` (2) and `CLOSED` (3), avoiding a redundant `close()`.

Every ref is nulled, so a subsequent `_cleanup()` is a no-op rather than operating on dead objects.

---

## History management

```javascript
setHistory(prev => [...prev.slice(-59), { ...p, ts: Date.now() }]);
```

Three things in one line:

- **Functional update.** `prev =>` reads the current value rather than a closed-over one, which is essential
  since this runs inside a WebSocket callback created once at `start()` and never recreated. Using
  `setHistory([...history, …])` would append to the first render's empty array forever.
- **Cap at 60.** `slice(-59)` keeps the last 59 and appends one. At 2 predictions per second that is a
  30-second window — enough to see a trend, bounded so a long session does not grow the array without limit.
- **Timestamp added.** `ts: Date.now()` is stored on each entry. Currently unused for rendering (`Timeline`
  keys by array index), but available — and it would make a better React key. See
  [components.md](components.md#chip-rendering).

`{ ...p, ts }` copies the payload rather than mutating it, keeping the entries immutable.

---

## App-level state

Not everything lives in the hook. `App.jsx` owns three pieces:

| State | Why not in the hook |
|---|---|
| `health` | Concerns the backend, not the stream. Polls whether or not a stream is active |
| `filePrediction` | The upload path is independent of streaming — different transport, different lifecycle |
| `uploading` | Belongs with `filePrediction` |

The division is clean: `useStream` owns *the stream*, `App` owns *everything else*. Health polling in
particular must work when no stream exists, which is exactly when you most want to know the backend's
state.

The two prediction sources converge with a precedence rule:

```javascript
const activePrediction = prediction ?? filePrediction;
```

Live wins. `filePrediction` is never cleared when streaming starts, so stopping a stream reveals the earlier
file result — defensible, mildly surprising.

---

## Known bugs

### The stale `status` closure

```javascript
ws.onclose = () => {
  if (status !== 'error') setStatus('idle');
};
```

`start` is `useCallback(…, [])`, so every closure created inside it captures `status` **from the render in
which `start` was created** — the first render, where `status` is `'idle'`. That value never updates,
because the callback is never recreated.

So `status !== 'error'` is evaluated as `'idle' !== 'error'`, which is always `true`. The guard never fires.

The consequence: when a connection errors, `ws.onerror` sets `status` to `'error'`, then the socket closes
and `ws.onclose` overwrites it back to `'idle'`. The user sees the error banner — which is separate state and
survives — but the mic button returns to its idle appearance rather than showing an error state. Confusing
rather than broken, and the retry path still works.

Two fixes. A ref mirroring the state:

```javascript
const statusRef = useRef('idle');
const setStatusBoth = (s) => { statusRef.current = s; setStatus(s); };
// …
ws.onclose = () => { if (statusRef.current !== 'error') setStatusBoth('idle'); };
```

Or a functional update, which reads the current value without needing a ref:

```javascript
ws.onclose = () => setStatus(prev => (prev === 'error' ? prev : 'idle'));
```

The second is cleaner. Note that `setHistory` already uses the functional form correctly — the same
technique, applied inconsistently.

The `// eslint-disable-line react-hooks/exhaustive-deps` on the `useCallback` is what allowed this through.
The lint rule was reporting a real problem.

### No unmount cleanup

```javascript
// missing from useStream:
useEffect(() => () => _cleanup(), []);
```

If the component unmounts while streaming, the `AudioContext`, `MediaStream`, and WebSocket all leak — and
the browser's recording indicator stays lit until the tab closes.

Invisible in this app, which is a single screen that never unmounts. It would become a real bug the moment a
router, a modal, or conditional rendering is introduced. Adding the effect is one line and costs nothing.

### `reset()` does not reset the server

Covered [above](#stop-and-reset). The server's `AudioStreamBuffer` retains its audio, so the next prediction
still covers a window spanning the moment the user pressed "Clear".

### `inputRef` is unused

`AudioCapture` declares `const inputRef = useRef(null)` and never uses it — leftover from an implementation
that presumably forwarded clicks to the hidden file input before the `<label>` wrapper made that
unnecessary. Harmless dead code.

### `API_URL` is duplicated

Both `App.jsx` and `useStream.js` read `import.meta.env.VITE_API_URL` independently rather than sharing a
constant. Harmless; belongs in `constants.js`.

---

## Why no state library

The app has exactly one non-trivial stateful concern — the audio stream — and it is fully encapsulated in
one hook. Introducing Redux, Zustand, or Context would add:

- A store, actions or setters, and a provider
- Indirection between "a prediction arrived" and "the UI updated"
- A second place to look for state, alongside the hook

for benefits that do not apply here:

| Store benefit | Applicability |
|---|---|
| Sharing state across distant components | The tree is 2 levels deep; prop drilling never exceeds one hop |
| Time-travel debugging | Predictions arrive twice a second and are not user actions to replay |
| Middleware / side-effect management | The side effects are Web Audio and WebSocket lifecycle — imperative by nature, and refs handle them better than any middleware |
| Persistence | Nothing needs to survive a reload |

The hook pattern also keeps the imperative Web Audio and WebSocket APIs where they belong: behind a
declarative interface, with refs for the mutable objects and state for what renders. That boundary is the
actual design work; a store would sit on top of it without removing any of it.

If the app grew a second screen, a settings panel, or multiple concurrent streams, the calculation would
change — and the natural next step would be Context around this same hook, not a rewrite.
