"""
Tests for the FastAPI backend — HTTP endpoints and WebSocket streaming.

Engine is mocked so no trained checkpoint is required.
"""
import io
import json
import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from src.datasets import UNIFIED

# ── Shared mock data ──────────────────────────────────────

MOCK_PRED = {
    "emotion":       "happy",
    "confidence":    0.87,
    "probabilities": {e: (0.87 if e == "happy" else round(0.13 / 5, 4)) for e in UNIFIED},
    "latency_ms":    11.5,
    "model_name":    "audio_cnn_lstm",
}


def _make_engine():
    eng = MagicMock()
    eng.model_name              = "audio_cnn_lstm"
    eng.device                  = "cpu"
    eng.sr                      = 22050
    eng.predict.return_value            = MOCK_PRED
    eng.predict_from_bytes.return_value = MOCK_PRED
    return eng


def _wav_bytes(duration=3.0, sr=22050):
    t     = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf   = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def client():
    """TestClient with no model loaded (engine = None)."""
    from backend.main import app
    with patch("backend.main._load_engine", return_value=None):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_m():
    """TestClient with a mocked InferenceEngine."""
    from backend.main import app
    with patch("backend.main._load_engine", return_value=_make_engine()):
        with TestClient(app) as c:
            yield c


# ── GET /health ───────────────────────────────────────────


def test_health_status_200(client):
    assert client.get("/health").status_code == 200


def test_health_no_model(client):
    data = client.get("/health").json()
    assert data["model_loaded"] is False
    assert data["status"] == "ok"


def test_health_with_model(client_m):
    data = client_m.get("/health").json()
    assert data["model_loaded"] is True
    assert data["model_name"] == "audio_cnn_lstm"
    assert data["device"] == "cpu"
    assert data["sample_rate"] == 22050


def test_health_schema(client_m):
    data = client_m.get("/health").json()
    for field in ("status", "model_loaded", "model_name", "device", "sample_rate"):
        assert field in data


# ── GET /models ───────────────────────────────────────────


def test_models_returns_200(client):
    assert client.get("/models").status_code == 200


def test_models_has_checkpoints_key(client):
    data = client.get("/models").json()
    assert "checkpoints" in data
    assert isinstance(data["checkpoints"], list)


# ── POST /predict/audio ───────────────────────────────────


def test_predict_audio_503_when_no_model(client):
    r = client.post("/predict/audio", files={"file": ("t.wav", b"", "audio/wav")})
    assert r.status_code == 503


def test_predict_audio_422_on_empty_file(client_m):
    r = client_m.post("/predict/audio", files={"file": ("empty.wav", b"", "audio/wav")})
    assert r.status_code == 422


def test_predict_audio_200_on_valid_wav(client_m):
    r = client_m.post("/predict/audio", files={"file": ("s.wav", _wav_bytes(), "audio/wav")})
    assert r.status_code == 200


def test_predict_audio_response_shape(client_m):
    data = client_m.post("/predict/audio",
                         files={"file": ("s.wav", _wav_bytes(), "audio/wav")}).json()
    assert data["emotion"] in UNIFIED
    assert 0.0 <= data["confidence"] <= 1.0
    assert set(data["probabilities"].keys()) == set(UNIFIED)
    assert "latency_ms" in data
    assert "model_name" in data


def test_predict_audio_probabilities_sum_to_one(client_m):
    data  = client_m.post("/predict/audio",
                          files={"file": ("s.wav", _wav_bytes(), "audio/wav")}).json()
    total = sum(data["probabilities"].values())
    assert abs(total - 1.0) < 0.02


def test_predict_audio_calls_engine(client_m):
    """Engine.predict_from_bytes must be called exactly once per request."""
    from backend import main as m
    client_m.post("/predict/audio", files={"file": ("s.wav", _wav_bytes(), "audio/wav")})
    m.engine.predict_from_bytes.assert_called_once()


# ── POST /predict/switch ──────────────────────────────────


def test_switch_model_404_for_missing_ckpt():
    # Use a fresh patch that returns None for any path (simulates missing file)
    # so the real path-existence check isn't short-circuited by the global fixture.
    from backend.main import app
    with patch("backend.main._load_engine", return_value=None):
        with TestClient(app) as c:
            r = c.post("/predict/switch?checkpoint=does_not_exist.pt")
    assert r.status_code == 404


def test_switch_model_success(client_m, tmp_path):
    new_eng = _make_engine()
    new_eng.model_name = "attention"
    ckpt = tmp_path / "model.pt"
    ckpt.touch()
    with patch("backend.main._load_engine", return_value=new_eng):
        r = client_m.post(f"/predict/switch?checkpoint={ckpt}")
    assert r.status_code == 200
    assert r.json()["model"] == "attention"


# ── WebSocket /ws/stream ──────────────────────────────────


def test_ws_no_model_sends_error(client):
    with client.websocket_connect("/ws/stream") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "not loaded" in msg["payload"]["message"].lower()


def test_ws_handshake_returns_ready(client_m):
    with client_m.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"sample_rate": 16000}))
        msg = ws.receive_json()
    assert msg["type"] == "ready"
    assert msg["payload"]["sample_rate"] == 16000
    assert msg["payload"]["model"] == "audio_cnn_lstm"


def test_ws_ready_contains_window_info(client_m):
    with client_m.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"sample_rate": 16000}))
        payload = ws.receive_json()["payload"]
    assert "window_sec" in payload
    assert "hop_sec" in payload


def test_ws_prediction_after_window_fills(client_m):
    """Sending ≥3 s of PCM at 16 kHz should trigger one prediction."""
    sr            = 16000
    window_s      = 3.0
    hop_s         = 0.5
    chunk         = 4096
    window_n      = int(sr * window_s)    # 48 000
    n_chunks      = math.ceil(window_n / chunk) + 1
    silent        = np.zeros(chunk, dtype=np.float32).tobytes()

    with client_m.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"sample_rate": sr}))
        ws.receive_json()                 # ready

        for _ in range(n_chunks):
            ws.send_bytes(silent)

        pred = ws.receive_json()

    assert pred["type"] == "prediction"
    assert pred["payload"]["emotion"] == "happy"
    assert set(pred["payload"]["probabilities"].keys()) == set(UNIFIED)


def test_ws_reset_clears_buffer(client_m):
    with client_m.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"sample_rate": 16000}))
        ws.receive_json()                 # ready

        ws.send_text(json.dumps({"type": "reset"}))
        msg = ws.receive_json()

    assert msg["type"] == "info"
    text = msg["payload"].get("message", "").lower()
    assert "clear" in text or "reset" in text


def test_ws_ping_returns_pong(client_m):
    with client_m.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"sample_rate": 16000}))
        ws.receive_json()                 # ready

        ws.send_text(json.dumps({"type": "ping"}))
        msg = ws.receive_json()

    assert msg["type"] == "info"
    assert "pong" in msg["payload"].get("message", "").lower()
