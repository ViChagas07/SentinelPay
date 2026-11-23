from argon2 import PasswordHasher as Argon2PasswordHasherImpl
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from paysentineliq.application.ports.password_hasher import PasswordHasher

_DUMMY_PASSWORD = "sentinelpay-dummy-password-not-a-real-credential"


class Argon2PasswordHasher(PasswordHasher):
    def __init__(
        self,
        *,
        time_cost: int,
        memory_cost_kib: int,
        parallelism: int,
        hash_len: int,
        salt_len: int,
    ) -> None:
        self._hasher = Argon2PasswordHasherImpl(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash(_DUMMY_PASSWORD)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True

    def verify_dummy(self, password: str) -> None:
        try:
            self._hasher.verify(self._dummy_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return
