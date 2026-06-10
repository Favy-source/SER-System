from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

UNIFIED = ["neutral", "happy", "sad", "angry", "fearful", "disgust"]
LABEL2IDX = {e: i for i, e in enumerate(UNIFIED)}
IDX2LABEL = {i: e for e, i in LABEL2IDX.items()}


# ---------------------------------------------------------------------------
# Dataset parsers
# ---------------------------------------------------------------------------

def parse_ravdess(root: str, emotion_map: dict) -> pd.DataFrame:
    records = []
    for f in sorted(Path(root).rglob("*.wav")):
        parts = f.stem.split("-")
        if len(parts) < 7:
            continue
        label = emotion_map.get(parts[2])
        if label is None:
            continue
        video = f.with_suffix(".mp4")
        records.append({
            "audio_path": str(f),
            "video_path": str(video) if video.exists() else None,
            "label": label,
            "speaker": f"ravdess_{parts[6]}",
            "dataset": "ravdess",
        })
    return pd.DataFrame(records)


def parse_cremad(root: str, emotion_map: dict) -> pd.DataFrame:
    records = []
    audio_dir = Path(root) / "AudioWAV"
    video_dir = Path(root) / "VideoFlash"
    for f in sorted(audio_dir.glob("*.wav")):
        parts = f.stem.split("_")
        if len(parts) < 3:
            continue
        label = emotion_map.get(parts[2])
        if label is None:
            continue
        video = video_dir / f.with_suffix(".flv").name
        records.append({
            "audio_path": str(f),
            "video_path": str(video) if video.exists() else None,
            "label": label,
            "speaker": f"cremad_{parts[0]}",
            "dataset": "cremad",
        })
    return pd.DataFrame(records)


def parse_msp_improv(root: str, emotion_map: dict) -> pd.DataFrame:
    """Parse MSP-IMPROV.

    Evalution.txt (note original typo) has semicolon-delimited fields.
    Field 0 = filename stem, field 2 = categorical emotion label.
    Adjust field index if your copy uses a different column ordering.
    """
    records = []
    label_file = Path(root) / "Evalution.txt"
    if not label_file.exists():
        return pd.DataFrame()
    with open(label_file) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 3:
                continue
            fname, code = parts[0], parts[2]
            label = emotion_map.get(code)
            if label is None:
                continue
            audio = Path(root) / "Audio" / f"{fname}.wav"
            if not audio.exists():
                continue
            records.append({
                "audio_path": str(audio),
                "video_path": None,
                "label": label,
                "speaker": f"msp_{fname[:6]}",
                "dataset": "msp_improv",
            })
    return pd.DataFrame(records)


def load_datasets(cfg: dict) -> pd.DataFrame:
    dfs = []
    root = Path(".")
    paths = {
        "ravdess": (root / cfg["data"]["ravdess_path"], parse_ravdess, cfg["emotions"]["ravdess_map"]),
        "cremad":  (root / cfg["data"]["cremad_path"],  parse_cremad,  cfg["emotions"]["cremad_map"]),
        "msp":     (root / cfg["data"]["msp_improv_path"], parse_msp_improv, cfg["emotions"]["msp_improv_map"]),
    }
    for name, (path, parser, emap) in paths.items():
        if path.exists():
            df = parser(str(path), emap)
            if len(df):
                print(f"  {name}: {len(df)} samples")
                dfs.append(df)
            else:
                print(f"  {name}: directory found but no samples parsed")
        else:
            print(f"  {name}: not found at {path} — skipping")

    if not dfs:
        raise RuntimeError("No datasets found. Check paths in config/settings.yaml.")
    return pd.concat(dfs, ignore_index=True)


# ---------------------------------------------------------------------------
# Speaker-independent split
# ---------------------------------------------------------------------------

def speaker_independent_split(
    df: pd.DataFrame,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    speakers = df["speaker"].unique()
    rng.shuffle(speakers)
    n = len(speakers)
    n_test = max(1, int(n * test_frac))
    n_val  = max(1, int(n * val_frac))
    test_spk  = set(speakers[:n_test])
    val_spk   = set(speakers[n_test: n_test + n_val])
    train_spk = set(speakers[n_test + n_val:])
    return (
        df[df["speaker"].isin(train_spk)].reset_index(drop=True),
        df[df["speaker"].isin(val_spk)].reset_index(drop=True),
        df[df["speaker"].isin(test_spk)].reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# PyTorch Dataset
# ---------------------------------------------------------------------------

class EmotionDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        processed_dir: str,
        modality: str = "audio",   # "audio" | "visual" | "multimodal"
        feature: str = "mel",      # "mel"   | "mfcc"
    ):
        self.df = df.reset_index(drop=True)
        self.proc = Path(processed_dir)
        self.modality = modality
        self.feature = feature

    def __len__(self) -> int:
        return len(self.df)

    def _load_audio(self, audio_path: str) -> torch.Tensor:
        p = self.proc / self.feature / (Path(audio_path).stem + ".npy")
        t = torch.from_numpy(np.load(p)).float()
        if self.feature == "mel":
            t = t.unsqueeze(0)  # (1, n_mels, T)
        return t

    def _load_visual(self, video_path: Optional[str]) -> torch.Tensor:
        if video_path:
            p = self.proc / "landmarks" / (Path(video_path).stem + ".npy")
            if p.exists():
                return torch.from_numpy(np.load(p)).float()
        return torch.zeros(75, 1404)  # zero-fill when video unavailable

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        label = torch.tensor(LABEL2IDX[row["label"]], dtype=torch.long)

        if self.modality == "audio":
            return self._load_audio(row["audio_path"]), label

        if self.modality == "visual":
            return self._load_visual(row.get("video_path")), label

        # multimodal
        return (
            self._load_audio(row["audio_path"]),
            self._load_visual(row.get("video_path")),
            label,
        )
