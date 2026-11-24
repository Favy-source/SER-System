import torch
import torch.nn as nn
import torch.nn.functional as F


from ..constants import LANDMARK_DIM


class VisualLSTM(nn.Module):
    """Bidirectional LSTM with attention pooling over facial landmark sequences."""

    def __init__(
        self,
        input_dim: int = LANDMARK_DIM,   # N_FACE_LANDMARKS * 3
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

    def valid_mask(self, x: torch.Tensor) -> torch.Tensor:
        """(B, T) bool mask: True for real landmark frames, False for zero padding."""
        return x.abs().sum(dim=-1) > 0

    def encode_sequence(self, x: torch.Tensor) -> torch.Tensor:
        """Return pre-pooled temporal features (B, T, 2H) with padded frames zeroed."""
        valid = self.valid_mask(x)                  # (B, T)
        h = F.relu(self.proj(x))
        out, _ = self.lstm(h)                       # (B, T, 2H)
        return out * valid.unsqueeze(-1).to(out.dtype)

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, input_dim)
        valid = self.valid_mask(x)                  # (B, T)
        out = self.encode_sequence(x)               # (B, T, 2H)
        scores = out.mean(-1)                       # (B, T)
        has_any = valid.any(dim=1, keepdim=True)    # (B, 1)
        masked = scores.masked_fill(~valid, -1e9)
        safe = torch.where(has_any, masked, torch.zeros_like(scores))
        attn = torch.softmax(safe, dim=1).unsqueeze(-1)
        return (out * attn).sum(1)                  # (B, 2H)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.embed(x))
