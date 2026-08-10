/**
 * Vendors the MediaPipe vision assets into public/ so the app runs offline.
 *
 * Two kinds of asset are needed at runtime and neither belongs in git:
 *   - the WASM runtime (~34 MB) which ships inside @mediapipe/tasks-vision
 *   - face_landmarker.task (~3.8 MB) which is downloaded from Google's CDN
 *
 * Both land in public/mediapipe/ and are gitignored. This runs automatically
 * before `npm run dev` and `npm run build`; it is idempotent and skips work
 * that is already done, so the common case costs nothing.
 *
 * Offline/air-gapped install: fetch face_landmarker.task on a connected machine
 * and drop it at frontend/public/mediapipe/models/face_landmarker.task. The
 * WASM copy needs no network — it comes from node_modules.
 */
import { existsSync, mkdirSync, copyFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

const WASM_SRC  = join(root, 'node_modules/@mediapipe/tasks-vision/wasm');
const WASM_DEST = join(root, 'public/mediapipe/wasm');
const MODEL_DIR = join(root, 'public/mediapipe/models');
const MODEL     = join(MODEL_DIR, 'face_landmarker.task');
const MODEL_URL =
  process.env.FACE_MODEL_URL ??
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

const mb = (b) => (b / 1024 / 1024).toFixed(1);

function copyWasm() {
  if (!existsSync(WASM_SRC)) {
    console.error('[mediapipe] node_modules/@mediapipe/tasks-vision not found — run npm install first');
    process.exit(1);
  }
  mkdirSync(WASM_DEST, { recursive: true });
  let copied = 0, skipped = 0;
  for (const f of readdirSync(WASM_SRC)) {
    const src = join(WASM_SRC, f), dest = join(WASM_DEST, f);
    if (existsSync(dest) && statSync(dest).size === statSync(src).size) { skipped++; continue; }
    copyFileSync(src, dest);
    copied++;
  }
  console.log(`[mediapipe] wasm: ${copied} copied, ${skipped} already present -> public/mediapipe/wasm`);
}

async function fetchModel() {
  if (existsSync(MODEL) && statSync(MODEL).size > 1_000_000) {
    console.log(`[mediapipe] model present (${mb(statSync(MODEL).size)} MB) — skipping download`);
    return;
  }
  mkdirSync(MODEL_DIR, { recursive: true });
  console.log(`[mediapipe] downloading face_landmarker.task ...`);
  try {
    const res = await fetch(MODEL_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length < 1_000_000) throw new Error(`suspiciously small (${buf.length} bytes)`);
    writeFileSync(MODEL, buf);
    console.log(`[mediapipe] model saved (${mb(buf.length)} MB)`);
  } catch (err) {
    // Not fatal: face tracking simply stays unavailable, and the app falls back
    // to audio-only. Failing the build over an optional asset would be worse.
    console.warn(`[mediapipe] could not download the model: ${err.message}`);
    console.warn(`[mediapipe] face tracking will be unavailable until it exists at:`);
    console.warn(`[mediapipe]   ${MODEL}`);
    console.warn(`[mediapipe] fetch it manually from: ${MODEL_URL}`);
  }
}

copyWasm();
await fetchModel();
