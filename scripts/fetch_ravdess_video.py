"""
Stream RAVDESS video actor-by-actor, extract face landmarks, delete the video.

    python3 scripts/fetch_ravdess_video.py                    # all 24 actors
    python3 scripts/fetch_ravdess_video.py --actors 1-8       # a subset
    python3 scripts/fetch_ravdess_video.py --keep-video       # don't delete

WHY STREAM RATHER THAN BULK DOWNLOAD
    The 24 video archives are ~528 MB each — about 12.5 GB in total, which will
    not fit comfortably on a disk that is already near capacity. But the video is
    TRANSIENT: landmark extraction reduces each clip to a ~421 KB .npy, so only
    ~526 MB of derived data is actually needed. Processing one actor at a time
    keeps peak extra usage near 1 GB instead of 12.5 GB.

RESUMABLE
    An actor whose landmark files already exist is skipped, so an interrupted run
    can simply be restarted.

THE FILENAME TRAP
    RAVDESS encodes modality in field 1: 01 = audio-visual, 02 = video-only,
    03 = audio-only. Audio is `03-...wav`; its video counterpart is `01-...mp4`.
    The stems differ, so landmarks are keyed by the VIDEO stem, and the manifest's
    video_path must record that stem for EmotionDataset to find them. This script
    updates manifest.csv accordingly — note that it stores the path the video HAD,
    which is deliberate: only Path(video_path).stem is ever used downstream, so
    the row stays valid after the .mp4 is deleted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import functools
import shutil
import subprocess
import tempfile
import time
import zipfile

import numpy as np
import pandas as pd
import yaml

from src.features import extract_visual_features

URL = ("https://zenodo.org/records/1188976/files/"
       "Video_Speech_Actor_{a:02d}.zip?download=1")

# Redirected python stdout is block-buffered, so a multi-hour job writes nothing
# to its log for minutes at a time and looks hung. Flush every line.
print = functools.partial(__builtins__.print if not isinstance(__builtins__, dict)
                          else __builtins__["print"], flush=True)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--actors", default="1-24",
                   help="e.g. '1-24', '1-8', or '3,7,11'")
    p.add_argument("--config", default="config/settings.yaml")
    p.add_argument("--keep-video", action="store_true",
                   help="keep the .mp4 files (needs ~12.5 GB for all actors)")
    p.add_argument("--cache", default=None,
                   help="reuse an already-downloaded zip for the first actor")
    return p.parse_args()


def actor_list(spec):
    out = []
    for chunk in spec.split(","):
        if "-" in chunk:
            a, b = chunk.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(chunk))
    return sorted(set(out))


def human(n):
    return f"{n/1024/1024:.0f} MB" if n < 1024**3 else f"{n/1024**3:.2f} GB"


def download(actor, dest: Path, cache=None):
    if cache and Path(cache).exists():
        print(f"    reusing cached zip: {cache}")
        shutil.copy(cache, dest)
        return dest
    url = URL.format(a=actor)
    # curl rather than urllib: resumes, and reports nothing to stdout so the
    # per-actor log stays readable.
    subprocess.run(["curl", "-sL", "--retry", "3", "-o", str(dest), url], check=True)
    return dest


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    proc = Path(cfg["data"]["processed_path"])
    lm_dir = proc / "landmarks"
    lm_dir.mkdir(parents=True, exist_ok=True)
    video_root = Path(cfg["data"]["ravdess_path"])
    max_frames = cfg["visual"]["max_frames"]
    frame_size = tuple(cfg["visual"]["frame_size"])

    manifest_path = proc / "manifest.csv"
    if not manifest_path.exists():
        sys.exit("manifest.csv not found — run scripts/preprocess.py first")
    manifest = pd.read_csv(manifest_path)

    # Which video stems do we actually need? Only utterances that survived the
    # emotion mapping, i.e. the ones already in the manifest.
    wanted = set()
    for ap in manifest["audio_path"]:
        parts = Path(ap).stem.split("-")
        wanted.add("-".join(["01"] + parts[1:]))
    print(f"manifest rows: {len(manifest)}   video stems needed: {len(wanted)}")

    actors = actor_list(args.actors)
    print(f"actors: {actors[0]}..{actors[-1]} ({len(actors)})   "
          f"delete video after extraction: {not args.keep_video}\n")

    t_start = time.time()
    total_new = total_skip = total_fail = 0

    for actor in actors:
        tag = f"Actor_{actor:02d}"
        expected = sorted(s for s in wanted if s.endswith(f"-{actor:02d}"))
        already = [s for s in expected if (lm_dir / f"{s}.npy").exists()]
        if len(already) == len(expected) and expected:
            print(f"{tag}: all {len(expected)} landmarks present — skipping")
            total_skip += len(expected)
            continue

        print(f"{tag}: need {len(expected) - len(already)}/{len(expected)}")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = td / f"{tag}.zip"
            t0 = time.time()
            try:
                download(actor, zp, cache=args.cache if actor == actors[0] else None)
            except subprocess.CalledProcessError as e:
                print(f"    download FAILED: {e}")
                continue
            print(f"    downloaded {human(zp.stat().st_size)} in {time.time()-t0:.0f}s")

            # Extract only the modality-01 clips we need; 02 is video-only and
            # carries the same frames, so it would double the work for nothing.
            with zipfile.ZipFile(zp) as z:
                members = [m for m in z.namelist()
                           if m.endswith(".mp4") and Path(m).stem in wanted]
                z.extractall(td, members=members)
            vids = sorted(td.rglob("*.mp4"))
            print(f"    extracted {len(vids)} clips")

            t0 = time.time()
            new = fail = 0
            for i, v in enumerate(vids, 1):
                out = lm_dir / f"{v.stem}.npy"
                if out.exists():
                    continue
                try:
                    seq = extract_visual_features(str(v), max_frames, frame_size)
                except Exception as exc:
                    print(f"      {v.stem}: ERROR {type(exc).__name__}: {exc}")
                    fail += 1
                    continue
                if seq is None:
                    fail += 1
                    continue
                np.save(out, seq)
                new += 1
                if i % 20 == 0:
                    print(f"      {i}/{len(vids)}  ({time.time()-t0:.0f}s elapsed)")

            if args.keep_video:
                dest = video_root / tag
                dest.mkdir(parents=True, exist_ok=True)
                for v in vids:
                    shutil.move(str(v), dest / v.name)

            total_new += new
            total_fail += fail
            print(f"    landmarks: {new} written, {fail} no-face/error "
                  f"({time.time()-t0:.0f}s)")
        # tempdir (and the zip) removed here, reclaiming the space immediately

    # ---- update the manifest so EmotionDataset can find the landmarks ----
    def video_for(audio_path):
        stem = "-".join(["01"] + Path(audio_path).stem.split("-")[1:])
        if (lm_dir / f"{stem}.npy").exists():
            # Records the path the video HAD. Only .stem is used downstream, so
            # this stays correct after the .mp4 has been deleted.
            return str(video_root / f"Actor_{Path(audio_path).stem.split('-')[6]}" / f"{stem}.mp4")
        return None

    manifest["video_path"] = manifest["audio_path"].map(video_for)
    manifest.to_csv(manifest_path, index=False)
    have = int(manifest["video_path"].notna().sum())

    print(f"\n{'='*66}")
    print(f"  landmarks written this run : {total_new}")
    print(f"  already present            : {total_skip}")
    print(f"  no face / errors           : {total_fail}")
    print(f"  manifest rows with video   : {have}/{len(manifest)}")
    print(f"  landmarks on disk          : {human(sum(p.stat().st_size for p in lm_dir.glob('*.npy')))}")
    print(f"  elapsed                    : {(time.time()-t_start)/60:.1f} min")
    print(f"{'='*66}")
    if have == 0:
        print("  NOTHING matched — check that video stems use modality 01")
    else:
        print("  next: scripts/train.py --model decision_level")


if __name__ == "__main__":
    main()
