#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,re,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta
from pathlib import Path
import requests

URL='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
UA={'User-Agent':'Mozilla/5.0 HENGCE-E2-PROFIT-MAX/1.0','Accept':'text/csv,application/json'}

def sha256(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def parse_csv(content:bytes):
 text=None
 for enc in ('utf-8-sig','utf-8','cp950','big5'):
  try:text=content.decode(enc);break
  except UnicodeDecodeError:pass
 if text is None:text=content.decode('utf-8',errors='replace')
 rows=list(csv.reader(text.splitlines()));hi=None
 for i,r in enumerate(rows):
  s='|'.join(r)
  if '證券代號' in s and '證券名稱' in s and '收盤價' in s:hi=i;break
 if hi is None:return []
 hdr=[x.strip().replace('\ufeff','') for x in rows[hi]];out=[]
 for r in rows[hi+1:]:
  if len(r)<2:continue
  r=r+['']*(len(hdr)-len(r));d={hdr[j]:r[j].strip() for j in range(len(hdr))}
  t=d.get('證券代號','').replace('=','').replace('"','').strip();n=d.get('證券名稱','').strip()
  if re.fullmatch(r'\d{4}',t) and n:out.append((t,n))
 return out

def fetch(d:date):
 ds=d.strftime('%Y%m%d');last=''
 for k in range(4):
  try:
   r=requests.get(URL,params={'date':ds,'type':'13','response':'csv'},headers=UA,timeout=(8,30))
   if r.status_code==200 and r.content:
    rows=parse_csv(r.content)
    if rows:
     u={t:n for t,n in rows}
     if len(u)<150:return d,'REVIEW',u,f'ROW_COUNT_{len(u)}'
     return d,'PASS',u,''
    return d,'NO_DATA',{},''
   last=f'HTTP_{r.status_code}'
  except Exception as e:last=repr(e)
  time.sleep(min(8,1.5**k))
 return d,'ERROR',{},last

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',default='2023-01-01');ap.add_argument('--end',default='2026-10-19');ap.add_argument('--out',default='research/e2_profit_max/membership');ap.add_argument('--workers',type=int,default=6);a=ap.parse_args()
 s=date.fromisoformat(a.start);e=date.fromisoformat(a.end);days=[];d=s
 while d<=e:
  if d.weekday()<5:days.append(d)
  d+=timedelta(days=1)
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);year_rows={};qa=[]
 with ThreadPoolExecutor(max_workers=a.workers) as ex:
  fs={ex.submit(fetch,d):d for d in days}
  for i,f in enumerate(as_completed(fs),1):
   d,st,rows,err=f.result();qa.append({'date':d.isoformat(),'status':st,'members':len(rows),'error':err})
   if st=='PASS':
    for t,n in rows.items():year_rows.setdefault(d.year,[]).append((d.isoformat(),t,n))
   if i%50==0:print(f'{i}/{len(days)}',flush=True)
 qa.sort(key=lambda x:x['date']);files={}
 for y,rows in sorted(year_rows.items()):
  rows.sort();p=out/f'twse_electronics_membership_{y}.csv'
  with p.open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.writer(f);w.writerow(['Date','Ticker','Name']);w.writerows(rows)
  files[str(y)]={'path':str(p),'rows':len(rows),'dates':len(set(x[0] for x in rows)),'sha256':sha256(p)}
 qp=out/'membership_qa.csv'
 with qp.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['date','status','members','error']);w.writeheader();w.writerows(qa)
 rec={'system':'HENGCE','engine':'E2_PROFIT_MAX','artifact':'PIT_TWSE_ELECTRONICS_MEMBERSHIP','source':'TWSE MI_INDEX type=13 official daily electronics table','start':a.start,'end':a.end,'policy':'POINT_IN_TIME_OBSERVED_ON_DATE_NO_CURRENT_CONSTITUENT_BACKFILL','weekday_candidates':len(days),'pass_days':sum(x['status']=='PASS' for x in qa),'no_data_days':sum(x['status']=='NO_DATA' for x in qa),'review_days':sum(x['status']=='REVIEW' for x in qa),'error_days':sum(x['status']=='ERROR' for x in qa),'files':files,'qa_sha256':sha256(qp)}
 rec['hard_gate']='PASS' if rec['review_days']==0 and rec['error_days']==0 and rec['pass_days']>=900 else 'FAIL_REVIEW'
 rp=out/'membership_receipt.json';rp.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(rec,ensure_ascii=False,indent=2));raise SystemExit(0 if rec['hard_gate']=='PASS' else 2)
if __name__=='__main__':main()
