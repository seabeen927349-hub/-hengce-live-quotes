"""Frozen four-request public issuer/filing discovery, never model input."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent
def h(raw):return hashlib.sha256(raw).hexdigest()

def main():
    plan=json.loads((HERE/'DISCOVERY_PLAN_V2.json').read_text())
    target=HERE/'discovery';target.mkdir(exist_ok=False)
    (target/'DISCOVERY_SOURCE.py').write_bytes(Path(__file__).read_bytes())
    denied=set();records=[]
    for task in plan['sources']:
        record={**task,'fetched_at_utc':datetime.now(timezone.utc).isoformat(),
                'historical_first_seen_at':None,'status':'UNREVIEWED_NOT_MODEL_INPUT'}
        if task['family'] in denied:
            record['status']='NOT_ATTEMPTED_AFTER_FAMILY_STOP';records.append(record);continue
        raw=b''
        try:
            with urllib.request.urlopen(task['url'],timeout=25) as response:
                raw=response.read(8388609);record['http_status']=response.status
                if len(raw)>8388608:raise ValueError('BODY_LIMIT')
        except urllib.error.HTTPError as exc:
            raw=exc.read(8388608);record.update(http_status=exc.code,status='HTTP_REFUSAL_RETAINED',error=str(exc))
        except Exception as exc:record.update(status='FAILED_RETAINED',error=str(exc))
        lower=raw.decode('utf-8',errors='ignore').lower()
        challenge=any(x in lower for x in ('captcha','access denied','forbidden','查詢過於頻繁','驗證碼'))
        if record.get('http_status') in (401,403,429) or challenge:
            denied.add(task['family']);record['status']='SOURCE_FAMILY_STOP_NO_BYPASS'
        data=gzip.compress(raw,mtime=0);record.update(raw_path=task['id']+'.gz',response_sha256=h(raw),archive_sha256=h(data),
            completed_at_utc=datetime.now(timezone.utc).isoformat())
        with (target/record['raw_path']).open('xb') as f:f.write(data)
        records.append(record);print(task['id'],record['status'],flush=True);time.sleep(1.5)
    with (target/'MANIFEST.json').open('x') as f:
        json.dump({'plan_sha256':h((HERE/'DISCOVERY_PLAN_V2.json').read_bytes()),'records':records,
                   'source_code_sha256':h((target/'DISCOVERY_SOURCE.py').read_bytes()),
                   'terms_promoted_to_ledger':False,'new_model_evaluations':0},f,indent=2,sort_keys=True)
        f.write('\n')

if __name__=='__main__':main()
