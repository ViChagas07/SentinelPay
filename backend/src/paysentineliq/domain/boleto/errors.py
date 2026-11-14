from paysentineliq.domain.boleto.sources import MANUAL_FEBRABAN
from paysentineliq.domain.errors import DomainError


class NotVerifiableLayoutError(DomainError):
    def __init__(
        self,
        *,
        reason: str = "Boleto layout and check digits are not documented in the registered source.",
        source: str = MANUAL_FEBRABAN,
    ) -> None:
        super().__init__(
            code="boleto_layout_not_verifiable",
            message=reason,
            status_code=422,
            title="Not verifiable",
        )
        self.reason = reason
        self.source = source
