import { forwardRef } from 'react';

const STATUS = {
  idle:        { label: 'Camera off',              dot: '' },
  loading:     { label: 'Loading face model…',     dot: 'loading' },
  tracking:    { label: 'Face tracked',            dot: 'online' },
  'no-face':   { label: 'No face detected',        dot: 'loading' },
  error:       { label: 'Camera unavailable',      dot: 'offline' },
  unsupported: { label: 'Face tracking failed',    dot: 'offline' },
};

/**
 * Webcam preview plus face-tracking state.
 *
 * The <video> element is forwarded to useFaceTracking, which attaches the
 * MediaStream and reads frames from it. Nothing is drawn on top of the video —
 * only landmark coordinates leave the browser, never pixels.
 */
export const VideoCapture = forwardRef(function VideoCapture(
  { enabled, onToggle, status, frameRate, error, visualEnabled, streaming, delegate },
  videoRef,
) {
  const s = STATUS[status] ?? STATUS.idle;
  const live = status === 'tracking' || status === 'no-face';

  return (
    <div className="video-wrap">
      <div className="video-head">
        <span className="section-label" style={{ marginBottom: 0 }}>Face tracking</span>
        <label className="switch" title={
          streaming ? 'Stop the stream to change this' : 'Use the webcam as a second modality'
        }>
          <input
            type="checkbox"
            checked={enabled}
            disabled={streaming}
            onChange={(e) => onToggle(e.target.checked)}
          />
          <span>{enabled ? 'On' : 'Off'}</span>
        </label>
      </div>

      <div className={`video-frame ${live ? 'live' : ''}`}>
        {/* muted + playsInline are required for autoplay; mirrored for a
            natural self-view */}
        <video
          ref={videoRef}
          className="video-el"
          muted
          playsInline
          style={{ display: live ? 'block' : 'none' }}
        />
        {!live && (
          <div className="video-placeholder">
            {enabled ? s.label : 'Camera off — audio only'}
          </div>
        )}
      </div>

      <div className="video-meta">
        <span className="model-badge">
          <span className={`status-dot ${s.dot}`} />
          <span>{s.label}</span>
        </span>
        {live && frameRate > 0 && <span className="chip">{frameRate} fps</span>}
        {live && delegate && <span className="chip">{delegate}</span>}
      </div>

      {error && <div className="video-note error">{error}</div>}

      {/* The honest disclosure: a fusion model with no live face still predicts,
          but on a zero visual tensor — so it is not the model that was
          evaluated. Say so rather than letting the UI imply otherwise. */}
      {enabled && streaming && !visualEnabled && !error && (
        <div className="video-note">
          Predictions are audio-only — the server did not enable the visual stream.
        </div>
      )}
    </div>
  );
});
