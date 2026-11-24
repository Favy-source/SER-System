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
import sys
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.constants import LANDMARK_COORDS, LANDMARK_DIM, N_FACE_LANDMARKS
from src.features import normalize_landmarks


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
        visual: Optional["VisualStreamBuffer"] = None,
    ):
        self.engine         = engine
        self.input_sr       = input_sr
        self.target_sr      = engine.sr
        self.window_samples = int(input_sr * window_sec)
        self.hop_samples    = int(input_sr * hop_sec)
        # Audio drives the clock: when this buffer fires, it asks the visual
        # buffer for whatever it currently holds. Both windows are anchored to
        # "now", which matches how training paired one clip with one label.
        self.visual         = visual

        self._buf: np.ndarray = np.zeros(0, dtype=np.float32)
        self._since_last: int = 0

    # ------------------------------------------------------------------

    def push(self, chunk: bytes) -> Optional[dict]:
        """
        Ingest a PCM chunk.  Returns a prediction dict when a full window
        has accumulated and the hop interval has elapsed, otherwise None.
        """
        if len(chunk) % 4 != 0:
            return {"_error": f"PCM chunk length {len(chunk)} is not a multiple of 4 bytes"}
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

            # Sample the visual state at the moment the audio window closes,
            # BEFORE any expensive work. Reading it after resampling made the
            # freshness check include our own compute time, so a slow call — the
            # first one pays a multi-second lazy `import librosa` — aged a
            # perfectly good face track past stale_after and silently dropped
            # the visual stream.
            visual_window = self.visual.window() if self.visual is not None else None

            if self.input_sr != self.target_sr:
                import librosa
                window = librosa.resample(window, orig_sr=self.input_sr, target_sr=self.target_sr)

            try:
                return self.engine.predict(window, visual_window)
            except Exception as exc:
                return {"_error": str(exc)}

        return None

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        self._since_last = 0


class VisualStreamBuffer:
    """
    Rolling window of face-landmark frames from a live video stream.

    The client (browser MediaPipe FaceLandmarker) sends *raw* landmark
    coordinates; normalisation happens here via the shared
    src.features.normalize_landmarks, so the live path and the offline training
    path apply byte-identical maths. Reimplementing the normalisation in
    JavaScript would be train/serve skew of exactly the kind the shared
    src/features.py import exists to prevent.

    Unlike audio there is no hop gate: the audio buffer decides when inference
    fires and simply asks this one for whatever it currently holds. Video and
    audio arrive at unrelated rates (~10-30 fps vs ~125 blocks/s), so aligning
    them frame-by-frame is neither possible nor useful for a window classifier.
    Both windows are anchored to "now", which is the same contract training
    used: one clip, one label.
    """

    def __init__(self, max_frames: int = 75, stale_after: float = 2.0):
        self.max_frames = max_frames
        self.stale_after = stale_after           # seconds before we call it dead
        self._frames: list = []
        self._last_ts: Optional[float] = None
        self._received = 0
        self._rejected = 0

    # ------------------------------------------------------------------

    def push(self, coords: np.ndarray, ts: Optional[float] = None) -> None:
        """Ingest one frame of raw (n_landmarks, 3) coordinates."""
        import time
        self._frames.append(normalize_landmarks(coords))
        if len(self._frames) > self.max_frames:
            self._frames = self._frames[-self.max_frames:]
        self._last_ts = time.perf_counter() if ts is None else ts
        self._received += 1

    def push_bytes(self, chunk: bytes) -> None:
        """Ingest a raw float32 landmark frame: n_landmarks * 3 values."""
        if len(chunk) % 4 != 0:
            self._rejected += 1
            raise ValueError(
                f"landmark frame length {len(chunk)} bytes is not a multiple of 4 (float32)"
            )
        flat = np.frombuffer(chunk, dtype=np.float32)
        if flat.size % LANDMARK_COORDS:
            self._rejected += 1
            raise ValueError(
                f"landmark frame has {flat.size} floats, not a multiple of "
                f"{LANDMARK_COORDS}"
            )
        self.push(flat.reshape(-1, LANDMARK_COORDS))

    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """True when a usable, recent face track exists.

        Goes false when the client stops sending — the user walks away, covers
        the camera, or face detection drops out. The caller then falls back to
        an audio-only prediction rather than feeding the model a stale face.
        """
        import time
        if not self._frames or self._last_ts is None:
            return False
        return (time.perf_counter() - self._last_ts) <= self.stale_after

    def window(self) -> Optional[np.ndarray]:
        """(max_frames, LANDMARK_DIM) zero-padded at the END, or None if stale.

        Padding at the end matches extract_visual_features, so a short live
        track is shaped exactly like a short training clip.
        """
        if not self.is_active():
            return None
        seq = np.stack(self._frames)                       # (T, LANDMARK_DIM)
        if len(seq) < self.max_frames:
            pad = np.zeros((self.max_frames - len(seq), LANDMARK_DIM), dtype=np.float32)
            seq = np.vstack([seq, pad])
        return seq[:self.max_frames].astype(np.float32)

    def stats(self) -> dict:
        return {
            "frames_buffered": len(self._frames),
            "frames_received": self._received,
            "frames_rejected": self._rejected,
            "active": self.is_active(),
            "expected_landmarks": N_FACE_LANDMARKS,
        }

    def reset(self) -> None:
        self._frames = []
        self._last_ts = None
