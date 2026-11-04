#!/usr/bin/env python3
"""Opt-in private transport for quotes ALREADY fetched by HENGCE FinMind vessel.

This is a *delivery adapter*, not a vendor client, second collector or mother.
Default: DISABLED. Enabled only when owner provisions a private HTTPS endpoint,
bearer token, signing secret, AND explicitly confirms permitted private use.
No price, credential, endpoint, or exception body is written to public logs.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any, Callable, Collection, Mapping

ALLOWED_HOST_BAD_SUFFIXES = (".github.io", ".githubusercontent.com")
MAX_BODY_BYTES = 2_000_000

class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _private_https_target(value: str) -> bool:
    try:
        url = urllib.parse.urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            return False
        if url.fragment or url.query or not url.path.startswith("/"):
            return False
        host = url.hostname.lower()
        if host in ("github.com", "api.github.com", "raw.githubusercontent.com", "localhost"):
            return False
        if host.endswith(ALLOWED_HOST_BAD_SUFFIXES):
            return False
        try:
            addr = ip_address(host)
            if not addr.is_global:
                return False
        except ValueError:
            pass
        return url.port in (None, 443)
    except (ValueError, TypeError):
        return False


def config_status(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    url = env.get("HENGCE_PRIVATE_QUOTE_ENDPOINT", "")
    token = env.get("HENGCE_PRIVATE_QUOTE_BEARER", "")
    signing_key = env.get("HENGCE_PRIVATE_QUOTE_HMAC_KEY", "")
    approval = env.get("HENGCE_PRIVATE_QUOTE_LICENSED_PRIVATE_USE_APPROVED", "")
    if not (url or token or signing_key or approval):
        return "NOT_CONFIGURED"
    if not url or not token or not signing_key:
        return "CONFIGURATION_INCOMPLETE"
    if not _private_https_target(url):
        return "REJECTED_NONPRIVATE_OR_INSECURE_ENDPOINT"
    if len(token) < 24 or len(signing_key) < 32:
        return "REJECTED_WEAK_PRIVATE_CREDENTIALS"
    if approval != "I_CONFIRM_AUTHORIZED_PRIVATE_USE":
        return "NOT_LICENSE_APPROVED"
    return "CONFIGURED"


def deliver(
    getter: Callable[[str], tuple[Any, str]],
    allowed_tickers: Collection[str],
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    opener: Any | None = None,
) -> dict[str, Any]:
    """Send only fresh, validated quote values to ONE owner-approved private HTTPS inbox.

    Fail closed, no redirect, no retries to alternate hosts, no error-body logging.
    Private receiver must enforce HTTPS, bearer, signature, replay and 480s TTL.
    The routine returns redacted metadata only, safe to persist publicly.
    """
    env = environ if environ is not None else os.environ
    status = config_status(env)
    result: dict[str, Any] = {
        "status": status,
        "delivered": False,
        "fresh_quote_count": 0,
        "private_endpoint_used": False,
        "public_quote_values_persisted": False,
        "trading_authority": False,
    }
    if status != "CONFIGURED":
        return result
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        result["status"] = "BLOCKED_NAIVE_CLOCK"
        return result
    current_utc = current.astimezone(timezone.utc)
    records: list[dict[str, Any]] = []
    for code in sorted(set(allowed_tickers)):
        quote, state = getter(code)
        if quote is None or state != "READY_IN_RUNNER_MEMORY_ONLY":
            continue
        # Only a small normalized subset is delivered privately. No raw rows.
        records.append({
            "ticker": quote.ticker,
            "asof": quote.asof.isoformat(),
            "price": quote.price,
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "average_price": quote.average_price,
            "total_volume": quote.total_volume,
            "total_amount": quote.total_amount,
        })
    result["fresh_quote_count"] = len(records)
    if not records:
        result["status"] = "NO_FRESH_QUOTE_FAIL_CLOSED"
        return result
    body = json.dumps({
        "schema": "HENGCE_PRIVATE_QUOTE_DELIVERY_V1",
        "created_at": current_utc.isoformat(),
        "nonce": secrets.token_hex(16),
        "source": "HENGCE_EXISTING_FINMIND_SNAPSHOT_VESSEL",
        "ttl_seconds": 480,
        "quotes": records,
    }, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(body) > MAX_BODY_BYTES:
        result["status"] = "BLOCKED_OVERSIZE_PAYLOAD"
        return result
    key = env["HENGCE_PRIVATE_QUOTE_HMAC_KEY"].encode("utf-8")
    signature = hmac.new(key, body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        env["HENGCE_PRIVATE_QUOTE_ENDPOINT"],
        data=body,
        headers={
            "Authorization": "Bearer " + env["HENGCE_PRIVATE_QUOTE_BEARER"],
            "Content-Type": "application/json",
            "X-Hengce-Signature": "sha256=" + signature,
            "X-Hengce-Schema": "HENGCE_PRIVATE_QUOTE_DELIVERY_V1",
            "User-Agent": "HENGCE-PRIVATE-OWNER-QUOTE-DELIVERY/1",
        },
        method="POST",
    )
    result["private_endpoint_used"] = True
    client = opener or urllib.request.build_opener(_NoRedirects())
    try:
        with client.open(req, timeout=12) as response:
            # No response body is read or logged (might include sensitive data).
            if response.status != 202:
                result["status"] = "PRIVATE_RECEIVER_REJECTED"
                return result
    except Exception:
        # Never serialize arbitrary exception messages (which may contain a URL).
        result["status"] = "PRIVATE_DELIVERY_FAILED"
        return result
    result["status"] = "DELIVERED_PRIVATE_ONLY"
    result["delivered"] = True
    return result
