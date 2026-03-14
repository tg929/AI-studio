#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.runtime import load_video_model_config
from pipeline.video_jobs import generate_video_jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble video_jobs.json from a validated storyboard.json file."
    )
    parser.add_argument(
        "--storyboard",
        required=True,
        help="Path to an existing storyboard.json file.",
    )
    parser.add_argument(
        "--config",
        default="agentkit.local.yaml",
        help="Path to the local AgentKit config file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    storyboard_path = Path(args.storyboard).resolve()
    config_path = Path(args.config).resolve()

    if not storyboard_path.exists():
        raise FileNotFoundError(f"Storyboard file not found: {storyboard_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    model_config = load_video_model_config(config_path)
    artifacts = generate_video_jobs(storyboard_path=storyboard_path, model_config=model_config)
    print(f"Run directory: {artifacts.run_dir}")
    print(f"Video job artifacts: {artifacts.jobs_dir}")
    print(f"Video jobs: {artifacts.jobs_dir / 'video_jobs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
