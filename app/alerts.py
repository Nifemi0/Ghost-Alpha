"""
Alert system for insider detection
Sends notifications via Discord webhooks
"""
import requests
import os
from datetime import datetime

# Discord webhook URL (set via environment variable)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

def send_discord_alert(insider):
    """
    Send insider alert to Discord
    
    Args:
        insider: dict with keys: wallet, wallet_age_hours, market_count, market_id, trade_size, trade_price
    """
    if not DISCORD_WEBHOOK_URL:
        print("Warning: DISCORD_WEBHOOK_URL not set - skipping Discord alert")
        return False
    
    # Format wallet address (truncate for readability)
    wallet_short = f"{insider['wallet'][:6]}...{insider['wallet'][-4:]}"
    
    # Build embed
    embed = {
        "title": "🚨 Fresh Wallet Insider Alert",
        "color": 0xFF4500,  # Orange-red
        "fields": [
            {
                "name": "Wallet",
                "value": f"`{wallet_short}`",
                "inline": True
            },
            {
                "name": "Age",
                "value": f"{insider['wallet_age_hours']:.1f}h",
                "inline": True
            },
            {
                "name": "Markets",
                "value": str(insider['market_count']),
                "inline": True
            },
            {
                "name": "Market ID",
                "value": f"`{insider['market_id']}`",
                "inline": False
            },
            {
                "name": "Trade Size",
                "value": f"${insider['trade_size']:.2f}",
                "inline": True
            },
            {
                "name": "Price",
                "value": f"{insider['trade_price']:.3f}",
                "inline": True
            }
        ],
        "footer": {
            "text": f"Detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    }
    
    payload = {
        "embeds": [embed]
    }
    
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code in [200, 204]:
            return True
        else:
            print(f"Discord webhook failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"Error sending Discord alert: {e}")
        return False

def send_batch_summary(insiders):
    """
    Send a summary of multiple insider alerts
    
    Args:
        insiders: list of insider dicts
    """
    if not DISCORD_WEBHOOK_URL or not insiders:
        return False
    
    count = len(insiders)
    avg_age = sum(i['wallet_age_hours'] for i in insiders) / count
    
    # Build summary message
    summary_lines = [f"**{count} Fresh Wallet Insiders Detected**", ""]
    
    for i, insider in enumerate(insiders[:5], 1):  # Show first 5
        wallet_short = f"{insider['wallet'][:6]}...{insider['wallet'][-4:]}"
        summary_lines.append(
            f"{i}. `{wallet_short}` - {insider['wallet_age_hours']:.1f}h old, {insider['market_count']} markets"
        )
    
    if count > 5:
        summary_lines.append(f"\n*...and {count - 5} more*")
    
    summary_lines.append(f"\n📊 Average wallet age: {avg_age:.1f}h")
    
    payload = {
        "content": "\n".join(summary_lines)
    }
    
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        return resp.status_code in [200, 204]
    except Exception as e:
        print(f"Error sending batch summary: {e}")
        return False

if __name__ == "__main__":
    # Test alert
    test_insider = {
        "wallet": "0xabc123def456789012345678901234567890abcd",
        "wallet_age_hours": 12.5,
        "market_count": 2,
        "market_id": "12345",
        "trade_size": 500,
        "trade_price": 0.65
    }
    
    print("Testing Discord alert...")
    if DISCORD_WEBHOOK_URL:
        success = send_discord_alert(test_insider)
        print(f"Alert sent: {success}")
    else:
        print("Set DISCORD_WEBHOOK_URL environment variable to test")
