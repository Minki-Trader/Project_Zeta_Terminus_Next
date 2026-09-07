"""Own price-transition learning and preliminary inventory-account simulation.

No terminal/broker interaction. M1 quote assumptions and conservative OHLC
equity bounds do not confer native account, fee, margin or compounding authority.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import deque, Counter
import csv
import gzip
import hashlib
import json
import math
import shutil
import sys
import numpy as np
import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

F=Path(__file__).resolve().parent;ROOT=F.parents[2];E=F/'evidence';M=F/'models'
RAW=ROOT/'optimization/artifacts/raw/v7-onnx-online-inventory-q-policy-v1'
PRICE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/market-before-control/US30-M1.npy'
LIFE=ROOT/'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-lifecycles.csv'
PRICE_SHA='B56FAF1B495504A48DF982B91EB2EBF390A8B258E1F2864C6F0A3444A9446586'
LIFE_SHA='6455361C78BF9227247860E85CB01C0A611CE725E636C28082ED8B505529B78B'
KEYS=('W1','b1','W2','b2');DIRECTIONS=(-1,0,1)

def epoch(s):return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())
def date(t):return str(datetime.fromtimestamp(int(t),timezone.utc).date())
def sha(p):
    with p.open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest().upper()
def record(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def save(p,data):
    if p.exists():raise RuntimeError('Immutable output '+str(p))
    p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def reserve():
    if shutil.disk_usage(ROOT).free<30*1024**3+512*1024**2:raise RuntimeError('Storage reserve')
def serial(p):return {k:v.tolist() for k,v in p.items()}
def copy_params(p):return {k:v.copy() for k,v in p.items()}

class Tape:
    def __init__(self,path,names):
        if path.exists():raise RuntimeError('Immutable tape')
        self.handle=(gzip.open(path,'wt',encoding='utf-8',newline='') if path.suffix=='.gz' else path.open('w',encoding='utf-8',newline=''))
        self.writer=csv.DictWriter(self.handle,names);self.writer.writeheader();self.rows=0
    def row(self,values):self.writer.writerow(values);self.rows+=1
    def close(self):self.handle.close()

def prepare():
    reserve();dest=RAW/'input';dest.mkdir(parents=True,exist_ok=False)
    if sha(PRICE)!=PRICE_SHA or sha(LIFE)!=LIFE_SHA:raise RuntimeError('Original source binding')
    a=np.load(PRICE,mmap_mode='r',allow_pickle=False);start,end=np.searchsorted(a['time'],[epoch('2023-11-01'),epoch('2026-01-01')])
    own=np.array(a[start:end],copy=True);np.save(dest/'US30-M1.npy',own,allow_pickle=False)
    with LIFE.open(encoding='utf-8-sig',newline='') as h:
        reader=csv.DictReader(h);names=reader.fieldnames
        rows=[v for v in reader if v['event'] in ('BIRTH','CLOSE') and '2024.01.01'<=v['entry_time_server']<'2026.01.01']
    with (dest/'original-control-lifecycles.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,names);w.writeheader();w.writerows(rows)
    if sha(PRICE)!=PRICE_SHA or sha(LIFE)!=LIFE_SHA:raise RuntimeError('Original changed during copy')
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='OWN_INPUT_COPIED_BEFORE_FEATURES_OR_OUTCOMES',rows=len(own),first=int(own['time'][0]),last=int(own['time'][-1]),
                lifecycle_rows=len(rows),source_files=[record(PRICE),record(LIFE)],files=[record(p) for p in sorted(dest.iterdir())],free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save(E/'INPUT_COPY_V1.json',result);print(json.dumps(result,indent=2),flush=True)

def contexts(rates,dest):
    t=rates['time']
    if np.any(np.diff(t)<=0) or np.any(rates['spread']<0):raise RuntimeError('Original time/spread')
    if any(not np.isfinite(rates[k]).all() or np.any(rates[k]<=0) for k in ('open','high','low','close')):raise RuntimeError('Original OHLC')
    keys=t//1800;starts=np.r_[0,np.flatnonzero(np.diff(keys))+1];ends=np.r_[starts[1:],len(t)];bars=[]
    for a,b in zip(starts,ends):
        q=rates[a:b];bars.append((int(keys[a])*1800,float(q['high'].max()),float(q['low'].min()),float(q['close'][-1]),.01*int(q['spread'][-1]),int(q['time'][-1])))
    lookup={v[0]+1800:i for i,v in enumerate(bars)};ready={};calendar=[]
    for year in (2024,2025):
        for base in range(epoch(str(year)+'-01-01'),epoch(str(year+1)+'-01-01'),86400):
            for D in range(base+8*3600,base+20*3600,1800):
                row=dict(date=date(base),D=D,status='MISSING_PREFIX',execution_time='',source_mark_time='')
                i=lookup.get(D)
                if i is not None and i>=31 and bars[i-31][0]>=D-7*86400:
                    history=bars[i-31:i+1];high=np.array([v[1] for v in history]);low=np.array([v[2] for v in history]);close=np.array([v[3] for v in history]);scale=max(.01,float(np.mean(high-low)))
                    x=np.array([(close[-1]-close[-2])/scale,(close[-1]-close[-5])/scale,(close[-1]-close[-17])/scale,
                                np.std(np.diff(close))/scale,(high[-4:].max()-low[-4:].min())/scale,
                                2*(close[-1]-low.min())/max(.01,high.max()-low.min())-1,(D-base-8*3600)/(12*3600),history[-1][4]/scale])
                    index=int(np.searchsorted(t,D));row['status']='NO_CURRENT_QUOTE'
                    if index<len(t) and t[index]<D+120:
                        row.update(status='READY',execution_time=int(t[index]),source_mark_time=history[-1][5])
                        ready[D]=dict(D=D,index=index,x=x,scale=scale,mark_bid=history[-1][3],mark_spread=history[-1][4],mark_time=history[-1][5])
                calendar.append(row)
    out=Tape(dest/'calendar-grids.csv',['date','D','status','execution_time','source_mark_time'])
    for row in calendar:out.row(row)
    out.close()
    X=np.array([v['x'] for D,v in ready.items() if D<epoch('2025-01-01')])
    if not len(X):raise RuntimeError('No original fit market states')
    normalization=dict(mean=X.mean(axis=0).tolist(),sd=np.maximum(X.std(axis=0),1e-6).tolist(),fit_market_states=len(X))
    return ready,calendar,normalization

def make_graph(path):
    shapes={'state':[1,14],'W1':[14,32],'b1':[1,32],'W2':[32,3],'b2':[1,3]}
    inputs=[helper.make_tensor_value_info(k,TensorProto.FLOAT,v) for k,v in shapes.items()]
    nodes=[helper.make_node('MatMul',['state','W1'],['h0']),helper.make_node('Add',['h0','b1'],['h1']),helper.make_node('Relu',['h1'],['h']),
           helper.make_node('MatMul',['h','W2'],['q0']),helper.make_node('Add',['q0','b2'],['Q'])]
    graph=helper.make_graph(nodes,'OwnInventoryDoubleDQN',inputs,[helper.make_tensor_value_info('Q',TensorProto.FLOAT,[1,3])])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)],producer_name='own-inventory-policy');model.ir_version=8;onnx.save(model,path)

def greedy(Q):
    Q=np.atleast_2d(Q);ordered=Q[:,[1,2,0]];return np.array([1,2,0])[np.argmax(ordered,axis=1)]
def forward(X,p):return np.maximum(0,X@p['W1']+p['b1'])@p['W2']+p['b2']

class Learner:
    def __init__(self,mode,params,normalization,session,dest):
        self.mode=mode;self.p=copy_params(params);self.target=copy_params(params);self.mean=np.array(normalization['mean']);self.sd=np.array(normalization['sd']);self.session=session
        self.rng=np.random.default_rng(20260908 if mode=='training' else 20260909);self.m={k:np.zeros_like(v) for k,v in params.items()};self.v=copy_params(self.m)
        self.nupdate=0;self.transition_id=0;self.forecasts=0;self.loss_sum=0.;self.matured=0;self.reset_pass();self.snapshots=[]
        self.transitions=Tape(dest/(mode+'-transitions.csv.gz'),['id','pass','D','available','next_D','action','reward','terminal','steps','state','next_state'])
        self.decisions=Tape(dest/(mode+'-decisions.csv.gz'),['pass','D','execution_time','action','direction','Q','state','updates','matured','replay_count'])
        self.learning=Tape(dest/(mode+'-learning.csv.gz'),['pass','D','update','loss','max_sample_available','sample_ids','target_copied'])
        self.current_pass=0
    def reset_pass(self):self.replay=[];self.pointer=0;self.pending=deque()
    def enqueue(self,previous,next_state,reward,next_D,available,terminal):
        self.transition_id+=1;steps=max(1.,(next_D-previous['D'])/1800)
        value=dict(id=self.transition_id,D=previous['D'],available=available,a=previous['a'],r=reward,s=previous['s'].copy(),sn=next_state.copy(),done=terminal,steps=steps)
        self.pending.append(value)
        self.transitions.row(dict(id=value['id'],**{'pass':self.current_pass},D=value['D'],available=available,next_D=next_D,action=value['a'],reward=reward,
                                  terminal=int(terminal),steps=steps,state=json.dumps(value['s'].tolist()),next_state=json.dumps(value['sn'].tolist())))
    def mature(self,D):
        while self.pending and self.pending[0]['available']<D:
            item=self.pending.popleft();self.matured+=1
            if len(self.replay)<4096:self.replay.append(item)
            else:self.replay[self.pointer]=item;self.pointer=(self.pointer+1)%4096
    def gradient_step(self,D):
        if self.mode=='static' or len(self.replay)<32:return
        sample=[self.replay[int(i)] for i in self.rng.choice(len(self.replay),32,replace=False)]
        if max(v['available'] for v in sample)>=D:raise RuntimeError('Noncausal sampled transition')
        S=np.array([v['s'] for v in sample]);N=np.array([v['sn'] for v in sample]);a=np.array([v['a'] for v in sample]);r=np.array([v['r'] for v in sample])
        bootstrap=forward(N,self.target)[np.arange(32),greedy(forward(N,self.p))]
        target=r+np.array([0 if v['done'] else .95**v['steps'] for v in sample])*bootstrap
        H0=S@self.p['W1']+self.p['b1'];H=np.maximum(0,H0);Q=H@self.p['W2']+self.p['b2'];error=Q[np.arange(32),a]-target
        absolute=np.abs(error);huber=np.where(absolute<=1,.5*error**2,absolute-.5)
        loss=float(np.mean(huber)+.001*(np.sum(self.p['W1']**2)+np.sum(self.p['W2']**2)))
        out=np.zeros_like(Q);out[np.arange(32),a]=np.where(absolute<=1,error,np.sign(error))/32
        hidden=(out@self.p['W2'].T)*(H0>0)
        gradient=dict(W1=S.T@hidden+.002*self.p['W1'],b1=hidden.sum(axis=0,keepdims=True),W2=H.T@out+.002*self.p['W2'],b2=out.sum(axis=0,keepdims=True))
        if not math.isfinite(loss) or any(not np.isfinite(v).all() for v in gradient.values()):raise RuntimeError('DQN gradient arithmetic')
        self.nupdate+=1;rate=.001 if self.mode=='training' else .0001
        for k in KEYS:
            self.m[k]=.9*self.m[k]+.1*gradient[k];self.v[k]=.999*self.v[k]+.001*gradient[k]**2
            self.p[k]-=rate*(self.m[k]/(1-.9**self.nupdate))/(np.sqrt(self.v[k]/(1-.999**self.nupdate))+1e-8)
        if any(not np.isfinite(v).all() for v in self.p.values()):raise RuntimeError('DQN parameter arithmetic')
        copied=self.nupdate%256==0
        if copied:self.target=copy_params(self.p)
        self.loss_sum+=loss
        self.learning.row(dict(**{'pass':self.current_pass},D=D,update=self.nupdate,loss=loss,max_sample_available=max(v['available'] for v in sample),
                               sample_ids=json.dumps([v['id'] for v in sample]),target_copied=int(copied)))
    def choose(self,state,D,t):
        self.mature(D);self.gradient_step(D)
        inputs={k:v.astype(np.float32) for k,v in self.p.items()};inputs['state']=state.astype(np.float32).reshape(1,14)
        Q=self.session.run(None,inputs)[0][0]
        if not np.isfinite(Q).all():raise RuntimeError('ONNX Q arithmetic')
        action=int(greedy(Q)[0])
        if self.mode=='training' and self.rng.random()<.1:action=int(self.rng.integers(0,3))
        self.forecasts+=1
        self.decisions.row(dict(**{'pass':self.current_pass},D=D,execution_time=t,action=action,direction=DIRECTIONS[action],Q=json.dumps(Q.tolist()),
                               state=json.dumps(inputs['state'][0].tolist()),updates=self.nupdate,matured=self.matured,replay_count=len(self.replay)))
        if self.mode=='online':self.snapshots.append(np.concatenate([inputs[k].ravel() for k in KEYS]))
        return action
    def final_state(self):
        pending=[dict(id=v['id'],D=v['D'],available=v['available'],a=v['a'],r=v['r'],s=v['s'].tolist(),sn=v['sn'].tolist(),done=v['done'],steps=v['steps']) for v in self.pending]
        replay=[dict(id=v['id'],D=v['D'],available=v['available'],a=v['a'],r=v['r'],s=v['s'].tolist(),sn=v['sn'].tolist(),done=v['done'],steps=v['steps']) for v in self.replay]
        return dict(parameters=serial(self.p),target=serial(self.target),adam_m=serial(self.m),adam_v=serial(self.v),updates=self.nupdate,forecasts=self.forecasts,
                    matured=self.matured,transition_count=self.transition_id,mean_loss=self.loss_sum/max(1,self.nupdate),rng=self.rng.bit_generator.state,
                    replay_pointer=self.pointer,replay=replay,pending=pending)
    def close(self,dest):
        self.transitions.close();self.decisions.close();self.learning.close()
        if self.snapshots:np.savez_compressed(dest/(self.mode+'-inference-weights.npz'),parameters=np.stack(self.snapshots))

TRADE_FIELDS=['pass','episode_date','id','entry_time','exit_time','direction','volume','entry_price','exit_price','stop','initial_gross_risk','entry_spread','exit_spread','adverse_gap','reason','actual','stress','entry_balance','exit_balance','exit_stress_balance']

class Account:
    def __init__(self,trade_tape,equity_tape=None):
        self.actual=100.;self.stress=100.;self.position=None;self.ruined=False;self.next_id=0;self.trades=[];self.refusals=Counter()
        self.actual_peak=self.stress_peak=100.;self.actual_DD=self.stress_DD=0.;self.minimum_actual=self.minimum_stress=100.
        self.trade_tape=trade_tape;self.equity_tape=equity_tape;self.current_pass=0;self.episode='';self.forced_carry=0
    def marked(self,bid,spread):
        if self.position is None:return self.actual,self.stress
        p=self.position;exit_price=bid+(spread if p['direction']<0 else 0);pnl=p['direction']*(exit_price-p['entry_price'])*.01
        return self.actual+pnl,self.stress+pnl-max(p['entry_spread'],spread)*.01
    def observe(self,t,bid,spread,stage):
        actual,stress=self.marked(bid,spread);self.actual_peak=max(self.actual_peak,actual);self.stress_peak=max(self.stress_peak,stress)
        self.actual_DD=max(self.actual_DD,100*(self.actual_peak-actual)/self.actual_peak);self.stress_DD=max(self.stress_DD,100*(self.stress_peak-stress)/self.stress_peak)
        self.minimum_actual=min(self.minimum_actual,actual);self.minimum_stress=min(self.minimum_stress,stress)
        if self.equity_tape is not None:self.equity_tape.row(dict(time=t,stage=stage,actual=actual,stress=stress,balance=self.actual,closed_stress=self.stress,direction=0 if self.position is None else self.position['direction']))
        return actual,stress
    def close_position(self,t,bid,spread,reason,gap=0.):
        if self.position is None:return
        p=self.position;quote=bid+(spread if p['direction']<0 else 0);actual=p['direction']*(quote-p['entry_price'])*.01;stress=actual-(max(p['entry_spread'],spread)+gap)*.01
        self.actual+=actual;self.stress+=stress
        row=dict(**{'pass':self.current_pass},episode_date=self.episode,id=p['id'],entry_time=p['entry_time'],exit_time=t,direction=p['direction'],volume=.01,entry_price=p['entry_price'],exit_price=quote,
                 stop=p['stop'],initial_gross_risk=p['distance']*.01,entry_spread=p['entry_spread'],exit_spread=spread,adverse_gap=gap,reason=reason,actual=actual,stress=stress,entry_balance=p['entry_balance'],exit_balance=self.actual,exit_stress_balance=self.stress)
        self.trades.append(row);self.trade_tape.row(row);self.position=None
        if min(self.actual,self.stress)<=0:self.ruined=True
    def opening(self,t,bar):
        bid=float(bar['open']);spread=.01*int(bar['spread'])
        if self.position is not None:
            p=self.position;quote=bid+(spread if p['direction']<0 else 0)
            if p['direction']*(quote-p['stop'])<=0:
                gap=max(0.,p['direction']*(p['stop']-quote));self.close_position(t,bid,spread,'STOP_OPEN',gap)
        return self.observe(t,bid,spread,'OPEN')
    def set_target(self,t,bar,target):
        current=0 if self.position is None else self.position['direction'];bid=float(bar['open']);spread=.01*int(bar['spread'])
        if target==current:return
        if current:self.close_position(t,bid,spread,'POLICY_FLAT' if target==0 else 'POLICY_REVERSE')
        if not target:return
        capital=min(self.actual,self.marked(bid,spread)[0],self.stress)
        if self.ruined or capital<=0:self.refusals['RUIN_OR_CAPITAL']+=1;return
        distance=math.floor((capital*.02/.01)/.01+1e-8)*.01
        if distance<max(.01,spread+.01):self.refusals['MINIMUM_STOP']+=1;return
        entry=bid+(spread if target>0 else 0);stop=round(entry-target*distance,2)
        if stop<=0:self.refusals['NONPOSITIVE_STOP']+=1;return
        self.next_id+=1;self.position=dict(id=self.next_id,entry_time=t,direction=target,entry_price=entry,entry_spread=spread,stop=stop,distance=distance,entry_balance=self.actual)
    def minute(self,t,bar):
        spread=.01*int(bar['spread'])
        if self.position is not None:
            p=self.position;side=p['direction'];favorable=float(bar['high']) if side>0 else float(bar['low']);adverse=float(bar['low']) if side>0 else float(bar['high'])
            adverse_exit=adverse+(spread if side<0 else 0);touched=side*(adverse_exit-p['stop'])<=0
            reachable_bid=(p['stop']-(spread if side<0 else 0)) if touched else adverse
            self.observe(t,favorable,spread,'FAVORABLE_BOUND');self.observe(t,reachable_bid,spread,'ADVERSE_BOUND')
            if touched:self.close_position(t,reachable_bid,spread,'STOP_MINUTE')
        self.observe(t,float(bar['close']),spread,'CLOSE')
    def state(self,context,learner):
        p=self.position;bid=context['mark_bid'];spread=context['mark_spread'];actual,_=self.marked(bid,spread);capital=min(self.actual,actual,self.stress)
        extra=[0.,0.,0.,0.,capital/100,0.]
        if p is not None:
            quote=bid+(spread if p['direction']<0 else 0);extra=[p['direction'],p['direction']*(quote-p['entry_price'])/p['distance'],
                p['direction']*(quote-p['stop'])/p['distance'],(context['D']-p['entry_time'])/1800/24,capital/100,p['distance']/context['scale']]
        state=np.r_[(context['x']-learner.mean)/learner.sd,extra]
        if not np.isfinite(state).all():raise RuntimeError('Inventory state arithmetic')
        return state

def run_day(base,rates,ready,account,learner):
    times=rates['time'];start=int(np.searchsorted(times,base+8*3600));end=int(np.searchsorted(times,base+20*3600))
    schedule={v['index']:v for D,v in ready.items() if base+8*3600<=D<base+20*3600}
    if not schedule:return dict(decisions=0,forced_carry=False)
    if end>=len(times):raise RuntimeError('No source forced-close quote; input correction')
    if learner.mode=='training' and int(times[end])+60>=epoch('2025-01-01'):raise RuntimeError('Training terminal label outside fit period')
    account.episode=date(base);previous=None;decisions=0
    for i in range(start,end+1):
        bar=rates[i];t=int(bar['time']);account.opening(t,bar)
        if i==end:
            account.close_position(t,float(bar['open']),.01*int(bar['spread']),'FORCED_SESSION')
            eq=account.observe(t,float(bar['open']),.01*int(bar['spread']),'FORCED_FLAT')[1]
            if previous is not None:learner.enqueue(previous,np.zeros(14),(eq-previous['equity'])/2,base+20*3600,t+60,True)
            carry=t>=base+86400;account.forced_carry+=int(carry);return dict(decisions=decisions,forced_carry=carry)
        context=schedule.get(i)
        if context is not None:
            state=account.state(context,learner);eq=account.marked(float(bar['open']),.01*int(bar['spread']))[1]
            if previous is not None:learner.enqueue(previous,state,(eq-previous['equity'])/2,context['D'],t+60,False)
            action=learner.choose(state,context['D'],t);account.set_target(t,bar,DIRECTIONS[action]);decisions+=1
            previous=dict(D=context['D'],s=state.copy(),a=action,equity=eq)
        account.minute(t,bar)
    raise RuntimeError('Unfinished day')

def evaluation(role,params,normalization,session,ready,calendar,rates,dest):
    learner=Learner(role,params,normalization,session,dest);trades=Tape(dest/(role+'-trades.csv.gz'),TRADE_FIELDS)
    equity=Tape(dest/(role+'-equity-bounds.csv.gz'),['time','stage','actual','stress','balance','closed_stress','direction']);account=Account(trades,equity);episode_records=[]
    for base in range(epoch('2025-01-01'),epoch('2026-01-01'),86400):
        before_actual,before_stress=account.actual,account.stress;detail=run_day(base,rates,ready,account,learner)
        episode_records.append(dict(date=date(base),actual_change=account.actual-before_actual,stress_change=account.stress-before_stress,actual_balance=account.actual,stress_balance=account.stress,ruined=account.ruined,**detail))
    if account.position is not None:raise RuntimeError('Unfinished selection position')
    final=learner.final_state();save(M/('final-'+role+'-state.json'),final);learner.close(dest);trades.close();equity.close();save(dest/(role+'-calendar-accounts.json'),episode_records)
    def totals(rows):return dict(trades=len(rows),actual=sum(v['actual'] for v in rows),stress=sum(v['stress'] for v in rows))
    halves={name:totals([v for v in account.trades if (v['exit_time']<epoch('2025-07-01'))==first]) for name,first in [('2025-H1',True),('2025-H2',False)]}
    result=dict(**totals(account.trades),actual_wealth=account.actual,stress_wealth=account.stress,halves=halves,
                actual_equity_bound_relativeDD=account.actual_DD,stress_equity_bound_relativeDD=account.stress_DD,
                minimum_actual_bound=account.minimum_actual,minimum_stress_bound=account.minimum_stress,ruined=account.ruined,refusals=dict(account.refusals),forced_carry_dates=account.forced_carry,
                forecasts=learner.forecasts,updates=learner.nupdate,matured=learner.matured,transitions=learner.transition_id,pending=len(learner.pending),replay_count=len(learner.replay),mean_learning_loss=final['mean_loss'])
    result['gates']=dict(actual_exceeds_original127_89=result['actual']>127.89,stress_exceeds_1_05x118_609=result['stress']>=1.05*118.609,
        both_halves_positive=all(v['actual']>0 and v['stress']>0 for v in halves.values()),atleast100_trades=result['trades']>=100,
        atleast25_each_half=all(v['trades']>=25 for v in halves.values()),actual_equity_bound_DD20=account.actual_DD<=20,no_ruin=not account.ruined,complete_flat=account.position is None)
    return result

def run():
    reserve();dest=RAW/'selection-v1';dest.mkdir(exist_ok=False);M.mkdir(exist_ok=False)
    rates=np.load(RAW/'input/US30-M1.npy',allow_pickle=False);ready,calendar,normalization=contexts(rates,dest);save(M/'market-normalization.json',normalization)
    path=M/'inventory-action-values.onnx';make_graph(path);session=ort.InferenceSession(str(path),providers=['CPUExecutionProvider'])
    rng=np.random.default_rng(20260908);params=dict(W1=rng.normal(0,math.sqrt(2/14),(14,32)),b1=np.zeros((1,32)),W2=rng.normal(0,1/math.sqrt(32),(32,3)),b2=np.zeros((1,3)))
    save(M/'untrained-parameters.json',serial(params));learner=Learner('training',params,normalization,session,dest);training_trades=Tape(dest/'training-trades.csv.gz',TRADE_FIELDS);passes=[]
    for pass_id in range(1,21):
        learner.reset_pass();learner.current_pass=pass_id;start_updates=learner.nupdate;start_loss=learner.loss_sum;actual=stress=0.;count=0
        for base in range(epoch('2024-01-01'),epoch('2025-01-01'),86400):
            account=Account(training_trades);account.current_pass=pass_id;run_day(base,rates,ready,account,learner)
            actual+=account.actual-100;stress+=account.stress-100;count+=len(account.trades)
        result=dict(pass_id=pass_id,training_episode_actual_sum=actual,training_episode_stress_sum=stress,trades=count,updates=learner.nupdate-start_updates,
                    mean_loss=(learner.loss_sum-start_loss)/max(1,learner.nupdate-start_updates),pending_at_pass_end=[dict(id=v['id'],available=v['available']) for v in learner.pending])
        passes.append(result);print(json.dumps(result),flush=True)
    initial=learner.final_state();save(M/'initial-trained-state.json',initial);save(E/'FIT_PASSES_V1.json',passes);learner.close(dest);training_trades.close();params=copy_params(learner.p)
    roles={role:evaluation(role,params,normalization,session,ready,calendar,rates,dest) for role in ('static','online')}
    qualified=[k for k,v in roles.items() if all(v['gates'].values())];survivor=max(qualified,key=lambda k:(roles[k]['stress'],k=='static')) if qualified else None
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_FIXED_CASH_STATIC_ONLINE_INVENTORY_SELECTION_ONLY',survivor=survivor,
                fit_passes=20,fit_forecasts=learner.forecasts,fit_updates=learner.nupdate,cash_reference=dict(actual_wealth=100,stress_wealth=100,trades=0),roles=roles,
                calendar2025=dict(Counter(v['status'] for v in calendar if '2025-01-01'<=v['date']<'2026-01-01')),
                files=[record(p) for folder in (M,dest) for p in sorted(folder.iterdir()) if p.is_file()],free_bytes=shutil.disk_usage(ROOT).free,live_changes=False,
                scope='Continuous100USDfixed0.01M1quote simulator with conservativeOHLCequitybounds; not actualbrokercommission/financing/margin/tickordering/lotcompounding/nativeequityDD authority.')
    save(E/'MODEL_SELECTION_V1.json',result);print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('Use ordinary prepare or run phase')
