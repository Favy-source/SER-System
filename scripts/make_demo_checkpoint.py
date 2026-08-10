"""
Create UNTRAINED checkpoints so the system can be run and demonstrated before
any corpus has been downloaded or any model trained.

    python3 scripts/make_demo_checkpoint.py                 # all six
    python3 scripts/make_demo_checkpoint.py --model attention

WHAT THIS IS FOR
    Exercising the machinery: the API, the WebSocket, the webcam landmark path,
    the fusion forward passes, the UI. Everything downstream of "a checkpoint
    exists" becomes reachable.

WHAT THIS IS NOT
    A model. The weights are random initialisations, so predictions are noise.
    A confident-looking "HAPPY 87%" from one of these means nothing at all.

    Because that is genuinely dangerous in a live demo or a screenshot, every
    checkpoint written here carries `untrained: True`, which InferenceEngine
    surfaces, /health reports, and the front end renders as a standing warning
    banner. Do not remove that flag to make the UI look cleaner.

Outputs: models/DEMO_UNTRAINED_<model>.pt
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import torch
import yaml

from src.datasets import UNIFIED
from src.models.builder import FUSION, UNIMODAL, build_model

ALL_MODELS = sorted(UNIMODAL | FUSION)
PREFIX = "DEMO_UNTRAINED_"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="all", choices=["all"] + ALL_MODELS)
    p.add_argument("--feature", default="mel", choices=["mel", "mfcc"])
    p.add_argument("--config", default="config/settings.yaml")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    out_dir = Path(cfg["output"]["model_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    names = ALL_MODELS if args.model == "all" else [args.model]
    torch.manual_seed(args.seed)

    print("=" * 72)
    print("  Writing UNTRAINED checkpoints — predictions from these are NOISE")
    print("=" * 72)

    for name in names:
        model = build_model(name, cfg, len(UNIFIED), args.feature)
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        path = out_dir / f"{PREFIX}{name}.pt"

        torch.save({
            "epoch": 0,
            "model": model.state_dict(),
            "val_loss": float("nan"),
            "val_acc": float("nan"),
            "model_name": name,
            "feature": args.feature,
            "cfg": cfg,
            # The honesty flag. Surfaced by InferenceEngine -> /health -> UI.
            "untrained": True,
        }, path)

        kind = "fusion  " if name in FUSION else "unimodal"
        print(f"  {kind}  {name:<16} {n_params:>11,} params  ->  {path}")

    print()
    print("Serve one:")
    print(f"  MODEL_CHECKPOINT={out_dir}/{PREFIX}attention.pt \\")
    print("    uvicorn backend.main:app --port 8000")
    print()
    print("The fusion checkpoints (feature_level, decision_level, attention) are the")
    print("ones that respond to webcam landmarks. The unimodal ones ignore video.")


if __name__ == "__main__":
    main()
