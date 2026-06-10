import math

import torch.nn as nn

from .audio import AudioCNN, AudioCNNLSTM
from .visual import VisualLSTM
from .fusion import build_fusion_model

UNIMODAL = {"audio_cnn", "audio_cnn_lstm", "visual_lstm"}
FUSION    = {"feature_level", "decision_level", "attention"}


def is_multimodal(name: str) -> bool:
    return name in FUSION


def _n_frames(cfg: dict) -> int:
    sr  = cfg["audio"]["sample_rate"]
    dur = cfg["audio"]["duration"]
    hop = cfg["audio"]["hop_length"]
    return math.floor(sr * dur / hop) + 1


def _audio_backbone(cfg: dict, num_classes: int) -> AudioCNNLSTM:
    c = cfg["model"]["audio_cnn_lstm"]
    return AudioCNNLSTM(
        num_classes, c["cnn_channels"], c["lstm_hidden"],
        c["lstm_layers"], c["dropout"], cfg["audio"]["n_mels"],
    )


def _visual_backbone(cfg: dict, num_classes: int) -> VisualLSTM:
    c = cfg["model"]["visual_lstm"]
    return VisualLSTM(1404, c["hidden_dim"], c["num_layers"], num_classes, c["dropout"])


def build_model(name: str, cfg: dict, num_classes: int) -> nn.Module:
    mc = cfg["model"]
    n_mels = cfg["audio"]["n_mels"]

    if name == "audio_cnn":
        c = mc["audio_cnn"]
        return AudioCNN(num_classes, c["channels"], c["dropout"])

    if name == "audio_cnn_lstm":
        c = mc["audio_cnn_lstm"]
        return AudioCNNLSTM(
            num_classes, c["cnn_channels"], c["lstm_hidden"],
            c["lstm_layers"], c["dropout"], n_mels,
        )

    if name == "visual_lstm":
        return _visual_backbone(cfg, num_classes)

    if name in FUSION:
        audio_base  = _audio_backbone(cfg, num_classes)
        visual_base = _visual_backbone(cfg, num_classes)
        fc = mc["fusion"]
        return build_fusion_model(name, audio_base, visual_base, num_classes,
                                  fc["n_heads"], fc["dropout"])

    raise ValueError(f"Unknown model: {name!r}. Choose from {UNIMODAL | FUSION}")
