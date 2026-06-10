"""
Shared fixtures available to all test modules.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
import soundfile as sf

SR       = 22050
DURATION = 3.0
N        = int(SR * DURATION)


@pytest.fixture
def audio_cfg():
    return {
        "sample_rate": SR,
        "duration":    DURATION,
        "n_mfcc":      40,
        "n_mels":      128,
        "n_fft":       2048,
        "hop_length":  512,
        "f_min":       20.0,
        "f_max":       8000.0,
        "use_delta":   True,
        "normalize":   True,
    }


@pytest.fixture
def sine_audio():
    """3-second 440 Hz sine wave as float32 numpy array."""
    t = np.linspace(0, DURATION, N, endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def sine_wav_path(tmp_path, sine_audio):
    """Sine wave written to a temp .wav file; returns path string."""
    p = tmp_path / "sine.wav"
    sf.write(str(p), sine_audio, SR)
    return str(p)


@pytest.fixture
def sine_wav_bytes(sine_audio):
    """Sine wave as raw WAV bytes (in-memory)."""
    buf = io.BytesIO()
    sf.write(buf, sine_audio, SR, format="WAV")
    return buf.getvalue()
