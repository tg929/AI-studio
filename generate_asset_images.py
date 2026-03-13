#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.asset_images import generate_asset_images
from pipeline.runtime import load_image_model_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate labeled asset images from a validated asset_prompts.json file."
    )
    parser.add_argument(
        "--asset-prompts",
        required=True,
        help="Path to an existing asset_prompts.json file.",
    )
    parser.add_argument(
        "--config",
        default="agentkit.local.yaml",
        help="Path to the local AgentKit config file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare jobs and validate config without calling the image model.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asset_prompts_path = Path(args.asset_prompts).resolve()
    config_path = Path(args.config).resolve()

    if not asset_prompts_path.exists():
        raise FileNotFoundError(f"Asset prompts file not found: {asset_prompts_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    model_config = load_image_model_config(config_path)
    artifacts = generate_asset_images(
        asset_prompts_path=asset_prompts_path,
        model_config=model_config,
        dry_run=args.dry_run,
    )

    print(f"Run directory: {artifacts.run_dir}")
    print(f"Asset image artifacts: {artifacts.image_dir}")
    if args.dry_run:
        print("Dry run completed.")
    else:
        print(f"Asset manifest: {artifacts.image_dir / 'asset_images_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
