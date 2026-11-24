from typing import Optional, Tuple

import numpy as np
import librosa

from .constants import (
    LANDMARK_COORDS,
    LANDMARK_DIM,
    N_FACE_LANDMARKS,
    REFINE_LANDMARKS,
)


# ---------------------------------------------------------------------------
# MediaPipe availability
# ---------------------------------------------------------------------------
#
# We use the **Tasks** API (mediapipe.tasks.python.vision.FaceLandmarker), not
# the old `mp.solutions.face_mesh` one. The legacy solutions namespace was
# REMOVED in mediapipe 1.0 — `import mediapipe` still succeeds, so an
# ImportError guard does not catch it and the failure only appears at call time
# as `AttributeError: module 'mediapipe' has no attribute 'solutions'`.
# preprocess.py catches per-file exceptions, so that would have logged every
# video as an error and written no landmarks at all, quietly producing an
# audio-only training set that looked like it had worked.
#
# The Tasks API exists in 0.10.x as well, so this path covers both.
#
# The Tasks FaceLandmarker has no refine_landmarks switch: it always returns 478
# points (468 base mesh + 10 iris) — the same as the browser's FaceLandmarker.
# normalize_landmarks() keeps the leading N_FACE_LANDMARKS, so both feed a
# 468-point model unchanged.
try:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as _mp_python
    from mediapipe.tasks.python import vision as _mp_vision
    _MEDIAPIPE = True
    _MEDIAPIPE_ERROR = None
except Exception as _exc:            # ImportError, or a reshuffled namespace
    _MEDIAPIPE = False
    _MEDIAPIPE_ERROR = f"{type(_exc).__name__}: {_exc}"


# Where to find face_landmarker.task. The front end already vendors it via
# `npm run setup:mediapipe`, so the default reuses that download rather than
# fetching a second copy.
_MODEL_ENV = "FACE_LANDMARKER_MODEL"
_DEFAULT_MODEL_PATHS = (
    "frontend/public/mediapipe/models/face_landmarker.task",
    "models/face_landmarker.task",
)


def face_landmarker_model_path() -> Optional[str]:
    """Locate face_landmarker.task, or None with the reason logged by callers."""
    import os
    from pathlib import Path as _Path

    env = os.getenv(_MODEL_ENV)
    if env:
        return env if _Path(env).exists() else None
    for cand in _DEFAULT_MODEL_PATHS:
        if _Path(cand).exists():
            return cand
    return None


def load_audio(path: str, sr: int = 22050, duration: float = 3.0) -> np.ndarray:
    audio, _ = librosa.load(path, sr=sr, mono=True)
    n = int(sr * duration)
    if len(audio) >= n:
        start = (len(audio) - n) // 2
        audio = audio[start: start + n]
    else:
        pad = n - len(audio)
        audio = np.pad(audio, (pad // 2, pad - pad // 2))
    return audio


def mel_spectrogram(
    audio: np.ndarray,
    sr: int,
    n_mels: int = 128,
    n_fft: int = 2048,
    hop_length: int = 512,
    f_min: float = 20.0,
    f_max: float = 8000.0,
    normalize: bool = True,
) -> np.ndarray:
    mel = librosa.feature.melspectrogram(
        y=audio, sr=sr, n_mels=n_mels, n_fft=n_fft,
        hop_length=hop_length, fmin=f_min, fmax=f_max,
    )
    log_mel = librosa.power_to_db(mel, ref=np.max)
    if normalize:
        log_mel = (log_mel - log_mel.mean()) / (log_mel.std() + 1e-8)
    return log_mel  # (n_mels, T)


def mfcc_features(
    audio: np.ndarray,
    sr: int,
    n_mfcc: int = 40,
    n_fft: int = 2048,
    hop_length: int = 512,
    use_delta: bool = True,
    normalize: bool = True,
) -> np.ndarray:
    mfcc = librosa.feature.mfcc(
        y=audio, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop_length,
    )
    if use_delta:
        d1 = librosa.feature.delta(mfcc)
        d2 = librosa.feature.delta(mfcc, order=2)
        mfcc = np.vstack([mfcc, d1, d2])  # (3*n_mfcc, T)
    if normalize:
        mfcc = (mfcc - mfcc.mean(1, keepdims=True)) / (mfcc.std(1, keepdims=True) + 1e-8)
    return mfcc


def extract_audio_features(path: str, cfg: dict) -> dict:
    audio = load_audio(path, cfg["sample_rate"], cfg["duration"])
    mel = mel_spectrogram(
        audio, cfg["sample_rate"], cfg["n_mels"], cfg["n_fft"],
        cfg["hop_length"], cfg["f_min"], cfg["f_max"], cfg["normalize"],
    )
    mfcc = mfcc_features(
        audio, cfg["sample_rate"], cfg["n_mfcc"], cfg["n_fft"],
        cfg["hop_length"], cfg["use_delta"], cfg["normalize"],
    )
    return {"mel": mel, "mfcc": mfcc}


def normalize_landmarks(coords: np.ndarray) -> np.ndarray:
    """Translation- and scale-normalise one frame of face landmarks.

    coords: (n_landmarks, 3) raw (x, y, z) -> (LANDMARK_DIM,) flattened.

    Subtracting the centroid removes head position within the frame; dividing
    by the maximum radius removes apparent face size, which varies with
    distance from the camera. What survives is the *shape* of the face, which
    is where expression lives. Without both steps a network can reach low
    training loss by tracking head movement, which correlates with emotion in
    acted corpora but will not generalise.

    Accepts more landmarks than configured and keeps the leading
    N_FACE_LANDMARKS. MediaPipe appends the 10 iris points after the 468-point
    base mesh, so the base mesh is always the leading block — which lets a
    browser-side FaceLandmarker (478 points) feed a model trained on 468
    without the two implementations having to agree on refine_landmarks.

    This is the single normalisation used by BOTH the offline training path and
    the live serving path. Reimplementing it per call site — in JavaScript, say
    — would be textbook train/serve skew.
    """
    coords = np.asarray(coords, dtype=np.float32)
    if coords.ndim != 2 or coords.shape[1] != LANDMARK_COORDS:
        raise ValueError(
            f"expected (n_landmarks, {LANDMARK_COORDS}) coordinates, got {coords.shape}"
        )
    if len(coords) < N_FACE_LANDMARKS:
        raise ValueError(
            f"got {len(coords)} landmarks, need at least {N_FACE_LANDMARKS}"
        )
    coords = coords[:N_FACE_LANDMARKS]

    coords = coords - coords.mean(0)
    scale = np.linalg.norm(coords, axis=1).max()
    return (coords / (scale + 1e-8)).flatten()   # (LANDMARK_DIM,)


def extract_visual_features(
    video_path: str,
    max_frames: int = 75,
    frame_size: Tuple[int, int] = (112, 112),
) -> Optional[np.ndarray]:
    """Extract a normalised face-landmark sequence from a video.

    Returns (max_frames, LANDMARK_DIM) float32, or None when mediapipe is
    unavailable, the model file is missing, the video cannot be opened, or no
    face was detected in any frame.

    Uses the MediaPipe **Tasks** FaceLandmarker in VIDEO mode. Requires
    face_landmarker.task — see face_landmarker_model_path() for where it is
    looked up, and `cd frontend && npm run setup:mediapipe` to fetch it.
    """
    if not _MEDIAPIPE:
        return None

    model_path = face_landmarker_model_path()
    if model_path is None:
        # Loud, because silently returning None here would produce an
        # audio-only training set that looks like a successful run.
        raise FileNotFoundError(
            "face_landmarker.task not found. Fetch it with "
            "`cd frontend && npm run setup:mediapipe`, or set "
            f"${_MODEL_ENV} to its path. Looked in: {list(_DEFAULT_MODEL_PATHS)}"
        )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    options = _mp_vision.FaceLandmarkerOptions(
        base_options=_mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=_mp_vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
    )

    frames = []
    with _mp_vision.FaceLandmarker.create_from_options(options) as landmarker:
        idx = 0
        while cap.isOpened() and len(frames) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.resize(frame, frame_size)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # VIDEO mode requires strictly increasing timestamps. Derive them
            # from the frame index and the container's fps rather than a wall
            # clock, so the same file always yields the same sequence.
            timestamp_ms = int(idx * 1000 / fps)
            idx += 1

            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            if result.face_landmarks:
                lm = result.face_landmarks[0]
                # Fail loudly rather than writing arrays the models cannot load.
                # preprocess.py collects this per file into errors_visual.txt.
                if len(lm) < N_FACE_LANDMARKS:
                    raise ValueError(
                        f"FaceLandmarker returned {len(lm)} landmarks, need at least "
                        f"{N_FACE_LANDMARKS}. Reconcile src/constants.py "
                        f"(REFINE_LANDMARKS={REFINE_LANDMARKS}) with your mediapipe version."
                    )
                frames.append(normalize_landmarks(
                    np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)
                ))
    cap.release()

    if not frames:
        return None

    seq = np.stack(frames)  # (T, LANDMARK_DIM)
    if len(seq) < max_frames:
        pad = np.zeros((max_frames - len(seq), LANDMARK_DIM), dtype=np.float32)
        seq = np.vstack([seq, pad])
    return seq[:max_frames]