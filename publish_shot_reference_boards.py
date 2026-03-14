#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.shot_reference_publish import publish_shot_reference_boards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish stitched shot reference boards to a static directory and write board_public_url values."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to an existing shot_reference_manifest.json file.",
    )
    parser.add_argument(
        "--public-base-url",
        required=True,
        help="Absolute http(s) base URL for the published board files.",
    )
    parser.add_argument(
        "--publish-root-dir",
        required=True,
        help="Static-root directory where published board files should be copied.",
    )
    parser.add_argument(
        "--url-prefix",
        default="",
        help="Optional path prefix to add between the public base URL and the published board files.",
    )
    parser.add_argument(
        "--output-manifest",
        default="",
        help="Optional output path for the updated manifest. Defaults to overwriting the input manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    publish_root_dir = Path(args.publish_root_dir).resolve()
    output_manifest_path = Path(args.output_manifest).resolve() if args.output_manifest else None

    if not manifest_path.exists():
        raise FileNotFoundError(f"Shot reference manifest not found: {manifest_path}")

    artifacts = publish_shot_reference_boards(
        manifest_path=manifest_path,
        public_base_url=args.public_base_url,
        publish_root_dir=publish_root_dir,
        url_prefix=args.url_prefix,
        output_manifest_path=output_manifest_path,
    )
    print(f"Run directory: {artifacts.run_dir}")
    print(f"Published root: {artifacts.publish_root_dir}")
    print(f"Updated manifest: {artifacts.output_manifest_path}")
    print(f"Publish result: {artifacts.result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
