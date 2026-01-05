# Quick Start Guide: Discord Alerting

## Setup

1. **Create Discord Webhook**
   - Open Discord server settings
   - Go to Integrations → Webhooks
   - Click "New Webhook"
   - Copy the webhook URL

2. **Set Environment Variable**
   ```bash
   export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
   ```

3. **Test Alert**
   ```bash
   python3 app/alerts.py
   ```

## Running Insider Detection with Alerts

```bash
# One-time run
python3 app/insider_detection.py

# Schedule with cron (every 5 minutes)
crontab -e
# Add: */5 * * * * cd /root/.gemini/antigravity/scratch/poly && python3 app/insider_detection.py >> /var/log/insider.log 2>&1
```

## Alert Types

- **Batch Summary**: Sent for all detected insiders
- **Individual Alerts**: Sent for trades > $1000

## Example Alert

```
🚨 Fresh Wallet Insider Alert
Wallet: 0xabc1...abcd
Age: 12.5h
Markets: 2
Market ID: 12345
Trade Size: $500.00
Price: 0.650
```
