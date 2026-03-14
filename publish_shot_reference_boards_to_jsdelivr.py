#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from pipeline.shot_reference_publish import publish_shot_reference_boards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish stitched shot reference boards into a GitHub repo checkout and generate jsDelivr URLs."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to an existing shot_reference_manifest.json file.",
    )
    parser.add_argument(
        "--target-repo-root",
        required=True,
        help="Local checkout root of the public GitHub repo that will serve the published files.",
    )
    parser.add_argument(
        "--repo-slug",
        default="",
        help="Optional GitHub repo slug like owner/name. Defaults to inferring from target repo origin.",
    )
    parser.add_argument(
        "--ref",
        default="",
        help="Optional Git ref for jsDelivr URLs. Defaults to inferring the current branch in the target repo.",
    )
    parser.add_argument(
        "--url-prefix",
        default="static",
        help="Path prefix inside the target repo for published board files. Default: static",
    )
    parser.add_argument(
        "--output-manifest",
        default="",
        help="Optional output path for the updated manifest. Defaults to overwriting the input manifest.",
    )
    return parser.parse_args()


def run_git(args: list[str], repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def infer_repo_slug(repo_root: Path) -> str:
    remote_url = run_git(["config", "--get", "remote.origin.url"], repo_root)
    if not remote_url:
        raise ValueError(f"Cannot infer GitHub repo slug from target repo: {repo_root}")

    normalized = remote_url.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    if normalized.startswith("git@github.com:"):
        path = normalized.split("git@github.com:", 1)[1]
    elif normalized.startswith("https://github.com/"):
        path = normalized.split("https://github.com/", 1)[1]
    else:
        raise ValueError(f"Unsupported GitHub remote URL format: {remote_url}")

    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        raise ValueError(f"Cannot parse owner/repo from remote URL: {remote_url}")
    return f"{parts[0]}/{parts[1]}"


def infer_ref(repo_root: Path) -> str:
    branch = run_git(["branch", "--show-current"], repo_root)
    if branch:
        return branch
    raise ValueError(f"Cannot infer current branch for target repo: {repo_root}")


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    target_repo_root = Path(args.target_repo_root).resolve()
    output_manifest_path = Path(args.output_manifest).resolve() if args.output_manifest else None

    if not manifest_path.exists():
        raise FileNotFoundError(f"Shot reference manifest not found: {manifest_path}")
    if not target_repo_root.exists():
        raise FileNotFoundError(f"Target repo root not found: {target_repo_root}")
    if not (target_repo_root / ".git").exists():
        raise ValueError(f"Target repo root is not a git repository: {target_repo_root}")

    repo_slug = args.repo_slug or infer_repo_slug(target_repo_root)
    ref = args.ref or infer_ref(target_repo_root)
    public_base_url = f"https://cdn.jsdelivr.net/gh/{repo_slug}@{ref}"

    artifacts = publish_shot_reference_boards(
        manifest_path=manifest_path,
        public_base_url=public_base_url,
        publish_root_dir=target_repo_root,
        url_prefix=args.url_prefix,
        output_manifest_path=output_manifest_path,
    )
    print(f"Run directory: {artifacts.run_dir}")
    print(f"Target repo root: {target_repo_root}")
    print(f"jsDelivr base URL: {public_base_url}")
    print(f"Updated manifest: {artifacts.output_manifest_path}")
    print(f"Publish result: {artifacts.result_path}")
    print("Next step: commit and push the copied files in the target repo so jsDelivr can serve them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
