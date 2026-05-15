from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import asyncio
from datetime import datetime
from typing import List, Dict
import json
import os

app = FastAPI(title="No-Brain-Trade Pro")

# FIXED: Use absolute path for templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "web", "templates")
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
        # Fallback HTML with API links
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>No-Brain-Trade Pro</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ background: #0a0a0a; color: #00ff00; font-family: monospace; padding: 20px; }}
                h1 {{ color: #00ff00; }}
                a {{ color: #00ff00; }}
                .token {{ background: #111; padding: 10px; margin: 5px; border-left: 3px solid #00ff00; }}
                .spike {{ border-left-color: #ff0000; background: #1a0000; }}
            </style>
        </head>
        <body>
            <h1>⚡ No-Brain-Trade Pro ⚡</h1>
            <p>Real-time pump.fun spike detection | 150%+ alerts</p>
            
            <h2>Live Tokens:</h2>
            <div id="tokens"></div>
            
            <p><a href="/api/tokens">View API</a> | <a href="/health">Health Check</a></p>
            
            <script>
                const eventSource = new EventSource('/events');
                const tokensDiv = document.getElementById('tokens');
                
                eventSource.addEventListener('spike', function(e) {{
                    const token = JSON.parse(e.data);
                    const div = document.createElement('div');
                    div.className = 'token spike';
                    div.innerHTML = `<strong>🚀 ${{token.symbol}}</strong> +${{token.spike_pct?.toFixed(0) || 0}}% - ${{token.price_sol?.toFixed(8) || 0}} SOL`;
                    tokensDiv.prepend(div);
                    while(tokensDiv.children.length > 50) tokensDiv.removeChild(tokensDiv.lastChild);
                }});
                
                eventSource.addEventListener('token', function(e) {{
                    const token = JSON.parse(e.data);
                    const div = document.createElement('div');
                    div.className = 'token';
                    div.innerHTML = `<strong>${{token.symbol}}</strong> ${{token.price_sol?.toFixed(8) || 0}} SOL`;
                    tokensDiv.prepend(div);
                    while(tokensDiv.children.length > 50) tokensDiv.removeChild(tokensDiv.lastChild);
                }});
            </script>
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
        "tokens_tracked": len(recent_tokens),
        "template_dir": TEMPLATES_DIR,
        "template_exists": os.path.exists(os.path.join(TEMPLATES_DIR, "index.html"))
    }

@app.get("/api/stats")
async def stats():
    """Get service statistics"""
    return {
        "uptime": "running",
        "queue_size": token_queue.qsize(),
        "recent_tokens": len(recent_tokens)
    }
