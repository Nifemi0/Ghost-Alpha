# Production Deployment Guide

## 1. Install Systemd Services

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable polybot-api.service
sudo systemctl enable polybot-insider.timer

# Start services
sudo systemctl start polybot-api.service
sudo systemctl start polybot-insider.timer
```

## 2. Configure Environment

```bash
# Set Discord webhook (required for alerts)
sudo systemctl edit polybot-api.service
# Add under [Service]:
# Environment="DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_URL"

sudo systemctl edit polybot-insider.service
# Add same Discord webhook

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart polybot-api.service
sudo systemctl restart polybot-insider.timer
```

## 3. Verify Services

```bash
# Check API status
sudo systemctl status polybot-api.service
curl http://localhost:8000/health

# Check insider detection
sudo systemctl status polybot-insider.timer
sudo systemctl list-timers | grep polybot

# View logs
sudo journalctl -u polybot-api.service -f
sudo journalctl -u polybot-insider.service -f
```

## 4. Run Tests

```bash
# Full test suite
python3 tests/test_suite.py

# Expected output:
# ✅ Passed: 8
# ❌ Failed: 0
# 🎉 ALL TESTS PASSED!
```

## 5. Monitoring

**Health Check**:
```bash
curl http://localhost:8000/health
```

**Metrics**:
```bash
curl http://localhost:8000/metrics
```

**Logs**:
```bash
tail -f /var/log/polybot-api.log
tail -f /var/log/polybot-insider.log
```

## 6. Maintenance

**Restart API**:
```bash
sudo systemctl restart polybot-api.service
```

**Manually trigger detection**:
```bash
sudo systemctl start polybot-insider.service
```

**Stop all services**:
```bash
sudo systemctl stop polybot-api.service
sudo systemctl stop polybot-insider.timer
```

## 7. Troubleshooting

**API won't start**:
- Check logs: `sudo journalctl -u polybot-api.service -n 50`
- Verify port 8000 is free: `sudo lsof -i :8000`
- Test manually: `python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

**No insider alerts**:
- Check Discord webhook is set: `sudo systemctl show polybot-insider.service | grep DISCORD`
- Verify timer is active: `sudo systemctl status polybot-insider.timer`
- Run manually: `python3 app/insider_detection.py`

**Database issues**:
- Check permissions: `ls -la poly.db`
- Verify schema: `sqlite3 poly.db ".schema"`
- Run backfill: `python3 data/backfill_simple.py`
