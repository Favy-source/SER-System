# Styling

One CSS file, 338 lines, no preprocessor and no framework.
[`src/index.css`](../../frontend/src/index.css)

- [Approach](#approach)
- [Design tokens](#design-tokens)
- [Layout system](#layout-system)
- [Component styles](#component-styles)
- [Animations](#animations)
- [Emotion colours](#emotion-colours)
- [Responsive behaviour](#responsive-behaviour)
- [Details worth keeping](#details-worth-keeping)
- [Theming](#theming)
- [Accessibility gaps](#accessibility-gaps)

---

## Approach

Plain CSS with custom properties, organised into commented sections in one file:

```
Design tokens · Reset · Layout · Header · Error banner · AudioCapture ·
EmotionDisplay · ProbabilityBars · Timeline · Status bar · Responsive
```

No Tailwind, no CSS-in-JS, no CSS modules, no Sass. For roughly 340 lines styling five components, the
tooling would cost more than it saves — a build step, a dependency, and a second syntax to read.

Class naming is flat and semantic (`.mic-btn`, `.prob-fill`, `.tl-chip`), with modifier classes
(`.streaming`, `.active`, `.drag-over`) applied conditionally from JSX. No BEM, no nesting deeper than one
level, so specificity never becomes a problem — every rule is a single class or a class pair.

The only inline styles are values that genuinely come from data: emotion colours, bar widths, and the
Timeline's outline. Everything static lives in the stylesheet.

---

## Design tokens

```css
:root {
  --bg-base:     #0f172a;   /* page background — deepest */
  --bg-surface:  #1e293b;   /* cards */
  --bg-elevated: #263348;   /* chips, tracks, buttons */
  --border:      #334155;

  --text-1:      #f1f5f9;   /* primary */
  --text-2:      #94a3b8;   /* secondary */
  --text-3:      #64748b;   /* tertiary / labels */

  --accent:      #38bdf8;   /* sky   — interactive */
  --success:     #34d399;   /* green — online */
  --error:       #f87171;   /* red   — offline, recording */
  --warning:     #fbbf24;   /* amber — connecting */

  --radius:      12px;      /* cards */
  --radius-sm:   6px;       /* inputs, small elements */
}
```

A dark slate palette drawn from the Tailwind scale — `slate-900` through `slate-600` for surfaces,
`slate-100` through `slate-500` for text — but hand-written rather than imported.

Two deliberate structures:

**Three surface levels, three text levels.** `--bg-base` → `--bg-surface` → `--bg-elevated` gives depth
without shadows, which read poorly on dark backgrounds. `--text-1/2/3` gives hierarchy without varying font
size, so labels, values, and metadata are distinguishable at the same scale.

**Semantic status colours, not named ones.** `--success` / `--error` / `--warning` rather than
`--green` / `--red` / `--amber`, so the status dot's meaning is legible in the CSS. `--error` doubles as the
recording indicator, which is intentional — a live microphone warrants the same visual weight as an error
state.

Dark-first is the right default here: the UI is a monitoring display likely to be watched for extended
periods, and the emotion colours read more vividly against dark surfaces.

---

## Layout system

```css
.app {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 16px 40px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
```

A single vertical flex column with `gap: 14px`, so no component carries its own margins — spacing is the
container's responsibility and stays uniform automatically. `.row` nests a two-column grid inside it for the
capture/display pair.

`max-width: 960px` with `margin: 0 auto` centres the app on wide screens. The extra bottom padding (40px
versus 24px top) gives the last card breathing room above the viewport edge.

Cards are `border` + `border-radius`, no `box-shadow`. Shadows are barely visible on a dark background;
a 1px border at `--border` separates surfaces far more cleanly.

---

## Component styles

### Status dot

```css
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-3); flex-shrink: 0; }
.status-dot.online  { background: var(--success); box-shadow: 0 0 6px var(--success); }
.status-dot.offline { background: var(--error); }
.status-dot.loading { background: var(--warning); animation: blink 1s infinite; }
```

Three states, three affordances beyond colour alone: online glows (`box-shadow`), loading blinks, offline is
flat. That redundancy is what makes the states distinguishable without relying purely on hue.

`flex-shrink: 0` stops the dot deforming into an ellipse when the label text is long.

### Mic button

```css
.mic-btn {
  width: 72px; height: 72px; border-radius: 50%;
  border: none; cursor: pointer; font-size: 26px;
  display: flex; align-items: center; justify-content: center;
  transition: transform .15s, box-shadow .2s;
  background: var(--bg-elevated);
}
.mic-btn:hover:not(:disabled) { transform: scale(1.07); }
.mic-btn:disabled             { opacity: .4; cursor: not-allowed; }
.mic-btn.streaming            { background: var(--error); animation: mic-pulse 1.6s ease-in-out infinite; }
.mic-btn.connecting           { background: var(--accent); opacity: .8; }
```

72px is comfortably above the 44px minimum touch target. `:hover:not(:disabled)` means a disabled button
does not respond to hover — a small honesty about what is clickable.

The three states are visually unmistakable: neutral grey idle, blue and dimmed while connecting, red and
pulsing while recording.

### Drop zone

```css
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-sm);
  transition: border-color .2s, color .2s;
  cursor: pointer;
}
.drop-zone input { display: none; }
.drop-zone:hover, .drop-zone.drag-over { border-color: var(--accent); color: var(--accent); }
.drop-zone.uploading { opacity: .6; cursor: wait; }
```

The dashed border is the conventional drop-target signal. `.drop-zone input { display: none }` is what makes
the `<label>`-wraps-`<input>` pattern work — see
[components.md](components.md#the-drop-zone).

Hover and `drag-over` share the same styling, so the affordance is identical whether you are about to click
or about to drop. `cursor: wait` during upload reinforces the disabled state.

### Probability bars

```css
.prob-row {
  display: grid;
  grid-template-columns: 68px 1fr 42px;
  align-items: center;
  gap: 10px;
}
.prob-track { height: 7px; background: var(--bg-elevated); border-radius: 4px; overflow: hidden; }
.prob-fill  { height: 100%; border-radius: 4px; transition: width .35s ease; opacity: .7; }

.prob-row.active .prob-label { color: var(--text-1); font-weight: 600; }
.prob-row.active .prob-fill  { opacity: 1; }
.prob-row.active .prob-pct   { color: var(--text-1); font-weight: 600; }
```

Fixed gutters (68px label, 42px percentage) with a flexing track, so labels and numbers align vertically
across all six rows regardless of text length.

`transition: width .35s ease` is what makes the bars animate smoothly rather than jumping — and it only
works because `ProbabilityBars` renders a stable list of six rows from the `EMOTIONS` constant, so each
`.prob-fill` is the same DOM node between renders. 350 ms is slightly shorter than the 500 ms prediction
interval, so each animation completes before the next arrives.

The active row gets three simultaneous emphases — brighter label, full-opacity fill, bolder percentage —
rather than relying on any single one.

### Timeline

```css
.timeline-scroll {
  overflow-x: auto; overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.timeline-scroll::-webkit-scrollbar        { height: 4px; }
.timeline-scroll::-webkit-scrollbar-thumb  { background: var(--border); border-radius: 2px; }

.timeline-track { display: flex; gap: 5px; padding: 4px 2px 8px; min-width: max-content; }

.tl-chip {
  width: 34px; height: 34px; border-radius: 50%;
  flex-shrink: 0; opacity: .7;
  transition: opacity .2s, transform .2s;
}
.tl-chip:hover      { opacity: 1; transform: scale(1.12); }
.tl-chip:last-child { opacity: 1; outline: 2px solid rgba(255,255,255,.25); }
```

`min-width: max-content` is the key line — it makes the flex track grow beyond its container so chips scroll
rather than compress. Without it, 60 chips would squeeze into the visible width.

`flex-shrink: 0` on the chips is the same guarantee at the item level.

The scrollbar is styled for both Firefox (`scrollbar-width`, `scrollbar-color`) and WebKit
(`::-webkit-scrollbar`), thin and unobtrusive.

Past chips sit at 0.7 opacity; the newest is full opacity with a subtle white outline. Combined with the
inline coloured outline from JSX, the current prediction is unmistakable in a row of tinted circles.

---

## Animations

Four keyframes, all short and all purposeful.

```css
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: .3; } }
```
Status dot while connecting or checking. Communicates "in progress" without a spinner.

```css
@keyframes mic-pulse {
  0%,100% { box-shadow: 0 0 0 0    rgba(248,113,113,.5); }
  50%     { box-shadow: 0 0 0 16px rgba(248,113,113,0);  }
}
```
An expanding ring that fades as it grows — the standard "live recording" idiom. Animating `box-shadow`
spread rather than a pseudo-element's `transform` is slightly less efficient but far simpler, and at 1.6 s
it is imperceptible either way.

```css
@keyframes pop { 0% { transform: scale(.7); } 70% { transform: scale(1.15); } 100% { transform: scale(1); } }
```
The emoji when the emotion **changes** — overshooting past 1.0 before settling gives it a physical quality.
250 ms. Only fires on an actual change, guarded by `prevRef` in
[`EmotionDisplay`](../../frontend/src/components/EmotionDisplay.jsx#L8), so repeated identical predictions
do not cause a constant twitch. Re-triggering the animation requires a forced reflow — see
[components.md](components.md#animation-re-triggering).

Plus CSS transitions on hover scale, bar width, and colour changes.

Every duration is between 150 ms and 350 ms except the two infinite loops. Nothing blocks perception of a
new prediction arriving 500 ms later.

**There is no `prefers-reduced-motion` handling.** Two infinitely looping animations run whenever the app is
active, which is exactly what that media query exists to suppress. A three-line addition:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
```

---

## Emotion colours

Defined in [`constants.js`](../../frontend/src/constants.js), not CSS, because JSX needs them for inline
styles:

| Emotion | Hex | Reasoning |
|---|---|---|
| `neutral` | `#94a3b8` | Slate — the `--text-2` token itself |
| `happy` | `#fbbf24` | Amber — warm, matches `--warning` |
| `sad` | `#60a5fa` | Blue — the conventional cool/melancholy mapping |
| `angry` | `#f87171` | Red — matches `--error` |
| `fearful` | `#a78bfa` | Violet — distinct from both red and blue |
| `disgust` | `#34d399` | Green — matches `--success` |

Reusing palette tokens where the mapping is natural keeps the six colours coherent with the rest of the UI
rather than looking like a separate decision.

They are applied three ways:

```jsx
style={{ color: EMOTION_COLORS[emotion] }}                    // EmotionDisplay label
style={{ background: EMOTION_COLORS[emotion] }}               // ProbabilityBars fill
style={{ background: EMOTION_COLORS[item.emotion] + '33' }}   // Timeline chip, ~20% alpha
```

The `+ '33'` trick appends an alpha channel to 6-digit hex — `#fbbf24` → `#fbbf2433`. Compact, and it works
only because every value is 6-digit hex; an `rgb()` or named colour would break it silently.

All six are light enough for adequate contrast on `--bg-surface`. They have **not** been checked for
colour-blind distinguishability — `angry` (red) and `disgust` (green) are the classic confusion pair. This
is mitigated substantially by never relying on colour alone: the emoji and the text label carry the same
information everywhere the colour appears.

---

## Responsive behaviour

```css
@media (max-width: 600px) {
  .row { grid-template-columns: 1fr; }
  .app { padding: 16px 12px 32px; }
}
```

One breakpoint, two rules. The two-column row stacks and the page padding tightens.

Everything else adapts without intervention because the layout is a flex column with `gap` and
`max-width: 960px` — it fills narrow viewports and centres on wide ones. The probability bars' `1fr` middle
column flexes; the timeline already scrolls horizontally; the mic button is a fixed comfortable size at all
widths.

Font sizes are fixed pixels rather than fluid or `rem`-based. That means the layout does not respond to a
user's browser font-size preference — an accessibility gap. Switching the type scale to `rem` would fix it
with no visual change at default settings.

---

## Details worth keeping

**`font-variant-numeric: tabular-nums`** on `.prob-pct`:

```css
.prob-pct { font-variant-numeric: tabular-nums; text-align: right; }
```

Forces monospaced digits, so a percentage changing from `9%` to `88%` does not shift horizontally. With
values updating twice a second, proportional digits would produce constant jitter. A one-line fix for
something that would otherwise look broken.

**`min-height` to reserve space:**

```css
.emotion-display { min-height: 160px; }
.status-text     { min-height: 18px;  }
```

The placeholder and a real prediction occupy the same vertical space, so the layout does not jump when the
first prediction arrives. `.status-text` reserves a line even when empty.

**Semi-transparent error banner:**

```css
.error-banner {
  background: rgba(248, 113, 113, .08);
  border: 1px solid rgba(248, 113, 113, .25);
  color: var(--error);
}
```

Two alpha levels of the same red rather than solid fills — visible without shouting, and it composites over
whatever surface is behind it.

**`box-sizing: border-box` globally**, so padding never expands an element beyond its declared width:

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
```

**A system font stack** with `'Inter'` first:

```css
font-family: 'Inter', system-ui, -apple-system, sans-serif;
```

Inter is not loaded — no `@font-face`, no Google Fonts link — so this resolves to `system-ui` unless the
user happens to have Inter installed locally. Either load it or drop it from the stack; as written it is
misleading, though harmless.

**`-webkit-font-smoothing: antialiased`** on body, which reduces the heaviness of light text on dark
backgrounds in WebKit.

---

## Theming

The token structure makes a light theme straightforward — every colour is a custom property, and no
component hard-codes one:

```css
@media (prefers-color-scheme: light) {
  :root {
    --bg-base:     #f8fafc;
    --bg-surface:  #ffffff;
    --bg-elevated: #f1f5f9;
    --border:      #e2e8f0;
    --text-1:      #0f172a;
    --text-2:      #475569;
    --text-3:      #94a3b8;
    /* status colours generally need darkening for contrast on white */
    --success:     #059669;
    --error:       #dc2626;
    --warning:     #d97706;
  }
}
```

Two things would need attention beyond the tokens:

- **The emotion colours live in JavaScript**, not CSS, so they would not switch with a media query. Moving
  them to CSS custom properties and reading them via `getComputedStyle` — or defining a second palette
  keyed off a theme flag — would be needed. As chosen, they are tuned for dark surfaces and several would
  be too light on white.
- **The Timeline's `rgba(255,255,255,.25)` outline** is hard-coded white and would be invisible on a light
  background. It should be a token.

An explicit toggle rather than only `prefers-color-scheme` would mean a `data-theme` attribute on the root
and duplicating the token block under `[data-theme="light"]`.

---

## Accessibility gaps

Honest inventory.

| Gap | Impact | Fix |
|---|---|---|
| No `prefers-reduced-motion` | Two infinite animations run regardless of user preference | The media query [above](#animations) |
| Fixed `px` font sizes | Ignores browser font-size preference | Switch the type scale to `rem` |
| Red/green emotion pair | `angry`/`disgust` confusable for ~8% of men | Mitigated by emoji + labels; could add patterns to bars |
| No focus-visible styling | Keyboard focus is browser-default and low-contrast on dark | `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }` |
| No live region for predictions | Screen readers do not announce new results | `aria-live="polite"` on `.emotion-display` |
| Drop zone keyboard path | The `<label>`+hidden-input pattern is focusable via the input, but the input is `display: none` — which removes it from the tab order entirely | Use `opacity: 0; position: absolute` instead of `display: none` |
| Contrast of `--text-3` on `--bg-surface` | `#64748b` on `#1e293b` is roughly 3.3:1 — below the 4.5:1 WCAG AA threshold for body text | Lighten `--text-3`, or reserve it for large text only |

The last two are the most consequential. `display: none` on the file input is a genuine keyboard trap — the
drop zone is unreachable without a mouse. And `--text-3` is used for section labels, percentages, and the
status bar, all of which are small text below the contrast threshold.
