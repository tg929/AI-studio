"""Final video concatenation node."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline.io import read_json, write_json
from schemas.final_video_manifest import FinalVideoManifest
from schemas.shot_videos_manifest import ShotVideosManifest


@dataclass(frozen=True, slots=True)
class FinalVideoArtifacts:
    run_dir: Path
    final_dir: Path
    concat_list_path: Path
    final_video_path: Path


def resolve_run_dir(shot_videos_manifest_path: Path) -> Path:
    if shot_videos_manifest_path.name != "shot_videos_manifest.json":
        raise ValueError(f"Expected a shot_videos_manifest.json file: {shot_videos_manifest_path}")
    if shot_videos_manifest_path.parent.name != "09_shot_videos":
        raise ValueError(
            f"Expected shot_videos_manifest.json under a 09_shot_videos directory: {shot_videos_manifest_path}"
        )
    return shot_videos_manifest_path.parent.parent


def build_final_video_artifacts(run_dir: Path) -> FinalVideoArtifacts:
    final_dir = run_dir / "10_final"
    final_dir.mkdir(parents=True, exist_ok=True)
    return FinalVideoArtifacts(
        run_dir=run_dir,
        final_dir=final_dir,
        concat_list_path=(final_dir / "concat_inputs.txt").resolve(),
        final_video_path=(final_dir / "final_video.mp4").resolve(),
    )


def shell_quote_for_ffmpeg(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def generate_final_video(*, shot_videos_manifest_path: Path) -> FinalVideoArtifacts:
    shot_videos = ShotVideosManifest.model_validate(read_json(shot_videos_manifest_path))
    run_dir = resolve_run_dir(shot_videos_manifest_path)
    artifacts = build_final_video_artifacts(run_dir)

    succeeded_results = [item for item in shot_videos.results if item.status == "succeeded"]
    if len(succeeded_results) != len(shot_videos.results):
        failed = [item.shot_id for item in shot_videos.results if item.status != "succeeded"]
        raise ValueError(f"Cannot concatenate final video because some shots did not succeed: {failed}")

    concat_lines: list[str] = []
    inputs_payload: list[dict[str, object]] = []
    for item in succeeded_results:
        video_path = Path(item.video_local_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Shot video file not found: {video_path}")
        concat_lines.append(f"file '{shell_quote_for_ffmpeg(video_path.resolve())}'")
        inputs_payload.append(
            {
                "shot_id": item.shot_id,
                "order": item.order,
                "video_path": str(video_path.resolve()),
            }
        )

    artifacts.concat_list_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(artifacts.concat_list_path),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(artifacts.final_video_path),
        ],
        check=True,
    )

    manifest = FinalVideoManifest.model_validate(
        {
            "schema_version": "1.0",
            "source_run": run_dir.name,
            "source_script_name": shot_videos.source_script_name,
            "title": shot_videos.title,
            "concat_spec": {
                "concat_mode": "ffmpeg_concat_demuxer_reencode",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "pixel_format": "yuv420p",
                "faststart": True,
            },
            "concat_list_path": str(artifacts.concat_list_path),
            "final_video_path": str(artifacts.final_video_path),
            "inputs": inputs_payload,
        }
    )
    write_json(artifacts.final_dir / "final_video_manifest.json", manifest.model_dump(mode="json"))

    return artifacts
