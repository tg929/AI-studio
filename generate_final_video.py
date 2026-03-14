#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.final_video import generate_final_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Concatenate succeeded shot videos into a final video."
    )
    parser.add_argument(
        "--shot-videos",
        required=True,
        help="Path to an existing shot_videos_manifest.json file.",
    )
    parser.add_argument(
        "--trim-leading-seconds",
        type=float,
        default=1.5,
        help="Seconds to trim from the start of every shot video before concatenation. Default: 1.0",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    shot_videos_manifest_path = Path(args.shot_videos).resolve()
    if not shot_videos_manifest_path.exists():
        raise FileNotFoundError(f"Shot videos manifest not found: {shot_videos_manifest_path}")

    artifacts = generate_final_video(
        shot_videos_manifest_path=shot_videos_manifest_path,
        trim_leading_seconds=args.trim_leading_seconds,
    )
    print(f"Run directory: {artifacts.run_dir}")
    print(f"Final video artifacts: {artifacts.final_dir}")
    print(f"Concat list: {artifacts.concat_list_path}")
    print(f"Final video: {artifacts.final_video_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
