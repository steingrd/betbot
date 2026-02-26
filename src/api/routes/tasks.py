"""Task endpoints - start/cancel long-running tasks and stream progress via SSE."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models import TaskStarted
from ..services.task_manager import TaskManager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_task_manager(request: Request) -> TaskManager:
    return request.app.state.task_manager


@router.post("/download")
def start_download(request: Request, full: bool = False) -> TaskStarted:
    tm = get_task_manager(request)
    try:
        task_id = tm.start_download(full=full)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TaskStarted(task_id=task_id, task_type="download")


@router.post("/train")
def start_training(request: Request) -> TaskStarted:
    tm = get_task_manager(request)
    try:
        task_id = tm.start_training()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TaskStarted(task_id=task_id, task_type="train")


@router.post("/predict")
def start_predictions(request: Request) -> TaskStarted:
    tm = get_task_manager(request)
    try:
        task_id = tm.start_predictions()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TaskStarted(task_id=task_id, task_type="predict")


@router.get("/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    tm = get_task_manager(request)

    # Verify this is the active task
    if tm.active_task is None or tm.active_task.task_id != task_id:
        raise HTTPException(status_code=404, detail="No such active task")

    queue = tm.subscribe()

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue

                if event is None:
                    # End of stream
                    break

                data = json.dumps(event.data, default=str)
                yield f"event: {event.event_type}\ndata: {data}\n\n"

                if event.event_type in ("finished", "error"):
                    break
        finally:
            tm.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{task_id}")
def cancel_task(task_id: str, request: Request):
    tm = get_task_manager(request)
    if not tm.cancel(task_id):
        raise HTTPException(status_code=404, detail="No such active task")
    return {"status": "cancelled"}
