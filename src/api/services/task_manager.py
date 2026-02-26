"""TaskManager - manages at most one background task with progress broadcasting."""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    DOWNLOAD = "download"
    TRAIN = "train"
    PREDICT = "predict"


@dataclass
class TaskEvent:
    """A progress/completion/error event from a background task."""

    event_type: str  # "progress", "finished", "error"
    data: dict[str, Any]


@dataclass
class RunningTask:
    task_id: str
    task_type: TaskType
    thread: threading.Thread
    cancelled: bool = False


class TaskManager:
    """Manages at most one long-running background task.

    Thread-safe: background threads call broadcast() which puts events into
    asyncio queues for SSE subscribers.
    """

    def __init__(self) -> None:
        self._current: RunningTask | None = None
        self._subscribers: list[asyncio.Queue[TaskEvent | None]] = []
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def active_task(self) -> RunningTask | None:
        return self._current

    def start_download(self, full: bool = False) -> str:
        return self._start_task(TaskType.DOWNLOAD, full=full)

    def start_training(self) -> str:
        return self._start_task(TaskType.TRAIN)

    def start_predictions(self) -> str:
        return self._start_task(TaskType.PREDICT)

    def _start_task(self, task_type: TaskType, **kwargs) -> str:
        with self._lock:
            if self._current is not None and self._current.thread.is_alive():
                raise RuntimeError(f"Task {self._current.task_type.value} is already running")

            task_id = uuid.uuid4().hex[:8]
            thread = threading.Thread(
                target=self._run_task,
                args=(task_id, task_type),
                kwargs=kwargs,
                daemon=True,
            )
            self._current = RunningTask(task_id=task_id, task_type=task_type, thread=thread)
            thread.start()
            return task_id

    def _run_task(self, task_id: str, task_type: TaskType, **kwargs) -> None:
        """Entry point for the background thread."""
        from src.tui.tasks import (
            DownloadError,
            DownloadFinished,
            PredictionError,
            PredictionFinished,
            TrainingError,
            TrainingFinished,
            run_download,
            run_predictions,
            run_training,
        )

        def on_progress(event: Any) -> None:
            """Convert Textual Message objects to TaskEvents."""
            # Determine event type from class name
            cls_name = type(event).__name__

            if isinstance(event, (DownloadFinished, TrainingFinished, PredictionFinished)):
                data = _serialize_event(event)
                # Cache predictions to disk for the /api/predictions/latest endpoint
                if isinstance(event, PredictionFinished) and event.picks:
                    _cache_predictions(event.picks)
                self.broadcast(TaskEvent(event_type="finished", data=data))
            elif isinstance(event, (DownloadError, TrainingError, PredictionError)):
                self.broadcast(TaskEvent(event_type="error", data={"message": event.error}))
            else:
                data = _serialize_event(event)
                self.broadcast(TaskEvent(event_type="progress", data=data))

        def is_cancelled() -> bool:
            with self._lock:
                return self._current is not None and self._current.cancelled

        try:
            if task_type == TaskType.DOWNLOAD:
                run_download(on_progress=on_progress, is_cancelled=is_cancelled, full=kwargs.get("full", False))
            elif task_type == TaskType.TRAIN:
                run_training(on_progress=on_progress, is_cancelled=is_cancelled)
            elif task_type == TaskType.PREDICT:
                run_predictions(on_progress=on_progress, is_cancelled=is_cancelled)
        except Exception as e:
            self.broadcast(TaskEvent(event_type="error", data={"message": str(e)}))
        finally:
            # Signal end of stream to all subscribers
            self.broadcast(None)  # type: ignore[arg-type]
            with self._lock:
                if self._current and self._current.task_id == task_id:
                    self._current = None

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            if self._current and self._current.task_id == task_id:
                self._current.cancelled = True
                return True
            return False

    def subscribe(self) -> asyncio.Queue[TaskEvent | None]:
        q: asyncio.Queue[TaskEvent | None] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast(self, event: TaskEvent | None) -> None:
        """Thread-safe: push event to all SSE subscriber queues."""
        if self._loop is None:
            return
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, event)


def _cache_predictions(picks: list) -> None:
    """Save predictions to disk so the REST endpoint can serve them."""
    import json
    from pathlib import Path

    cache_path = Path(__file__).parent.parent.parent.parent / "data" / "processed" / "latest_predictions.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(picks, f, indent=2, default=str)


def _serialize_event(event: Any) -> dict:
    """Convert a Message event to a JSON-serializable dict."""
    from src.tui.tasks import (
        DownloadFinished,
        DownloadProgress,
        PredictionFinished,
        PredictionProgress,
        TrainingFinished,
        TrainingProgress,
    )

    if isinstance(event, DownloadProgress):
        r = event.result
        return {
            "step": f"{r.task.country} {r.task.league_name} {r.task.year}",
            "detail": f"{r.match_count} kamper" if r.ok else (r.error or "ingen kamper"),
            "completed": event.completed,
            "total": event.total,
            "percent": int((event.completed / event.total) * 100) if event.total else 0,
        }
    elif isinstance(event, DownloadFinished):
        ok = sum(1 for r in event.results if r.ok and not r.skipped)
        failed = sum(1 for r in event.results if r.error)
        skipped = sum(1 for r in event.results if r.skipped)
        matches = sum(r.match_count for r in event.results if r.ok and not r.skipped)
        return {
            "ok": ok,
            "failed": failed,
            "skipped": skipped,
            "matches": matches,
        }
    elif isinstance(event, TrainingProgress):
        return {
            "step": event.step,
            "detail": event.detail,
            "percent": event.percent,
        }
    elif isinstance(event, TrainingFinished):
        return {"report": event.report}
    elif isinstance(event, PredictionProgress):
        return {
            "step": event.step,
            "detail": event.detail,
        }
    elif isinstance(event, PredictionFinished):
        return {
            "picks": event.picks,
            "match_count": event.match_count,
            "stale_warning": event.stale_warning,
        }
    return {"type": type(event).__name__}
