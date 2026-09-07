"""Own input, fixed error-correction learning and paired quote selection.

No terminal/broker interaction. Quote accounting is a preliminary fixed-volume
selection, not a native shared-account, financing, margin or compounding result.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import deque, Counter
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

FAMILY=Path(__file__).resolve().parent
ROOT=FAMILY.parents[2]
RAW=ROOT/'optimization/artifacts/raw/v7-onnx-online-relative-value-book-v1'
E=FAMILY/'evidence'
MODEL=FAMILY/'models'
SOURCE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/market-before-control'
LIFE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-lifecycles.csv'
HASHES={'US100':'EF5DEA36AF11B67B6C34D79BADD713E1F9167A0009D10A5AFB01AACF46ED856B',
        'US500':'E4E104309434EA8D4965E4AEB737E93806F596173D95D4C606602C28EB5B46D3'}
COMPONENTS={'ZT-H1-US100-CROSS-IN-14b72317b7','ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8'}

def epoch(label):return int(datetime.fromisoformat(label).replace(tzinfo=timezone.utc).timestamp())
def sha(p):
    with p.open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest().upper()
def save(p,value):
    if p.exists():raise RuntimeError('Immutable output exists: '+str(p))
    p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def reserve():
    if shutil.disk_usage(ROOT).free<30*1024**3+384*1024**2:raise RuntimeError('Storage reserve')

def prepare():
    reserve();dest=RAW/'input';dest.mkdir(parents=True,exist_ok=False)
    bindings={SOURCE/(s+'-M1.npy'):v for s,v in HASHES.items()}
    bindings[LIFE]='6455361C78BF9227247860E85CB01C0A611CE725E636C28082ED8B505529B78B'
    for p,value in bindings.items():
        if sha(p)!=value:raise RuntimeError('Original source binding changed')
    rows={}
    for symbol in HASHES:
        original=np.load(SOURCE/(symbol+'-M1.npy'),mmap_mode='r',allow_pickle=False)
        times=original['time'];a=np.searchsorted(times,epoch('2023-12-01'));b=np.searchsorted(times,epoch('2026-01-01'))
        own=np.array(original[a:b],copy=True);np.save(dest/(symbol+'-M1.npy'),own,allow_pickle=False)
        rows[symbol]=dict(rows=len(own),first=int(own['time'][0]),last=int(own['time'][-1]))
    with LIFE.open(encoding='utf-8-sig',newline='') as h:
        reader=csv.DictReader(h);names=reader.fieldnames
        life=[r for r in reader if r['component_id'] in COMPONENTS and r['event'] in ('BIRTH','CLOSE')
              and '2024.01.01'<=r['entry_time_server']<'2026.01.01']
    with (dest/'original-two-engines.csv').open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,names);writer.writeheader();writer.writerows(life)
    for p,value in bindings.items():
        if sha(p)!=value:raise RuntimeError('Original source changed during copy')
    d=dict(utc=datetime.now(timezone.utc).isoformat(),status='OWN_ORIGINAL_INPUT_COPIED_BEFORE_FEATURES',rows=rows,
           lifecycle_rows=len(life),source_hashes={p.relative_to(ROOT).as_posix():v for p,v in bindings.items()},
           files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in dest.iterdir()],
           free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'INPUT_COPY_V1.json',d);print(json.dumps(d,indent=2),flush=True)

def observations(rates):
    bars={};t=rates['time'];keys=t//900
    if np.any(np.diff(t)<=0) or np.any(rates['low']<=0) or np.any(rates['high']<rates['low']) or np.any(rates['spread']<0):
        raise RuntimeError('Original market ordering/price fault')
    starts=np.r_[0,np.flatnonzero(np.diff(keys))+1];ends=np.r_[starts[1:],len(t)]
    for a,b in zip(starts,ends):
        begin=int(keys[a])*900
        if b-a!=15 or not np.array_equal(t[a:b],np.arange(begin,begin+900,60)):continue
        close=float(rates['close'][b-1]);spread=.01*int(rates['spread'][b-1])
        if not math.isfinite(close) or close<=0:raise RuntimeError('Invalid close')
        bars[begin+900]=(close,spread)
    return bars

def build_graph(path):
    inputs=[helper.make_tensor_value_info(name,TensorProto.FLOAT,[1,1]) for name in ('z','drift','persistence')]
    nodes=[];previous='z'
    for step in range(8):
        nodes.append(helper.make_node('Mul',[previous,'persistence'],['product'+str(step)]))
        name='future_z' if step==7 else 'state'+str(step)
        nodes.append(helper.make_node('Add',['product'+str(step),'drift'],[name]));previous=name
    graph=helper.make_graph(nodes,'OwnRelativeValueEightStep',inputs,[helper.make_tensor_value_info('future_z',TensorProto.FLOAT,[1,1])])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)],producer_name='own-relative-value-book');model.ir_version=8
    onnx.save(model,path)

def learn_role(role,states,initial,session,dest):
    theta=np.array(initial['theta'],float);P=np.array(initial['P'],float)
    center,scale=initial['center'],initial['scale'];pending=deque();rows=[]
    updates=scored=missing_labels=0;model_sse=random_sse=0.;last_update=0;labels=[]
    names=['D','status','S','z','c','phi','forecast','target','direction','eligible','reference100','reference500',
           'spread100','spread500','updates','max_update_label_end','label_end']
    with (dest/(role+'-forecasts.csv')).open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,names);writer.writeheader()
        for D in range(epoch('2025-01-01'),epoch('2026-01-01'),900):
            while pending and pending[0]['end']<D:
                item=pending.popleft()
                if item['end'] not in states:
                    missing_labels+=1;labels.append(dict(forecast_D=item['end']-900,label_end=item['end'],consumed_D=D,status='MISSING_FUTURE',observed_z='',prediction=item['prediction'],random_walk=item['x'][1],update_number=updates));continue
                y=(states[item['end']]['S']-center)/scale;x=item['x']
                model_sse+=(y-item['prediction'])**2;random_sse+=(y-x[1])**2;scored+=1
                if role=='online':
                    denom=.999+float(x@P@x)
                    if not math.isfinite(denom) or denom<=0:raise RuntimeError('RLS denominator')
                    k=P@x/denom;theta=theta+k*(y-float(x@theta));P=(P-np.outer(k,x@P))/.999;P=.5*(P+P.T)
                    if not np.isfinite(theta).all() or not np.isfinite(P).all() or np.min(np.diag(P))<=0:raise RuntimeError('RLS arithmetic')
                    updates+=1;last_update=item['end']
                labels.append(dict(forecast_D=item['end']-900,label_end=item['end'],consumed_D=D,status='MATURE',observed_z=y,prediction=item['prediction'],random_walk=x[1],update_number=updates))
            row={name:'' for name in names};row.update(D=D,status='MISSING_PREFIX',updates=updates,max_update_label_end=last_update,
                                                      direction=0,eligible=0,label_end=D+900)
            if D in states:
                obs=states[D];z=(obs['S']-center)/scale;c,phi=[float(np.float32(v)) for v in theta];z32=float(np.float32(z))
                future=float(session.run(None,{'z':np.array([[z32]],np.float32),'drift':np.array([[c]],np.float32),
                                              'persistence':np.array([[phi]],np.float32)})[0][0,0])
                if not math.isfinite(future):raise RuntimeError('ONNX arithmetic')
                predicted=(future-z32)*scale;stationary=0<phi<1
                hurdle=2*(max(.01,obs['spread100'])/obs['reference100']+max(.01,obs['spread500'])/obs['reference500'])
                direction=int(np.sign(predicted)) if stationary and abs(predicted)>hurdle else 0
                eligible=8*3600<=D%86400<20*3600
                row.update(**obs,z=z,c=c,phi=phi,forecast=predicted,target=center+scale*c/(1-phi) if stationary else '',
                           direction=direction,eligible=int(eligible),status='MEAN_REVERTING' if stationary else 'NON_REVERTING')
                pending.append(dict(end=D+900,x=np.array([1.,z]),prediction=c+phi*z32))
            writer.writerow(row);rows.append(row)
    with (dest/(role+'-labels.csv')).open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,list(labels[0]) if labels else ['empty']);writer.writeheader();writer.writerows(labels)
    state=dict(theta=theta.tolist(),P=P.tolist(),updates=updates,scored=scored,missing_mature_labels=missing_labels,
               model_mean_squared_error=model_sse/max(1,scored),random_walk_mean_squared_error=random_sse/max(1,scored),
               pending=[dict(end=p['end'],x=p['x'].tolist(),prediction=p['prediction']) for p in pending])
    save(MODEL/('final-'+role+'-state.json'),state)
    return rows,state

def select_quotes(role,forecasts,prices,dest):
    symbols=('US100','US500');arrays=[prices[s] for s in symbols]
    times=np.union1d(arrays[0]['time'],arrays[1]['time'])
    indices=[np.searchsorted(a['time'],times) for a in arrays]
    cursor=0;book=None;intent=None;book_id=0;books=[];legs=[];intent_rows=[]
    def finish_intent(status):
        nonlocal intent
        if intent is not None:intent_rows.append(dict(D=intent['D'],direction=intent['direction'],status=status));intent=None
    def close_leg(leg,t,quote,spread,reason,gap=0.):
        actual=leg['direction']*(quote-leg['entry'])*leg['volume']
        leg.update(exit_time=int(t),exit_price=quote,exit_spread=spread,reason=reason,actual=actual,
                   stress=actual-(max(leg['entry_spread'],spread)+gap)*leg['volume'],adverse_gap=gap,closed=True)
    def finish_book():
        nonlocal book
        if book is not None and all(leg['closed'] for leg in book['legs']):
            books.append(dict(book_id=book['id'],D=book['D'],entry_time=book['entry_time'],
                              exit_time=max(leg['exit_time'] for leg in book['legs']),direction=book['direction'],target=book['target'],deadline=book['deadline'],
                              actual=sum(leg['actual'] for leg in book['legs']),stress=sum(leg['stress'] for leg in book['legs']),
                              close_reason=book['close_reason'],stop_legs=sum(leg['reason'].startswith('STOP') for leg in book['legs'])))
            legs.extend(book['legs']);book=None
    for time_index,t0 in enumerate(times):
        t=int(t0);present={}
        for n,symbol in enumerate(symbols):
            i=int(indices[n][time_index])
            if i<len(arrays[n]) and int(arrays[n]['time'][i])==t:present[symbol]=arrays[n][i]
        while cursor<len(forecasts) and forecasts[cursor]['D']<=t:
            row=forecasts[cursor];cursor+=1
            if intent is not None:finish_intent('OCCUPIED' if book is not None else 'NO_JOINT_QUOTE')
            if book is not None and row['status']!='MISSING_PREFIX' and row['D']>book['D']:
                if book['direction']*(row['S']-book['target'])>=0 and book['close_request'] is None:
                    book['close_request']=row['D'];book['close_reason']='EQUILIBRIUM'
            if row['eligible'] and row['direction']:
                if book is not None:intent_rows.append(dict(D=row['D'],direction=row['direction'],status='OCCUPIED_AT_DECISION'))
                else:intent=row
        if book is not None and t>=book['deadline'] and book['close_request'] is None:
            book['close_request']=book['deadline'];book['close_reason']='TIME'
        if book is not None:
            for leg in book['legs']:
                if leg['closed'] or leg['symbol'] not in present:continue
                bar=present[leg['symbol']];spread=.01*int(bar['spread']);quote=float(bar['open'])+(spread if leg['direction']<0 else 0)
                if leg['direction']*(quote-leg['stop'])<=0:
                    gap=max(0.,leg['direction']*(leg['stop']-quote));close_leg(leg,t,quote,spread,'STOP_OPEN',gap)
                    book['close_request']=t+60 if book['close_request'] is None else min(book['close_request'],t+60)
                    book['close_reason']='LEG_STOP'
                elif book['close_request'] is not None and t>=book['close_request']:
                    close_leg(leg,t,quote,spread,book['close_reason'])
            finish_book()
        if intent is not None and t>=intent['D']+120:finish_intent('OCCUPIED' if book is not None else 'NO_JOINT_QUOTE')
        if book is None and intent is not None and len(present)==2 and intent['D']<=t<intent['D']+120:
            direction=intent['direction'];spreads={s:.01*int(present[s]['spread']) for s in symbols}
            entries={'US100':float(present['US100']['open'])+(spreads['US100'] if direction>0 else 0),
                     'US500':float(present['US500']['open'])+(spreads['US500'] if direction<0 else 0)}
            volumes={'US100':.01,'US500':max(1,math.floor(entries['US100']/entries['US500']+.5))*.01}
            book_id+=1;book=dict(id=book_id,D=intent['D'],entry_time=t,direction=direction,target=float(intent['target']),
                                 deadline=intent['D']+7200,close_request=None,close_reason='',legs=[])
            for symbol,side in [('US100',direction),('US500',-direction)]:
                ticks=math.floor((2/volumes[symbol])/.01+1e-9);stop=round(entries[symbol]-side*ticks*.01,2)
                book['legs'].append(dict(book_id=book_id,symbol=symbol,entry_time=t,direction=side,volume=volumes[symbol],
                                         entry=entries[symbol],entry_spread=spreads[symbol],stop=stop,closed=False))
            finish_intent('FILLED')
        if book is not None:
            for leg in book['legs']:
                if leg['closed'] or leg['symbol'] not in present:continue
                bar=present[leg['symbol']];spread=.01*int(bar['spread']);opening=float(bar['open'])+(spread if leg['direction']<0 else 0)
                touched=float(bar['low'])<=leg['stop'] if leg['direction']>0 else float(bar['high'])+spread>=leg['stop']
                if touched:
                    quote=min(opening,leg['stop']) if leg['direction']>0 else max(opening,leg['stop'])
                    close_leg(leg,t,quote,spread,'STOP_MINUTE',max(0.,leg['direction']*(leg['stop']-quote)))
                    book['close_request']=t+60 if book['close_request'] is None else min(book['close_request'],t+60)
                    book['close_reason']='LEG_STOP'
            finish_book()
    if intent is not None:finish_intent('OCCUPIED' if book is not None else 'NO_JOINT_QUOTE')
    if book is not None:raise RuntimeError('Unfinished paired quote book at source end; input correction required')
    for name,rows in [('books',books),('legs',legs),('intents',intent_rows)]:
        with (dest/(role+'-'+name+'.csv')).open('w',encoding='utf-8',newline='') as h:
            writer=csv.DictWriter(h,list(rows[0]) if rows else ['empty']);writer.writeheader();writer.writerows(rows)
    def totals(rows):return dict(starts=len(rows),actual=sum(r['actual'] for r in rows),stress=sum(r['stress'] for r in rows))
    halves={name:totals([r for r in books if (r['entry_time']<epoch('2025-07-01'))==first])
            for name,first in [('2025-H1',True),('2025-H2',False)]}
    cash=peak=100.;dd=0.;minimum=100.
    for r in books:cash+=r['stress'];peak=max(peak,cash);dd=max(dd,peak-cash);minimum=min(minimum,cash)
    result=dict(**totals(books),halves=halves,complete_legs=len(legs),intent_status=dict(Counter(r['status'] for r in intent_rows)),
                stop_legs=sum(r['reason'].startswith('STOP') for r in legs),fixed_quote_stress_cash_dd=dd,
                fixed_quote_min_stress_cash=minimum,observed_source_days=len(set((times//86400).tolist())))
    result['daily']={str(datetime.fromtimestamp(day*86400,timezone.utc).date()):totals([r for r in books if r['exit_time']//86400==day])
                     for day in range(epoch('2025-01-01')//86400,epoch('2026-01-01')//86400)}
    result['gates']=dict(stressed_quote_exceeds_original_two_engines_actual=result['stress']>35.38,
        both_halves_stress_positive=all(v['stress']>0 for v in halves.values()),at_least50_pairs=len(books)>=50,
        at_least10_pairs_each_half=all(v['starts']>=10 for v in halves.values()),both_legs_complete=len(legs)==2*len(books))
    return result

def run():
    reserve();dest=RAW/'selection-v1';dest.mkdir(exist_ok=False);MODEL.mkdir(exist_ok=False)
    prices={s:np.load(RAW/'input'/(s+'-M1.npy'),allow_pickle=False) for s in HASHES}
    bars={s:observations(a) for s,a in prices.items()};states={}
    for D in sorted(set(bars['US100'])&set(bars['US500'])):
        a,b=bars['US100'][D],bars['US500'][D]
        states[D]=dict(S=math.log(a[0]/b[0]),reference100=a[0],reference500=b[0],spread100=a[1],spread500=b[1])
    fit_dates=[D for D in states if epoch('2024-01-01')<=D and D+900<epoch('2025-01-01') and D+900 in states]
    current=np.array([states[D]['S'] for D in fit_dates]);future=np.array([states[D+900]['S'] for D in fit_dates])
    center=float(current.mean());scale=max(1e-6,float(current.std()));z=(current-center)/scale;y=(future-center)/scale
    X=np.column_stack([np.ones(len(z)),z]);A=X.T@X+np.diag([1.,10.]);theta=np.linalg.solve(A,X.T@y+np.array([0.,10.]));P=np.linalg.inv(A)
    initial=dict(center=center,scale=scale,theta=theta.tolist(),P=P.tolist(),fit_rows=len(fit_dates),fit_first=fit_dates[0],fit_last=fit_dates[-1])
    save(MODEL/'initial-state.json',initial);graph=MODEL/'relative-value-eight-step.onnx';build_graph(graph)
    session=ort.InferenceSession(str(graph),providers=['CPUExecutionProvider'])
    selection_prices={s:a[(a['time']>=epoch('2025-01-01'))&(a['time']<epoch('2026-01-01'))] for s,a in prices.items()}
    roles={}
    for role in ('static','online'):
        forecasts,state=learn_role(role,states,initial,session,dest);result=select_quotes(role,forecasts,selection_prices,dest)
        result.update(forecasts=len(forecasts),forecast_status=dict(Counter(r['status'] for r in forecasts)),learning=state)
        roles[role]=result
    qualified=[role for role in roles if all(roles[role]['gates'].values())]
    survivor=max(qualified,key=lambda role:(roles[role]['stress'],role=='static')) if qualified else None
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_FIXED_BUNDLE_QUOTE_SELECTION_ONLY',survivor=survivor,
                initial=initial,roles=roles,model_sha256=sha(graph),model_bytes=graph.stat().st_size,calendar_dates=365,
                scope='Paired fixed-volume M1 quote selection; no actual shared V7 account, financing/fees, intraminute order, compounding or nativeDD authority.',
                files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                       for base in (dest,MODEL) for p in sorted(base.iterdir()) if p.is_file()],
                free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'MODEL_SELECTION_V1.json',result)
    print(json.dumps(dict(status=result['status'],survivor=survivor,initial=initial,
                         roles={role:{k:v for k,v in data.items() if k!='daily'} for role,data in roles.items()}),indent=2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('Use normal prepare or run phase')
