"""
Tests for model architectures and the build_model factory.

Run:  pytest tests/test_model.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
import pytest

from src.models.audio  import AudioCNN, AudioCNNLSTM
from src.models.visual import VisualLSTM
from src.models.fusion import (
    FeatureLevelFusion, DecisionLevelFusion, CrossModalAttentionFusion,
)
from src.constants import LANDMARK_DIM
from src.models.builder import build_model, is_multimodal, FUSION, UNIMODAL

N_CLASSES = 6
B         = 4
MEL       = (B, 1, 128, 130)          # (batch, channel, n_mels, n_frames)
VISUAL    = (B, 75, LANDMARK_DIM)     # (batch, frames, landmarks × 3 coords)

# Minimal config sufficient for build_model
CFG = {
    "audio": {
        "sample_rate": 22050, "duration": 3.0,
        "n_mels": 128, "n_fft": 2048, "hop_length": 512,
        "f_min": 20.0, "f_max": 8000.0,
        "n_mfcc": 40, "use_delta": True, "normalize": True,
    },
    "model": {
        "audio_cnn":      {"channels": [32, 64, 128, 256], "dropout": 0.3},
        "audio_cnn_lstm": {"cnn_channels": [32, 64, 128], "lstm_hidden": 256,
                           "lstm_layers": 2, "dropout": 0.3},
        "visual_lstm":    {"hidden_dim": 256, "num_layers": 2, "dropout": 0.3},
        "fusion":         {"strategy": "attention", "n_heads": 8, "dropout": 0.3},
    },
}


# ── Forward pass shapes ───────────────────────────────────


def test_audio_cnn_forward_shape():
    model = AudioCNN(N_CLASSES)
    out   = model(torch.randn(*MEL))
    assert out.shape == (B, N_CLASSES)


def test_audio_cnn_lstm_forward_shape():
    model = AudioCNNLSTM(N_CLASSES)
    out   = model(torch.randn(*MEL))
    assert out.shape == (B, N_CLASSES)


def test_visual_lstm_forward_shape():
    model = VisualLSTM(num_classes=N_CLASSES)
    out   = model(torch.randn(*VISUAL))
    assert out.shape == (B, N_CLASSES)


def test_feature_level_fusion_forward_shape():
    model = FeatureLevelFusion(AudioCNNLSTM(N_CLASSES), VisualLSTM(num_classes=N_CLASSES), N_CLASSES)
    out   = model(torch.randn(*MEL), torch.randn(*VISUAL))
    assert out.shape == (B, N_CLASSES)


def test_decision_level_fusion_forward_shape():
    model = DecisionLevelFusion(AudioCNNLSTM(N_CLASSES), VisualLSTM(num_classes=N_CLASSES), N_CLASSES)
    out   = model(torch.randn(*MEL), torch.randn(*VISUAL))
    assert out.shape == (B, N_CLASSES)


def test_cross_modal_attention_fusion_forward_shape():
    model = CrossModalAttentionFusion(AudioCNNLSTM(N_CLASSES), VisualLSTM(num_classes=N_CLASSES), N_CLASSES, n_heads=8)
    out   = model(torch.randn(*MEL), torch.randn(*VISUAL))
    assert out.shape == (B, N_CLASSES)


# ── Embed dimensions ──────────────────────────────────────


def test_audio_cnn_embed_dim():
    model = AudioCNN(N_CLASSES)
    emb   = model.embed(torch.randn(*MEL))
    assert emb.shape == (B, model._embed_dim)


def test_audio_cnn_lstm_embed_dim():
    model = AudioCNNLSTM(N_CLASSES)
    emb   = model.embed(torch.randn(*MEL))
    assert emb.shape == (B, model._embed_dim)


def test_visual_lstm_embed_dim():
    model = VisualLSTM(num_classes=N_CLASSES)
    emb   = model.embed(torch.randn(*VISUAL))
    assert emb.shape == (B, model._embed_dim)


def test_audio_visual_embed_dims_match():
    """CrossModalAttentionFusion requires equal embed dims (or projects)."""
    audio  = AudioCNNLSTM(N_CLASSES)
    visual = VisualLSTM(num_classes=N_CLASSES)
    assert audio._embed_dim == visual._embed_dim


# ── Gradient flow ─────────────────────────────────────────


@pytest.mark.parametrize("model_name", list(UNIMODAL | FUSION))
def test_backward_pass(model_name):
    model = build_model(model_name, CFG, N_CLASSES)
    model.train()
    multi = is_multimodal(model_name)

    if multi:
        out = model(torch.randn(*MEL), torch.randn(*VISUAL))
    elif model_name == "visual_lstm":
        out = model(torch.randn(*VISUAL))
    else:
        out = model(torch.randn(*MEL))

    loss = out.sum()
    loss.backward()

    missing = [
        name for name, p in model.named_parameters()
        if p.requires_grad and (p.grad is None or p.grad.abs().sum().item() == 0)
    ]
    assert not missing, f"Zero/missing gradients in {model_name}: {missing}"

    # Verify Q, K, and V projections in cross-modal attention all train
    if model_name == "attention":
        for blk in ("cross_attn_av", "cross_attn_va"):
            g = getattr(model, blk).in_proj_weight.grad
            d = g.shape[0] // 3
            assert g[:d].abs().sum().item() > 0, f"{blk} Q projection has zero gradient"
            assert g[d:2*d].abs().sum().item() > 0, f"{blk} K projection has zero gradient"
            assert g[2*d:].abs().sum().item() > 0, f"{blk} V projection has zero gradient"


# ── Eval mode ─────────────────────────────────────────────


def test_eval_mode_no_dropout_variance():
    """Same input should produce identical output in eval mode."""
    model = AudioCNNLSTM(N_CLASSES, dropout=0.5)
    model.eval()
    x   = torch.randn(*MEL)
    o1  = model(x)
    o2  = model(x)
    assert torch.allclose(o1, o2)


def test_no_nan_in_outputs():
    for Cls in [AudioCNN, AudioCNNLSTM]:
        model = Cls(N_CLASSES)
        model.eval()
        with torch.no_grad():
            out = model(torch.randn(*MEL))
        assert not torch.isnan(out).any(), f"NaN in {Cls.__name__} output"


# ── Builder factory ───────────────────────────────────────


@pytest.mark.parametrize("name", list(UNIMODAL | FUSION))
def test_builder_returns_nn_module(name):
    model = build_model(name, CFG, N_CLASSES)
    assert isinstance(model, torch.nn.Module)


def test_builder_unknown_name_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        build_model("nonexistent_model", CFG, N_CLASSES)


def test_is_multimodal_correct():
    for name in FUSION:
        assert is_multimodal(name) is True
    for name in UNIMODAL:
        assert is_multimodal(name) is False


# ── Decision-level fusion ─────────────────────────────────


def test_decision_weights_are_learnable():
    model = DecisionLevelFusion(AudioCNNLSTM(N_CLASSES), VisualLSTM(num_classes=N_CLASSES))
    assert model.weights.requires_grad


def test_decision_weights_softmax_sums_to_one():
    model = DecisionLevelFusion(AudioCNNLSTM(N_CLASSES), VisualLSTM(num_classes=N_CLASSES))
    w = torch.softmax(model.weights, dim=0)
    assert abs(w.sum().item() - 1.0) < 1e-5


# ── Parameter count sanity ────────────────────────────────


def test_audio_cnn_lstm_has_fewer_params_than_fusion():
    unimodal = build_model("audio_cnn_lstm", CFG, N_CLASSES)
    fusion   = build_model("attention",      CFG, N_CLASSES)
    n_uni    = sum(p.numel() for p in unimodal.parameters())
    n_fusion = sum(p.numel() for p in fusion.parameters())
    assert n_fusion > n_uni


if __name__ == "__main__":
    import inspect
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            sig = inspect.signature(fn)
            if sig.parameters:
                continue   # skip parametrized tests when run directly
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
