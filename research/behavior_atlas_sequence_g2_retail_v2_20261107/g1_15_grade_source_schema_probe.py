#!/usr/bin/env python3
"""G1 source schema probe for archived 15-level TDCC account counts.
Only raw field headers and example masked rows; no modeling or returns.
"""
import csv,io,zipfile,json,urllib.request,os
from pathlib import Path
base="https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/main/"
files=[
"ownership/tdcc/20261106/tdcc_1_5_raw.csv",
"ownership/tdcc/backfill_candidate/wirelessr/20261022/tdcc_1_5_raw.csv.gz",
"ownership/tdcc/backfill_candidate/full_market_2025_tail/20251107/raw_html.zip",
"ownership/tdcc/backfill_candidate/full_market_2026_jan_apr/20260424/raw_html.zip"]
def fetch(p):
  req=urllib.request.Request(base+p,headers={"User-Agent":"HENGCE-G1-source-audit"})
  with urllib.request.urlopen(req,timeout=90) as r:return r.read()
for f in files:
 try:
  b=fetch(f);print("SOURCE",f,"BYTES",len(b))
  if f.endswith(".csv") or f.endswith(".csv.gz"):
   import gzip
   text=(gzip.decompress(b) if f.endswith(".gz") else b).decode("utf-8-sig","replace")
   rows=csv.reader(io.StringIO(text))
   for i in range(3):
    r=next(rows)
    print("ROW",i,repr(r[:15]),"FIELDS",len(r))
  else:
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    names=z.namelist();print("ZIP_NAMES",len(names),names[:5])
    for n in names[:2]:
     raw=z.read(n);txt=raw.decode("utf-8-sig","replace")
     print("ZIP_ENTRY",n,"BYTES",len(raw),"HEAD",repr(txt[:260]))
 except Exception as e:print("SOURCE_ERROR",f,type(e).__name__,str(e)[:140])
