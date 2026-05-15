from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio
from datetime import datetime
from typing import List
from models.token import TokenData
import json

# Try to import sse-starlette, fallback to simple implementation
try:
    from sse_starlette.sse import EventSourceResponse
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    print("[web] sse-starlette not available, using fallback")

app = FastAPI(title="No-Brain-Trade Pro")

# Create templates directory if not exists
import os
os.makedirs("web/templates", exist_ok=True)

templates = Jinja2Templates(directory="web/templates")

# Store for real-time updates
token_queue: asyncio.Queue = asyncio.Queue()
recent_tokens: List[TokenData] = []

def push_to_web(token: TokenData, event_type: str):
    """Push token update to web dashboard"""
    try:
        token_queue.put_nowait((event_type, token))
        recent_tokens.append(token)
        if len(recent_tokens) > 100:
            recent_tokens.pop(0)
    except asyncio.QueueFull:
        pass

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/events")
async def events():
    """SSE endpoint for real-time updates"""
    async def event_generator():
        while True:
            try:
                event_type, token = await asyncio.wait_for(token_queue.get(), timeout=30)
                yield {
                    "event": event_type,
                    "data": token.json()
                }
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
    
    if SSE_AVAILABLE:
        return EventSourceResponse(event_generator())
    else:
        # Fallback: return a simple streaming response
        from fastapi.responses import StreamingResponse
        async def generate():
            async for event in event_generator():
                yield f"event: {event['event']}\ndata: {event['data']}\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/tokens")
async def get_tokens(limit: int = 50):
    """Get recent tokens"""
    return [t.dict() for t in recent_tokens[-limit:]]

@app.get("/api/trending")
async def get_trending():
    """Get trending tokens"""
    return {"trending": []}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
