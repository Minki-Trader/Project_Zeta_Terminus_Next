"""Account the complete, fixed Family23 native economic comparison and its own ledgers."""
from pathlib import Path
from html.parser import HTMLParser
import datetime as dt
import json, math, re
import numpy as np
import pandas as pd
import onnxruntime as ort
import native_campaign as n

TAGS=['cs-v3','static-v3','co-v3','online-v3']
START=1735689600
MID=1751328000
END=1767225600

class ReportRows(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.row=[]
  if tag in ['td','th'] and self.row is not None:self.cell=[]
 def handle_data(self,data):
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag in ['td','th'] and self.cell is not None:
   self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
  if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None

def decode(path):
 b=path.read_bytes()
 if b[:2] in [b'\xff\xfe',b'\xfe\xff']:return b.decode('utf-16')
 if b[:200].count(b'\x00')>len(b[:200])/4:return b.decode('utf-16-le')
 return b.decode('utf-8-sig',errors='replace')

def drawdown(values):
 a=np.r_[100.,np.asarray(values,dtype=float)];peak=np.maximum.accumulate(a)
 return {'cash':float(np.max(peak-a)),'percent':float(np.max((peak-a)/peak)*100)}

def ordinary(value):
 if isinstance(value,dict):return {str(k):ordinary(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [ordinary(v) for v in value]
 if isinstance(value,np.generic):return value.item()
 return value

def record(path,obj):
 value=ordinary(obj);json.dumps(value,allow_nan=False)
 n.save(path,value)

def epoch(e,x,start,end):
 columns=['balance','equity','conservative_closed','conservative_equity']
 left=e[e.server<start];right=e[e.server<end]
 a=left.iloc[-1] if len(left) else dict.fromkeys(columns,100.)
 b=right.iloc[-1]
 closed=x[(x.completion_msc>=start*1000)&(x.completion_msc<end*1000)]
 result={k:float(b[k]-a[k]) for k in columns}
 result.update(actual_closed=float(closed.deal_actual.sum()),conservative_closed_deals=float((closed.deal_stressed-closed.swap.clip(lower=0)).sum()),closed_lifecycles=int(closed.full_exit.sum()))
 return result

def account(tag,model_session,model):
 root=n.RAW/'native'/tag
 complete=json.loads((root/'complete.json').read_text())
 e=pd.read_csv(root/'files/learning/equity.csv')
 en=pd.read_csv(root/'files/learning/entries.csv')
 x=pd.read_csv(root/'files/learning/exits.csv')
 f=pd.read_csv(root/'files/learning/forecasts.csv')
 u=pd.read_csv(root/'files/learning/updates.csv')
 final=json.loads((root/'files/learning/final.json').read_text())
 candidates=pd.read_csv(root/'files/research/research-candidates.csv')
 lifecycle=pd.read_csv(root/'files/research/research-lifecycles.csv')
 log=decode(root/'Agent-127.0.0.1-3000-episode.log')
 htmls=list((root/'reports').glob('*.htm'))
 if len(htmls)!=1:raise RuntimeError('One complete native HTML report is required: '+tag)
 parser=ReportRows();parser.feed(decode(htmls[0]));rows=parser.rows
 pairs={row[i].rstrip(':'):row[i+1] for row in rows for i in range(len(row)-1) if row[i].endswith(':')}
 native_line=re.findall(r'V7RR1_NATIVE ([^\r\n]+)',log)
 result_line=re.findall(r'V7RR1_RESULT ([^\r\n]+)',log)
 if len(native_line)!=1 or len(result_line)!=1:raise RuntimeError('One native final outcome is required: '+tag)
 native=dict(re.findall(r'(\w+)=([^ ]+)',native_line[0]))
 core=dict(re.findall(r'(\w+)=([^ ]+)',result_line[0]))
 native={k:float(v) for k,v in native.items()}
 bars=np.load(n.RAW/'input-v2/US30-M1.npy',allow_pickle=False)
 bars=bars[(bars['time']>=START)&(bars['time']<END)]
 missing_minutes=np.setdiff1d(bars['time']//60,e.minute.unique()).tolist()
 extra_minutes=np.setdiff1d(e.minute.unique(),bars['time']//60).tolist()
 conservative_deals=x.deal_stressed-x.swap.clip(lower=0)
 conservative_net=float(conservative_deals.sum());actual_net=float(x.deal_actual.sum())
 closed_dd=drawdown(100+conservative_deals.cumsum())
 minute_dd=drawdown(e.conservative_equity)
 robust_denominator=max(native['equity_dd'],closed_dd['cash'],minute_dd['cash'],.01)
 issues=[]
 def evidence(condition,message):
  if not bool(condition):issues.append(message)
 evidence(not complete['input_drift'],'Frozen input drift')
 quality=pairs.get('History Quality',pairs.get('\ud788\uc2a4\ud1a0\ub9ac \ud488\uc9c8',''))
 evidence('100%' in quality,'Native history quality not100percent')
 tick_starts={symbol:re.findall(re.escape(symbol)+r'\s*:\s*real ticks begin from ([^\r\n]+)',log) for symbol in n.SYMBOLS}
 evidence(all(tick_starts.values()),'Required symbol has no native real-tick start record')
 bad_tick_lines=[line for line in log.splitlines() if re.search(r'\t(?:History|Ticks|Tester)\t',line) and re.search(r'real ticks (?:absent|discarded)|generated ticks|mismatch|no history data|history synchronization error',line,re.I)]
 evidence(not bad_tick_lines,'Native history substitution/incompleteness line')
 final_operating=[line for line in log.splitlines() if ' final portfolio=' in line]
 evidence(len(final_operating)==1,'Missing exact final native operating state')
 if len(final_operating)==1:
  for healthy in ['safety_stopped=false','persistence_failed=false','broker_mismatch=false','foreign_exposure=false','protection_calc_failures=0','protection_mismatches=0','aggregate_planned_risk=0.0000']:
   evidence(healthy in final_operating[0],'Native final operating fault: '+healthy)
 evidence(not missing_minutes and not extra_minutes,'Incomplete full native minute equity coverage')
 evidence(e.server.is_monotonic_increasing and int(e.server.iloc[-1])==final['final_server'],'Minute chronology/final mismatch')
 evidence(final['faults']==0 and e.faults.max()==0 and core['status']=='ECONOMIC','EA/learning/final economic fault')
 evidence(len(e)==final['minute_marks'] and len(f)==final['forecasts'],'Final ledger counters mismatch')
 evidence(abs(actual_net-native['profit'])<1e-7 and abs(actual_net-float(core['actual_net']))<1e-7,'Actual native/core/exit reconciliation mismatch')
 evidence(abs(100+actual_net-e.balance.iloc[-1])<1e-7 and abs(e.equity.iloc[-1]-e.balance.iloc[-1])<1e-7,'Final actual equity mismatch')
 evidence(abs(100+conservative_net-e.conservative_closed.iloc[-1])<1e-7 and abs(e.conservative_equity.iloc[-1]-e.conservative_closed.iloc[-1])<1e-7,'Final conservative equity mismatch')
 evidence(int(e.positions.iloc[-1])==0 and int(e.pending_orders.iloc[-1])==0 and abs(e.aggregate_risk.iloc[-1])<1e-8,'Final native account/owned risk not flat')
 evidence(len(en)==x.position_id.nunique() and en.position_id.is_unique,'Own entry/exit population mismatch')
 full=x[x.full_exit==1].copy()
 evidence(full.position_id.is_unique and set(full.position_id)==set(en.position_id) and len(full)==final['labels'],'Own complete lifecycle mismatch')
 evidence(final['checkpoint_sequence']==final['checkpoint_readbacks'],'Checkpoint write/readback count mismatch')
 evidence((candidates.research_dropped_records==0).all() and (lifecycle.research_dropped_records==0).all(),'Dropped normal operating evidence')
 deal_rows=[r for r in rows if len(r)==13 and re.fullmatch(r'\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}',r[0]) and r[3] in ['buy','sell'] and r[4] in ['in','out','in/out']]
 report_deals=pd.DataFrame(deal_rows,columns=['time','deal','symbol','type','entry','volume','price','order','commission','swap','profit','balance','comment'])
 for column in ['deal','volume','price','order','commission','swap','profit','balance']:report_deals[column]=pd.to_numeric(report_deals[column].str.replace(' ','',regex=False))
 native_in=report_deals[report_deals.entry=='in'];native_out=report_deals[report_deals.entry=='out']
 evidence(abs(report_deals[['commission','swap','profit']].to_numpy().sum()-actual_net)<1e-7,'Native HTML deals do not reconcile to actual wealth')
 evidence(len(native_out)==len(x) and set(native_out.deal)==set(x.deal),'Native HTML exits do not match complete own exit ledger')
 evidence(len(native_in)==len(en) and set(native_in.order)==set(en.position_id),'Native HTML entries do not match complete own entry ledger')
 if len(native_out)==len(x) and set(native_out.deal)==set(x.deal):
  joined=x.merge(native_out,on='deal',validate='one_to_one',suffixes=('_own','_report'))
  evidence(np.max(np.abs(joined.swap_own-joined.swap_report))<1e-7,'Native financing ledger mismatch')
 if len(native_in)==len(en) and set(native_in.order)==set(en.position_id):
  joined=en.merge(native_in,left_on='position_id',right_on='order',validate='one_to_one',suffixes=('_own','_report'))
  evidence(np.max(np.abs(joined.volume_own-joined.volume_report))<1e-7,'Native actual filled quantity mismatch')
 symbols=dict(en.component.map(lambda c:model['component_ids'][int(c)]).value_counts())
 contracts=json.loads((n.RAW/'input-v2/market.json').read_text())['contracts']
 symbol_for={0:'US30',1:'US30',2:'US100',3:'US30',4:'US30',5:'US100'}
 volume_mismatches=[]
 for row in en.itertuples():
  contract=contracts[symbol_for[row.component]];step=contract['volume_step'];minimum=contract['volume_min']
  if row.volume<minimum-1e-8 or row.volume>contract['volume_max']+1e-8 or abs(row.volume/step-round(row.volume/step))>1e-7:volume_mismatches.append(int(row.position_id))
  if final['role']>0:
   expected=.01 if row.component==5 else max(minimum,math.floor(.01*row.capital/100/step+1e-9)*step)
   if abs(expected-row.volume)>1e-7:volume_mismatches.append(int(row.position_id))
 evidence(not volume_mismatches,'Legal or frozen capital-proportional quantity mismatch')
 evidence((en.planned_entry_risk<=en.capital*en.risk_fraction+1e-6).all(),'Entry budget exceeds frozen per-position cap')
 admitted=candidates[candidates.admission_reason=='ADMITTED']
 evidence((admitted.attempted_planned_risk_usd<=admitted.position_cap_usd+1e-6).all(),'Buffered entry risk exceeds native position admission cap')
 evidence((admitted.attempted_aggregate_after_usd<=admitted.aggregate_cap_usd+1e-6).all(),'Buffered aggregate risk exceeds native admission cap')
 max_onnx_error=0.;causal_errors=[];bias=np.zeros(6);update_index=0
 if final['role']>0:
  evidence(f.forecast_id.tolist()==list(range(1,len(f)+1)) and f.server.is_monotonic_increasing,'Forecast sequence or chronology mismatch')
  evidence((f.decision_bar<=f.server).all(),'Decision bar is in the future')
  features=f[['f'+str(i) for i in range(14)]].to_numpy(dtype=np.float32)
  predictions=np.array([model_session.run(None,{model_session.get_inputs()[0].name:a.reshape(1,14)})[0].ravel()[0] for a in features])
  max_onnx_error=float(np.max(np.abs(predictions-f.frozen_prediction)))
  evidence(max_onnx_error<2e-6,'Stored native prediction differs from exact own frozen ONNX')
  expected_features=np.zeros_like(features)
  for i,row in enumerate(f.itertuples()):
   expected_features[i,row.component]=1
   expected_features[i,row.component+6]=np.float32(np.sign(row.feature)*math.log1p(abs(row.feature)))
   expected_features[i,12:14]=[row.direction,row.direction*row.prior_direction]
  evidence(np.max(np.abs(features-expected_features))<2e-6,'Frozen raw feature schema mismatch')
  forecast_map=f.set_index('forecast_id');closed_map=full.set_index('position_id');entry_map=en.set_index('position_id')
  evidence(u.position_id.is_unique,'Completed own label applied more than once')
  expected_applied=0
  for row in u.itertuples():
   z=closed_map.loc[row.position_id];entry=entry_map.loc[row.position_id]
   label=float(np.clip(z.lifecycle_stressed/z.planned_entry_risk,-2,2))
   expected_after=np.clip(.97*bias[row.component]+.03*(label-z.frozen_prediction),-.5,.5) if final['role']==2 else bias[row.component]
   if not (row.completion_msc//1000<row.applied_server and row.observed_server<=row.applied_server and row.completion_msc==z.completion_msc and row.forecast_id==entry.forecast_id and row.component==entry.component):causal_errors.append('attribution or strict-second chronology')
   if abs(row.label-label)>1e-10 or abs(row.frozen_prediction-z.frozen_prediction)>1e-10 or abs(row.bias_before-bias[row.component])>1e-10 or abs(row.bias_after-expected_after)>1e-10:causal_errors.append('own residual update equation')
   bias[row.component]=expected_after
   if final['role']==2:expected_applied+=1
   if row.update_id!=expected_applied:causal_errors.append('update count')
  evidence(np.max(np.abs(np.asarray(final['bias'])-bias))<1e-10,'Final bias does not reconcile to own complete updates')
  evidence(len(full)-len(u)==final['pending_mature_labels'],'Pending completed-label count mismatch')
  evidence(expected_applied==final['updates'],'Actual online update counter mismatch')
  bias[:]=0
  applied=u.to_dict('records')
  for row in f.itertuples():
   while update_index<len(applied) and applied[update_index]['applied_server']<=row.server:
    q=applied[update_index];bias[int(q['component'])]=q['bias_after'];update_index+=1
   expected_seen=sum(1 for q in applied[:update_index] if q['mode']=='ONLINE')
   if abs(row.bias-bias[row.component])>1e-10 or row.updates_seen!=expected_seen:causal_errors.append('forecast does not see exactly prior own state')
   expected_fraction=.04 if row.component==5 else .04*np.clip(.75+.5*math.tanh(row.score/.25),.25,1)
   if abs(row.score-row.frozen_prediction-row.bias)>1e-10 or abs(row.risk_fraction-expected_fraction)>1e-10:causal_errors.append('frozen score/risk equation')
  for row in en.itertuples():
   q=forecast_map.loc[row.forecast_id]
   if row.entry_server<q.server or row.component!=q.component or abs(row.frozen_prediction-q.frozen_prediction)>1e-10:causal_errors.append('entry forecast identity')
  evidence(not causal_errors,'Own-learning accounting or causal mismatch')
 else:
  evidence(len(f)==0 and len(u)==0 and final['updates']==0,'Exact control adopted learning')
 halves={'2025H1':epoch(e,x,START,MID),'2025H2':epoch(e,x,MID,END)}
 monthly={}
 for month in range(1,13):
  a=int(dt.datetime(2025,month,1,tzinfo=dt.timezone.utc).timestamp())
  b=int(dt.datetime(2025+int(month==12),month%12+1,1,tzinfo=dt.timezone.utc).timestamp())
  monthly[f'2025-{month:02d}']=epoch(e,x,a,b)
 larger=en[en.volume>.01000001]
 metrics=dict(tag=tag,role=final['role'],actual_net=actual_net,actual_terminal_wealth=100+actual_net,actual_log_growth=math.log((100+actual_net)/100),conservative_net=conservative_net,conservative_terminal_wealth=100+conservative_net,conservative_log_growth=math.log((100+conservative_net)/100),native_equity_dd_percent=native['equity_dd_relative_pct'],native_equity_dd_cash=native['equity_dd'],conservative_closed_dd=closed_dd,conservative_minute_dd=minute_dd,robust_recovery=conservative_net/robust_denominator,robust_denominator=robust_denominator,closed_lifecycles=len(full),actual_cost_surcharge=float((x.deal_actual-x.deal_stressed).sum()),removed_positive_financing=float(x.swap.clip(lower=0).sum()),halves=halves,monthly=monthly)
 metrics['operating_evidence']=dict(final=final,forecasts=len(f),mature_label_rows=len(u),actual_online_updates=final['updates'],max_exact_onnx_prediction_error=max_onnx_error,causal_errors=causal_errors[:20],expected_minutes=len(bars),observed_unique_minutes=e.minute.nunique(),force_final_extra_marks=len(e)-e.minute.nunique(),missing_minutes=missing_minutes,extra_minutes=extra_minutes,quality=quality,tick_starts=tick_starts,bad_tick_lines=bad_tick_lines,report_deals=len(report_deals),report_commission=float(report_deals.commission.sum()),report_swap=float(report_deals.swap.sum()),report_profit=float(report_deals.profit.sum()),component_entry_counts=symbols,admission_rows=len(admitted),max_marked_margin_fraction=float((e.margin/e.equity).max()),max_marked_risk=float(e.aggregate_risk.max()),volume_counts={str(k):int(v) for k,v in en.volume.value_counts().sort_index().items()},original_daily_units=sorted(e.original_daily_units.unique().tolist()),larger_lot_entries=len(larger),larger_lot_first=None if not len(larger) else ordinary(larger.iloc[0].to_dict()),volume_mismatches=volume_mismatches,issues=issues,valid=not issues)
 metrics['sources']=[dict(path=str(p.relative_to(n.REPO)),bytes=p.stat().st_size,sha256=n.sha(p)) for p in [root/'complete.json',htmls[0],root/'Agent-127.0.0.1-3000-episode.log']]
 return metrics,e

def main():
 # All four paths must already be complete before any selection judgment.
 for tag in TAGS:
  if not (n.RAW/'native'/tag/'complete.json').exists():raise RuntimeError('Fixed native matrix is incomplete: '+tag)
 post_path=n.CAMPAIGN/'evidence/NATIVE_POST_MATRIX_INPUT_RECHECK_V1.json'
 post=json.loads(post_path.read_text())
 if post['mismatches'] or not all(post[k] for k in ['contracts_unchanged','version_unchanged','frozen_inputs_unchanged']):raise RuntimeError('Native historical inputs changed across the matrix')
 opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
 session=ort.InferenceSession(str(n.CAMPAIGN/'models/v7-risk-score.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
 model=json.loads((n.CAMPAIGN/'models/model.json').read_text())
 metrics={};equity={}
 for tag in TAGS:metrics[tag],equity[tag]=account(tag,session,model)
 comparisons={}
 for control_tag,tag in [(TAGS[0],TAGS[1]),(TAGS[2],TAGS[3])]:
  c=metrics[control_tag];m=metrics[tag]
  tolerance=min(c['native_equity_dd_percent']+1.5,c['native_equity_dd_percent']*1.1)
  gates=dict(valid_complete_evidence=c['operating_evidence']['valid'] and m['operating_evidence']['valid'],actual_wealth_log_growth=m['actual_terminal_wealth']>c['actual_terminal_wealth'] and m['actual_log_growth']>c['actual_log_growth'],conservative_net_5percent=m['conservative_net']>=c['conservative_net']*1.05,robust_recovery=m['robust_recovery']>c['robust_recovery'],both_halves_positive=all(all(v[k]>0 for k in ['balance','equity','conservative_closed','conservative_equity','actual_closed','conservative_closed_deals']) for v in m['halves'].values()),dd_within_fixed_tolerance=m['native_equity_dd_percent']<=tolerance)
  nominal=m['native_equity_dd_percent']<=c['native_equity_dd_percent']
  eligible=all(gates.values())
  comparisons[tag]=dict(control=control_tag,gates=gates,nominal_dd_pass=nominal,dd_tolerance_ceiling=tolerance,dd_miss_percentage_points=m['native_equity_dd_percent']-c['native_equity_dd_percent'],dd_exception_used=eligible and not nominal,conservative_net_uplift_percent=(m['conservative_net']/c['conservative_net']-1)*100,eligible=eligible)
 eligible=[tag for tag,v in comparisons.items() if v['eligible']]
 finalist=max(eligible,key=lambda tag:(metrics[tag]['conservative_net'],metrics[tag]['role']==2)) if eligible else None
 control_ledger_identity={leaf:n.sha(n.RAW/'native'/TAGS[0]/'files/learning'/leaf)==n.sha(n.RAW/'native'/TAGS[2]/'files/learning'/leaf) for leaf in ['equity.csv','entries.csv','exits.csv','forecasts.csv','updates.csv','final.json']}
 result=dict(utc=n.utc(),family=23,program=5,status='COMPLETE_FIXED_NATIVE_SELECTION',period=['2025-01-01','2026-01-01'],initial_usd=100,metrics=metrics,comparisons=comparisons,finalist=finalist,candidate_2026_opened=False,development_next='Finish this fixed bundle then PAUSED_BY_USER; no successor',source_sha256=n.sha(Path(__file__)),post_matrix_input_evidence=dict(path=str(post_path.relative_to(n.REPO)),sha256=n.sha(post_path)),control_ledger_identity=control_ledger_identity)
 record(n.CAMPAIGN/'evidence/NATIVE_SELECTION_RESULT_V2.json',result)
 print(json.dumps(ordinary({'metrics':{k:{q:v[q] for q in ['actual_net','conservative_net','native_equity_dd_percent','robust_recovery']}|{'issues':v['operating_evidence']['issues']} for k,v in metrics.items()},'comparisons':comparisons,'finalist':finalist}),indent=2))
 return result,equity

def figure(result,equity):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import matplotlib.dates as mdates
 from matplotlib import font_manager
 font=Path('C:/Windows/Fonts/malgun.ttf')
 if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']='Malgun Gothic'
 plt.rcParams['axes.unicode_minus']=False
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'#f7f8fc','axes.facecolor':'white'})
 fig,axes=plt.subplots(2,2,figsize=(14,9),layout='constrained')
 labels={TAGS[0]:'기존 V7',TAGS[1]:'고정 ONNX',TAGS[3]:'ONNX + 온라인 학습'}
 colors={TAGS[0]:'#455469',TAGS[1]:'#d58a19',TAGS[3]:'#007e88'}
 for tag,label in labels.items():
  e=equity[tag];series=e.iloc[::30].copy()
  if series.index[-1]!=e.index[-1]:series=pd.concat([series,e.iloc[[-1]]])
  times=pd.to_datetime(series.server,unit='s')
  axes[0,0].plot(times,series.equity,label=label,color=colors[tag],lw=1.15)
  axes[0,1].plot(times,np.log(series.equity/100),label=label,color=colors[tag],lw=1.15)
  dd=(1-e.conservative_equity/e.conservative_equity.cummax())*100
  axes[1,0].plot(times,dd.loc[series.index],color=colors[tag],lw=1.05)
  en=pd.read_csv(n.RAW/'native'/tag/'files/learning/entries.csv')
  market=en[en.component!=5]
  axes[1,1].step(pd.to_datetime(market.entry_server,unit='s'),market.volume,where='post',color=colors[tag],lw=1.6,label=label)
  m=result['metrics'][tag]
  axes[0,0].annotate(f"${m['actual_terminal_wealth']:.2f}",xy=(times.iloc[-1],series.equity.iloc[-1]),xytext=(4,0),textcoords='offset points',color=colors[tag],fontsize=9)
 axes[0,0].set_title('실제 계좌 자산');axes[0,0].set_ylabel('USD');axes[0,0].legend(loc='upper left',fontsize=9)
 axes[0,1].set_title('초기 $100 대비 로그 성장');axes[0,1].set_ylabel('ln(자산 / 100)')
 axes[1,0].set_title('보수적 자산의 분 단위 낙폭');axes[1,0].set_ylabel('%');axes[1,0].invert_yaxis()
 axes[1,1].set_title('실제 체결된 시장가 주문 수량');axes[1,1].set_ylabel('lot');axes[1,1].set_ylim(bottom=0)
 for ax in axes.flat:
  ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'));ax.margins(x=.045)
 native=' / '.join(f"{labels[t]} {result['metrics'][t]['native_equity_dd_percent']:.2f}%" for t in labels)
 fig.suptitle('V7 — 2025년 실제 틱 비교\n초기 $100 · 1:100 · US30/US100/US500 원본 시세',fontsize=16,fontweight='bold')
 fig.supxlabel('MT5 전체 틱 기준 최대 DD: '+native+'\n곡선은 30분 간격 표시. 판정은 전체 거래·분 원장과 MT5 전체 틱 수치 사용. Passive 수량은 0.01 lot 유지.',fontsize=9)
 folder=n.CAMPAIGN/'results';folder.mkdir(exist_ok=True)
 path=folder/'native-selection-v4.png'
 if path.exists():raise RuntimeError('Existing figure must be retained')
 fig.savefig(path,dpi=155);plt.close(fig)
 record(folder/'FIGURE_MANIFEST_V2.json',dict(path=str(path.relative_to(n.REPO)),bytes=path.stat().st_size,sha256=n.sha(path),selection_sha256=n.sha(n.CAMPAIGN/'evidence/NATIVE_SELECTION_RESULT_V2.json'),description='Actual native equity/loggrowth, complete conservative minute DD and actual filled market lot progression; no simulated curve or future path'))
 return path

if __name__=='__main__':main()
