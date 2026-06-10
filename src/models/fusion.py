import torch
import torch.nn as nn


class FeatureLevelFusion(nn.Module):
    """Concatenate audio + visual embeddings, then classify."""

    def __init__(
        self,
        audio_model: nn.Module,
        visual_model: nn.Module,
        num_classes: int = 6,
        hidden: int = 512,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.audio = audio_model
        self.visual = visual_model
        self.head = nn.Sequential(
            nn.Linear(audio_model._embed_dim + visual_model._embed_dim, hidden),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden, num_classes),
        )

    def forward(self, audio: torch.Tensor, visual: torch.Tensor) -> torch.Tensor:
        a = self.audio.embed(audio)
        v = self.visual.embed(visual)
        return self.head(torch.cat([a, v], dim=-1))


class DecisionLevelFusion(nn.Module):
    """Learnable weighted average of unimodal logit scores."""

    def __init__(
        self,
        audio_model: nn.Module,
        visual_model: nn.Module,
        num_classes: int = 6,
    ):
        super().__init__()
        self.audio = audio_model
        self.visual = visual_model
        self.weights = nn.Parameter(torch.ones(2))

    def forward(self, audio: torch.Tensor, visual: torch.Tensor) -> torch.Tensor:
        w = torch.softmax(self.weights, dim=0)
        return w[0] * self.audio(audio) + w[1] * self.visual(visual)


class CrossModalAttentionFusion(nn.Module):
    """Cross-modal attention: audio attends to visual and visual attends to audio."""

    def __init__(
        self,
        audio_model: nn.Module,
        visual_model: nn.Module,
        num_classes: int = 6,
        n_heads: int = 8,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.audio = audio_model
        self.visual = visual_model
        dim = audio_model._embed_dim

        self.v_proj = (
            nn.Linear(visual_model._embed_dim, dim)
            if visual_model._embed_dim != dim else nn.Identity()
        )
        self.cross_attn_av = nn.MultiheadAttention(dim, n_heads, dropout=dropout, batch_first=True)
        self.cross_attn_va = nn.MultiheadAttention(dim, n_heads, dropout=dropout, batch_first=True)
        self.norm_a = nn.LayerNorm(dim)
        self.norm_v = nn.LayerNorm(dim)
        self.head = nn.Sequential(
            nn.Linear(dim * 2, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, num_classes),
        )

    def forward(self, audio: torch.Tensor, visual: torch.Tensor) -> torch.Tensor:
        a = self.audio.embed(audio).unsqueeze(1)              # (B, 1, D)
        v = self.v_proj(self.visual.embed(visual)).unsqueeze(1)  # (B, 1, D)

        a_ctx, _ = self.cross_attn_av(a, v, v)
        v_ctx, _ = self.cross_attn_va(v, a, a)

        a_out = self.norm_a(a + a_ctx).squeeze(1)
        v_out = self.norm_v(v + v_ctx).squeeze(1)
        return self.head(torch.cat([a_out, v_out], dim=-1))


def build_fusion_model(
    strategy: str,
    audio_model: nn.Module,
    visual_model: nn.Module,
    num_classes: int = 6,
    n_heads: int = 8,
    dropout: float = 0.3,
) -> nn.Module:
    if strategy == "feature_level":
        return FeatureLevelFusion(audio_model, visual_model, num_classes, dropout=dropout)
    if strategy == "decision_level":
        return DecisionLevelFusion(audio_model, visual_model, num_classes)
    if strategy == "attention":
        return CrossModalAttentionFusion(audio_model, visual_model, num_classes, n_heads, dropout)
    raise ValueError(f"Unknown fusion strategy: {strategy!r}")
