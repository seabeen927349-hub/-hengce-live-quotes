#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,hashlib,json,re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'ownership'/'tdcc'
OUT=BASE/'consolidated_candidate'
OUT.mkdir(parents=True,exist_ok=True)
TZ=ZoneInfo('Asia/Taipei')
COLS=['SnapshotDate','Ticker','Big400Pct','Big1000Pct','Big400Holders','Big400Shares','Big1000Holders','Big1000Shares','TotalHolders','TotalShares','SourceTier','SourcePath','RawSHA256','ConflictFlag']

def val(x,typ=float):
 s=str(x or '').strip()
 if not s:return None
 try:return typ(float(s)) if typ is int else typ(s)
 except:return None

def load_csv(path, tier, rawsha=None):
 rows=[]
 with path.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   d=str(r.get('SnapshotDate','')).replace('-','');t=str(r.get('Ticker','')).strip()
   if not re.fullmatch(r'\d{8}',d) or not re.fullmatch(r'[1-9]\d{3}',t):continue
   rows.append({'SnapshotDate':d,'Ticker':t,'Big400Pct':val(r.get('Big400Pct')),'Big1000Pct':val(r.get('Big1000Pct')),'Big400Holders':val(r.get('Big400Holders'),int),'Big400Shares':val(r.get('Big400Shares'),int),'Big1000Holders':val(r.get('Big1000Holders'),int),'Big1000Shares':val(r.get('Big1000Shares'),int),'TotalHolders':val(r.get('TotalHolders'),int),'TotalShares':val(r.get('TotalShares'),int),'SourceTier':tier,'SourcePath':str(path.relative_to(ROOT)),'RawSHA256':rawsha or r.get('RawSHA256') or '','ConflictFlag':''})
 return rows

def receipt_sha(path):
 try:
  o=json.loads(path.read_text(encoding='utf-8'))
  return o.get('raw_uncompressed_sha256') or o.get('raw_sha256') or o.get('source_sha256') or ''
 except:return ''

def key(r):return (r['SnapshotDate'],r['Ticker'])
def sig(r):return tuple(r.get(x) for x in ['Big400Pct','Big1000Pct','Big400Holders','Big400Shares','Big1000Holders','Big1000Shares','TotalHolders','TotalShares'])

def main():
 sources=[]
 # lowest first; later tiers replace earlier ones.
 lisa=BASE/'backfill_candidate'/'lisa_access_db'/'lisa_access_db_big400_history.csv'
 if lisa.exists():sources.append((10,'ACCESS_DB_DERIVED',lisa,''))
 # NCHC raw snapshots. Prefer revise on same date if conflicts, but flag it.
 nchc=BASE/'backfill_candidate'/'nchc'
 if nchc.exists():
  for p in sorted(nchc.glob('*/*_ownership_4d.csv')):
   rec=p.with_name(p.name.replace('_ownership_4d.csv','_receipt.json'))
   tier='NCHC_RAW_REVISE' if '73eafd49' in p.name else 'NCHC_RAW'
   rank=31 if tier.endswith('REVISE') else 30
   sources.append((rank,tier,p,receipt_sha(rec)))
 # public raw archive; 20261022 was formally cross-verified against official summary.
 wa=BASE/'backfill_candidate'/'wirelessr'
 if wa.exists():
  for p in sorted(wa.glob('*'+'/tdcc_ownership_4d.csv')):
   rec=p.with_name('receipt.json');ro=json.loads(rec.read_text()) if rec.exists() else {}
   verified=ro.get('verification')=='VERIFIED_AGAINST_OFFICIAL_SUMMARY'
   sources.append((50 if not verified else 70,'RAW_ARCHIVE_VERIFIED_OFFICIAL' if verified else 'RAW_ARCHIVE',p,ro.get('raw_uncompressed_sha256','')))
 # official HENGCE TDCC vessel snapshots
 for p in sorted(BASE.glob('20*/tdcc_ownership_4d.csv')):
  rec=p.with_name('receipt.json');sources.append((100,'TDCC_OFFICIAL',p,receipt_sha(rec)))

 best={};hist={};source_counts={}
 for rank,tier,p,rh in sorted(sources,key=lambda x:x[0]):
  rr=load_csv(p,tier,rh);source_counts[tier]=source_counts.get(tier,0)+len(rr)
  for r in rr:
   k=key(r);hist.setdefault(k,[]).append((rank,tier,sig(r)))
   old=best.get(k)
   if old is None or rank>=old[0]:best[k]=(rank,r)
 # conflicts = overlapping sources disagree on any metric both sides actually contain
 conflict_keys=0
 for k,items in hist.items():
  conflict=False
  for i in range(len(items)):
   for j in range(i+1,len(items)):
    a=items[i][2];b=items[j][2]
    for av,bv in zip(a,b):
     if av is not None and bv is not None and av!=bv:
      # pct round tolerance only
      if isinstance(av,float) or isinstance(bv,float):
       if abs(float(av)-float(bv))<=1e-6:continue
      conflict=True;break
    if conflict:break
   if conflict:break
  if conflict:
   conflict_keys+=1;best[k][1]['ConflictFlag']='SOURCE_DISAGREEMENT'
 rows=[v[1] for k,v in sorted(best.items())]
 # no duplicate guarantee
 if len(rows)!=len({key(r) for r in rows}):raise SystemExit('DUPLICATE_KEY')
 outcsv=OUT/'tdcc_fourth_leg_best_available.csv'
 with outcsv.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(rows)
 raw=outcsv.read_bytes();gz=gzip.compress(raw,compresslevel=9,mtime=0);(OUT/'tdcc_fourth_leg_best_available.csv.gz').write_bytes(gz);outcsv.unlink()
 dates=sorted({r['SnapshotDate'] for r in rows})
 tiers={}
 for r in rows:tiers[r['SourceTier']]=tiers.get(r['SourceTier'],0)+1
 manifest={'system':'HENGCE','artifact':'TDCC_FOURTH_LEG_CONSOLIDATED_CANDIDATE','status':'COMPLETE','generated_at_taipei':datetime.now(TZ).replace(microsecond=0).isoformat(),'rows':len(rows),'unique_snapshots':len(dates),'first_snapshot':dates[0] if dates else None,'last_snapshot':dates[-1] if dates else None,'years':sorted({d[:4] for d in dates}),'selected_source_tiers':tiers,'raw_loaded_source_rows':source_counts,'overlap_conflict_keys':conflict_keys,'output_sha256_uncompressed':hashlib.sha256(raw).hexdigest(),'output_sha256_gzip':hashlib.sha256(gz).hexdigest(),'authority':'RESEARCH_BACKFILL_CANDIDATE_NO_CANONICAL_AUTHORITY','precedence':'TDCC_OFFICIAL > VERIFIED_RAW_ARCHIVE > RAW_ARCHIVE > NCHC_RAW_REVISE > NCHC_RAW > ACCESS_DB_DERIVED','pit_policy':'WEEKLY_SNAPSHOT_ONLY; DO NOT BACKFILL/FORWARD-FILL AS DAILY KNOWLEDGE','missing_fields_policy':'LEAVE_NULL_DO_NOT_RECONSTRUCT'}
 (OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (OUT/'dates.json').write_text(json.dumps(dates,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(manifest,ensure_ascii=False))
if __name__=='__main__':main()
