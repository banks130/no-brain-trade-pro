from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
from datetime import datetime
from typing import List, Dict
import json
import os

app = FastAPI(title="No-Brain-Trade Pro")

# Ensure templates directory exists
TEMPLATES_DIR = "web/templates"
os.makedirs(TEMPLATES_DIR, exist_ok=True)

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Store for real-time updates
token_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
recent_tokens: List[Dict] = []

def push_to_web(token, event_type: str):
    """Push token update to web dashboard"""
    try:
        token_dict = {
            "mint": token.mint,
            "symbol": token.symbol,
            "name": token.name,
            "price_sol": token.price_sol,
            "spike_pct": token.spike_pct,
            "timestamp": datetime.utcnow().isoformat()
        }
        token_queue.put_nowait((event_type, token_dict))
        recent_tokens.insert(0, token_dict)
        if len(recent_tokens) > 100:
            recent_tokens.pop()
    except asyncio.QueueFull:
        pass

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the dashboard"""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        # Fallback HTML if template not found
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>No-Brain-Trade Pro</title></head>
        <body style="background:black;color:lime;font-family:monospace;padding:20px;">
        <h1>⚡ No-Brain-Trade Pro</h1>
        <p>Service is running. Template loading failed, but API is working.</p>
        <p><a href="/api/tokens" style="color:lime;">View API</a></p>
        </body>
        </html>
        """)

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
        "queue_size": token_queue.qsize(),
        "tokens_tracked": len(recent_tokens)
    }

@app.get("/api/stats")
async def stats():
    """Get service statistics"""
    return {
        "uptime": "running",
        "queue_size": token_queue.qsize(),
        "recent_tokens": len(recent_tokens)
    }
