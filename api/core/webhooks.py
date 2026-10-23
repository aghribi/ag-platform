import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)


class WebhookURLError(ValueError):
    pass


def _check_url(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise WebhookURLError("webhook_url must be an https URL")
    if parts.username or parts.password:
        raise WebhookURLError("webhook_url must not contain credentials")
    return parts.hostname, parts.port or 443


async def _resolve_public(host: str, port: int) -> str:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addrs = {info[4][0] for info in infos}
    if not addrs:
        raise WebhookURLError("webhook_url host does not resolve")
    for a in addrs:
        if not ipaddress.ip_address(a).is_global:
            raise WebhookURLError("webhook_url must resolve to public addresses only")
    return sorted(addrs)[0]


async def validate_webhook_url(url: str) -> None:
    host, port = _check_url(url)
    await _resolve_public(host, port)


async def post_webhook(url: str, payload: dict) -> None:
    """POST to a user-supplied URL without reaching internal addresses.

    The connection goes to the IP checked here, with the original name kept for
    the Host header and TLS (SNI and certificate check), so DNS cannot be
    rebound between the check and the request. Redirects are not followed.
    """
    try:
        host, port = _check_url(url)
        ip = await _resolve_public(host, port)
    except (WebhookURLError, OSError) as exc:
        logger.warning("Webhook to %s refused: %s", url, exc)
        return
    parts = urlsplit(url)
    netloc = f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"
    target = urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))
    host_header = host if port == 443 else f"{host}:{port}"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            await client.post(
                target,
                json=payload,
                headers={"Host": host_header},
                extensions={"sni_hostname": host},
            )
    except httpx.HTTPError as exc:
        logger.warning("Webhook to %s failed: %s", url, exc)
