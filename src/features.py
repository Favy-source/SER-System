import warnings
from typing import Optional, Tuple

import numpy as np
import librosa

from .constants import LANDMARK_DIM, N_FACE_LANDMARKS, REFINE_LANDMARKS

warnings.filterwarnings("ignore")

try:
    import cv2
    import mediapipe as mp
    _MEDIAPIPE = True
except ImportError:
    _MEDIAPIPE = False


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


def extract_visual_features(
    video_path: str,
    max_frames: int = 75,
    frame_size: Tuple[int, int] = (112, 112),
) -> Optional[np.ndarray]:
    if not _MEDIAPIPE:
        return None

    mp_face = mp.solutions.face_mesh
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    frames = []
    with mp_face.FaceMesh(
        static_image_mode=False, max_num_faces=1,
        refine_landmarks=REFINE_LANDMARKS, min_detection_confidence=0.5,
    ) as mesh:
        while cap.isOpened() and len(frames) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.resize(frame, frame_size)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = mesh.process(rgb)
            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0].landmark
                # Fail loudly rather than writing arrays the models cannot load.
                # preprocess.py collects this per file into errors_visual.txt.
                if len(lm) != N_FACE_LANDMARKS:
                    raise ValueError(
                        f"FaceMesh returned {len(lm)} landmarks, expected "
                        f"{N_FACE_LANDMARKS} (REFINE_LANDMARKS={REFINE_LANDMARKS}). "
                        f"Reconcile src/constants.py with your mediapipe version."
                    )
                coords = np.array([[l.x, l.y, l.z] for l in lm], dtype=np.float32)
                coords -= coords.mean(0)
                scale = np.linalg.norm(coords, axis=1).max()
                coords /= scale + 1e-8
                frames.append(coords.flatten())  # (LANDMARK_DIM,)
    cap.release()

    if not frames:
        return None

    seq = np.stack(frames)  # (T, LANDMARK_DIM)
    if len(seq) < max_frames:
        pad = np.zeros((max_frames - len(seq), LANDMARK_DIM), dtype=np.float32)
        seq = np.vstack([seq, pad])
    return seq[:max_frames]