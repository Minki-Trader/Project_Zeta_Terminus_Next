"""Owned fixed MT5 economic campaign operations; no synthetic tests or proxy orders."""
from pathlib import Path
import ctypes, datetime as dt, hashlib, json, os, shutil, subprocess, time
import MetaTrader5 as mt5
import numpy as np
import psutil

CAMPAIGN=Path(__file__).resolve().parents[1]
REPO=CAMPAIGN.parents[2]
RUNTIME=REPO/'optimization/runtime/v7-native-entry-compound-completion-v1-portable'
RAW=REPO/'optimization/artifacts/raw/v7-native-entry-compound-completion-v1'
SYMBOLS=['US30','US100','US500']
FRAMES={'M1':mt5.TIMEFRAME_M1,'M15':mt5.TIMEFRAME_M15,'M30':mt5.TIMEFRAME_M30,'H1':mt5.TIMEFRAME_H1}
CONTRACT_FIELDS=['digits','point','trade_calc_mode','trade_mode','trade_exemode','trade_contract_size','trade_tick_size','trade_tick_value_profit','trade_tick_value_loss','volume_min','volume_max','volume_step','volume_limit','trade_stops_level','trade_freeze_level','swap_mode','swap_long','swap_short','swap_rollover3days','margin_initial','margin_maintenance','currency_base','currency_profit','currency_margin']

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest().upper()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file()) if p.exists() else 0
def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def capacity(stage):
 cap_path=CAMPAIGN/'evidence/PROSPECTIVE_STORAGE_AMENDMENT_V2.json'
 if not cap_path.exists():cap_path=CAMPAIGN/'evidence/PROSPECTIVE_STORAGE_AMENDMENT_V1.json'
 caps=json.loads(cap_path.read_text())
 used={'runtime':size(RUNTIME),'raw':size(RAW),'source':size(CAMPAIGN)}
 free=shutil.disk_usage(REPO).free
 required=caps['reserve']+sum(max(0,caps[k+'_cap']-used[k]) for k in used)
 row=dict(utc=utc(),stage=stage,free=free,required_free=required,used=used,valid=free>=required and all(used[k]<=caps[k+'_cap'] for k in used))
 with (CAMPAIGN/'evidence/capacity.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 if not row['valid']:raise RuntimeError('Complete remaining native growth is not funded: '+json.dumps(row))
 return row
class OwnedTerminal:
 def __init__(self,process,bootstrap):self.process=process;self.pid=process.pid;self.bootstrap=bootstrap;self.returncode=None
 def poll(self):
  if not self.process.is_running():
   try:self.returncode=self.process.wait(timeout=0)
   except (psutil.NoSuchProcess,psutil.TimeoutExpired):self.returncode=0
   return self.returncode if self.returncode is not None else 0
  return None
 def wait(self,timeout):
  self.returncode=self.process.wait(timeout=timeout)
  return self.returncode
def launch(config):
 executable=str((RUNTIME/'terminal64.exe').resolve()).casefold()
 def owners():
  result=[]
  for proc in psutil.process_iter(['pid','name','exe','create_time']):
   try:
    if proc.info['exe'] and str(Path(proc.info['exe']).resolve()).casefold()==executable:result.append(proc)
   except (psutil.NoSuchProcess,psutil.AccessDenied):pass
  return result
 if owners():raise RuntimeError('Own runtime already has a terminal owner')
 info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
 env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=''
 bootstrap=subprocess.Popen([str(RUNTIME/'terminal64.exe'),'/portable','/config:'+str(config)],cwd=RUNTIME,env=env,startupinfo=info,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 time.sleep(3)
 found=owners()
 if len(found)!=1:raise RuntimeError('Expected one exact owned terminal after bootstrap, found '+str(len(found)))
 return OwnedTerminal(found[0],bootstrap)
def close_owned(p):
 # Normal WM_CLOSE, matched to this exact child PID only. No broad terminal kill.
 fn=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
 def cb(hwnd,_):
  pid=ctypes.c_ulong();ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
  if pid.value==p.pid:ctypes.windll.user32.PostMessageW(hwnd,0x0010,0,0)
  return True
 callback=fn(cb);ctypes.windll.user32.EnumWindows(callback,0)
 p.wait(timeout=60)
def fingerprint():
 paths=[]
 for base in [RUNTIME/'Bases/FPMarketsSC-Live',RUNTIME/'Tester/bases/FPMarketsSC-Live']:
  for p in base.rglob('*'):
   if p.is_file() and ((p.suffix=='.hcc' and p.stem in ['2024','2025']) or (p.suffix=='.tkc' and (p.stem=='202412' or p.stem.startswith('2025'))) or (p.suffix=='.dat' and p.parent.name=='symbols' and p.name.startswith('symbols-'))):paths.append(p)
 paths += [RUNTIME/x for x in ['terminal64.exe','metatester64.exe','MetaEditor64.exe']]
 paths += [p for p in (RUNTIME/'MQL5').rglob('*') if p.is_file() and p.suffix in ['.mq5','.mqh','.ex5','.onnx']]
 return [dict(path=str(p.relative_to(RUNTIME)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(paths))]

def prepare_market():
 capacity('before_market_reader')
 out=RAW/'input-v2';out.mkdir(parents=True,exist_ok=False)
 config=CAMPAIGN/'settings/market-reader.ini'
 config.write_text('[Common]\nNewsEnable=0\n[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n',encoding='utf-16')
 p=launch(config);save(out/'reader-start.json',dict(utc=utc(),pid=p.pid,executable=str(RUNTIME/'terminal64.exe'),scope='Only own Portable native bars/contracts; no account/position/order/deal API queries'))
 try:
  if not mt5.initialize(str(RUNTIME/'terminal64.exe'),portable=True,timeout=60000):raise RuntimeError('Own history connection failed: '+str(mt5.last_error()))
  info=mt5.terminal_info()
  if info is None or Path(info.data_path).resolve()!=RUNTIME.resolve():raise RuntimeError('SDK did not bind own physical Portable')
  version=mt5.version();contracts={};streams=[]
  start=dt.datetime(2024,1,1,tzinfo=dt.timezone.utc);end=dt.datetime(2025,12,31,23,59,59,tzinfo=dt.timezone.utc)
  for symbol in SYMBOLS:
   if not mt5.symbol_select(symbol,True):raise RuntimeError('Required symbol unavailable: '+symbol)
   si=mt5.symbol_info(symbol);contracts[symbol]={k:getattr(si,k) for k in CONTRACT_FIELDS}
   for name,frame in FRAMES.items():
    bars=mt5.copy_rates_range(symbol,frame,start,end)
    if bars is None or len(bars)==0:raise RuntimeError('Required native historical bars unavailable: '+symbol+' '+name+' '+str(mt5.last_error()))
    path=out/(symbol+'-'+name+'.npy');np.save(path,bars,allow_pickle=False)
    streams.append(dict(symbol=symbol,frame=name,rows=len(bars),first=int(bars['time'][0]),last=int(bars['time'][-1]),path=str(path.relative_to(REPO)),bytes=path.stat().st_size,sha256=sha(path)))
   print('Prepared native historical bars:',symbol,flush=True)
  save(out/'market.json',dict(utc=utc(),version=version,contracts=contracts,streams=streams,server_period=['2024-01-01','2026-01-01'],no_broker_account_queries=True))
 finally:
  mt5.shutdown()
  if p.poll() is None:close_owned(p)
 save(out/'reader-stop.json',dict(utc=utc(),pid=p.pid,exit_code=p.returncode))
 capacity('after_market_reader')
 save(CAMPAIGN/'evidence/SELECTION_INPUT_FREEZE_V1.json',dict(utc=utc(),files=fingerprint(),market_path=str((out/'market.json').relative_to(REPO)),market_sha256=sha(out/'market.json'),period=['2025-01-01','2026-01-01'],initial=100,leverage=100,quality='Model4 all3requiredsymbols100percent real ticks',roles=['control-static','static','control-online','online']))

def native_path(role,tag):
 capacity('before_'+tag)
 freeze=CAMPAIGN/'evidence/SELECTION_INPUT_FREEZE_V2.json'
 baseline=json.loads(freeze.read_text())['files']
 current=fingerprint()
 if current!=baseline:raise RuntimeError('Frozen native source/price/contract bytes drifted before '+tag)
 folder=RAW/'native'/tag;folder.mkdir(parents=True,exist_ok=False)
 config=CAMPAIGN/'settings'/(tag+'.ini');setpath=RUNTIME/'MQL5/Profiles/Tester'/(tag+'.set')
 content=(CAMPAIGN/'settings'/(role.lower()+'.set')).read_text(encoding='utf-8-sig').replace('InpECRunTag=unconfigured','InpECRunTag='+tag)
 setpath.write_text(content,encoding='utf-16')
 report=RUNTIME/'reports'/tag;report.parent.mkdir(parents=True,exist_ok=True)
 config.write_text('[Common]\nNewsEnable=0\n[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n[Tester]\nExpert=ZetaV7EC\\ZetaV7EC'+role+'.ex5\nExpertParameters='+tag+'.set\nSymbol=US30\nPeriod=M30\nModel=4\nExecutionMode=0\nOptimization=0\nFromDate=2025.01.01\nToDate=2026.01.01\nForwardMode=0\nDeposit=100\nCurrency=USD\nLeverage=100\nUseLocal=1\nUseRemote=0\nUseCloud=0\nVisual=0\nReport=reports\\'+tag+'.htm\nReplaceReport=0\nShutdownTerminal=1\n',encoding='utf-16')
 before_logs={str(x):x.stat().st_size for x in RUNTIME.glob('Tester/Agent-*/logs/*.log')}
 p=launch(config)
 save(folder/'start.json',dict(utc=utc(),role=role,tag=tag,pid=p.pid,config_sha256=sha(config),set_sha256=sha(setpath),frozen_inputs_sha256=sha(freeze),own_child_environment={'CUDA_VISIBLE_DEVICES':''},before_agent_log_bytes=before_logs))
 print('Native run started:',tag,'PID',p.pid,flush=True)
 failure=None
 try:
  while p.poll() is None:
   time.sleep(8)
   if p.poll() is None:capacity('running_'+tag)
 except BaseException as exc:
  failure=repr(exc)
  if p.poll() is None:close_owned(p)
 time.sleep(1)
 records=[]
 def archive(src,dest):
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);records.append(dict(source=str(src.relative_to(RUNTIME)),path=str(dest.relative_to(REPO)),bytes=dest.stat().st_size,sha256=sha(dest)))
 for src in RUNTIME.glob('reports/'+tag+'*'):
  if src.is_file():archive(src,folder/'reports'/src.name)
 for agent in RUNTIME.glob('Tester/Agent-*'):
  owned=agent/'MQL5/Files'/('ZetaV7EC'+role)/tag
  if owned.exists():
   for src in owned.rglob('*'):
    if src.is_file():archive(src,folder/'files'/src.relative_to(owned))
  for src in agent.glob('logs/*.log'):
   offset=before_logs.get(str(src),0);data=src.read_bytes()[offset:]
   if data:
    dest=folder/(agent.name+'-episode.log');dest.write_bytes(data);records.append(dict(source=str(src.relative_to(RUNTIME)),path=str(dest.relative_to(REPO)),offset=offset,bytes=len(data),sha256=sha(dest)))
 after=fingerprint();drift=after!=baseline
 if failure is not None:
  save(folder/'interrupted.json',dict(utc=utc(),role=role,tag=tag,process_exit_code=p.returncode,files=records,input_drift=drift,after_inputs=after,status='INCOMPLETE_OPERATING_CORRECTION_NO_ECONOMIC_VERDICT',failure=failure))
  raise RuntimeError('Owned native closed and partial evidence archived: '+failure)
 save(folder/'complete.json',dict(utc=utc(),role=role,tag=tag,process_exit_code=p.returncode,files=records,input_drift=drift,after_inputs=after,capacity=capacity('after_'+tag)))
 print('Native process exited and evidence archived:',tag,'files',len(records),'drift',drift,flush=True)
 if drift:raise RuntimeError('Input drift invalidates matrix: '+tag)

def post_matrix_market():
 # Re-read only the same historical streams and contracts from the owned Portable.
 # No broker account, position, order or deal SDK API is used.
 capacity('before_post_matrix_historical_read')
 for tag in ['cs-v3','static-v3','co-v3','online-v3']:
  if not (RAW/'native'/tag/'complete.json').exists():raise RuntimeError('Fixed matrix not complete')
 before=json.loads((RAW/'input-v2/market.json').read_text())
 baseline=json.loads((CAMPAIGN/'evidence/SELECTION_INPUT_FREEZE_V2.json').read_text())['files']
 if fingerprint()!=baseline:raise RuntimeError('Input drift before historical re-read')
 out=RAW/'input-post-v3';out.mkdir(parents=True,exist_ok=False)
 p=launch(CAMPAIGN/'settings/market-reader.ini')
 save(out/'reader-start.json',dict(utc=utc(),pid=p.pid,scope='Same12historical streams and symbol contracts only; no account/position/order/deal API'))
 streams=[];contracts={};mismatches=[]
 try:
  if not mt5.initialize(str(RUNTIME/'terminal64.exe'),portable=True,timeout=60000):raise RuntimeError('Own historical re-read connection failed: '+str(mt5.last_error()))
  info=mt5.terminal_info()
  if info is None or Path(info.data_path).resolve()!=RUNTIME.resolve():raise RuntimeError('Wrong physical Portable')
  version=list(mt5.version())
  start=dt.datetime(2024,1,1,tzinfo=dt.timezone.utc);end=dt.datetime(2025,12,31,23,59,59,tzinfo=dt.timezone.utc)
  for symbol in SYMBOLS:
   if not mt5.symbol_select(symbol,True):raise RuntimeError('Required symbol unavailable: '+symbol)
   si=mt5.symbol_info(symbol);contracts[symbol]={k:getattr(si,k) for k in CONTRACT_FIELDS}
   for name,frame in FRAMES.items():
    bars=mt5.copy_rates_range(symbol,frame,start,end)
    if bars is None or len(bars)==0:raise RuntimeError('Required historical stream unavailable')
    path=out/(symbol+'-'+name+'.npy');np.save(path,bars,allow_pickle=False)
    prior=next(x for x in before['streams'] if x['symbol']==symbol and x['frame']==name)
    row=dict(symbol=symbol,frame=name,path=str(path.relative_to(REPO)),bytes=path.stat().st_size,sha256=sha(path),prior_sha256=prior['sha256'],rows=len(bars))
    row['unchanged']=row['sha256']==prior['sha256'] and row['bytes']==prior['bytes']
    if not row['unchanged']:mismatches.append(symbol+'-'+name)
    streams.append(row)
   print('Re-read same native historical bars:',symbol,flush=True)
 finally:
  mt5.shutdown()
  if p.poll() is None:close_owned(p)
 save(out/'reader-stop.json',dict(utc=utc(),pid=p.pid,exit_code=p.returncode))
 after=fingerprint()
 result=dict(utc=utc(),streams=streams,contracts_unchanged=contracts==before['contracts'],version_unchanged=version==before['version'],frozen_inputs_unchanged=after==baseline,after_inputs=after,contracts=contracts,version=version,mismatches=mismatches,capacity=capacity('after_post_matrix_historical_read'))
 save(out/'market.json',result)
 save(CAMPAIGN/'evidence/NATIVE_POST_MATRIX_INPUT_RECHECK_V1.json',dict(utc=utc(),path=str((out/'market.json').relative_to(REPO)),bytes=(out/'market.json').stat().st_size,sha256=sha(out/'market.json'),stream_count=len(streams),mismatches=mismatches,contracts_unchanged=result['contracts_unchanged'],version_unchanged=result['version_unchanged'],frozen_inputs_unchanged=result['frozen_inputs_unchanged']))
 if mismatches or not all(result[k] for k in ['contracts_unchanged','version_unchanged','frozen_inputs_unchanged']):raise RuntimeError('Post-matrix historical input drift')
 print('Complete historical stream/contract/build/input re-read unchanged.',flush=True)

if __name__=='__main__':
 prepare_market()
