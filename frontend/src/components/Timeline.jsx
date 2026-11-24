import { useRef, useEffect } from 'react';
import { EMOTION_COLORS, EMOTION_EMOJIS } from '../constants.js';

export function Timeline({ history, onReset }) {
  const scrollRef = useRef(null);

  const lastTs = history[history.length - 1]?.ts;
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [history.length, lastTs]);

  return (
    <div>
      <div className="timeline-header">
        <span className="section-label" style={{ marginBottom: 0 }}>
          Emotion history
          {history.length > 0 && (
            <span style={{ marginLeft: 6, color: 'var(--text-3)', fontWeight: 400 }}>
              ({history.length})
            </span>
          )}
        </span>
        {history.length > 0 && (
          <button className="reset-btn" onClick={onReset}>Clear</button>
        )}
      </div>

      {history.length === 0 ? (
        <div className="timeline-empty">No predictions yet</div>
      ) : (
        <div className="timeline-scroll" ref={scrollRef}>
          <div className="timeline-track">
            {history.map((item, i) => (
              <div
                key={item.ts ?? i}
                className="tl-chip"
                style={{ background: EMOTION_COLORS[item.emotion] + '33',
                         outline: i === history.length - 1
                           ? `2px solid ${EMOTION_COLORS[item.emotion]}`
                           : 'none' }}
                title={`${item.emotion} — ${(item.confidence * 100).toFixed(0)}%`}
              >
                {EMOTION_EMOJIS[item.emotion] ?? '❓'}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
