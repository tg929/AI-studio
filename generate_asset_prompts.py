#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.asset_prompts import generate_asset_prompts
from pipeline.runtime import load_text_model_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate asset_prompts.json from a validated style_bible.json file."
    )
    parser.add_argument(
        "--style-bible",
        required=True,
        help="Path to an existing style_bible.json file.",
    )
    parser.add_argument(
        "--config",
        default="agentkit.local.yaml",
        help="Path to the local AgentKit config file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare inputs and validate config without calling the model.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    style_bible_path = Path(args.style_bible).resolve()
    config_path = Path(args.config).resolve()

    if not style_bible_path.exists():
        raise FileNotFoundError(f"Style bible file not found: {style_bible_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    model_config = load_text_model_config(config_path)
    artifacts = generate_asset_prompts(
        style_bible_path=style_bible_path,
        model_config=model_config,
        dry_run=args.dry_run,
    )

    print(f"Run directory: {artifacts.run_dir}")
    print(f"Asset prompt artifacts: {artifacts.prompt_dir}")
    if args.dry_run:
        print("Dry run completed.")
    else:
        print(f"Asset prompts: {artifacts.prompt_dir / 'asset_prompts.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
