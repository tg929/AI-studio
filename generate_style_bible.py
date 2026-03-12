#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.runtime import load_text_model_config
from pipeline.style_bible import generate_style_bible


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate style_bible.json from a validated asset_registry.json file."
    )
    parser.add_argument(
        "--asset-registry",
        required=True,
        help="Path to an existing asset_registry.json file.",
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
    asset_registry_path = Path(args.asset_registry).resolve()
    config_path = Path(args.config).resolve()

    if not asset_registry_path.exists():
        raise FileNotFoundError(f"Asset registry file not found: {asset_registry_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    model_config = load_text_model_config(config_path)
    artifacts = generate_style_bible(
        asset_registry_path=asset_registry_path,
        model_config=model_config,
        dry_run=args.dry_run,
    )

    print(f"Run directory: {artifacts.run_dir}")
    print(f"Style artifacts: {artifacts.style_dir}")
    if args.dry_run:
        print("Dry run completed.")
    else:
        print(f"Style bible: {artifacts.style_dir / 'style_bible.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
