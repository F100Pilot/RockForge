#!/usr/bin/env python3
"""Thin wrapper to run Banquet (query-bandit) inference on one file — EXPERIMENTAL.

Outside the RockForge pipeline: it only assembles and runs the repo's native
`train.py inference_byoq` command (see experiments/banquet/README.md), validating
paths first so mistakes fail fast instead of deep inside the model. Nothing here
is imported by the app or the worker.

Example:
    python experiments/banquet/run_banquet.py \
        --repo ~/src/query-bandit \
        --ckpt ~/models/ev-pre-aug.ckpt \
        --input song.wav \
        --query queries/distorted-electric.wav \
        --out out/guitar.wav
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Banquet query-based separation (experimental).")
    ap.add_argument("--repo", required=True, type=Path, help="path to a cloned query-bandit repo")
    ap.add_argument("--ckpt", required=True, type=Path, help="checkpoint (e.g. ev-pre-aug.ckpt)")
    ap.add_argument("--input", required=True, type=Path, help="input mixture audio (wav)")
    ap.add_argument("--query", required=True, type=Path, help="reference clip of the target class")
    ap.add_argument("--out", required=True, type=Path, help="output stem path (wav)")
    ap.add_argument("--batch-size", type=int, default=12, help="lower it if VRAM is tight")
    ap.add_argument("--cpu", action="store_true", help="force CPU (slow) instead of CUDA")
    args = ap.parse_args()

    train_py = args.repo / "train.py"
    for label, p in [("repo", args.repo), ("checkpoint", args.ckpt),
                     ("input", args.input), ("query", args.query), ("train.py", train_py)]:
        if not p.exists():
            print(f"error: {label} not found: {p}", file=sys.stderr)
            return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "train.py", "inference_byoq",
        f"--ckpt_path={args.ckpt}",
        f"--input_path={args.input}",
        f"--output_path={args.out}",
        f"--query_path={args.query}",
        f"--batch_size={args.batch_size}",
        f"--use_cuda={'false' if args.cpu else 'true'}",
    ]
    # The repo reads config from $CONFIG_ROOT; default it if the caller didn't.
    env = {**os.environ}
    env.setdefault("CONFIG_ROOT", str(args.repo / "config"))
    print("running:", " ".join(cmd), f"(cwd={args.repo})")
    return subprocess.run(cmd, cwd=args.repo, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
