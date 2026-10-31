#!/usr/bin/env python3
"""Compare official MOPS quarterly bulk-ZIP member timestamps to independently
verified TWSE electronic-book upload timestamps.

NO prices. NO returns. If timestamps do not match exactly, the ZIP timestamp
must not be promoted to PIT authority.
"""
from __future__ import annotations
import datetime as dt, hashlib, io, json, zipfile
from pathlib import Path
import requests

OUT=Path('research/selection_core_rebuild/generated/IF07_BULK_ZIP_TIMESTAMP_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
BASE='https://mopsov.twse.com.tw/server-java/FileDownLoad'
SAMPLES=[
    {'ticker':'2330','year':2023,'quarter':1,'verified_upload':'2023-05-12T13:51:34'},
    {'ticker':'2454','year':2024,'quarter':2,'verified_upload':'2024-08-13T17:27:52'},
    {'ticker':'3037','year':2025,'quarter':3,'verified_upload':'2025-10-30T18:45:28'},
    {'ticker':'2303','year':2026,'quarter':2,'verified_upload':'2026-07-29T17:18:33'},
]

def main():
    s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-zip-ts-probe/0.1','Referer':'https://mopsov.twse.com.tw/mops/web/t203sb02'})
    cache={}; out=[]
    for x in SAMPLES:
        key=(x['year'],x['quarter'])
        if key not in cache:
            fn=f"tifrs-{x['year']}Q{x['quarter']}.zip"
            p={'step':'9','functionName':'show_file2','fileName':fn,'filePath':f"/ifrs/{x['year']}/"}
            r=s.get(BASE,params=p,timeout=240)
            b=r.content
            if r.status_code!=200 or b[:2]!=b'PK': raise RuntimeError(f'bulk fail {key} status={r.status_code} bytes={len(b)}')
            cache[key]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'zip':zipfile.ZipFile(io.BytesIO(b))}
        z=cache[key]['zip']
        target=f"tifrs-fr1-m1-ci-cr-{x['ticker']}-{x['year']}Q{x['quarter']}.html"
        hits=[zi for zi in z.infolist() if Path(zi.filename).name.lower()==target.lower()]
        row={**x,'bulk_zip_bytes':cache[key]['bytes'],'bulk_zip_sha256':cache[key]['sha256'],'target_member':target,'hit_count':len(hits)}
        if len(hits)==1:
            zi=hits[0]
            member_ts=dt.datetime(*zi.date_time)
            verified=dt.datetime.fromisoformat(x['verified_upload'])
            row.update({'member_filename':zi.filename,'zip_member_timestamp':member_ts.isoformat(),'zip_member_timestamp_raw':list(zi.date_time),'member_file_size':zi.file_size,'member_crc':zi.CRC,'delta_seconds_vs_verified_upload':(member_ts-verified).total_seconds(),'exact_match':member_ts==verified})
        out.append(row)
    exact=all(r.get('exact_match') for r in out)
    obj={'system':'HENGCE','artifact':'IF07_BULK_ZIP_TIMESTAMP_PROBE','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'verified_upload_source':'independent TWSE electronic-book t57sb01 observations frozen before this probe','samples':out,'all_exact_match':exact,'verdict':'PASS_AS_UPLOAD_TIMESTAMP_AUTHORITY' if exact else 'FAIL_AS_UPLOAD_TIMESTAMP_AUTHORITY'}
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'all_exact_match':exact,'rows':[{k:r.get(k) for k in ['ticker','year','quarter','verified_upload','zip_member_timestamp','delta_seconds_vs_verified_upload','exact_match']} for r in out]},ensure_ascii=False))
if __name__=='__main__': main()
