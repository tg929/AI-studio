#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.shot_reference_boards import generate_shot_reference_boards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate stitched shot reference boards from a validated storyboard.json file."
    )
    parser.add_argument(
        "--storyboard",
        required=True,
        help="Path to an existing storyboard.json file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    storyboard_path = Path(args.storyboard).resolve()

    if not storyboard_path.exists():
        raise FileNotFoundError(f"Storyboard file not found: {storyboard_path}")

    artifacts = generate_shot_reference_boards(storyboard_path=storyboard_path)
    print(f"Run directory: {artifacts.run_dir}")
    print(f"Shot reference board artifacts: {artifacts.board_dir}")
    print(f"Shot reference manifest: {artifacts.board_dir / 'shot_reference_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
