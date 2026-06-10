export function Header({ health, status }) {
  const dotClass =
    status === 'streaming' ? 'online' :
    status === 'connecting' ? 'loading' :
    status === 'error' ? 'offline' :
    health?.model_loaded ? 'online' :
    health ? 'offline' : 'loading';

  const label =
    status === 'streaming'  ? 'Streaming' :
    status === 'connecting' ? 'Connecting…' :
    status === 'error'      ? 'Error' :
    health?.model_loaded    ? health.model_name ?? 'Model ready' :
    health                  ? 'No model loaded' : 'Checking…';

  return (
    <div className="header">
      <div>
        <div className="header-title">SER System</div>
        <div className="header-sub">Multimodal Speech Emotion Recognition</div>
      </div>
      <div className="model-badge">
        <span className={`status-dot ${dotClass}`} />
        <span>{label}</span>
      </div>
    </div>
  );
}
