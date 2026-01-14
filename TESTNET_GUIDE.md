# 👻 GHOST ALPHA CAPTURE - Testnet Guide

## 🎯 What Is This?

**Ghost Alpha Capture** is a high-frequency trading simulation engine. It is designed to capture **micro-inefficiencies** between the Binance BTC Spot market and Polymarket’s prediction markets.

While many bots claim "Latency Arbitrage," this engine specifically targets **Statistical Alpha** during periods of high price volatility.

Users get **$1,000 virtual funds** to monitor the engine's performance in real-time.

---

## �️ Ghost Shield: Safety Engines

To handle the "Bad" parts of high-frequency trading (noise, slippage, and whipsaws), we've implemented the **Ghost Shield**:

### 1. **Entropy Monitor (Noise Filter)**
- The engine tracks signal density.
- If the market becomes "noisy" (>5 spikes in 60s), the system **Freezes** to protect your balance from chaotic volatility.
- Trading resumes automatically once the market stabilizes (ENTROPY < Threshold).

### 2. **ML Confidence Gating**
- Every trade signal is cross-referenced with a confidence score.
- The engine only executes if **Confidence > 75%**, effectively ignoring low-probability signals that often lead to slippage losses.

### 3. **Drawdown Guard**
- If your account balance drops more than **5% from its peak**, the system pauses your trading automatically to prevent catastrophic loss.

---

## 📋 Features Available for Testing

### 1. **Alpha Capture Engine**
- **Micro-Inefficiency Detection**: Triggers when Binance moves significantly faster than Polymarket.
- **Risk Modes (`/strategy`)**: Toggle between Conservative, Balanced, and Aggressive profiles.
- **Decoupled Analytics**: Multi-timeline simulations (3s, 7s, 15s) are logged separately to ensure zero-latency execution for the live trader.

### 2. **Dynamic UI (`/balance`)**
- Monitor your performance with one command.
- Real-time progress bars for Drawdown and ROI.
- **One-Tap Refresh**: Update your wallet without re-typing commands.

### 3. **Social & History**
- **`/leaderboard`**: Compete with other testnet "Hunters" for the top ROI spot.
- **`/history`**: Audit your last 10 trades to see exactly how the engine performed.

### 4. **Auto-Rollover**
- The engine automatically finds and follows the new Bitcoin market daily.

---

## 🧪 How to Test

### **Step 1: Join the Bot**
1. Search for: `@YourBotUsername`
2. Send `/start` to receive your $1,000 virtual credit.

### **Step 2: Set Your Strategy**
- Send `/strategy` and pick your risk level.
  - 🐢 **Conservative**: Low exposure (15%), safe targets.
  - ⚖️ **Balanced**: Standard exposure (35%).
  - 🚀 **Aggressive**: High exposure (50%), hunting larger swings.

### **Step 3: Monitor Trades**
- The bot will ping you **twice** per trade:
  - ⚡ **Signal Detected**: When it enters a position.
  - ✨ **Trade Settled**: Final P/L, Exit Reason, and New Balance.

---

## � Expected Behavior

### ✅ **Optimal Performance:**
- "WINNER" settlements during clear Binance trends.
- "FROZEN" status during chaotic market news (system protection).
- Smooth balance updates in `/balance`.

### ⚠️ **Known Realities (The "Ghost" Truth):**
- **Statistical Arb**: We don't bet on "winning" every trade; we bet on the statistical probability of the gap closing.
- **Execution Bottlenecks**: Polymarket is slower than Binance. Our engine accounts for this with staggered exits.
- **Paper Trading**: Not real money. This environment tests logic, not liquidity.

---

## 🚀 Roadmap (Beyond Testnet)

1. **duckDB Integration**: For massive-scale trade analytics.
2. **Privilege Separation**: Moving API keys to a dedicated secrets manager.
3. **Regime Detection V3**: Deep Learning based market state classification (Bull/Bear/Sideways/Chaos).

**Happy Hunting!** 👻📉�
