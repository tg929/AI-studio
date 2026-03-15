"""Final video concatenation node."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline.io import read_json, write_json
from schemas.final_video_manifest import FinalVideoManifest
from schemas.shot_videos_manifest import ShotVideosManifest

DEFAULT_TRIM_LEADING_SECONDS = 1.0
DEFAULT_BLACKOUT_LEADING_SECONDS = 0.4


@dataclass(frozen=True, slots=True)
class FinalVideoArtifacts:
    run_dir: Path
    final_dir: Path
    trimmed_dir: Path
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
    trimmed_dir = final_dir / "trimmed"
    final_dir.mkdir(parents=True, exist_ok=True)
    trimmed_dir.mkdir(parents=True, exist_ok=True)
    return FinalVideoArtifacts(
        run_dir=run_dir,
        final_dir=final_dir,
        trimmed_dir=trimmed_dir,
        concat_list_path=(final_dir / "concat_inputs.txt").resolve(),
        final_video_path=(final_dir / "final_video.mp4").resolve(),
    )


def shell_quote_for_ffmpeg(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def build_leading_blackout_filter(blackout_leading_seconds: float) -> str | None:
    if blackout_leading_seconds <= 0:
        return None
    return (
        "drawbox="
        "x=0:y=0:w=iw:h=ih:"
        "color=black:t=fill:"
        f"enable=lt(t\\,{blackout_leading_seconds:.3f})"
    )


def trim_video_clip(
    *,
    source_path: Path,
    output_path: Path,
    trim_leading_seconds: float,
    blackout_leading_seconds: float,
) -> None:
    command = ["ffmpeg", "-y"]
    if trim_leading_seconds > 0:
        command.extend(["-ss", f"{trim_leading_seconds:.3f}"])
    command.extend(["-i", str(source_path)])

    video_filter = build_leading_blackout_filter(blackout_leading_seconds)
    if video_filter:
        command.extend(["-vf", video_filter])

    command.extend(
        [
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def generate_final_video(
    *,
    shot_videos_manifest_path: Path,
    trim_leading_seconds: float = DEFAULT_TRIM_LEADING_SECONDS,
    blackout_leading_seconds: float = DEFAULT_BLACKOUT_LEADING_SECONDS,
) -> FinalVideoArtifacts:
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
        source_video_path = Path(item.video_local_path)
        if not source_video_path.exists():
            raise FileNotFoundError(f"Shot video file not found: {source_video_path}")
        trimmed_video_path = (artifacts.trimmed_dir / f"{item.shot_id}.mp4").resolve()
        trim_video_clip(
            source_path=source_video_path.resolve(),
            output_path=trimmed_video_path,
            trim_leading_seconds=trim_leading_seconds,
            blackout_leading_seconds=blackout_leading_seconds,
        )
        concat_lines.append(f"file '{shell_quote_for_ffmpeg(trimmed_video_path)}'")
        inputs_payload.append(
            {
                "shot_id": item.shot_id,
                "order": item.order,
                "source_video_path": str(source_video_path.resolve()),
                "trimmed_video_path": str(trimmed_video_path),
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
                "trim_leading_seconds": trim_leading_seconds,
                "blackout_leading_seconds": blackout_leading_seconds,
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
