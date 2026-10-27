#!/usr/bin/env python3
"""Read-only canonical bridge verification; no model imports or networking."""
from pathlib import Path
import csv, collections, datetime, hashlib, json, sys

EXPECTED='60fb82570d48ef2620a8390d612457fc79e795b9e1fe485f61739103bfa8db47'

def verify(bundle):
    bundle=Path(bundle)
    inventory=[]
    for line in (bundle/'MANIFEST.sha256').read_text().splitlines():
        h,name=line.split(maxsplit=1); name=name.lstrip('*')
        p=bundle/name
        assert p.parent==bundle and p.is_file(),name
        b=p.read_bytes();actual=hashlib.sha256(b).hexdigest()
        assert actual==h,name
        inventory.append({'path':name,'bytes':len(b),'sha256':actual})
    p=bundle/'HENGCE_2026_HIST_MOTHER.csv'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED
    with p.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); columns=reader.fieldnames; rows=list(reader)
    expected=json.loads((bundle/'MOTHER_VERIFICATION.json').read_text())
    receipt=json.loads((bundle/'HENGCE_HIST_MOTHER_INCREMENTAL_RECEIPT_20261021.json').read_text())
    state=json.loads((bundle/'HENGCE_CANONICAL_STATE.json').read_text())
    keys=collections.Counter((r['Date'],r['Ticker']) for r in rows)
    for r in rows:
        datetime.date.fromisoformat(r['Date'])
        assert r['Ticker'] and len(r)==len(columns)
    counts=collections.Counter(r['Date'] for r in rows)
    latest=[r for r in rows if r['Date']=='2026-10-21']
    null=lambda value:value in ('','null','NULL','None')
    missing={c:sorted(r['Ticker'] for r in latest if null(r[c])) for c in columns}
    result={'sha256':EXPECTED,'size_bytes':p.stat().st_size,'rows':len(rows),'columns':columns,'min_date':min(counts),'max_date':max(counts),'unique_dates':len(counts),'unique_tickers':len({r['Ticker'] for r in rows}),'duplicate_date_ticker_rows':sum(n-1 for n in keys.values()),'rows_2026_10_21':counts['2026-10-21'],'rows_2026_10_22':counts['2026-10-22']}
    for key,value in result.items(): assert expected[key]==value,(key,value)
    assert result['rows']==207218 and result['duplicate_date_ticker_rows']==0
    for doc in [receipt,state]: assert doc['mother_sha256']==EXPECTED and doc['mother_latest_date']=='2026-10-21'
    assert receipt['mother_rows']==len(rows) and receipt['target_mother_rows']==len(latest)
    assert missing['Margin_MarginBalance']==sorted(receipt['target_price_missing_margin_tickers'])
    for c in ['ForeignNet','TrustNet','TotalNet']:
        assert missing[c]==sorted(receipt['target_price_missing_institutional_tickers'])
    assert len(missing['Margin_MarginBalance'])==30 and len(missing['ForeignNet'])==9
    eod=json.loads((bundle/'EOD_20261022_STATUS_SNAPSHOT.json').read_text())
    assert eod['mother_status']=='PENDING' and eod['formal_complete_day'] is False
    assert result['rows_2026_10_22']==0
    return {'status':'PASS_ACCESSIBILITY_AND_20261021_ARTIFACT_AUTHENTICITY','computed':result,'latest_missing_tickers':missing,'receipt_identity_match':True,'receipt_null_ticker_sets_match':True,'new_model_evaluations':0,'canonical_bytes_modified':False,'second_mother_created':False,'pit_electronics_membership_proven':False,'warmup_bridge_proven':False,'promotion_20261022_proven':False,'source_inventory':inventory,'interpretation':'Hash identity, schema/key checks and receipt consistency authenticate the supplied 10/21 artifact. They do not independently verify every official raw value, PIT sector membership, historical instrument identity or 10/22 promotion.'}

if __name__=='__main__':
    result=verify(sys.argv[1])
    text=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if len(sys.argv)>2: Path(sys.argv[2]).write_text(text)
    else: print(text,end='')
