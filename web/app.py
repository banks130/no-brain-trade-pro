"""
web/app.py — No-Brain-Trade Pro
FastAPI web dashboard. Live feed + trending + Pro gate.
"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from models.db import get_db, TokenCache
from models.token import TokenData
from utils.helpers import format_number, shorten_address
from utils.logger import logger
import os

app = FastAPI(title="No-Brain-Trade")

# Static + templates
BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))
static_dir = os.path.join(BASE, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── Shared in-memory state (populated by main pipeline) ───────
_feed: list[dict] = []         # live token feed
_spikes: list[dict] = []       # spike events
_sse_queues: list[asyncio.Queue] = []


def push_to_web(token: TokenData, event_type: str = "token"):
    """Called by main pipeline to push updates to the web dashboard."""
    data = {
        "type": event_type,
        "mint": token.mint,
        "symbol": token.symbol,
        "name": token.name,
        "spike_pct": round(token.spike_pct, 1),
        "safety_score": token.safety_score,
        "liquidity_sol": round(token.liquidity_sol, 2),
        "holder_count": token.holder_count,
        "volume_5m": round(token.volume_5m_usd, 0),
        "tags": token.tags[:3],
        "risk": token.risk_label(),
        "ts": datetime.utcnow().strftime("%H:%M:%S"),
    }
    if event_type == "spike":
        _spikes.insert(0, data)
        if len(_spikes) > 100:
            _spikes.pop()
    _feed.insert(0, data)
    if len(_feed) > 200:
        _feed.pop()
    for q in _sse_queues:
        try:
            q.put_nowait(json.dumps(data))
        except asyncio.QueueFull:
            pass


# ── Routes ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/feed")
async def api_feed():
    return JSONResponse(_feed[:50])


@app.get("/api/spikes")
async def api_spikes():
    return JSONResponse(_spikes[:50])


@app.get("/stream")
async def sse_stream():
    """Server-Sent Events stream for real-time updates."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_queues.append(q)

    async def generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keep-alive
        except asyncio.CancelledError:
            pass
        finally:
            if q in _sse_queues:
                _sse_queues.remove(q)

    return StreamingResponse(generator(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
