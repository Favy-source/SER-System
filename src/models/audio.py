from typing import List

import torch
import torch.nn as nn


class _ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, kernel: int = 3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel, padding=kernel // 2, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class AudioCNN(nn.Module):
    """Lightweight 2-D CNN on mel spectrogram — audio-only baseline."""

    def __init__(
        self,
        num_classes: int = 6,
        channels: List[int] = None,
        dropout: float = 0.3,
    ):
        super().__init__()
        channels = channels or [32, 64, 128, 256]

        layers: list = [_ConvBlock(1, channels[0])]
        for i in range(1, len(channels)):
            layers += [
                _ConvBlock(channels[i - 1], channels[i]),
                nn.MaxPool2d(2),
                nn.Dropout2d(dropout / 2),
            ]
        self.cnn = nn.Sequential(*layers)
        self.pool = nn.AdaptiveAvgPool2d((4, 4))
        self._embed_dim = channels[-1] * 16
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(self._embed_dim, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, num_classes),
        )

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        return self.pool(self.cnn(x)).flatten(1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.embed(x))


class AudioCNNLSTM(nn.Module):
    """CNN feature extractor + bidirectional LSTM with attention pooling."""

    def __init__(
        self,
        num_classes: int = 6,
        cnn_channels: List[int] = None,
        lstm_hidden: int = 256,
        lstm_layers: int = 2,
        dropout: float = 0.3,
        n_freq: int = 128,
    ):
        """n_freq — rows on the frequency axis of the input feature.

        128 for a default log-mel spectrogram, 120 for MFCC + delta + delta-delta.
        Use src.models.builder.feature_height() to derive it from a config.
        """
        super().__init__()
        cnn_channels = cnn_channels or [32, 64, 128]

        layers: list = [_ConvBlock(1, cnn_channels[0]), nn.MaxPool2d(2)]
        for i in range(1, len(cnn_channels)):
            layers += [_ConvBlock(cnn_channels[i - 1], cnn_channels[i]), nn.MaxPool2d(2)]
        self.cnn = nn.Sequential(*layers)

        # derive LSTM input size from a dummy forward pass, so changing n_freq
        # or the channel list needs no hand-computed shapes
        with torch.no_grad():
            dummy = torch.zeros(1, 1, n_freq, 130)
            out = self.cnn(dummy)
            _, C, F, _ = out.shape
            lstm_in = C * F

        self.lstm = nn.LSTM(
            lstm_in, lstm_hidden, lstm_layers,
            batch_first=True, bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )
        self._embed_dim = lstm_hidden * 2
        self.head = nn.Sequential(
            nn.Linear(self._embed_dim, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes),
        )

    def encode_sequence(self, x: torch.Tensor) -> torch.Tensor:
        """Return pre-pooled temporal features (B, T', 2H) for cross-modal attention."""
        B = x.size(0)
        feat = self.cnn(x)                          # (B, C, F, T')
        _, C, F, T2 = feat.shape
        feat = feat.permute(0, 3, 1, 2).reshape(B, T2, C * F)
        out, _ = self.lstm(feat)                    # (B, T', 2H)
        return out

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        out = self.encode_sequence(x)               # (B, T', 2H)
        attn = torch.softmax(out.mean(-1, keepdim=True), dim=1)
        return (out * attn).sum(1)                  # (B, 2H)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.embed(x))
