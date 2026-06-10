"""
Feature extraction pipeline.

Usage:
    python scripts/preprocess.py
    python scripts/preprocess.py --config config/settings.yaml

Outputs (written to datasets/processed/):
    mel/<stem>.npy          log-mel spectrogram  (n_mels, T)
    mfcc/<stem>.npy         MFCC + delta         (3*n_mfcc, T)
    landmarks/<stem>.npy    facial landmarks     (max_frames, 1404)
    manifest.csv            unified metadata for all parsed samples
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import yaml
import numpy as np
import pandas as pd
from tqdm import tqdm

from src.features import extract_audio_features, extract_visual_features
from src.datasets import load_datasets


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/settings.yaml")
    return p.parse_args()


def main():
    args = parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    print("Parsing datasets...")
    df = load_datasets(cfg)
    print(f"\nTotal samples: {len(df)}")
    print(df["label"].value_counts().to_string())

    proc = Path(cfg["data"]["processed_path"])
    for sub in ("mel", "mfcc", "landmarks"):
        (proc / sub).mkdir(parents=True, exist_ok=True)

    # Audio features
    print("\nExtracting audio features...")
    audio_cfg = cfg["audio"]
    audio_errors = []
    for _, row in tqdm(df.iterrows(), total=len(df)):
        stem = Path(row["audio_path"]).stem
        if (proc / "mel" / f"{stem}.npy").exists():
            continue
        try:
            feats = extract_audio_features(row["audio_path"], audio_cfg)
            np.save(proc / "mel"  / f"{stem}.npy", feats["mel"])
            np.save(proc / "mfcc" / f"{stem}.npy", feats["mfcc"])
        except Exception as exc:
            audio_errors.append((row["audio_path"], str(exc)))

    if audio_errors:
        err_path = proc / "errors_audio.txt"
        err_path.write_text("\n".join(f"{p}: {e}" for p, e in audio_errors))
        print(f"  {len(audio_errors)} audio errors — see {err_path}")

    # Visual features (only for samples that have a video path)
    vis_rows = df[df["video_path"].notna()]
    if len(vis_rows):
        vis_cfg = cfg["visual"]
        print(f"\nExtracting visual features ({len(vis_rows)} files with video)...")
        vis_errors = []
        for _, row in tqdm(vis_rows.iterrows(), total=len(vis_rows)):
            stem = Path(row["video_path"]).stem
            out = proc / "landmarks" / f"{stem}.npy"
            if out.exists():
                continue
            try:
                seq = extract_visual_features(
                    row["video_path"],
                    vis_cfg["max_frames"],
                    tuple(vis_cfg["frame_size"]),
                )
                if seq is not None:
                    np.save(out, seq)
            except Exception as exc:
                vis_errors.append((row["video_path"], str(exc)))

        if vis_errors:
            err_path = proc / "errors_visual.txt"
            err_path.write_text("\n".join(f"{p}: {e}" for p, e in vis_errors))
            print(f"  {len(vis_errors)} visual errors — see {err_path}")
    else:
        print("\nNo video paths found — skipping visual feature extraction.")

    manifest = proc / "manifest.csv"
    df.to_csv(manifest, index=False)
    print(f"\nDone. Manifest: {manifest}  ({len(df)} rows)")


if __name__ == "__main__":
    main()
