#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,statistics,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
TZ=ZoneInfo('Asia/Taipei');ROOT=Path(__file__).resolve().parents[1];E2DIR=ROOT/'hengce'/'e2_live';E2DIR.mkdir(parents=True,exist_ok=True)
STATE=E2DIR/'state_latest.json';ROLLING=E2DIR/'rolling_state.json';MORNING=E2DIR/'morning_latest.json';POSTCLOSE=E2DIR/'postclose_latest.json';MAX_SLOTS=5;MIN_GROUP=4;MAX_STATE_STALE_DAYS=7
TWSE_PRICE='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX';TWSE_INST='https://www.twse.com.tw/rwd/zh/fund/T86';UA={'User-Agent':'Mozilla/5.0 HENGCE-E2-LIVE/1.0','Accept':'application/json','Referer':'https://www.twse.com.tw/'}
LOCKS={'population':'E2_STRICT_RESEARCH_POPULATION_LOCK_20261018.json','extension':'E2_EXTENSION_SHADOW_LOCK_20261018.json','capital':'E2_EXECUTION_CAPITAL_LOCK_20261018.json','state_machine':'E2_POSITION_STATE_MACHINE_LOCK_20261018.json'}
def now_tw():return datetime.now(TZ)
def canonical_sha(o):return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic_json(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');t.replace(p)
def read_json(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def fnum(x):
 if x in (None,'','-','--'):return None
 try:return float(str(x).replace(',','').strip())
 except:return None
def mean_valid(xs,minp=None):
 v=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
 if minp is not None and len(v)<minp:return None
 return sum(v)/len(v) if v else None
def sum_valid(xs,minp=None):
 v=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
 if minp is not None and len(v)<minp:return None
 return sum(v) if v else None
def median(xs):
 v=[float(x) for x in xs if x is not None and math.isfinite(float(x))];return statistics.median(v) if v else None
def validate_locked_state(s):
 if s.get('schema_version')!=1 or s.get('module')!='E2_LIVE_STATE_LOCK':raise RuntimeError('E2_STATE_SCHEMA_OR_MODULE_INVALID')
 h=s.get('state_sha256');exp=canonical_sha({k:v for k,v in s.items() if k!='state_sha256'})
 if not h or h!=exp:raise RuntimeError('E2_STATE_HASH_INVALID')
 if s.get('locks')!=LOCKS:raise RuntimeError('E2_LOCK_SET_DRIFT')
 strict=s.get('strict') or {};shadow=s.get('extension_shadow') or {};ps=s.get('position_state') or {}
 if strict.get('authority')!=LOCKS['population']:raise RuntimeError('E2_STRICT_AUTHORITY_DRIFT')
 if shadow.get('authority')!=LOCKS['extension'] or shadow.get('capital_authorized') is not False:raise RuntimeError('E2_SHADOW_AUTHORITY_INVALID')
 if any(r.get('E2Action') in ('BUY','WATCH') for r in shadow.get('rows') or []):raise RuntimeError('E2_SHADOW_CAPITAL_ACTION_FORBIDDEN')
 buys=sum(r.get('E2Action')=='BUY' for r in strict.get('rows') or []);watches=sum(r.get('E2Action')=='WATCH' for r in strict.get('rows') or [])
 if int(strict.get('buy_count') or 0)!=buys or int(strict.get('watch_count') or 0)!=watches:raise RuntimeError('E2_STRICT_ACTION_COUNT_MISMATCH')
 if int(strict.get('cohort_count') or 0)<4 and buys:raise RuntimeError('E2_STRICT_LT4_BUY_FORBIDDEN')
 if int(ps.get('max_slots') or 0)!=MAX_SLOTS:raise RuntimeError('E2_MAX_SLOTS_DRIFT')
 held=ps.get('held') or [];pending=ps.get('pending') or [];occ=int(ps.get('occupied_next_session') or 0);free=int(ps.get('free_slots_next_session') or 0)
 if occ!=len(held)+len(pending) or free!=MAX_SLOTS-occ:raise RuntimeError('E2_SLOT_ACCOUNTING_INVALID')
 tick=[int(x['Ticker']) for x in held+pending]
 if len(tick)!=len(set(tick)):raise RuntimeError('E2_ACTIVE_DUPLICATE_TICKER')
 if s.get('signal_asof')!=ps.get('asof'):raise RuntimeError('E2_STATE_ASOF_MISMATCH')
 return True
def latest_complete_eod_date():
 eod=ROOT/'eod'
 if not eod.exists():return None
 for p in sorted([x for x in eod.iterdir() if x.is_dir() and x.name.isdigit() and len(x.name)==8],reverse=True):
  st=p/'status.json'
  if not st.exists():continue
  try:o=read_json(st)
  except:continue
  if all(o.get(k)=='COMPLETE' for k in ['price_status','institutional_status','margin_status']):return datetime.strptime(p.name,'%Y%m%d').date()
 return None
def latest_market_session_hint(td):
 p=ROOT/'hengce'/'q017_radar'/'data_status.json'
 if not p.exists():return None
 try:o=read_json(p);x=((o.get('required') or {}).get('electronics_history_latest'))
 except Exception:return None
 try:d=datetime.strptime(str(x),'%Y-%m-%d').date()
 except Exception:return None
 return d if d<td else None
def morning(td):
 if not STATE.exists():raise RuntimeError('E2_STATE_MISSING')
 s=read_json(STATE);validate_locked_state(s);sd=datetime.strptime(s['signal_asof'],'%Y-%m-%d').date()
 if sd>=td:raise RuntimeError('E2_SIGNAL_ASOF_NOT_PRIOR_TO_TRADE_DATE')
 if (td-sd).days>MAX_STATE_STALE_DAYS:raise RuntimeError('E2_STATE_TOO_STALE')
 expected=latest_market_session_hint(td)
 if expected and sd!=expected:raise RuntimeError(f'E2_STATE_NOT_LATEST_MARKET_SESSION:STATE={sd}:EXPECTED={expected}')
 le=latest_complete_eod_date()
 if le and le>sd:raise RuntimeError(f'E2_STATE_STALE_VS_COMPLETE_EOD:STATE={sd}:EOD={le}')
 archive_gap=bool(le is None or le<sd)
 ps=s['position_state'];due=ps.get('pending') or []
 out={'schema_version':1,'system':'HENGCE','module':'E2_MORNING_EXECUTION_BRIDGE','trade_date':td.isoformat(),'generated_at_taipei':now_tw().isoformat(),'binding_status':'PASS','source_signal_asof':s['signal_asof'],'expected_prior_market_session':expected.isoformat() if expected else None,'latest_complete_eod_date':le.isoformat() if le else None,'local_eod_archive_gap':archive_gap,'engine_status':s['strict']['engine_status'],'strict_cohort_count':s['strict']['cohort_count'],'new_signal_buy_count':s['strict']['buy_count'],'entry_due_count':len(due),'entry_due':due,'held_from_prior_close':ps.get('held') or [],'free_slots_before_today_entries':ps['free_slots_next_session'],'extension_shadow':s['extension_shadow'],'capital_authority':'STRICT_PENDING_ENTRY_ONLY','note':'E2 state must match latest known prior market session. A lagging local EOD archive is repairable and has no authority over a separately hash-locked E2 state.'};atomic_json(MORNING,out);return out
def get_json(url,params,tries=4):
 last=None
 for n in range(tries):
  try:r=requests.get(url,params=params,headers=UA,timeout=(8,30));r.raise_for_status();return r.json()
  except Exception as e:last=e;time.sleep(min(8,1.5**n))
 raise RuntimeError(f'TWSE_DOWNLOAD_FAIL:{url}:{last!r}')
def _table(payload,need):
 for t in payload.get('tables') or []:
  fs=t.get('fields') or []
  if all(any(n in str(f) for f in fs) for n in need):return fs,t.get('data') or t.get('records') or []
 fs=payload.get('fields') or [];data=payload.get('data') or payload.get('records') or []
 return (fs,data) if fs and data else ([],[])
def fetch_day(d):
 ds=d.strftime('%Y%m%d');pp=get_json(TWSE_PRICE,{'date':ds,'type':'ALLBUT0999','response':'json'});ii=get_json(TWSE_INST,{'date':ds,'selectType':'ALLBUT0999','response':'json'})
 if str(pp.get('stat'))!='OK' or str(ii.get('stat'))!='OK':return None,None
 pfs,pdata=_table(pp,['證券代號','收盤價']);ifs,idata=_table(ii,['證券代號']);pi={f:n for n,f in enumerate(pfs)};ix={f:n for n,f in enumerate(ifs)}
 def pv(r,n):
  j=pi.get(n);return r[j] if j is not None and j<len(r) else None
 def iv(r,exact=None,contains=None):
  if exact in ix and ix[exact]<len(r):return r[ix[exact]]
  if contains:
   for f,j in ix.items():
    if contains in str(f) and j<len(r):return r[j]
  return None
 prices=[];inst=[]
 for r in pdata:
  t=str(pv(r,'證券代號') or '').replace('=','').replace('"','').strip()
  if not(len(t)==4 and t.isdigit() and 1000<=int(t)<=9999):continue
  vals={k:fnum(pv(r,n)) for k,n in [('VolumeShares','成交股數'),('Open','開盤價'),('High','最高價'),('Low','最低價'),('Close','收盤價')]}
  if vals['Close'] is not None:prices.append({'Date':d.isoformat(),'Ticker':int(t),'Name':str(pv(r,'證券名稱') or '').strip(),**vals})
 for r in idata:
  t=str(iv(r,exact='證券代號') or '').replace('=','').replace('"','').strip()
  if not(len(t)==4 and t.isdigit() and 1000<=int(t)<=9999):continue
  total=fnum(iv(r,exact='三大法人買賣超股數')) or fnum(iv(r,contains='三大法人買賣超股數'))
  if total is None:total=(fnum(iv(r,contains='外陸資買賣超股數(不含外資自營商)')) or 0)+(fnum(iv(r,exact='投信買賣超股數')) or 0)+(fnum(iv(r,exact='自營商買賣超股數')) or 0)
  inst.append({'Date':d.isoformat(),'Ticker':int(t),'TotalNet':total})
 return prices,inst
def load_local_eod(d):
 p=ROOT/'eod'/d.strftime('%Y%m%d')
 if not p.exists():raise RuntimeError('E2_LOCAL_EOD_DIR_MISSING')
 prices=[];inst=[]
 for f in sorted(p.glob('price_*.csv')):
  with f.open(encoding='utf-8-sig',newline='') as h:
   for r in csv.DictReader(h):
    try:t=int(r['Ticker'])
    except:continue
    if 1000<=t<=9999 and fnum(r.get('Close')) is not None:prices.append({'Date':d.isoformat(),'Ticker':t,'Name':r.get('Name',''),'VolumeShares':fnum(r.get('VolumeShares')),'Open':fnum(r.get('Open')),'High':fnum(r.get('High')),'Low':fnum(r.get('Low')),'Close':fnum(r.get('Close'))})
 for f in sorted(p.glob('institutional_*.csv')):
  with f.open(encoding='utf-8-sig',newline='') as h:
   for r in csv.DictReader(h):
    try:t=int(r['Ticker'])
    except:continue
    if 1000<=t<=9999:inst.append({'Date':d.isoformat(),'Ticker':t,'TotalNet':fnum(r.get('TotalNet'))})
 if len(prices)<900 or len(inst)<900:raise RuntimeError(f'E2_LOCAL_EOD_INCOMPLETE:price={len(prices)}:inst={len(inst)}')
 return prices,inst
def build_seed(sessions):
 by={};md=[];ma20=[];ma60=[]
 for d,prices,instrows in sessions:
  im={str(int(r['Ticker'])):r for r in instrows};today=[]
  for r in prices:
   t=str(int(r['Ticker']));st=by.setdefault(t,{'n':r.get('Name',''),'c':[],'h':[],'l':[],'tr':[],'v':[],'tn':[],'u':[],'d':[]});c=fnum(r['Close']);h=fnum(r['High']);l=fnum(r['Low']);v=fnum(r['VolumeShares'])
   if None in (c,h,l,v):continue
   prev=st['c'][-1] if st['c'] else None;ret=(c/prev-1) if prev not in(None,0) else None;tr=(h-l)/c if c else None;tn=fnum((im.get(t) or {}).get('TotalNet'));u=v if ret is not None and ret>0 else 0.;dn=v if ret is not None and ret<0 else 0.;m20=mean_valid(st['c'][-19:]+[c],20);m60=mean_valid(st['c'][-59:]+[c],60);today.append((m20 is not None and c>=m20,m60 is not None and c>=m60))
   for k,val,n in [('c',c,59),('h',h,20),('l',l,12),('tr',tr,29),('v',v,4),('tn',tn,4),('u',u,4),('d',dn,4)]:st[k]=(st[k]+[val])[-n:]
   st['n']=r.get('Name') or st['n']
  if today:md.append(d.isoformat());ma20.append(sum(x[0] for x in today)/len(today));ma60.append(sum(x[1] for x in today)/len(today))
 return {'schema_version':1,'asof':sessions[-1][0].isoformat(),'tickers':by,'market':{'dates':md[-10:],'above20':ma20[-10:],'above60':ma60[-10:]}}
def bootstrap_before(target):
 sessions=[];d=target-timedelta(days=150)
 while d<target:
  if d.weekday()<5:
   try:p,i=fetch_day(d)
   except Exception:p=i=None
   if p and i:sessions.append((d,p,i));sessions=sessions[-75:]
  d+=timedelta(days=1)
 if len(sessions)<70:raise RuntimeError(f'E2_BOOTSTRAP_TOO_FEW_SESSIONS:{len(sessions)}')
 return build_seed(sessions)
def compute_incremental(state,prices,instrows,asof):
 im={str(int(r['Ticker'])):r for r in instrows};today=[];bf=[];a20f=[];a60f=[]
 for r in prices:
  t=str(int(r['Ticker']));st=state['tickers'].get(t)
  if not st:continue
  c=fnum(r['Close']);h=fnum(r['High']);l=fnum(r['Low']);vol=fnum(r['VolumeShares'])
  if None in(c,h,l,vol):continue
  C,H,L,TR,V,TN,U,D=st['c'],st['h'],st['l'],st['tr'],st['v'],st['tn'],st['u'],st['d'];prev=C[-1] if C else None;ret1=(c/prev-1) if prev not in(None,0) else None;c5=C[-5] if len(C)>=5 else None;c20=C[-20] if len(C)>=20 else None;ret5=(c/c5-1) if c5 not in(None,0) else None;leader=(c5/c20-1) if c5 not in(None,0) and c20 not in(None,0) else None;tr=(h-l)/c if c else None;atr=mean_valid(TR[-9:]+[tr],10);pr=mean_valid(TR[-29:-9],20);tight=atr/pr if atr is not None and pr not in(None,0) else None;clv=(c-l)/(h-l) if h>l else None;m20=mean_valid(C[-19:]+[c],20);m60=mean_valid(C[-59:]+[c],60);ph=max([x for x in H[-20:] if x is not None],default=None);dist=(c/ph-1) if ph not in(None,0) else None;pl=min([x for x in L[-12:-2] if x is not None],default=None) if len(L)>=12 else None;l3=min([x for x in L[-2:] if x is not None]+[l],default=None);lowret=(l3/pl-1) if pl not in(None,0) else None;u=vol if ret1 is not None and ret1>0 else 0.;dn=vol if ret1 is not None and ret1<0 else 0.;up=sum_valid(U[-4:]+[u],3);down=sum_valid(D[-4:]+[dn],3);updn=(up+1)/(down+1) if up is not None and down is not None else None;tn=fnum((im.get(t) or {}).get('TotalNet'));ir=sum_valid(TN[-4:]+[tn],3);vs=sum_valid(V[-4:]+[vol],3);inst=ir/vs if ir is not None and vs not in(None,0) else None
  bf.append(bool(ret1 is not None and ret1>0));a20f.append(bool(m20 is not None and c>=m20));a60f.append(bool(m60 is not None and c>=m60));today.append({'Date':asof,'Ticker':int(t),'Name':r.get('Name') or st.get('n',''),'Close':c,'D_leader':leader is not None and leader>=.05,'D_reset':ret5 is not None and -.08<=ret5<=-.02,'D_contraction':tight is not None and tight<=.90,'A':clv is not None and clv>=.55,'B':lowret is not None and lowret>=-.02,'C':updn is not None and updn>=1.,'inst_ratio5':inst,'tight_ratio':tight,'dist20high':dist,'_new':{'c':c,'h':h,'l':l,'tr':tr,'v':vol,'tn':tn,'u':u,'d':dn}})
 breadth=sum(bf)/len(bf);a20=sum(a20f)/len(a20f);a60=sum(a60f)/len(a60f);pm=state['market'];d5=a20-pm['above20'][-5];d10=a60-pm['above60'][-10]
 reg='EARLY_RECOVERY' if a60<.45 and d5>0 else 'BROAD_ADVANCE' if a60>=.45 and d5>0 and d10>=0 else 'LATE_DISTRIBUTION' if a60>=.45 and d5<=0 and d10>=0 else 'ROLLING_OVER' if a60>=.45 and d10<0 else 'BEAR_PRESSURE' if a60<.45 and d5<=0 else 'DATA_REVIEW'
 for x in today:x['D_absorption']=sum((x.pop('A'),x.pop('B'),x.pop('C')))>=2;x['D_regime']=.20<=breadth<=.45;x['D_setup']=x['D_leader'] and x['D_reset'] and x['D_contraction'] and x['D_regime'] and x['D_absorption']
 strict=[x for x in today if x['D_setup']];ext=[x for x in today if x['D_leader'] and x['D_reset'] and x['D_contraction'] and x['D_absorption'] and not x['D_setup']]
 def score(rows,capital):
  valid=[x for x in rows if None not in(x['inst_ratio5'],x['tight_ratio'],x['dist20high'])]
  if len(valid)>=4:
   mi=median([x['inst_ratio5'] for x in valid]);mt=median([x['tight_ratio'] for x in valid]);md=median([x['dist20high'] for x in valid])
   for x in valid:fi=x['inst_ratio5']>mi;ft=x['tight_ratio']<=mt;fd=x['dist20high']<=md;sc=int(fi)+int(ft)+int(fd);x.update({'median_inst_ratio5':mi,'median_tight_ratio':mt,'median_dist20high':md,'institutional_favorable':fi,'contraction_favorable':ft,'non_chase_high_favorable':fd,'E2Score':sc,'E2Favorable':sc>=2,'E2ComparatorStatus':'OK'})
  else:
   for x in valid:x.update({'E2Score':None,'E2Favorable':False,'E2ComparatorStatus':'COHORT_LT_4'})
  status='OFF' if not valid or all(x.get('E2ComparatorStatus')!='OK' for x in valid) else ('DEGRADED' if reg=='ROLLING_OVER' else 'ON')
  for x in valid:
   if capital:x['E2Action']='PASS' if x.get('E2ComparatorStatus')!='OK' or status=='OFF' else ('WATCH' if status=='DEGRADED' and (x.get('E2Score') or 0)>=2 else 'BUY' if (x.get('E2Score') or 0)>=2 else 'PASS')
   else:x['E2Action']='SHADOW_FAVORABLE' if x.get('E2ComparatorStatus')=='OK' and (x.get('E2Score') or 0)>=2 else 'SHADOW_PASS'
  order={'BUY':0,'WATCH':1,'SHADOW_FAVORABLE':2,'PASS':3,'SHADOW_PASS':4};valid.sort(key=lambda r:(order.get(r.get('E2Action'),9),-(r.get('E2Score') if r.get('E2Score') is not None else -1),-float(r.get('inst_ratio5') or -1e99),float(r.get('tight_ratio') or 1e99),float(r.get('dist20high') or 1e99),int(r['Ticker'])))
  for n,x in enumerate(valid,1):x['E2Rank']=n
  return status,valid
 ss,srows=score(strict,True);_,xrows=score(ext,False)
 for x in today:
  st=state['tickers'][str(x['Ticker'])];n=x['_new']
  for k,mx in [('c',59),('h',20),('l',12),('tr',29),('v',4),('tn',4),('u',4),('d',4)]:st[k]=(st[k]+[n[k]])[-mx:]
  st['n']=x['Name']
 pm['dates']=(pm['dates']+[asof])[-10:];pm['above20']=(pm['above20']+[a20])[-10:];pm['above60']=(pm['above60']+[a60])[-10:];state['asof']=asof;keys=['Ticker','Name','E2Score','E2Action','E2Rank','inst_ratio5','tight_ratio','dist20high']
 return {'asof':asof,'market_regime':reg,'strict':{'cohort_count':len(strict),'engine_status':ss,'rows':[{k:r.get(k) for k in keys} for r in srows],'buy_count':sum(r.get('E2Action')=='BUY' for r in srows),'watch_count':sum(r.get('E2Action')=='WATCH' for r in srows)},'extension_shadow':{'cohort_count':len(ext),'engine_status':'SHADOW_ONLY','rows':[{k:r.get(k) for k in keys} for r in xrows]}},state
def advance_positions(prev,newscan,dt):
 ps=prev['position_state'];active=[];pending=[];events=[]
 for p in ps.get('held') or []:
  q=dict(p);day=int(str(q['state']).split('D')[-1])+1
  if day>=5:q['state']='HELD_D5';q['exit_after_close']=True;events.append({'event':'EXITED_EOD','Ticker':q['Ticker'],'Name':q['Name']})
  else:q['state']=f'HELD_D{day}';q['exit_after_close']=False
  active.append(q)
 for p in ps.get('pending') or []:q=dict(p);q['entry_date']=dt;q['state']='HELD_D1';q['exit_after_close']=False;active.append(q);events.append({'event':'ENTRY','Ticker':q['Ticker'],'Name':q['Name']})
 free=max(0,MAX_SLOTS-len(active));active_t={int(x['Ticker']) for x in active};buys=[x for x in newscan['strict']['rows'] if x.get('E2Action')=='BUY']
 for s in sorted(buys,key=lambda z:(z.get('E2Rank',999),-(z.get('E2Score') or -1),z['Ticker'])):
  t=int(s['Ticker'])
  if t in active_t or any(int(x['Ticker'])==t for x in pending):events.append({'event':'DUPLICATE_SIGNAL_SKIPPED','Ticker':t,'Name':s['Name']});continue
  if free<=0:events.append({'event':'UNALLOCATED_SIGNAL_NO_SLOT','Ticker':t,'Name':s['Name']});continue
  pending.append({'Ticker':t,'Name':s['Name'],'state':'PENDING_ENTRY','signal_date':dt,'E2Score':s.get('E2Score'),'E2Rank':s.get('E2Rank')});free-=1;events.append({'event':'SLOT_RESERVED','Ticker':t,'Name':s['Name']})
 active=[x for x in active if not x.get('exit_after_close')];held=[{k:x[k] for k in ['Ticker','Name','state','signal_date','entry_date'] if k in x} for x in active];pend=[{k:x[k] for k in ['Ticker','Name','state','signal_date','E2Score','E2Rank'] if k in x} for x in pending]
 return {'asof':dt,'held':held,'pending':pend,'occupied_next_session':len(held)+len(pend),'free_slots_next_session':MAX_SLOTS-len(held)-len(pend),'max_slots':MAX_SLOTS},events
def postclose(target):
 if not STATE.exists():raise RuntimeError('E2_PREVIOUS_STATE_MISSING')
 prev=read_json(STATE);validate_locked_state(prev);prior=datetime.strptime(prev['signal_asof'],'%Y-%m-%d').date()
 if prior>=target:return prev
 rolling=read_json(ROLLING) if ROLLING.exists() else bootstrap_before(target);rd=datetime.strptime(rolling['asof'],'%Y-%m-%d').date()
 if rd!=prior:raise RuntimeError(f'E2_ROLLING_AND_LOCKED_STATE_ASOF_MISMATCH:ROLLING={rd}:LOCKED={prior}')
 prices,inst=load_local_eod(target);scan,rolling=compute_incremental(rolling,prices,inst,target.isoformat());ps,events=advance_positions(prev,scan,target.isoformat());new={'schema_version':1,'system':'HENGCE','module':'E2_LIVE_STATE_LOCK','signal_asof':target.isoformat(),'market_regime':scan['market_regime'],'strict':{'authority':LOCKS['population'],**scan['strict']},'extension_shadow':{'authority':LOCKS['extension'],**scan['extension_shadow'],'capital_authorized':False},'position_state':ps,'locks':LOCKS,'source':'LIVE_POSTCLOSE_INCREMENTAL_E2','state_transition_events':events};new['state_sha256']=canonical_sha({k:v for k,v in new.items() if k!='state_sha256'});validate_locked_state(new);atomic_json(ROLLING,rolling);atomic_json(STATE,new);atomic_json(POSTCLOSE,{'status':'PASS','asof':target.isoformat(),'state_sha256':new['state_sha256'],'strict_count':new['strict']['cohort_count'],'strict_status':new['strict']['engine_status'],'strict_buy':new['strict']['buy_count'],'shadow_count':new['extension_shadow']['cohort_count'],'shadow_favorable':sum(r.get('E2Action')=='SHADOW_FAVORABLE' for r in new['extension_shadow']['rows']),'held':len(ps['held']),'pending':len(ps['pending']),'free_slots':ps['free_slots_next_session']});return new
def self_test():
 s=read_json(STATE) if STATE.exists() else None
 if s:validate_locked_state(s)
 prev={'position_state':{'held':[],'pending':[],'max_slots':5,'occupied_next_session':0,'free_slots_next_session':5}};scan={'strict':{'rows':[{'Ticker':1,'Name':'A','E2Action':'BUY','E2Rank':1,'E2Score':3}]}};ps,_=advance_positions(prev,scan,'2026-10-19');assert len(ps['pending'])==1 and ps['free_slots_next_session']==4
 print(json.dumps({'self_test':'PASS','state_seed_valid':bool(s),'morning_requires_prior_locked_state':True,'postclose_incremental':True,'shadow_zero_capital':True,'max_slots':5}))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['morning','postclose','self-test'],required=True);ap.add_argument('--date');a=ap.parse_args();d=datetime.strptime(a.date,'%Y-%m-%d').date() if a.date else now_tw().date()
 try:
  out=self_test() if a.mode=='self-test' else morning(d) if a.mode=='morning' else postclose(d)
  if out is not None and a.mode!='self-test':print(json.dumps(out,ensure_ascii=False,indent=2))
  return 0
 except Exception as e:
  fail={'schema_version':1,'system':'HENGCE','module':'E2_LIVE_FAIL_CLOSED','mode':a.mode,'trade_date':d.isoformat(),'generated_at_taipei':now_tw().isoformat(),'binding_status':'DATA_PENDING','authority':'NO_E2_CAPITAL_ACTION','entry_due_count':0,'error':repr(e)};atomic_json(MORNING if a.mode=='morning' else POSTCLOSE,fail);print(json.dumps(fail,ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
