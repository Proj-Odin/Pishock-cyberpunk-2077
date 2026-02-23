import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, provided_signature: str) -> bool:
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, provided_signature)
