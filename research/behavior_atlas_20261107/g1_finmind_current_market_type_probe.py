#!/usr/bin/env python3
"""G1 data-capability probe ONLY: current FinMind TaiwanStockInfo market types.

Do NOT treat snapshot date/type as point-in-time listing, delisting or security
identity; no price, factor, model, return, or behavioral target is queried.
"""
import collections,datetime,json,os,re,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path("/tmp/hengce-behavior-g1-info")
ROOT.mkdir(parents=True,exist_ok=True)
out={
  "artifact":"HENGCE_G1_FINMIND_MARKET_TYPE_CAPABILITY_PROBE",
  "date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "status":"BLOCKED_NOT_TESTED","source":"FinMind TaiwanStockInfo",
  "historical_pit_listing_authority":False,"security_common_stock_identity_authority":False,
  "no_model_no_return_query":True,
}
try:
  token=os.environ.get("FINMIND_TOKEN","").strip()
  if not token:raise RuntimeError("FINMIND_TOKEN_MISSING")
  params=urllib.parse.urlencode({"dataset":"TaiwanStockInfo"})
  req=urllib.request.Request("https://api.finmindtrade.com/api/v4/data?"+params,headers={"Authorization":"Bearer "+token})
  with urllib.request.urlopen(req,timeout=120) as response:
    body=json.load(response)
  data=body.get("data") if isinstance(body,dict) else None
  if body.get("status")!=200 or not isinstance(data,list):raise RuntimeError("DATASET_UNAVAILABLE")
  types=collections.Counter()
  latest={}
  dates=collections.Counter()
  every4=0
  for r in data:
    for k in ["stock_id","stock_name","type","date","industry_category"]:
      if k not in r:raise ValueError("SCHEMA_MISSING_"+k)
    t=str(r["stock_id"])
    if not re.fullmatch(r"[1-9]\d{3}",t):continue
    every4+=1
    dates[str(r["date"])[:4]]+=1
    types[str(r["type"])]+=1
    if t not in latest or str(r["date"])>str(latest[t]["date"]):latest[t]=r
  latesttypes=collections.Counter(str(r["type"]) for r in latest.values())
  transition=collections.Counter()
  before=collections.defaultdict(set)
  for r in data:
    t=str(r["stock_id"])
    if re.fullmatch(r"[1-9]\d{3}",t):before[t].add(str(r["type"]))
  samples={}
  for t in ("1101","2330","1258","1240","9103","2881","2891"):
    r=latest.get(t,{})
    samples[t]={k:r.get(k) for k in ("stock_name","type","date","industry_category")} if r else "not_in_response"
  out.update(status="PASS_METADATA_CAPABILITY_ONLY",total_dataset_rows=len(data),four_digit_rows=every4,
   distinct_four_digit_tickers=len(latest),
   four_digit_type_counts=dict(types),four_digit_latest_type_counts=dict(latesttypes),
   rows_by_record_year=dict(dates),
   ids_with_multiple_market_types=sum(len(v)>1 for v in before.values()),
   examples=samples,
   caution="Latest FinMind type/date is not historical listed common-stock identity; delisted historical universe unknown.")
except Exception as e:
  out.update(status="BLOCKED_FAIL_CLOSED",blocker=str(e).splitlines()[0][:140])
finally:
  (ROOT/"manifest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print("HENGCE_G1_INFO_RESULT",json.dumps(out,ensure_ascii=False),flush=True)
raise SystemExit(0 if out["status"]=="PASS_METADATA_CAPABILITY_ONLY" else 2)
