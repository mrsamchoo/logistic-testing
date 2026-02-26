import os
import json
import base64
from cryptography.fernet import Fernet

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = os.environ.get("ENCRYPTION_KEY")
        if not key:
            # Auto-generate for dev; store in .env for persistence
            key = Fernet.generate_key().decode()
            os.environ["ENCRYPTION_KEY"] = key
            print(f"[DEV] Auto-generated ENCRYPTION_KEY (add to .env for persistence)")
        # Accept both url-safe base64 and raw strings
        try:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            # If key isn't valid Fernet key, derive one from it
            padded = base64.urlsafe_b64encode(key.encode().ljust(32, b"\0")[:32])
            _fernet = Fernet(padded)
    return _fernet


def encrypt_json(data: dict) -> str:
    """Encrypt a dict to a Fernet-encrypted string."""
    plaintext = json.dumps(data).encode("utf-8")
    return _get_fernet().encrypt(plaintext).decode("utf-8")


def decrypt_json(encrypted: str) -> dict:
    """Decrypt a Fernet-encrypted string back to a dict."""
    plaintext = _get_fernet().decrypt(encrypted.encode("utf-8"))
    return json.loads(plaintext.decode("utf-8"))


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret string, showing only the last N chars."""
    if not value or len(value) <= show_chars:
        return "****"
    return "*" * 8 + value[-show_chars:]
