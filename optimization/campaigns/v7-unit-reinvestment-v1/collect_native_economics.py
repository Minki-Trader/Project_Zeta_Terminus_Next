"""Preserve complete native economic evidence for the fixed whole-V7 unit policy."""
from collections import Counter,defaultdict
import csv,hashlib,json,math,re,shutil,sys
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
FAMILY=Path(__file__).resolve().parent
RUNTIME=ROOT/'optimization/runtime/v7-unit-reinvestment-v1-portable'
RAW=ROOT/'optimization/artifacts/raw/v7-unit-reinvestment-v1'

def record(p):
    return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest().upper())
def decode(p):
    b=p.read_bytes()
    return b.decode('utf-16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig',errors='replace')
def fields(line):return dict(re.findall(r'([A-Za-z0-9_]+)=([^\s]+)',line))
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
class Tables(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=[];self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row:self.rows.append(self.row);self.row=[]

def collect(tag):
    match=re.fullmatch(r'(selection|confirmation)-(control|reinvest)-v[1-9][0-9]*',tag)
    if not match:raise ValueError('Only the declared whole native unit matrix is supported')
    phase,role=match.groups();name='ZetaV7UIControl' if role=='control' else 'ZetaV7UIReinvest'
    if phase=='confirmation' and json.loads((FAMILY/'evidence/FINALIST_FREEZE_V1.json').read_text())['status']!='ONE_UNCHANGED_NATIVE_UNIT_FINALIST':raise RuntimeError('No finalist authority')
    destination=RAW/phase/tag
    if destination.exists():raise RuntimeError('A native result already exists; preserve it')
    if shutil.disk_usage(ROOT).free<30*1024**3+192*1024**2:raise RuntimeError('Native result storage reserve')
    candidates=[(p,p/'MQL5/Files'/name/'ui'/tag) for p in (RUNTIME/'Tester').glob('Agent-*') if p.is_dir()]
    candidates=[(p,q) for p,q in candidates if q.is_dir()]
    if len(candidates)!=1:raise RuntimeError('Exactly one own native run output is required')
    agent,own=candidates[0];logs=[(p,decode(p)) for p in sorted((agent/'logs').glob('*.log'))];logs=[(p,t) for p,t in logs if 'InpUnitRunTag='+tag in t]
    if len(logs)!=1:raise RuntimeError('Exactly one source log contains the run tag')
    source_log,text=logs[0];anchor=text.rfind('InpUnitRunTag='+tag);start=text.rfind('testing of Experts\\',0,anchor)
    if start<0:raise RuntimeError('No native run header')
    start=text.rfind('\n',0,start)+1;next_start=text.find('testing of Experts\\',anchor+1);end=text.rfind('\n',anchor,next_start) if next_start>=0 else len(text);episode=text[start:end]
    if ' thread finished' not in episode:raise RuntimeError('The native run is incomplete')
    destination.mkdir(parents=True);archived=destination/'Files'/name/'ui'/tag
    shutil.copytree(own,archived);shutil.copytree(RUNTIME/'reports'/tag,destination/'report');(destination/'agent-episode.log').write_text(episode,encoding='utf-8')
    report=list((destination/'report').glob('*.htm'))
    if len(report)!=1:raise RuntimeError('Exactly one complete HTML report is required')
    table=Tables();table.feed(decode(report[0]));labels=defaultdict(list)
    for row in table.rows:
        for i,value in enumerate(row[:-1]):
            if value.endswith(':'):labels[value].append(row[i+1])
    quality=labels.get('히스토리 품질:',labels.get('History Quality:',[]));reasons=[]
    if not quality or not all(re.search(r'^100%\s',v) and ('실제' in v or 'real' in v.lower()) for v in quality):reasons.append('Complete100%real-tick quality is required')
    summaries=[[fields(line) for line in episode.splitlines() if marker in line] for marker in ('V7UI_NATIVE profit=','V7UI_RESULT status=','V7UI_PATH role=')]
    if any(len(v)!=1 for v in summaries):reasons.append('Native/core/account-path summary is not unique')
    contracts=defaultdict(dict)
    for line in episode.splitlines():
        if 'V7UI_CONTRACT stage=' in line:
            item=fields(line);stage=item.pop('stage');symbol=item.pop('symbol');contracts[stage][symbol]=item
    if set(contracts.get('START',{}))!={'US30','US100','US500'} or contracts.get('START')!=contracts.get('END'):reasons.append('Contract/swap snapshots are incomplete orchanged')
    warning_lines=[line for line in episode.splitlines() if any(t in line.lower() for t in ('history mismatch','ticks mismatch','no real tick','real ticks absent','real ticks missing','real ticks discarded','real ticks replaced','history unavailable','critical error'))]
    if warning_lines:reasons.append('Native detail contains an explicit history/tick/execution warning')
    economics=None;epochs={};months={}
    if all(len(v)==1 for v in summaries):
        native,core,path_summary=(v[0] for v in summaries)
        if core['status']!='ECONOMIC' or path_summary['role']!=role or path_summary['tag']!=tag or int(path_summary['complete'])!=1:reasons.append('Trading/account-path completion is not valid')
        if core['status']=='ECONOMIC':
            life=rows(archived/'research/research-lifecycles.csv');births=[v for v in life if v['event']=='BIRTH'];closes=[v for v in life if v['event']=='CLOSE'];path=rows(archived/'equity.csv')
            key=lambda v:(v['component_id'],v['position_identifier'])
            birth_counts=Counter(key(v) for v in births);close_counts=Counter(key(v) for v in closes)
            if birth_counts!=close_counts or any(v!=1 for v in birth_counts.values()) or any(v['partial_observation']!='0' for v in life):reasons.append('Lifecycle accounting is not one-to-one complete')
            actual=float(core['actual_net']);stress=float(core['stressed_net']);positive=float(path_summary['positive_closed_swap']);conservative=stress-positive
            if len(closes)!=int(core['closed']) or abs(sum(float(v['actual_net_usd']) for v in closes)-actual)>1e-5 or abs(sum(float(v['stressed_net_usd']) for v in closes)-stress)>1e-5:reasons.append('Complete trade economics differ from native core totals')
            if len(path)!=int(path_summary['rows']) or not path or abs(float(path[-1]['actual_equity'])-(100+actual))>1e-5 or abs(float(path[-1]['conservative_stress_equity'])-(100+conservative))>1e-5:reasons.append('Complete account path differs from terminalwealth')
            if path and any(a['server']>b['server'] for a,b in zip(path,path[1:])):reasons.append('Account path time regressed')
            bounds=[('2025-H1','2025.01.01','2025.07.01'),('2025-H2','2025.07.01','2026.01.01')]
            if phase=='confirmation':bounds.extend([('2026-H1','2026.01.01','2026.07.01'),('2026-JulAug','2026.07.01','2026.09.01')])
            previous_actual=previous_stress=100.0
            for label,begin,end in bounds:
                marked=[v for v in path if begin<=v['server']<end];closed=[v for v in closes if begin<=v['server_time']<end]
                if not marked:reasons.append('Missing full calendar epoch '+label);continue
                last=marked[-1];now_actual=float(last['actual_equity']);now_stress=float(last['conservative_stress_equity'])
                epochs[label]=dict(closed=len(closed),actual_closed=sum(float(v['actual_net_usd']) for v in closed),stressed_closed=sum(float(v['stressed_net_usd']) for v in closed),actual_marked_change=now_actual-previous_actual,conservative_marked_change=now_stress-previous_stress,ending_actual_equity=now_actual,ending_conservative_equity=now_stress,path_rows=len(marked))
                previous_actual,previous_stress=now_actual,now_stress
            previous_actual=previous_stress=100.0
            for month in sorted({v['server'][:7] for v in path}):
                data=[v for v in path if v['server'].startswith(month)];a=float(data[-1]['actual_equity']);s=float(data[-1]['conservative_stress_equity']);months[month]=dict(actual_return=a/previous_actual-1,conservative_return=s/previous_stress-1,actual_wealth=a,conservative_wealth=s,day_multipliers=sorted({int(v['day_multiplier']) for v in data}));previous_actual,previous_stress=a,s
            dd_cash=float(native['equity_dd']);stress_dd=float(core['stressed_dd']);volume_counts=Counter(float(v['volume']) for v in births)
            economics=dict(actual_net=actual,original_stressed_net=stress,no_positive_swap_stressed_net=conservative,actual_wealth=100+actual,original_stressed_wealth=100+stress,conservative_stressed_wealth=100+conservative,actual_log_growth=math.log1p(actual/100) if actual>-100 else None,conservative_log_growth=math.log1p(conservative/100) if conservative>-100 else None,native_equity_DD_cash=dd_cash,native_equity_DD_percent=float(native['equity_dd_relative_pct']),stressed_closed_DD_cash=stress_dd,conservative_recovery=conservative/max(.01,dd_cash,stress_dd),closed_lifecycles=len(closes),reinvested_lifecycles=sum(v for q,v in volume_counts.items() if q>.01000001),volume_counts=dict(volume_counts),per_component=dict(Counter(v['component_id'] for v in closes)),path_rows=len(path),daily_lot_multipliers=sorted({int(v['day_multiplier']) for v in path}))
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_NATIVE_UNIT_RUN_REQUIRES_ADJACENT_BINDING' if not reasons else 'CORRECTION_REQUIRED_NO_ECONOMIC_VERDICT',run_tag=tag,role=role,phase=phase,reasons=reasons,economics=economics,epochs=epochs,months=months,contracts=dict(contracts),report_labels=dict(labels),explicit_warning_lines=warning_lines,source_agent_log=record(source_log),archived_files=[record(p) for p in sorted(destination.rglob('*')) if p.is_file()],scope='One whole native observation; only the complete immediately adjacent unchanged-input matrix may support economic judgment.',live_changes=False,free_bytes=shutil.disk_usage(ROOT).free)
    (destination/'NATIVE_RESULT_V1.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','run_tag','reasons','economics','epochs')},indent=2))
if __name__=='__main__':collect(sys.argv[1])
