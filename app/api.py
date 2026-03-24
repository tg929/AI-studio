from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

from .review_state import ReviewStage
from .task_runner import WorkflowTaskRunner
from .workflow_service import (
    DEFAULT_BLACKOUT_LEADING_SECONDS,
    DEFAULT_TRIM_LEADING_SECONDS,
    DEFAULT_OUTPUT_ROOT,
    WorkflowService,
    WorkflowStage,
)


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".txt", ".md", ".log", ".jsonl"}:
        return "text"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if suffix in {".mp4", ".mov", ".webm"}:
        return "video"
    return "file"


def _preview_url(run_dir: Path, artifact_path: Path) -> str:
    try:
        relative = artifact_path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return ""
    return f"/media/{run_dir.name}/{relative.as_posix()}"


class CreateRunRequest(BaseModel):
    source_text: str = ""
    source_path: str = ""
    source_script_name: str = ""
    input_mode: Literal["auto", "keywords", "brief", "script"] = "auto"
    run_dir: str = ""
    execution_mode: Literal["upstream_only", "mainline"] = "mainline"
    parallel_planning: bool = True

    @model_validator(mode="after")
    def validate_source(self) -> "CreateRunRequest":
        if self.run_dir.strip():
            return self
        if self.source_text.strip() or self.source_path.strip():
            return self
        raise ValueError("Provide `run_dir`, `source_text`, or `source_path`.")


class ContinueRunRequest(BaseModel):
    parallel_planning: bool = False


class RerunStageRequest(BaseModel):
    force: bool = True
    selected_shots: list[str] = Field(default_factory=list)
    resolution: str = "720p"
    timeout_seconds: int = 1800
    poll_interval_seconds: int = 10
    keep_remote_media: bool = False
    trim_leading_seconds: float = DEFAULT_TRIM_LEADING_SECONDS
    blackout_leading_seconds: float = DEFAULT_BLACKOUT_LEADING_SECONDS


class ReviewUpdateRequest(BaseModel):
    status: Literal["pending", "approved", "rejected"]
    reviewer: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def create_api_app(
    *,
    service: WorkflowService | None = None,
    task_runner: WorkflowTaskRunner | None = None,
) -> FastAPI:
    workflow_service = service or WorkflowService(output_root=DEFAULT_OUTPUT_ROOT)
    runner = task_runner or WorkflowTaskRunner(workflow_service)

    app = FastAPI(title="AI Studio Operator API", version="0.1.0")
    app.state.workflow_service = workflow_service
    app.state.task_runner = runner
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/runs")
    def list_runs(limit: int = 50) -> dict[str, Any]:
        return {"runs": workflow_service.list_runs(limit=limit)}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return workflow_service.inspect_run(run_dir)

    @app.get("/api/runs/{run_id}/artifacts")
    def get_run_artifacts(run_id: str) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        snapshot = workflow_service.artifact_snapshot(run_dir)
        artifacts = []
        for key, raw_path in snapshot.items():
            path = Path(raw_path) if raw_path else None
            exists = bool(path and path.exists())
            artifacts.append(
                {
                    "key": key,
                    "path": raw_path,
                    "exists": exists,
                    "kind": _artifact_kind(path) if exists and path is not None else "missing",
                    "preview_url": _preview_url(run_dir, path) if exists and path is not None else "",
                }
            )
        return {"run_id": run_id, "artifacts": artifacts}

    @app.get("/api/runs/{run_id}/events")
    def get_run_events(run_id: str, limit: int = 200) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return {"run_id": run_id, "events": workflow_service.read_events(run_dir, limit=limit)}

    @app.get("/api/runs/{run_id}/videos")
    def get_run_videos(run_id: str) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return workflow_service.build_video_payload(run_dir)

    @app.get("/api/runs/{run_id}/tasks")
    def get_run_tasks(run_id: str, limit: int = 20) -> dict[str, Any]:
        return {"run_id": run_id, "tasks": runner.list_tasks(run_id=run_id, limit=limit)}

    @app.get("/api/runs/{run_id}/reviews")
    def get_run_reviews(run_id: str) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return workflow_service.list_reviews(run_dir)

    @app.get("/api/runs/{run_id}/reviews/{stage}")
    def get_stage_review(run_id: str, stage: ReviewStage) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return workflow_service.get_review(run_dir, stage)

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = runner.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return task

    @app.post("/api/runs")
    def create_run(request: CreateRunRequest) -> dict[str, Any]:
        try:
            task = runner.launch_run(
                source_text=request.source_text,
                source_path=request.source_path,
                source_script_name=request.source_script_name,
                input_mode=request.input_mode,
                run_dir=request.run_dir,
                execution_mode=request.execution_mode,
                parallel_planning=request.parallel_planning,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return task

    @app.post("/api/runs/{run_id}/continue")
    def continue_run(run_id: str, request: ContinueRunRequest) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        try:
            task = runner.launch_continue_run(run_dir=str(run_dir), parallel_planning=request.parallel_planning)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return task

    @app.post("/api/runs/{run_id}/rerun-stage/{stage}")
    def rerun_stage(run_id: str, stage: WorkflowStage, request: RerunStageRequest) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        try:
            task = runner.launch_stage(
                run_dir=str(run_dir),
                stage=stage,
                force=request.force,
                selected_shots=set(request.selected_shots),
                resolution=request.resolution,
                timeout_seconds=request.timeout_seconds,
                poll_interval_seconds=request.poll_interval_seconds,
                keep_remote_media=request.keep_remote_media,
                trim_leading_seconds=request.trim_leading_seconds,
                blackout_leading_seconds=request.blackout_leading_seconds,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return task

    @app.post("/api/runs/{run_id}/reviews/{stage}")
    def submit_stage_review(run_id: str, stage: ReviewStage, request: ReviewUpdateRequest) -> dict[str, Any]:
        run_dir = workflow_service.output_root / run_id
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        try:
            return workflow_service.submit_review(
                run_dir,
                stage=stage,
                status=request.status,
                reviewer=request.reviewer,
                notes=request.notes,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/media/{run_id}/{relative_path:path}")
    def read_run_media(run_id: str, relative_path: str) -> FileResponse:
        run_dir = (workflow_service.output_root / run_id).resolve()
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        target_path = (run_dir / relative_path).resolve()
        try:
            target_path.relative_to(run_dir)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid media path.") from exc
        if not target_path.exists() or not target_path.is_file():
            raise HTTPException(status_code=404, detail=f"Artifact not found: {relative_path}")
        return FileResponse(target_path)

    return app
