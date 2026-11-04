#!/usr/bin/env python3
"""Reference PRIVATE, in-memory HENGCE quote receiver; NOT deployed by the repo.

Only for an owner-controlled machine behind a properly authenticated TLS
reverse proxy. Runs on loopback by default, with no file or access logs.
RECEIVES existing FinMind snapshot values, does not fetch or collect vendors.
No outbound calls. Read endpoint is for a PRIVATE authorized client, not public.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlsplit

MAX_BODY_BYTES = 2_000_000
TTL_SECONDS = 480
TICKER = re.compile(r"[1-9][0-9]{3}\Z")
INGEST_PATH = "/hengce/v1/ingest"
QUOTE_PATH = re.compile(r"/hengce/v1/quotes/([1-9][0-9]{3})\Z")


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo else None


def _field_number(value: Any, required: bool = False) -> float | None:
    if value is None:
        if required:
            raise ValueError("required number missing")
        return None
    if isinstance(value, bool):
        raise ValueError("invalid number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("invalid number") from None
    if not math.isfinite(number):
        raise ValueError("nonfinite number")
    return number


class QuoteInbox:
    """Private only. Thread-safe ephemeral data, never written to disk."""

    def __init__(self, signing_secret: str, now: Callable[[], datetime] | None = None):
        if len(signing_secret) < 32:
            raise ValueError("signing key too short")
        self.key = signing_secret.encode("utf-8")
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._quotes: dict[str, dict[str, Any]] = {}
        self._nonces: dict[str, datetime] = {}

    def accept(self, body: bytes, signature: str) -> tuple[int, str]:
        """Authenticate exact body bytes and reject stale/replayed packets."""
        if not body or len(body) > MAX_BODY_BYTES:
            return 413, "INVALID_PAYLOAD"
        digest = "sha256=" + hmac.new(self.key, body, hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(digest, signature):
            return 401, "AUTHENTICATION_FAILED"
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                return 400, "INVALID_PAYLOAD"
            if payload.get("schema") != "HENGCE_PRIVATE_QUOTE_DELIVERY_V1":
                return 400, "INVALID_SCHEMA"
            if payload.get("source") != "HENGCE_EXISTING_FINMIND_SNAPSHOT_VESSEL":
                return 400, "INVALID_SOURCE"
            if payload.get("ttl_seconds") != TTL_SECONDS:
                return 400, "INVALID_TTL"
            created = _timestamp(payload.get("created_at"))
            nonce = payload.get("nonce")
            quotes = payload.get("quotes")
            current = self.now().astimezone(timezone.utc)
            if created is None or (current - created).total_seconds() > TTL_SECONDS or (created - current).total_seconds() > 30:
                return 422, "PACKET_EXPIRED_OR_FUTURE"
            if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
                return 400, "INVALID_NONCE"
            if not isinstance(quotes, list) or not quotes or len(quotes) > 3000:
                return 400, "INVALID_QUOTE_COUNT"
            incoming: dict[str, dict[str, Any]] = {}
            for item in quotes:
                if not isinstance(item, dict):
                    return 400, "INVALID_QUOTE_ROW"
                code = item.get("ticker")
                if not isinstance(code, str) or not TICKER.fullmatch(code) or code in incoming:
                    return 400, "INVALID_OR_DUPLICATE_TICKER"
                stamp = _timestamp(item.get("asof"))
                if stamp is None or stamp.date() != current.date():
                    return 422, "NOT_CURRENT_MARKET_DATE"
                age = (current - stamp).total_seconds()
                if age > TTL_SECONDS or age < -30:
                    return 422, "STALE_OR_FUTURE_QUOTE"
                price = _field_number(item.get("price"), required=True)
                if price is None or price <= 0:
                    return 422, "INVALID_PRICE"
                normalized = {"ticker": code, "asof": stamp.isoformat(), "price": price}
                for field in ("open", "high", "low", "average_price", "total_volume", "total_amount"):
                    normalized[field] = _field_number(item.get(field))
                incoming[code] = normalized
        except (UnicodeDecodeError, ValueError, TypeError):
            return 400, "INVALID_PAYLOAD"

        with self._lock:
            for seen, expire in list(self._nonces.items()):
                if expire <= current:
                    self._nonces.pop(seen, None)
            if nonce in self._nonces:
                return 409, "REPLAY_REJECTED"
            self._nonces[nonce] = current + __import__("datetime").timedelta(seconds=TTL_SECONDS)
            for code, quote in incoming.items():
                self._quotes[code] = quote
        return 202, "ACCEPTED"

    def get(self, ticker: str) -> tuple[int, dict[str, Any]]:
        if not isinstance(ticker, str) or not TICKER.fullmatch(ticker):
            return 400, {"status": "INVALID_TICKER"}
        now = self.now().astimezone(timezone.utc)
        with self._lock:
            quote = self._quotes.get(ticker)
            if quote is None:
                return 404, {"status": "NOT_IN_PRIVATE_CACHE"}
            stamp = _timestamp(quote["asof"])
            if stamp is None or stamp.date() != now.date() or not (0 <= (now - stamp).total_seconds() <= TTL_SECONDS):
                self._quotes.pop(ticker, None)
                return 410, {"status": "NOT_FRESH"}
            result = dict(quote)
        return 200, {"status": "FRESH_PRIVATE_QUOTE", "quote": result, "source": "HENGCE_FINMIND_PRIVATE_DELIVERY"}


def make_handler(inbox: QuoteInbox, ingest_token: str, read_token: str):
    if len(ingest_token) < 24 or len(read_token) < 24:
        raise ValueError("private bearer/read key too short")
    class PrivateHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            # No URLs, query params, received payload, prices or IPs in logs.
            return

        def _reply(self, code: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store, private")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != INGEST_PATH:
                return self._reply(404, {"status": "NOT_FOUND"})
            provided = self.headers.get("Authorization", "")
            if not hmac.compare_digest(provided, "Bearer " + ingest_token):
                return self._reply(401, {"status": "UNAUTHORIZED"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = -1
            if not (0 < size <= MAX_BODY_BYTES):
                return self._reply(413, {"status": "PAYLOAD_REJECTED"})
            body = self.rfile.read(size)
            code, state = inbox.accept(body, self.headers.get("X-Hengce-Signature", ""))
            return self._reply(code, {"status": state})

        def do_GET(self) -> None:
            path = urlsplit(self.path)
            match = QUOTE_PATH.fullmatch(path.path)
            if not match or path.query:
                return self._reply(404, {"status": "NOT_FOUND"})
            supplied = self.headers.get("X-Hengce-Read-Token", "")
            if not hmac.compare_digest(supplied, read_token):
                return self._reply(401, {"status": "UNAUTHORIZED"})
            code, value = inbox.get(match.group(1))
            return self._reply(code, value)
    return PrivateHandler


def main() -> None:
    # Bind only loopback; NEVER expose raw HTTP to the Internet.
    # An owner-controlled TLS reverse proxy must terminate HTTPS and enforce
    # additional client authentication/allowlists before exposing this service.
    secret = os.environ["HENGCE_PRIVATE_QUOTE_HMAC_KEY"]
    ingest = os.environ["HENGCE_PRIVATE_QUOTE_BEARER"]
    read_key = os.environ["HENGCE_PRIVATE_QUOTE_READ_KEY"]
    if not os.environ.get("HENGCE_PRIVATE_QUOTE_LICENSED_PRIVATE_USE_APPROVED") == "I_CONFIRM_AUTHORIZED_PRIVATE_USE":
        raise SystemExit("PRIVATE_QUOTE_LICENSE_APPROVAL_REQUIRED")
    handler = make_handler(QuoteInbox(secret), ingest, read_key)
    server = ThreadingHTTPServer(("127.0.0.1", 8787), handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
