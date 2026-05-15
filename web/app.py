from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from datetime import datetime
from typing import List, Dict
import json
import os

app = FastAPI(title="No-Brain-Trade Pro")

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "web", "templates")

# Ensure templates directory exists
os.makedirs(TEMPLATES_DIR, exist_ok=True)

token_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
recent_tokens: List[Dict] = []

def push_to_web(token, event_type: str):
    """Push real token to web dashboard"""
    try:
        token_dict = {
            "mint": getattr(token, 'mint', 'unknown'),
            "symbol": getattr(token, 'symbol', '???'),
            "name": getattr(token, 'name', 'Unknown'),
            "price_sol": getattr(token, 'price_sol', 0),
            "spike_pct": getattr(token, 'spike_pct', 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        token_queue.put_nowait((event_type, token_dict))
        recent_tokens.insert(0, token_dict)
        if len(recent_tokens) > 100:
            recent_tokens.pop()
        print(f"[web] {event_type.upper()}: {token_dict['symbol']}")
    except asyncio.QueueFull:
        pass

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard"""
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>No-Brain-Trade Pro</h1><p>Index template not found</p>")

@app.get("/warroom", response_class=HTMLResponse)
async def war_room(request: Request):
    """Serve the War Room dashboard"""
    warroom_path = os.path.join(TEMPLATES_DIR, "war_room.html")
    if os.path.exists(warroom_path):
        with open(warroom_path, 'r') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>War Room</h1><p>War room template not found</p>")

@app.get("/events")
async def events():
    """SSE endpoint for real-time updates"""
    async def event_generator():
        while True:
            try:
                event_type, token = await asyncio.wait_for(token_queue.get(), timeout=30)
                yield f"event: {event_type}\ndata: {json.dumps(token)}\n\n"
            except asyncio.TimeoutError:
                yield "event: ping\ndata: \n\n"
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/tokens")
async def get_tokens(limit: int = 50):
    """Get recent tokens"""
    return recent_tokens[:limit]

@app.get("/api/health")
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "alive", 
        "timestamp": datetime.utcnow().isoformat(), 
        "tokens": len(recent_tokens),
        "queue_size": token_queue.qsize()
    }

@app.get("/api/stats")
async def stats():
    """Get statistics"""
    spikes = [t for t in recent_tokens if t.get('spike_pct', 0) > 150]
    return {
        "total_tokens": len(recent_tokens),
        "total_spikes": len(spikes),
        "highest_spike": max([t.get('spike_pct', 0) for t in recent_tokens]) if recent_tokens else 0
    }
