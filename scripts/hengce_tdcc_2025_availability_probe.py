#!/usr/bin/env python3
import json, requests
from pathlib import Path
# Import the verified ordinal runner first; it patches the base parser to use the official TDCC `序` column.
import hengce_tdcc_monster_pit_backfill_runner as runner

tdcc = runner.m

DATES=['20251031','20251107','20251114','20251121','20251128','20251205','20251212','20251219','20251226']
OUT=Path('out/tdcc_2025_probe'); OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-TDCC-2025-PROBE/1.1','Referer':tdcc.ENDPOINT,'Accept-Language':'zh-TW,zh;q=0.9,en;q=0.5'})
rows=[]
for d in DATES:
    try:
        raw,text,sm=tdcc.fetch_one(s,'2330',d)
        rows.append({'ReferenceDate':d,'status':'OK','Big400Holders':sm['Big400Holders'],'Big400Shares':sm['Big400Shares'],'Big1000Holders':sm['Big1000Holders'],'Big1000Shares':sm['Big1000Shares'],'TotalHolders':sm['TotalHolders']})
        print('OK',d,sm['Big400Shares'],sm['Big1000Shares'],flush=True)
    except Exception as e:
        rows.append({'ReferenceDate':d,'status':'ERROR','error':f'{type(e).__name__}:{e}'})
        print('ERROR',d,type(e).__name__,e,flush=True)
manifest={'system':'HENGCE','artifact':'TDCC_2025_LATE_SNAPSHOT_AVAILABILITY_PROBE','ticker':'2330','dates':DATES,'rows':rows,'all_ok':all(r['status']=='OK' for r in rows),'parser':'VERIFIED_ORDINAL_COLUMN_RUNNER','authority':'RESEARCH_AVAILABILITY_PROBE_ONLY_NO_MODEL_AUTHORITY'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
if not manifest['all_ok']:
    raise SystemExit('FAIL_CLOSED_TDCC_2025_SNAPSHOT_GAP')
