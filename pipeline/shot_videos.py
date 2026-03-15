"""Shot video generation node."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pipeline.io import dump_model, read_json, write_json
from pipeline.runtime import VideoModelConfig, build_video_client
from schemas.video_jobs import VideoJobsManifest
from schemas.shot_videos_manifest import ShotVideosManifest


DEFAULT_RESOLUTION = "720p"


@dataclass(frozen=True, slots=True)
class ShotVideoArtifacts:
    run_dir: Path
    output_dir: Path
    request_dir: Path
    response_dir: Path
    video_dir: Path


def resolve_run_dir(video_jobs_path: Path) -> Path:
    if video_jobs_path.name != "video_jobs.json":
        raise ValueError(f"Expected a video_jobs.json file: {video_jobs_path}")
    if video_jobs_path.parent.name != "08_video_jobs":
        raise ValueError(f"Expected video_jobs.json under a 08_video_jobs directory: {video_jobs_path}")
    return video_jobs_path.parent.parent


def build_shot_video_artifacts(run_dir: Path) -> ShotVideoArtifacts:
    output_dir = run_dir / "09_shot_videos"
    request_dir = output_dir / "requests"
    response_dir = output_dir / "responses"
    video_dir = output_dir / "videos"
    for path in (output_dir, request_dir, response_dir, video_dir):
        path.mkdir(parents=True, exist_ok=True)
    return ShotVideoArtifacts(
        run_dir=run_dir,
        output_dir=output_dir,
        request_dir=request_dir,
        response_dir=response_dir,
        video_dir=video_dir,
    )


def infer_suffix_from_url(url: str, default: str = ".mp4") -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix or default


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "curl",
            "-fsSL",
            "--http1.1",
            "--tlsv1.2",
            "--retry",
            "3",
            "--retry-delay",
            "1",
            "--output",
            str(dest),
            url,
        ],
        check=True,
    )


def parse_selected_shot_ids(selected_shots: str) -> set[str]:
    if not selected_shots.strip():
        return set()
    parts = [
        part.strip()
        for chunk in selected_shots.split(",")
        for part in chunk.split()
        if part.strip()
    ]
    return set(parts)


def build_task_content(prompt: str, first_frame_url: str) -> list[dict[str, object]]:
    return [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": first_frame_url},
            "role": "first_frame",
        },
    ]


def write_manifest_snapshot(
    *,
    artifacts: ShotVideoArtifacts,
    video_jobs: VideoJobsManifest,
    model_name: str,
    resolution: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
    keep_remote_media: bool,
    results_payload: list[dict[str, object]],
) -> None:
    if not results_payload:
        return
    manifest_payload = {
        "schema_version": "1.0",
        "source_run": artifacts.run_dir.name,
        "source_script_name": video_jobs.source_script_name,
        "title": video_jobs.title,
        "video_model": model_name,
        "execution_spec": {
            "resolution": resolution,
            "timeout_seconds": timeout_seconds,
            "poll_interval_seconds": poll_interval_seconds,
            "keep_remote_media": keep_remote_media,
        },
        "results": results_payload,
    }
    manifest = ShotVideosManifest.model_validate(manifest_payload)
    write_json(artifacts.output_dir / "shot_videos_manifest.json", manifest.model_dump(mode="json"))


def generate_shot_videos(
    *,
    video_jobs_path: Path,
    model_config: VideoModelConfig,
    selected_shots: set[str] | None = None,
    resolution: str = DEFAULT_RESOLUTION,
    timeout_seconds: int = 1800,
    poll_interval_seconds: int = 10,
    keep_remote_media: bool = False,
) -> ShotVideoArtifacts:
    video_jobs = VideoJobsManifest.model_validate(read_json(video_jobs_path))
    run_dir = resolve_run_dir(video_jobs_path)
    artifacts = build_shot_video_artifacts(run_dir)
    client = build_video_client(model_config)
    selected = selected_shots or set()
    existing_manifest_path = artifacts.output_dir / "shot_videos_manifest.json"
    existing_results_by_shot: dict[str, dict[str, object]] = {}
    if existing_manifest_path.exists():
        existing_manifest = ShotVideosManifest.model_validate(read_json(existing_manifest_path))
        existing_results_by_shot = {
            item.shot_id: item.model_dump(mode="json") for item in existing_manifest.results
        }

    results_payload: list[dict[str, object]] = []

    for job in video_jobs.jobs:
        request_path = (artifacts.request_dir / f"{job.shot_id}_request.json").resolve()
        created_response_path = (artifacts.response_dir / f"{job.shot_id}_created.json").resolve()
        result_response_path = (artifacts.response_dir / f"{job.shot_id}_result.json").resolve()

        base_result = {
            "shot_id": job.shot_id,
            "order": job.order,
            "segment_ids": job.segment_ids,
            "video_name": job.video_name,
            "task_id": "",
            "request_path": str(request_path),
            "created_response_path": str(created_response_path),
            "result_response_path": str(result_response_path),
            "video_local_path": "",
            "video_url": "",
            "file_url": "",
            "error_message": "",
        }

        if selected and job.shot_id not in selected:
            if job.shot_id in existing_results_by_shot:
                results_payload.append(existing_results_by_shot[job.shot_id])
            else:
                results_payload.append({**base_result, "status": "skipped_not_selected"})
            write_manifest_snapshot(
                artifacts=artifacts,
                video_jobs=video_jobs,
                model_name=model_config.model_name,
                resolution=resolution,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                keep_remote_media=keep_remote_media,
                results_payload=results_payload,
            )
            continue
        if job.status != "ready":
            if job.shot_id in existing_results_by_shot:
                results_payload.append(existing_results_by_shot[job.shot_id])
            else:
                results_payload.append(
                    {
                        **base_result,
                        "status": "skipped_job_not_ready",
                        "error_message": f"video job status is {job.status}",
                    }
                )
            write_manifest_snapshot(
                artifacts=artifacts,
                video_jobs=video_jobs,
                model_name=model_config.model_name,
                resolution=resolution,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                keep_remote_media=keep_remote_media,
                results_payload=results_payload,
            )
            continue

        request_payload = {
            "model": model_config.model_name,
            "content": build_task_content(job.prompt, job.first_frame_url),
            "duration": job.duration_sec,
            "resolution": resolution,
            "ratio": job.aspect_ratio,
            "watermark": job.watermark,
        }
        write_json(request_path, request_payload)

        created = client.content_generation.tasks.create(
            model=model_config.model_name,
            content=request_payload["content"],
            duration=job.duration_sec,
            resolution=resolution,
            ratio=job.aspect_ratio,
            watermark=job.watermark,
            timeout=300.0,
        )
        write_json(created_response_path, dump_model(created))
        task_id = created.id

        deadline = time.time() + timeout_seconds
        latest = None
        status = "timed_out"
        error_message = ""
        while time.time() < deadline:
            latest = client.content_generation.tasks.get(task_id=task_id, timeout=300.0)
            latest_status = getattr(latest, "status", "unknown")
            if latest_status == "succeeded":
                status = "succeeded"
                break
            if latest_status in {"failed", "cancelled"}:
                status = "failed"
                error = getattr(latest, "error", None)
                error_message = str(dump_model(error)) if error else f"video task ended with status={latest_status}"
                break
            time.sleep(poll_interval_seconds)

        if latest is None:
            raise RuntimeError(f"Video task polling did not start for {job.shot_id}")

        write_json(result_response_path, dump_model(latest))

        content = getattr(latest, "content", None)
        video_url = getattr(content, "video_url", "") if content else ""
        file_url = getattr(content, "file_url", "") if content else ""
        target_url = video_url or file_url
        video_local_path = ""

        if status == "succeeded" and target_url and not keep_remote_media:
            video_output_path = (artifacts.video_dir / f"{job.shot_id}{infer_suffix_from_url(target_url)}").resolve()
            download_file(target_url, video_output_path)
            video_local_path = str(video_output_path)
        elif status == "timed_out":
            error_message = f"video task did not finish within {timeout_seconds}s"

        results_payload.append(
            {
                **base_result,
                "status": status,
                "task_id": task_id,
                "video_local_path": video_local_path,
                "video_url": video_url or "",
                "file_url": file_url or "",
                "error_message": error_message,
            }
        )
        write_manifest_snapshot(
            artifacts=artifacts,
            video_jobs=video_jobs,
            model_name=model_config.model_name,
            resolution=resolution,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            keep_remote_media=keep_remote_media,
            results_payload=results_payload,
        )

    return artifacts
