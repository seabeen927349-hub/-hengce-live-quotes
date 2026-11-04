#!/usr/bin/env python3
"""Offline tests of the private, RAM-only FinMind quote receiver."""
import hashlib
import hmac
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_private_receiver import QuoteInbox

BASE=datetime(2026,11,4,2,13,tzinfo=timezone.utc)
SIGN_KEY="h"*64

class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.now=BASE
        self.inbox=QuoteInbox(SIGN_KEY,now=lambda: self.now)

    def packet(self, *, code="3042", price=151.5, age=0, nonce="ab"*16):
        p={"schema":"HENGCE_PRIVATE_QUOTE_DELIVERY_V1",
           "created_at":self.now.isoformat(),
           "nonce":nonce,
           "source":"HENGCE_EXISTING_FINMIND_SNAPSHOT_VESSEL",
           "ttl_seconds":480,
           "quotes":[{"ticker":code,"asof":(self.now-timedelta(seconds=age)).isoformat(),
                       "price":price,"open":150.0,"high":151.5,"low":149.0,
                       "average_price":150.5,"total_volume":20,"total_amount":35000}]}
        b=json.dumps(p).encode("utf-8")
        return b,"sha256="+hmac.new(SIGN_KEY.encode(),b,hashlib.sha256).hexdigest()

    def test_authentication_and_short_lived_private_read(self):
        b,s=self.packet()
        self.assertEqual(self.inbox.accept(b,s),(202,"ACCEPTED"))
        code,value=self.inbox.get("3042")
        self.assertEqual(code,200)
        self.assertEqual(value["quote"]["price"],151.5)
        self.assertEqual(value["source"],"HENGCE_FINMIND_PRIVATE_DELIVERY")
        self.now += timedelta(seconds=481)
        code,value=self.inbox.get("3042")
        self.assertEqual(code,410)
        self.assertNotIn("151.5",str(value))

    def test_signature_and_nonce_replay_blocked(self):
        b,s=self.packet()
        self.assertEqual(self.inbox.accept(b,"sha256="+"0"*64)[0],401)
        self.assertEqual(self.inbox.accept(b,s)[0],202)
        self.assertEqual(self.inbox.accept(b,s),(409,"REPLAY_REJECTED"))

    def test_stale_and_invalid_price_never_enter_cache(self):
        b,s=self.packet(age=481)
        self.assertEqual(self.inbox.accept(b,s)[0],422)
        self.assertEqual(self.inbox.get("3042")[0],404)
        b,s=self.packet(price=float("nan"))
        self.assertEqual(self.inbox.accept(b,s)[0],400)
        self.assertEqual(self.inbox.get("3042")[0],404)

    def test_future_quote_rejected(self):
        b,s=self.packet(age=-80)
        self.assertEqual(self.inbox.accept(b,s)[0],422)

    def test_other_stock_needs_no_new_receiver(self):
        b,s=self.packet(code="3420")
        self.assertEqual(self.inbox.accept(b,s)[0],202)
        self.assertEqual(self.inbox.get("3420")[0],200)

    def test_no_persistence_and_missing(self):
        self.assertEqual(self.inbox.get("3042")[0],404)
        self.assertFalse(hasattr(self.inbox,"file"))
        self.assertFalse(hasattr(self.inbox,"database"))

if __name__=="__main__":
    unittest.main()
