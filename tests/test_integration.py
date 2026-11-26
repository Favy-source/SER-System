"""
Cross-stage contract tests.

The rest of the suite tests each stage against inputs it constructs itself,
which verifies the consumer but not the contract between producer and consumer.
Three bugs lived in exactly that gap:

  - MFCC tensors reached Conv2d 3-D, because only the mel branch of
    EmotionDataset._load_audio added a channel axis. Extraction was tested and
    mel loading was tested; MFCC loading feeding a model was tested by neither.
  - AudioCNNLSTM sized its LSTM from n_mels, so an MFCC input (120 rows, not
    128) produced a state dict that did not match.
  - The landmark width was hard-coded independently in three files and
    disagreed with what the extractor produced.

So these tests deliberately chain real stages: audio file -> feature extraction
-> .npy -> EmotionDataset -> DataLoader -> build_model -> forward, and a real
checkpoint round-trip through InferenceEngine.

Run:  pytest tests/test_integration.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
import soundfile as sf
import torch
import yaml
from torch.utils.data import DataLoader

from src.constants import LANDMARK_COORDS, LANDMARK_DIM, N_FACE_LANDMARKS
from src.datasets import UNIFIED, EmotionDataset
from src.features import extract_audio_features
from src.models.builder import build_model, feature_height, n_frames
from src.models.visual import VisualLSTM

CFG = yaml.safe_load(open("config/settings.yaml"))
N_CLASSES = len(UNIFIED)
AUDIO_MODELS = ["audio_cnn", "audio_cnn_lstm"]
FUSION_MODELS = ["feature_level", "decision_level", "attention"]


# ── Helpers ───────────────────────────────────────────────


def _write_sine(path: Path, duration=3.0, sr=None) -> Path:
    sr = sr or CFG["audio"]["sample_rate"]
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    sf.write(str(path), (0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), sr)
    return path


def _build_processed_dir(tmp_path: Path, feature: str, n=4, with_video=False):
    """Run real feature extraction into the on-disk layout the Dataset expects."""
    import pandas as pd

    (tmp_path / feature).mkdir(parents=True, exist_ok=True)
    if with_video:
        (tmp_path / "landmarks").mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(n):
        stem = f"clip_{i:02d}"
        wav = _write_sine(tmp_path / f"{stem}.wav")
        feats = extract_audio_features(str(wav), CFG["audio"])
        np.save(tmp_path / feature / f"{stem}.npy", feats[feature])

        video_path = None
        if with_video:
            video_path = f"/fake/{stem}.mp4"
            np.save(
                tmp_path / "landmarks" / f"{stem}.npy",
                np.random.randn(CFG["visual"]["max_frames"], LANDMARK_DIM).astype(np.float32),
            )
        rows.append({
            "audio_path": str(wav),
            "video_path": video_path,
            "label": UNIFIED[i % N_CLASSES],
            "speaker": f"spk_{i:02d}",
            "dataset": "synthetic",
        })
    return pd.DataFrame(rows)


# ── feature_height matches what extraction produces ───────


@pytest.mark.parametrize("feature", ["mel", "mfcc"])
def test_feature_height_matches_extraction(tmp_path, feature):
    """The height build_model assumes must equal the height on disk."""
    wav = _write_sine(tmp_path / "a.wav")
    feats = extract_audio_features(str(wav), CFG["audio"])
    assert feats[feature].shape == (feature_height(CFG, feature), n_frames(CFG))


def test_mel_and_mfcc_heights_differ():
    """If these were equal the mfcc LSTM-width bug would be unobservable."""
    assert feature_height(CFG, "mel") != feature_height(CFG, "mfcc")


def test_feature_height_honours_use_delta():
    cfg = {"audio": {**CFG["audio"], "use_delta": False}}
    assert feature_height(cfg, "mfcc") == cfg["audio"]["n_mfcc"]
    assert feature_height(CFG, "mfcc") == CFG["audio"]["n_mfcc"] * 3


# ── Full chain: extraction -> Dataset -> DataLoader -> model


@pytest.mark.parametrize("feature", ["mel", "mfcc"])
def test_dataset_item_has_channel_axis(tmp_path, feature):
    """Both features must arrive 3-D as (channel, freq, time)."""
    df = _build_processed_dir(tmp_path, feature, n=2)
    ds = EmotionDataset(df, str(tmp_path), "audio", feature,
                        max_frames=CFG["visual"]["max_frames"])
    x, _ = ds[0]
    assert x.shape == (1, feature_height(CFG, feature), n_frames(CFG))


@pytest.mark.parametrize("feature", ["mel", "mfcc"])
@pytest.mark.parametrize("model_name", AUDIO_MODELS)
def test_audio_chain_forward(tmp_path, feature, model_name):
    """The regression test for the MFCC crash, over the real pipeline."""
    df = _build_processed_dir(tmp_path, feature, n=4)
    ds = EmotionDataset(df, str(tmp_path), "audio", feature,
                        max_frames=CFG["visual"]["max_frames"])
    xb, yb = next(iter(DataLoader(ds, batch_size=4)))

    assert xb.dim() == 4, f"Conv2d needs 4-D input, got {tuple(xb.shape)}"

    model = build_model(model_name, CFG, N_CLASSES, feature)
    model.eval()
    with torch.no_grad():
        out = model(xb)
    assert out.shape == (4, N_CLASSES)
    assert not torch.isnan(out).any()


@pytest.mark.parametrize("feature", ["mel", "mfcc"])
@pytest.mark.parametrize("model_name", FUSION_MODELS)
def test_multimodal_chain_forward(tmp_path, feature, model_name):
    """Fusion models must accept both feature types too."""
    df = _build_processed_dir(tmp_path, feature, n=4, with_video=True)
    ds = EmotionDataset(df, str(tmp_path), "multimodal", feature,
                        max_frames=CFG["visual"]["max_frames"])
    xa, xv, y = next(iter(DataLoader(ds, batch_size=4)))

    assert xa.shape == (4, 1, feature_height(CFG, feature), n_frames(CFG))
    assert xv.shape == (4, CFG["visual"]["max_frames"], LANDMARK_DIM)

    model = build_model(model_name, CFG, N_CLASSES, feature)
    model.eval()
    with torch.no_grad():
        out = model(xa, xv)
    assert out.shape == (4, N_CLASSES)


@pytest.mark.parametrize("feature", ["mel", "mfcc"])
def test_state_dict_round_trip(tmp_path, feature):
    """A model built for one feature must reload its own weights.

    This is what the LSTM-width bug broke: build with mel, save, rebuild with
    mfcc, and load_state_dict raises on a shape mismatch.
    """
    saved = build_model("audio_cnn_lstm", CFG, N_CLASSES, feature)
    reloaded = build_model("audio_cnn_lstm", CFG, N_CLASSES, feature)
    reloaded.load_state_dict(saved.state_dict())   # must not raise

    other = "mel" if feature == "mfcc" else "mfcc"
    mismatched = build_model("audio_cnn_lstm", CFG, N_CLASSES, other)
    with pytest.raises(RuntimeError):
        mismatched.load_state_dict(saved.state_dict())


# ── Landmark dimension: one constant, every consumer ──────


def test_landmark_constants_consistent():
    assert LANDMARK_DIM == N_FACE_LANDMARKS * LANDMARK_COORDS
    assert N_FACE_LANDMARKS in (468, 478), (
        "MediaPipe FaceMesh returns 468 landmarks, or 478 with refine_landmarks"
    )


def test_visual_lstm_default_input_dim_is_the_constant():
    assert VisualLSTM()._embed_dim  # constructs with defaults
    assert VisualLSTM().proj.in_features == LANDMARK_DIM


def test_builder_visual_input_dim_is_the_constant():
    assert build_model("visual_lstm", CFG, N_CLASSES).proj.in_features == LANDMARK_DIM


@pytest.mark.parametrize("max_frames", [75, 40, 100])
def test_zero_fill_shape_follows_config(tmp_path, max_frames):
    """Missing video must zero-fill at the configured length, not a fixed 75."""
    df = _build_processed_dir(tmp_path, "mel", n=1)          # video_path is None
    ds = EmotionDataset(df, str(tmp_path), "multimodal", "mel", max_frames=max_frames)
    _, visual, _ = ds[0]
    assert visual.shape == (max_frames, LANDMARK_DIM)
    assert visual.sum().item() == 0.0


def test_zero_fill_is_collatable_with_real_landmarks(tmp_path):
    """Zero-filled and real visual tensors must batch together.

    Mixed manifests are the normal case: MSP-IMPROV has no video at all, so a
    width or length disagreement here breaks collation at training time.
    """
    import pandas as pd
    real = _build_processed_dir(tmp_path, "mel", n=2, with_video=True)
    blank = _build_processed_dir(tmp_path / "b", "mel", n=2, with_video=False)
    blank["video_path"] = None

    # both halves resolve landmarks against the first processed dir
    df = pd.concat([real, blank], ignore_index=True)
    ds = EmotionDataset(df, str(tmp_path), "multimodal", "mel",
                        max_frames=CFG["visual"]["max_frames"])
    _, xv, _ = next(iter(DataLoader(ds, batch_size=4)))
    assert xv.shape == (4, CFG["visual"]["max_frames"], LANDMARK_DIM)


# ── InferenceEngine round-trip, no mock ───────────────────


@pytest.mark.parametrize("model_name", ["audio_cnn_lstm", "attention"])
def test_inference_engine_real_checkpoint(tmp_path, model_name):
    """Save a real checkpoint, load it through InferenceEngine, predict.

    Every API test mocks the engine, so checkpoint loading and serving-side
    feature extraction are otherwise never exercised.
    """
    from backend.inference import InferenceEngine

    model = build_model(model_name, CFG, N_CLASSES, "mel")
    ckpt = tmp_path / f"{model_name}_test.pt"
    torch.save({
        "epoch": 1, "model": model.state_dict(),
        "val_loss": 1.0, "val_acc": 0.5,
        "model_name": model_name, "feature": "mel", "cfg": CFG,
    }, ckpt)

    engine = InferenceEngine(str(ckpt), "config/settings.yaml")
    assert engine.model_name == model_name

    sr = CFG["audio"]["sample_rate"]
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    result = engine.predict((0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))

    assert result["emotion"] in UNIFIED
    assert set(result["probabilities"]) == set(UNIFIED)
    assert abs(sum(result["probabilities"].values()) - 1.0) < 0.01
    assert result["model_name"] == model_name
    assert result["latency_ms"] > 0


def test_inference_engine_zero_visual_width(tmp_path):
    """The serving placeholder must match the visual branch's input width."""
    from backend.inference import InferenceEngine

    model = build_model("attention", CFG, N_CLASSES, "mel")
    ckpt = tmp_path / "attention_test.pt"
    torch.save({
        "epoch": 1, "model": model.state_dict(), "val_loss": 1.0, "val_acc": 0.5,
        "model_name": "attention", "feature": "mel", "cfg": CFG,
    }, ckpt)

    engine = InferenceEngine(str(ckpt), "config/settings.yaml")
    zv = engine._zero_visual()
    assert zv.shape == (1, CFG["visual"]["max_frames"], LANDMARK_DIM)


def test_inference_engine_mfcc_checkpoint(tmp_path):
    """An mfcc checkpoint must serve — the serving-side half of the crash."""
    from backend.inference import InferenceEngine

    model = build_model("audio_cnn_lstm", CFG, N_CLASSES, "mfcc")
    ckpt = tmp_path / "mfcc.pt"
    torch.save({
        "epoch": 1, "model": model.state_dict(), "val_loss": 1.0, "val_acc": 0.5,
        "model_name": "audio_cnn_lstm", "feature": "mfcc", "cfg": CFG,
    }, ckpt)

    engine = InferenceEngine(str(ckpt), "config/settings.yaml")
    assert engine.feature == "mfcc"

    sr = CFG["audio"]["sample_rate"]
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    audio = (0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    tensor = engine._to_tensor(engine._pad_or_crop(audio))
    assert tensor.dim() == 4, f"Conv2d needs 4-D, got {tuple(tensor.shape)}"
    assert tensor.shape == (1, 1, feature_height(CFG, "mfcc"), n_frames(CFG))

    assert engine.predict(audio)["emotion"] in UNIFIED


# ── Real multimodal serving: does vision actually contribute? ──
#
# The whole point of the visual path. Before it existed, fusion checkpoints were
# served with a zero visual tensor, so a "multimodal" prediction was audio-only
# in everything but name. Mocked API tests cannot catch that — they assert the
# plumbing, not that the model's output depends on the visual input. These use
# real models.

def _sine(seconds=3.0):
    sr = CFG["audio"]["sample_rate"]
    t = np.linspace(0, seconds, int(sr*seconds), endpoint=False)
    return (0.4*np.sin(2*np.pi*440*t)).astype(np.float32)


def _engine_for(tmp_path, model_name, feature="mel"):
    from backend.inference import InferenceEngine
    torch.manual_seed(0)
    model = build_model(model_name, CFG, N_CLASSES, feature)
    ckpt = tmp_path / f"{model_name}.pt"
    torch.save({"epoch":1,"model":model.state_dict(),"val_loss":1.0,"val_acc":0.5,
                "model_name":model_name,"feature":feature,"cfg":CFG}, ckpt)
    return InferenceEngine(str(ckpt), "config/settings.yaml")


def _landmark_window(seed=0):
    rng = np.random.default_rng(seed)
    from src.features import normalize_landmarks
    frames = [normalize_landmarks(rng.random((N_FACE_LANDMARKS, 3)).astype(np.float32))
              for _ in range(CFG["visual"]["max_frames"])]
    return np.stack(frames).astype(np.float32)


@pytest.mark.parametrize("model_name", FUSION_MODELS)
def test_visual_input_changes_fusion_prediction(tmp_path, model_name):
    """A real landmark window must alter a fusion model's output.

    If this fails, the visual branch is not wired into the forward pass and the
    model is effectively audio-only regardless of what it reports.
    """
    eng = _engine_for(tmp_path, model_name)
    audio = _sine()

    without = eng.predict(audio)                              # zero-filled visual
    with_v  = eng.predict(audio, _landmark_window(seed=1))

    assert without["visual_active"] is False
    assert with_v["visual_active"] is True
    assert without["modalities"] == ["audio"]
    assert with_v["modalities"] == ["audio", "visual"]

    a = np.array([without["probabilities"][e] for e in UNIFIED])
    b = np.array([with_v["probabilities"][e]  for e in UNIFIED])
    assert not np.allclose(a, b, atol=1e-6), (
        f"{model_name}: visual input did not change the output — branch not wired"
    )


@pytest.mark.parametrize("model_name", FUSION_MODELS)
def test_different_faces_give_different_predictions(tmp_path, model_name):
    """Two different landmark windows must not collapse to the same output."""
    eng = _engine_for(tmp_path, model_name)
    audio = _sine()
    p1 = eng.predict(audio, _landmark_window(seed=1))["probabilities"]
    p2 = eng.predict(audio, _landmark_window(seed=2))["probabilities"]
    a = np.array([p1[e] for e in UNIFIED]); b = np.array([p2[e] for e in UNIFIED])
    assert not np.allclose(a, b, atol=1e-6)


def test_unimodal_model_ignores_visual(tmp_path):
    """An audio-only model must not claim vision, even if handed a window."""
    eng = _engine_for(tmp_path, "audio_cnn_lstm")
    r = eng.predict(_sine(), _landmark_window())
    assert r["visual_active"] is False
    assert r["modalities"] == ["audio"]


def test_engine_rejects_wrong_visual_shape(tmp_path):
    eng = _engine_for(tmp_path, "attention")
    with pytest.raises(ValueError, match="shape"):
        eng.predict(_sine(), np.zeros((10, LANDMARK_DIM), dtype=np.float32))
    with pytest.raises(ValueError, match="shape"):
        eng.predict(_sine(), np.zeros((CFG["visual"]["max_frames"], 99), dtype=np.float32))


# ── VisualStreamBuffer behaviour ──────────────────────────


def test_visual_buffer_window_shape_and_padding():
    from backend.stream import VisualStreamBuffer
    mf = CFG["visual"]["max_frames"]
    b = VisualStreamBuffer(max_frames=mf)
    rng = np.random.default_rng(0)
    for _ in range(5):
        b.push(rng.random((N_FACE_LANDMARKS, 3)).astype(np.float32))
    w = b.window()
    assert w.shape == (mf, LANDMARK_DIM)
    assert not np.allclose(w[:5], 0), "real frames should be non-zero"
    assert np.allclose(w[5:], 0), "short tracks pad at the END, as in training"


def test_visual_buffer_keeps_newest_frames():
    from backend.stream import VisualStreamBuffer
    mf = 10
    b = VisualStreamBuffer(max_frames=mf)
    for i in range(mf + 7):
        coords = np.full((N_FACE_LANDMARKS, 3), float(i) + 1.0, dtype=np.float32)
        coords[0] += 1.0                       # break the degenerate all-equal case
        b.push(coords)
    assert b.stats()["frames_buffered"] == mf
    assert b.stats()["frames_received"] == mf + 7


def test_visual_buffer_goes_stale():
    from backend.stream import VisualStreamBuffer
    b = VisualStreamBuffer(max_frames=75, stale_after=0.0)
    b.push(np.random.rand(N_FACE_LANDMARKS, 3).astype(np.float32))
    import time; time.sleep(0.01)
    assert b.is_active() is False
    assert b.window() is None, "a stale face track must not be fed to the model"


def test_visual_buffer_empty_window_is_none():
    from backend.stream import VisualStreamBuffer
    assert VisualStreamBuffer(max_frames=75).window() is None


def test_visual_buffer_truncates_extra_landmarks():
    """478-point browser output feeds a 468-point model."""
    from backend.stream import VisualStreamBuffer
    b = VisualStreamBuffer(max_frames=75)
    b.push(np.random.rand(N_FACE_LANDMARKS + 10, 3).astype(np.float32))
    assert b.window().shape == (75, LANDMARK_DIM)


def test_audio_buffer_pulls_visual_window(tmp_path):
    """Audio drives the clock and must hand the visual window to the engine."""
    from backend.stream import AudioStreamBuffer, VisualStreamBuffer
    eng = _engine_for(tmp_path, "attention")
    vb = VisualStreamBuffer(max_frames=CFG["visual"]["max_frames"])
    for _ in range(20):
        vb.push(np.random.rand(N_FACE_LANDMARKS, 3).astype(np.float32))
    ab = AudioStreamBuffer(eng, input_sr=16000, visual=vb)
    r = ab.push(np.zeros(16000 * 4, dtype=np.float32).tobytes())
    assert r is not None and "_error" not in r
    assert r["visual_active"] is True

    ab2 = AudioStreamBuffer(eng, input_sr=16000, visual=None)
    r2 = ab2.push(np.zeros(16000 * 4, dtype=np.float32).tobytes())
    assert r2["visual_active"] is False


# ── Normalisation is shared, not reimplemented ────────────


def test_normalize_landmarks_is_translation_invariant():
    from src.features import normalize_landmarks
    rng = np.random.default_rng(3)
    c = rng.random((N_FACE_LANDMARKS, 3)).astype(np.float32)
    shifted = c + np.array([5.0, -3.0, 2.0], dtype=np.float32)
    assert np.allclose(normalize_landmarks(c), normalize_landmarks(shifted), atol=1e-5)


def test_normalize_landmarks_is_scale_invariant():
    from src.features import normalize_landmarks
    rng = np.random.default_rng(4)
    c = rng.random((N_FACE_LANDMARKS, 3)).astype(np.float32)
    assert np.allclose(normalize_landmarks(c), normalize_landmarks(c * 7.5), atol=1e-5)


def test_normalize_landmarks_output_width():
    from src.features import normalize_landmarks
    c = np.random.rand(N_FACE_LANDMARKS, 3).astype(np.float32)
    assert normalize_landmarks(c).shape == (LANDMARK_DIM,)


def test_normalize_landmarks_rejects_bad_input():
    from src.features import normalize_landmarks
    with pytest.raises(ValueError):
        normalize_landmarks(np.random.rand(N_FACE_LANDMARKS, 2).astype(np.float32))
    with pytest.raises(ValueError):
        normalize_landmarks(np.random.rand(10, 3).astype(np.float32))


def test_normalize_landmarks_handles_degenerate_frame():
    """All-identical points would divide by zero without the epsilon guard."""
    from src.features import normalize_landmarks
    out = normalize_landmarks(np.ones((N_FACE_LANDMARKS, 3), dtype=np.float32))
    assert not np.isnan(out).any()


# ── End-to-end: real engine over the real WebSocket app ────
#
# The API tests mock the engine, so they verify plumbing but cannot show that a
# prediction's output actually depends on the landmarks that were streamed.
# These use a real fusion checkpoint through the real FastAPI app.

def _save_ckpt(tmp_path, model_name, feature="mel"):
    torch.manual_seed(0)
    model = build_model(model_name, CFG, N_CLASSES, feature)
    p = tmp_path / f"{model_name}.pt"
    torch.save({"epoch":1,"model":model.state_dict(),"val_loss":1.0,"val_acc":0.5,
                "model_name":model_name,"feature":feature,"cfg":CFG}, p)
    return p


def _real_client(tmp_path, model_name):
    from fastapi.testclient import TestClient
    from backend.inference import InferenceEngine
    from unittest.mock import patch
    import backend.main as bm
    ckpt = _save_ckpt(tmp_path, model_name)
    eng = InferenceEngine(str(ckpt), "config/settings.yaml")
    return patch.object(bm, "_load_engine", return_value=eng), bm.app, eng


def _tag(tag, payload):
    import struct
    return struct.pack("<Bxxx", tag) + payload


def _raw_landmarks(seed=0):
    rng = np.random.default_rng(seed)
    return rng.random((N_FACE_LANDMARKS, 3)).astype(np.float32).tobytes()


def test_e2e_websocket_multimodal_prediction(tmp_path):
    """Stream landmarks + audio to the real app and confirm vision was used."""
    from fastapi.testclient import TestClient
    import json
    patcher, app, _ = _real_client(tmp_path, "attention")
    with patcher, TestClient(app) as c:
        with c.websocket_connect("/ws/stream") as ws:
            ws.send_text(json.dumps({"sample_rate": 16000,
                                     "tagged_binary": True, "visual": True}))
            ready = ws.receive_json()
            assert ready["payload"]["visual_enabled"] is True

            for i in range(30):
                ws.send_bytes(_tag(1, _raw_landmarks(i)))
            ws.send_bytes(_tag(0, np.zeros(16000 * 4, dtype=np.float32).tobytes()))
            msg = ws.receive_json()

    assert msg["type"] == "prediction"
    p = msg["payload"]
    assert p["visual_active"] is True
    assert p["modalities"] == ["audio", "visual"]
    assert p["emotion"] in UNIFIED
    assert abs(sum(p["probabilities"].values()) - 1.0) < 0.02


def test_e2e_websocket_audio_only_when_no_face(tmp_path):
    """Same model, same audio, no landmarks -> honestly reported as audio-only."""
    from fastapi.testclient import TestClient
    import json
    patcher, app, _ = _real_client(tmp_path, "attention")
    with patcher, TestClient(app) as c:
        with c.websocket_connect("/ws/stream") as ws:
            ws.send_text(json.dumps({"sample_rate": 16000,
                                     "tagged_binary": True, "visual": True}))
            ws.receive_json()
            ws.send_bytes(_tag(0, np.zeros(16000 * 4, dtype=np.float32).tobytes()))
            p = ws.receive_json()["payload"]

    assert p["visual_active"] is False
    assert p["modalities"] == ["audio"]


def test_e2e_landmarks_change_the_streamed_prediction(tmp_path):
    """The end-to-end version of the claim: streamed faces move the output.

    Identical audio, one run with landmarks and one without, must not produce
    identical probabilities — otherwise the visual stream is decorative.
    """
    from fastapi.testclient import TestClient
    import json
    audio = np.zeros(16000 * 4, dtype=np.float32).tobytes()

    def run(with_face):
        patcher, app, _ = _real_client(tmp_path, "attention")
        with patcher, TestClient(app) as c:
            with c.websocket_connect("/ws/stream") as ws:
                ws.send_text(json.dumps({"sample_rate": 16000,
                                         "tagged_binary": True, "visual": True}))
                ws.receive_json()
                if with_face:
                    for i in range(30):
                        ws.send_bytes(_tag(1, _raw_landmarks(i)))
                ws.send_bytes(_tag(0, audio))
                return ws.receive_json()["payload"]["probabilities"]

    a = np.array([run(False)[e] for e in UNIFIED])
    b = np.array([run(True)[e]  for e in UNIFIED])
    assert not np.allclose(a, b, atol=1e-6), "streamed landmarks had no effect"


def test_e2e_unimodal_checkpoint_refuses_visual(tmp_path):
    """An audio-only checkpoint must decline visual regardless of the request."""
    from fastapi.testclient import TestClient
    import json
    patcher, app, _ = _real_client(tmp_path, "audio_cnn_lstm")
    with patcher, TestClient(app) as c:
        with c.websocket_connect("/ws/stream") as ws:
            ws.send_text(json.dumps({"sample_rate": 16000,
                                     "tagged_binary": True, "visual": True}))
            payload = ws.receive_json()["payload"]
    assert payload["visual_enabled"] is False
    assert payload["multimodal_model"] is False


def test_visual_freshness_survives_slow_inference():
    """Server compute must not age the face track.

    Regression: the visual window was read AFTER resampling, so the freshness
    check included our own latency. The first inference pays a multi-second
    lazy `import librosa`, which pushed a live track past stale_after and
    silently degraded the prediction to audio-only.
    """
    import time
    from backend.stream import AudioStreamBuffer, VisualStreamBuffer

    class SlowEngine:
        sr = 22050
        def predict(self, audio, visual=None):
            time.sleep(0.3)                        # slow forward pass
            return {"visual_active": visual is not None}

    vb = VisualStreamBuffer(max_frames=75, stale_after=0.2)
    for _ in range(20):
        vb.push(np.random.rand(N_FACE_LANDMARKS, 3).astype(np.float32))

    ab = AudioStreamBuffer(SlowEngine(), input_sr=22050, visual=vb)
    first = ab.push(np.zeros(22050 * 4, dtype=np.float32).tobytes())
    assert first["visual_active"] is True, "slow inference aged a live face track"


def test_visual_track_still_goes_stale_when_abandoned():
    """The freshness check must still work — the fix must not disable it."""
    import time
    from backend.stream import AudioStreamBuffer, VisualStreamBuffer

    class Engine:
        sr = 22050
        def predict(self, audio, visual=None):
            return {"visual_active": visual is not None}

    vb = VisualStreamBuffer(max_frames=75, stale_after=0.05)
    for _ in range(20):
        vb.push(np.random.rand(N_FACE_LANDMARKS, 3).astype(np.float32))
    time.sleep(0.1)                                # client stopped sending

    ab = AudioStreamBuffer(Engine(), input_sr=22050, visual=vb)
    r = ab.push(np.zeros(22050 * 4, dtype=np.float32).tobytes())
    assert r["visual_active"] is False, "an abandoned face track was still used"


# ── Offline visual extraction (needs mediapipe) ────────────
#
# mediapipe is optional: audio-only training and ALL serving work without it,
# because the browser produces landmarks for the live path. It is required only
# to build landmarks/*.npy for TRAINING a fusion model, so these skip rather
# than fail when it is absent.
#
# They exist because the extractor was silently broken: it used the legacy
# `mp.solutions.face_mesh` namespace, which mediapipe 1.0 REMOVED. `import
# mediapipe` still succeeded, so the ImportError guard passed and the failure
# only appeared at call time as AttributeError — which preprocess.py catches per
# file, meaning every video would have been logged as an error and the run would
# have produced an audio-only dataset that looked successful.

mediapipe_required = pytest.mark.skipif(
    not __import__("src.features", fromlist=["_MEDIAPIPE"])._MEDIAPIPE,
    reason="mediapipe not installed (optional: needed only to build training landmarks)",
)


def _draw_synthetic_face(t):
    """A crude frontal face, good enough for MediaPipe's detector."""
    import cv2
    img = np.full((480, 640, 3), (90, 110, 130), np.uint8)
    cx, cy = 320, 250
    cv2.ellipse(img, (cx, cy), (110, 145), 0, 0, 360, (150, 180, 205), -1)
    cv2.ellipse(img, (cx, cy - 150), (115, 60), 0, 0, 360, (40, 45, 55), -1)
    for sx in (-42, 42):
        cv2.ellipse(img, (cx + sx, cy - 35), (26, 14), 0, 0, 360, (250, 250, 250), -1)
        cv2.circle(img, (cx + sx, cy - 35), 9, (60, 50, 45), -1)
        cv2.ellipse(img, (cx + sx, cy - 55), (28, 8), 0, 200, 340, (50, 55, 65), 4)
    cv2.line(img, (cx, cy - 25), (cx, cy + 25), (120, 150, 175), 6)
    cv2.ellipse(img, (cx, cy + 30), (10, 8), 0, 0, 360, (110, 140, 165), -1)
    cv2.ellipse(img, (cx, cy + 72), (44, 10 + int(8 * np.sin(t))), 0, 0, 360, (70, 60, 90), -1)
    return img


def _write_face_video(path, n_frames=50, fps=25.0):
    import cv2
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 480))
    for i in range(n_frames):
        w.write(_draw_synthetic_face(i * 0.3))
    w.release()
    return path


@mediapipe_required
def test_extract_visual_features_uses_the_tasks_api(tmp_path):
    """The regression test: the extractor must not touch mp.solutions."""
    from src.features import extract_visual_features
    video = _write_face_video(tmp_path / "face.mp4", n_frames=50)
    seq = extract_visual_features(str(video), max_frames=75, frame_size=(256, 256))

    assert seq is not None, "no face detected in the synthetic video"
    assert seq.shape == (75, LANDMARK_DIM)
    assert seq.dtype == np.float32
    assert not np.isnan(seq).any()


@mediapipe_required
def test_extract_visual_features_pads_at_the_end(tmp_path):
    """Short clips zero-pad at the END, matching how the Dataset zero-fills."""
    from src.features import extract_visual_features
    video = _write_face_video(tmp_path / "short.mp4", n_frames=20)
    seq = extract_visual_features(str(video), max_frames=75, frame_size=(256, 256))
    assert seq is not None

    nonzero = (np.abs(seq).sum(1) > 0)
    assert nonzero[:20].all(),  "real frames should lead"
    assert not nonzero[25:].any(), "padding should trail"


@mediapipe_required
def test_extract_visual_features_output_feeds_the_model(tmp_path):
    """The whole point: extracted landmarks must load into VisualLSTM."""
    from src.features import extract_visual_features
    video = _write_face_video(tmp_path / "face.mp4")
    seq = extract_visual_features(str(video), max_frames=CFG["visual"]["max_frames"],
                                  frame_size=(256, 256))
    assert seq is not None

    model = build_model("visual_lstm", CFG, N_CLASSES)
    model.eval()
    with torch.no_grad():
        out = model(torch.from_numpy(seq).unsqueeze(0))
    assert out.shape == (1, N_CLASSES)
    assert not torch.isnan(out).any()


@mediapipe_required
def test_extract_visual_features_returns_none_without_a_face(tmp_path):
    import cv2
    from src.features import extract_visual_features
    p = tmp_path / "noise.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (320, 240))
    rng = np.random.default_rng(0)
    for _ in range(30):
        w.write(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8))
    w.release()
    assert extract_visual_features(str(p)) is None


@mediapipe_required
def test_extract_visual_features_raises_when_model_missing(tmp_path, monkeypatch):
    """A missing .task must be loud, not a silent audio-only dataset."""
    import src.features as F
    video = _write_face_video(tmp_path / "face.mp4", n_frames=5)
    monkeypatch.setattr(F, "face_landmarker_model_path", lambda: None)
    with pytest.raises(FileNotFoundError, match="face_landmarker.task"):
        F.extract_visual_features(str(video))


# ── Cross-validation harness end-to-end smoke test ────────


def test_cross_validate_decision_level_3fold_smoke_and_resume(tmp_path):
    """Exercise the real k-fold CV pipeline end-to-end on synthetic features."""
    import copy
    import json
    from scripts.cross_validate import run_cv

    proc = tmp_path / "proc"
    res_dir = tmp_path / "results"
    df = _build_processed_dir(proc, "mel", n=6, with_video=True)
    # _build_processed_dir creates 6 distinct speakers -> valid for 3-fold SI CV
    small_cfg = copy.deepcopy(CFG)
    small_cfg["training"] = {
        **CFG["training"],
        "batch_size": 2,
        "epochs": 1,
        "early_stopping_patience": 1,
        "num_workers": 0,
        "pin_memory": False,
        "amp": False,
    }
    small_cfg["model"]["audio_cnn_lstm"]["cnn_channels"] = [8, 16, 16]
    small_cfg["model"]["audio_cnn_lstm"]["lstm_hidden"] = 16
    small_cfg["model"]["audio_cnn_lstm"]["lstm_layers"] = 1
    small_cfg["model"]["visual_lstm"]["hidden_dim"] = 16
    small_cfg["model"]["visual_lstm"]["num_layers"] = 1

    summary = run_cv(
        df, "decision_level", small_cfg, proc, res_dir,
        n_splits=3, only_with_video=True, epochs=1, resume=False,
    )
    assert summary["n_splits"] == 3
    assert summary["n_total_oof"] == 6
    assert "decision_weights" in summary
    assert abs(summary["decision_weights"]["audio_mean"] + summary["decision_weights"]["visual_mean"] - 1.0) < 1e-3
    assert set(summary["per_class"].keys()) == set(UNIFIED)
    assert (res_dir / "cv_decision_level_av_3fold.json").exists()
    assert (res_dir / "cv_decision_level_av_3fold_confusion.png").exists()

    # Resuming must return identical metrics without retraining.
    resumed = run_cv(
        df, "decision_level", small_cfg, proc, res_dir,
        n_splits=3, only_with_video=True, epochs=1, resume=True,
    )
    assert resumed["accuracy_mean"] == summary["accuracy_mean"]
    assert resumed["f1_macro_mean"] == summary["f1_macro_mean"]
    assert json.loads((res_dir / "cv_decision_level_av_3fold.json").read_text())["n_total_oof"] == 6
