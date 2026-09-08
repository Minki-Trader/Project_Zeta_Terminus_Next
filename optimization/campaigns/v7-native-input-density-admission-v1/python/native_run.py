"""Produce and preserve this family's ordinary MT5 native economic runs."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import shutil
import subprocess
import time
import zipfile

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
RUNTIME = ROOT/'optimization/runtime/v7-native-input-density-admission-v1-portable'
RAW = ROOT/'optimization/artifacts/raw/v7-native-input-density-admission-v1'
ROLES = {'cs': 'ZetaV7DensityControl', 'static': 'ZetaV7DensityStatic',
         'co': 'ZetaV7DensityControl', 'online': 'ZetaV7DensityOnline'}
FLOOR = 30*2**30
CAPS = (6*2**30, 2*2**30, 32*2**20)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def ref(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def save(path, value):
    if path.exists():
        raise RuntimeError('Preserve existing evidence: '+str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def capacity(enforce=True):
    used = [sum(p.stat().st_size for p in base.rglob('*') if p.is_file())
            if base.exists() else 0 for base in (RUNTIME, RAW, FAMILY)]
    free = shutil.disk_usage(ROOT).free
    remaining = sum(max(0, cap-size) for cap, size in zip(CAPS, used))
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'used': used, 'caps': CAPS,
              'free': free, 'remaining': remaining, 'floor_ok': free>=FLOOR,
              'caps_ok': all(x<=y for x,y in zip(used,CAPS)), 'funded': free>=FLOOR+remaining}
    if enforce and not all(result[k] for k in ('floor_ok', 'caps_ok', 'funded')):
        raise RuntimeError('Complete native storage envelope is not funded')
    return result


def powershell(command):
    return subprocess.run(['powershell', '-NoProfile', '-Command', command],
                          capture_output=True, text=True, check=True).stdout.strip()


def owners():
    raw = powershell("Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('terminal64.exe','metatester64.exe','MetaEditor64.exe') } | Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress")
    rows = json.loads(raw) if raw else []
    rows = rows if isinstance(rows, list) else [rows]
    return [r for r in rows if (r.get('ExecutablePath') or '').lower().startswith(str(RUNTIME).lower()+'\\')]


def hidden_start(arguments):
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return subprocess.Popen(arguments, cwd=RUNTIME, startupinfo=info)


def compile_and_install(tag):
    capacity()
    if owners():
        raise RuntimeError('Owned runtime is already in use')
    folder = FAMILY/'evidence'/tag
    if folder.exists():
        raise RuntimeError('Preserve prior compile attempt')
    folder.mkdir()
    own = FAMILY/'mt5/MQL5'
    sources = sorted(list((own/'Experts').glob('*.mq5'))+
                     list((own/'Include/ZetaV7Density').rglob('*.mqh')))
    with zipfile.ZipFile(folder/'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            archive.write(path, path.relative_to(own).as_posix())
    records = []
    for name in sorted(set(ROLES.values())):
        source = own/'Experts'/(name+'.mq5')
        log = folder/(name+'.log')
        proc = hidden_start([str(RUNTIME/'MetaEditor64.exe'), '/compile:'+str(source),
                             '/inc:'+str(own), '/log:'+str(log)])
        proc.wait(timeout=60)
        data = log.read_bytes()
        content = data.decode('utf-16' if data[:2]==b'\xff\xfe' else 'utf-16-le')
        result = [line for line in content.splitlines() if 'error' in line.lower() or 'warning' in line.lower()]
        print(name, '\n'.join(result), flush=True)
        record = {'source': ref(source), 'log': ref(log), 'process_returncode': proc.returncode,
                  'compiler_result': result}
        binary = source.with_suffix('.ex5')
        if '0 errors, 0 warnings' not in content or not binary.exists():
            records.append(record)
            save(folder/'compile.json', {'status': 'COMPILE_CORRECTION_REQUIRED', 'roles': records})
            return
        retained = folder/binary.name
        shutil.copyfile(binary, retained)
        record['binary'] = ref(retained)
        records.append(record)
    installed = []
    for base in (own/'Experts', own/'Include/ZetaV7Density', own/'Files/V7InputDensity'):
        for source in sorted(base.rglob('*')):
            if source.is_file():
                target = RUNTIME/'MQL5'/source.relative_to(own)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                installed.append(ref(target))
    save(folder/'compile.json', {'status': 'ALL_ROLES_COMPILE_CLEAN_INSTALLED',
         'source_snapshot': ref(folder/'source.zip'), 'roles': records, 'installed': installed,
         'capacity': capacity()})
    print('NATIVE_ASSEMBLIES_INSTALLED', tag, flush=True)


def close_owned():
    terminals = [r for r in owners() if r['Name'].lower()=='terminal64.exe']
    if len(terminals)>1:
        raise RuntimeError('Ambiguous own terminal')
    for row in terminals:
        powershell(f'$p=Get-Process -Id {int(row["ProcessId"])} -ErrorAction Stop; if(-not $p.CloseMainWindow()) {{ throw "Normal owned terminal close failed" }}')
    deadline = time.monotonic()+45
    while owners():
        if time.monotonic()>deadline:
            raise RuntimeError('Normal owned runtime shutdown is incomplete')
        time.sleep(1)


def symbol_databases():
    return [ref(p) for p in sorted((RUNTIME/'Bases').rglob('symbols-*.dat')) if p.is_file()]


def history(tag, warmup=False):
    import MetaTrader5 as mt5
    folder = RAW/'history'/tag
    if folder.exists() or owners():
        raise RuntimeError('Fresh history observation requires unused tag and stopped owner')
    config = FAMILY/'settings/history.ini'
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text('[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n', encoding='utf-8')
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'before': capacity(),
              'symbol_db_before': symbol_databases(), 'streams': [], 'contracts': {}, 'tick_months': []}
    folder.mkdir(parents=True)
    proc = hidden_start([str(RUNTIME/'terminal64.exe'), '/portable', '/config:'+str(config)])
    try:
        if not mt5.initialize(path=str(RUNTIME/'terminal64.exe'), portable=True, timeout=60000):
            raise RuntimeError('Own history SDK initialization failed')
        terminal = mt5.terminal_info()
        if terminal is None or Path(terminal.path).resolve()!=RUNTIME.resolve() or Path(terminal.data_path).resolve()!=RUNTIME.resolve():
            raise RuntimeError('SDK endpoint is not the own physical terminal')
        result['build'] = terminal.build
        result['terminal_path'] = terminal.path
        result['data_path'] = terminal.data_path
        properties = ('trade_contract_size','point','digits','trade_tick_size',
                      'trade_tick_value_profit','trade_tick_value_loss','volume_min','volume_step',
                      'volume_max','trade_stops_level','trade_freeze_level','trade_calc_mode',
                      'trade_exemode','filling_mode','swap_mode','swap_long','swap_short',
                      'swap_rollover3days','currency_base','currency_profit','currency_margin')
        begin = datetime(2024,1,1,tzinfo=timezone.utc)
        end = datetime(2026,1,1,tzinfo=timezone.utc)
        for symbol in ('US30','US100','US500'):
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError('Required own symbol unavailable')
            specification = mt5.symbol_info(symbol)
            if specification is None:
                raise RuntimeError('Required contract unavailable')
            result['contracts'][symbol] = {k:getattr(specification,k) for k in properties}
            if warmup:
                tick_begin = datetime(2024,12,1,tzinfo=timezone.utc)
                while tick_begin<end:
                    tick_end = datetime(tick_begin.year+(tick_begin.month==12),
                                        1 if tick_begin.month==12 else tick_begin.month+1,
                                        1,tzinfo=timezone.utc)
                    ticks = mt5.copy_ticks_range(symbol,tick_begin,tick_end-timedelta(milliseconds=1),mt5.COPY_TICKS_ALL)
                    if ticks is None or len(ticks)==0:
                        raise RuntimeError('Required complete past tick month unavailable')
                    result['tick_months'].append({'symbol':symbol,'month':tick_begin.strftime('%Y-%m'),
                        'count':len(ticks),'first_msc':int(ticks['time_msc'][0]),
                        'last_msc':int(ticks['time_msc'][-1]),'sha256':hashlib.sha256(ticks).hexdigest().upper()})
                    print('PAST_TICK_MONTH',symbol,tick_begin.strftime('%Y-%m'),len(ticks),flush=True)
                    del ticks
                    tick_begin=tick_end
            for label,tf in (('M1',mt5.TIMEFRAME_M1),('M15',mt5.TIMEFRAME_M15),
                             ('M30',mt5.TIMEFRAME_M30),('H1',mt5.TIMEFRAME_H1)):
                rates=mt5.copy_rates_range(symbol,tf,begin,end-timedelta(seconds=1))
                if rates is None or len(rates)==0:
                    raise RuntimeError('Complete required past bar stream unavailable')
                rates=rates[(rates['time']>=int(begin.timestamp())) & (rates['time']<int(end.timestamp()))]
                result['streams'].append({'symbol':symbol,'timeframe':label,'count':len(rates),
                    'first':int(rates['time'][0]),'last':int(rates['time'][-1]),
                    'sha256':hashlib.sha256(rates).hexdigest().upper()})
        result['status']='OWN_COMPLETE_PAST_HISTORY_OBSERVED'
    except Exception as exc:
        result['status']='HISTORY_CORRECTION_REQUIRED'
        result['error']=str(exc)
        raise
    finally:
        mt5.shutdown()
        close_owned()
        proc.wait(timeout=5)
        result['symbol_db_after']=symbol_databases()
        result['after']=capacity(enforce=False)
        save(folder/'observation.json',result)
    print('HISTORY_COMPLETE',tag,flush=True)


def prepare_settings(version):
    if owners():
        raise RuntimeError('Preparing a complete matrix requires stopped owner')
    capacity()
    matrix_path=FAMILY/'evidence'/('MATRIX_'+version.upper()+'.json')
    if matrix_path.exists():
        raise RuntimeError('Preserve existing matrix settings')
    original=FAMILY/'parent/MQL5/Presets/ZetaTerminusNext/next-v7-return.set'
    data=original.read_bytes()
    content=data.decode('utf-16' if data[:2]==b'\xff\xfe' else 'utf-8-sig')
    settings=[]
    for line in content.splitlines():
        if line.startswith('InpExpectedLiveAccountLogin='): line='InpExpectedLiveAccountLogin=0'
        if line.startswith('InpAllowNewEntries='): line='InpAllowNewEntries=false'
        if line.startswith('InpEventCapacity='): line='InpEventCapacity=8192'
        settings.append(line)
    implementation=[ref(p) for p in sorted((FAMILY/'mt5').rglob('*')) if p.is_file()]
    model=[ref(p) for p in sorted((FAMILY/'models').glob('*')) if p.is_file()]
    matrix=[]
    for role,name in ROLES.items():
        tag=role+'-'+version
        canonical_set='\n'.join(settings+['InpRunTag='+tag])+'\n'
        ini=('[Experts]\nEnabled=1\nAllowLiveTrading=0\nAllowDllImport=0\n'
             '[Tester]\nExpert='+name+'.ex5\nExpertParameters='+tag+'.set\n'
             'Symbol=US30\nPeriod=M30\nModel=4\nExecutionMode=0\nOptimization=0\n'
             'FromDate=2025.01.01\nToDate=2026.01.01\nForwardMode=0\nDeposit=100\n'
             'Currency=USD\nLeverage=1:100\nUseLocal=1\nUseRemote=0\nUseCloud=0\n'
             'Visual=0\nReport=reports\\'+tag+'\nReplaceReport=0\nShutdownTerminal=1\n')
        basis={'implementation':implementation,'model':model,'canonical_set_without_recursive_binding':canonical_set,
               'native_ini':ini,'role':role,'ea':name,'tag':tag}
        binding=hashlib.sha256(json.dumps(basis,sort_keys=True,separators=(',',':')).encode()).hexdigest().upper()
        save(FAMILY/'settings'/('binding-'+tag+'.json'),{'sha256':binding,'basis':basis})
        set_path=FAMILY/'settings'/(tag+'.set')
        ini_path=FAMILY/'settings'/(tag+'.ini')
        if set_path.exists() or ini_path.exists():
            raise RuntimeError('Preserve prior complete run settings')
        set_path.write_text(canonical_set+'InpNativeBinding='+binding+'\n',encoding='utf-8')
        ini_path.write_text(ini,encoding='utf-8')
        target=RUNTIME/'MQL5/Profiles/Tester'/set_path.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(set_path,target)
        matrix.append({'role':role,'ea':name,'tag':tag,'ini':ref(ini_path),'set':ref(set_path),'binding':binding})
    save(matrix_path,{'utc':datetime.now(timezone.utc).isoformat(),'status':'FULL_FOUR_PATH_MATRIX_PREPARED',
                     'paths':matrix,'capacity':capacity()})
    print('MATRIX_PREPARED',version,flush=True)


def freeze(name,history_tag):
    if owners():
        raise RuntimeError('Whole native inputs must be bound with stopped owner')
    observation=RAW/'history'/history_tag/'observation.json'
    history_record=json.loads(observation.read_bytes())
    if history_record['status']!='OWN_COMPLETE_PAST_HISTORY_OBSERVED':
        raise RuntimeError('Complete own history observation missing')
    files=set()
    for folder in ('parent','mt5','models','settings'):
        files.update(p for p in (FAMILY/folder).rglob('*') if p.is_file())
    files.update((FAMILY/'python').glob('*.py'))
    for name_ in ('terminal64.exe','MetaEditor64.exe','metatester64.exe'):
        files.add(RUNTIME/name_)
    for folder in ('MQL5/Experts','MQL5/Include','MQL5/Profiles/Tester','MQL5/Files/V7InputDensity'):
        files.update(p for p in (RUNTIME/folder).rglob('*') if p.is_file())
    for folder in ('Bases','Tester/bases'):
        for p in (RUNTIME/folder).rglob('*'):
            if p.is_file() and ((p.suffix.lower() in ('.tkc','.hcc','.hcs') and p.stem[:4] in ('2024','2025'))
                               or p.name.startswith('symbols-') and p.suffix.lower()=='.dat'):
                files.add(p)
    save(FAMILY/'evidence'/name,{'utc':datetime.now(timezone.utc).isoformat(),
         'status':'WHOLE_FOUR_PATH_NATIVE_INPUTS_FROZEN','history':history_record,
         'history_receipt':ref(observation),'files':[ref(p) for p in sorted(files)],'capacity':capacity()})
    print('INPUTS_FROZEN',name,len(files),flush=True)


def binding(record):
    changes=[]
    for row in record['files']:
        p=ROOT/row['path']
        if not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
            changes.append(row['path'])
    return {'files':len(record['files']),'unchanged':not changes,'changed':changes}


def run(tag,freeze_name):
    folder=RAW/'native'/tag
    if folder.exists() or owners():
        raise RuntimeError('A native path needs unused tag and stopped own runtime')
    declaration=FAMILY/'evidence'/freeze_name
    frozen=json.loads(declaration.read_bytes())
    before=binding(frozen)
    if not before['unchanged']:
        raise RuntimeError('Frozen consumed inputs changed before start: '+json.dumps(before))
    ini=FAMILY/'settings'/(tag+'.ini')
    if not ini.exists():
        raise RuntimeError('Declared run settings missing')
    budget=capacity()
    offsets={p:p.stat().st_size for base in (RUNTIME/'logs',RUNTIME/'Tester')
             for p in base.rglob('*.log') if p.is_file()}
    folder.mkdir(parents=True)
    proc=hidden_start([str(RUNTIME/'terminal64.exe'),'/portable','/config:'+str(ini)])
    save(folder/'start.json',{'utc':datetime.now(timezone.utc).isoformat(),'pid':proc.pid,
         'freeze':ref(declaration),'binding':before,'capacity':budget})
    print('NATIVE_STARTED',tag,proc.pid,flush=True)
    while proc.poll() is None:
        cap=capacity(enforce=False)
        with (folder/'storage.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps(cap)+'\n')
        if not cap['caps_ok'] or cap['free']<FLOOR+128*2**20:
            save(folder/'capacity-stop.json',cap)
            close_owned()
            proc.wait(timeout=5)
            break
        time.sleep(30)
    time.sleep(2)
    if owners():
        raise RuntimeError('Owned process has not completed normal native shutdown')
    archive=folder/'files'
    archive.mkdir()
    for agent in (RUNTIME/'Tester').glob('Agent-*'):
        for name in sorted(set(ROLES.values())):
            source=agent/'MQL5/Files'/name/tag
            if source.exists():
                shutil.copytree(source,archive/'Files'/name/tag)
    for source in (RUNTIME/'reports').glob(tag+'*'):
        if source.is_file():
            shutil.copyfile(source,archive/source.name)
    for base in (RUNTIME/'logs',RUNTIME/'Tester'):
        for source in base.rglob('*.log'):
            offset=offsets.get(source,0)
            if source.stat().st_size>offset:
                target=archive/'logs'/source.relative_to(RUNTIME)
                target.parent.mkdir(parents=True,exist_ok=True)
                with source.open('rb') as src,target.open('wb') as dst:
                    src.seek(offset)
                    shutil.copyfileobj(src,dst)
    save(folder/'complete.json',{'utc':datetime.now(timezone.utc).isoformat(),'returncode':proc.returncode,
         'binding':binding(frozen),'capacity':capacity(enforce=False),
         'files':[ref(p) for p in sorted(archive.rglob('*')) if p.is_file()]})
    print('NATIVE_COMPLETE',tag,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['compile','history','prepare','freeze','run'])
    parser.add_argument('tag')
    parser.add_argument('--warmup',action='store_true')
    parser.add_argument('--history')
    parser.add_argument('--freeze')
    args = parser.parse_args()
    if args.action=='compile': compile_and_install(args.tag)
    elif args.action=='history': history(args.tag,args.warmup)
    elif args.action=='prepare': prepare_settings(args.tag)
    elif args.action=='freeze': freeze(args.tag,args.history)
    else: run(args.tag,args.freeze)
