from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio
from datetime import datetime
from typing import List, Dict
import json
import os
import random

app = FastAPI(title="No-Brain-Trade Pro")

# Store for real-time updates
token_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
recent_tokens: List[Dict] = []

# Sample tokens for testing (remove in production)
SAMPLE_TOKENS = [
    {"symbol": "BONK", "name": "Bonk", "price_sol": 0.000042, "spike_pct": 0},
    {"symbol": "WIF", "name": "DogWifHat", "price_sol": 0.0023, "spike_pct": 0},
    {"symbol": "POPCAT", "name": "Popcat", "price_sol": 0.0018, "spike_pct": 0},
]

def push_to_web(token, event_type: str):
    """Push token update to web dashboard"""
    try:
        token_dict = {
            "mint": getattr(token, 'mint', f"test_{random.randint(1,9999)}"),
            "symbol": getattr(token, 'symbol', f"TOKEN{random.randint(1,99)}"),
            "name": getattr(token, 'name', 'Test Token'),
            "price_sol": getattr(token, 'price_sol', random.uniform(0.0001, 0.01)),
            "spike_pct": getattr(token, 'spike_pct', random.uniform(50, 300)),
            "timestamp": datetime.utcnow().isoformat()
        }
        token_queue.put_nowait((event_type, token_dict))
        recent_tokens.insert(0, token_dict)
        if len(recent_tokens) > 100:
            recent_tokens.pop()
        print(f"[web] Pushed {event_type}: {token_dict['symbol']}")
    except asyncio.QueueFull:
        pass

# Function to generate test spikes (remove in production)
async def generate_test_spikes():
    """Generate test spikes every 30 seconds for testing"""
    test_spikes = [
        {"symbol": "🚀 MOON", "name": "MoonToken", "price": 0.005, "spike": 250},
        {"symbol": "💎 DIAMOND", "name": "DiamondHands", "price": 0.008, "spike": 180},
        {"symbol": "🐶 DOGE2", "name": "Doge 2.0", "price": 0.003, "spike": 320},
        {"symbol": "🟣 PEPE", "name": "Pepe Coin", "price": 0.0005, "spike": 200},
        {"symbol": "🔥 FIRE", "name": "FireToken", "price": 0.012, "spike": 450},
    ]
    
    while True:
        await asyncio.sleep(25)
        spike = random.choice(test_spikes)
        test_token = type('Token', (), {
            'mint': f"test_{random.randint(1,9999)}",
            'symbol': spike["symbol"],
            'name': spike["name"],
            'price_sol': spike["price"],
            'spike_pct': spike["spike"]
        })
        push_to_web(test_token, "spike")
        print(f"[test] Generated test spike: {spike['symbol']} +{spike['spike']}%")

@app.on_event("startup")
async def startup_event():
    """Start test spike generator on startup"""
    asyncio.create_task(generate_test_spikes())

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the dashboard"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>No-Brain-Trade Pro</title>
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
            .header h1 { font-size: 1.8rem; margin-bottom: 10px; }
            .header p { color: #888; font-size: 0.9rem; }
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
                transition: all 0.3s;
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
            .token-symbol {
                font-size: 1.2rem;
                font-weight: bold;
                display: inline-block;
            }
            .token-price {
                float: right;
                font-size: 0.9rem;
                color: #888;
            }
            .token-spike {
                color: #ff0000;
                font-weight: bold;
                margin-left: 10px;
                display: inline-block;
            }
            .token-time {
                font-size: 0.7rem;
                color: #444;
                margin-top: 5px;
            }
            .footer {
                text-align: center;
                padding: 20px;
                color: #666;
                font-size: 0.7rem;
                margin-top: 20px;
                border-top: 1px solid #222;
            }
            .status {
                position: fixed;
                bottom: 10px;
                right: 10px;
                background: #000;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 0.7rem;
                font-family: monospace;
            }
            .status.online { color: #00ff00; }
            .status.offline { color: #ff0000; }
            .clear-btn {
                background: #222;
                color: #fff;
                border: none;
                padding: 5px 10px;
                margin-left: 10px;
                cursor: pointer;
                border-radius: 3px;
                font-size: 0.7rem;
            }
            .clear-btn:hover { background: #333; }
            @media (max-width: 600px) {
                body { padding: 10px; }
                .token { padding: 10px; }
                .token-symbol { font-size: 1rem; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ NO-BRAIN-TRADE PRO ⚡</h1>
            <p>Real-time pump.fun spike detection | 150%+ alerts | Test mode active</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="spikeCount">0</div>
                <div class="stat-label">SPIKES TODAY</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="tokenCount">0</div>
                <div class="stat-label">TOKENS</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="highestSpike">0%</div>
                <div class="stat-label">HIGHEST SPIKE</div>
            </div>
        </div>
        
        <div class="token-list" id="tokens">
            <div style="text-align: center; color: #666; padding: 40px;">
                ⏳ Waiting for spikes... Test spikes every 25 seconds
            </div>
        </div>
        
        <div class="footer">
            🔥 Free alerts | 🤖 Pro AI analysis | 💰 Non-custodial auto-trading | 📊 Test data active
        </div>
        
        <div class="status online" id="status">
            🟢 CONNECTED
        </div>
        
        <script>
            let spikeCount = 0;
            let tokenCount = 0;
            let highestSpike = 0;
            let reconnectAttempts = 0;
            let eventSource = null;
            
            function connect() {
                if (eventSource) eventSource.close();
                
                eventSource = new EventSource('/events');
                
                eventSource.onopen = () => {
                    document.getElementById('status').innerHTML = '🟢 CONNECTED';
                    document.getElementById('status').className = 'status online';
                    reconnectAttempts = 0;
                };
                
                eventSource.onerror = () => {
                    document.getElementById('status').innerHTML = '🔴 RECONNECTING...';
                    document.getElementById('status').className = 'status offline';
                    reconnectAttempts++;
                    setTimeout(connect, Math.min(5000, reconnectAttempts * 1000));
                };
                
                eventSource.addEventListener('spike', (e) => {
                    const token = JSON.parse(e.data);
                    addToken(token, true);
                    spikeCount++;
                    document.getElementById('spikeCount').innerHTML = spikeCount;
                    if (token.spike_pct > highestSpike) {
                        highestSpike = token.spike_pct;
                        document.getElementById('highestSpike').innerHTML = Math.round(highestSpike) + '%';
                    }
                });
                
                eventSource.addEventListener('token', (e) => {
                    const token = JSON.parse(e.data);
                    addToken(token, false);
                    tokenCount++;
                    document.getElementById('tokenCount').innerHTML = tokenCount;
                });
                
                eventSource.addEventListener('ping', () => {});
            }
            
            function addToken(token, isSpike) {
                const container = document.getElementById('tokens');
                const tokenDiv = document.createElement('div');
                tokenDiv.className = isSpike ? 'token spike' : 'token';
                
                const spikeHtml = isSpike ? `<span class="token-spike">🚀 +${Math.round(token.spike_pct || 0)}%</span>` : '';
                const price = (token.price_sol || 0).toFixed(8);
                const time = new Date().toLocaleTimeString();
                const symbol = token.symbol || '???';
                const name = token.name || '';
                
                tokenDiv.innerHTML = `
                    <div>
                        <span class="token-symbol">${symbol}</span>
                        ${spikeHtml}
                        <span class="token-price">💰 ${price} SOL</span>
                    </div>
                    <div class="token-time">🕐 ${time}</div>
                `;
                
                container.prepend(tokenDiv);
                
                // Keep only last 50
                while (container.children.length > 50) {
                    container.removeChild(container.lastChild);
                }
                
                // Play notification sound effect (vibrate on mobile)
                if (isSpike && navigator.vibrate) {
                    navigator.vibrate(200);
                }
            }
            
            function clearTokens() {
                document.getElementById('tokens').innerHTML = '';
                spikeCount = 0;
                tokenCount = 0;
                highestSpike = 0;
                document.getElementById('spikeCount').innerHTML = '0';
                document.getElementById('tokenCount').innerHTML = '0';
                document.getElementById('highestSpike').innerHTML = '0%';
            }
            
            // Start connection
            connect();
            
            // Auto-refresh connection every 5 minutes
            setInterval(() => {
                if (eventSource) {
                    eventSource.close();
                    connect();
                }
            }, 300000);
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
        "test_mode": True
    }

@app.get("/api/stats")
async def stats():
    """Get service statistics"""
    spikes = [t for t in recent_tokens if t.get('spike_pct', 0) > 150]
    return {
        "total_tokens": len(recent_tokens),
        "total_spikes": len(spikes),
        "highest_spike": max([t.get('spike_pct', 0) for t in recent_tokens]) if recent_tokens else 0,
        "queue_size": token_queue.qsize()
    }
