import hashlib
import secrets

TOKEN_BYTES = 32


def generate_auth_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_auth_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
