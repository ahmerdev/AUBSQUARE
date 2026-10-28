from dataclasses import dataclass, field


class GatewayError(Exception):
    """Raised with a message that is safe to show to staff (never contains secrets)."""


@dataclass
class WebhookResult:
    event_id: str
    event_type: str
    action: str = "ignore"            # paid | failed | cancelled | refunded | ignore
    payment_id: int | None = None
    session_id: str = ""
    txn_id: str = ""
    amount_minor: int | None = None
    currency: str = ""
    refund_id: str = ""
    refund_minor: int | None = None
    reason: str = ""
    raw: dict = field(default_factory=dict)


class Gateway:
    provider = ""
    label = ""

    def __init__(self, method):
        self.method = method

    def configured(self) -> bool:
        raise NotImplementedError

    def missing(self) -> list:
        """Names of environment variables that still need to be set."""
        return []

    def create_checkout(self, invoice, payment, success_url, cancel_url) -> str:
        raise NotImplementedError

    def verify_and_parse(self, body: bytes, headers) -> WebhookResult:
        """Validate the signature and return a normalised event. Raise GatewayError when invalid."""
        raise NotImplementedError

    def refund(self, payment, amount, reason="") -> dict:
        raise NotImplementedError
