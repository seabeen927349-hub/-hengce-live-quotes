#!/usr/bin/env python3
"""Read licensed 9A81 FinMind data; commit ONLY recipient-encrypted output to the public vessel.

The receiver holds a one-time X25519 private transport key in the PRIVATE research repo.
No raw/derived per-stock trading data, FinMind token or symmetric key is committed here.
"""
from __future__ import annotations
import base64, concurrent.futures, csv, datetime as dt, hashlib, io, json, os, pathlib, random, time, zlib
from decimal import Decimal
import requests
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

PUBLIC_TRANSPORT_KEY_B64 = "sEsZLJNAX3HB_-ckjmqUPATit5yHDyQ4ToaYVI7V1X4"
BRANCH="9A81"
FIRST="2026-01-01"
LAST="2026-11-20"
BASE="https://api.finmindtrade.com/api/v4"
OUT=pathlib.Path("research/9a81_secure_2026_envelope.json")
STATUS=pathlib.Path("research/9a81_secure_2026_status.json")
FIELDS=("date","stock_id","securities_trader_id","price","buy","sell")

def get_data(path,params,token,retries=5):
    last_exc=None
    for attempt in range(retries):
        try:
            response=requests.get(BASE+"/"+path,params=params,
                headers={"Authorization":"Bearer "+token,
                         "Accept":"application/json",
                         "User-Agent":"HENGCE-Secure-9A81-2026-Export/1.0"},
                timeout=(20,110))
            response.raise_for_status()
            obj=response.json()
            if not isinstance(obj,dict) or not isinstance(obj.get("data"),list):
                raise ValueError("NO_DATA_ARRAY")
            if str(obj.get("status",200)) not in ("200","0"):
                raise ValueError("INVALID_API_STATUS")
            return obj["data"]
        except Exception as exc:
            last_exc=exc
            if attempt < retries-1:
                time.sleep(min(45,2**attempt+random.random()*2))
    raise RuntimeError(type(last_exc).__name__)

def get_calendar(token):
    rows=get_data("data",{"dataset":"TaiwanStockTradingDate","start_date":FIRST,"end_date":LAST},token)
    days=sorted({str(x.get("date",""))[:10] for x in rows if isinstance(x,dict)
                 and FIRST <= str(x.get("date",""))[:10] <= LAST})
    if len(days)<210 or days[0] > "2026-01-09" or days[-1] < "2026-11-19":
        raise RuntimeError("IMPLAUSIBLE_OR_TRUNCATED_TRADING_CALENDAR")
    return days

def fetch_day(day,token):
    rows=get_data("taiwan_stock_trading_daily_report",
                  {"securities_trader_id":BRANCH,"date":day},token)
    if not rows:
        raise RuntimeError("TRADING_DAY_EMPTY")
    out=[]
    for row in rows:
        if any(x not in row for x in FIELDS):
            raise RuntimeError("MISSING_FIELDS")
        if str(row["date"])[:10]!=day or str(row["securities_trader_id"]).upper()!=BRANCH:
            raise RuntimeError("BRANCH_OR_DATE_MISMATCH")
        code=str(row["stock_id"]).strip()
        if not code:
            raise RuntimeError("EMPTY_STOCK_ID")
        pr=Decimal(str(row["price"]))
        buy=Decimal(str(row["buy"]))
        sell=Decimal(str(row["sell"]))
        if pr<=0 or buy<0 or sell<0 or buy!=int(buy) or sell!=int(sell):
            raise RuntimeError("INVALID_PRICE_VOLUME")
        out.append((day,code,BRANCH,str(pr),int(buy),int(sell)))
    return day,out

def report(s):
    STATUS.parent.mkdir(parents=True,exist_ok=True)
    STATUS.write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def main():
    token=os.environ.get("FINMIND_TOKEN","").strip()
    status={"schema":"HENGCE_9A81_2026_ENCRYPTED_TRANSFER_STATUS_V1",
            "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "requested_start":FIRST,"requested_end":LAST,"recipient":"PRIVATE_RESEARCH_REPOSITORY",
            "source":"FinMind TaiwanStockTradingDailyReport","encrypted_output_only":True,
            "state":"STARTED"}
    if not token:
        status["state"]="BLOCKED_NO_TOKEN"
        report(status)
        raise SystemExit("ORIGINAL_REPO_TOKEN_NOT_VISIBLE")
    try:
        days=get_calendar(token)
        status["calendar_days"]=len(days)
        trade_rows={}
        failures=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(fetch_day,day,token):day for day in days}
            for n,future in enumerate(concurrent.futures.as_completed(futures),1):
                day=futures[future]
                try:
                    d,items=future.result()
                    trade_rows[d]=items
                except Exception as exc:
                    failures.append({"date":day,"error_type":type(exc).__name__,
                                     "error_code":str(exc)[:70]})
                if n%20==0:
                    print("ENCRYPTED_EXPORT_PROGRESS",n,"/",len(days),flush=True)
        status["successful_days"]=len(trade_rows)
        status["exceptions"]=sorted(failures,key=lambda x:x["date"])
        if failures:
            status["state"]="FAILED_INCOMPLETE_DAYS"
            report(status)
            raise SystemExit("FINMIND_DAYS_INCOMPLETE: "+str(len(failures)))
        buf=io.StringIO()
        csv_out=csv.writer(buf,lineterminator="\n")
        csv_out.writerow(FIELDS)
        total=0
        tickers=set()
        for day in days:
            for row in sorted(trade_rows[day]):
                csv_out.writerow(row)
                tickers.add(row[1])
                total+=1
        raw=buf.getvalue().encode("utf-8")
        packed=zlib.compress(raw,level=9)
        recipient_bytes=base64.urlsafe_b64decode(PUBLIC_TRANSPORT_KEY_B64+"=")
        recipient=x25519.X25519PublicKey.from_public_bytes(recipient_bytes)
        ephemeral=x25519.X25519PrivateKey.generate()
        shared=ephemeral.exchange(recipient)
        key=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,
                 info=b"HENGCE-9A81-FINMIND-2026-TRANSPORT-v1").derive(shared)
        nonce=os.urandom(12)
        aad=b"HENGCE:9A81:2026-01-01:2026-11-20:v1"
        sealed=ChaCha20Poly1305(key).encrypt(nonce,packed,aad)
        envelope={
            "schema":"HENGCE_9A81_2026_ENCRYPTED_TRANSFER_V1",
            "source_repo":"seabeen927349-hub/-hengce-live-quotes",
            "target_private_repo":"seabeen927349-hub/twse--backfill-test",
            "source":"FinMind TaiwanStockTradingDailyReport",
            "broker":"9A81",
            "date_start":FIRST,"date_end":LAST,
            "calendar_dates":days,
            "calendar_days":len(days),
            "price_rows":total,"distinct_stock_codes":len(tickers),
            "plaintext_sha256":hashlib.sha256(raw).hexdigest(),
            "compressed_bytes":len(packed),
            "encryption":"X25519-HKDF-SHA256-ChaCha20Poly1305",
            "ephemeral_pub_b64":base64.urlsafe_b64encode(ephemeral.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode(),
            "nonce_b64":base64.urlsafe_b64encode(nonce).decode(),
            "payload_b64":base64.b64encode(sealed).decode(),
        }
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(envelope,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
        status.update({"state":"ENCRYPTED_COMPLETE","calendar_days":len(days),
                "successful_days":len(days),"raw_price_rows":total,
                "distinct_stock_codes":len(tickers),"ciphertext_file":str(OUT),
                "plaintext_rows_persisted":False})
        report(status)
        print("ENCRYPTED_TRANSFER_READY",json.dumps({k:v for k,v in status.items() if k!="exceptions"},ensure_ascii=False))
    except Exception:
        if status.get("state")=="STARTED":
            status["state"]="FAILED_PRE_ENCRYPTION"
            report(status)
        raise
if __name__=="__main__":
    main()
