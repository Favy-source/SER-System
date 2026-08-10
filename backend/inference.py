"""
InferenceEngine — loads a trained checkpoint and runs predictions.

Supports:
  - predict(audio_array)           raw numpy float32 PCM
  - predict_from_bytes(bytes)      any format readable by soundfile
  - predict_from_file(path)        audio file on disk
"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import torch
import torch.nn.functional as F
import yaml

from src.constants import LANDMARK_DIM
from src.datasets import UNIFIED, IDX2LABEL
from src.features import mel_spectrogram, mfcc_features
from src.models.builder import build_model, is_multimodal


class InferenceEngine:
    def __init__(
        self,
        checkpoint_path: str,
        config_path: str = "config/settings.yaml",
    ):
        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        ckpt = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        self.model_name = ckpt["model_name"]
        self.feature     = ckpt.get("feature", "mel")
        self.multimodal  = is_multimodal(self.model_name)

        # Architecture comes from the checkpoint's own config, and the feature
        # type it was trained on, so the LSTM width matches the state dict.
        model = build_model(self.model_name, ckpt["cfg"], len(UNIFIED), self.feature)
        model.load_state_dict(ckpt["model"])
        model.eval()
        self.model = model.to(self.device)

        acfg    = self.cfg["audio"]
        self.sr = acfg["sample_rate"]
        self._duration   = acfg["duration"]
        self._audio_cfg  = acfg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pad_or_crop(self, audio: np.ndarray) -> np.ndarray:
        n = int(self.sr * self._duration)
        if len(audio) >= n:
            start = (len(audio) - n) // 2
            return audio[start: start + n]
        pad = n - len(audio)
        return np.pad(audio, (pad // 2, pad - pad // 2))

    def _to_tensor(self, audio: np.ndarray) -> torch.Tensor:
        acfg = self._audio_cfg
        if self.feature == "mel":
            feat = mel_spectrogram(
                audio, self.sr, acfg["n_mels"], acfg["n_fft"],
                acfg["hop_length"], acfg["f_min"], acfg["f_max"], acfg["normalize"],
            )
            return torch.from_numpy(feat).float().unsqueeze(0).unsqueeze(0).to(self.device)
        # mfcc — same rank as the mel branch: (batch, channel, freq, time).
        # A single unsqueeze left this 3-D and Conv2d rejected it.
        feat = mfcc_features(
            audio, self.sr, acfg["n_mfcc"], acfg["n_fft"],
            acfg["hop_length"], acfg["use_delta"], acfg["normalize"],
        )
        return torch.from_numpy(feat).float().unsqueeze(0).unsqueeze(0).to(self.device)

    def _zero_visual(self) -> torch.Tensor:
        vcfg = self.cfg["visual"]
        return torch.zeros(1, vcfg["max_frames"], LANDMARK_DIM, device=self.device)

    # ------------------------------------------------------------------
    # Public prediction API
    # ------------------------------------------------------------------

    def predict(self, audio: np.ndarray) -> dict:
        """Run inference on a raw float32 mono PCM array (any length)."""
        t0 = time.perf_counter()

        audio = self._pad_or_crop(audio.astype(np.float32))
        tensor = self._to_tensor(audio)

        with torch.no_grad():
            if self.multimodal:
                logits = self.model(tensor, self._zero_visual())
            else:
                logits = self.model(tensor)
            probs = F.softmax(logits, dim=1)[0].cpu().numpy()

        idx     = int(probs.argmax())
        latency = (time.perf_counter() - t0) * 1000

        return {
            "emotion":       IDX2LABEL[idx],
            "confidence":    round(float(probs[idx]), 4),
            "probabilities": {e: round(float(probs[i]), 4) for i, e in enumerate(UNIFIED)},
            "latency_ms":    round(latency, 2),
            "model_name":    self.model_name,
        }

    def predict_from_bytes(self, audio_bytes: bytes) -> dict:
        """Accept any audio format supported by soundfile (wav, flac, ogg, …)."""
        import soundfile as sf
        buf = io.BytesIO(audio_bytes)
        audio, sr = sf.read(buf, always_2d=False, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != self.sr:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sr)
        return self.predict(audio)

    def predict_from_file(self, path: str) -> dict:
        """Load from a file path on disk."""
        with open(path, "rb") as fh:
            return self.predict_from_bytes(fh.read())
