#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.workflow_service import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_ENV_PATH,
    DEFAULT_OUTPUT_ROOT,
    PROJECT_ROOT,
    WorkflowService,
)
from pipeline.final_video import (
    DEFAULT_BLACKOUT_LEADING_SECONDS,
    DEFAULT_TRIM_LEADING_SECONDS,
)
from pipeline.intent_to_script import AUTO_INPUT_MODE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full script-to-video experiment end to end and auto-approve "
            "the current review checkpoints (`upstream`, `asset_images`, `storyboard`)."
        )
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
    source_group.add_argument(
        "--run-dir",
        help="Resume an existing run directory and continue it to final_video with auto approvals.",
    )
    parser.add_argument(
        "--input-mode",
        choices=("auto", "keywords", "brief", "script"),
        default=AUTO_INPUT_MODE,
        help="How to interpret the source input. Defaults to auto detection.",
    )
    parser.add_argument(
        "--source-name",
        default="",
        help="Optional logical source script name. Defaults to the input file stem or `intent_input`.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the local AgentKit config file.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Optional .env file to load before board publishing. Default: ai_studio_flow/.env",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory for generated run artifacts when starting a new workflow.",
    )
    parser.add_argument(
        "--publish-strategy",
        choices=("auto", "tos", "jsdelivr"),
        default="auto",
        help="How to publish shot reference boards. `auto` tries TOS first, then GitHub + jsDelivr.",
    )
    parser.add_argument(
        "--target-repo-root",
        default=str(PROJECT_ROOT),
        help="Local checkout root for jsDelivr publishing. Defaults to the current project root.",
    )
    parser.add_argument(
        "--resolution",
        default="720p",
        help="Video resolution for shot generation. Default: 720p",
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
        help="Do not download remote video files locally in the shot-video stage.",
    )
    parser.add_argument(
        "--trim-leading-seconds",
        type=float,
        default=DEFAULT_TRIM_LEADING_SECONDS,
        help=f"Seconds to trim from the start of every shot before concat. Default: {DEFAULT_TRIM_LEADING_SECONDS}",
    )
    parser.add_argument(
        "--blackout-leading-seconds",
        type=float,
        default=DEFAULT_BLACKOUT_LEADING_SECONDS,
        help=(
            "Seconds to force to pure black at the start of every trimmed shot before concat. "
            f"Default: {DEFAULT_BLACKOUT_LEADING_SECONDS}"
        ),
    )
    parser.add_argument(
        "--reviewer",
        default="auto-runner",
        help="Reviewer name recorded when auto-approving checkpoints. Default: auto-runner",
    )
    parser.add_argument(
        "--review-notes",
        default="auto-approved for full experiment run",
        help="Review note recorded when auto-approving checkpoints.",
    )
    return parser.parse_args()


def build_service(args: argparse.Namespace) -> WorkflowService:
    return WorkflowService(
        config_path=Path(args.config).resolve(),
        output_root=Path(args.output_root).resolve(),
        target_repo_root=Path(args.target_repo_root).resolve(),
        env_file=Path(args.env_file).resolve() if args.env_file else None,
    )


def build_workflow_kwargs(args: argparse.Namespace) -> dict[str, object]:
    return {
        "publish_strategy": args.publish_strategy,
        "resolution": args.resolution,
        "timeout_seconds": args.timeout_seconds,
        "poll_interval_seconds": args.poll_interval_seconds,
        "keep_remote_media": args.keep_remote_media,
        "trim_leading_seconds": args.trim_leading_seconds,
        "blackout_leading_seconds": args.blackout_leading_seconds,
    }


def start_or_continue(service: WorkflowService, args: argparse.Namespace, workflow_kwargs: dict[str, object]) -> dict[str, object]:
    if args.run_dir:
        return service.run_mainline(
            run_dir=args.run_dir,
            source_script_name=args.source_name,
            **workflow_kwargs,
        )
    if args.text:
        return service.run_mainline(
            source_text=args.text,
            source_script_name=args.source_name,
            input_mode=args.input_mode,
            **workflow_kwargs,
        )
    return service.run_mainline(
        source_path=args.input,
        source_script_name=args.source_name,
        input_mode=args.input_mode,
        **workflow_kwargs,
    )


def continue_from_run(service: WorkflowService, run_dir: str, source_name: str, workflow_kwargs: dict[str, object]) -> dict[str, object]:
    return service.run_mainline(
        run_dir=run_dir,
        source_script_name=source_name,
        **workflow_kwargs,
    )


def main() -> int:
    args = parse_args()
    service = build_service(args)
    workflow_kwargs = build_workflow_kwargs(args)

    result = start_or_continue(service, args, workflow_kwargs)
    auto_approved_stages: list[str] = []

    while result.get("status") == "awaiting_approval":
        run_dir = str(result["run_dir"])
        review_stage = str(result.get("review_stage", "")).strip()
        source_name = str(result.get("source_script_name", args.source_name)).strip()
        if not review_stage:
            raise RuntimeError(f"Missing review_stage in awaiting_approval result: {result}")

        print(f"[auto-approve] {review_stage} @ {run_dir}")
        service.submit_review(
            run_dir,
            stage=review_stage,  # type: ignore[arg-type]
            status="approved",
            reviewer=args.reviewer,
            notes=args.review_notes,
            metadata={"source": "run_full_experiment.py"},
        )
        auto_approved_stages.append(review_stage)
        result = continue_from_run(service, run_dir, source_name, workflow_kwargs)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("status") != "ok":
        return 1

    artifacts = result.get("artifacts", {})
    final_video_path = artifacts.get("final_video_path", "") if isinstance(artifacts, dict) else ""
    if auto_approved_stages:
        print("auto_approved_reviews:", ", ".join(auto_approved_stages))
    if final_video_path:
        print("final_video:", final_video_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
