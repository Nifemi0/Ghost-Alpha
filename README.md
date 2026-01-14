# 👻 GHOST ALPHA CAPTURE - V3.0 "FLUX CAPACITOR"

> **"Where we're going, we don't need distinct Token IDs."**

Ghost Alpha Capture is an ultra-low-latency HFT bot designed for **Polymarket** binary options, specifically targeting microstructure inefficiencies in highly liquid markets (e.g., "Bitcoin Daily Price").

---

## 🚀 New Features (V3.0)

### 1. 🐌 Flux Capacitor (Auto-Slug Market Discovery)
Legacy bots break when Polymarket rolls over to a new daily market ID.
**Ghost V3** uses a deterministic prediction engine:
- **Predicts** tomorrow's market slug (e.g., `bitcoin-up-or-down-on-january-16`).
- **Resolves** the Slug to the correct CLOB Token ID automatically.
- **Micro-Rollover:** Seamlessly switches targets without restart or manual intervention.

### 2. 🛡️ Depth Charge (Liquidity Protection)
Before firing a trade, the bot performs a **Flash Calculation** of the order book depth.
- If the trade size would cause >0.5% slippage, the trade is aborted (`Zero Slippage Protocol`).
- Prevents "Ghost Trades" that execute at unfavorable average prices.

### 3. 🧠 Neural Brain (Heuristic Tuning)
- **Random Forest Classifier** trained on high-velocity moves.
- Tuned for "Admin Mode" Aggression (0.008% Volatility Threshold).
- Rejects "Fake Outs" (High Move, Low Velocity).

### 4. 📈 Reverse Equity Reconstruction
- The Dashboard (`/balance`) now mathematically reconstructs your Equity Curve in reverse from your specific wallet balance.
- 100% Accuracy even after manual deposits/withdrawals.

---

## 🛠️ Installation

```bash
# 1. Clone
git clone https://github.com/your-repo/ghost-alpha-poly.git
cd ghost-alpha-poly

# 2. Setup Env
python3 -m venv poly_venv
source poly_venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your POLY_API_KEY and TELEGRAM_TOKEN
```

## 🎮 Usage

**Start the Engine:**
```bash
sudo systemctl start poly-unified-bot
```

**Telegram Commands:**
- `/balance`: View real-time equity curve (Cyberpunk Dark Mode).
- `/status`: Check Engine Heartbeat & Market Target.
- `/reset`: Emergency Drawdown Reset (Use with caution).

---

## ⚠️ Risk Warning
This bot executes trades in milliseconds.
**Past performance (+$521 in 48h) does not guarantee future results.**
Use "Paper Mode" (Observer) first.

---

*Verified Production Grade. Clean Code Architecture.*
