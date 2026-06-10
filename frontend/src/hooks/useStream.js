import { useState, useRef, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL  = API_URL.replace(/^http/, 'ws') + '/ws/stream';

export function useStream() {
  const [status,     setStatus]     = useState('idle');      // idle|connecting|streaming|error
  const [prediction, setPrediction] = useState(null);
  const [history,    setHistory]    = useState([]);
  const [error,      setError]      = useState(null);

  const wsRef      = useRef(null);
  const ctxRef     = useRef(null);
  const workletRef = useRef(null);
  const streamRef  = useRef(null);

  // ── cleanup (called by both stop and start's catch) ─────
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

  const start = useCallback(async () => {
    setStatus('connecting');
    setError(null);

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

      ws.onopen = () => ws.send(JSON.stringify({ sample_rate: 16000 }));

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
            // AudioWorklet unavailable — fall back to ScriptProcessorNode
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
            proc.connect(ctx.destination);
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
        setError('Cannot reach backend. Is it running on port 8000?');
        setStatus('error');
        _cleanup();
      };

      ws.onclose = () => {
        if (status !== 'error') setStatus('idle');
      };

    } catch (e) {
      setError(e.message);
      setStatus('error');
      _cleanup();
    }
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const stop = useCallback(() => {
    _cleanup();
    setStatus('idle');
  }, []);

  const reset = useCallback(() => {
    setHistory([]);
    setPrediction(null);
    setError(null);
  }, []);

  return { status, prediction, history, error, start, stop, reset };
}
