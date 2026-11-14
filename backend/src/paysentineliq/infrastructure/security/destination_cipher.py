import base64
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_PREFIX = "v1:"
_SALT = b"paysentineliq-notification-destination-v1"
_INFO = b"notification-destination"


class DestinationCipher:
    def __init__(self, secret: str) -> None:
        if not secret.strip():
            raise ValueError("destination cipher secret is required")
        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_SALT,
            info=_INFO,
        ).derive(secret.encode("utf-8"))
        self._cipher = AESGCM(key)

    def encrypt(self, value: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), _INFO)
        token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{_PREFIX}{token}"

    def decrypt(self, token: str) -> str:
        if not token.startswith(_PREFIX):
            raise ValueError("destination token has an unknown version")
        encoded = token[len(_PREFIX) :]
        try:
            raw = base64.urlsafe_b64decode(encoded)
        except ValueError as error:
            raise ValueError("destination token is invalid") from error
        if len(raw) <= 12:
            raise ValueError("destination token is invalid")
        try:
            plaintext = self._cipher.decrypt(raw[:12], raw[12:], _INFO)
        except Exception as error:
            raise ValueError("destination token cannot be decrypted") from error
        return plaintext.decode("utf-8")
