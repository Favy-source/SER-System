import { useRef, useState } from 'react';

const STATUS_TEXT = {
  idle:       'Click the mic to start live recognition',
  connecting: 'Connecting to backend…',
  streaming:  'Listening — click to stop',
  error:      'Something went wrong',
};

export function AudioCapture({ status, onStart, onStop, onFile, uploading }) {
  const inputRef  = useRef(null);
  const [drag, setDrag] = useState(false);

  const isStreaming  = status === 'streaming';
  const isConnecting = status === 'connecting';
  const busy = isConnecting || uploading;

  const handleFile = (f) => {
    if (f && f.type.startsWith('audio/')) onFile(f);
  };

  return (
    <div className="capture-wrap">
      <div className="section-label">Live recording</div>

      <button
        className={`mic-btn ${isStreaming ? 'streaming' : isConnecting ? 'connecting' : ''}`}
        onClick={isStreaming ? onStop : onStart}
        disabled={busy && !isStreaming}
        title={isStreaming ? 'Stop recording' : 'Start recording'}
        aria-label={isStreaming ? 'Stop' : 'Record'}
      >
        {isConnecting ? '⏳' : isStreaming ? '⏹' : '🎙'}
      </button>

      <div className="status-text">{STATUS_TEXT[status] ?? ''}</div>

      <div className="section-label" style={{ marginTop: 4 }}>Upload file</div>

      <label
        className={`drop-zone ${drag ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="audio/*"
          onChange={(e) => handleFile(e.target.files[0])}
          disabled={uploading}
        />
        {uploading
          ? 'Analysing…'
          : drag
          ? 'Drop to analyse'
          : 'Drop audio file or click to browse'}
      </label>
    </div>
  );
}
