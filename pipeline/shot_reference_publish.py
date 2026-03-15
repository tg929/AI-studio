"""Shot reference board publishing node."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

from pipeline.io import read_json, write_json
from schemas.shot_reference_manifest import ShotReferenceManifest


@dataclass(frozen=True, slots=True)
class ShotReferencePublishArtifacts:
    run_dir: Path
    board_dir: Path
    publish_root_dir: Path
    output_manifest_path: Path
    result_path: Path


def resolve_run_dir(manifest_path: Path) -> Path:
    if manifest_path.name != "shot_reference_manifest.json":
        raise ValueError(f"Expected a shot_reference_manifest.json file: {manifest_path}")
    if manifest_path.parent.name != "07_shot_reference_boards":
        raise ValueError(
            f"Expected shot_reference_manifest.json under a 07_shot_reference_boards directory: {manifest_path}"
        )
    return manifest_path.parent.parent


def normalize_public_base_url(public_base_url: str) -> str:
    stripped = public_base_url.strip().rstrip("/")
    parsed = urlsplit(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"public_base_url must be an absolute http(s) URL: {public_base_url}")
    return stripped


def normalize_url_prefix(url_prefix: str) -> str:
    return "/".join(part for part in url_prefix.strip().split("/") if part)


def build_publish_relative_path(*, source_run: str, filename: str, url_prefix: str) -> Path:
    parts: list[str] = []
    if url_prefix:
        parts.extend(part for part in url_prefix.split("/") if part)
    parts.extend(["runs", source_run, "07_shot_reference_boards", "boards", filename])
    return Path(*parts)


def build_public_url(*, public_base_url: str, relative_path: Path, query: str = "") -> str:
    parsed = urlsplit(public_base_url)
    relative_posix = PurePosixPath(relative_path.as_posix())
    base_path = PurePosixPath(parsed.path or "/")
    full_path = (base_path / relative_posix).as_posix()
    return urlunsplit((parsed.scheme, parsed.netloc, full_path, query, ""))


def publish_shot_reference_boards(
    *,
    manifest_path: Path,
    public_base_url: str,
    publish_root_dir: Path,
    url_prefix: str = "",
    output_manifest_path: Path | None = None,
) -> ShotReferencePublishArtifacts:
    manifest = ShotReferenceManifest.model_validate(read_json(manifest_path))
    run_dir = resolve_run_dir(manifest_path)
    board_dir = manifest_path.parent
    publish_root = publish_root_dir.resolve()
    publish_root.mkdir(parents=True, exist_ok=True)

    normalized_base_url = normalize_public_base_url(public_base_url)
    normalized_prefix = normalize_url_prefix(url_prefix)

    boards_payload: list[dict[str, object]] = []
    published_entries: list[dict[str, str]] = []

    for board in manifest.boards:
        source_path = Path(board.board_local_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Shot board image not found: {source_path}")

        relative_publish_path = build_publish_relative_path(
            source_run=manifest.source_run,
            filename=source_path.name,
            url_prefix=normalized_prefix,
        )
        published_local_path = publish_root / relative_publish_path
        published_local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, published_local_path)
        cache_query = f"v={source_path.stat().st_mtime_ns}"

        board_payload = board.model_dump(mode="json")
        board_payload["board_public_url"] = build_public_url(
            public_base_url=normalized_base_url,
            relative_path=relative_publish_path,
            query=cache_query,
        )
        boards_payload.append(board_payload)
        published_entries.append(
            {
                "shot_id": board.shot_id,
                "source_path": str(source_path),
                "published_local_path": str(published_local_path),
                "public_url": board_payload["board_public_url"],
            }
        )

    updated_manifest = ShotReferenceManifest.model_validate(
        {
            **manifest.model_dump(mode="json"),
            "boards": boards_payload,
        }
    )
    final_manifest_path = (output_manifest_path or manifest_path).resolve()
    final_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(final_manifest_path, updated_manifest.model_dump(mode="json"))

    result_path = board_dir / "board_publish_result.json"
    write_json(
        result_path,
        {
            "source_run": manifest.source_run,
            "source_script_name": manifest.source_script_name,
            "public_base_url": normalized_base_url,
            "publish_root_dir": str(publish_root),
            "url_prefix": normalized_prefix,
            "output_manifest_path": str(final_manifest_path),
            "published_boards": published_entries,
        },
    )

    return ShotReferencePublishArtifacts(
        run_dir=run_dir,
        board_dir=board_dir,
        publish_root_dir=publish_root,
        output_manifest_path=final_manifest_path,
        result_path=result_path,
    )
