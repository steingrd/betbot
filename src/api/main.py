"""BetBot Web API - FastAPI application."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import chat, data, predictions, tasks
from .services.task_manager import TaskManager

# Ensure src/ is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env
load_dotenv(PROJECT_ROOT / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tm = TaskManager()
    tm.set_loop(asyncio.get_running_loop())
    app.state.task_manager = tm
    yield
    # Shutdown - cancel any running task
    if tm.active_task:
        tm.cancel(tm.active_task.task_id)


app = FastAPI(title="BetBot API", lifespan=lifespan)

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(data.router)
app.include_router(tasks.router)
app.include_router(predictions.router)
app.include_router(chat.router)

# Serve built React app in production
WEB_DIST = PROJECT_ROOT / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static")
