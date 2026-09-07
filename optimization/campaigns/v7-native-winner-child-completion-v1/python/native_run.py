"""Ordinary owned MT5 history acquisition, native execution and evidence archiving."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import subprocess
import time

import numpy as np

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / 'optimization/runtime/v7-native-winner-child-completion-v1-portable'
RAW = ROOT / 'optimization/artifacts/raw/v7-native-winner-child-completion-v1'
FLOOR = 30 * 2**30
CAPS = [(RUNTIME, 3 * 2**30), (RAW, 2**30), (FAMILY, 32 * 2**20)]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest().upper()


def receipt(path, obj):
    path = Path(path)
    if path.exists():
        raise RuntimeError('Evidence already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def capacity(enforce=True):
    used = [sum(p.stat().st_size for p in base.rglob('*') if p.is_file()) for base, _ in CAPS]
    free = shutil.disk_usage(ROOT).free
    remaining = sum(max(0, limit - size) for size, (_, limit) in zip(used, CAPS))
    record = {'utc': datetime.now(timezone.utc).isoformat(), 'free': free,
              'used': used, 'caps': [x[1] for x in CAPS], 'remaining': remaining,
              'funded': free >= FLOOR + remaining, 'floor_ok': free >= FLOOR,
              'caps_ok': all(size <= limit for size, (_, limit) in zip(used, CAPS))}
    if enforce and not all(record[k] for k in ('funded', 'floor_ok', 'caps_ok')):
        raise RuntimeError('Complete remaining capacity unavailable: ' + json.dumps(record))
    return record


def owners():
    command = 'Get-CimInstance Win32_Process | Where-Object {$_.Name -in @("terminal64.exe","metatester64.exe","MetaEditor64.exe")} | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress'
    value = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True, encoding='utf-8-sig').strip()
    rows = json.loads(value) if value else []
    if isinstance(rows, dict):
        rows = [rows]
    prefix = str(RUNTIME).lower() + '\\'
    return [x for x in rows if str(x.get('ExecutablePath', '')).lower().startswith(prefix)]


def start(config):
    if owners():
        raise RuntimeError('An owned runtime process already exists')
    window = subprocess.STARTUPINFO()
    window.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    window.wShowWindow = 0
    return subprocess.Popen([str(RUNTIME / 'terminal64.exe'), '/portable', '/config:' + str(config)],
                            cwd=RUNTIME, startupinfo=window, creationflags=subprocess.CREATE_NO_WINDOW)


def close_history_owner():
    # Request normal close only for an executable inside the exact owned runtime.
    for row in owners():
        if Path(row['ExecutablePath']).name.lower() != 'terminal64.exe':
            continue
        pid = int(row['ProcessId'])
        command = f'$p=Get-Process -Id {pid} -ErrorAction Stop; if($p.Path -ne ' + "'" + str(RUNTIME / 'terminal64.exe').replace("'", "''") + "'){throw 'path mismatch'}; $p.CloseMainWindow()"
        subprocess.run(['powershell', '-NoProfile', '-Command', command], check=True, capture_output=True)
    deadline = time.monotonic() + 45
    while owners() and time.monotonic() < deadline:
        time.sleep(2)
    if owners():
        raise RuntimeError('Owned history reader did not close normally')


def history(tag):
    import MetaTrader5 as mt5
    folder = RAW / 'history' / tag
    if folder.exists():
        raise RuntimeError('History observation tag already exists')
    before = capacity()
    folder.mkdir(parents=True)
    config = FAMILY / 'settings/connection-history.ini'
    process = start(config)
    time.sleep(2)
    if not mt5.initialize(str(RUNTIME / 'terminal64.exe'), portable=True, timeout=60000):
        receipt(folder / 'failure.json', {'stage': 'initialize', 'error': mt5.last_error(), 'pid': process.pid})
        raise RuntimeError('Owned SDK initialization failed; preserve process for exact-path correction')
    try:
        info = mt5.terminal_info()
        if info is None or Path(info.path).resolve() != RUNTIME.resolve():
            raise RuntimeError('SDK terminal path mismatch')
        contracts = {}
        streams = []
        for symbol in ('US30', 'US100', 'US500'):
            detail = mt5.symbol_info(symbol)
            if detail is None:
                raise RuntimeError('Missing required contract ' + symbol)
            fields = ['digits', 'point', 'trade_mode', 'trade_exemode', 'trade_calc_mode',
                      'trade_contract_size', 'trade_tick_size', 'trade_tick_value',
                      'volume_min', 'volume_max', 'volume_step', 'trade_stops_level',
                      'trade_freeze_level', 'filling_mode', 'order_mode', 'swap_mode',
                      'swap_long', 'swap_short', 'swap_rollover3days', 'currency_base',
                      'currency_profit', 'currency_margin']
            contracts[symbol] = {field: getattr(detail, field) for field in fields}
            for label, timeframe in [('M1', mt5.TIMEFRAME_M1), ('M15', mt5.TIMEFRAME_M15),
                                     ('M30', mt5.TIMEFRAME_M30), ('H1', mt5.TIMEFRAME_H1)]:
                rates = mt5.copy_rates_range(symbol, timeframe,
                    datetime(2024, 1, 1, tzinfo=timezone.utc),
                    datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
                if rates is None or not len(rates):
                    raise RuntimeError('Missing required bar stream ' + symbol + label)
                if np.any(rates['time'] < 1704067200) or np.any(rates['time'] >= 1767225600):
                    raise RuntimeError('Returned bar stream outside declared past input')
                array_hash = hashlib.sha256(rates.tobytes()).hexdigest().upper()
                target = RAW / 'market' / (symbol + '-' + label + '-' + array_hash + '.npy')
                target.parent.mkdir(exist_ok=True)
                if not target.exists():
                    capacity()
                    np.save(target, rates, allow_pickle=False)
                streams.append({'symbol': symbol, 'timeframe': label, 'rows': len(rates),
                    'first': int(rates['time'][0]), 'last': int(rates['time'][-1]),
                    'array_sha256': array_hash, 'path': target.relative_to(ROOT).as_posix(),
                    'bytes': target.stat().st_size, 'file_sha256': digest(target)})
        receipt(folder / 'observation.json', {'utc': datetime.now(timezone.utc).isoformat(),
            'pid': process.pid, 'build': info.build, 'path': str(RUNTIME), 'contracts': contracts,
            'streams': streams, 'capacity_before': before, 'capacity_after': capacity()})
    finally:
        mt5.shutdown()
        close_history_owner()
    print('HISTORY_COMPLETE', tag, flush=True)


def binding(freeze):
    changed = []
    for row in freeze['files']:
        p = ROOT / row['path']
        if not p.is_file() or p.stat().st_size != row['bytes'] or digest(p) != row['sha256']:
            changed.append(row['path'])
    if changed:
        raise RuntimeError('Frozen input changed: ' + json.dumps(changed))
    return {'files': len(freeze['files']), 'unchanged': True}


def run(tag, freeze_name):
    folder = RAW / 'native' / tag
    if folder.exists():
        raise RuntimeError('Native tag already exists')
    freeze_path = FAMILY / 'evidence' / freeze_name
    freeze = json.loads(freeze_path.read_bytes())
    before_binding = binding(freeze)
    before = capacity()
    folder.mkdir(parents=True)
    log_offsets = {p: p.stat().st_size for base in [RUNTIME / 'logs', RUNTIME / 'Tester']
                   for p in base.rglob('*.log') if p.is_file()}
    started = datetime.now(timezone.utc).isoformat()
    proc = start(FAMILY / 'settings' / (tag + '.ini'))
    receipt(folder / 'start.json', {'utc': started, 'pid': proc.pid, 'freeze': freeze_name,
            'freeze_sha256': digest(freeze_path), 'binding': before_binding, 'capacity': before})
    print('NATIVE_STARTED', tag, proc.pid, flush=True)
    capacity_events = []
    while proc.poll() is None:
        # A background-volume change must not orphan the running owned terminal.
        # Record it, retain the attempt, and require funding again before any new path.
        record = capacity(enforce=False)
        with (folder / 'storage.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')
        if not all(record[k] for k in ('funded', 'floor_ok', 'caps_ok')):
            capacity_events.append(record)
            print('CAPACITY_CHANGE', tag, json.dumps(record), flush=True)
        if not record['caps_ok'] or record['free'] < FLOOR + 128 * 2**20:
            receipt(folder / 'capacity-stop.json', record)
            close_history_owner()
            proc.wait(timeout=45)
            break
        time.sleep(30)
    time.sleep(2)
    if owners():
        raise RuntimeError('Native process exited with remaining owned processes')
    archive = folder / 'files'
    archive.mkdir()
    installed_tag = freeze['runs'][tag]['include']
    for agent in (RUNTIME / 'Tester').glob('Agent-*'):
        source = agent / 'MQL5/Files' / installed_tag / tag
        if source.exists():
            shutil.copytree(source, archive / 'Files' / installed_tag / tag)
    for p in (RUNTIME / 'reports').glob(tag + '*'):
        if p.is_file():
            shutil.copyfile(p, archive / p.name)
    for base in [RUNTIME / 'logs', RUNTIME / 'Tester']:
        for p in base.rglob('*.log'):
            offset = log_offsets.get(p, 0)
            if p.stat().st_size <= offset:
                continue
            target = archive / 'logs' / p.relative_to(RUNTIME)
            target.parent.mkdir(parents=True, exist_ok=True)
            with p.open('rb') as src, target.open('wb') as dest:
                src.seek(offset)
                shutil.copyfileobj(src, dest)
    files = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
              'sha256': digest(p)} for p in sorted(archive.rglob('*')) if p.is_file()]
    receipt(folder / 'complete.json', {'utc': datetime.now(timezone.utc).isoformat(),
            'returncode': proc.returncode, 'files': files, 'binding': binding(freeze),
            'capacity': capacity(enforce=False), 'capacity_events': capacity_events})
    print('NATIVE_COMPLETE', tag, len(files), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['history', 'run'])
    parser.add_argument('tag')
    parser.add_argument('--freeze', default='SELECTION_INPUT_FREEZE_V1.json')
    args = parser.parse_args()
    if args.action == 'history':
        history(args.tag)
    else:
        run(args.tag, args.freeze)
