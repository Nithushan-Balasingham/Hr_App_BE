"""Verify backend/frontend AES-GCM envelope compatibility."""
import json
import os

os.environ["API_ENCRYPTION_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

from app.core.encryption import decrypt_payload, encrypt_payload

sample = {"email": "admin@hrportal.local", "password": "Admin@123"}
envelope = encrypt_payload(sample)
roundtrip = decrypt_payload(envelope)
assert roundtrip == sample, roundtrip
print("Encryption roundtrip OK")
print(json.dumps(envelope))
