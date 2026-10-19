#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,random
from datetime import date,timedelta
from pathlib import Path
import requests

URL='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
UA={'User-Agent':'Mozilla/5.0 HENGCE-E2-PIT-V2/1.1','Accept':'application/json,text/plain,*/*','Referer':'https://www.twse.com.tw/'}

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def parse_stock_table(z):
    for t in z.get('tables') or []:
        fs=t.get('fields') or []
        if '證券代號' in fs and '證券名稱' in fs and '收盤價' in fs:
            i0=fs.index('證券代號'); i1=fs.index('證券名稱')
            out={}
            for r in (t.get('data') or t.get('records') or []):
                if not isinstance(r,(list,tuple)) or max(i0,i1)>=len(r): continue
                tk=str(r[i0]).replace('=','').replace('"','').strip(); nm=str(r[i1]).strip()
                if re.fullmatch(r'\d{4}',tk) and nm: out[tk]=nm
            return out
    return None

def request_json(s,ds,type_):
    r=s.get(URL,params={'date':ds,'type':type_,'response':'json'},timeout=(10,45))
    if r.status_code!=200: raise RuntimeError(f'HTTP_{r.status_code}')
    return r.json()

def confirm_nontrading(s,ds):
    """Fail closed: an empty type=13 table is NO_DATA only if ALLBUT0999 is also empty."""
    try:
        z=request_json(s,ds,'ALLBUT0999')
        stat=str(z.get('stat') or ''); got=str(z.get('date') or '')
        rows=parse_stock_table(z)
        if stat=='OK' and rows is not None and len(rows)>=500:
            return False,'ALLBUT0999_HAS_TRADING_ROWS'
        if ('沒有符合條件' in stat or '查無資料' in stat or not got or rows is None or len(rows)==0):
            return True,'OFFICIAL_ALLBUT0999_EMPTY'
        return False,f'ALLBUT0999_AMBIGUOUS:{stat}:{got}:{0 if rows is None else len(rows)}'
    except Exception as e:
        return False,f'NONTRADING_CONFIRM_ERROR:{type(e).__name__}:{e}'

def fetch_day(s:requests.Session,d:date,retries:int,sleep_s:float):
    ds=d.strftime('%Y%m%d'); last=''
    for k in range(retries):
        try:
            z=request_json(s,ds,'13')
            stat=str(z.get('stat') or '')
            got=str(z.get('date') or '')
            if stat=='OK':
                if got and got!=ds: return 'REVIEW',{},f'DATE_MISMATCH:{got}'
                rows=parse_stock_table(z)
                if rows is None: return 'REVIEW',{},'ELECTRONICS_TABLE_NOT_FOUND'
                if len(rows)==0:
                    nontrading,why=confirm_nontrading(s,ds)
                    return ('NO_DATA',{},why) if nontrading else ('REVIEW',{},why)
                if len(rows)<300: return 'REVIEW',rows,f'ROW_COUNT_{len(rows)}'
                return 'PASS',rows,''
            if '沒有符合條件' in stat or '查無資料' in stat or not got:
                return 'NO_DATA',{},stat
            last=f'STAT:{stat}:DATE:{got}'
        except Exception as e:
            last=f'{type(e).__name__}:{e}'
        time.sleep(min(20.0,(1.8**k)+random.random()*0.5))
    return 'ERROR',{},last

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--year',type=int,required=True); ap.add_argument('--out',required=True); ap.add_argument('--sleep',type=float,default=1.1); ap.add_argument('--retries',type=int,default=8); a=ap.parse_args()
    y=a.year; start=date(y,1,1); end=date(y,12,31)
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    s=requests.Session(); s.headers.update(UA)
    qa=[]; rows_all=[]; d=start; n=0
    weekdays=[]
    while d<=end:
        if d.weekday()<5: weekdays.append(d)
        d+=timedelta(days=1)
    for d in weekdays:
        st,rows,err=fetch_day(s,d,a.retries,a.sleep)
        qa.append({'date':d.isoformat(),'status':st,'members':len(rows),'error':err})
        if st=='PASS':
            for tk,nm in sorted(rows.items()): rows_all.append((d.isoformat(),tk,nm))
        n+=1
        if n%25==0: print(f'{y} {n}/{len(weekdays)} pass={sum(x["status"]=="PASS" for x in qa)} err={sum(x["status"]=="ERROR" for x in qa)}',flush=True)
        time.sleep(a.sleep)
    p=out/f'twse_electronics_membership_{y}.csv'
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(['Date','Ticker','Name']); w.writerows(rows_all)
    q=out/f'membership_qa_{y}.csv'
    with q.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['date','status','members','error']); w.writeheader(); w.writerows(qa)
    rec={'system':'HENGCE','engine':'E2_PROFIT_MAX','artifact':'PIT_TWSE_ELECTRONICS_MEMBERSHIP_YEAR_V2','year':y,'source':'TWSE MI_INDEX type=13 official daily electronics table','policy':'POINT_IN_TIME_OBSERVED_ON_DATE_NO_CURRENT_CONSTITUENT_BACKFILL','transport':'JSON_SINGLE_THREAD_RATE_LIMITED','holiday_policy':'EMPTY_TYPE13_MUST_BE_CONFIRMED_EMPTY_BY_ALLBUT0999','weekday_candidates':len(weekdays),'pass_days':sum(x['status']=='PASS' for x in qa),'no_data_days':sum(x['status']=='NO_DATA' for x in qa),'review_days':sum(x['status']=='REVIEW' for x in qa),'error_days':sum(x['status']=='ERROR' for x in qa),'rows':len(rows_all),'dates':len({x[0] for x in rows_all}),'membership_sha256':sha256(p),'qa_sha256':sha256(q)}
    rec['hard_gate']='PASS' if rec['review_days']==0 and rec['error_days']==0 and rec['pass_days']>=230 else 'FAIL_REVIEW'
    (out/f'membership_receipt_{y}.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rec,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
