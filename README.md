# NO-BRAIN-TRADE PRO ⚡

Real-time pump.fun intelligence platform. Free spike alerts + Pro AI analysis + non-custodial auto-trading.

## Architecture

```
pump.fun WS → Scanner → Spike Detector → DeepNet AI
                                              ↓
                                    ┌─────────────────┐
                                    │  Telegram Bot   │ ← Free users get basic alerts
                                    │  (alerts + pay) │ ← Pro users get full AI data
                                    └─────────────────┘
                                    ┌─────────────────┐
                                    │  Web Dashboard  │ ← Mobile-friendly live feed
                                    │  (FastAPI + SSE)│
                                    └─────────────────┘
                                    ┌─────────────────┐
                                    │  Auto-Trader    │ ← Pro: Jupiter swaps
                                    │  (non-custodial)│ ← Each user owns their wallet
                                    └─────────────────┘
                                    ┌─────────────────┐
                                    │   PostgreSQL    │ ← Users, subs, trades, wallets
                                    └─────────────────┘
```

## Deploy to Railway (from iPhone)

### Step 1 — Generate keys
```bash
python scripts/generate_keys.py
```
Copy the output — you'll need it for env vars.

### Step 2 — Set up Railway
1. Create new project on Railway
2. Add **PostgreSQL** plugin
3. Create a new service, connect your GitHub repo
4. Set all environment variables (see below)

### Step 3 — Environment variables

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `ADMIN_CHAT_ID` | Your Telegram chat ID |
| `TREASURY_WALLET` | Your Solana wallet (receives 0.5 SOL/month payments) |
| `DATABASE_URL` | Auto-filled by Railway Postgres plugin |
| `ENCRYPTION_KEY` | From generate_keys.py (NEVER change after deploy) |
| `SECRET_KEY` | From generate_keys.py |
| `HELIUS_API_KEY` | From helius.xyz |
| `BIRDEYE_API_KEY` | From birdeye.so |
| `PRO_PRICE_SOL` | `0.5` |
| `PORT` | `8080` |

### Step 4 — Deploy
Drag and drop the project folder to GitHub, Railway auto-deploys.

---

## User Flow

### Free users
1. `/start` the bot
2. Receive spike alerts (150%+) with basic data
3. Can upgrade to Pro anytime

### Pro users
1. `/menu` → Subscribe Pro
2. Send 0.5 SOL to treasury wallet
3. `/verify <TX_SIGNATURE>`
4. Pro activates — full AI alerts fire immediately
5. `/menu` → My Wallet — fund their auto-trade wallet
6. `/menu` → Auto-Trade — configure and enable

---

## Tiers

| Feature | Free | Pro |
|---------|------|-----|
| Spike alerts (150%+) | ✅ | ✅ |
| Basic token data | ✅ | ✅ |
| Full DeepNet AI analysis | ❌ | ✅ |
| Bundle/whale detection | ❌ | ✅ |
| Dev safety scoring | ❌ | ✅ |
| Auto-trade (Jupiter) | ❌ | ✅ |
| Take profit / stop loss | ❌ | ✅ |
| Web dashboard | ✅ | ✅ |

---

## Non-Custodial Wallet System

- Each Pro user gets a **dedicated Solana keypair** generated on first use
- The private key is encrypted with AES-256-GCM using `ENCRYPTION_KEY`
- Users can export their private key anytime → import to Phantom/Solflare
- You **never hold funds** — users fund their own wallet directly
- Auto-trades sign transactions server-side using the user's keypair

---

## Web Dashboard

Live at your Railway URL. Mobile-friendly. Shows:
- Real-time token feed
- Spike alerts (highlighted)
- Click any token → opens DexScreener

---

## Files

```
main.py                    # Entry point — runs everything
config.py                  # All settings from .env
Procfile                   # Railway deploy
railway.json               # Railway config

core/
  scanner.py               # pump.fun WebSocket
  spike_detector.py        # 150%+ spike logic
  trending_engine.py       # Token ranking
  autotrade.py             # Jupiter swap execution

deepnet_ai/
  analyzer.py              # Full AI pipeline

bot/
  handlers.py              # All Telegram commands + callbacks

web/
  app.py                   # FastAPI dashboard
  templates/index.html     # Mobile live feed UI

models/
  db.py                    # SQLAlchemy: users, subs, wallets, trades
  token.py                 # Pydantic token model

utils/
  subscription.py          # Sub management + payment verification
  wallet.py                # Keypair generation
  crypto.py                # AES-256 encryption
  rpc.py                   # Solana RPC
  birdeye.py               # Price/volume data

scripts/
  generate_keys.py         # One-time key generation
```
