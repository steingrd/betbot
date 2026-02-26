"""Chat WebSocket endpoint - bidirectional LLM streaming."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ..models import ChatMessageResponse

router = APIRouter(tags=["chat"])

BASE_DIR = Path(__file__).parent.parent.parent.parent


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()

    from src.chat.history import ChatHistory
    from src.chat.llm_provider import ChatMessage
    from src.chat.providers import create_provider
    from src.chat.system_prompt import build_system_prompt

    history = ChatHistory()

    try:
        provider = create_provider()
    except RuntimeError as e:
        await websocket.send_json({"type": "error", "content": str(e)})
        await websocket.close()
        return

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            user_text = data.get("content", "")

            if not user_text.strip():
                continue

            # Save user message
            history.add(ChatMessage(role="user", content=user_text))

            # Load predictions for system prompt context
            predictions = _load_predictions()

            # Build message list
            system = build_system_prompt(predictions=predictions)
            messages = [ChatMessage(role="system", content=system)]
            messages.extend(history.get_recent(limit=20))

            # Stream response
            full_response = ""
            try:
                async for token in provider.stream_response(messages):
                    full_response += token
                    await websocket.send_json({"type": "token", "content": token})

                # Save and signal done
                history.add(ChatMessage(role="assistant", content=full_response))
                await websocket.send_json({"type": "done", "content": full_response})
            except Exception as e:
                await websocket.send_json({"type": "error", "content": f"LLM error: {e}"})

    except WebSocketDisconnect:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        history.close()


@router.get("/api/chat/history")
def get_chat_history(limit: int = Query(default=20, le=100)) -> list[ChatMessageResponse]:
    from src.chat.history import ChatHistory

    history = ChatHistory()
    try:
        messages = history.get_recent(limit=limit)
    finally:
        history.close()

    return [
        ChatMessageResponse(role=m.role, content=m.content)
        for m in messages
    ]


@router.delete("/api/chat/history")
def clear_chat_history():
    from src.chat.history import ChatHistory

    history = ChatHistory()
    try:
        history.clear()
    finally:
        history.close()
    return {"status": "cleared"}


def _load_predictions() -> list[dict] | None:
    cache_path = BASE_DIR / "data" / "processed" / "latest_predictions.json"
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            return json.load(f)
    except Exception:
        return None
