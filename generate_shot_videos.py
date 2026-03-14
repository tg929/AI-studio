#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.runtime import load_video_model_config
from pipeline.shot_videos import generate_shot_videos, parse_selected_shot_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate shot videos from a validated video_jobs.json file."
    )
    parser.add_argument(
        "--jobs",
        required=True,
        help="Path to an existing video_jobs.json file.",
    )
    parser.add_argument(
        "--config",
        default="agentkit.local.yaml",
        help="Path to the local AgentKit config file.",
    )
    parser.add_argument(
        "--shots",
        default="",
        help="Optional comma-separated shot IDs to run, for example: shot_001,shot_002",
    )
    parser.add_argument(
        "--resolution",
        default="720p",
        help="Video resolution to request. Default: 720p",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help="Max seconds to wait for each shot video task. Default: 1800",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=10,
        help="Seconds between video task polling. Default: 10",
    )
    parser.add_argument(
        "--keep-remote-media",
        action="store_true",
        help="Do not download remote video files locally.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    video_jobs_path = Path(args.jobs).resolve()
    config_path = Path(args.config).resolve()

    if not video_jobs_path.exists():
        raise FileNotFoundError(f"Video jobs file not found: {video_jobs_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    model_config = load_video_model_config(config_path)
    artifacts = generate_shot_videos(
        video_jobs_path=video_jobs_path,
        model_config=model_config,
        selected_shots=parse_selected_shot_ids(args.shots),
        resolution=args.resolution,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        keep_remote_media=args.keep_remote_media,
    )
    print(f"Run directory: {artifacts.run_dir}")
    print(f"Shot video artifacts: {artifacts.output_dir}")
    print(f"Shot videos manifest: {artifacts.output_dir / 'shot_videos_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
