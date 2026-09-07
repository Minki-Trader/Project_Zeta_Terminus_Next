"""Own spatial quote-activity profile, shrunk cell learning and quote selection.

No terminal/broker interaction. Tick activity is not exchange trade volume;
fixed-reference M1 paths do not prove native shared-account compounding.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import hashlib
import heapq
import json
import math
import shutil
import sys
import numpy as np
import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

F=Path(__file__).resolve().parent;ROOT=F.parents[2];E=F/'evidence';M=F/'models'
RAW=ROOT/'optimization/artifacts/raw/v7-onnx-online-volume-profile-return-v1'
PRICE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/market-before-control/US30-M1.npy'
LIFE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-lifecycles.csv'
PRICE_SHA='B56FAF1B495504A48DF982B91EB2EBF390A8B258E1F2864C6F0A3444A9446586'
LIFE_SHA='6455361C78BF9227247860E85CB01C0A611CE725E636C28082ED8B505529B78B'
PASSIVE='ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8'

def epoch(s):return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())
def day(t):return str(datetime.fromtimestamp(int(t),timezone.utc).date())
def sha(p):
    with p.open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest().upper()
def record(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def save(p,data):
    if p.exists():raise RuntimeError('Immutable output '+str(p))
    p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def tape(p,rows,names=None):
    if p.exists():raise RuntimeError('Immutable tape')
    keys=names or list(dict.fromkeys(k for row in rows for k in row)) or ['empty']
    with p.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,keys);w.writeheader();w.writerows(rows)
def reserve():
    if shutil.disk_usage(ROOT).free<30*1024**3+256*1024**2:raise RuntimeError('Storage reserve')

def prepare():
    reserve();dest=RAW/'input';dest.mkdir(parents=True,exist_ok=False)
    if sha(PRICE)!=PRICE_SHA or sha(LIFE)!=LIFE_SHA:raise RuntimeError('Original source binding')
    source=np.load(PRICE,mmap_mode='r',allow_pickle=False);a,b=np.searchsorted(source['time'],[epoch('2023-11-01'),epoch('2026-01-01')])
    own=np.array(source[a:b],copy=True);np.save(dest/'US30-M1.npy',own,allow_pickle=False)
    with LIFE.open(encoding='utf-8-sig',newline='') as h:
        reader=csv.DictReader(h);names=reader.fieldnames
        rows=[r for r in reader if r['component_id']==PASSIVE and r['event'] in ('BIRTH','CLOSE') and '2024.01.01'<=r['entry_time_server']<'2026.01.01']
    tape(dest/'original-passive.csv',rows,names)
    if sha(PRICE)!=PRICE_SHA or sha(LIFE)!=LIFE_SHA:raise RuntimeError('Original drift during copy')
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='OWN_ORIGINAL_INPUT_COPIED_BEFORE_FEATURES',rows=len(own),first=int(own['time'][0]),last=int(own['time'][-1]),lifecycle_rows=len(rows),
                source_files=[record(PRICE),record(LIFE)],files=[record(p) for p in sorted(dest.iterdir())],free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'INPUT_COPY_V1.json',result);print(json.dumps(result,indent=2),flush=True)

def market_structure(rates):
    t=rates['time']
    if np.any(np.diff(t)<=0) or np.any(rates['spread']<0):raise RuntimeError('Original market ordering/spread')
    if any(not np.isfinite(rates[k]).all() or np.any(rates[k]<=0) for k in ('open','high','low','close')) or np.any(rates['high']<np.maximum(rates['open'],rates['close'])) or np.any(rates['low']>np.minimum(rates['open'],rates['close'])):raise RuntimeError('Original prices')
    keys=t//86400;starts=np.r_[0,np.flatnonzero(np.diff(keys))+1];ends=np.r_[starts[1:],len(t)];profiles={};prior={};previous=None;profile_rows=[]
    for a,b in zip(starts,ends):
        date_key=int(keys[a]);q=rates[a:b];low=float(q['low'].min());high=float(q['high'].max());volume=float(q['tick_volume'].sum(dtype=np.float64))
        prior[date_key]=previous;previous=date_key
        if high<=low or volume<=0:
            profiles[date_key]=None;profile_rows.append(dict(date=day(date_key*86400),status='NO_RANGE_OR_VOLUME',low=low,high=high,raw_tick_count=volume,weights='',mode=''));continue
        if np.any(q['close']<low) or np.any(q['close']>high):raise RuntimeError('Profile close outside source range')
        indices=np.minimum(31,np.floor(32*(q['close']-low)/(high-low)).astype(int));weights=np.bincount(indices,weights=q['tick_volume'].astype(float),minlength=32)+1.
        mode_index=int(np.argmax(weights));mode=low+(mode_index+.5)*(high-low)/32
        profiles[date_key]=dict(source_day=date_key,low=low,high=high,weights=weights,peak=float(weights.max()),mode=mode)
        profile_rows.append(dict(date=day(date_key*86400),status='COMPLETE',low=low,high=high,raw_tick_count=volume,weights=json.dumps(weights.tolist()),mode=mode))
    keys=t//1800;starts=np.r_[0,np.flatnonzero(np.diff(keys))+1];ends=np.r_[starts[1:],len(t)];bars={}
    for a,b in zip(starts,ends):
        q=rates[a:b];bars[int(keys[a])*1800]=dict(open=float(q['open'][0]),close=float(q['close'][-1]),spread=.01*int(q['spread'][-1]),last_time=int(q['time'][-1]))
    return profiles,prior,bars,profile_rows

def shadow_path(rates,D,side,mode,completed_spread):
    i=int(np.searchsorted(rates['time'],D))
    if i>=len(rates) or int(rates['time'][i])>=D+120:return dict(status='NO_ENTRY_QUOTE')
    first=rates[i];spread=.01*int(first['spread']);entry=float(first['open'])+(spread if side>0 else 0)
    target=(math.floor(mode/.01+1e-8) if side>0 else math.ceil(mode/.01-1e-8))*.01
    if side*(target-entry)<=2*max(.01,completed_spread,spread):return dict(status='TARGET_OR_COST_REFUSED')
    if 200<max(.01,spread+.01):return dict(status='SPREAD_PROTECTION_REFUSED')
    stop=round(entry-side*200,2)
    if stop<=0:raise RuntimeError('Invalid protected price')
    for bar in rates[i:]:
        t=int(bar['time']);exit_spread=.01*int(bar['spread']);opening=float(bar['open'])+(exit_spread if side<0 else 0)
        quote=None;reason=None;gap=0.
        if side*(opening-stop)<=0:quote=opening;reason='STOP_OPEN';gap=max(0.,side*(stop-opening))
        elif side*(opening-target)>=0:quote=target;reason='TARGET_OPEN'
        elif t>=D+14400:quote=opening;reason='TIME'
        else:
            adverse=float(bar['low']) if side>0 else float(bar['high'])+exit_spread
            favorable=float(bar['high']) if side>0 else float(bar['low'])+exit_spread
            if side*(adverse-stop)<=0:quote=stop;reason='STOP_MINUTE'
            elif side*(favorable-target)>=0:quote=target;reason='TARGET_MINUTE'
        if reason is not None:
            actual=side*(quote-entry)*.01;stress=actual-(max(spread,exit_spread)+gap)*.01
            return dict(status='COMPLETE',entry_time=int(first['time']),exit_time=t,available=t+60,direction=side,volume=.01,entry=entry,entry_spread=spread,
                        stop=stop,target=target,exit_price=quote,exit_spread=exit_spread,reason=reason,adverse_gap=gap,actual=actual,stress=stress,label=stress/2,
                        crossed_source_date=t//86400>int(first['time'])//86400)
    raise RuntimeError('Unfinished profile book at source end; input correction')

def create_events(rates,dest):
    profiles,prior,bars,profile_rows=market_structure(rates);calendar=[];events=[];event_rows=[]
    tape(dest/'prior-source-profiles.csv',profile_rows)
    for base in range(epoch('2024-01-01'),epoch('2026-01-01'),86400):
        key=base//86400;consumed=False
        for D in range(base+8*3600,base+20*3600,1800):
            row=dict(date=day(base),D=D,status='NO_SOURCE_DATE',profile_date='',previous_bin='',current_bin='',mode='',direction='',cell='')
            if key not in profiles:calendar.append(row);continue
            source_day=prior[key];profile=profiles.get(source_day);row['status']='NO_PRIOR_PROFILE'
            if profile is None:calendar.append(row);continue
            row.update(profile_date=day(source_day*86400),mode=profile['mode'])
            if consumed:row['status']='EVENT_ALREADY_CONSUMED';calendar.append(row);continue
            row['status']='MISSING_M30_PREFIX'
            if D-1800 not in bars or D-3600 not in bars:calendar.append(row);continue
            previous,current=bars[D-3600],bars[D-1800];low,high=profile['low'],profile['high'];row['status']='PRICE_OUTSIDE_PROFILE'
            if not (low<=previous['close']<=high and low<=current['close']<=high):calendar.append(row);continue
            index=lambda price:min(31,int(math.floor(32*(price-low)/(high-low))))
            oldbin,newbin=index(previous['close']),index(current['close']);row.update(previous_bin=oldbin,current_bin=newbin,status='NO_BUSY_THIN_CROSSING')
            if not (profile['weights'][oldbin]>.25*profile['peak'] and profile['weights'][newbin]<=.25*profile['peak']):calendar.append(row);continue
            consumed=True;side=1 if profile['mode']>current['close'] else -1;distance=abs(profile['mode']-current['close'])/(high-low)
            bucket=int(np.searchsorted([.125,.25,.5],distance,side='right'));response=int(side*(current['close']-current['open'])>0);cell=(1 if side>0 else 0)*8+response*4+bucket
            row.update(direction=side,cell=cell,status='FIRST_CROSSING')
            if abs(profile['mode']-current['close'])<=2*max(.01,current['spread']):path=dict(status='COMPLETED_COST_REFUSED')
            else:path=shadow_path(rates,D,side,profile['mode'],current['spread'])
            event=dict(D=D,date=day(base),cell=cell,profile_day=source_day,mode=profile['mode'],distance=distance,response=response,direction=side,path=path)
            events.append(event);event_rows.append(dict(D=D,date=day(base),cell=cell,profile_date=day(source_day*86400),mode=profile['mode'],distance=distance,response=response,**path));calendar.append(row)
    tape(dest/'all-calendar-grids.csv',calendar);tape(dest/'all-first-event-shadow-paths.csv',event_rows)
    return events,calendar

def fit(events):
    rows=[v for v in events if epoch('2024-01-01')<=v['D'] and v['path']['status']=='COMPLETE' and v['path']['available']<epoch('2025-01-01')]
    if len(rows)<64:return dict(status='FIT_READINESS_NONCONFIRMATION',fit_labels=len(rows))
    count=np.zeros(16);sums=np.zeros(16)
    for v in rows:count[v['cell']]+=1;sums[v['cell']]+=v['path']['label']
    prior=float(sum(v['path']['label'] for v in rows)/len(rows));means=(sums+8*prior)/(count+8)
    return dict(status='FIXED_2024_SPATIAL_CELL_FIT_COMPLETE',fit_labels=len(rows),first_D=rows[0]['D'],last_D=rows[-1]['D'],max_label_available=max(v['path']['available'] for v in rows),
                global_prior=prior,counts=count.tolist(),sums=sums.tolist(),means=means.tolist())

def build_graph(path):
    inputs=[helper.make_tensor_value_info('cell',TensorProto.INT64,[1]),helper.make_tensor_value_info('means',TensorProto.FLOAT,[16])]
    graph=helper.make_graph([helper.make_node('Gather',['means','cell'],['expected_R'],axis=0)],'OwnSpatialProfilePosterior',inputs,[helper.make_tensor_value_info('expected_R',TensorProto.FLOAT,[1])])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)],producer_name='own-spatial-profile-return');model.ir_version=8;onnx.save(model,path)

def role_run(role,events,initial,session,dest):
    counts=np.array(initial['counts']);sums=np.array(initial['sums']);prior=initial['global_prior'];pending=[];forecasts=[];updates=[];chosen=[];last_available=0;occupied_until=0;sse=zero=0.;scored=0
    for sequence,event in enumerate(events):
        D=event['D']
        while pending and pending[0][0]<D:
            available,old_D,old_sequence,past=heapq.heappop(pending);label=past['label'];cell=past['cell'];sse+=(label-past['prediction'])**2;zero+=label*label;scored+=1
            if role=='online':counts*=.99;sums*=.99;counts[cell]+=1;sums[cell]+=label;last_available=available
            if not np.isfinite(counts).all() or not np.isfinite(sums).all() or np.min(counts)<0:raise RuntimeError('Posterior arithmetic')
            updates.append(dict(forecast_D=old_D,available=available,consumed_D=D,cell=cell,label=label,prediction=past['prediction'],learned=int(role=='online')))
        means=((sums+8*prior)/(counts+8)).astype(np.float32);prediction=float(session.run(None,{'cell':np.array([event['cell']],np.int64),'means':means})[0][0])
        if not math.isfinite(prediction):raise RuntimeError('ONNX inference')
        path=event['path'];eligible=path['status']=='COMPLETE';occupied=D<occupied_until;selected=prediction>0 and eligible and not occupied
        forecasts.append(dict(D=D,date=event['date'],cell=event['cell'],prediction=prediction,model_intent=int(prediction>0),eligible=int(eligible),occupied=int(occupied),selected=int(selected),
                              path_status=path['status'],matured=scored,max_update_available=last_available,means=json.dumps(means.tolist())))
        if eligible:
            heapq.heappush(pending,(path['available'],D,sequence,dict(cell=event['cell'],label=path['label'],prediction=prediction)))
            if selected:chosen.append(dict(D=D,date=event['date'],cell=event['cell'],**path));occupied_until=path['available']
    tape(dest/(role+'-forecasts.csv'),forecasts);tape(dest/(role+'-updates.csv'),updates);tape(dest/(role+'-trades.csv'),chosen)
    final=dict(counts=counts.tolist(),sums=sums.tolist(),global_prior=prior,means=((sums+8*prior)/(counts+8)).tolist(),updates=len(updates) if role=='online' else 0,scored=scored,
               model_MSE=sse/max(1,scored),zero_MSE=zero/max(1,scored),pending=[dict(available=v[0],D=v[1],**v[3]) for v in sorted(pending)])
    save(M/('final-'+role+'-state.json'),final)
    def totals(rows):return dict(trades=len(rows),actual=sum(v['actual'] for v in rows),stress=sum(v['stress'] for v in rows))
    halves={name:totals([v for v in chosen if (v['D']<epoch('2025-07-01'))==first]) for name,first in [('2025-H1',True),('2025-H2',False)]}
    balance=peak=100.;dd=0.;minimum=100.
    for v in sorted(chosen,key=lambda v:v['exit_time']):balance+=v['stress'];peak=max(peak,balance);dd=max(dd,peak-balance);minimum=min(minimum,balance)
    result=dict(**totals(chosen),halves=halves,forecasts=len(forecasts),path_status=dict(Counter(v['path']['status'] for v in events)),learning=final,fixed_quote_closed_cashDD=dd,
                minimum_fixed_quote_cash=minimum,crossed_source_date_trades=sum(v['crossed_source_date'] for v in chosen),
                daily={day(d*86400):totals([v for v in chosen if v['exit_time']//86400==d]) for d in range(epoch('2025-01-01')//86400,epoch('2026-01-01')//86400)})
    result['gates']=dict(stress_exceeds_original_passive_actual=result['stress']>9.66,both_halves_actual_stress_positive=all(v['actual']>0 and v['stress']>0 for v in halves.values()),
                         atleast20_trades=len(chosen)>=20,atleast5_each_half=all(v['trades']>=5 for v in halves.values()))
    return result

def run():
    reserve();dest=RAW/'selection-v1';dest.mkdir(exist_ok=False);M.mkdir(exist_ok=False)
    rates=np.load(RAW/'input/US30-M1.npy',allow_pickle=False);events,calendar=create_events(rates,dest);initial=fit(events);save(M/'initial-state.json',initial)
    if initial['status']!='FIXED_2024_SPATIAL_CELL_FIT_COMPLETE':
        result=dict(status='FIT_READINESS_NONCONFIRMATION_NO_NATIVE_ECONOMIC_VERDICT',initial=initial,survivor=None,events_by_year=dict(Counter(day(v['D'])[:4] for v in events)),files=[record(p) for p in sorted(dest.iterdir())]);save(E/'MODEL_SELECTION_V1.json',result);print(json.dumps(result,indent=2));return
    path=M/'profile-posterior.onnx';build_graph(path);session=ort.InferenceSession(str(path),providers=['CPUExecutionProvider']);selected=[v for v in events if epoch('2025-01-01')<=v['D']<epoch('2026-01-01')]
    roles={role:role_run(role,selected,initial,session,dest) for role in ('static','online')};qualified=[role for role in roles if all(roles[role]['gates'].values())]
    survivor=max(qualified,key=lambda role:(roles[role]['stress'],role=='static')) if qualified else None
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_FIXED_SPATIAL_PROFILE_QUOTE_SELECTION_ONLY',survivor=survivor,initial=initial,roles=roles,
                calendar2025=dict(Counter(v['status'] for v in calendar if '2025-01-01'<=v['date']<'2026-01-01')),events2025=len(selected),
                files=[record(p) for folder in (M,dest) for p in sorted(folder.iterdir()) if p.is_file()],free_bytes=shutil.disk_usage(ROOT).free,live_changes=False,
                scope='Fixed0.01reference M1quote selection; no native sharedrisk/capital/fee/financing/tick/lotcompounding/equityDD proof.')
    save(E/'MODEL_SELECTION_V1.json',result)
    print(json.dumps(dict(status=result['status'],survivor=survivor,initial=initial,calendar=result['calendar2025'],roles={k:{a:b for a,b in v.items() if a!='daily'} for k,v in roles.items()}),indent=2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('Use ordinary prepare or run')
