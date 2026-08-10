import re
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from .constants import LANDMARK_DIM

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


_MSP_SPEAKER_RE = re.compile(r"^[MF]\d+$")


def msp_speaker(fname: str) -> Optional[str]:
    """Extract the actor id from an MSP-IMPROV filename stem.

        MSP-IMPROV-S01A-M01-P-FM01
                        ^^^ actor (M01..M06, F01..F06)

    Scans for the first hyphen-delimited segment matching a single M/F followed
    by digits, rather than slicing at a fixed offset. "MSP", "IMPROV", "S01A"
    and the trailing take id ("FM01", "FF01") do not match that pattern.

    Returns None when no actor field is recognisable, so the caller decides how
    to handle it instead of this inventing a speaker.
    """
    for seg in fname.split("-"):
        if _MSP_SPEAKER_RE.match(seg):
            return seg
    return None


def parse_msp_improv(root: str, emotion_map: dict) -> pd.DataFrame:
    """Parse MSP-IMPROV.

    Evalution.txt (note original typo) has semicolon-delimited fields.
    Field 0 = filename stem, field 2 = categorical emotion label.
    Adjust field index if your copy uses a different column ordering.
    """
    records = []
    unknown_speakers = 0
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
            spk = msp_speaker(fname)
            if spk is None:
                unknown_speakers += 1
            records.append({
                "audio_path": str(audio),
                "video_path": None,
                "label": label,
                # Unrecognised stems collapse into one bucket. That is coarse
                # but leakage-safe; per-file ids would scatter one actor across
                # splits and break speaker independence.
                "speaker": f"msp_{spk}" if spk else "msp_unknown",
                "dataset": "msp_improv",
            })

    if unknown_speakers:
        print(
            f"  msp_improv: {unknown_speakers} files had no recognisable actor "
            f"field and were grouped as 'msp_unknown' — check the stem layout"
        )
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

    # np.asarray(..., dtype=object) is load-bearing, not tidying. Modern pandas
    # returns an extension array (StringArray) from .unique(), and numpy warns:
    #   "shuffling a 'StringArray' ... `shuffle` is not guaranteed to behave
    #    correctly ... may contain duplicates after shuffling"
    # A duplicate here would place one speaker in two splits and silently void
    # the speaker-independence guarantee every reported number rests on. No
    # corruption was observed on pandas 3.0.3 / numpy 2.4.6, but the guarantee
    # must not depend on which pandas happens to be installed.
    speakers = np.asarray(df["speaker"].unique(), dtype=object)
    rng.shuffle(speakers)

    n = len(speakers)
    n_test = max(1, int(n * test_frac))
    n_val  = max(1, int(n * val_frac))
    test_spk  = set(speakers[:n_test])
    val_spk   = set(speakers[n_test: n_test + n_val])
    train_spk = set(speakers[n_test + n_val:])

    # Cheap, and it converts a silent leak into a loud failure.
    assert len(train_spk) + len(val_spk) + len(test_spk) == n, (
        "speaker partition lost or duplicated speakers during shuffle: "
        f"{len(train_spk)}+{len(val_spk)}+{len(test_spk)} != {n}"
    )
    assert not (train_spk & val_spk) and not (val_spk & test_spk) \
        and not (train_spk & test_spk), "speaker splits overlap"

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
        max_frames: int = 75,      # must match cfg["visual"]["max_frames"]
    ):
        self.df = df.reset_index(drop=True)
        self.proc = Path(processed_dir)
        self.modality = modality
        self.feature = feature
        self.max_frames = max_frames

    def __len__(self) -> int:
        return len(self.df)

    def _load_audio(self, audio_path: str) -> torch.Tensor:
        p = self.proc / self.feature / (Path(audio_path).stem + ".npy")
        t = torch.from_numpy(np.load(p)).float()
        # Both feature types are (freq, T) on disk and both are consumed by
        # Conv2d, so both need the channel axis — mel: (1, n_mels, T),
        # mfcc: (1, 3*n_mfcc, T). Adding it only for mel left MFCC tensors 3-D
        # and Conv2d read the batch dimension as channels.
        return t.unsqueeze(0)

    def _load_visual(self, video_path: Optional[str]) -> torch.Tensor:
        if video_path:
            p = self.proc / "landmarks" / (Path(video_path).stem + ".npy")
            if p.exists():
                return torch.from_numpy(np.load(p)).float()
        # zero-fill when video unavailable — this is what lets audio-only
        # corpora participate in multimodal training
        return torch.zeros(self.max_frames, LANDMARK_DIM)

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
