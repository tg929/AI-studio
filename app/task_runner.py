from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any, Callable, Literal
from uuid import uuid4

from pipeline.intent_to_script import AUTO_INPUT_MODE

from .run_state import append_run_event, utc_now_iso
from .workflow_service import WorkflowService, WorkflowStage


TaskStatus = Literal["queued", "running", "succeeded", "failed", "blocked", "partial", "awaiting_approval"]


@dataclass(slots=True)
class WorkflowTask:
    task_id: str
    action: str
    run_id: str = ""
    run_dir: str = ""
    stage: str = ""
    status: TaskStatus = "queued"
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str = ""
    finished_at: str = ""
    error: str = ""
    progress_message: str = ""
    progress_step: str = ""
    progress_stage: str = ""
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "action": self.action,
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "stage": self.stage,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "progress_message": self.progress_message,
            "progress_step": self.progress_step,
            "progress_stage": self.progress_stage,
            "result": self.result,
        }


class WorkflowTaskRunner:
    def __init__(self, service: WorkflowService):
        self.service = service
        self._lock = threading.RLock()
        self._tasks: dict[str, WorkflowTask] = {}
        self._threads: dict[str, threading.Thread] = {}

    def _build_task(self, *, action: str, run_dir: Path | None = None, stage: str = "") -> WorkflowTask:
        return WorkflowTask(
            task_id=uuid4().hex,
            action=action,
            run_id=run_dir.name if run_dir is not None else "",
            run_dir=str(run_dir.resolve()) if run_dir is not None else "",
            stage=stage,
            progress_message="任务已提交，正在等待后台执行。",
            progress_step="输入接收",
            progress_stage=stage or "upstream",
        )

    def _has_active_task(self, run_id: str) -> bool:
        if not run_id:
            return False
        for task in self._tasks.values():
            if task.run_id == run_id and task.status in {"queued", "running"}:
                return True
        return False

    def _register_task(self, task: WorkflowTask) -> None:
        with self._lock:
            if self._has_active_task(task.run_id):
                raise RuntimeError(f"Run `{task.run_id}` already has an active background task.")
            self._tasks[task.task_id] = task

    @staticmethod
    def _event_run_dir(task: WorkflowTask) -> Path | None:
        if not task.run_dir.strip():
            return None
        resolved = Path(task.run_dir).resolve()
        if not resolved.exists():
            return None
        return resolved

    def _set_task_progress(
        self,
        task: WorkflowTask,
        *,
        message: str = "",
        step: str = "",
        stage: str = "",
        run_dir: str = "",
    ) -> None:
        with self._lock:
            if message:
                task.progress_message = message
            if step:
                task.progress_step = step
            if stage:
                task.progress_stage = stage
                if not task.stage:
                    task.stage = stage
            if run_dir.strip():
                resolved = Path(run_dir).resolve()
                task.run_dir = str(resolved)
                task.run_id = resolved.name

    def _append_task_event(
        self,
        task: WorkflowTask,
        *,
        event_type: str,
        message: str,
        stage: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        run_dir = self._event_run_dir(task)
        if run_dir is None:
            return
        append_run_event(
            run_dir,
            event_type=event_type,
            stage=stage or task.stage,
            message=message,
            data=data,
        )

    def _start_task(self, task: WorkflowTask, fn: Callable[[Callable[[dict[str, Any]], None]], dict[str, Any]]) -> WorkflowTask:
        self._register_task(task)
        self._append_task_event(
            task,
            event_type="task_queued",
            stage=task.stage,
            message=f"Queued background task `{task.action}`.",
            data={"task_id": task.task_id},
        )

        def worker() -> None:
            with self._lock:
                task.status = "running"
                task.started_at = utc_now_iso()
            self._set_task_progress(
                task,
                message="任务已提交，正在创建工作空间。",
                step=task.progress_step or "输入接收",
                stage=task.stage or "upstream",
            )

            def progress_callback(payload: dict[str, Any]) -> None:
                message = str(payload.get("message", "")).strip()
                step = str(payload.get("step", "")).strip()
                stage = str(payload.get("stage", "")).strip()
                run_dir = str(payload.get("run_dir", "")).strip()
                self._set_task_progress(task, message=message, step=step, stage=stage, run_dir=run_dir)

            self._append_task_event(
                task,
                event_type="task_started",
                stage=task.stage,
                message=f"Started background task `{task.action}`.",
                data={"task_id": task.task_id},
            )
            try:
                result = fn(progress_callback)
                status = str(result.get("status", "")).strip()
                resolved_run_dir = str(result.get("run_dir", "")).strip()
                if resolved_run_dir:
                    self._set_task_progress(task, run_dir=resolved_run_dir)
                with self._lock:
                    task.result = result
                    task.finished_at = utc_now_iso()
                    if status == "ok":
                        task.status = "succeeded"
                    elif status == "awaiting_approval":
                        task.status = "awaiting_approval"
                        task.error = str(result.get("reason", "")).strip()
                    elif status == "blocked":
                        task.status = "blocked"
                        task.error = str(result.get("reason", "")).strip()
                    elif status == "partial":
                        task.status = "partial"
                        task.error = str(result.get("last_result", {}).get("reason", "")).strip()
                    else:
                        task.status = "failed"
                        task.error = str(result.get("reason") or result.get("message") or "workflow task failed").strip()
                self._append_task_event(
                    task,
                    event_type="task_finished",
                    stage=task.stage,
                    message=f"Finished background task `{task.action}` with status `{task.status}`.",
                    data={"task_id": task.task_id, "status": task.status},
                )
            except Exception as exc:
                with self._lock:
                    task.status = "failed"
                    task.finished_at = utc_now_iso()
                    task.error = str(exc)
                    task.result = {"status": "failed", "reason": str(exc), "stage": task.stage, "run_dir": task.run_dir}
                self._append_task_event(
                    task,
                    event_type="task_failed",
                    stage=task.stage,
                    message=str(exc),
                    data={"task_id": task.task_id},
                )

        thread = threading.Thread(target=worker, name=f"workflow-task-{task.task_id[:8]}", daemon=True)
        with self._lock:
            self._threads[task.task_id] = thread
        thread.start()
        return task

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.to_dict()

    def list_tasks(self, *, run_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            tasks = list(self._tasks.values())
        if run_id:
            tasks = [task for task in tasks if task.run_id == run_id]
        tasks.sort(key=lambda task: task.created_at, reverse=True)
        return [task.to_dict() for task in tasks[: max(1, limit)]]

    def launch_run(
        self,
        *,
        source_text: str = "",
        source_path: str = "",
        source_script_name: str = "",
        input_mode: Literal["auto", "keywords", "brief", "script"] = AUTO_INPUT_MODE,
        run_dir: str = "",
        execution_mode: Literal["upstream_only", "mainline"] = "mainline",
        parallel_planning: bool = True,
    ) -> dict[str, Any]:
        if run_dir.strip():
            resolved_run_dir = Path(run_dir).resolve()
            if not resolved_run_dir.exists():
                raise FileNotFoundError(f"Run directory not found: {resolved_run_dir}")
            effective_run_dir = resolved_run_dir
            effective_source_name = source_script_name.strip() or self.service.load_source_script_name(effective_run_dir)
        else:
            effective_run_dir = None
            effective_source_name = source_script_name.strip() or "intent_input"

        action = "run_mainline" if execution_mode == "mainline" else "start_upstream_only"
        task = self._build_task(action=action, run_dir=effective_run_dir, stage="upstream")

        def run_job(progress_callback: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
            if execution_mode == "upstream_only":
                return self.service.start_or_resume(
                    source_text=source_text,
                    source_path=source_path,
                    source_script_name=effective_source_name,
                    input_mode=input_mode,
                    run_dir=str(effective_run_dir) if effective_run_dir is not None else "",
                    progress_callback=progress_callback,
                )
            return self.service.run_mainline(
                source_text=source_text,
                source_path=source_path,
                source_script_name=effective_source_name,
                input_mode=input_mode,
                run_dir=str(effective_run_dir) if effective_run_dir is not None else "",
                parallel_planning=parallel_planning,
                progress_callback=progress_callback,
            )

        launched = self._start_task(task, run_job)
        return launched.to_dict()

    def launch_continue_run(
        self,
        *,
        run_dir: str,
        parallel_planning: bool = False,
    ) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        if not resolved_run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {resolved_run_dir}")
        source_script_name = self.service.load_source_script_name(resolved_run_dir)
        task = self._build_task(action="continue_mainline", run_dir=resolved_run_dir, stage="")

        def run_job(progress_callback: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
            return self.service.run_mainline(
                run_dir=str(resolved_run_dir),
                source_script_name=source_script_name,
                parallel_planning=parallel_planning,
                progress_callback=progress_callback,
            )

        launched = self._start_task(task, run_job)
        return launched.to_dict()

    def launch_stage(
        self,
        *,
        run_dir: str,
        stage: WorkflowStage,
        force: bool = True,
        selected_shots: set[str] | None = None,
        resolution: str = "720p",
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 10,
        keep_remote_media: bool = False,
        trim_leading_seconds: float = 1.0,
        blackout_leading_seconds: float = 0.2,
    ) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        if not resolved_run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {resolved_run_dir}")
        source_script_name = self.service.load_source_script_name(resolved_run_dir)
        task = self._build_task(action="run_stage", run_dir=resolved_run_dir, stage=stage)

        def run_job(_progress_callback: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
            return self.service.run_stage(
                stage,
                run_dir=resolved_run_dir,
                source_script_name=source_script_name,
                force=force,
                selected_shots=selected_shots,
                resolution=resolution,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                keep_remote_media=keep_remote_media,
                trim_leading_seconds=trim_leading_seconds,
                blackout_leading_seconds=blackout_leading_seconds,
            )

        launched = self._start_task(task, run_job)
        return launched.to_dict()
