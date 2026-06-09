import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


class EncryptionError(Exception):
    pass


def _load_key() -> bytes:
    key_hex = get_settings().API_ENCRYPTION_KEY.strip()
    key = bytes.fromhex(key_hex)
    if len(key) != 32:
        raise ValueError("API_ENCRYPTION_KEY must be a 64-character hex string representing 32 bytes")
    return key


_aesgcm: AESGCM | None = None


def get_aesgcm() -> AESGCM:
    global _aesgcm
    if _aesgcm is None:
        _aesgcm = AESGCM(_load_key())
    return _aesgcm


def encrypt_payload(data: Any) -> dict[str, str]:
    plaintext = json.dumps(data, default=str).encode("utf-8")
    nonce = os.urandom(12)
    ct_with_tag = get_aesgcm().encrypt(nonce, plaintext, None)
    ciphertext = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]
    return {
        "iv": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }


def decrypt_payload(envelope: dict[str, str]) -> Any:
    try:
        nonce = base64.b64decode(envelope["iv"])
        ciphertext = base64.b64decode(envelope["ciphertext"])
        tag = base64.b64decode(envelope["tag"])
        ct_with_tag = ciphertext + tag
        plaintext = get_aesgcm().decrypt(nonce, ct_with_tag, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise EncryptionError("Invalid encrypted payload") from exc
