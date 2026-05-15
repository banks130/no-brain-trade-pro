from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio
from datetime import datetime
from typing import List, Dict
import json

app = FastAPI(title="No-Brain-Trade Pro")

token_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
recent_tokens: List[Dict] = []

def push_to_web(token, event_type: str):
    """Push real token to web dashboard"""
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
        print(f"[web] REAL {event_type.upper()}: {token.symbol} @ ${token.price_sol:.8f}")
    except asyncio.QueueFull:
        pass

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Real dashboard - no test spikes"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>No-Brain-Trade Pro - Real Pump.fun Scanner</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                background: #0a0a0a; 
                color: #00ff00; 
                font-family: 'Courier New', monospace; 
                padding: 20px; 
                min-height: 100vh;
            }
            .header { 
                text-align: center; 
                padding: 20px; 
                border-bottom: 2px solid #00ff00; 
                margin-bottom: 20px;
            }
            .header h1 { font-size: 1.5rem; }
            .header p { color: #888; font-size: 0.8rem; margin-top: 10px; }
            .badge {
                display: inline-block;
                background: #00ff0020;
                color: #00ff00;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 0.7rem;
                margin-top: 10px;
            }
            .stats { 
                display: flex; 
                justify-content: space-between; 
                max-width: 800px; 
                margin: 0 auto 20px;
                padding: 10px;
                background: #111;
                border-radius: 5px;
            }
            .stat { text-align: center; }
            .stat-value { font-size: 1.5rem; font-weight: bold; }
            .stat-label { font-size: 0.7rem; color: #666; }
            .token-list { max-width: 800px; margin: 0 auto; }
            .token {
                background: #111;
                padding: 15px;
                margin: 10px 0;
                border-left: 3px solid #00ff00;
                border-radius: 5px;
                animation: slideIn 0.3s ease;
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateX(-20px); }
                to { opacity: 1; transform: translateX(0); }
            }
            .token.spike {
                border-left-color: #ff0000;
                background: #1a0000;
                animation: pulse 0.5s, slideIn 0.3s;
            }
            @keyframes pulse {
                0% { background: #1a0000; }
                50% { background: #ff000020; }
                100% { background: #1a0000; }
            }
            .token-symbol { font-size: 1.2rem; font-weight: bold; display: inline-block; }
            .token-price { float: right; font-size: 0.9rem; color: #888; }
            .token-spike { color: #ff0000; font-weight: bold; margin-left: 10px; display: inline-block; }
            .token-mint { font-size: 0.7rem; color: #444; margin-top: 5px; font-family: monospace; }
            .token-time { font-size: 0.7rem; color: #444; margin-top: 5px; }
            .footer { text-align: center; padding: 20px; color: #666; font-size: 0.7rem; margin-top: 20px; }
            .status { position: fixed; bottom: 10px; right: 10px; background: #000; padding: 5px 10px; border-radius: 5px; font-size: 0.7rem; }
            .status.online { color: #00ff00; }
            .warning { background: #ff000020; border: 1px solid #ff0000; color: #ff0000; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ NO-BRAIN-TRADE PRO ⚡</h1>
            <p>REAL pump.fun scanner | Live token detection | 150%+ spike alerts</p>
            <div class="badge">🔴 LIVE MODE - REAL TOKENS</div>
        </div>
        
        <div class="stats">
            <div class="stat"><div class="stat-value" id="spikeCount">0</div><div class="stat-label">SPIKES</div></div>
            <div class="stat"><div class="stat-value" id="tokenCount">0</div><div class="stat-label">TOKENS</div></div>
            <div class="stat"><div class="stat-value" id="highestSpike">0%</div><div class="stat-label">HIGHEST</div></div>
        </div>
        
        <div class="token-list" id="tokens">
            <div style="text-align: center; color: #666; padding: 40px;">
                ⏳ Waiting for real pump.fun tokens...<br>
                Scanner is connected and listening for new tokens.
            </div>
        </div>
        
        <div class="footer">
            🔥 Real pump.fun data | 🤖 AI Analysis | 💰 Non-custodial auto-trading
        </div>
        
        <div class="status online" id="status">
            🟢 CONNECTED TO PUMP.FUN
        </div>
        
        <script>
            let spikeCount = 0, tokenCount = 0, highestSpike = 0;
            let eventSource = null;
            
            function connect() {
                if (eventSource) eventSource.close();
                eventSource = new EventSource('/events');
                eventSource.onopen = () => {
                    document.getElementById('status').innerHTML = '🟢 CONNECTED - LISTENING FOR TOKENS';
                    document.getElementById('status').className = 'status online';
                };
                eventSource.onerror = () => {
                    document.getElementById('status').innerHTML = '⚠️ RECONNECTING...';
                };
                eventSource.addEventListener('spike', (e) => {
                    const token = JSON.parse(e.data);
                    addToken(token, true);
                    spikeCount++;
                    document.getElementById('spikeCount').innerHTML = spikeCount;
                    tokenCount++;
                    document.getElementById('tokenCount').innerHTML = tokenCount;
                    if (token.spike_pct > highestSpike) {
                        highestSpike = token.spike_pct;
                        document.getElementById('highestSpike').innerHTML = Math.round(highestSpike) + '%';
                    }
                    if (navigator.vibrate) navigator.vibrate(200);
                });
                eventSource.addEventListener('token', (e) => {
                    const token = JSON.parse(e.data);
                    addToken(token, false);
                    tokenCount++;
                    document.getElementById('tokenCount').innerHTML = tokenCount;
                });
            }
            
            function addToken(token, isSpike) {
                const container = document.getElementById('tokens');
                const tokenDiv = document.createElement('div');
                tokenDiv.className = isSpike ? 'token spike' : 'token';
                const spikeHtml = isSpike ? `<span class="token-spike">🚀 +${Math.round(token.spike_pct || 0)}%</span>` : '';
                const price = (token.price_sol || 0).toFixed(8);
                const mintShort = token.mint ? token.mint.slice(0, 8) + '...' : 'unknown';
                const time = new Date().toLocaleTimeString();
                tokenDiv.innerHTML = `
                    <div><span class="token-symbol">${token.symbol || '???'}</span>${spikeHtml}<span class="token-price">💰 ${price} SOL</span></div>
                    <div class="token-mint">📝 ${mintShort}</div>
                    <div class="token-time">🕐 ${time}</div>
                `;
                container.prepend(tokenDiv);
                while(container.children.length > 50) container.removeChild(container.lastChild);
            }
            
            connect();
            setInterval(() => { if(eventSource) eventSource.close(); connect(); }, 300000);
        </script>
    </body>
    </html>
    """)

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
async def get_tokens(limit: int = 50):
    return recent_tokens[:limit]

@app.get("/api/health")
@app.get("/health")
async def health():
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat(), "tokens": len(recent_tokens)}
