from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio
from datetime import datetime
from typing import List, Dict
import json
import os

app = FastAPI(title="No-Brain-Trade Pro")

# Create templates directory
os.makedirs("web/templates", exist_ok=True)

token_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
recent_tokens: List[Dict] = []

def push_to_web(token, event_type: str):
    """Push token to web dashboard"""
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
        print(f"[web] {event_type}: {token_dict['symbol']} +{token_dict['spike_pct']:.0f}%")
    except:
        pass

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No-Brain-Trade Pro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff00; padding: 20px; }
        h1 { text-align: center; border-bottom: 2px solid #00ff00; padding-bottom: 20px; margin-bottom: 20px; }
        .stats { display: flex; justify-content: space-between; max-width: 800px; margin: 0 auto 20px; padding: 10px; background: #111; border-radius: 5px; }
        .stat { text-align: center; }
        .stat-value { font-size: 2rem; font-weight: bold; }
        .stat-label { font-size: 0.7rem; color: #666; }
        .token-list { max-width: 800px; margin: 0 auto; }
        .token { background: #111; padding: 15px; margin: 10px 0; border-left: 3px solid #00ff00; border-radius: 5px; animation: slideIn 0.3s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-20px); } to { opacity: 1; transform: translateX(0); } }
        .token.spike { border-left-color: #ff0000; background: #1a0000; animation: pulse 0.5s, slideIn 0.3s; }
        @keyframes pulse { 0% { background: #1a0000; } 50% { background: #ff000020; } 100% { background: #1a0000; } }
        .token-symbol { font-size: 1.2rem; font-weight: bold; display: inline-block; }
        .token-price { float: right; font-size: 0.9rem; color: #888; }
        .token-spike { color: #ff0000; font-weight: bold; margin-left: 10px; display: inline-block; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.7rem; margin-top: 20px; }
        .status { position: fixed; bottom: 10px; right: 10px; background: #000; padding: 5px 10px; border-radius: 5px; font-size: 0.7rem; color: #00ff00; }
        .nav { display: flex; justify-content: center; gap: 20px; margin-bottom: 20px; }
        .nav a { color: #00ff00; text-decoration: none; padding: 5px 10px; border: 1px solid #00ff00; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">LIVE FEED</a>
        <a href="/warroom">WAR ROOM</a>
    </div>
    <h1>⚡ NO-BRAIN-TRADE PRO ⚡</h1>
    <div class="stats">
        <div class="stat"><div class="stat-value" id="spikeCount">0</div><div class="stat-label">SPIKES</div></div>
        <div class="stat"><div class="stat-value" id="tokenCount">0</div><div class="stat-label">TOKENS</div></div>
        <div class="stat"><div class="stat-value" id="highestSpike">0%</div><div class="stat-label">HIGHEST</div></div>
    </div>
    <div class="token-list" id="tokens"><div style="text-align:center;padding:40px;">⏳ Waiting for tokens...</div></div>
    <div class="footer">🔥 Live Scanner | 🤖 AI Analysis | 💰 Auto-Trading</div>
    <div class="status" id="status">🟢 CONNECTED</div>
    <script>
        let spikeCount=0,tokenCount=0,highestSpike=0;
        let es=new EventSource('/events');
        es.onopen=()=>document.getElementById('status').innerHTML='🟢 CONNECTED';
        es.onerror=()=>document.getElementById('status').innerHTML='⚠️ RECONNECTING';
        es.addEventListener('spike',e=>{let t=JSON.parse(e.data);addToken(t,true);spikeCount++;tokenCount++;updateStats(t);});
        es.addEventListener('token',e=>{let t=JSON.parse(e.data);addToken(t,false);tokenCount++;updateStats(t);});
        function updateStats(t){document.getElementById('spikeCount').innerHTML=spikeCount;document.getElementById('tokenCount').innerHTML=tokenCount;if(t.spike_pct>highestSpike){highestSpike=t.spike_pct;document.getElementById('highestSpike').innerHTML=Math.round(highestSpike)+'%';}}
        function addToken(t,isSpike){let c=document.getElementById('tokens');let d=document.createElement('div');d.className=isSpike?'token spike':'token';let s=isSpike?`<span class="token-spike">🚀 +${Math.round(t.spike_pct)}%</span>`:'';d.innerHTML=`<div><span class="token-symbol">${t.symbol}</span>${s}<span class="token-price">💰 ${(t.price_sol||0).toFixed(8)} SOL</span></div>`;c.prepend(d);while(c.children.length>50)c.removeChild(c.lastChild);}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/warroom", response_class=HTMLResponse)
async def war_room(request: Request):
    warroom_path = "web/templates/war_room.html"
    if os.path.exists(warroom_path):
        with open(warroom_path, 'r') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>War Room</h1><p>Upload war_room.html to web/templates/</p>")

@app.get("/events")
async def events():
    async def event_generator():
        while True:
            try:
                event_type, token = await asyncio.wait_for(token_queue.get(), timeout=30)
                yield f"event: {event_type}\ndata: {json.dumps(token)}\n\n"
            except asyncio.TimeoutError:
                yield "event: ping\ndata: \n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/tokens")
async def get_tokens():
    return recent_tokens[:50]

@app.get("/health")
async def health():
    return {"status": "alive", "tokens": len(recent_tokens)}
