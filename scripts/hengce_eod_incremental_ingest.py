#!/usr/bin/env python3
"""HENGCE post-close incremental official three-leg ingest.

Each EOD leg (price / institutional / margin) is independently validated and
promoted as soon as TWSE publishes it. No leg waits for the margin leg.

Historical Mother contract:
- price is the authoritative row universe;
- available institutional/margin evidence is left-joined immediately;
- unavailable evidence stays null and is filled by later runs;
- a date becomes THREE_LEG_COMPLETE only when all three legs are complete.

This is market-data ingestion only. It does not create Q017/E2 ranking,
signal, capital, or broker authority and never reconstructs Q017 09:01 PIT.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
EOD_ROOT = ROOT / "eod"
MOTHER_ROOT = ROOT / "hengce" / "historical_mother" / "incremental"
MOTHER_RECEIPTS = MOTHER_ROOT / "receipts"
TW_HISTORY = ROOT / "hengce" / "q017_radar" / "data" / "twse_electronics_history_2026.csv"

BASE = "https://www.twse.com.tw/rwd/zh"
PRICE_URL = BASE + "/afterTrading/MI_INDEX"
INST_URL = BASE + "/fund/T86"
MARGIN_URL = BASE + "/marginTrading/MI_MARGN"
UA = {"User-Agent": "Mozilla/5.0 HENGCE-EOD-INCREMENTAL/1.0", "Accept": "application/json", "Referer": "https://www.twse.com.tw/"}

PRICE_COLS = ["Date","Ticker","Name","VolumeShares","Trades","TurnoverTWD","Open","High","Low","Close","ChangeSign","Change","LastBid","LastBidVolume","LastAsk","LastAskVolume","PE","Source"]
INST_COLS = ["Date","Ticker","Name","ForeignBuy","ForeignSell","ForeignNet","ForeignDealerBuy","ForeignDealerSell","ForeignDealerNet","TrustBuy","TrustSell","TrustNet","DealerNet","DealerProprietaryBuy","DealerProprietarySell","DealerProprietaryNet","DealerHedgeBuy","DealerHedgeSell","DealerHedgeNet","TotalNet","Source"]
MARGIN_COLS = ["Date","Ticker","Name","MarginBuy","MarginSell","MarginCashRepayment","MarginPreviousBalance","MarginBalance","MarginNextDayLimit","ShortBuy","ShortSell","ShortStockRepayment","ShortPreviousBalance","ShortBalance","ShortNextDayLimit","Offset","Note","Source"]
MOTHER_COLS = ["Date","Ticker","Name","Volume","Turnover","Open","High","Low","Close","Margin_MarginBalance","ForeignNet","TrustNet","TotalNet"]
MIN_ROWS = {"price": 900, "institutional": 900, "margin": 500}

class NotReady(RuntimeError):
    pass


def now_tw() -> datetime:
    return datetime.now(TZ)


def clean(x):
    return "" if x is None else str(x).replace(",", "").strip()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    os.close(fd)
    try:
        Path(tmp).write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_json(path: Path, obj: dict) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def fetch_json(url: str, params: dict, timeout: int = 30) -> dict:
    from urllib.parse import urlencode
    req = Request(url + "?" + urlencode(params), headers=UA)
    with urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8"))


def canonical_rows_sha(rows: list[dict], cols: list[str]) -> str:
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for row in sorted(rows, key=lambda r: (str(r.get("Date","")), str(r.get("Ticker","")))):
        w.writerow({c: row.get(c, "") for c in cols})
    return hashlib.sha256(s.getvalue().encode("utf-8")).hexdigest()


def find_price_table(p: dict):
    for t in p.get("tables") or []:
        fs = t.get("fields") or []
        if "證券代號" in fs and "收盤價" in fs and ("成交股數" in fs or "成交量" in fs):
            return fs, t.get("data") or t.get("records") or []
    raise RuntimeError("PRICE_TABLE_NOT_FOUND")


def parse_price(p: dict, iso: str) -> list[dict]:
    fs, data = find_price_table(p); idx = {f:i for i,f in enumerate(fs)}
    def v(row, *names):
        for n in names:
            i = idx.get(n)
            if i is not None and i < len(row): return clean(row[i])
        return ""
    out=[]
    for r in data:
        t=v(r,"證券代號").replace("=","").replace('"',"")
        if not re.fullmatch(r"[1-9]\d{3}",t): continue
        out.append({"Date":iso,"Ticker":t,"Name":v(r,"證券名稱"),"VolumeShares":v(r,"成交股數","成交量"),"Trades":v(r,"成交筆數"),"TurnoverTWD":v(r,"成交金額"),"Open":v(r,"開盤價"),"High":v(r,"最高價"),"Low":v(r,"最低價"),"Close":v(r,"收盤價"),"ChangeSign":v(r,"漲跌(+/-)","漲跌"),"Change":v(r,"漲跌價差"),"LastBid":v(r,"最後揭示買價"),"LastBidVolume":v(r,"最後揭示買量"),"LastAsk":v(r,"最後揭示賣價"),"LastAskVolume":v(r,"最後揭示賣量"),"PE":v(r,"本益比"),"Source":PRICE_URL})
    return out


def parse_inst(q: dict, iso: str) -> list[dict]:
    qf=q.get("fields") or []; qd=q.get("data") or q.get("records") or []
    if not qd and isinstance(q.get("tables"),list):
        for t in q["tables"]:
            fs=t.get("fields") or []
            if "證券代號" in fs and any("外陸資買賣超股數" in str(x) for x in fs):
                qf=fs; qd=t.get("data") or t.get("records") or []; break
    if not qd: raise RuntimeError("INST_TABLE_NOT_FOUND")
    qi={f:i for i,f in enumerate(qf)}
    def qv(row, exact=None, contains=None):
        if exact is not None and exact in qi and qi[exact] < len(row): return clean(row[qi[exact]])
        if contains:
            for f,i in qi.items():
                if contains in f and i < len(row): return clean(row[i])
        return ""
    out=[]
    for r in qd:
        t=qv(r,exact="證券代號").replace("=","").replace('"',"")
        if not re.fullmatch(r"[1-9]\d{3}",t): continue
        out.append({"Date":iso,"Ticker":t,"Name":qv(r,exact="證券名稱"),"ForeignBuy":qv(r,contains="外陸資買進股數(不含外資自營商)"),"ForeignSell":qv(r,contains="外陸資賣出股數(不含外資自營商)"),"ForeignNet":qv(r,contains="外陸資買賣超股數(不含外資自營商)"),"ForeignDealerBuy":qv(r,exact="外資自營商買進股數"),"ForeignDealerSell":qv(r,exact="外資自營商賣出股數"),"ForeignDealerNet":qv(r,exact="外資自營商買賣超股數"),"TrustBuy":qv(r,exact="投信買進股數"),"TrustSell":qv(r,exact="投信賣出股數"),"TrustNet":qv(r,exact="投信買賣超股數"),"DealerNet":qv(r,exact="自營商買賣超股數"),"DealerProprietaryBuy":qv(r,exact="自營商買進股數(自行買賣)"),"DealerProprietarySell":qv(r,exact="自營商賣出股數(自行買賣)"),"DealerProprietaryNet":qv(r,exact="自營商買賣超股數(自行買賣)"),"DealerHedgeBuy":qv(r,exact="自營商買進股數(避險)"),"DealerHedgeSell":qv(r,exact="自營商賣出股數(避險)"),"DealerHedgeNet":qv(r,exact="自營商買賣超股數(避險)"),"TotalNet":qv(r,exact="三大法人買賣超股數"),"Source":INST_URL})
    return out


def margin_candidates(m: dict):
    out=[]
    if isinstance(m.get("tables"),list): out += m["tables"]
    if isinstance(m.get("fields"),list) and isinstance(m.get("data"),list): out += [{"fields":m["fields"],"data":m["data"]}]
    for k,v in m.items():
        mm=re.fullmatch(r"fields(\d+)",str(k))
        if mm and isinstance(v,list) and isinstance(m.get("data"+mm.group(1)),list): out += [{"fields":v,"data":m["data"+mm.group(1)]}]
    return out


def parse_margin(m: dict, iso: str) -> list[dict]:
    mt=None
    for t in margin_candidates(m):
        fs=[clean(x).replace(" ","") for x in (t.get("fields") or [])]; data=t.get("data") or t.get("records") or []
        if len(fs)>=15 and len(data)>=MIN_ROWS["margin"] and any("現金償還" in x for x in fs) and any("現券償還" in x for x in fs) and sum("今日餘額" in x for x in fs)>=2:
            mt=data; break
    if mt is None: raise RuntimeError("MARGIN_TABLE_NOT_FOUND")
    out=[]
    for r in mt:
        if not isinstance(r,(list,tuple)) or len(r)<15: continue
        t=clean(r[0]).replace("=","").replace('"',"")
        if not re.fullmatch(r"[1-9]\d{3}",t): continue
        out.append({"Date":iso,"Ticker":t,"Name":clean(r[1]),"MarginBuy":clean(r[2]),"MarginSell":clean(r[3]),"MarginCashRepayment":clean(r[4]),"MarginPreviousBalance":clean(r[5]),"MarginBalance":clean(r[6]),"MarginNextDayLimit":clean(r[7]),"ShortBuy":clean(r[8]),"ShortSell":clean(r[9]),"ShortStockRepayment":clean(r[10]),"ShortPreviousBalance":clean(r[11]),"ShortBalance":clean(r[12]),"ShortNextDayLimit":clean(r[13]),"Offset":clean(r[14]),"Note":clean(r[15]) if len(r)>15 else "","Source":MARGIN_URL})
    return out


def leg_files(folder: Path, leg: str):
    return sorted(folder.glob(f"{leg}_[1-9].csv"))


def read_leg(folder: Path, leg: str, cols: list[str]) -> list[dict]:
    rows=[]
    for fp in leg_files(folder,leg):
        with fp.open(encoding="utf-8-sig",newline="") as f:
            for r in csv.DictReader(f): rows.append({c:r.get(c,"") for c in cols})
    rows=[r for r in rows if re.fullmatch(r"[1-9]\d{3}",str(r.get("Ticker","")))]
    uniq={(r["Date"],r["Ticker"]):r for r in rows}
    return [uniq[k] for k in sorted(uniq)]


def write_leg(folder: Path, leg: str, rows: list[dict], cols: list[str]) -> str:
    if len(rows)<MIN_ROWS[leg]: raise RuntimeError(f"{leg.upper()}_ROWS_TOO_SMALL:{len(rows)}")
    if len({(r["Date"],r["Ticker"]) for r in rows}) != len(rows): raise RuntimeError(f"{leg.upper()}_DUPLICATE_DATE_TICKER")
    grouped={str(i):[] for i in range(1,10)}
    for r in sorted(rows,key=lambda x:x["Ticker"]): grouped[r["Ticker"][0]].append(r)
    folder.mkdir(parents=True,exist_ok=True)
    written=set()
    for k,rs in grouped.items():
        if not rs: continue
        path=folder/f"{leg}_{k}.csv"
        s=io.StringIO(newline=""); w=csv.DictWriter(s,fieldnames=cols,lineterminator="\n"); w.writeheader(); w.writerows(rs)
        atomic_text(path,s.getvalue()); written.add(path.name)
    for old in leg_files(folder,leg):
        if old.name not in written: old.unlink()
    return canonical_rows_sha(rows,cols)


def load_status(folder: Path, iso: str) -> dict:
    p=folder/"status.json"
    if p.exists():
        try: x=json.loads(p.read_text(encoding="utf-8"))
        except Exception: x={}
    else: x={}
    x.update({"system":"HENGCE","artifact":"EOD_INCREMENTAL_LEG_INGEST","target_date":iso,"policy":"INDEPENDENT_LEG_PROMOTION_NO_WAIT_FOR_MARGIN","mother_policy":"PRICE_ROW_UNIVERSE_LEFT_JOIN_AVAILABLE_EVIDENCE_MISSING_NULL","q017_late_backfill_policy":"EOD_HISTORY_ONLY_NEVER_RECONSTRUCT_0901_PIT"})
    for leg in ("price","institutional","margin"):
        x.setdefault(f"{leg}_status","PENDING")
        x.setdefault(f"{leg}_rows",0)
    return x


def leg_is_complete(folder: Path, status: dict, leg: str, cols: list[str]) -> bool:
    if status.get(f"{leg}_status") != "COMPLETE": return False
    rows=read_leg(folder,leg,cols)
    return len(rows)>=MIN_ROWS[leg] and set(r["Date"] for r in rows)=={status["target_date"]}


def try_leg(folder: Path, status: dict, leg: str, target: date) -> dict:
    cols={"price":PRICE_COLS,"institutional":INST_COLS,"margin":MARGIN_COLS}[leg]
    if leg_is_complete(folder,status,leg,cols):
        rows=read_leg(folder,leg,cols)
        return {"leg":leg,"result":"ALREADY_COMPLETE","rows":len(rows),"sha256":canonical_rows_sha(rows,cols)}
    ds=target.strftime("%Y%m%d"); iso=target.isoformat()
    try:
        if leg=="price": payload=fetch_json(PRICE_URL,{"date":ds,"type":"ALLBUT0999","response":"json"}); parser=parse_price
        elif leg=="institutional": payload=fetch_json(INST_URL,{"date":ds,"selectType":"ALLBUT0999","response":"json"}); parser=parse_inst
        else: payload=fetch_json(MARGIN_URL,{"date":ds,"selectType":"ALL","response":"json"}); parser=parse_margin
        if str(payload.get("stat","")).upper()!="OK" or str(payload.get("date",""))!=ds:
            raise NotReady(f"{leg.upper()}_NOT_READY:stat={payload.get('stat')}:date={payload.get('date')}")
        rows=parser(payload,iso)
        if len(rows)<MIN_ROWS[leg]: raise RuntimeError(f"{leg.upper()}_ROWS_TOO_SMALL:{len(rows)}")
        if set(r["Date"] for r in rows)!={iso}: raise RuntimeError(f"{leg.upper()}_DATE_MISMATCH")
        sha=write_leg(folder,leg,rows,cols)
        status.update({f"{leg}_status":"COMPLETE",f"{leg}_date":iso,f"{leg}_rows":len(rows),f"{leg}_sha256":sha,f"{leg}_completed_at_taipei":now_tw().isoformat()})
        atomic_json(folder/f"{leg}_receipt.json",{"system":"HENGCE","artifact":"EOD_LEG_PROMOTION_RECEIPT","target_date":iso,"leg":leg,"status":"PASS","rows":len(rows),"sha256":sha,"source":{"price":PRICE_URL,"institutional":INST_URL,"margin":MARGIN_URL}[leg],"authority":"MARKET_DATA_ONLY_NO_MODEL_AUTHORITY","promoted_at_taipei":now_tw().isoformat()})
        return {"leg":leg,"result":"NEWLY_PROMOTED","rows":len(rows),"sha256":sha}
    except NotReady as e:
        status[f"{leg}_status"]="PENDING"; status[f"{leg}_last_not_ready_reason"]=str(e); status[f"{leg}_last_checked_at_taipei"]=now_tw().isoformat()
        return {"leg":leg,"result":"PENDING","reason":str(e)}


def build_mother_rows(price: list[dict], inst: list[dict], margin: list[dict]) -> list[dict]:
    im={r["Ticker"]:r for r in inst}; mm={r["Ticker"]:r for r in margin}; out=[]
    for p in sorted(price,key=lambda r:r["Ticker"]):
        i=im.get(p["Ticker"],{}); m=mm.get(p["Ticker"],{})
        out.append({"Date":p["Date"],"Ticker":p["Ticker"],"Name":p["Name"],"Volume":p["VolumeShares"],"Turnover":p["TurnoverTWD"],"Open":p["Open"],"High":p["High"],"Low":p["Low"],"Close":p["Close"],"Margin_MarginBalance":m.get("MarginBalance", ""),"ForeignNet":i.get("ForeignNet", ""),"TrustNet":i.get("TrustNet", ""),"TotalNet":i.get("TotalNet", "")})
    return out


def materialize_mother_delta(folder: Path, status: dict, target: date) -> dict:
    iso=target.isoformat(); ds=target.strftime("%Y%m%d")
    if status.get("price_status")!="COMPLETE":
        return {"status":"WAITING_FOR_PRICE_ROW_UNIVERSE","target_date":iso,"evidence_legs_promoted":[x for x in ("institutional","margin") if status.get(f"{x}_status")=="COMPLETE"]}
    price=read_leg(folder,"price",PRICE_COLS)
    inst=read_leg(folder,"institutional",INST_COLS) if status.get("institutional_status")=="COMPLETE" else []
    margin=read_leg(folder,"margin",MARGIN_COLS) if status.get("margin_status")=="COMPLETE" else []
    rows=build_mother_rows(price,inst,margin)
    s=io.StringIO(newline=""); w=csv.DictWriter(s,fieldnames=MOTHER_COLS,lineterminator="\n"); w.writeheader(); w.writerows(rows)
    out=MOTHER_ROOT/f"{ds}.csv"; atomic_text(out,s.getvalue()); sha=hashlib.sha256(s.getvalue().encode("utf-8")).hexdigest()
    available=[x for x in ("price","institutional","margin") if status.get(f"{x}_status")=="COMPLETE"]
    pending=[x for x in ("price","institutional","margin") if x not in available]
    rec={"system":"HENGCE","artifact":"HIST_MOTHER_INCREMENTAL_APPEND_RECEIPT","version":"v2_incremental_no_wait_for_margin_20261020","status":"PASS","target_date":iso,"rule":"PRICE_ROW_UNIVERSE_LEFT_JOIN_AVAILABLE_MARGIN_AND_INSTITUTIONAL_MISSING_EVIDENCE_NULL","target_mother_rows":len(rows),"available_legs":available,"pending_legs":pending,"three_leg_complete":not pending,"margin_nonnull_rows":sum(bool(r["Margin_MarginBalance"]) for r in rows),"institutional_nonnull_rows":sum(bool(r["ForeignNet"] or r["TrustNet"] or r["TotalNet"]) for r in rows),"missing_evidence_is_null":True,"mother_delta_path":str(out.relative_to(ROOT)),"mother_delta_sha256":sha,"model_mutated":False,"q017_mutated":False,"e2_formula_mutated":False,"generated_at_taipei":now_tw().isoformat()}
    atomic_json(MOTHER_RECEIPTS/f"{ds}.json",rec)
    return rec


def append_electronics_history(target: date) -> dict:
    iso=target.isoformat(); ds=target.strftime("%Y%m%d")
    if not TW_HISTORY.exists(): return {"status":"ERROR","reason":"TW_HISTORY_MISSING"}
    with TW_HISTORY.open(encoding="utf-8-sig",newline="") as f: old=list(csv.DictReader(f))
    current=[r for r in old if r.get("date")==iso]
    if len(current)>=150: return {"status":"COMPLETE","date":iso,"rows":len(current),"source":"ALREADY_PRESENT"}
    p=fetch_json(PRICE_URL,{"date":ds,"type":"13","response":"json"})
    if str(p.get("stat","")).upper()!="OK": return {"status":"PENDING","reason":f"TWSE_ELECTRONICS_NOT_READY:{p.get('stat')}"}
    rows=[]
    try:
        fs,data=find_price_table(p); idx={f:i for i,f in enumerate(fs)}
        def v(r,*names):
            for n in names:
                i=idx.get(n)
                if i is not None and i<len(r): return clean(r[i])
            return ""
        for r in data:
            t=v(r,"證券代號").replace("=","").replace('"',"")
            if re.fullmatch(r"[1-9]\d{3}",t): rows.append({"date":iso,"ticker":t,"name":v(r,"證券名稱"),"open":v(r,"開盤價"),"high":v(r,"最高價"),"low":v(r,"最低價"),"close":v(r,"收盤價"),"volume_shares":v(r,"成交股數","成交量"),"turnover_ntd":v(r,"成交金額")})
    except Exception as e: return {"status":"ERROR","reason":f"ELECTRONICS_PARSE:{type(e).__name__}:{e}"}
    if len(rows)<150: return {"status":"ERROR","reason":f"TWSE_ELECTRONICS_ROWS_TOO_FEW:{len(rows)}"}
    merged=[r for r in old if r.get("date")!=iso]+rows; merged.sort(key=lambda r:(r["date"],r["ticker"]))
    fields=["date","ticker","name","open","high","low","close","volume_shares","turnover_ntd"]
    s=io.StringIO(newline=""); w=csv.DictWriter(s,fieldnames=fields,lineterminator="\n"); w.writeheader(); w.writerows(merged); atomic_text(TW_HISTORY,s.getvalue())
    return {"status":"COMPLETE","date":iso,"rows":len(rows),"source":"TWSE_TYPE13"}


def ingest(target: date | None = None) -> dict:
    target=target or now_tw().date()
    if target.weekday()>=5: return {"status":"SKIP_WEEKEND","target_date":target.isoformat()}
    iso=target.isoformat(); folder=EOD_ROOT/target.strftime("%Y%m%d"); folder.mkdir(parents=True,exist_ok=True); status=load_status(folder,iso)
    results=[]; fatal=[]
    for leg in ("price","institutional","margin"):
        try: results.append(try_leg(folder,status,leg,target))
        except Exception as e:
            fatal.append({"leg":leg,"error":f"{type(e).__name__}:{e}"[:1000]}); status[f"{leg}_status"]="ERROR"; status[f"{leg}_error"]=fatal[-1]["error"]
    mother=materialize_mother_delta(folder,status,target)
    electronics={"status":"PENDING","reason":"PRICE_NOT_COMPLETE"}
    if status.get("price_status")=="COMPLETE":
        try: electronics=append_electronics_history(target)
        except Exception as e: electronics={"status":"ERROR","reason":f"{type(e).__name__}:{e}"[:1000]}
    status["electronics_history_status"]=electronics.get("status"); status["electronics_history"]=electronics
    complete=[x for x in ("price","institutional","margin") if status.get(f"{x}_status")=="COMPLETE"]
    pending=[x for x in ("price","institutional","margin") if status.get(f"{x}_status")!="COMPLETE"]
    status.update({"available_legs":complete,"pending_legs":pending,"three_leg_complete":len(complete)==3,"mother_append_status":mother.get("status"),"mother_receipt":mother,"formal_complete_day":len(complete)==3,"e2_price_history_ready":electronics.get("status")=="COMPLETE","last_run_at_taipei":now_tw().isoformat(),"last_run_results":results,"fatal_integrity_errors":fatal,"status":"ERROR" if fatal else ("COMPLETE" if len(complete)==3 else "PARTIAL")})
    atomic_json(folder/"status.json",status)
    print(json.dumps(status,ensure_ascii=False,indent=2))
    return status


def self_test() -> None:
    price=[{"Date":"2026-10-20","Ticker":"1001","Name":"A","VolumeShares":"10","TurnoverTWD":"100","Open":"9","High":"11","Low":"8","Close":"10"},{"Date":"2026-10-20","Ticker":"1002","Name":"B","VolumeShares":"20","TurnoverTWD":"200","Open":"19","High":"21","Low":"18","Close":"20"}]
    inst=[{"Date":"2026-10-20","Ticker":"1001","ForeignNet":"5","TrustNet":"1","TotalNet":"6"}]
    rows=build_mother_rows(price,inst,[])
    assert len(rows)==2
    assert rows[0]["ForeignNet"]=="5" and rows[0]["Margin_MarginBalance"]==""
    assert rows[1]["ForeignNet"]=="" and rows[1]["Margin_MarginBalance"]==""
    assert canonical_rows_sha(price,["Date","Ticker","Name","VolumeShares","TurnoverTWD","Open","High","Low","Close"])==canonical_rows_sha(list(reversed(price)),["Date","Ticker","Name","VolumeShares","TurnoverTWD","Open","High","Low","Close"])
    print(json.dumps({"self_test":"PASS","atomic_per_leg_commit":True,"no_wait_for_margin":True,"price_row_universe":True,"missing_evidence_null":True,"formal_complete_day_requires_three_legs":True,"q017_0901_reconstruction":False},ensure_ascii=False))


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--mode",choices=["ingest","self-test"],required=True); ap.add_argument("--date")
    a=ap.parse_args()
    if a.mode=="self-test": self_test(); return 0
    target=date.fromisoformat(a.date) if a.date else None
    out=ingest(target)
    return 2 if out.get("fatal_integrity_errors") else 0

if __name__=="__main__": raise SystemExit(main())
