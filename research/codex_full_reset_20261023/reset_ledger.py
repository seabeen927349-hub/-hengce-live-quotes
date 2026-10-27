"""Research-only append journal; every attempted evaluation and failure survives."""
import fcntl
import hashlib
import json
import os
from pathlib import Path

AUTHORITY={'research_only':True,'signal_authority':False,'ranking_authority':False,
           'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False}
def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class TrialLedger:
    def __init__(self,path,provenance):
        self.path=Path(path);self.provenance=provenance;self.ids=set();self.previous='0'*64;self.count=0
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=self.path.with_suffix('.lock').open('a')
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pending={}
        try:
            if self.path.exists():
                for line in self.path.read_text().splitlines():
                    record=json.loads(line);claimed=record.pop('record_hash')
                    if record['previous_hash']!=self.previous or digest(record)!=claimed or record['record_id'] in self.ids:
                        raise ValueError('LEDGER_PREFIX_INTEGRITY_FAILURE')
                    if record.get('status')=='STARTED':pending[record['experiment_id']]=record
                    elif record.get('experiment_id'):pending.pop(record['experiment_id'],None)
                    self.previous=claimed;self.ids.add(record['record_id']);self.count+=1
            self.stream=self.path.open('a',encoding='utf-8')
            for experiment_id,record in pending.items():
                self.append({'record_id':experiment_id+':RECOVERED_ABORTED','experiment_id':experiment_id,
                             'status':'ABORTED','reason':'PREVIOUS_PROCESS_DID_NOT_RETAIN_A_TERMINAL_RESULT',
                             'original_provenance':record.get('provenance')})
            return self
        except Exception:
            self.lock.close();raise
    def append(self,record):
        if record['record_id'] in self.ids:raise ValueError('DUPLICATE_LEDGER_RECORD_ID')
        payload={**record,'provenance':self.provenance,'authority':AUTHORITY,'previous_hash':self.previous}
        payload['record_hash']=digest(payload)
        self.stream.write(json.dumps(payload,sort_keys=True,allow_nan=False)+'\n')
        self.stream.flush();os.fsync(self.stream.fileno())
        self.ids.add(record['record_id']);self.previous=payload['record_hash'];self.count+=1
    def __exit__(self,*exc):
        self.stream.close();self.lock.close()
