import torch
import torch.nn as nn
import torch.nn.functional as F


class VisualLSTM(nn.Module):
    """Bidirectional LSTM with attention pooling over facial landmark sequences."""

    def __init__(
        self,
        input_dim: int = 1404,   # 468 landmarks * 3 coords
        hidden_dim: int = 256,
        num_layers: int = 2,
        num_classes: int = 6,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.proj = nn.Linear(input_dim, 256)
        self.lstm = nn.LSTM(
            256, hidden_dim, num_layers,
            batch_first=True, bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self._embed_dim = hidden_dim * 2
        self.head = nn.Sequential(
            nn.Linear(self._embed_dim, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes),
        )

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, input_dim)
        x = F.relu(self.proj(x))
        out, _ = self.lstm(x)                       # (B, T, 2H)
        attn = torch.softmax(out.mean(-1, keepdim=True), dim=1)
        return (out * attn).sum(1)                  # (B, 2H)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.embed(x))
