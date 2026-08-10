# Components

Every component's props, state, and rendering logic. All are function components; none use
`React.memo`, `useMemo`, or `useReducer` — the tree is shallow enough that re-rendering it twice a second
costs nothing measurable.

- [App](#app)
- [Header](#header)
- [AudioCapture](#audiocapture)
- [EmotionDisplay](#emotiondisplay)
- [ProbabilityBars](#probabilitybars)
- [Timeline](#timeline)
- [constants.js](#constantsjs)
- [Composition notes](#composition-notes)

---

## App

[`src/App.jsx`](../../frontend/src/App.jsx) · 102 lines · the only stateful component besides the hook

Owns layout, backend health polling, file upload, and the precedence rule between live and file
predictions.

### State

| State | Type | Purpose |
|---|---|---|
| `health` | `object \| null` | Latest `/health` response, or `{status:'offline', model_loaded:false}` on fetch failure |
| `filePrediction` | `object \| null` | Result of the most recent file upload |
| `uploading` | `bool` | Upload in flight — disables the drop zone |

Plus everything from `useStream()`: `status`, `prediction`, `history`, `error`, `start`, `stop`, `reset`.

### Health polling

```javascript
useEffect(() => {
  const check = () =>
    fetch(`${API_URL}/health`)
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'offline', model_loaded: false }));
  check();
  const id = setInterval(check, 10_000);
  return () => clearInterval(id);
}, []);
```

Runs immediately, then every 10 seconds, with the interval cleared on unmount. The `catch` maps a network
failure to a synthetic offline object rather than leaving `health` null, so `Header` can distinguish three
states: not yet checked (`null` → amber "Checking…"), reachable but model-less (red "No model loaded"),
and reachable with a model (green, model name).

10 seconds is a reasonable compromise — fast enough to notice a backend restart, slow enough not to spam
the log. It runs regardless of whether a stream is active, which is deliberate: the health signal matters
most when nothing is streaming.

### File upload

```javascript
const handleFile = async (file) => {
  if (!file) return;
  setUploading(true);
  setFilePrediction(null);
  const form = new FormData();
  form.append('file', file);
  try {
    const res  = await fetch(`${API_URL}/predict/audio`, { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail ?? 'Upload failed');
    setFilePrediction(data);
  } catch (e) {
    setFilePrediction(null);
    // surface as a transient alert rather than breaking the whole UI
    console.error(e);
  }
  setUploading(false);
};
```

`if (!res.ok) throw` is the important line — `fetch` resolves successfully for 4xx and 5xx responses, so
without it a 503 body would be stored as if it were a prediction and `EmotionDisplay` would render
`undefined`. The thrown message prefers the API's `detail` field, which carries the real reason ("Model
not loaded", "Could not process audio: …").

**The error path is console-only.** The comment describes surfacing a transient alert; the code logs and
clears. A failed upload looks to the user like nothing happened. Routing `e.message` into the existing
`error-banner` would close the gap:

```javascript
} catch (e) {
  setFilePrediction(null);
  setUploadError(e.message);        // and render it
}
```

`setUploading(false)` sits outside the try/catch rather than in a `finally`, which works here because the
catch does not rethrow — but a `finally` would be more robust to future edits.

### Prediction precedence

```javascript
const activePrediction = prediction ?? filePrediction;
```

Live predictions win. `??` rather than `||` so a falsy-but-present value would still take precedence —
defensive, since predictions are always objects.

The consequence: `filePrediction` is never cleared when a stream starts, so stopping the stream reveals
the earlier file result. Defensible (the analysis is still valid) but potentially confusing.

### Layout

```jsx
<div className="app">
  <Header health={health} status={status} />
  {error && <div className="error-banner">⚠ {error}</div>}

  <div className="row">
    <div className="card"><AudioCapture … /></div>
    <div className="card"><EmotionDisplay prediction={activePrediction} /></div>
  </div>

  <div className="card"><ProbabilityBars prediction={activePrediction} /></div>
  <div className="card"><Timeline history={history} onReset={reset} /></div>

  {activePrediction && (
    <div className="status-bar">…model, latency, count, device…</div>
  )}
</div>
```

`.row` is a two-column grid that collapses to one column below 600 px. The status bar only appears once a
prediction exists, so the initial layout is not cluttered with placeholder metadata.

Note the status bar renders `activePrediction.model_name` and `latency_ms` from the prediction, but
`health.device` from the health poll — two sources, because the prediction payload does not carry the
device.

---

## Header

[`src/components/Header.jsx`](../../frontend/src/components/Header.jsx) · 28 lines · stateless

### Props

| Prop | Type | Purpose |
|---|---|---|
| `health` | `object \| null` | Latest `/health` response |
| `status` | `string` | Stream status from `useStream` |

### Status derivation

Two parallel ternary chains compute a CSS class and a label from the same precedence order:

```javascript
const dotClass =
  status === 'streaming'  ? 'online'  :
  status === 'connecting' ? 'loading' :
  status === 'error'      ? 'offline' :
  health?.model_loaded    ? 'online'  :
  health                  ? 'offline' : 'loading';

const label =
  status === 'streaming'  ? 'Streaming'   :
  status === 'connecting' ? 'Connecting…' :
  status === 'error'      ? 'Error'       :
  health?.model_loaded    ? health.model_name ?? 'Model ready' :
  health                  ? 'No model loaded' : 'Checking…';
```

**Stream status takes precedence over health status**, which is correct: while streaming, what the user
cares about is the stream, and the 10-second-stale health poll is less relevant.

The three-way distinction at the end is the useful part:

| Condition | Dot | Label |
|---|---|---|
| `health` is `null` | amber, blinking | "Checking…" |
| `health.model_loaded` false | red | "No model loaded" |
| `health.model_loaded` true | green | model name, or "Model ready" |

So "backend unreachable", "backend up but no model", and "ready" are visually distinct — which is exactly
the diagnostic information a developer needs on a fresh clone.

The duplicated ternary chains are a small smell; a single lookup returning `{dotClass, label}` would keep
them in sync by construction.

---

## AudioCapture

[`src/components/AudioCapture.jsx`](../../frontend/src/components/AudioCapture.jsx) · 61 lines

Mic button and drag-and-drop upload zone.

### Props

| Prop | Type | Purpose |
|---|---|---|
| `status` | `string` | Drives button appearance and label |
| `onStart` | `fn` | Begin streaming |
| `onStop` | `fn` | Stop streaming |
| `onFile` | `fn(File)` | Upload handler |
| `uploading` | `bool` | Disables the drop zone |

### Local state

`drag` — whether a drag is currently over the drop zone, for the highlight.

### The mic button

```javascript
const isStreaming  = status === 'streaming';
const isConnecting = status === 'connecting';
const busy = isConnecting || uploading;

<button
  className={`mic-btn ${isStreaming ? 'streaming' : isConnecting ? 'connecting' : ''}`}
  onClick={isStreaming ? onStop : onStart}
  disabled={busy && !isStreaming}
  aria-label={isStreaming ? 'Stop' : 'Record'}
>
  {isConnecting ? '⏳' : isStreaming ? '⏹' : '🎙'}
</button>
```

One button, three visual states, and the handler swaps between start and stop — a toggle rather than two
buttons, which keeps the layout stable.

`disabled={busy && !isStreaming}` is the careful part: the button is disabled while connecting or
uploading, **but never while streaming**. Without the `!isStreaming` guard, a user who started a stream
and then uploaded a file would be unable to stop the stream. Stop must always be reachable.

The CSS gives `.streaming` a red background with a pulsing box-shadow (`mic-pulse`), making it obvious
that the microphone is live.

### The drop zone

```jsx
<label
  className={`drop-zone ${drag ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
  onDragOver={(e)  => { e.preventDefault(); setDrag(true); }}
  onDragLeave={()  => setDrag(false)}
  onDrop={(e)      => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
>
  <input type="file" accept="audio/*" onChange={(e) => handleFile(e.target.files[0])} disabled={uploading} />
  {uploading ? 'Analysing…' : drag ? 'Drop to analyse' : 'Drop audio file or click to browse'}
</label>
```

Using a `<label>` wrapping a hidden `<input type="file">` is the standard pattern for a styled file
picker — clicking anywhere in the label opens the file dialog, with no JavaScript click forwarding
needed. `.drop-zone input { display: none; }` hides the native control.

`e.preventDefault()` on both `dragOver` and `drop` is required; without it the browser navigates to the
dropped file.

Type filtering happens in the handler as well as the input's `accept`:

```javascript
const handleFile = (f) => {
  if (f && f.type.startsWith('audio/')) onFile(f);
};
```

`accept` only filters the file dialog, not drops, so the guard is what actually prevents a dropped PDF
from being uploaded. Note it silently ignores a wrong-type file — no feedback at all. Also, `f.type` is
browser-inferred and can be empty for unusual extensions, so a valid `.flac` may occasionally be rejected.

`inputRef` is declared but never used — leftover from an earlier implementation that presumably forwarded
clicks programmatically.

---

## EmotionDisplay

[`src/components/EmotionDisplay.jsx`](../../frontend/src/components/EmotionDisplay.jsx) · 42 lines

The dominant emotion, large, with confidence and latency chips.

### Props

| Prop | Type |
|---|---|
| `prediction` | `object \| null` |

### Animation re-triggering

```javascript
const emojiRef = useRef(null);
const prevRef  = useRef(null);

useEffect(() => {
  if (!prediction || prediction.emotion === prevRef.current) return;
  prevRef.current = prediction.emotion;
  if (emojiRef.current) {
    emojiRef.current.classList.remove('fresh');
    void emojiRef.current.offsetWidth;   // reflow to restart animation
    emojiRef.current.classList.add('fresh');
  }
}, [prediction?.emotion]);
```

The `void element.offsetWidth` line is the interesting trick. A CSS animation only plays when the class is
added; removing and immediately re-adding it in the same tick has no effect, because the browser batches
style changes and never observes the intermediate state. Reading a layout property (`offsetWidth`) forces
a synchronous reflow, so the removal is committed before the re-add and the animation restarts.

`void` discards the read so linters do not flag it as a useless expression. The `pop` keyframe scales from
0.7 → 1.15 → 1.0 over 250 ms.

`prevRef` guards against re-triggering on every prediction. With a 0.5-second hop, the same emotion arrives
repeatedly; animating each one would be a constant twitch. Only an actual *change* of emotion animates.

Note the effect depends on `prediction?.emotion` rather than `prediction`, so a confidence change with the
same label does not re-run it — correct, and it means the dependency array and the internal guard are
partially redundant.

### Rendering

Null prediction renders a placeholder:

```jsx
<div className="emotion-placeholder">
  Start recording or upload a file<br />to see emotion predictions
</div>
```

Otherwise emoji, the label coloured by emotion, and two chips:

```jsx
<span ref={emojiRef} className="emotion-emoji">{emoji}</span>
<span className="emotion-name" style={{ color }}>{emotion}</span>
<div className="emotion-meta">
  <span className="chip">{(confidence * 100).toFixed(0)}% confidence</span>
  <span className="chip">{latency_ms} ms</span>
</div>
```

Colour and emoji both fall back for unknown labels (`?? '#94a3b8'`, `?? '❓'`), so a taxonomy change on the
backend degrades rather than crashes.

`.emotion-display` has `min-height: 160px`, so the placeholder and a real prediction occupy the same
vertical space and the layout does not jump on the first result.

> **The confidence figure is an uncalibrated softmax output.** "87% confidence" reads as "87% likely
> correct", which it is not — neural networks are typically overconfident. For a clinical context this
> framing is actively misleading. See
> [evaluation.md](../evaluation.md#what-is-not-measured).

---

## ProbabilityBars

[`src/components/ProbabilityBars.jsx`](../../frontend/src/components/ProbabilityBars.jsx) · 33 lines ·
stateless

All six classes as colour-coded horizontal bars.

### Props

| Prop | Type |
|---|---|
| `prediction` | `object \| null` |

### The key decision

```javascript
const probs = prediction?.probabilities ?? {};
const top   = prediction?.emotion;

{EMOTIONS.map((emotion) => {
  const p   = probs[emotion] ?? 0;
  const pct = (p * 100).toFixed(0);
  …
})}
```

**Iteration is over the `EMOTIONS` constant, not the response keys.** Three consequences, all good:

1. **Fixed order.** Bars never reorder, so the eye can track one class over time.
2. **Fixed count.** With no prediction, six bars render at 0% instead of the section collapsing — no
   layout shift when the first result arrives.
3. **Smooth animation.** Because each bar is the same DOM node across renders, the CSS
   `transition: width .35s ease` on `.prob-fill` animates from the old value to the new one. Re-keying by
   response order would remount the nodes and the transition would not fire.

The active class gets emphasis via a CSS class rather than a separate render path:

```jsx
<div className={`prob-row ${emotion === top ? 'active' : ''}`}>
```

`.prob-row.active` brightens the label, raises the fill opacity from 0.7 to 1, and bolds the percentage.

The row is a three-column grid — `68px 1fr 42px` — so labels and percentages align in fixed gutters while
the track flexes. `.prob-pct` uses `font-variant-numeric: tabular-nums`, so the percentage does not jitter
horizontally as digits change width. A small detail that matters a lot when the number updates twice a
second.

---

## Timeline

[`src/components/Timeline.jsx`](../../frontend/src/components/Timeline.jsx) · 52 lines

Horizontally scrolling history of predictions as coloured emoji chips.

### Props

| Prop | Type | Purpose |
|---|---|---|
| `history` | `array` | Prediction objects with an added `ts` timestamp |
| `onReset` | `fn` | Clears history |

### Auto-scroll

```javascript
const scrollRef = useRef(null);
useEffect(() => {
  if (scrollRef.current) {
    scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
  }
}, [history.length]);
```

Scrolls to the far right whenever an entry is added, so the newest prediction is always visible. Keyed on
`history.length` rather than `history`, so it only runs on append.

This forcibly overrides manual scrolling — a user inspecting older chips gets yanked back to the end
twice a second. Checking whether the user is already near the end before scrolling would be the polite
fix.

### Chip rendering

```jsx
<div
  key={i}
  className="tl-chip"
  style={{
    background: EMOTION_COLORS[item.emotion] + '33',
    outline: i === history.length - 1 ? `2px solid ${EMOTION_COLORS[item.emotion]}` : 'none',
  }}
  title={`${item.emotion} — ${(item.confidence * 100).toFixed(0)}%`}
>
  {EMOTION_EMOJIS[item.emotion] ?? '❓'}
</div>
```

`+ '33'` appends alpha to the hex colour — `#fbbf24` becomes `#fbbf2433`, about 20% opacity. A compact way
to get a tinted background from a solid token without a second colour definition, and it works because
every value in `EMOTION_COLORS` is 6-digit hex. It would break silently for an `rgb()` or named colour.

The newest chip gets a solid outline in the full colour, so the current state is identifiable at a glance
within a row of tinted circles. `.tl-chip:last-child` in CSS also raises opacity to 1 and adds a white
outline — so the last chip receives styling from both the inline `outline` and the CSS rule, with the
inline style winning on `outline`.

`title` provides a hover tooltip with the emotion and confidence — the only place confidence is visible
for historical predictions.

**`key={i}` uses the array index.** The history array is append-only until it hits the 60-entry cap, at
which point `prev.slice(-59)` shifts every element down one index. Every chip's key then changes meaning,
so React re-renders all of them rather than just adding one. `item.ts` is already stored on each entry and
would be a stable key.

### Empty state and count

```jsx
{history.length === 0
  ? <div className="timeline-empty">No predictions yet</div>
  : <div className="timeline-scroll" ref={scrollRef}>…</div>}
```

The header shows a count and a "Clear" button, both only when history is non-empty — no disabled button
sitting there doing nothing.

The scroll container styles a thin custom scrollbar for both Firefox (`scrollbar-width`,
`scrollbar-color`) and WebKit (`::-webkit-scrollbar`), and `.timeline-track` uses
`min-width: max-content` so the flex row grows past the container rather than compressing the chips.

---

## constants.js

[`src/constants.js`](../../frontend/src/constants.js) · 19 lines

```javascript
export const EMOTIONS = ['neutral', 'happy', 'sad', 'angry', 'fearful', 'disgust'];

export const EMOTION_COLORS = {
  neutral: '#94a3b8',   // slate  — the neutral token itself
  happy:   '#fbbf24',   // amber  — warm, positive
  sad:     '#60a5fa',   // blue   — the conventional cool/melancholy mapping
  angry:   '#f87171',   // red    — matches the error token
  fearful: '#a78bfa',   // violet — distinct from both red and blue
  disgust: '#34d399',   // green  — matches the success token
};

export const EMOTION_EMOJIS = {
  neutral: '😐', happy: '😊', sad: '😢',
  angry:   '😠', fearful: '😨', disgust: '🤢',
};
```

Three components consume these, so an emotion looks identical everywhere.

**`EMOTIONS` mirrors `UNIFIED` in [`src/datasets.py`](../../src/datasets.py#L9) and must stay in the same
order.** Lookups are by key rather than index, so a mismatch would not break rendering — it would only
change the display order relative to the model's class indices. Still worth keeping aligned: reading a raw
prediction payload against the UI is much easier when they agree. If you change the taxonomy, change both.

The colours are chosen to be distinguishable and to reuse the palette's semantic tokens where the mapping
is natural (`angry` ≈ error red, `disgust` ≈ success green — the latter is a colour coincidence, not a
semantic one). All six are light enough for adequate contrast on the dark surface.

They have **not** been checked for colour-blind distinguishability. Red/green (`angry`/`disgust`) is the
most common confusion pair, and here it is doing real work — an accessibility gap worth addressing, most
cheaply by never relying on colour alone (the emoji and text labels already carry the information, which
mitigates it substantially).

---

## Composition notes

**Props down, callbacks up.** No context, no store. `App` holds or forwards all state; children receive
values and callbacks. With a tree this shallow, prop drilling never exceeds one level.

**Every component tolerates a null prediction.** `EmotionDisplay` renders a placeholder,
`ProbabilityBars` renders zeros, `Timeline` renders an empty state. Nothing crashes before the first
prediction arrives, and nothing needs a loading guard in `App`.

**Presentational components are pure.** Only `App` and `useStream` hold meaningful state; `EmotionDisplay`
and `Timeline` use refs for DOM effects (animation restart, scroll) but derive everything rendered from
props.

**No memoisation anywhere.** No `React.memo`, `useMemo`, or `useCallback` in the components. At two
renders per second over five small components, the entire tree costs well under a millisecond —
memoisation would add complexity for no measurable gain.

**Reserved space prevents layout shift.** `min-height` on `.emotion-display` and `.status-text`, a fixed
six-row `ProbabilityBars`, and a conditional status bar mean the layout does not jump as predictions
arrive.

**Unknown values degrade rather than crash.** `EMOTION_COLORS[x] ?? '#94a3b8'`,
`EMOTION_EMOJIS[x] ?? '❓'`, `probs[e] ?? 0`. If the backend's taxonomy changes, the UI shows a question
mark rather than throwing.
