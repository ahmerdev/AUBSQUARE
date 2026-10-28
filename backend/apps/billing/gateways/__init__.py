"""Provider-independent payment layer. Each provider is one adapter class; nothing provider-specific lives outside this package."""
from .base import Gateway, GatewayError, WebhookResult  # noqa: F401


def get_gateway(method):
    """Adapter for a PaymentMethod row, or None when the provider has no online adapter (manual methods)."""
    from ..models import PaymentMethod
    if method is None:
        return None
    if method.kind == PaymentMethod.STRIPE:
        from .stripe import StripeGateway
        return StripeGateway(method)
    return None


def get_gateway_by_provider(provider):
    from ..models import PaymentMethod
    m = PaymentMethod.objects.filter(kind=provider).order_by("-is_enabled", "id").first()
    return get_gateway(m)
