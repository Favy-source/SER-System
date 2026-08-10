import { useState, useRef, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL  = API_URL.replace(/^http/, 'ws') + '/ws/stream';

// Binary channel tags, matching backend/main.py. Used only when the handshake
// sets tagged_binary — 4-byte header keeps the float32 payload 4-aligned.
const TAG_AUDIO     = 0;
const TAG_LANDMARKS = 1;
const TAG_HEADER    = 4;

function tagFrame(tag, buffer) {
  const out = new Uint8Array(TAG_HEADER + buffer.byteLength);
  out[0] = tag;                                  // bytes 1..3 stay zero (reserved)
  out.set(new Uint8Array(buffer), TAG_HEADER);
  return out.buffer;
}

export function useStream() {
  const [status,        setStatus]        = useState('idle');   // idle|connecting|streaming|error
  const [prediction,    setPrediction]    = useState(null);
  const [history,       setHistory]       = useState([]);
  const [error,         setError]         = useState(null);
  const [visualEnabled, setVisualEnabled] = useState(false);    // what the SERVER agreed to

  const wsRef      = useRef(null);
  const ctxRef     = useRef(null);
  const workletRef = useRef(null);
  const streamRef  = useRef(null);
  const taggedRef  = useRef(false);

  // ── cleanup (called by stop, ws.onerror, and start's catch) ─────
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
    taggedRef.current = false;
  };

  /** Forward one frame of RAW landmark coords (Float32Array of n*3). */
  const sendLandmarks = useCallback((flat) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !taggedRef.current) return;
    ws.send(tagFrame(TAG_LANDMARKS, flat.buffer));
  }, []);

  // Set from /health. When the server has no websockets/wsproto, /ws/stream
  // answers 404 — which surfaces as a generic connection failure and reads like
  // an unreachable backend. It is not; it is a missing dependency.
  const wsSupportRef = useRef(true);
  const setWsSupported = useCallback((ok) => { wsSupportRef.current = ok !== false; }, []);

  const start = useCallback(async ({ visual = false } = {}) => {
    setStatus('connecting');
    setError(null);
    setVisualEnabled(false);

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = mediaStream;

      const ctx = new AudioContext({ sampleRate: 16000 });
      ctxRef.current = ctx;

      const ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      // Declare the context's ACTUAL rate, not the requested one — a browser
      // that could not honour 16 kHz would otherwise have every window
      // resampled with the wrong ratio, silently, with no error anywhere.
      ws.onopen = () => ws.send(JSON.stringify({
        sample_rate:    Math.round(ctx.sampleRate),
        tagged_binary:  true,
        visual,
      }));

      ws.onmessage = async (evt) => {
        const msg = JSON.parse(evt.data);

        if (msg.type === 'ready') {
          taggedRef.current = msg.payload.tagged_binary === true;
          setVisualEnabled(msg.payload.visual_enabled === true);

          if (visual && msg.payload.visual_enabled === false) {
            setError(msg.payload.multimodal_model === false
              ? 'Loaded model is audio-only, so the camera cannot contribute. Load a fusion checkpoint for multimodal.'
              : 'Server declined visual streaming.');
          }

          const send = (buf) => {
            if (ws.readyState !== WebSocket.OPEN) return;
            ws.send(taggedRef.current ? tagFrame(TAG_AUDIO, buf) : buf);
          };

          try {
            await ctx.audioWorklet.addModule('/worklets/pcm-processor.js');
            const source  = ctx.createMediaStreamSource(mediaStream);
            const worklet = new AudioWorkletNode(ctx, 'pcm-processor');
            workletRef.current = worklet;
            worklet.port.onmessage = (e) => send(e.data);
            source.connect(worklet);
          } catch (err) {
            // AudioWorklet unavailable (older Safari) or the worklet file failed
            // to load — log it, because a 404 here is a deploy bug, not a
            // browser capability limit.
            console.warn('AudioWorklet unavailable, falling back to ScriptProcessorNode:', err);
            const source = ctx.createMediaStreamSource(mediaStream);
            const proc   = ctx.createScriptProcessor(4096, 1, 1);
            workletRef.current = proc;
            proc.onaudioprocess = (e) => {
              send(new Float32Array(e.inputBuffer.getChannelData(0)).buffer);
            };
            source.connect(proc);
            // Route through a silent gain node so the fallback does not send the
            // microphone to the speakers and cause feedback.
            const mute = ctx.createGain();
            mute.gain.value = 0;
            proc.connect(mute);
            mute.connect(ctx.destination);
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

      ws.onerror = () => {
        setError(wsSupportRef.current
          ? 'Cannot reach backend. Is it running on port 8000?'
          : "Server has no WebSocket support, so live streaming is unavailable "
            + "(file upload still works). Fix: pip install 'uvicorn[standard]'");
        setStatus('error');
        _cleanup();
      };

      // Functional update: the previous `status !== 'error'` read a value
      // captured at first render (always 'idle'), so the guard never fired and
      // an errored connection was reset to idle on close.
      ws.onclose = () => setStatus(prev => (prev === 'error' ? prev : 'idle'));

    } catch (e) {
      const msg = String(e?.message ?? e);
      // "Could not start audio source" is the browser wording for a mic it
      // cannot open — usually another app holding it, or a context with no
      // media access at all (embedded webviews).
      let friendly = msg;
      if (/NotReadable|Could not start audio/i.test(msg)) {
        friendly = 'Could not start the microphone. Another application may be using it, or this '
                 + 'browser context has no media access. Open http://localhost:3000 in Chrome or '
                 + 'Firefox — an embedded webview such as VS Code Simple Browser cannot capture audio.';
      } else if (/NotAllowed|Permission/i.test(msg)) {
        friendly = 'Microphone permission denied. Allow it in the browser, then try again.';
      } else if (/NotFound|Requested device/i.test(msg)) {
        friendly = 'No microphone found. Check your system input device.';
      } else if (/mediaDevices|undefined/i.test(msg)) {
        friendly = 'This page is not in a secure context, so the microphone is unavailable. '
                 + 'Use http://localhost (not an IP address) or serve over HTTPS.';
      }
      setError(friendly);
      setStatus('error');
      _cleanup();
    }
  }, []);

  const stop = useCallback(() => {
    _cleanup();
    setStatus('idle');
    setVisualEnabled(false);
  }, []);

  const reset = useCallback(() => {
    // Clear the server's buffers too, so the next prediction does not cover a
    // window spanning the moment the user pressed Clear.
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'reset' }));
    }
    setHistory([]);
    setPrediction(null);
    setError(null);
  }, []);

  return { status, prediction, history, error, visualEnabled,
           start, stop, reset, sendLandmarks, setWsSupported };
}
