from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OIDCState:
    nonce: str
    code_verifier: str
    redirect_uri: str


class OIDCStateStore(Protocol):
    async def save(
        self,
        state: str,
        data: OIDCState,
        ttl_seconds: int,
    ) -> None: ...

    async def pop(self, state: str) -> OIDCState | None: ...
