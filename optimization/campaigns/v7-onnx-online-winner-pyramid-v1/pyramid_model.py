"""Original-parent inventory-branch data, kernel learning and basket selection.

Ordinary historical production only; teacher-basket quantities, occupancy and
M1 side quotes are not an actual candidate account or compounding path.
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
from onnx import helper, TensorProto, numpy_helper
import onnxruntime as ort

F=Path(__file__).resolve().parent;ROOT=F.parents[2];E=F/'evidence';M=F/'models'
RAW=ROOT/'optimization/artifacts/raw/v7-onnx-online-winner-pyramid-v1'
SOURCE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/market-before-control'
LIFE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-lifecycles.csv'
HASHES={'US30':'B56FAF1B495504A48DF982B91EB2EBF390A8B258E1F2864C6F0A3444A9446586',
        'US100':'EF5DEA36AF11B67B6C34D79BADD713E1F9167A0009D10A5AFB01AACF46ED856B'}
LIFE_SHA='6455361C78BF9227247860E85CB01C0A611CE725E636C28082ED8B505529B78B'
PASSIVE='ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8'
HOLDS={'ZT-M30-US30-RANGE-COMP-61f61deaba':14400,'ZT-M30-US30-RANGE-COMP-64efb16616':21600,
       'ZT-H1-US100-CROSS-IN-14b72317b7':14400,'ZT-M30-US30-INTRADAY-R-2eb111fc46':14400,
       'ZT-H1-US30-RETURN-I-c870a788ec':21600}

def epoch(s):return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())
def server(s):return int(datetime.strptime(s,'%Y.%m.%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
def day(t):return str(datetime.fromtimestamp(int(t),timezone.utc).date())
def sha(p):
    with p.open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest().upper()
def record(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def save(p,data):
    if p.exists():raise RuntimeError('Immutable output '+str(p))
    p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def tape(p,rows,names=None):
    if p.exists():raise RuntimeError('Immutable tape '+str(p))
    keys=names or list(dict.fromkeys(k for row in rows for k in row)) or ['empty']
    with p.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,keys);w.writeheader();w.writerows(rows)
def reserve():
    if shutil.disk_usage(ROOT).free<30*1024**3+384*1024**2:raise RuntimeError('Storage reserve')

def prepare():
    reserve();dest=RAW/'input';dest.mkdir(parents=True,exist_ok=False)
    bindings={SOURCE/(s+'-M1.npy'):v for s,v in HASHES.items()};bindings[LIFE]=LIFE_SHA
    if any(sha(p)!=v for p,v in bindings.items()):raise RuntimeError('Original binding')
    counts={}
    for symbol in HASHES:
        a=np.load(SOURCE/(symbol+'-M1.npy'),mmap_mode='r',allow_pickle=False)
        start,end=np.searchsorted(a['time'],[epoch('2023-12-01'),epoch('2026-01-01')]);own=np.array(a[start:end],copy=True)
        np.save(dest/(symbol+'-M1.npy'),own,allow_pickle=False);counts[symbol]=dict(rows=len(own),first=int(own['time'][0]),last=int(own['time'][-1]))
    with LIFE.open(encoding='utf-8-sig',newline='') as h:
        r=csv.DictReader(h);names=r.fieldnames
        life=[v for v in r if v['event'] in ('BIRTH','CLOSE') and '2024.01.01'<=v['entry_time_server']<'2026.01.01']
    tape(dest/'original-lifecycles.csv',life,names)
    if any(sha(p)!=v for p,v in bindings.items()):raise RuntimeError('Original drift during copy')
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='OWN_ORIGINAL_INPUT_COPIED_BEFORE_FEATURES',rows=counts,lifecycle_rows=len(life),
                source_files=[record(p) for p in bindings],files=[record(p) for p in sorted(dest.iterdir())],free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'INPUT_COPY_V1.json',result);print(json.dumps(result,indent=2),flush=True)

def parents():
    with (RAW/'input/original-lifecycles.csv').open(encoding='utf-8',newline='') as h:rows=list(csv.DictReader(h))
    groups={}
    for row in rows:
        key=(row['component_id'],row['position_identifier']);groups.setdefault(key,[]).append(row)
    result=[]
    for key,parts in groups.items():
        births=[v for v in parts if v['event']=='BIRTH'];closes=[v for v in parts if v['event']=='CLOSE']
        if len(births)!=1 or len(closes)!=1 or any(int(v['partial_observation'])!=0 for v in parts):raise RuntimeError('Incomplete original lifecycle')
        birth,close=births[0],closes[0]
        p=dict(id=key[0]+':'+key[1],component=key[0],position=key[1],symbol=birth['symbol'],direction=int(birth['direction']),
               entry_time=server(birth['entry_time_server']),close_observed=server(close['server_time']),entry_price=float(birth['entry_price']),
               original_stop=float(birth['stop_loss']),planned_risk=float(birth['planned_risk_usd']),volume=float(birth['volume']),
               actual=float(close['actual_net_usd']),stress=float(close['stressed_net_usd']))
        if p['close_observed']<p['entry_time'] or p['volume']<=0:raise RuntimeError('Original parent chronology/volume')
        result.append(p)
    return sorted(result,key=lambda p:(p['entry_time'],p['id']))

def child_path(parent,rates,D):
    times=rates['time'];i=int(np.searchsorted(times,D))
    if i>=len(rates) or times[i]>=D+120 or times[i]>=parent['close_observed']//60*60:return dict(status='NO_ENTRY_QUOTE')
    side=parent['direction'];volume=parent['volume'];first=rates[i];spread=.01*int(first['spread'])
    entry=float(first['open'])+(spread if side>0 else 0);mid=.5*(entry+parent['entry_price'])
    stop=(math.ceil(mid/.01-1e-8) if side>0 else math.floor(mid/.01+1e-8))*.01;distance=side*(entry-stop);gross=distance*volume
    if distance<=0 or gross>.5*parent['planned_risk']+1e-9:return dict(status='RISK_REFUSED',attempted_gross_risk=gross)
    close_due=(parent['close_observed']//60+1)*60
    for bar in rates[i:]:
        t=int(bar['time']);exit_spread=.01*int(bar['spread']);opening=float(bar['open'])+(exit_spread if side<0 else 0)
        adverse=float(bar['low']) if side>0 else float(bar['high'])+exit_spread;quote=None;reason=None;gap=0.
        if side*(opening-stop)<=0:
            quote=opening;reason='STOP_OPEN';gap=max(0.,side*(stop-opening))
        elif t>=close_due:quote=opening;reason='PARENT_OBSERVED_COMPLETE'
        elif side*(adverse-stop)<=0:quote=stop;reason='STOP_MINUTE'
        if reason is not None:
            actual=side*(quote-entry)*volume;stress=actual-(max(spread,exit_spread)+gap)*volume
            return dict(status='COMPLETE',entry_time=int(first['time']),entry_price=entry,entry_spread=spread,volume=volume,
                        direction=side,stop=stop,gross_risk=gross,exit_time=t,exit_price=quote,exit_spread=exit_spread,
                        reason=reason,adverse_gap=gap,actual=actual,stress=stress,label=stress/gross,available=t+60,
                        parent_observed_close=parent['close_observed'],parent_close_proxy_due=close_due)
    raise RuntimeError('Unfinished child source path; input correction required')

def inventory(all_parents,prices,dest):
    observed=[];events=[]
    for p in all_parents:
        row=dict(parent_id=p['id'],component=p['component'],parent_entry=p['entry_time'],parent_close_observed=p['close_observed'],status='PASSIVE_UNCHANGED',D='',features='')
        if p['component']==PASSIVE:observed.append(row);continue
        if p['component'] not in HOLDS:raise RuntimeError('Unknown original market parent')
        a=prices[p['symbol']];times=a['time'];side=p['direction'];riskpoints=side*(p['entry_price']-p['original_stop'])
        if riskpoints<=0:raise RuntimeError('Original initial stop geometry')
        first=int(np.searchsorted(times,p['entry_time']));last=int(np.searchsorted(times,p['close_observed']//60*60-60,side='left'))
        row['status']='NO_TRIGGER';trigger=None
        for i in range(first,last):
            quote=float(a['close'][i])+(.01*int(a['spread'][i]) if side<0 else 0)
            if side*(quote-p['entry_price'])>=riskpoints:trigger=i;break
        if trigger is None:observed.append(row);continue
        i=trigger;D=int(times[i])+60;row['D']=D;row['status']='MISSING_PREFIX'
        if i<30 or not np.array_equal(times[i-30:i+1],np.arange(D-31*60,D,60)):
            observed.append(row);continue
        prefix=a[i-30:i+1];quotes=prefix['close']+(.01*prefix['spread'] if side<0 else 0)
        path_start=int(np.searchsorted(times,(p['entry_time']//60+1)*60));path=a[path_start:i+1]
        adverse=path['low'] if side>0 else path['high']+.01*path['spread'];favorable=path['high'] if side>0 else path['low']+.01*path['spread']
        adverse_points=max(0.,float(np.max(-side*(adverse-p['entry_price'])))) if len(path) else 0.
        favorable_points=max(side*(quotes[-1]-p['entry_price']),float(np.max(side*(favorable-p['entry_price']))) if len(path) else 0.)
        x=np.array([side*(quotes[-1]-p['entry_price'])/riskpoints,(D-p['entry_time'])/HOLDS[p['component']],
                    side*(quotes[-1]-quotes[-6])/riskpoints,side*(quotes[-1]-quotes[-31])/riskpoints,
                    (float(prefix['high'][-30:].max())-float(prefix['low'][-30:].min()))/riskpoints,
                    adverse_points/riskpoints,favorable_points/riskpoints,.01*int(prefix['spread'][-1])/riskpoints])
        if not np.isfinite(x).all():raise RuntimeError('Feature arithmetic')
        child=child_path(p,a,D);row.update(status=child['status'],features=json.dumps(x.tolist()),**{k:v for k,v in child.items() if k!='status'})
        observed.append(row)
        events.append(dict(D=D,parent=p,x=x,child=child))
    tape(dest/'all-parent-trigger-child-paths.csv',observed)
    return sorted(events,key=lambda v:(v['D'],v['parent']['id'])),observed

def basis(X,centers,width):
    d=((np.atleast_2d(X)[:,None,:]-centers[None,:,:])**2).sum(axis=2)
    return np.column_stack([np.ones(len(d)),np.exp(-d/(2*width))])

def fit(events):
    rows=[v for v in events if epoch('2024-01-01')<=v['D'] and v['child']['status']=='COMPLETE' and v['child']['available']<epoch('2025-01-01')]
    if len(rows)<64:return dict(status='FIT_READINESS_NONCONFIRMATION',fit_rows=len(rows))
    raw=np.array([v['x'] for v in rows]);mean=raw.mean(axis=0);sd=np.maximum(raw.std(axis=0),1e-6);X=(raw-mean)/sd
    chosen=[0];distance=((X-X[0])**2).sum(axis=1)
    while len(chosen)<16:
        candidate=distance.copy();candidate[chosen]=-np.inf;i=int(np.argmax(candidate));chosen.append(i)
        distance=np.minimum(distance,((X-X[i])**2).sum(axis=1))
    centers=X[chosen];distances=((centers[:,None,:]-centers[None,:,:])**2).sum(axis=2);values=distances[np.triu_indices(16,1)];positive=values[values>0]
    width=max(1e-6,float(np.median(positive))) if len(positive) else 1e-6
    Phi=basis(X,centers,width);Y=np.array([v['child']['label'] for v in rows]);A=Phi.T@Phi+np.eye(17)
    weights=np.linalg.solve(A,Phi.T@Y);P=np.linalg.inv(A)
    if not np.isfinite(weights).all() or not np.isfinite(P).all():raise RuntimeError('Kernel fit arithmetic')
    return dict(status='FIXED_2024_KERNEL_FIT_COMPLETE',fit_rows=len(rows),fit_first_D=rows[0]['D'],fit_last_D=rows[-1]['D'],
                max_fit_label_available=max(v['child']['available'] for v in rows),mean=mean.tolist(),sd=sd.tolist(),
                centers=centers.tolist(),center_indices=chosen,width_squared=width,weights=weights.tolist(),P=P.tolist())

def graph(initial,path):
    const=[numpy_helper.from_array(np.array(initial['centers'],np.float32),'centers'),numpy_helper.from_array(np.array([1],np.int64),'sum_axis'),
           numpy_helper.from_array(np.array([[2*initial['width_squared']]],np.float32),'two_width'),numpy_helper.from_array(np.ones((1,1),np.float32),'bias'),
           numpy_helper.from_array(np.array([1,16],np.int64),'kernel_shape')]
    nodes=[helper.make_node('Sub',['features','centers'],['diff']),helper.make_node('Mul',['diff','diff'],['square']),
           helper.make_node('ReduceSum',['square','sum_axis'],['distance'],keepdims=0),helper.make_node('Reshape',['distance','kernel_shape'],['distance_row']),
           helper.make_node('Div',['distance_row','two_width'],['scaled']),helper.make_node('Neg',['scaled'],['negative']),
           helper.make_node('Exp',['negative'],['kernel']),helper.make_node('Concat',['bias','kernel'],['phi'],axis=1),
           helper.make_node('MatMul',['phi','weights'],['expected_child_R'])]
    g=helper.make_graph(nodes,'OwnWinnerPyramidKernel',[helper.make_tensor_value_info('features',TensorProto.FLOAT,[1,8]),
        helper.make_tensor_value_info('weights',TensorProto.FLOAT,[17,1])],[helper.make_tensor_value_info('expected_child_R',TensorProto.FLOAT,[1,1]),helper.make_tensor_value_info('phi',TensorProto.FLOAT,[1,17])],const)
    m=helper.make_model(g,opset_imports=[helper.make_opsetid('',17)],producer_name='own-winner-pyramid');m.ir_version=8;onnx.save(m,path)

def role_forecasts(role,events,initial,session,dest):
    weights=np.array(initial['weights']);P=np.array(initial['P']);mean=np.array(initial['mean']);sd=np.array(initial['sd']);centers=np.array(initial['centers'])
    pending=[];updates=[];forecasts=[];selected=[];params=[];sse=zero=0.;scored=0;last_available=0
    for order,event in enumerate(events):
        D=event['D']
        while pending and pending[0][0]<D:
            available,prior_D,parent_id,sequence,past=heapq.heappop(pending);phi=past['phi'];y=past['label']
            sse+=(past['prediction']-y)**2;zero+=y*y;scored+=1
            if role=='online':
                denom=.995+float(phi@P@phi)
                if not math.isfinite(denom) or denom<=0:raise RuntimeError('RLS denominator')
                k=P@phi/denom;weights+=k*(y-float(phi@weights));P=(P-np.outer(k,phi@P))/.995;P=.5*(P+P.T)
                if not np.isfinite(weights).all() or not np.isfinite(P).all() or np.min(np.diag(P))<=0:raise RuntimeError('RLS arithmetic')
                last_available=available
            updates.append(dict(forecast_D=prior_D,parent_id=parent_id,label_available=available,consumed_D=D,
                                label=y,prediction=past['prediction'],learned=int(role=='online')))
        X=(event['x']-mean)/sd;w32=weights.astype(np.float32).reshape(17,1)
        outputs=session.run(None,{'features':X.astype(np.float32).reshape(1,8),'weights':w32});prediction=float(outputs[0][0,0])
        if not math.isfinite(prediction):raise RuntimeError('ONNX inference')
        phi=basis(X,centers,initial['width_squared'])[0];eligible=event['child']['status']=='COMPLETE';chosen=prediction>0 and eligible
        forecasts.append(dict(D=D,parent_id=event['parent']['id'],prediction=prediction,model_intent=int(prediction>0),chosen=int(chosen),
                              matured_labels=len(updates),max_update_label_available=last_available,label_available=event['child'].get('available',''),child_status=event['child']['status']))
        params.append(dict(D=D,parent_id=event['parent']['id'],features=X.astype(np.float32).tolist(),weights=w32[:,0].tolist(),phi=outputs[1][0].tolist()))
        if eligible:
            item=dict(phi=phi,label=event['child']['label'],prediction=prediction)
            heapq.heappush(pending,(event['child']['available'],D,event['parent']['id'],order,item))
        if chosen:selected.append(event)
    tape(dest/(role+'-forecasts.csv'),forecasts);tape(dest/(role+'-updates.csv'),updates);save(dest/(role+'-inference-parameters.json'),params)
    final=dict(weights=weights.tolist(),P=P.tolist(),updates=len(updates) if role=='online' else 0,scored=scored,
               model_MSE=sse/max(1,scored),zero_MSE=zero/max(1,scored),pending=[dict(available=v[0],D=v[1],parent_id=v[2],phi=v[4]['phi'].tolist(),label=v[4]['label'],prediction=v[4]['prediction']) for v in sorted(pending)])
    save(M/('final-'+role+'-state.json'),final)
    return selected,final

def basket(original,children):
    entries=[dict(time=p['close_observed'],actual=p['actual'],stress=p['stress'],kind='PARENT',id=p['id']) for p in original]
    entries.extend(dict(time=v['child']['exit_time'],actual=v['child']['actual'],stress=v['child']['stress'],kind='CHILD',id=v['parent']['id']) for v in children)
    cash=peak=100.;dd=0.;minimum=100.;cashdd=0.
    by_time={}
    for e in entries:by_time[e['time']]=by_time.get(e['time'],0.)+e['stress']
    for t,value in sorted(by_time.items()):
        cash+=value;peak=max(peak,cash);minimum=min(minimum,cash);cashdd=max(cashdd,peak-cash);dd=max(dd,100*(peak-cash)/peak)
    def sums(rows):return dict(events=len(rows),actual=sum(v['actual'] for v in rows),stress=sum(v['stress'] for v in rows))
    return dict(**sums(entries),closed_stress_relativeDD=dd,closed_stress_cashDD=cashdd,min_fixed_basket_cash=minimum,
                halves={name:sums([e for e in entries if (e['time']<epoch('2025-07-01'))==first]) for name,first in [('2025-H1',True),('2025-H2',False)]},
                daily={day(d*86400):sums([e for e in entries if e['time']//86400==d]) for d in range(epoch('2025-01-01')//86400,epoch('2026-01-01')//86400)})

def run():
    reserve();dest=RAW/'selection-v1';dest.mkdir(exist_ok=False);M.mkdir(exist_ok=False)
    prices={s:np.load(RAW/'input'/(s+'-M1.npy'),allow_pickle=False) for s in HASHES}
    for a in prices.values():
        if np.any(np.diff(a['time'])<=0) or np.any(a['spread']<0):raise RuntimeError('Original price ordering/spread')
        if any(not np.isfinite(a[k]).all() or np.any(a[k]<=0) for k in ('open','high','low','close')):raise RuntimeError('Original price arithmetic')
    all_parents=parents();events,inventory_rows=inventory(all_parents,prices,dest);initial=fit(events);save(M/'initial-state.json',initial)
    selected_events=[v for v in events if epoch('2025-01-01')<=v['D']<epoch('2026-01-01')]
    population=[p for p in all_parents if epoch('2025-01-01')<=p['entry_time']<epoch('2026-01-01')]
    if initial['status']!='FIXED_2024_KERNEL_FIT_COMPLETE':
        result=dict(status='FIT_READINESS_NONCONFIRMATION_NO_NATIVE_ECONOMIC_VERDICT',initial=initial,survivor=None,inventory_status=dict(Counter(r['status'] for r in inventory_rows)),files=[record(p) for p in sorted(dest.iterdir())]);save(E/'MODEL_SELECTION_V1.json',result);print(json.dumps(result,indent=2));return
    path=M/'winner-child-kernel.onnx';graph(initial,path);session=ort.InferenceSession(str(path),providers=['CPUExecutionProvider'])
    eligible_events=[v for v in selected_events if v['child']['status']=='COMPLETE']
    control=basket(population,[]);unfiltered=basket(population,eligible_events);reference_increment=sum(v['child']['stress'] for v in eligible_events);roles={}
    for role in ('static','online'):
        chosen,learning=role_forecasts(role,selected_events,initial,session,dest);combined=basket(population,chosen)
        childrows=[dict(parent_id=v['parent']['id'],D=v['D'],**v['child']) for v in chosen];tape(dest/(role+'-children.csv'),childrows)
        def childsum(rows):return dict(starts=len(rows),actual=sum(r['actual'] for r in rows),stress=sum(r['stress'] for r in rows))
        increment=childsum(childrows);halves={name:childsum([r for r in childrows if (r['D']<epoch('2025-07-01'))==first]) for name,first in [('2025-H1',True),('2025-H2',False)]}
        abstention=1-len(chosen)/max(1,len(eligible_events));ddlimit=min(control['closed_stress_relativeDD']+1.5,control['closed_stress_relativeDD']*1.1)
        gates=dict(child_stress_5pct_control=increment['stress']>=.05*control['stress'],positive_child_halves=all(v['actual']>0 and v['stress']>0 for v in halves.values()),
                   combined_improves=combined['actual']>control['actual'] and combined['stress']>control['stress'],positive_combined_halves=all(v['actual']>0 and v['stress']>0 for v in combined['halves'].values()),
                   child_count20=len(chosen)>=20,child_count5_each_half=all(v['starts']>=5 for v in halves.values()),closed_DD_tolerance=combined['closed_stress_relativeDD']<=ddlimit,
                   beats_unfiltered=increment['stress']>=reference_increment,abstains5pct=abstention>=.05)
        roles[role]=dict(child_increment=increment,child_halves=halves,combined=combined,learning=learning,abstention_fraction=abstention,gates=gates)
    qualified=[k for k,v in roles.items() if all(v['gates'].values())];survivor=max(qualified,key=lambda k:(roles[k]['child_increment']['stress'],k=='static')) if qualified else None
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_FIXED_THREE_ROLE_TEACHER_BASKET_SELECTION_ONLY',survivor=survivor,initial=initial,
                control=control,unfiltered=dict(combined=unfiltered,children=len(eligible_events),child_stress_increment=reference_increment),roles=roles,
                original_2025_parents=len(population),eligible_2025_children=len(eligible_events),forecastable_2025_triggers=len(selected_events),inventory_by_entry_year={year:dict(Counter(v['status'] for v in inventory_rows if epoch(year+'-01-01')<=v['parent_entry']<epoch(str(int(year)+1)+'-01-01'))) for year in ('2024','2025')},
                files=[record(p) for base in (M,dest) for p in sorted(base.iterdir()) if p.is_file()],
                scope='Additive original-quantity M1teacherbasket, not feasible sharedcapital/nativefees/financing/tickordering/compounding/equityDD proof.',free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'MODEL_SELECTION_V1.json',result)
    print(json.dumps(dict(status=result['status'],survivor=survivor,fit_rows=initial['fit_rows'],inventory=result['inventory_by_entry_year'],
                         control={k:v for k,v in control.items() if k!='daily'},unfiltered_children=len(eligible_events),unfiltered_stress_increment=reference_increment,
                         roles={k:{'child_increment':v['child_increment'],'child_halves':v['child_halves'],'combined':{a:b for a,b in v['combined'].items() if a!='daily'},'gates':v['gates'],'abstention':v['abstention_fraction']} for k,v in roles.items()}),indent=2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('Use ordinary prepare or run')
