
import json
import secrets
import hashlib
import hmac

from pathlib import Path
from cryptography.fernet import Fernet


BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / ".pipeline_keys.json"


def load_keys():
    """
    Load existing encryption keys.
    Generate and save them if they don't exist.
    """

    if KEY_FILE.exists():
        with open(KEY_FILE, "r", encoding="utf-8") as file:
            keys = json.load(file)

    else:
        keys = {
            "encryption_key": Fernet.generate_key().decode("utf-8"),
            "hmac_key": secrets.token_hex(32)
        }

        with open(KEY_FILE, "w", encoding="utf-8") as file:
            json.dump(keys, file)

    return keys


KEYS = load_keys()

FERNET = Fernet(
    KEYS["encryption_key"].encode("utf-8")
)

HMAC_KEY = bytes.fromhex(KEYS["hmac_key"])


def encrypt_value(value):
    """
    Encrypt a value before storing it in SQLite.
    """

    if value is None:
        return None

    encrypted = FERNET.encrypt(
        str(value).encode("utf-8")
    )

    return encrypted


def decrypt_value(encrypted_value):
    """
    Decrypt an encrypted value when needed.
    """

    if encrypted_value is None:
        return None

    decrypted = FERNET.decrypt(encrypted_value)

    return decrypted.decode("utf-8")


def create_phone_hash(phone):
    """
    Create a deterministic HMAC fingerprint
    from a canonical phone number.
    """

    if phone is None:
        return None

    fingerprint = hmac.new(
        HMAC_KEY,
        phone.encode("utf-8"),
        hashlib.sha256
    )

    return fingerprint.hexdigest()
