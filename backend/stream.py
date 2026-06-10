"""
AudioStreamBuffer — sliding-window inference over a live PCM stream.

Protocol (WebSocket):
  Client → server (text):    JSON handshake  {"sample_rate": 16000}
  Client → server (text):    control frame   {"type": "reset"} | {"type": "ping"}
  Client → server (bytes):   raw float32 PCM chunk (any size)

  Server → client (text):    {"type": "ready",      "payload": {"sample_rate": ...}}
                              {"type": "prediction", "payload": <PredictionResult>}
                              {"type": "info",       "payload": {"message": ...}}
                              {"type": "error",      "payload": {"message": ...}}
"""
from typing import Optional

import numpy as np


class AudioStreamBuffer:
    """
    Accumulates raw float32 PCM chunks and triggers inference on a
    sliding window once enough audio has accumulated.

    window_sec  — length of each inference window (should match model training duration)
    hop_sec     — minimum gap between successive inferences
    """

    def __init__(
        self,
        engine,
        input_sr: int   = 16000,
        window_sec: float = 3.0,
        hop_sec: float    = 0.5,
    ):
        self.engine         = engine
        self.input_sr       = input_sr
        self.target_sr      = engine.sr
        self.window_samples = int(input_sr * window_sec)
        self.hop_samples    = int(input_sr * hop_sec)

        self._buf: np.ndarray = np.zeros(0, dtype=np.float32)
        self._since_last: int = 0

    # ------------------------------------------------------------------

    def push(self, chunk: bytes) -> Optional[dict]:
        """
        Ingest a PCM chunk.  Returns a prediction dict when a full window
        has accumulated and the hop interval has elapsed, otherwise None.
        """
        pcm = np.frombuffer(chunk, dtype=np.float32)
        self._buf = np.concatenate([self._buf, pcm])
        self._since_last += len(pcm)

        # keep at most 2 windows to bound memory
        max_buf = self.window_samples * 2
        if len(self._buf) > max_buf:
            self._buf = self._buf[-max_buf:]

        if len(self._buf) >= self.window_samples and self._since_last >= self.hop_samples:
            self._since_last = 0
            window = self._buf[-self.window_samples:].copy()

            if self.input_sr != self.target_sr:
                import librosa
                window = librosa.resample(window, orig_sr=self.input_sr, target_sr=self.target_sr)

            try:
                return self.engine.predict(window)
            except Exception as exc:
                return {"_error": str(exc)}

        return None

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        self._since_last = 0
