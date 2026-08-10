import { useState, useEffect, useRef, useCallback } from 'react';
import { Header }          from './components/Header.jsx';
import { AudioCapture }    from './components/AudioCapture.jsx';
import { VideoCapture }    from './components/VideoCapture.jsx';
import { EmotionDisplay }  from './components/EmotionDisplay.jsx';
import { ProbabilityBars } from './components/ProbabilityBars.jsx';
import { Timeline }        from './components/Timeline.jsx';
import { useStream }       from './hooks/useStream.js';
import { useFaceTracking } from './hooks/useFaceTracking.js';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const {
    status, prediction, history, error, visualEnabled,
    start, stop, reset, sendLandmarks,
  } = useStream();

  const face     = useFaceTracking();
  const videoRef = useRef(null);

  const [health,         setHealth]         = useState(null);
  const [filePrediction, setFilePrediction] = useState(null);
  const [uploading,      setUploading]      = useState(false);
  const [useCamera,      setUseCamera]      = useState(false);
  const [uploadError,    setUploadError]    = useState(null);

  // Poll /health every 10 s
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

  const streaming = status === 'streaming' || status === 'connecting';

  // Start/stop face tracking alongside the audio stream. Landmarks go straight
  // to the socket; the server normalises them with the same function the
  // training pipeline used.
  const handleStart = useCallback(async () => {
    await start({ visual: useCamera });
    if (useCamera && videoRef.current) {
      await face.start(videoRef.current, sendLandmarks);
    }
  }, [start, useCamera, face, sendLandmarks]);

  const handleStop = useCallback(() => {
    face.stop();
    stop();
  }, [face, stop]);

  // Release the camera if the whole stream dies for any other reason.
  useEffect(() => {
    if (status === 'idle' || status === 'error') face.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
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
      setUploadError(e.message);
    }
    setUploading(false);
  };

  // Live predictions take priority over file predictions
  const activePrediction = prediction ?? filePrediction;
  const banner = error ?? uploadError;

  return (
    <div className="app">
      <Header health={health} status={status} />

      {health?.untrained && (
        <div className="warn-banner">
          <strong>Untrained model.</strong> These weights are randomly initialised, so every
          prediction below is noise — useful for seeing the pipeline run, meaningless as a result.
          Train a model with <code>scripts/train.py</code> for real output.
        </div>
      )}

      {banner && (
        <div className="error-banner" onClick={() => setUploadError(null)}>⚠ {banner}</div>
      )}

      <div className="row">
        <div className="card">
          <AudioCapture
            status={status}
            onStart={handleStart}
            onStop={handleStop}
            onFile={handleFile}
            uploading={uploading}
          />
        </div>
        <div className="card">
          <EmotionDisplay prediction={activePrediction} />
        </div>
      </div>

      <div className="card">
        <VideoCapture
          ref={videoRef}
          enabled={useCamera}
          onToggle={setUseCamera}
          status={face.status}
          frameRate={face.frameRate}
          error={face.error}
          visualEnabled={visualEnabled}
          streaming={streaming}
        />
      </div>

      <div className="card">
        <ProbabilityBars prediction={activePrediction} />
      </div>

      <div className="card">
        <Timeline history={history} onReset={reset} />
      </div>

      {activePrediction && (
        <div className="status-bar">
          <span>Model: {activePrediction.model_name}</span>
          <span className="sep">·</span>
          <span>Latency: {activePrediction.latency_ms} ms</span>
          <span className="sep">·</span>
          {/* Which modalities actually contributed to THIS prediction */}
          <span className={activePrediction.visual_active ? 'mod-multi' : undefined}>
            {(activePrediction.modalities ?? ['audio']).join(' + ')}
          </span>
          {history.length > 0 && (
            <>
              <span className="sep">·</span>
              <span>Predictions: {history.length}</span>
            </>
          )}
          {health?.device && (
            <>
              <span className="sep">·</span>
              <span>Device: {health.device}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
