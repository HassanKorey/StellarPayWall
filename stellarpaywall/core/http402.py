from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
import time
from typing import Any, Callable, Mapping
import uuid

DEFAULT_MERCHANT_DESTINATION = "merchant_address"
DEFAULT_CHALLENGE_TTL_SECONDS = 300

BASE_ENDPOINT_PRICES: dict[str, str] = {
    "/protected-resource": "0.05",
    "/verify-payment": "0.01",
    "/api/v1/generate": "0.05",
    "/api/v1/search": "0.02",
    "/api/v1/analyze": "0.10",
    "/api/v1/embed": "0.01",
}

DEFAULT_ASSET_RATES_IN_XLM: dict[str, Decimal] = {
    "XLM": Decimal("1.0"),
    "USDC": Decimal("0.20"),
}

SUPPORTED_SCHEMES = ("Stellar", "x402", "L402")
SUPPORTED_ASSETS = ("XLM", "USDC")


@dataclass(frozen=True)
class RoutePaywallConfig:
    """Per-route paywall pricing and protocol configuration."""

    price: str
    asset: str = "XLM"
    scheme: str = "Stellar"
    expires_in: int = DEFAULT_CHALLENGE_TTL_SECONDS
    token_rate_per_1k: str = "0.01"
    depth_step_price: str = "0.01"
    row_rate_per_100: str = "0.005"


@dataclass(frozen=True)
class ProtocolNegotiationResult:
    """Result of HTTP 402 protocol and asset negotiation."""

    scheme: str
    asset: str
    expires_in: int


_ROUTE_PAYWALL_REGISTRY: dict[str, RoutePaywallConfig] = {}
_CHALLENGE_EXPIRATIONS: dict[str, int] = {}


def paywall(
    price: str | float | Decimal = "0.05",
    *,
    asset: str = "XLM",
    scheme: str = "Stellar",
    expires_in: int = DEFAULT_CHALLENGE_TTL_SECONDS,
    path: str | None = None,
    token_rate_per_1k: str = "0.01",
    depth_step_price: str = "0.01",
    row_rate_per_100: str = "0.005",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to configure custom HTTP 402 pricing, asset, and TTL per route.

    Example:
        @router.get("/protected-resource")
        @paywall(price="0.05", asset="XLM")
        async def protected_resource():
            ...
    """
    normalized_price = _format_decimal(Decimal(str(price)))
    config = RoutePaywallConfig(
        price=normalized_price,
        asset=asset.upper(),
        scheme=scheme,
        expires_in=expires_in,
        token_rate_per_1k=token_rate_per_1k,
        depth_step_price=depth_step_price,
        row_rate_per_100=row_rate_per_100,
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "__paywall_config__", config)
        route_key = path or f"/{func.__name__.replace('_', '-')}"
        _ROUTE_PAYWALL_REGISTRY[route_key] = config

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        import inspect

        wrapper = async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        setattr(wrapper, "__paywall_config__", config)
        return wrapper

    return decorator


def register_route_paywall(path: str, config: RoutePaywallConfig) -> None:
    """Register or override a route's paywall configuration."""
    _ROUTE_PAYWALL_REGISTRY[path] = config


def get_route_paywall_config(endpoint: str) -> RoutePaywallConfig | None:
    """Retrieve a registered RoutePaywallConfig for the given endpoint."""
    return _ROUTE_PAYWALL_REGISTRY.get(endpoint)


def clear_paywall_registry() -> None:
    """Clear dynamic route registrations (useful in tests)."""
    _ROUTE_PAYWALL_REGISTRY.clear()


def _format_decimal(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    text = format(quantized.normalize(), "f")
    if "." not in text:
        return f"{text}.00"
    integer_part, frac_part = text.split(".", 1)
    if len(frac_part) < 2:
        frac_part = frac_part.ljust(2, "0")
    return f"{integer_part}.{frac_part}"


def convert_asset_amount(
    amount_xlm: str | Decimal,
    target_asset: str = "XLM",
    exchange_rates: Mapping[str, Decimal] | None = None,
) -> str:
    """Convert an XLM base amount into the target asset."""
    rates = dict(DEFAULT_ASSET_RATES_IN_XLM)
    if exchange_rates:
        rates.update({k.upper(): Decimal(str(v)) for k, v in exchange_rates.items()})

    asset_key = target_asset.upper()
    rate = rates.get(asset_key, Decimal("1.0"))
    converted = Decimal(str(amount_xlm)) * rate
    return _format_decimal(converted)


def calculate_dynamic_price(
    endpoint: str,
    query_params: Mapping[str, Any] | None = None,
    payload_bytes: int = 0,
    asset: str | None = None,
    exchange_rates: Mapping[str, Decimal] | None = None,
) -> str:
    """
    Calculate dynamic pricing based on route decorator, endpoint base rate,
    query complexity (tokens, depth, rows), payload size, and target asset.
    """
    route_cfg = _ROUTE_PAYWALL_REGISTRY.get(endpoint)
    if route_cfg is not None:
        base = Decimal(route_cfg.price)
        token_rate = Decimal(route_cfg.token_rate_per_1k)
        depth_rate = Decimal(route_cfg.depth_step_price)
        row_rate = Decimal(route_cfg.row_rate_per_100)
        base_asset = route_cfg.asset
    else:
        base = Decimal(BASE_ENDPOINT_PRICES.get(endpoint, "0.05"))
        token_rate = Decimal("0.01")
        depth_rate = Decimal("0.01")
        row_rate = Decimal("0.005")
        base_asset = "XLM"

    surcharge = Decimal("0")
    if query_params:
        raw_tokens = query_params.get("tokens") or query_params.get("max_tokens")
        if raw_tokens is not None:
            try:
                tokens = max(0, int(raw_tokens))
                surcharge += (Decimal(tokens) / Decimal(1000)) * token_rate
            except (TypeError, ValueError):
                pass

        raw_depth = query_params.get("depth")
        if raw_depth is not None:
            try:
                depth = max(1, int(raw_depth))
                if depth > 1:
                    surcharge += Decimal(depth - 1) * depth_rate
            except (TypeError, ValueError):
                pass

        raw_rows = query_params.get("rows") or query_params.get("limit")
        if raw_rows is not None:
            try:
                rows = max(0, int(raw_rows))
                surcharge += (Decimal(rows) / Decimal(100)) * row_rate
            except (TypeError, ValueError):
                pass

    if payload_bytes > 0:
        surcharge += (Decimal(payload_bytes) / Decimal(10240)) * Decimal("0.005")

    total = base + surcharge
    target_asset = (asset or base_asset).upper()
    if target_asset != base_asset.upper():
        # Convert to XLM first if base_asset != XLM, then to target_asset
        rates = dict(DEFAULT_ASSET_RATES_IN_XLM)
        if exchange_rates:
            rates.update({k.upper(): Decimal(str(v)) for k, v in exchange_rates.items()})
        base_rate = rates.get(base_asset.upper(), Decimal("1.0"))
        in_xlm = total / base_rate if base_rate != 0 else total
        return convert_asset_amount(in_xlm, target_asset=target_asset, exchange_rates=rates)

    return _format_decimal(total)


def negotiate_payment_protocol(
    headers: Mapping[str, str] | None = None,
    route_config: RoutePaywallConfig | None = None,
) -> ProtocolNegotiationResult:
    """
    Negotiate the HTTP 402 payment protocol scheme and asset based on request headers
    (`Accept`, `Prefer`, `X-PayWall-Preferred-Asset`, `X-PayWall-Scheme`).
    """
    default_scheme = route_config.scheme if route_config else "Stellar"
    default_asset = route_config.asset if route_config else "XLM"
    default_ttl = route_config.expires_in if route_config else DEFAULT_CHALLENGE_TTL_SECONDS

    if not headers:
        return ProtocolNegotiationResult(
            scheme=default_scheme,
            asset=default_asset,
            expires_in=default_ttl,
        )

    lowered = {k.lower(): v for k, v in headers.items()}

    scheme = default_scheme
    explicit_scheme = lowered.get("x-paywall-scheme", "").strip()
    prefer_header = lowered.get("prefer", "")
    accept_header = lowered.get("accept", "")

    if explicit_scheme:
        for candidate in SUPPORTED_SCHEMES:
            if explicit_scheme.lower() == candidate.lower():
                scheme = candidate
                break
    elif "scheme=" in prefer_header.lower():
        for part in prefer_header.split(";"):
            part = part.strip()
            if part.lower().startswith("scheme="):
                val = part.split("=", 1)[1].strip('"').strip("'")
                for candidate in SUPPORTED_SCHEMES:
                    if val.lower() == candidate.lower():
                        scheme = candidate
                        break
    elif "application/vnd.x402+json" in accept_header.lower():
        scheme = "x402"
    elif "application/vnd.l402+json" in accept_header.lower():
        scheme = "L402"

    asset = default_asset
    explicit_asset = lowered.get("x-paywall-preferred-asset", "").strip().upper()
    if explicit_asset in SUPPORTED_ASSETS:
        asset = explicit_asset
    elif "asset=" in prefer_header.lower():
        for part in prefer_header.split(";"):
            part = part.strip()
            if part.lower().startswith("asset="):
                val = part.split("=", 1)[1].strip('"').strip("'").upper()
                if val in SUPPORTED_ASSETS:
                    asset = val
                    break

    return ProtocolNegotiationResult(
        scheme=scheme,
        asset=asset,
        expires_in=default_ttl,
    )


def register_challenge_ttl(
    challenge_uuid: str,
    expires_in: int = DEFAULT_CHALLENGE_TTL_SECONDS,
    now: int | None = None,
) -> int:
    """Record the expiration timestamp for a challenge UUID and return `expires_at`."""
    current_ts = int(time.time()) if now is None else int(now)
    expires_at = current_ts + max(1, int(expires_in))
    _CHALLENGE_EXPIRATIONS[challenge_uuid] = expires_at
    return expires_at


def is_challenge_expired(challenge_uuid: str | None, now: int | None = None) -> bool:
    """Return True if the challenge has a registered TTL that has already elapsed."""
    if not challenge_uuid:
        return False
    expires_at = _CHALLENGE_EXPIRATIONS.get(challenge_uuid)
    if expires_at is None:
        return False
    current_ts = int(time.time()) if now is None else int(now)
    return current_ts > expires_at


def clear_challenge_ttl_registry() -> None:
    """Clear registered challenge expiration timestamps."""
    _CHALLENGE_EXPIRATIONS.clear()


def generate_402_header(
    asset: str = "XLM",
    amount: str = "0.05",
    destination: str = DEFAULT_MERCHANT_DESTINATION,
    challenge_uuid: str | None = None,
    scheme: str = "Stellar",
    expires_in: int = DEFAULT_CHALLENGE_TTL_SECONDS,
    now: int | None = None,
) -> dict[str, str]:
    if not challenge_uuid:
        challenge_uuid = str(uuid.uuid4())

    expires_at = register_challenge_ttl(challenge_uuid, expires_in=expires_in, now=now)

    return {
        "WWW-Authenticate": (
            f'{scheme} asset="{asset}", amount="{amount}", '
            f'destination="{destination}", challenge="{challenge_uuid}"'
        ),
        "X-PayWall-Amount": str(amount),
        "X-PayWall-Asset": str(asset),
        "X-PayWall-Destination": str(destination),
        "X-PayWall-Challenge-UUID": str(challenge_uuid),
        "X-PayWall-Scheme": str(scheme),
        "X-PayWall-Expires-In": str(expires_in),
        "X-PayWall-Expires-At": str(expires_at),
    }
