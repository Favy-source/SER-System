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
    "modalities":    ["audio"],
    "visual_active": False,
}

MAX_FRAMES = 75


def _make_engine(model_name="audio_cnn_lstm", multimodal=False):
    """Mock engine. Attributes mirror the real InferenceEngine surface that
    main.py reads — model_name, device, sr, cfg, multimodal — because the
    WebSocket handshake serialises several of them into the ready payload."""
    eng = MagicMock()
    eng.model_name = model_name
    eng.device     = "cpu"
    eng.sr         = 22050
    eng.multimodal = multimodal
    eng.untrained  = False
    eng.cfg        = {"visual": {"max_frames": MAX_FRAMES}}
    pred = {**MOCK_PRED, "model_name": model_name}
    eng.predict.return_value            = pred
    eng.predict_from_bytes.return_value = pred
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
    """TestClient with a mocked unimodal InferenceEngine."""
    from backend.main import app
    with patch("backend.main._load_engine", return_value=_make_engine()):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def engine_mm():
    """A mocked fusion engine, so the visual path is reachable."""
    return _make_engine("attention", multimodal=True)


@pytest.fixture
def client_mm(engine_mm):
    """TestClient with a mocked multimodal (fusion) InferenceEngine."""
    from backend.main import app
    with patch("backend.main._load_engine", return_value=engine_mm):
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


# ── Visual streaming over the WebSocket ───────────────────
#
# Before this path existed, fusion checkpoints were served with a zero visual
# tensor: the model loaded and predicted, but its visual branch contributed
# nothing, so a "multimodal" prediction was audio-only in everything but name.
# These tests pin the opt-in negotiation, the tagged framing, and — most
# importantly — that the response reports which modalities actually ran.

import struct

import numpy as np

from src.constants import LANDMARK_COORDS, N_FACE_LANDMARKS

TAG_AUDIO, TAG_LANDMARKS = 0, 1


def _tagged(tag: int, payload: bytes) -> bytes:
    """4-byte header: tag + 3 reserved, keeping the float32 payload aligned."""
    return struct.pack("<Bxxx", tag) + payload


def _landmark_frame(n=None) -> bytes:
    n = n or N_FACE_LANDMARKS
    return np.random.rand(n, LANDMARK_COORDS).astype(np.float32).tobytes()


def _pcm(seconds=3.2, sr=16000) -> bytes:
    return np.zeros(int(sr * seconds), dtype=np.float32).tobytes()


def _handshake(ws, **extra):
    ws.send_text(json.dumps({"sample_rate": 16000, **extra}))
    return ws.receive_json()


# --- negotiation ---


def test_ws_visual_disabled_by_default(client_mm):
    """Opt-in only: a plain handshake must not enable visual."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        ready = _handshake(ws)
    assert ready["payload"]["visual_enabled"] is False
    assert ready["payload"]["tagged_binary"] is False


def test_ws_visual_enabled_when_requested(client_mm):
    with client_mm.websocket_connect("/ws/stream") as ws:
        ready = _handshake(ws, tagged_binary=True, visual=True)
    p = ready["payload"]
    assert p["visual_enabled"] is True
    assert p["multimodal_model"] is True
    assert p["expected_landmarks"] == N_FACE_LANDMARKS
    assert p["max_frames"] == MAX_FRAMES


def test_ws_visual_refused_for_unimodal_model(client_m):
    """An audio-only checkpoint cannot use vision, however the client asks."""
    with client_m.websocket_connect("/ws/stream") as ws:
        ready = _handshake(ws, tagged_binary=True, visual=True)
    assert ready["payload"]["visual_enabled"] is False
    assert ready["payload"]["multimodal_model"] is False


def test_ws_visual_requires_tagged_binary(client_mm):
    """Without tagging there is no way to tell landmarks from PCM."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        ready = _handshake(ws, visual=True)
    assert ready["payload"]["visual_enabled"] is False


# --- backward compatibility ---


def test_ws_untagged_audio_still_works(client_mm):
    """Legacy clients send bare PCM and must be unaffected."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws)
        ws.send_bytes(_pcm())
        msg = ws.receive_json()
    assert msg["type"] == "prediction"


def test_ws_tagged_audio_produces_prediction(client_mm):
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        ws.send_bytes(_tagged(TAG_AUDIO, _pcm()))
        msg = ws.receive_json()
    assert msg["type"] == "prediction"


# --- landmarks reach the engine ---


def test_ws_landmarks_do_not_trigger_inference(client_mm):
    """Audio drives the clock; landmarks only update state."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        for _ in range(5):
            ws.send_bytes(_tagged(TAG_LANDMARKS, _landmark_frame()))
        ws.send_text(json.dumps({"type": "ping"}))
        msg = ws.receive_json()
    assert msg["type"] == "info"
    assert "pong" in msg["payload"]["message"].lower()


def test_ws_landmarks_are_buffered(client_mm):
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        for _ in range(7):
            ws.send_bytes(_tagged(TAG_LANDMARKS, _landmark_frame()))
        ws.send_text(json.dumps({"type": "stats"}))
        msg = ws.receive_json()
    v = msg["payload"]["visual"]
    assert v["frames_received"] == 7
    assert v["frames_buffered"] == 7
    assert v["active"] is True


def test_ws_visual_window_reaches_engine(client_mm, engine_mm):
    """The regression test: engine.predict must receive a real visual window."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        for _ in range(10):
            ws.send_bytes(_tagged(TAG_LANDMARKS, _landmark_frame()))
        ws.send_bytes(_tagged(TAG_AUDIO, _pcm()))
        ws.receive_json()

    args, _ = engine_mm.predict.call_args
    assert len(args) == 2, "predict() was called without a visual argument"
    visual = args[1]
    assert visual is not None, "visual window was None despite a live track"
    assert visual.shape == (MAX_FRAMES, N_FACE_LANDMARKS * LANDMARK_COORDS)


def test_ws_no_landmarks_means_none_not_zeros(client_mm, engine_mm):
    """With no face track the engine gets None, so it can flag audio-only.

    Passing a zero array here instead would be indistinguishable from a real
    all-zero face and would silently claim the prediction was multimodal.
    """
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        ws.send_bytes(_tagged(TAG_AUDIO, _pcm()))
        ws.receive_json()

    args, _ = engine_mm.predict.call_args
    assert args[1] is None


def test_ws_reset_clears_landmarks(client_mm):
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        for _ in range(4):
            ws.send_bytes(_tagged(TAG_LANDMARKS, _landmark_frame()))
        ws.send_text(json.dumps({"type": "reset"}))
        ws.receive_json()                       # info: buffer cleared
        ws.send_text(json.dumps({"type": "stats"}))
        msg = ws.receive_json()
    v = msg["payload"]["visual"]
    assert v["frames_buffered"] == 0
    assert v["active"] is False


# --- malformed input ---


def test_ws_bad_landmark_frame_reports_error_and_survives(client_mm):
    """A truncated frame must not kill the connection."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        ws.send_bytes(_tagged(TAG_LANDMARKS, b"\x00" * 7))   # not a multiple of 3 floats
        err = ws.receive_json()
        assert err["type"] == "error"

        ws.send_text(json.dumps({"type": "ping"}))           # still alive
        assert "pong" in ws.receive_json()["payload"]["message"].lower()


def test_ws_too_few_landmarks_rejected(client_mm):
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        ws.send_bytes(_tagged(TAG_LANDMARKS, _landmark_frame(n=10)))
        err = ws.receive_json()
    assert err["type"] == "error"
    assert "landmark" in err["payload"]["message"].lower()


def test_ws_extra_landmarks_accepted(client_mm):
    """478-point browser output must feed a 468-point model."""
    with client_mm.websocket_connect("/ws/stream") as ws:
        _handshake(ws, tagged_binary=True, visual=True)
        ws.send_bytes(_tagged(TAG_LANDMARKS, _landmark_frame(n=N_FACE_LANDMARKS + 10)))
        ws.send_text(json.dumps({"type": "stats"}))
        msg = ws.receive_json()
    assert msg["type"] == "info"
    assert msg["payload"]["visual"]["frames_received"] == 1


# ── Untrained-checkpoint disclosure ───────────────────────


def test_health_reports_untrained_false_for_normal_model(client_m):
    assert client_m.get("/health").json()["untrained"] is False


def test_health_reports_untrained_true_for_demo_checkpoint():
    """A randomly initialised checkpoint must announce itself.

    scripts/make_demo_checkpoint.py exists so the pipeline is runnable before
    training, but its predictions are noise. If the UI could not tell, a demo
    screenshot would be indistinguishable from a result.
    """
    from unittest.mock import patch
    from backend.main import app
    eng = _make_engine()
    eng.untrained = True
    with patch("backend.main._load_engine", return_value=eng):
        with TestClient(app) as c:
            data = c.get("/health").json()
    assert data["untrained"] is True


def test_health_reports_multimodal_flag(client_mm):
    assert client_mm.get("/health").json()["multimodal"] is True
