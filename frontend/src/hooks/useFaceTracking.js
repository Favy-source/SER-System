import { useCallback, useRef, useState } from 'react';

/**
 * Webcam face-landmark tracking via MediaPipe FaceLandmarker.
 *
 * Emits RAW landmark coordinates. Normalisation (centroid subtraction, scale by
 * max radius) is deliberately NOT done here — the server applies the same
 * src.features.normalize_landmarks that produced the training features.
 * Reimplementing that maths in JavaScript would be textbook train/serve skew:
 * two implementations that agree today and drift silently later.
 *
 * The model returns 478 landmarks (468 base mesh + 10 iris). The server keeps
 * the leading N_FACE_LANDMARKS, so this works against a 468-point model without
 * either side having to know the other's refine_landmarks setting.
 */

const WASM_PATH  = import.meta.env.VITE_MEDIAPIPE_WASM  || '/mediapipe/wasm';
const MODEL_PATH = import.meta.env.VITE_FACE_MODEL_URL  || '/mediapipe/models/face_landmarker.task';

// ~10 fps. The server buffers up to max_frames (75) and audio drives inference,
// so a higher rate buys nothing and costs battery and main-thread time.
const TARGET_FPS = 10;
const FRAME_MS   = 1000 / TARGET_FPS;

export function useFaceTracking() {
  const [status,    setStatus]    = useState('idle');   // idle|loading|tracking|no-face|error|unsupported
  const [error,     setError]     = useState(null);
  const [frameRate, setFrameRate] = useState(0);
  const [delegate,  setDelegate]  = useState(null);   // GPU or CPU, whichever loaded

  const landmarkerRef = useRef(null);
  const streamRef     = useRef(null);
  const videoRef      = useRef(null);
  const rafRef        = useRef(null);
  const onFrameRef    = useRef(null);
  const lastSentRef   = useRef(0);
  const tickRef       = useRef({ count: 0, since: 0 });
  const runningRef    = useRef(false);

  const _cleanup = useCallback(() => {
    runningRef.current = false;
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    if (videoRef.current) {
      try { videoRef.current.pause(); } catch {}
      videoRef.current.srcObject = null;
      videoRef.current = null;
    }
    // Keep the landmarker: reloading 34 MB of WASM per start is wasteful and
    // it holds no per-session state.
    onFrameRef.current = null;
    setFrameRate(0);
  }, []);

  /**
   * @param videoEl  a <video> element to attach the camera to (for preview)
   * @param onFrame  called with a Float32Array of n*3 raw coords per frame
   */
  const start = useCallback(async (videoEl, onFrame) => {
    setStatus('loading');
    setError(null);
    onFrameRef.current = onFrame;

    try {
      // Dynamic import so the 34 MB WASM path is never touched unless the user
      // actually turns the camera on.
      const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');

      if (!landmarkerRef.current) {
        const fileset = await FilesetResolver.forVisionTasks(WASM_PATH);
        const opts = (delegate) => ({
          baseOptions: { modelAssetPath: MODEL_PATH, delegate },
          runningMode: 'VIDEO',
          numFaces: 1,
          outputFaceBlendshapes: false,
          outputFacialTransformationMatrixes: false,
        });

        // GPU is much faster, but WebGL is simply absent in some contexts —
        // embedded webviews (VS Code Simple Browser), software rendering,
        // headless. There it fails with
        //   emscripten_webgl_create_context() returned error 0; StartGraph failed
        // which is fatal rather than slow, so fall back to the CPU delegate
        // instead of losing face tracking altogether.
        try {
          landmarkerRef.current = await FaceLandmarker.createFromOptions(fileset, opts('GPU'));
          setDelegate('GPU');
        } catch (gpuErr) {
          console.warn('MediaPipe GPU delegate unavailable, retrying on CPU:', gpuErr);
          landmarkerRef.current = await FaceLandmarker.createFromOptions(fileset, opts('CPU'));
          setDelegate('CPU');
        }
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
      });
      streamRef.current = mediaStream;

      videoEl.srcObject = mediaStream;
      videoRef.current = videoEl;
      await videoEl.play();

      runningRef.current = true;
      tickRef.current = { count: 0, since: performance.now() };
      setStatus('tracking');

      const loop = () => {
        if (!runningRef.current) return;
        rafRef.current = requestAnimationFrame(loop);

        const video = videoRef.current;
        const lm = landmarkerRef.current;
        if (!video || !lm || video.readyState < 2) return;

        const now = performance.now();
        if (now - lastSentRef.current < FRAME_MS) return;
        lastSentRef.current = now;

        let result;
        try {
          result = lm.detectForVideo(video, now);
        } catch {
          return;                      // transient decode hiccup; try next frame
        }

        const faces = result?.faceLandmarks;
        if (!faces || faces.length === 0) {
          setStatus((s) => (s === 'tracking' ? 'no-face' : s));
          return;
        }
        setStatus((s) => (s === 'no-face' ? 'tracking' : s));

        // Flatten to [x0,y0,z0, x1,y1,z1, ...] — raw, unnormalised.
        const pts = faces[0];
        const flat = new Float32Array(pts.length * 3);
        for (let i = 0; i < pts.length; i++) {
          flat[i * 3]     = pts[i].x;
          flat[i * 3 + 1] = pts[i].y;
          flat[i * 3 + 2] = pts[i].z ?? 0;
        }
        onFrameRef.current?.(flat);

        const t = tickRef.current;
        t.count += 1;
        if (now - t.since >= 1000) {
          setFrameRate(Math.round((t.count * 1000) / (now - t.since)));
          t.count = 0; t.since = now;
        }
      };
      rafRef.current = requestAnimationFrame(loop);

    } catch (e) {
      const msg = String(e?.message ?? e);
      // Map the failures that actually happen onto their specific fixes, rather
      // than surfacing a six-line MediaPipe graph trace.
      let friendly = msg;
      if (/webgl|kGpuService|StartGraph|StartRun/i.test(msg)) {
        friendly = 'Face tracking needs WebGL, which this browser context does not provide. '
                 + 'Open http://localhost:3000 in Chrome or Firefox — an embedded webview such '
                 + 'as VS Code Simple Browser supports neither WebGL nor camera access.';
      } else if (/fetch|404|modelAssetPath/i.test(msg)) {
        friendly = 'Face model not found. Run "npm run setup:mediapipe" in frontend/.';
      } else if (/NotAllowed|Permission/i.test(msg)) {
        friendly = 'Camera permission denied. Allow it in the browser, then try again.';
      } else if (/NotFound|NotReadable|Could not start/i.test(msg)) {
        friendly = 'Camera unavailable — another application may be using it.';
      }
      setError(friendly);
      setStatus(/NotAllowed|Permission|NotFound|NotReadable/i.test(msg) ? 'error' : 'unsupported');
      _cleanup();
    }
  }, [_cleanup]);

  const stop = useCallback(() => {
    _cleanup();
    setStatus('idle');
  }, [_cleanup]);

  return { status, error, frameRate, delegate, start, stop };
}
