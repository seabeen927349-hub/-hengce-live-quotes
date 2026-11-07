#!/usr/bin/env python3
"""Offline E2E handoff: synthetic FinMind snapshot -> bridge -> private delivery -> receiver.

No FinMind token, no GitHub secrets, no requests on a network socket.
"""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_single_name_bridge import lookup, public_status
from hengce_finmind_private_delivery import deliver
from hengce_finmind_private_receiver import QuoteInbox

NOW = datetime(2026,11,4,10,15,tzinfo=ZoneInfo("Asia/Taipei"))
SECRET = "h" * 64

class LocalResponse:
    status=202
    def __enter__(self): return self
    def __exit__(self, *_): pass

class Loopback:
    def __init__(self, inbox):
        self.inbox=inbox
        self.calls=0
    def open(self, req, timeout=12):
        self.calls+=1
        headers={key.lower():value for key,value in req.header_items()}
        code,state=self.inbox.accept(req.data, headers.get("x-hengce-signature",""))
        if code!=202:
            raise ValueError("private receiver rejection")
        return LocalResponse()

class E2ETests(unittest.TestCase):
    def test_multiple_quotes_one_snapshot_private_only(self):
        data={
            "3042":{"stock_id":"3042","date":NOW.isoformat(),"close":152.5,
                    "open":151.0,"high":154.0,"low":150.0,"average_price":151.8,
                    "total_volume":500,"total_amount":76500},
            "3420":{"stock_id":"3420","date":NOW.isoformat(),"close":70.5,
                    "open":69.0,"high":72.0,"low":68.5,"average_price":70.1,
                    "total_volume":300,"total_amount":21300},
        }
        allowed=set(data)
        getter=lambda ticker:lookup(data,ticker,NOW,allowed)
        inbox=QuoteInbox(SECRET,now=lambda: NOW.astimezone(timezone.utc))
        fake=Loopback(inbox)
        credentials={
            "HENGCE_PRIVATE_QUOTE_ENDPOINT":"https://quotes.example.org/hengce/v1/ingest",
            "HENGCE_PRIVATE_QUOTE_BEARER":"b"*40,
            "HENGCE_PRIVATE_QUOTE_HMAC_KEY":SECRET,
            "HENGCE_PRIVATE_QUOTE_LICENSED_PRIVATE_USE_APPROVED":"I_CONFIRM_AUTHORIZED_PRIVATE_USE",
        }
        result=deliver(getter,allowed,credentials,NOW,opener=fake)
        self.assertEqual(result["status"],"DELIVERED_PRIVATE_ONLY")
        self.assertEqual(fake.calls,1)
        self.assertEqual(result["fresh_quote_count"],2)
        self.assertEqual(inbox.get("3042")[1]["quote"]["price"],152.5)
        self.assertEqual(inbox.get("3420")[1]["quote"]["price"],70.5)
        public=public_status(data,["3042","3420"],NOW,allowed)
        self.assertNotIn("152.5",json.dumps(public))
        self.assertNotIn("70.5",json.dumps(public))
        self.assertNotIn("152.5",str(result))
        self.assertNotIn("70.5",str(result))

if __name__=="__main__":
    unittest.main()
