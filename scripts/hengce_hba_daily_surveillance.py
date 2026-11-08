#!/usr/bin/env python3
"""HENGCE HBA daily research-side surveillance, independent of frozen selection/escape.
Reads existing EOD original vessel, canonical TDCC and governed overseas premarket.
No own data downloader, no model promotion or trading authority.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,statistics
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Taipei')
SCOPE='HENGCE_HBA_SURVEILLANCE_RESEARCH_ONLY_V1'

def number(v):
    try:return float(str(v).replace(',',''))
    except (ValueError,TypeError):return None

def jread(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError):return None

def csvrows(path):
    try:
        with path.open(encoding='utf-8-sig',newline='') as f: yield from csv.DictReader(f)
    except OSError:return

def stable_hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def eod(root):
    # Date contract: read only COMPLETE original-vessel 3-leg days; do not replace missing values by zero.
    out=defaultdict(list); days=[]
    for folder in sorted((root/'eod').glob('20??????')):
        s=jread(folder/'status.json')
        if not s or s.get('formal_complete_day') is not True or not s.get('downstream_ready'):continue
        date=folder.name[:4]+'-'+folder.name[4:6]+'-'+folder.name[6:8]
        if any(s.get(k+'_date')!=date for k in ('price','institutional','margin')):continue
        pp={};inst={};margin={}
        for path in sorted(folder.glob('price_*.csv')):
            for r in csvrows(path):
                if r.get('Date')==date and r.get('Ticker','').isdigit() and len(r['Ticker'])==4:
                    pp[r['Ticker']]=r
        for path in sorted(folder.glob('institutional_*.csv')):
            for r in csvrows(path):
                if r.get('Date')==date:inst[r.get('Ticker')]=r
        for path in sorted(folder.glob('margin_*.csv')):
            for r in csvrows(path):
                if r.get('Date')==date:margin[r.get('Ticker')]=r
        if not pp:continue
        days.append(date)
        for t,p in pp.items():
            i=inst.get(t);m=margin.get(t)
            if not i or not m:continue
            close=number(p.get('Close'));vol=number(p.get('VolumeShares'));turn=number(p.get('TurnoverTWD'))
            total=number(i.get('TotalNet'));mb=number(m.get('MarginBalance'))
            if close is None or close<=0 or vol is None or vol<=0 or turn is None or total is None or mb is None:continue
            out[t].append({'day':date,'name':p.get('Name') or t,'c':close,'vol':vol,'turn':turn,'flow':total,'margin':mb})
    for z in out.values():z.sort(key=lambda v:v['day'])
    return days,out

def tdcc(root,asof):
    latest=jread(root/'ownership/tdcc/latest.json') or {}
    dates=[]
    for folder in (root/'ownership/tdcc').glob('20??????'):
        d=folder.name
        if len(d)==8 and d.isdigit() and d<=asof.replace('-','') and (folder/'tdcc_ownership_4d.csv').exists():dates.append(d)
    series=defaultdict(list)
    for d in sorted(dates)[-10:]:
        for r in csvrows(root/'ownership/tdcc'/d/'tdcc_ownership_4d.csv'):
            if r.get('SnapshotDate')!=d:continue
            t=r.get('Ticker');pct=number(r.get('Big400Pct'));p1000=number(r.get('Big1000Pct'));holders=number(r.get('TotalHolders'))
            observed=r.get('ObservedAtTaipei','')
            if not(t and pct is not None and p1000 is not None and holders is not None and 0<=p1000<=pct<=100):continue
            # First observed time for historical decision-safety; no synthetic daily forward-fill.
            if not observed or observed[:10]>asof:continue
            series[t].append({'date':d,'pct':pct,'pct1000':p1000,'holders':holders,'observed':observed})
    return latest,series

def env(root,target):
    # Governed overseas packet is mandatory for an affirmed current macro direction.
    p=root/'overseas_premarket/latest.json';x=jread(p)
    result={'status':'資料不足','label':'資料不足','packet_date':None,'source_path':str(p),'reason':'未找到正式 SOX/VIX 盤前封包'}
    if not isinstance(x,dict):return result
    result['packet_date']=x.get('target_tw_date')
    if x.get('status')!='PASS_VERIFIED_VENDOR_EOD' or x.get('target_tw_date')!=target:
        result['reason']='SOX/VIX 封包驗證失敗或日期與監控日期不符';return result
    sources=x.get('sources') or {};a=sources.get('sox') or {};b=sources.get('vix') or {}
    verified=(a.get('publisher')=='Nasdaq' and b.get('publisher')=='Cboe' and
      a.get('latest_us_session')==b.get('latest_us_session')==x.get('latest_us_session') and
      all(isinstance(s.get('raw_sha256'),str) and len(s['raw_sha256'])==64 for s in (a,b)) and
      x.get('trading_authority') is False and x.get('capital_authority') is False)
    original=x.copy();claimed=original.pop('packet_sha256',None)
    if not verified or claimed!=stable_hash(original):
        result['reason']='SOX/VIX 來源或封包 SHA 不符';return result
    dc=x.get('direction_forecast') or {};grade=dc.get('grade');label=dc.get('label')
    if not isinstance(grade,int) or grade not in range(1,6) or label not in ('強烈偏空','偏空','中性','偏多','強烈偏多'):
        result['reason']='方向資訊不完整';return result
    return {'status':'已核對','label':label,'grade':grade,'packet_date':target,
       'us_session':x.get('latest_us_session'),'sox':a.get('latest_close'),'vix':b.get('latest_close'),
       'vix_band':(x.get('risk_forecast') or {}).get('vix_risk_band'),
       'gap_log_pct':dc.get('expected_taiex_open_gap_log_pct'),'packet_sha256':claimed,'source_path':str(p)}

def scan(root, target, limit=15):
    days,stocks=eod(root); latest=days[-1] if days else None
    meta,holding=tdcc(root,target); macro=env(root,target)
    report={'schema':SCOPE,'target_tw_date':target,'latest_verified_eod':latest,
      'source_scope':'TWSE original-vessel 3-leg + canonical TDCC + governed overseas packet',
      'source_coverage':{'available_eod_days':len(days),'available_tdcc_snapshots':len({r['date'] for v in holding.values() for r in v})},
      'external_environment':macro,'long_term_capital_environment':{'label':'資料不足','reason':'尚無正式20/60/120日資金環境核准憑證；個股法人淨額不可代替跨境資金流'},
      'data_gate':'BLOCKED','candidates':[],'stage_counts':{},'exclusions':[],'explanations':[],
      'not_an_order':True,'no_formula_profit_claim':True,'rules_fixed_ex_ante_for_forward_surveillance':True}
    if not days:
        report['exclusions'].append('缺少可核對的正式三腿 EOD');return report
    if (dt.date.fromisoformat(target)-dt.date.fromisoformat(latest)).days>5:
        report['exclusions'].append('EOD 超過 5 日，禁止冒充當日監控');return report
    if len(days)<8:
        report['exclusions'].append('歷史 EOD 少於 8 日，暫不能做連續性判斷');return report
    report['data_gate']='EOD_VALID_MACRO_'+('VALID' if macro['status']=='已核對' else 'UNKNOWN')
    # Market breadth is descriptive, not a substitute for the locked Market State or long-term capital axis.
    up=[]
    for t,z in stocks.items():
        if len(z)>1 and z[-1]['day']==latest:up.append(z[-1]['c']>z[-2]['c'])
    report['market_breadth_proxy']={'advancing_share':round(sum(up)/len(up),4) if up else None,'observed_stocks':len(up),'date':latest,'authority':'descriptive_only'}
    candidates=[]
    for t,z in stocks.items():
        if z[-1]['day']!=latest or len(z)<8:continue
        a=z[-1];prior=z[-2];back=z[-min(len(z),11):];last5=z[-5:]
        if statistics.mean(v['turn'] for v in last5)<15000000 or a['c']<8:continue
        p5=(a['c']/z[-6]['c']-1)*100 if len(z)>=6 else None
        f5=sum(v['flow'] for v in last5)/sum(v['vol'] for v in last5)
        f10=sum(v['flow'] for v in back)/sum(v['vol'] for v in back)
        flow_days=sum(v['flow']>0 for v in last5)
        vr=a['vol']/statistics.mean(v['vol'] for v in z[-6:-1])
        day_ret=(a['c']/prior['c']-1)*100
        margin_change=(a['margin']/z[-6]['margin']-1)*100 if len(z)>=6 and z[-6]['margin']>0 else None
        td=holding.get(t,[]);td=sorted(td,key=lambda x:x['date'])
        delta=round(td[-1]['pct']-td[-2]['pct'],3) if len(td)>=2 else None
        hchange=(td[-1]['holders']/td[-2]['holders']-1)*100 if len(td)>=2 and td[-2]['holders']>0 else None
        signs=[];counter=[];domains=set()
        if f5>=.012 and flow_days>=3:
            signs.append(f'法人5日淨買超/成交量 {f5*100:.2f}%（{flow_days}/5日淨買）');domains.add('flow')
        elif f5<-.012:counter.append(f'法人5日呈淨賣 {f5*100:.2f}%')
        if delta is not None and delta>=.25:
            signs.append(f'TDCC 400張以上本週增加 {delta:.2f}pp');domains.add('ownership')
        elif delta is not None and delta<=-.5:counter.append(f'TDCC 大額持股本週減少 {abs(delta):.2f}pp')
        if p5 is not None and p5>=3 and vr>=1.2:
            signs.append(f'5日價格變動 {p5:.1f}% 且量比 {vr:.2f}');domains.add('price')
        elif p5 is not None and p5<=-4:counter.append(f'5日股價回落 {p5:.1f}%')
        if margin_change is not None and margin_change<=-3 and f5>0:
            signs.append(f'融資5日減少 {abs(margin_change):.1f}% 且法人淨買');domains.add('leverage')
        elif margin_change is not None and margin_change>=12:counter.append(f'融資5日增加 {margin_change:.1f}%')
        if len(domains)<2 and not (f5<=-.018 and delta is not None and delta<=-.5):continue
        stage='疑似症狀'
        if len(domains)>=3 or ('ownership' in domains and 'flow' in domains):stage='準備監控'
        confirmed=('flow' in domains and 'price' in domains and day_ret>=2 and vr>=1.5 and len(domains)>=3)
        if confirmed:stage='行情確認（待人工評估）'
        if f5<=-.018 and delta is not None and delta<=-.5:stage='撤退警戒'
        if macro['status']!='已核對':counter.append('正式當日SOX/VIX環境未知')
        elif macro['label'] in ('強烈偏空','偏空'):counter.append('隔夜海外環境偏空，與個股訊號需交叉檢查')
        if len(td)<2:counter.append('TDCC可用週資料不足，不能認定累積完成')
        macro_alignment=('UNKNOWN_HOLD' if macro['status']!='已核對' else
                         'HEADWIND' if macro['label'] in ('強烈偏空','偏空') else
                         'TAILWIND' if macro['label'] in ('強烈偏多','偏多') else 'NEUTRAL')
        decision_readiness=('CROSS_ENVIRONMENT_REVIEW_PENDING' if macro_alignment in ('UNKNOWN_HOLD','HEADWIND') else
                            'MANUAL_CATALYST_AND_EXECUTION_REVIEW' if confirmed and stage!='撤退警戒' else
                            'WATCH_ONLY')
        candidates.append({'ticker':t,'name':a['name'],'stage':stage,'evidence_domains':sorted(domains),
          'positive_evidence':signs,'counter_evidence':counter,'macro_alignment':macro_alignment,'decision_readiness':decision_readiness,'eod_date':latest,
          'ownership_snapshot':td[-1]['date'] if td else None,'institution_5d_net_volume_pct':round(f5*100,2),
          'institution_10d_net_volume_pct':round(f10*100,2),'tdcc_big400_delta_pp':delta,
          'tdcc_total_holders_change_pct':round(hchange,2) if hchange is not None else None,
          'last_price':a['c'],'day_return_pct':round(day_ret,2),'five_day_return_pct':round(p5,2) if p5 is not None else None,
          'volume_ratio_vs_previous5':round(vr,2),'margin_change5_pct':round(margin_change,2) if margin_change is not None else None,
          'monitor_next':'下一交易日查法人延續、價量、TDCC新週資料和海外環境；事前設計風險退出條件'})
    priority={'行情確認（待人工評估）':0,'準備監控':1,'疑似症狀':2,'撤退警戒':3}
    candidates.sort(key=lambda r:(priority[r['stage']],-len(r['evidence_domains']),-r['institution_5d_net_volume_pct'],r['ticker']))
    report['total_candidates_before_limit']=len(candidates)
    report['candidate_registry']={c['ticker']:c['stage'] for c in candidates}
    old=jread(root/'research/hba_surveillance/latest.json') or {}
    old_registry=old.get('candidate_registry',{}) if old.get('latest_verified_eod','')<latest else {}
    report['new_or_escalated']=[{'ticker':c['ticker'],'name':c['name'],'prior':old_registry.get(c['ticker']),'now':c['stage']}
       for c in candidates if (c['ticker'] not in old_registry or priority.get(c['stage'],9)<priority.get(old_registry[c['ticker']],9)) and c['stage']!='撤退警戒'][:100]
    report['cleared']=[t for t in old_registry if t not in report['candidate_registry']][:100]
    report['candidates']=[c for c in candidates if c['stage']!='撤退警戒'][:limit]
    report['exit_alerts']=[c for c in candidates if c['stage']=='撤退警戒'][:10]
    report['stage_counts']={stage:sum(c['stage']==stage for c in candidates) for stage in priority}
    report['explanations']=['觀察分層不是勝率/預測機率，沒有交易授權；只供研究偵查與人工覆核',
       'TDCC持股級距不等於法人身分；公開法人買賣超是淨額，不能辨識特定資金意圖',
       '單日收盤確認只意味觀察訊號成立，不保證次日可以合理價格成交',
       '外部封包缺失不會填入中性，也不會以舊數據冒充當日']
    return report

def markdown(report):
    a=report; macro=a['external_environment'];lines=[f"# 衡策 HENGCE｜每日資金偵查｜{a['target_tw_date']}",'',
      f"- 最近正式EOD：{a['latest_verified_eod'] or '資料不足'}；資料門檻：{a['data_gate']}",
      f"- 海外 SOX/VIX：**{macro['label']}**；封包日期：{macro.get('packet_date') or '無'}；{macro.get('reason','已核對正式來源')}",
      '- 長期資金環境：**資料不足**（尚缺獨立正式20/60/120日憑證；不以每日淨買超代替）',
      f"- 當日市場廣度代理：{a.get('market_breadth_proxy',{}).get('advancing_share','未知')}（收盤後描述性訊號）",'',
      '## 偵查統計',f"候選股票 {a.get('total_candidates_before_limit',0)} 檔；"+'；'.join(f'{k} {v}' for k,v in a['stage_counts'].items()),'',
      '## 新增／升級',f"新增或升級 {len(a.get('new_or_escalated',[]))} 檔（首次建立基線時均屬新增）",'', '## 需要優先人工覆核的股票','']
    for c in a['candidates']:
        lines.extend([f"### {c['ticker']} {c['name']} — {c['stage']}",
          f"- 正面證據：{'；'.join(c['positive_evidence']) or '無'}",
          f"- 反面／缺口：{'；'.join(c['counter_evidence']) or '未見此批指標明確反證'}",
          f"- 外部環境交叉檢查：{c['macro_alignment']}；處置狀態：{c['decision_readiness']}",
          f"- 觀察：{c['monitor_next']}",''])
    if not a['candidates']:lines.append('沒有足夠獨立證據形成候選；缺資料時不虛構名單。')
    lines+=['','## 持股分散／撤退風險（獨立警報，非買進候選）','']
    for c in a.get('exit_alerts',[]):
        lines.append(f"- {c['ticker']} {c['name']}：法人5日淨買超比 {c['institution_5d_net_volume_pct']}%；TDCC大額持股週變化 {c['tdcc_big400_delta_pp']}pp")
    if not a.get('exit_alerts'):lines.append('本次未觸發這組撤退代理條件。')
    lines+=['','## 研究邊界',*['- '+x for x in a['explanations']],*['- '+x for x in a['exclusions']]]
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--target-tw-date',default=dt.datetime.now(TZ).date().isoformat());p.add_argument('--out',type=Path,default=Path('research/hba_surveillance/latest.json'));p.add_argument('--limit',type=int,default=15)
    a=p.parse_args();result=scan(a.root,a.target_tw_date,a.limit)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    md=a.out.with_suffix('.md');md.write_text(markdown(result),encoding='utf-8')
    print(json.dumps({'status':result['data_gate'],'target':result['target_tw_date'],'eod':result['latest_verified_eod'],'count':result.get('total_candidates_before_limit',0),'macro':result['external_environment']['label'],'output':str(a.out)},ensure_ascii=False))
if __name__=='__main__':main()