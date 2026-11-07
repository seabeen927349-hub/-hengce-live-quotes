#!/usr/bin/env python3
"""Inspect TDCC original HTML tables in 2025/2026, without output or return targets."""
import urllib.request,io,zipfile,csv,collections
from bs4 import BeautifulSoup
ROOT="https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/main/"
items=[
"ownership/tdcc/backfill_candidate/full_market_2025_tail/20251107/raw_html.zip",
"ownership/tdcc/backfill_candidate/full_market_2026_jan_apr/20260424/raw_html.zip"]
for u in items:
 req=urllib.request.Request(ROOT+u,headers={"User-Agent":"HENGCE-official-holder-audit"})
 b=urllib.request.urlopen(req,timeout=90).read()
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  nm="valid/2330.html"
  assert nm in z.namelist(),nm
  soup=BeautifulSoup(z.read(nm),"lxml")
  print("SAMPLE",u,"html_bytes",len(z.read(nm)),"table_count",len(soup.find_all('table')))
  for i,t in enumerate(soup.find_all("table")):
   rows=[[x.get_text(" ",strip=True) for x in tr.find_all(["td","th"])] for tr in t.find_all("tr")]
   print("TABLE",i,"numrows",len(rows),"first_5_rows",str(rows[:5])[:1700],"last_2",str(rows[-2:])[:450])
   if len(rows)>15:
    print("TABLE_CONTENT",str(rows[:22])[:3600])
