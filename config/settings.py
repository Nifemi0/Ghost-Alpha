
import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV = ["TELEGRAM_BOT_TOKEN", "GHOST_ENCRYPTION_KEY", "ADMIN_TELEGRAM_ID"]

def validate_env():
    for var in REQUIRED_ENV:
        if not os.getenv(var):
            raise ValueError(f"❌ Missing required environment variable: {var}")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ENCRYPTION_KEY = os.getenv("GHOST_ENCRYPTION_KEY")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
ADMIN_PASSWORD = os.getenv("GHOST_ADMIN_PASSWORD")
