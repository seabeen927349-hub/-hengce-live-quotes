#!/usr/bin/env python3
import csv, io, json, math, time
from datetime import date, datetime, timedelta
from pathlib import Path
import requests

OUT=Path('research/q017_sox_tw_electronics/archive_2026');OUT.mkdir(parents=True,exist_ok=True)
URL='https://indexes.nasdaq.com/Index/ExportHistory/SOX'
UA={'User-Agent':'Mozilla/5.0 (HENGCE SOX auto refresh)'}
START=date(2026,1,1);END=date.today()

def parse(raw):
    if raw.startswith(b'PK'):
        import openpyxl
        ws=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True).active
        records=list(ws.iter_rows(values_only=True))
    else:
        records=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
    out=[]
    for rec in records:
        if len(rec)<2:continue
        ds=rec[0];dt=None
        if isinstance(ds,datetime):dt=ds.date()
        elif isinstance(ds,date):dt=ds
        else:
            for fmt in ('%m/%d/%Y','%Y-%m-%d','%m/%d/%Y %H:%M:%S'):
                try:dt=datetime.strptime(str(ds).strip(),fmt).date();break
                except:pass
        try:c=float(str(rec[1]).replace(',','').strip())
        except:continue
        if dt and START<=dt<=END and math.isfinite(c) and c>0:out.append({'date':dt.isoformat(),'close':c})
    return sorted({x['date']:x for x in out}.values(),key=lambda x:x['date'])

def main():
    last=None;raw=None
    for a in range(6):
        try:
            r=requests.get(URL,params={'startDate':'2026-01-01T00:00:00.000','endDate':END.isoformat()+'T00:00:00.000','timeOfDay':'EOD'},headers=UA,timeout=(8,30))
            if r.status_code==200 and r.content:
                raw=r.content;break
            last=f'HTTP {r.status_code}'
        except Exception as e:last=repr(e)
        time.sleep(min(30,2**a))
    if raw is None:raise SystemExit(f'SOX_DOWNLOAD_FAIL:{last}')
    rows=parse(raw)
    if len(rows)<180:raise SystemExit(f'SOX_ROWS_TOO_FEW:{len(rows)}')
    latest=datetime.strptime(rows[-1]['date'],'%Y-%m-%d').date()
    if (END-latest).days>7:raise SystemExit(f'SOX_STALE:{latest}')
    (OUT/'nasdaq_sox_2026_raw.bin').write_bytes(raw)
    with (OUT/'sox_2026.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['date','close']);w.writeheader();w.writerows(rows)
    receipt={'status':'PASS','source':'Nasdaq ExportHistory/SOX','requested_through':END.isoformat(),'latest_session':latest.isoformat(),'rows':len(rows),'stale_days':(END-latest).days}
    (OUT/'sox_refresh_status.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))
if __name__=='__main__':main()
