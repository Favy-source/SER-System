import { useRef, useEffect } from 'react';
import { EMOTION_COLORS, EMOTION_EMOJIS } from '../constants.js';

export function EmotionDisplay({ prediction }) {
  const emojiRef = useRef(null);
  const prevRef  = useRef(null);

  useEffect(() => {
    if (!prediction || prediction.emotion === prevRef.current) return;
    prevRef.current = prediction.emotion;
    if (emojiRef.current) {
      emojiRef.current.classList.remove('fresh');
      void emojiRef.current.offsetWidth;   // reflow to restart animation
      emojiRef.current.classList.add('fresh');
    }
  }, [prediction?.emotion]);

  if (!prediction) {
    return (
      <div className="emotion-display">
        <div className="emotion-placeholder">
          Start recording or upload a file<br />to see emotion predictions
        </div>
      </div>
    );
  }

  const { emotion, confidence, latency_ms } = prediction;
  const color = EMOTION_COLORS[emotion] ?? '#94a3b8';
  const emoji = EMOTION_EMOJIS[emotion] ?? '❓';

  return (
    <div className="emotion-display">
      <span ref={emojiRef} className="emotion-emoji">{emoji}</span>
      <span className="emotion-name" style={{ color }}>{emotion}</span>
      <div className="emotion-meta">
        <span className="chip">{(confidence * 100).toFixed(0)}% confidence</span>
        <span className="chip">{latency_ms} ms</span>
      </div>
    </div>
  );
}
