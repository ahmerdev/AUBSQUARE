"""Decimal-safe money helpers. Never use float for money."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# code -> (name, symbol, decimals). Add a currency here and it can be enabled in Company billing settings.
CURRENCIES = {
    "PKR": ("Pakistani rupee", "Rs", 2), "USD": ("US dollar", "$", 2), "GBP": ("Pound sterling", "£", 2), "EUR": ("Euro", "€", 2),
    "AED": ("UAE dirham", "AED", 2), "SAR": ("Saudi riyal", "SAR", 2), "CAD": ("Canadian dollar", "CA$", 2), "AUD": ("Australian dollar", "A$", 2),
    "JPY": ("Japanese yen", "¥", 0), "KWD": ("Kuwaiti dinar", "KD", 3), "BHD": ("Bahraini dinar", "BD", 3),
}
DEFAULT_ENABLED = "USD,PKR,GBP,EUR,AED,SAR,CAD"
MAX_AMOUNT = Decimal("999999999.99")


def decimals(cur: str) -> int:
    return CURRENCIES.get((cur or "").upper(), ("", "", 2))[2]


def to_dec(v, default="0") -> Decimal:
    """Parse user input safely: strips thousands separators, rejects NaN/Infinity, never raises."""
    try:
        d = Decimal(str(v).replace(",", "").strip() or default)
    except (InvalidOperation, ValueError):
        return Decimal(default)
    return d if d.is_finite() else Decimal(default)


def q(amount, cur="USD") -> Decimal:
    """Round to the currency's precision (half-up, as accountants expect)."""
    exp = Decimal(1).scaleb(-decimals(cur))
    return to_dec(amount).quantize(exp, rounding=ROUND_HALF_UP)


def minor_units(amount, cur) -> int:
    """Amount in the provider's smallest unit (cents, fils...)."""
    return int(q(amount, cur).scaleb(decimals(cur)))


def from_minor(units, cur) -> Decimal:
    return q(Decimal(int(units)).scaleb(-decimals(cur)), cur)


def fmt(amount, cur="USD") -> str:
    cur = (cur or "USD").upper()
    d = decimals(cur)
    return f"{cur} {q(amount, cur):,.{d}f}"
