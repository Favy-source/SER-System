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
