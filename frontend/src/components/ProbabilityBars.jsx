import { EMOTIONS, EMOTION_COLORS } from '../constants.js';

export function ProbabilityBars({ prediction }) {
  const probs = prediction?.probabilities ?? {};
  const top   = prediction?.emotion;

  return (
    <div>
      <div className="section-label" style={{ marginBottom: 10 }}>Emotion probabilities</div>
      <div className="prob-list">
        {EMOTIONS.map((emotion) => {
          const p   = probs[emotion] ?? 0;
          const pct = (p * 100).toFixed(0);
          return (
            <div key={emotion} className={`prob-row ${emotion === top ? 'active' : ''}`}>
              <span className="prob-label">{emotion}</span>
              <div className="prob-track">
                <div
                  className="prob-fill"
                  style={{
                    width:      `${pct}%`,
                    background: EMOTION_COLORS[emotion],
                  }}
                />
              </div>
              <span className="prob-pct">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
