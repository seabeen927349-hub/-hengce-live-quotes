#!/usr/bin/env python3
"""TWSE original-vessel data helpers only; no selection/ranking code."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
TZ=ZoneInfo("Asia/Taipei")
ROOT=Path(__file__).resolve().parents[1]
TWSE_PRICE="https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TWSE_INST="https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN="https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
UA={"User-Agent":"Mozilla/5.0 HENGCE-ORIGINAL-EOD-DATA/1.0"}
def now_tw():return datetime.now(TZ)
def clean(x):return "" if x is None else str(x).replace(",","").strip()
def num(x):
    try:return float(str(x).replace(",","").strip())
    except (ValueError,TypeError):return None
def get_json(url,params=None,timeout=45):
    if url not in {TWSE_PRICE,TWSE_INST,TWSE_MARGIN}:
        raise ValueError("EOD_SHARED_HELPERS_ONLY_OFFICIAL_TWSE_ENDPOINTS")
    r=requests.get(url,params=params,headers={**UA,"Accept":"application/json","Referer":"https://www.twse.com.tw/"},timeout=timeout)
    r.raise_for_status()
    return r.json()
def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
