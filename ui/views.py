
def signal_alert(mode_label, mode_name, gap, confidence, entry, slots, conf_emoji):
    return (
        f"⚡ *GHOST SIGNAL DETECTED*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 **Mode:** {mode_label} `{mode_name.upper()}`\n"
        f"📊 **Binance Gap:** `{gap*100:.4f}%` 🔥\n"
        f"🧠 **Brain Confidence:** {conf_emoji} `{confidence*100:.1f}%`\n"
        f"📥 **Entry:** `${entry:.4f}`\n"
        f"🌀 **Action:** Opening `{slots}` concurrent positions."
    )

def welcome_msg(username, balance):
    return (
        f"👻 *WELCOME TO THE ALPHA PACK, {username.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"The Dual Engine is successfully targeting price micro-inefficiencies between Binance and Polymarket.\n\n"
        f"💰 **Virtual Wallet Assets**: `${balance:.2f}`\n\n"
        f"Use /balance to check your ROI or /strategy to shift your hunting style at any time."
    )
