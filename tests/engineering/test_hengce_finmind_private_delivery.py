#!/usr/bin/env python3
"""Synthetic-only tests for optional private quote delivery.

No network calls, no production credentials, no FinMind API calls.
"""
import hashlib
import hmac
import json
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_private_delivery import config_status, deliver, _private_https_target

NOW = datetime(2026, 11, 4, 2, 13, tzinfo=timezone.utc)

def env(**updates):
    v = {
        "HENGCE_PRIVATE_QUOTE_ENDPOINT": "https://quotes.example.org/hengce/v1/ingest",
        "HENGCE_PRIVATE_QUOTE_BEARER": "b" * 40,
        "HENGCE_PRIVATE_QUOTE_HMAC_KEY": "h" * 64,
        "HENGCE_PRIVATE_QUOTE_LICENSED_PRIVATE_USE_APPROVED": "I_CONFIRM_AUTHORIZED_PRIVATE_USE",
    }
    v.update(updates)
    return v

class Response:
    def __init__(self, status): self.status = status
    def __enter__(self): return self
    def __exit__(self, *_args): pass

class PrivateOpener:
    def __init__(self, status=202): self.status=status; self.requests=[]
    def open(self, req, timeout=12):
        self.requests.append((req,timeout))
        return Response(self.status)

class Checks(unittest.TestCase):
    def quote(self, code):
        if code=="3042":
            return SimpleNamespace(
                ticker=code, asof=NOW, price=155.5, open=151.0, high=158.0,
                low=150.0, average_price=153.5, total_volume=100,
                total_amount=1234567,
            ), "READY_IN_RUNNER_MEMORY_ONLY"
        return None, "STALE_GT_480_SECONDS"

    def test_missing_config_is_safe_without_calling_getter(self):
        def no_getter(_):
            raise AssertionError("MUST_NOT_INVOKE_QUOTE_LOOKUP_WHEN_DISABLED")
        obj=deliver(no_getter, ["3042"], {}, NOW)
        self.assertEqual(obj["status"],"NOT_CONFIGURED")
        self.assertFalse(obj["delivered"])
        self.assertFalse(obj["private_endpoint_used"])

    def test_rejects_insecure_urls_and_missing_approval(self):
        for url in ("http://quotes.example.org/path",
                    "https://localhost/quotes",
                    "https://api.github.com/private",
                    "https://quotes.github.io/ingest",
                    "https://127.0.0.1/ingest",
                    "https://user:secret@quotes.example.org/ingest",
                    "https://quotes.example.org/ingest?token=abc"):
            self.assertFalse(_private_https_target(url),url)
            self.assertEqual(config_status(env(HENGCE_PRIVATE_QUOTE_ENDPOINT=url)),
                             "REJECTED_NONPRIVATE_OR_INSECURE_ENDPOINT")
        self.assertEqual(config_status(env(HENGCE_PRIVATE_QUOTE_LICENSED_PRIVATE_USE_APPROVED="")),
                         "NOT_LICENSE_APPROVED")

    def test_hmac_and_private_delivery_with_no_public_price(self):
        opener=PrivateOpener()
        result=deliver(self.quote, {"3042","3420"}, env(), NOW, opener=opener)
        self.assertEqual(result["status"],"DELIVERED_PRIVATE_ONLY")
        self.assertTrue(result["delivered"])
        self.assertEqual(result["fresh_quote_count"],1)
        self.assertEqual(len(opener.requests),1)
        req,timeout=opener.requests[0]
        self.assertEqual(timeout,12)
        content=json.loads(req.data.decode("utf-8"))
        self.assertEqual([q["ticker"] for q in content["quotes"]],["3042"])
        self.assertEqual(content["quotes"][0]["price"],155.5)
        key=env()["HENGCE_PRIVATE_QUOTE_HMAC_KEY"].encode("utf-8")
        expected="sha256="+hmac.new(key,req.data,hashlib.sha256).hexdigest()
        self.assertEqual(req.headers["X-hengce-signature"],expected)
        self.assertNotIn("155.5",str(result))
        self.assertNotIn("quotes.example.org",str(result))
        self.assertFalse(result["public_quote_values_persisted"])

    def test_no_fresh_prices_fail_closed(self):
        result=deliver(lambda _ticker:(None,"STALE_GT_480_SECONDS"),{"3042"},env(),NOW,opener=PrivateOpener())
        self.assertEqual(result["status"],"NO_FRESH_QUOTE_FAIL_CLOSED")
        self.assertFalse(result["delivered"])

    def test_receiver_must_accept_with_202(self):
        result=deliver(self.quote,{"3042"},env(),NOW,opener=PrivateOpener(200))
        self.assertEqual(result["status"],"PRIVATE_RECEIVER_REJECTED")
        self.assertFalse(result["delivered"])

    def test_transport_exception_is_sanitized(self):
        class Failed:
            def open(self, *_args, **_kwargs):
                raise RuntimeError("SECRET_URL:https://private.example.org/token=secret")
        result=deliver(self.quote,{"3042"},env(),NOW,opener=Failed())
        self.assertEqual(result["status"],"PRIVATE_DELIVERY_FAILED")
        self.assertNotIn("SECRET",str(result))

if __name__=="__main__":
    unittest.main()
