/**
 * Capture the live dashboard for the interview deck.
 *
 *   node scripts/capture_dashboard.mjs <url> <out.png> [--video x.y4m] [--audio x.wav]
 *
 * WHY THIS EXISTS RATHER THAN A MANUAL SCREENSHOT
 *   A screenshot of an idle dashboard proves nothing. Chrome can be handed a
 *   FILE as its camera and microphone, so the capture below drives the real
 *   system with a real RAVDESS clip: a real actor's face into MediaPipe, that
 *   actor's speech into the audio model. What lands on the slide is the system
 *   genuinely running, not a mock-up.
 *
 *     --use-fake-device-for-media-stream  synthetic camera/mic — ALWAYS ON
 *     --use-file-for-fake-video-capture   .y4m only (uncompressed)
 *     --use-file-for-fake-audio-capture   16-bit PCM .wav
 *     --use-fake-ui-for-media-stream      auto-grants getUserMedia
 *
 *   Without a file, the synthetic device is a rolling test pattern with no face
 *   in it, so FaceLandmarker finds nothing and the visual stream never engages.
 *
 * SAFETY
 *   The auto-grant flag suppresses the permission prompt, so if the synthetic
 *   device is not also forced, Chrome silently opens the machine's real camera.
 *   See the comment on `args` — that is not a hypothetical.
 */
import { createRequire } from 'node:module'
import { readdirSync, existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, resolve } from 'node:path'

function resolveChromium() {
  const roots = []
  for (const base of [
    join(homedir(), '.vscode-server/extensions'),
    join(homedir(), '.vscode/extensions'),
  ]) {
    if (!existsSync(base)) continue
    const dirs = readdirSync(base)
      .filter((d) => d.startsWith('danielsanmedium.dscodegpt-'))
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }))
    const newest = dirs[dirs.length - 1]
    if (newest) roots.push(join(base, newest, 'standalone') + '/')
  }
  roots.push(process.cwd() + '/')
  for (const root of roots) {
    try {
      const mod = createRequire(root)('patchright')
      const chromium = mod?.chromium ?? mod?.default?.chromium
      if (chromium) return chromium
    } catch {}
  }
  throw new Error('Could not resolve patchright')
}

const argv = process.argv.slice(2)
const url = argv[0]
const out = argv[1]
const flag = (n) => { const i = argv.indexOf(n); return i === -1 ? undefined : argv[i + 1] }
const video = flag('--video')
const audio = flag('--audio')
const settle = Number(flag('--settle') ?? 14000)

// PRIVACY INVARIANT — do not weaken this.
//
// --use-fake-ui-for-media-stream auto-grants getUserMedia. On its own that
// means Chrome opens the REAL camera and microphone with no prompt. An earlier
// version of this script did exactly that and captured the machine owner's face
// into a screenshot intended for a slide deck.
//
// --use-fake-device-for-media-stream is therefore UNCONDITIONAL. It forces a
// synthetic device, and --use-file-for-fake-*-capture then substitutes a file
// for that synthetic device. Passing a file without this flag does not disable
// the real hardware; it is not a substitute for it.
const args = [
  '--no-sandbox',
  '--disable-dev-shm-usage',
  '--use-fake-device-for-media-stream',   // never the real camera/mic
  '--use-fake-ui-for-media-stream',
  '--autoplay-policy=no-user-gesture-required',
]
if (video) args.push(`--use-file-for-fake-video-capture=${resolve(video)}`)
if (audio) args.push(`--use-file-for-fake-audio-capture=${resolve(audio)}`)

const chromium = resolveChromium()
const browser = await chromium.launch({ headless: true, channel: 'chromium', args })
const ctx = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
  deviceScaleFactor: 2,
  permissions: ['camera', 'microphone'],
})
const page = await ctx.newPage()

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)) })
page.on('pageerror', (e) => errors.push('UNCAUGHT ' + String(e).slice(0, 200)))
page.on('requestfailed', (r) => errors.push('FAILED ' + r.url().slice(0, 120)))

await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 })

// Camera FIRST, then the microphone. FaceLandmarker needs time to initialise
// its WASM backend and lock onto a face; starting audio first would begin
// buffering — and predicting — before the visual stream has anything to
// contribute, and the capture would show a half-warmed system.
const actions = []

const camSwitch = page.locator('label.switch').first()
if (await camSwitch.count().catch(() => 0)) {
  await camSwitch.click().catch(() => {})
  actions.push('camera toggle')
  await page.waitForTimeout(4000)   // WASM load + first face lock
}

const mic = page.locator('button.mic-btn').first()
if (await mic.count().catch(() => 0)) {
  await mic.click().catch(() => {})
  actions.push('mic')
}

// Wait for the pipeline to actually produce something rather than a fixed nap:
// a prediction only appears after enough audio has buffered.
await page.waitForTimeout(settle)

const state = await page.evaluate(() => ({
  title: document.title,
  bodyChars: document.body?.innerText?.length ?? 0,
  text: (document.body?.innerText ?? '').slice(0, 1200),
  videoEls: [...document.querySelectorAll('video')].map((v) => ({
    w: v.videoWidth, h: v.videoHeight, playing: !v.paused && v.readyState > 2,
  })),
  canvases: [...document.querySelectorAll('canvas')].map((c) => ({ w: c.width, h: c.height })),
}))

await page.screenshot({ path: out, fullPage: false })
await browser.close()

console.log(JSON.stringify({
  actions, screenshot: out,
  consoleErrors: errors.slice(0, 8), ...state,
}, null, 2))
