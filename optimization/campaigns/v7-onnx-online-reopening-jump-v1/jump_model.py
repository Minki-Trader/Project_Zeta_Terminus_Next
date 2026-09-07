"""Own reopening-jump model and complete fixed-volume quote production.

Historical market data only. No terminal, broker, feasible account replay,
native financing or compounding authority is supplied by this producer.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, deque
import csv
import hashlib
import json
import math
import shutil
import sys
import numpy as np
import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

F=Path(__file__).resolve().parent
ROOT=F.parents[2]
E=F/'evidence'
RAW=ROOT/'optimization/artifacts/raw/v7-onnx-online-reopening-jump-v1'
MODELS=F/'models'
PRICE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/market-before-control/US30-M1.npy'
LIFE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-lifecycles.csv'
PRICE_SHA='B56FAF1B495504A48DF982B91EB2EBF390A8B258E1F2864C6F0A3444A9446586'
LIFE_SHA='6455361C78BF9227247860E85CB01C0A611CE725E636C28082ED8B505529B78B'
PASSIVE='ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8'
PARAMS=('W1','b1','W2','b2')

def ts(date):return int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp())
def date(t):return str(datetime.fromtimestamp(int(t),timezone.utc).date())
def sha(p):
    with p.open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest().upper()
def record(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def save(p,data):
    if p.exists():raise RuntimeError('Immutable output exists: '+str(p))
    p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def reserve():
    if shutil.disk_usage(ROOT).free<30*1024**3+256*1024**2:raise RuntimeError('Storage reserve')
def tape(p,rows,names=None):
    if p.exists():raise RuntimeError('Immutable tape exists')
    with p.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,names or (list(rows[0]) if rows else ['empty']));w.writeheader();w.writerows(rows)

def prepare():
    reserve();dest=RAW/'input';dest.mkdir(parents=True,exist_ok=False)
    if sha(PRICE)!=PRICE_SHA or sha(LIFE)!=LIFE_SHA:raise RuntimeError('Original input binding')
    source=np.load(PRICE,mmap_mode='r',allow_pickle=False)
    a,b=np.searchsorted(source['time'],[ts('2023-11-01'),ts('2026-01-01')]);own=np.array(source[a:b],copy=True)
    np.save(dest/'US30-M1.npy',own,allow_pickle=False)
    with LIFE.open(encoding='utf-8-sig',newline='') as h:
        r=csv.DictReader(h);names=r.fieldnames
        life=[v for v in r if v['component_id']==PASSIVE and v['event'] in ('BIRTH','CLOSE') and '2024.01.01'<=v['entry_time_server']<'2026.01.01']
    tape(dest/'original-passive.csv',life,names)
    if sha(PRICE)!=PRICE_SHA or sha(LIFE)!=LIFE_SHA:raise RuntimeError('Original changed during copy')
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='OWN_INPUT_COPIED_BEFORE_FEATURES',rows=len(own),
                first=int(own['time'][0]),last=int(own['time'][-1]),lifecycle_rows=len(life),
                source_files=[record(PRICE),record(LIFE)],files=[record(p) for p in sorted(dest.iterdir())],
                free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'INPUT_COPY_V1.json',result);print(json.dumps(result,indent=2),flush=True)

def action_path(rates,start,D,side,b,action):
    if start>=len(rates) or int(rates['time'][start])>=D+120:return dict(action=action,status='NO_ENTRY_QUOTE')
    first=rates[start];entry_spread=.01*int(first['spread']);entry=float(first['open'])+(entry_spread if side>0 else 0)
    stop=round(entry-side*b,2);target=round(entry+side*b,2);deadline=D+14400
    for bar in rates[start:]:
        t=int(bar['time']);spread=.01*int(bar['spread']);opening=float(bar['open'])+(spread if side<0 else 0)
        gap=0.;reason=None;quote=None
        if side*(opening-stop)<=0:
            quote=opening;reason='STOP_OPEN';gap=max(0.,side*(stop-opening))
        elif side*(opening-target)>=0:quote=target;reason='TARGET_OPEN'
        elif t>=deadline:quote=opening;reason='TIME'
        else:
            adverse=float(bar['low']) if side>0 else float(bar['high'])+spread
            favorable=float(bar['high']) if side>0 else float(bar['low'])+spread
            if side*(adverse-stop)<=0:quote=stop;reason='STOP_MINUTE'
            elif side*(favorable-target)>=0:quote=target;reason='TARGET_MINUTE'
        if reason is not None:
            actual=side*(quote-entry);stress=actual-max(entry_spread,spread)-gap
            return dict(action=action,status='COMPLETE',entry_time=int(first['time']),exit_time=t,label_available=t+60,
                        direction=side,volume=.01,barrier=b,entry_price=entry,entry_spread=entry_spread,stop=stop,target=target,
                        exit_price=quote,exit_spread=spread,exit_reason=reason,adverse_gap=gap,
                        actual=actual*.01,stress=stress*.01,label=stress/b)
    raise RuntimeError('Unfinished action at original source end; input correction')

def events(rates,dest):
    times=rates['time']
    if np.any(np.diff(times)<=0) or np.any(rates['spread']<0):raise RuntimeError('Market order/spread')
    for name in ('open','high','low','close'):
        if not np.isfinite(rates[name]).all() or np.any(rates[name]<=0):raise RuntimeError('Market price')
    if np.any(rates['high']<rates['low']):raise RuntimeError('Market range')
    daykeys=times//86400;starts=np.r_[0,np.flatnonzero(np.diff(daykeys))+1];ends=np.r_[starts[1:],len(times)]
    daily=[];result=[];calendar={};action_rows=[]
    for a,z in zip(starts,ends):
        block=rates[a:z];first=block[0];day=int(daykeys[a]);D=int(first['time'])+60
        summary=dict(day=day,open=float(first['open']),high=float(block['high'].max()),low=float(block['low'].min()),
                     close=float(block['close'][-1]),last_time=int(block['time'][-1]))
        row=dict(date=date(day*86400),D=D,status='NO_PRIOR_20_DATES',gap='',barrier='',scale='',features='',label_available='',filled=0)
        event=None
        if len(daily)>=20:
            previous=daily[-1];gap=float(first['open'])-previous['close'];closure=int(first['time'])-previous['last_time']
            row['gap']=gap;row['status']='NO_CLOSURE' if closure<1800 else 'ZERO_JUMP'
            if closure>=1800 and gap!=0:
                sign=1 if gap>0 else -1;scale=max(.01,float(np.median([v['high']-v['low'] for v in daily[-20:]])))
                spread=.01*int(first['spread']);b=math.floor(min(200.,max(abs(gap),4*max(.01,spread)))/.01+1e-8)*.01
                x=[math.asinh(abs(gap)/scale),math.asinh(sign*(float(first['close'])-float(first['open']))/scale),
                   math.asinh((float(first['high'])-float(first['low']))/scale),
                   math.asinh(sign*(previous['close']-previous['open'])/scale),
                   math.asinh((previous['high']-previous['low'])/scale),math.log1p(closure/3600)]
                start=int(np.searchsorted(times,D));paths=[action_path(rates,start,D,-sign,b,'FADE'),action_path(rates,start,D,sign,b,'FOLLOW')]
                complete=all(p['status']=='COMPLETE' for p in paths)
                available=max(p['label_available'] for p in paths) if complete else None
                event=dict(D=D,date=row['date'],x=np.array(x),gap=gap,barrier=b,scale=scale,paths=paths,complete=complete,available=available)
                row.update(status='EVENT',barrier=b,scale=scale,features=json.dumps(x),label_available=available or '',filled=int(complete))
                if ts('2024-01-01')<=D<ts('2026-01-01'):
                    result.append(event)
                    for path in paths:action_rows.append(dict(D=D,date=row['date'],**path))
        if ts('2024-01-01')<=D<ts('2026-01-01'):calendar[day]=row
        daily.append(summary)
    full=[]
    for day in range(ts('2024-01-01')//86400,ts('2026-01-01')//86400):
        full.append(calendar.get(day,dict(date=date(day*86400),D='',status='NO_SOURCE_DATE',gap='',barrier='',scale='',features='',label_available='',filled=0)))
    tape(dest/'calendar-and-events.csv',full)
    names=list(dict.fromkeys(k for row in action_rows for k in row));tape(dest/'paired-action-labels.csv',action_rows,names)
    return result,full

def loss_gradient(X,Y,p):
    H=np.tanh(X@p['W1']+p['b1']);pred=H@p['W2']+p['b2'];err=pred-Y
    loss=float(np.mean(err**2)+.001*(np.sum(p['W1']**2)+np.sum(p['W2']**2)))
    derivative=2*err/err.size;hidden=(derivative@p['W2'].T)*(1-H**2)
    grads=dict(W1=X.T@hidden+.002*p['W1'],b1=hidden.sum(axis=0,keepdims=True),
               W2=H.T@derivative+.002*p['W2'],b2=derivative.sum(axis=0,keepdims=True))
    if not math.isfinite(loss) or any(not np.isfinite(v).all() for v in grads.values()):raise RuntimeError('Model arithmetic')
    return loss,grads

def fit(all_events):
    sample=[v for v in all_events if ts('2024-01-01')<=v['D']<ts('2025-01-01') and v['complete'] and v['available']<ts('2025-01-01')]
    if len(sample)<120:return None,dict(status='FIT_READINESS_NONCONFIRMATION',complete_events=len(sample))
    features=np.array([v['x'] for v in sample]);mean=features.mean(axis=0);sd=np.maximum(features.std(axis=0),1e-6)
    X=(features-mean)/sd;Y=np.array([[p['label'] for p in v['paths']] for v in sample]);rng=np.random.default_rng(20260907)
    params=dict(W1=rng.normal(0,1/math.sqrt(6),(6,8)),b1=np.zeros((1,8)),W2=rng.normal(0,1/math.sqrt(8),(8,2)),b2=np.zeros((1,2)))
    first={k:np.zeros_like(v) for k,v in params.items()};second={k:np.zeros_like(v) for k,v in params.items()};trace=[]
    for step in range(1,1001):
        loss,gradient=loss_gradient(X,Y,params)
        for k in PARAMS:
            first[k]=.9*first[k]+.1*gradient[k];second[k]=.999*second[k]+.001*gradient[k]**2
            params[k]-=.01*(first[k]/(1-.9**step))/(np.sqrt(second[k]/(1-.999**step))+1e-8)
        if step==1 or step%100==0:trace.append(dict(step=step,pre_step_loss=loss))
    initial=dict(status='FIXED_2024_FIT_COMPLETE',events=len(sample),first_D=sample[0]['D'],last_D=sample[-1]['D'],
                 max_label_available=max(v['available'] for v in sample),mean=mean.tolist(),sd=sd.tolist(),
                 parameters={k:v.tolist() for k,v in params.items()},loss_trace=trace,final_loss=loss_gradient(X,Y,params)[0])
    return params,initial

def graph(path):
    shapes={'features':[1,6],'W1':[6,8],'b1':[1,8],'W2':[8,2],'b2':[1,2]}
    inputs=[helper.make_tensor_value_info(k,TensorProto.FLOAT,v) for k,v in shapes.items()]
    nodes=[helper.make_node('MatMul',['features','W1'],['hidden_linear']),helper.make_node('Add',['hidden_linear','b1'],['hidden_bias']),
           helper.make_node('Tanh',['hidden_bias'],['hidden']),helper.make_node('MatMul',['hidden','W2'],['output_linear']),
           helper.make_node('Add',['output_linear','b2'],['payoffs'])]
    g=helper.make_graph(nodes,'OwnReopeningJumpActions',inputs,[helper.make_tensor_value_info('payoffs',TensorProto.FLOAT,[1,2])])
    m=helper.make_model(g,opset_imports=[helper.make_opsetid('',17)],producer_name='own-reopening-jump');m.ir_version=8;onnx.save(m,path)

def run_role(role,selected,initial,session,dest):
    params={k:np.array(initial['parameters'][k],float) for k in PARAMS};mean=np.array(initial['mean']);sd=np.array(initial['sd'])
    pending=deque();forecasts=[];updates=[];trades=[];inferences=[];scored=0;sse=zero_sse=0.;last_label=0
    for event in selected:
        D=event['D']
        while pending and pending[0]['event']['available']<D:
            item=pending.popleft();past=item['event'];Y=np.array([[v['label'] for v in past['paths']]])
            sse+=float(np.sum((item['pred']-Y)**2));zero_sse+=float(np.sum(Y**2));scored+=2
            if role=='online':
                _,gradient=loss_gradient(item['X'],Y,params)
                for k in PARAMS:params[k]-=.005*gradient[k]
                if any(not np.isfinite(v).all() for v in params.values()):raise RuntimeError('Online arithmetic')
                last_label=past['available']
            updates.append(dict(forecast_D=past['D'],label_available=past['available'],consumed_D=D,learned=int(role=='online'),
                                fade_label=Y[0,0],follow_label=Y[0,1],fade_prediction=item['pred'][0,0],follow_prediction=item['pred'][0,1]))
        X=((event['x']-mean)/sd).reshape(1,6);inputs={k:params[k].astype(np.float32) for k in PARAMS};inputs['features']=X.astype(np.float32)
        prediction=session.run(None,inputs)[0]
        if not np.isfinite(prediction).all():raise RuntimeError('ONNX inference arithmetic')
        choice=int(np.argmax(prediction[0]));action=('FADE','FOLLOW')[choice] if prediction[0,choice]>0 else 'ABSTAIN'
        forecasts.append(dict(D=D,date=event['date'],fade_prediction=float(prediction[0,0]),follow_prediction=float(prediction[0,1]),
                              choice=action,filled=int(event['complete'] and action!='ABSTAIN'),max_update_label_available=last_label,
                              matured_pairs=len(updates),label_available=event['available'] or '',gap=event['gap'],barrier=event['barrier']))
        inferences.append(dict(D=D,parameters={k:inputs[k].tolist() for k in PARAMS},features=inputs['features'].tolist()))
        if event['complete']:
            pending.append(dict(event=event,X=X,pred=prediction.astype(float)))
            if action!='ABSTAIN':trades.append(dict(D=D,date=event['date'],**event['paths'][choice]))
    tape(dest/(role+'-forecasts.csv'),forecasts);tape(dest/(role+'-updates.csv'),updates);tape(dest/(role+'-trades.csv'),trades)
    save(dest/(role+'-inference-parameters.json'),inferences)
    final=dict(parameters={k:v.tolist() for k,v in params.items()},matured_pairs=len(updates),parameter_updates=len(updates) if role=='online' else 0,
               pending=[dict(D=v['event']['D'],label_available=v['event']['available'],X=v['X'].tolist(),prediction=v['pred'].tolist()) for v in pending],
               scored_action_labels=scored,model_MSE=sse/max(1,scored),zero_MSE=zero_sse/max(1,scored))
    save(MODELS/('final-'+role+'-state.json'),final)
    def sums(rows):return dict(starts=len(rows),actual=sum(t['actual'] for t in rows),stress=sum(t['stress'] for t in rows))
    halves={label:sums([t for t in trades if (t['D']<ts('2025-07-01'))==first]) for label,first in [('2025-H1',True),('2025-H2',False)]}
    cash=peak=100.;dd=0.;minimum=100.
    for trade in sorted(trades,key=lambda t:t['exit_time']):
        cash+=trade['stress'];peak=max(peak,cash);dd=max(dd,peak-cash);minimum=min(minimum,cash)
    result=dict(**sums(trades),halves=halves,choices=dict(Counter(v['choice'] for v in forecasts)),forecasts=len(forecasts),learning=final,
                fixed_closed_quote_cashDD=dd,minimum_fixed_quote_cash=minimum,
                daily={date(day*86400):sums([t for t in trades if t['exit_time']//86400==day]) for day in range(ts('2025-01-01')//86400,ts('2026-01-01')//86400)})
    result['gates']=dict(stress_exceeds_original_passive_actual=result['stress']>9.66,
                         both_halves_actual_stress_positive=all(v['actual']>0 and v['stress']>0 for v in halves.values()),
                         at_least30_starts=len(trades)>=30,at_least10_each_half=all(v['starts']>=10 for v in halves.values()))
    return result

def run():
    reserve();dest=RAW/'selection-v1';dest.mkdir(exist_ok=False);MODELS.mkdir(exist_ok=False)
    rates=np.load(RAW/'input/US30-M1.npy',allow_pickle=False);all_events,calendar=events(rates,dest)
    params,initial=fit(all_events);save(MODELS/'initial-state.json',initial)
    if params is None:
        save(E/'MODEL_SELECTION_V1.json',dict(status=initial['status'],initial=initial,survivor=None));print(json.dumps(initial));return
    path=MODELS/'reopening-jump-actions.onnx';graph(path);session=ort.InferenceSession(str(path),providers=['CPUExecutionProvider'])
    selected=[v for v in all_events if ts('2025-01-01')<=v['D']<ts('2026-01-01')]
    roles={role:run_role(role,selected,initial,session,dest) for role in ('static','online')}
    qualified=[role for role,v in roles.items() if all(v['gates'].values())]
    survivor=max(qualified,key=lambda role:(roles[role]['stress'],role=='static')) if qualified else None
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_FIXED_REOPENING_QUOTE_SELECTION_ONLY',survivor=survivor,
                initial=initial,roles=roles,events=len(selected),complete_paired_labels=sum(v['complete'] for v in selected),
                calendar2025=dict(Counter(v['status'] for v in calendar if '2025-01-01'<=v['date']<'2026-01-01')),
                files=[record(p) for base in (MODELS,dest) for p in sorted(base.iterdir()) if p.is_file()],
                scope='Fixed0.01M1 quote preliminary selection, not feasible shared-account/tick/fee/financing/compounding/nativeDD proof.',
                free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'MODEL_SELECTION_V1.json',result)
    print(json.dumps(dict(status=result['status'],survivor=survivor,fit_events=initial['events'],calendar=result['calendar2025'],
                         roles={k:{key:value for key,value in v.items() if key!='daily'} for k,v in roles.items()}),indent=2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('Use ordinary prepare or run phase')
