"""
Tests for src/features.py — audio feature extraction pipeline.
"""
import numpy as np
import pytest
import soundfile as sf

from src.features import extract_audio_features, load_audio, mel_spectrogram, mfcc_features

SR  = 22050
DUR = 3.0
N   = int(SR * DUR)


def _write_wav(tmp_path, audio, sr=SR, name="audio.wav"):
    p = tmp_path / name
    sf.write(str(p), audio, sr)
    return str(p)


# ── load_audio ────────────────────────────────────────────


def test_load_audio_short_is_padded(tmp_path):
    p = _write_wav(tmp_path, np.zeros(SR, dtype=np.float32))  # 1 s
    out = load_audio(p, SR, DUR)
    assert len(out) == N


def test_load_audio_long_is_cropped(tmp_path):
    p = _write_wav(tmp_path, np.zeros(SR * 6, dtype=np.float32))  # 6 s
    out = load_audio(p, SR, DUR)
    assert len(out) == N


def test_load_audio_exact_length_unchanged(tmp_path):
    p = _write_wav(tmp_path, np.zeros(N, dtype=np.float32))
    out = load_audio(p, SR, DUR)
    assert len(out) == N


def test_load_audio_crop_is_centered(tmp_path):
    # Mark first and last sample so we can verify center crop
    audio = np.zeros(SR * 5, dtype=np.float32)
    audio[0]  = 1.0
    audio[-1] = 1.0
    p = _write_wav(tmp_path, audio)
    out = load_audio(p, SR, DUR)
    # Center crop should not include index 0 or last sample
    assert out[0]  != pytest.approx(1.0)
    assert out[-1] != pytest.approx(1.0)


def test_load_audio_resamples(tmp_path):
    """Audio recorded at 8 kHz should be upsampled to target SR."""
    audio = np.zeros(8000 * 3, dtype=np.float32)
    p = _write_wav(tmp_path, audio, sr=8000)
    out = load_audio(p, SR, DUR)
    assert len(out) == N


# ── mel_spectrogram ───────────────────────────────────────


def test_mel_spectrogram_shape():
    n_mels = 128
    audio  = np.random.randn(N).astype(np.float32)
    mel    = mel_spectrogram(audio, SR, n_mels=n_mels, n_fft=2048, hop_length=512)
    assert mel.shape[0] == n_mels
    assert mel.shape[1] > 0


def test_mel_spectrogram_normalized_mean_near_zero():
    audio = np.random.randn(N).astype(np.float32)
    mel   = mel_spectrogram(audio, SR, normalize=True)
    assert abs(mel.mean()) < 0.15


def test_mel_spectrogram_no_nan_on_silence():
    audio = np.zeros(N, dtype=np.float32)
    mel   = mel_spectrogram(audio, SR, normalize=True)
    assert not np.any(np.isnan(mel))
    assert not np.any(np.isinf(mel))


def test_mel_spectrogram_without_normalization():
    audio = np.random.randn(N).astype(np.float32)
    mel   = mel_spectrogram(audio, SR, normalize=False)
    # Log-mel should be non-positive (power_to_db with ref=max)
    assert mel.max() <= 0.01


# ── mfcc_features ─────────────────────────────────────────


def test_mfcc_shape_with_delta():
    n_mfcc = 40
    audio  = np.random.randn(N).astype(np.float32)
    feats  = mfcc_features(audio, SR, n_mfcc=n_mfcc, use_delta=True)
    assert feats.shape[0] == 3 * n_mfcc  # mfcc + Δ + ΔΔ


def test_mfcc_shape_without_delta():
    n_mfcc = 40
    audio  = np.random.randn(N).astype(np.float32)
    feats  = mfcc_features(audio, SR, n_mfcc=n_mfcc, use_delta=False)
    assert feats.shape[0] == n_mfcc


def test_mfcc_no_nan(sine_audio):
    feats = mfcc_features(sine_audio, SR, normalize=True)
    assert not np.any(np.isnan(feats))
    assert not np.any(np.isinf(feats))


# ── extract_audio_features (combined pipeline) ────────────


def test_extract_returns_mel_and_mfcc(tmp_path, audio_cfg, sine_audio):
    p     = _write_wav(tmp_path, sine_audio)
    feats = extract_audio_features(p, audio_cfg)
    assert "mel"  in feats
    assert "mfcc" in feats


def test_extract_mel_shape(tmp_path, audio_cfg, sine_audio):
    p   = _write_wav(tmp_path, sine_audio)
    mel = extract_audio_features(p, audio_cfg)["mel"]
    assert mel.shape[0] == audio_cfg["n_mels"]
    assert mel.ndim == 2


def test_extract_mfcc_shape(tmp_path, audio_cfg, sine_audio):
    p    = _write_wav(tmp_path, sine_audio)
    mfcc = extract_audio_features(p, audio_cfg)["mfcc"]
    assert mfcc.shape[0] == 3 * audio_cfg["n_mfcc"]  # delta enabled
    assert mfcc.ndim == 2


def test_extract_silence_no_nan(tmp_path, audio_cfg):
    p     = _write_wav(tmp_path, np.zeros(N, dtype=np.float32))
    feats = extract_audio_features(p, audio_cfg)
    for key, arr in feats.items():
        assert not np.any(np.isnan(arr)), f"NaN in {key}"
        assert not np.any(np.isinf(arr)), f"Inf in {key}"
