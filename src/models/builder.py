import math

import torch.nn as nn

from ..constants import LANDMARK_DIM
from .audio import AudioCNN, AudioCNNLSTM
from .visual import VisualLSTM
from .fusion import build_fusion_model

UNIMODAL = {"audio_cnn", "audio_cnn_lstm", "visual_lstm"}
FUSION    = {"feature_level", "decision_level", "attention"}


def is_multimodal(name: str) -> bool:
    return name in FUSION


def n_frames(cfg: dict) -> int:
    """Time-axis length of the audio feature: floor(sr * duration / hop) + 1."""
    sr  = cfg["audio"]["sample_rate"]
    dur = cfg["audio"]["duration"]
    hop = cfg["audio"]["hop_length"]
    return math.floor(sr * dur / hop) + 1


def feature_height(cfg: dict, feature: str = "mel") -> int:
    """Rows on the frequency axis of the audio feature.

    The CNN front ends treat the feature as a single-channel 2-D image, and
    AudioCNNLSTM sizes its LSTM input from how far the CNN downsamples this
    axis. So the two feature types produce different LSTM widths and the model
    must be built knowing which one it will receive:

        mel   -> n_mels                 (128 by default)
        mfcc  -> n_mfcc * 3 with deltas (120 by default)
    """
    acfg = cfg["audio"]
    if feature == "mfcc":
        n = acfg["n_mfcc"]
        return n * 3 if acfg.get("use_delta", True) else n
    return acfg["n_mels"]


def _audio_backbone(cfg: dict, num_classes: int, feature: str = "mel") -> AudioCNNLSTM:
    c = cfg["model"]["audio_cnn_lstm"]
    return AudioCNNLSTM(
        num_classes, c["cnn_channels"], c["lstm_hidden"],
        c["lstm_layers"], c["dropout"], feature_height(cfg, feature),
    )


def _visual_backbone(cfg: dict, num_classes: int) -> VisualLSTM:
    c = cfg["model"]["visual_lstm"]
    return VisualLSTM(LANDMARK_DIM, c["hidden_dim"], c["num_layers"],
                      num_classes, c["dropout"])


def build_model(
    name: str,
    cfg: dict,
    num_classes: int,
    feature: str = "mel",
) -> nn.Module:
    """Construct an architecture by name.

    `feature` is required for the recurrent audio backbone, whose LSTM input
    width depends on the frequency-axis height of the incoming feature. Pass
    the same value used to extract the features this model will be trained or
    served on, or the state dict will not match.
    """
    mc = cfg["model"]

    if name == "audio_cnn":
        c = mc["audio_cnn"]
        # AdaptiveAvgPool2d makes this one height-agnostic
        return AudioCNN(num_classes, c["channels"], c["dropout"])

    if name == "audio_cnn_lstm":
        return _audio_backbone(cfg, num_classes, feature)

    if name == "visual_lstm":
        return _visual_backbone(cfg, num_classes)

    if name in FUSION:
        audio_base  = _audio_backbone(cfg, num_classes, feature)
        visual_base = _visual_backbone(cfg, num_classes)
        fc = mc["fusion"]
        return build_fusion_model(name, audio_base, visual_base, num_classes,
                                  fc["n_heads"], fc["dropout"])

    raise ValueError(f"Unknown model: {name!r}. Choose from {UNIMODAL | FUSION}")
