"""Run and preserve the campaign's ordinary original-V7 native source production."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import shutil
import subprocess
import time

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / 'optimization/runtime/v7-native-rc4-consensus-learning-v1-portable'
RAW = ROOT / 'optimization/artifacts/raw/v7-native-rc4-consensus-learning-v1'
CAPS = (6*2**30, 2*2**30, 32*2**20)
FLOOR = 30*2**30
NAME = 'ZetaV7RC4ConsensusControl'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def save(path, value):
    if path.exists():
        raise RuntimeError('Preserve existing evidence: '+str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def ref(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
            'sha256': digest(path)}


def capacity(enforce=True):
    used = [sum(p.stat().st_size for p in base.rglob('*') if p.is_file())
            if base.exists() else 0 for base in (RUNTIME, RAW, FAMILY)]
    free = shutil.disk_usage(ROOT).free
    remaining = sum(max(0, cap-size) for cap, size in zip(CAPS, used))
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'free': free,
              'used': used, 'caps': CAPS, 'remaining': remaining,
              'floor_ok': free >= FLOOR, 'caps_ok': all(x<=y for x,y in zip(used,CAPS)),
              'funded': free >= FLOOR+remaining}
    if enforce and not all(result[k] for k in ('floor_ok','caps_ok','funded')):
        raise RuntimeError('Native source envelope is not funded: '+json.dumps(result))
    return result


def powershell(script):
    return subprocess.run(['powershell','-NoProfile','-Command',script],
                          capture_output=True, text=True, check=True).stdout.strip()


def owners():
    text = powershell("Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('terminal64.exe','metatester64.exe','MetaEditor64.exe') } | Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress")
    rows = json.loads(text) if text else []
    if isinstance(rows, dict):
        rows = [rows]
    prefix = str(RUNTIME).lower()+'\\'
    return [x for x in rows if (x.get('ExecutablePath') or '').lower().startswith(prefix)]


def launch(config):
    if owners():
        raise RuntimeError('Own native runtime is already in use')
    capacity()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return subprocess.Popen([str(RUNTIME/'terminal64.exe'),'/portable','/config:'+str(config)],
                            cwd=RUNTIME, startupinfo=startup)


def close_owned_terminal():
    current = owners()
    terminals = [x for x in current if x['Name'].lower()=='terminal64.exe']
    if len(terminals)>1:
        raise RuntimeError('Ambiguous own terminal ownership')
    for row in terminals:
        pid = int(row['ProcessId'])
        powershell(f'$p=Get-Process -Id {pid} -ErrorAction Stop; if(-not $p.CloseMainWindow()) {{ throw "Normal own terminal close failed" }}')
    deadline = time.monotonic()+45
    while owners():
        if time.monotonic()>deadline:
            raise RuntimeError('Own terminal has not completed normal shutdown')
        time.sleep(1)


def history(tag, warmup=False):
    import MetaTrader5 as mt5
    folder = RAW/'history'/tag
    if folder.exists():
        raise RuntimeError('History observation already exists')
    before = capacity()
    folder.mkdir(parents=True)
    proc = launch(FAMILY/'settings/history.ini')
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'before': before,
              'streams': [], 'contracts': {}, 'warmup_ticks': []}
    try:
        if not mt5.initialize(path=str(RUNTIME/'terminal64.exe'), portable=True, timeout=60000):
            raise RuntimeError('Own SDK initialization failed')
        terminal = mt5.terminal_info()
        if terminal is None or Path(terminal.path).resolve()!=RUNTIME.resolve():
            raise RuntimeError('SDK attached to another terminal')
        result['build'] = terminal.build
        properties = ('trade_contract_size','point','digits','trade_tick_size',
                      'trade_tick_value_profit','trade_tick_value_loss','volume_min',
                      'volume_step','volume_max','trade_stops_level','trade_freeze_level',
                      'trade_calc_mode','trade_exemode','filling_mode','swap_mode',
                      'swap_long','swap_short','swap_rollover3days','currency_base',
                      'currency_profit','currency_margin')
        begin = datetime(2023,12,1,tzinfo=timezone.utc)
        end = datetime(2025,1,1,tzinfo=timezone.utc)
        for symbol in ('US30','US100','US500'):
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError('Own required symbol unavailable: '+symbol)
            contract = mt5.symbol_info(symbol)
            if contract is None:
                raise RuntimeError('Own contract unavailable')
            result['contracts'][symbol] = {k:getattr(contract,k) for k in properties}
            if warmup:
                tick_begin = begin
                while tick_begin < end:
                    tick_end = datetime(tick_begin.year+(tick_begin.month==12),
                                        1 if tick_begin.month==12 else tick_begin.month+1,
                                        1,tzinfo=timezone.utc)
                    ticks = mt5.copy_ticks_range(symbol,tick_begin,
                                                 tick_end-timedelta(milliseconds=1),mt5.COPY_TICKS_ALL)
                    if ticks is None or len(ticks)==0:
                        raise RuntimeError('Required source month ticks unavailable: '+symbol+str(tick_begin))
                    result['warmup_ticks'].append({'symbol':symbol,'month':tick_begin.strftime('%Y-%m'),
                        'count':len(ticks),'first_msc':int(ticks['time_msc'][0]),
                        'last_msc':int(ticks['time_msc'][-1]),
                        'sha256':hashlib.sha256(ticks).hexdigest().upper()})
                    print('PAST_TICK_MONTH',symbol,tick_begin.strftime('%Y-%m'),len(ticks),flush=True)
                    del ticks
                    tick_begin=tick_end
            for label, timeframe in (('M1',mt5.TIMEFRAME_M1),('M15',mt5.TIMEFRAME_M15),
                                     ('M30',mt5.TIMEFRAME_M30),('H1',mt5.TIMEFRAME_H1)):
                rates = mt5.copy_rates_range(symbol,timeframe,begin,end)
                if rates is None or len(rates)==0:
                    raise RuntimeError('Complete own past bars unavailable: '+symbol+label)
                rates = rates[(rates['time']>=int(begin.timestamp())) & (rates['time']<int(end.timestamp()))]
                result['streams'].append({'symbol':symbol,'timeframe':label,'count':len(rates),
                    'first':int(rates['time'][0]),'last':int(rates['time'][-1]),
                    'sha256':hashlib.sha256(rates.tobytes()).hexdigest().upper()})
        result['status'] = 'OWN_PAST_HISTORY_OBSERVED'
    except Exception as exc:
        result['status']='HISTORY_CORRECTION_REQUIRED'
        result['error']=str(exc)
        raise
    finally:
        mt5.shutdown()
        close_owned_terminal()
        proc.wait(timeout=5)
        result['after']=capacity(enforce=False)
        save(folder/'observation.json',result)
    print('HISTORY_COMPLETE',tag,flush=True)


def freeze(name, history_tag):
    capacity()
    if owners():
        raise RuntimeError('Input binding requires stopped own runtime')
    observation = RAW/'history'/history_tag/'observation.json'
    historical = json.loads(observation.read_bytes())
    if historical['status']!='OWN_PAST_HISTORY_OBSERVED':
        raise RuntimeError('Past observation is incomplete')
    files = set()
    for base in (FAMILY/'parent',FAMILY/'mt5',FAMILY/'settings'):
        files.update(p for p in base.rglob('*') if p.is_file())
    files.update([Path(__file__).resolve(),FAMILY/'python/materialize_source.py'])
    for name_ in ('terminal64.exe','MetaEditor64.exe','metatester64.exe'):
        files.add(RUNTIME/name_)
    for base in (RUNTIME/'MQL5/Experts',RUNTIME/'MQL5/Include',RUNTIME/'MQL5/Profiles/Tester'):
        files.update(p for p in base.rglob('*') if p.is_file())
    for base in (RUNTIME/'Bases',RUNTIME/'Tester/bases'):
        files.update(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in ('.tkc','.hcc','.hcs') and p.stem[:4] in ('2023','2024'))
    save(FAMILY/'evidence'/name,{'utc':datetime.now(timezone.utc).isoformat(),
         'status':'WHOLE_ORIGINAL_SOURCE_INPUT_FROZEN','files':[ref(p) for p in sorted(files)],
         'history':historical,'history_observation':ref(observation),'capacity':capacity()})
    print('INPUTS_FROZEN',name,len(files),flush=True)


def binding(declaration):
    changed=[]
    for row in declaration['files']:
        p=ROOT/row['path']
        if not p.is_file() or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:
            changed.append(row['path'])
    return {'files':len(declaration['files']),'unchanged':not changed,'changed':changed}


def run(tag, freeze_name):
    folder=RAW/'native'/tag
    if folder.exists():
        raise RuntimeError('Preserve previous native attempt')
    frozen_path=FAMILY/'evidence'/freeze_name
    frozen=json.loads(frozen_path.read_bytes())
    before=binding(frozen)
    if not before['unchanged']:
        raise RuntimeError('Consumed input changed before native production')
    budget=capacity()
    offsets={p:p.stat().st_size for base in (RUNTIME/'logs',RUNTIME/'Tester')
             for p in base.rglob('*.log') if p.is_file()}
    folder.mkdir(parents=True)
    proc=launch(FAMILY/'settings'/(tag+'.ini'))
    save(folder/'start.json',{'utc':datetime.now(timezone.utc).isoformat(),'pid':proc.pid,
         'freeze':ref(frozen_path),'binding':before,'capacity':budget})
    print('NATIVE_STARTED',tag,proc.pid,flush=True)
    while proc.poll() is None:
        cap=capacity(enforce=False)
        with (folder/'storage.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(cap)+'\n')
        if not cap['caps_ok'] or cap['free']<FLOOR+128*2**20:
            save(folder/'capacity-stop.json',cap)
            close_owned_terminal()
            proc.wait(timeout=5)
            break
        time.sleep(30)
    time.sleep(2)
    if owners():
        raise RuntimeError('Owned process remains after native completion')
    archive=folder/'files'
    archive.mkdir()
    for agent in (RUNTIME/'Tester').glob('Agent-*'):
        source=agent/'MQL5/Files'/NAME/tag
        if source.exists():
            shutil.copytree(source,archive/'Files'/NAME/tag)
    for path in (RUNTIME/'reports').glob(tag+'*'):
        if path.is_file():
            shutil.copyfile(path,archive/path.name)
    for base in (RUNTIME/'logs',RUNTIME/'Tester'):
        for path in base.rglob('*.log'):
            offset=offsets.get(path,0)
            if path.stat().st_size>offset:
                target=archive/'logs'/path.relative_to(RUNTIME)
                target.parent.mkdir(parents=True,exist_ok=True)
                with path.open('rb') as src,target.open('wb') as dst:
                    src.seek(offset)
                    shutil.copyfileobj(src,dst)
    save(folder/'complete.json',{'utc':datetime.now(timezone.utc).isoformat(),
         'returncode':proc.returncode,'binding':binding(frozen),'capacity':capacity(enforce=False),
         'files':[ref(p) for p in sorted(archive.rglob('*')) if p.is_file()]})
    print('NATIVE_COMPLETE',tag,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('history','freeze','run'))
    parser.add_argument('tag')
    parser.add_argument('--warmup',action='store_true')
    parser.add_argument('--history')
    parser.add_argument('--freeze')
    args=parser.parse_args()
    if args.action=='history':
        history(args.tag,args.warmup)
    elif args.action=='freeze':
        freeze(args.tag,args.history)
    else:
        run(args.tag,args.freeze)
