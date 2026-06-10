import { useState, useEffect } from 'react';
import { Header }          from './components/Header.jsx';
import { AudioCapture }    from './components/AudioCapture.jsx';
import { EmotionDisplay }  from './components/EmotionDisplay.jsx';
import { ProbabilityBars } from './components/ProbabilityBars.jsx';
import { Timeline }        from './components/Timeline.jsx';
import { useStream }       from './hooks/useStream.js';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const { status, prediction, history, error, start, stop, reset } = useStream();

  const [health,          setHealth]          = useState(null);
  const [filePrediction,  setFilePrediction]  = useState(null);
  const [uploading,       setUploading]       = useState(false);

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

  // Live predictions take priority over file predictions
  const activePrediction = prediction ?? filePrediction;

  return (
    <div className="app">
      <Header health={health} status={status} />

      {error && <div className="error-banner">⚠ {error}</div>}

      <div className="row">
        <div className="card">
          <AudioCapture
            status={status}
            onStart={start}
            onStop={stop}
            onFile={handleFile}
            uploading={uploading}
          />
        </div>
        <div className="card">
          <EmotionDisplay prediction={activePrediction} />
        </div>
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
