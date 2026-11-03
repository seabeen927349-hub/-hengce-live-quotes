#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

TZ = ZoneInfo("Asia/Taipei")
NOT_BEFORE = time(20, 15)
ROOT = Path("research/broker_prospective_20261103/captures")
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
TWSE_MASTER_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
ELECTRONICS_CODES = {"24","25","26","27","28","29","30","31"}
CORP_DATASETS = {
    "TaiwanStockDividendResult": "reference_price",
    "TaiwanStockSplitPrice": "after_price",
    "TaiwanStockCapitalReductionReferencePrice": "PostReductionReferencePrice",
    "TaiwanStockParValueChange": "after_ref_close",
}
FLOW_DATASET = "TaiwanStockInstitutionalInvestorsBuySellWide"
PRICE_DATASET = "TaiwanStockPrice"
TRADING_DATE_DATASET = "TaiwanStockTradingDate"


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for ch in iter(lambda: f.read(1024*1024), b""):
            h.update(ch)
    return h.hexdigest()


def canonical_json_sha(obj) -> str:
    return sha_bytes(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def norm_stock(x) -> str:
    s = str(x or "").strip()
    if re.fullmatch(r"\d+(?:\.0+)?", s):
        s = s.split(".")[0]
        if len(s) <= 4:
            return s.zfill(4)
    return s


def norm_industry(x) -> str:
    s = str(x or "").strip()
    m = re.match(r"^(\d{2})", s)
    return m.group(1) if m else s


def pick(row: dict, keys: list[str]):
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def get_public_json(url: str, timeout=60):
    r = requests.get(url, headers={"Accept":"application/json","User-Agent":"HENGCE-BROKER-PROSPECTIVE/1.0"}, timeout=timeout)
    r.raise_for_status()
    return r, r.json()


def finmind(token: str, dataset: str, start_date: str | None = None, end_date: str | None = None):
    params = {"dataset": dataset}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    r = requests.get(FINMIND_URL, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=90)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError(f"FINMIND_BAD_PAYLOAD:{dataset}:{payload}")
    data = payload["data"]
    if not isinstance(data, list):
        raise RuntimeError(f"FINMIND_DATA_NOT_LIST:{dataset}")
    rec = {
        "dataset": dataset,
        "query_start_date": start_date,
        "query_end_date": end_date,
        "retrieval_timestamp_taipei": datetime.now(TZ).isoformat(),
        "http_bytes_sha256": sha_bytes(r.content),
        "logical_data_sha256": canonical_json_sha(data),
        "row_count": len(data),
    }
    return data, rec


def all_rows_exact_date(token: str, dataset: str, d: str):
    rows, rec = finmind(token, dataset, d, d)
    exact = [r for r in rows if str(r.get("date","")) == d]
    rec["exact_event_date_row_count"] = len(exact)
    if rows and not exact:
        raise RuntimeError(f"DATE_MISMATCH:{dataset}:{d}")
    return exact, rec


def build_members(master_rows: list[dict]):
    out = {}
    for r in master_rows:
        code = norm_stock(pick(r, ["公司代號","公司代碼","證券代號","股票代號","Code"]))
        industry = norm_industry(pick(r, ["產業別","產業別代碼","IndustryCode","Industry"]))
        if re.fullmatch(r"[1-9]\d{3}", code) and industry in ELECTRONICS_CODES:
            out[code] = {
                "stock_id": code,
                "stock_name": str(pick(r, ["公司簡稱","公司名稱","證券名稱","Name"]) or "").strip(),
                "industry_code": industry,
            }
    if len(out) < 100:
        raise RuntimeError(f"CURRENT_TWSE_ELECTRONICS_TOO_SMALL:{len(out)}")
    return out


def number(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def price_rows_by_stock(rows, members, d):
    out = {}
    seen = set()
    for r in rows:
        sid = norm_stock(r.get("stock_id"))
        if sid not in members:
            continue
        key=(d,sid)
        if key in seen:
            raise RuntimeError(f"DUPLICATE_PRICE_ROW:{d}:{sid}")
        seen.add(key)
        out[sid] = {
            "close": number(r.get("close")),
            "open": number(r.get("open")),
            "turnover": number(r.get("Trading_money")),
            "volume": number(r.get("Trading_Volume")),
        }
    return out


def flow_rows_by_stock(rows, members, d):
    out = {}
    seen=set()
    for r in rows:
        sid=norm_stock(r.get("stock_id"))
        if sid not in members:
            continue
        key=(d,sid)
        if key in seen:
            raise RuntimeError(f"DUPLICATE_FLOW_ROW:{d}:{sid}")
        seen.add(key)
        buy_cols=[k for k in r if k.endswith("_buy")]
        sell_cols=[k for k in r if k.endswith("_sell")]
        if not buy_cols or not sell_cols:
            raise RuntimeError(f"FLOW_SCHEMA_MISSING_BUY_SELL:{d}:{sid}")
        vals=[number(r.get(k)) for k in buy_cols+sell_cols]
        if not all(np.isfinite(x) and x >= 0 for x in vals):
            raise RuntimeError(f"INVALID_FLOW_VALUE:{d}:{sid}")
        total_buy=sum(number(r.get(k)) for k in buy_cols)
        total_sell=sum(number(r.get(k)) for k in sell_cols)
        out[sid]=total_buy-total_sell
    return out


def action_ref_from_row(dataset, row):
    field=CORP_DATASETS[dataset]
    v=number(row.get(field))
    return v if np.isfinite(v) and v>0 else np.nan


def main():
    now=datetime.now(TZ)
    if now.time() < NOT_BEFORE:
        raise RuntimeError(f"TOO_EARLY_FOR_SELECTION_INPUT_CAPTURE:{now.isoformat()}")
    event_date=now.date().isoformat()
    token=os.environ.get("FINMIND_TOKEN")
    if not token:
        raise RuntimeError("FINMIND_TOKEN_MISSING")

    outdir=ROOT/event_date
    broker_receipt=outdir/"lineage_receipt.json"
    broker_panel=outdir/"broker_hhi_all_stock.csv"
    signal_path=outdir/"signal_input_preoutcome.csv"
    receipt_path=outdir/"selection_input_receipt.json"

    if not broker_receipt.exists() or not broker_panel.exists():
        raise RuntimeError("BROKER_FIRST_OBSERVED_CAPTURE_REQUIRED_BEFORE_SELECTION_INPUTS")

    if signal_path.exists() or receipt_path.exists():
        if not (signal_path.exists() and receipt_path.exists()):
            raise RuntimeError("PARTIAL_SELECTION_INPUT_CAPTURE_FAIL_CLOSED")
        receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("signal_input_sha256") != sha_file(signal_path):
            raise RuntimeError("EXISTING_SELECTION_INPUT_HASH_MISMATCH")
        print(json.dumps({"status":"ALREADY_CAPTURED_IMMUTABLE","event_date":event_date,"signal_input_sha256":sha_file(signal_path)}))
        return 0

    source_records=[]

    mr, master=get_public_json(TWSE_MASTER_URL)
    master_rec={
        "dataset":"TWSE_t187ap03_L",
        "retrieval_timestamp_taipei":datetime.now(TZ).isoformat(),
        "http_bytes_sha256":sha_bytes(mr.content),
        "logical_data_sha256":canonical_json_sha(master),
        "row_count":len(master) if isinstance(master,list) else None,
    }
    source_records.append(master_rec)
    if not isinstance(master,list):
        raise RuntimeError("TWSE_MASTER_NOT_LIST")
    members=build_members(master)

    trading_rows, tr_rec=finmind(token, TRADING_DATE_DATASET)
    source_records.append(tr_rec)
    trading_dates=sorted({str(r.get("date")) for r in trading_rows if r.get("date")})
    if event_date not in trading_dates:
        raise RuntimeError(f"EVENT_DATE_NOT_TWSE_TRADING_DATE:{event_date}")
    upto=[d for d in trading_dates if d <= event_date]
    if len(upto) < 21:
        raise RuntimeError("INSUFFICIENT_TRADING_DATE_HISTORY")
    sessions=upto[-21:]
    return_dates=sessions[1:]
    flow_dates=sessions[-5:]

    prices={}
    for d in sessions:
        rows, rec=all_rows_exact_date(token, PRICE_DATASET, d)
        source_records.append(rec)
        prices[d]=price_rows_by_stock(rows,members,d)

    flows={}
    for d in flow_dates:
        rows, rec=all_rows_exact_date(token, FLOW_DATASET, d)
        source_records.append(rec)
        flows[d]=flow_rows_by_stock(rows,members,d)

    ref_candidates={}
    action_conflicts=[]
    for d in return_dates:
        for dataset in CORP_DATASETS:
            rows, rec=all_rows_exact_date(token,dataset,d)
            source_records.append(rec)
            for row in rows:
                sid=norm_stock(row.get("stock_id"))
                if sid not in members:
                    continue
                ref=action_ref_from_row(dataset,row)
                if not np.isfinite(ref):
                    raise RuntimeError(f"CORP_ACTION_REF_INVALID:{dataset}:{d}:{sid}")
                ref_candidates.setdefault((d,sid),[]).append((dataset,float(ref)))
    action_ref={}
    for key, vals in ref_candidates.items():
        refs=[v for _,v in vals]
        base=refs[0]
        if any(abs(v-base) > max(1e-8,1e-8*abs(base)) for v in refs[1:]):
            action_conflicts.append({"date":key[0],"stock_id":key[1],"refs":vals})
        else:
            action_ref[key]=base

    rows=[]
    conflict_keys={(c["date"],c["stock_id"]) for c in action_conflicts}
    for sid, meta in sorted(members.items()):
        reason=[]
        series=[]
        for d in sessions:
            pr=prices[d].get(sid)
            series.append((d,pr))
        current=series[-1][1]
        if current is None or not np.isfinite(current["close"]) or current["close"] <= 0:
            reason.append("INVALID_CURRENT_CLOSE")

        rets=[]
        for j in range(1,len(series)):
            d,pr=series[j]
            _,prev=series[j-1]
            if pr is None or prev is None:
                rets.append(np.nan); continue
            close=pr["close"]; prev_close=prev["close"]
            if not np.isfinite(close) or close<=0 or not np.isfinite(prev_close) or prev_close<=0:
                rets.append(np.nan); continue
            if (d,sid) in conflict_keys:
                rets.append(np.nan); continue
            ref=action_ref.get((d,sid),prev_close)
            if not np.isfinite(ref) or ref<=0:
                rets.append(np.nan); continue
            rets.append(float(math.log(close/ref)))

        if len(rets)!=20 or not all(np.isfinite(x) for x in rets):
            reason.append("INVALID_20_RETURN_PATH")
            mom20=np.nan; rev5=np.nan
        else:
            mom20=float(sum(rets))
            rev5=float(sum(rets[-5:]))

        turns=[prices[d].get(sid,{}).get("turnover",np.nan) for d in return_dates]
        valid_turns=[x for x in turns if np.isfinite(x) and x>=0]
        liq20=float(np.median(valid_turns)) if len(valid_turns)>=18 else np.nan
        if not np.isfinite(liq20):
            reason.append("LIQ20_INSUFFICIENT")

        flow_ok=True
        flow_num=0.0; flow_den=0.0
        for d in flow_dates:
            pr=prices[d].get(sid)
            net=flows[d].get(sid)
            if pr is None or net is None or not np.isfinite(pr["volume"]) or pr["volume"]<0 or not np.isfinite(net):
                flow_ok=False; break
            flow_num += float(net)
            flow_den += float(pr["volume"])
        agg_flow5=float(flow_num/flow_den) if flow_ok and flow_den>0 else np.nan

        eligible=(not reason) and np.isfinite(mom20) and np.isfinite(liq20)
        rows.append({
            "date":event_date,
            "ticker":sid,
            "stock_name":meta["stock_name"],
            "industry_code":meta["industry_code"],
            "u100_eligible":bool(eligible),
            "MOM20":mom20,
            "REV5_LOG":rev5,
            "LIQ20":liq20,
            "AGG_FLOW5":agg_flow5,
            "eligibility_status":"PASS" if eligible else "+".join(sorted(set(reason))) or "FAIL",
        })

    universe=pd.DataFrame(rows)
    elig=universe[universe["u100_eligible"]].copy()
    elig=elig.sort_values(["LIQ20","ticker"],ascending=[False,True],kind="stable")
    if len(elig)<100:
        raise RuntimeError(f"U100_ELIGIBLE_LT_100:{len(elig)}")
    u100=elig.head(100).copy()
    u100["u100_rank"]=np.arange(1,101)

    bp=pd.read_csv(broker_panel,dtype={"stock_id":str})
    bp["stock_id"]=bp["stock_id"].map(norm_stock)
    if bp["stock_id"].duplicated().any():
        raise RuntimeError("BROKER_PANEL_DUPLICATE_STOCK")
    bp=bp.rename(columns={"stock_id":"ticker"})
    u100=u100.merge(bp[["ticker","status","broker_gross_hhi_1d","positive_gross_branch_count"]],on="ticker",how="left",validate="one_to_one")
    u100=u100.rename(columns={"status":"broker_status","broker_gross_hhi_1d":"BROKER_GROSS_HHI_1D"})
    complete=(
        (u100["broker_status"]=="PASS")
        & np.isfinite(pd.to_numeric(u100["BROKER_GROSS_HHI_1D"],errors="coerce"))
        & np.isfinite(pd.to_numeric(u100["MOM20"],errors="coerce"))
        & np.isfinite(pd.to_numeric(u100["REV5_LOG"],errors="coerce"))
        & np.isfinite(pd.to_numeric(u100["LIQ20"],errors="coerce"))
        & np.isfinite(pd.to_numeric(u100["AGG_FLOW5"],errors="coerce"))
    )
    u100["primary_input_complete"]=complete
    complete_n=int(complete.sum())
    status="PASS_PROSPECTIVE_PREOUTCOME_INPUT_FROZEN" if complete_n>=95 else "INPUT_GATE_FAIL_CLOSED"

    outdir.mkdir(parents=True,exist_ok=True)
    tmp=outdir/".signal_input_preoutcome.csv.tmp"
    cols=["date","ticker","u100_rank","MOM20","REV5_LOG","LIQ20","AGG_FLOW5","BROKER_GROSS_HHI_1D","positive_gross_branch_count","broker_status","primary_input_complete"]
    u100[cols].to_csv(tmp,index=False,lineterminator="\n")
    tmp.replace(signal_path)
    signal_sha=sha_file(signal_path)

    broker_obj=json.loads(broker_receipt.read_text(encoding="utf-8"))
    receipt={
        "system":"HENGCE",
        "artifact":"BROKER_PROSPECTIVE_PREOUTCOME_SIGNAL_INPUT_RECEIPT",
        "status":status,
        "authority":"PREOUTCOME_RESEARCH_INPUT_ONLY; NO_FORWARD_RETURN_LOADED; NO_TRADING_OR_PRODUCTION_AUTHORITY",
        "event_date":event_date,
        "retrieval_timestamp_taipei":datetime.now(TZ).isoformat(),
        "selection_rule":"FROZEN_SELECTION_CHALLENGE_U100_REPLICATION",
        "membership_source":"TWSE t187ap03_L current-date snapshot; TWSE-listed 4-digit industry codes 24-31",
        "electronics_member_count":len(members),
        "trading_sessions":sessions,
        "u100_size":len(u100),
        "u100_complete_primary_input_count":complete_n,
        "minimum_complete_primary_input_required":95,
        "broker_source_revision_class":broker_obj.get("source_revision_class"),
        "broker_physical_object_sha256":broker_obj.get("physical_object_sha256"),
        "broker_logical_content_sha256":broker_obj.get("logical_content_sha256"),
        "broker_derived_panel_sha256":broker_obj.get("derived_panel_sha256"),
        "source_query_receipts":source_records,
        "corporate_action_reference_conflict_count":len(action_conflicts),
        "corporate_action_reference_conflicts":action_conflicts,
        "signal_input_path":str(signal_path),
        "signal_input_sha256":signal_sha,
        "raw_vendor_rows_persisted":False,
        "forward_returns_loaded":False,
        "outcome_columns_present":False,
        "earliest_decision_time":"next TWSE open after event date",
        "hard_lock":"IMMUTABLE_FIRST_OBSERVED_SELECTION_INPUT; NO_RETROACTIVE_OVERWRITE",
        "preregistration_path":"research/broker_prospective_20261103/PREREGISTRATION_PROSPECTIVE.json",
    }
    tmpj=outdir/".selection_input_receipt.json.tmp"
    tmpj.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmpj.replace(receipt_path)
    print(json.dumps({"status":status,"event_date":event_date,"electronics_member_count":len(members),"u100_size":len(u100),"complete_primary_input_count":complete_n,"signal_input_sha256":signal_sha},ensure_ascii=False))
    if status!="PASS_PROSPECTIVE_PREOUTCOME_INPUT_FROZEN":
        return 2
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":f"{type(exc).__name__}:{exc}"},ensure_ascii=False),file=sys.stderr)
        raise
