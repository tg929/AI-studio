#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.intent_to_script import AUTO_INPUT_MODE, generate_script_from_intent
from pipeline.runtime import load_text_model_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the route-guided upstream workflow from keywords, brief, or script input."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--input",
        help="Path to a text file containing keywords, a brief, or a full script.",
    )
    source_group.add_argument(
        "--text",
        help="Inline keywords, brief, or full script text.",
    )
    parser.add_argument(
        "--input-mode",
        default=AUTO_INPUT_MODE,
        choices=[AUTO_INPUT_MODE, "keywords", "brief", "script"],
        help="How to interpret the source input. Defaults to auto detection.",
    )
    parser.add_argument(
        "--source-name",
        default="",
        help="Optional logical source script name. Defaults to the input file stem or `intent_input`.",
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
        "--run-dir",
        default="",
        help="Reuse an existing run directory instead of creating a new runN directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare inputs and the first-stage request without calling the model.",
    )
    parser.add_argument(
        "--extract-assets",
        action="store_true",
        help="After script generation, immediately run asset extraction into the same run directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    output_root = Path(args.output_root).resolve()
    run_dir = Path(args.run_dir).resolve() if args.run_dir else None

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    input_path: Path | None = None
    if args.input:
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        source_text = input_path.read_text(encoding="utf-8")
        default_source_name = input_path.stem
    else:
        source_text = args.text
        default_source_name = "intent_input"

    source_script_name = args.source_name.strip() or default_source_name
    model_config = load_text_model_config(config_path)
    artifacts = generate_script_from_intent(
        source_text=source_text,
        source_script_name=source_script_name,
        model_config=model_config,
        output_root=output_root,
        run_dir=run_dir,
        source_path=input_path,
        input_mode=args.input_mode,
        dry_run=args.dry_run,
        extract_assets=args.extract_assets and not args.dry_run,
    )

    print(f"Run directory: {artifacts.run_dir}")
    print(f"Source artifacts: {artifacts.source_dir}")
    print(f"Input artifacts: {artifacts.input_dir}")
    if artifacts.asset_dir is not None:
        print(f"Asset artifacts: {artifacts.asset_dir}")
    print(f"Intake router: {artifacts.source_dir / 'intake_router.json'}")
    if args.dry_run:
        print("Dry run completed.")
    else:
        generated_script_path = artifacts.source_dir / "generated_script.txt"
        script_quality_path = artifacts.source_dir / "script_quality_report.json"
        asset_readiness_path = artifacts.source_dir / "asset_readiness_report.json"
        if generated_script_path.exists():
            print(f"Generated script: {generated_script_path}")
        else:
            print("Generated script: not produced")
        if script_quality_path.exists():
            print(f"Script quality report: {script_quality_path}")
        if asset_readiness_path.exists():
            print(f"Asset readiness report: {asset_readiness_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
