#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.asset_extraction import extract_asset_registry
from pipeline.runtime import load_text_model_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run script preprocessing and asset extraction for the current project."
    )
    parser.add_argument(
        "--script",
        default="01-陨落的天才.txt",
        help="Path to the source script file.",
    )
    parser.add_argument(
        "--config",
        default="agentkit.local.yaml",
        help="Path to the local AgentKit config file.",
    )
    parser.add_argument(
        "--output-root",
        default="runs",
        help="Directory for generated run artifacts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare inputs and validate config without calling the model.",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Reuse an existing run directory instead of creating a new runN directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_path = Path(args.script).resolve()
    config_path = Path(args.config).resolve()
    output_root = Path(args.output_root).resolve()
    run_dir = Path(args.run_dir).resolve() if args.run_dir else None

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    model_config = load_text_model_config(config_path)
    artifacts = extract_asset_registry(
        script_path=script_path,
        model_config=model_config,
        output_root=output_root,
        run_dir=run_dir,
        dry_run=args.dry_run,
    )

    print(f"Run directory: {artifacts.run_dir}")
    print(f"Input artifacts: {artifacts.input_dir}")
    print(f"Asset artifacts: {artifacts.asset_dir}")
    if args.dry_run:
        print("Dry run completed.")
    else:
        print(f"Asset registry: {artifacts.asset_dir / 'asset_registry.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
