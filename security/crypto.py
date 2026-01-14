
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

ENCRYPTION_KEY = os.getenv("GHOST_ENCRYPTION_KEY")

class GhostCrypto:
    def __init__(self, key=None):
        self.key = key or ENCRYPTION_KEY
        if not self.key:
            raise ValueError("❌ Missing GHOST_ENCRYPTION_KEY in environment")
        self.cipher = Fernet(self.key.encode())

    def encrypt(self, value):
        if value is None: return None
        return self.cipher.encrypt(str(value).encode())

    def decrypt(self, encrypted_value):
        if encrypted_value is None: return None
        try:
            return float(self.cipher.decrypt(encrypted_value).decode())
        except:
            return 0.0
