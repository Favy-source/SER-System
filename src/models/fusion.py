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
        # Strip unused unimodal classifier heads so they do not sit as dead,
        # zero-gradient parameters inflating parameter counts and checkpoints.
        if hasattr(self.audio, "head"):
            self.audio.head = nn.Identity()
        if hasattr(self.visual, "head"):
            self.visual.head = nn.Identity()
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
        if hasattr(self.audio, "head"):
            self.audio.head = nn.Identity()
        if hasattr(self.visual, "head"):
            self.visual.head = nn.Identity()
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
        """Temporal cross-modal attention over pre-pooled sequences (T_a x T_v)."""
        a_seq = (
            self.audio.encode_sequence(audio)
            if hasattr(self.audio, "encode_sequence")
            else self.audio.embed(audio).unsqueeze(1)
        )
        v_raw = (
            self.visual.encode_sequence(visual)
            if hasattr(self.visual, "encode_sequence")
            else self.visual.embed(visual).unsqueeze(1)
        )
        v_seq = self.v_proj(v_raw)

        if hasattr(self.visual, "valid_mask"):
            v_valid = self.visual.valid_mask(visual)          # (B, T_v)
            v_has_any = v_valid.any(dim=1)                    # (B,)
            # Mask padded frames only on samples with at least one real frame;
            # masking every key would yield softmax(-inf) -> NaN.
            v_key_pad = (~v_valid) & v_has_any.unsqueeze(1)
        else:
            v_valid = torch.ones(v_seq.shape[:2], dtype=torch.bool, device=v_seq.device)
            v_has_any = torch.ones(v_seq.size(0), dtype=torch.bool, device=v_seq.device)
            v_key_pad = None

        a_ctx, _ = self.cross_attn_av(a_seq, v_seq, v_seq, key_padding_mask=v_key_pad)
        v_ctx, _ = self.cross_attn_va(v_seq, a_seq, a_seq)

        a_out = self.norm_a(a_seq + a_ctx)                    # (B, T_a, D)
        v_out = self.norm_v(v_seq + v_ctx)                    # (B, T_v, D)

        a_attn = torch.softmax(a_out.mean(-1, keepdim=True), dim=1)
        a_pool = (a_out * a_attn).sum(1)                      # (B, D)

        v_scores = v_out.mean(-1)
        v_masked = v_scores.masked_fill(~v_valid, -1e9)
        v_safe = torch.where(v_has_any.unsqueeze(1), v_masked, torch.zeros_like(v_scores))
        v_attn = torch.softmax(v_safe, dim=1).unsqueeze(-1)
        v_pool = (v_out * v_attn).sum(1) * v_has_any.unsqueeze(1).to(v_out.dtype)

        return self.head(torch.cat([a_pool, v_pool], dim=-1))


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
