"""Capture the complete exercised V7 policy-evaluation history in the own Portable."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys

import MetaTrader5 as mt5
import numpy as np

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / 'optimization/runtime/v7-native-onnx-causal-admission-v1-portable'
RAW = ROOT / 'optimization/artifacts/raw/v7-native-onnx-causal-admission-v1'


def capture(phase):
    if not re.fullmatch(r'(selection|confirmation)-(before|after)-(control|static|online)-v[1-9][0-9]*', phase):
        raise ValueError('Use a declared complete policy-input phase')
    confirmation = phase.startswith('confirmation-')
    if confirmation:
        finalist = json.loads((FAMILY / 'evidence/POLICY_FINALIST_FREEZE_V1.json').read_text(encoding='utf-8'))
        if finalist['status'] != 'ONE_FIXED_2025_NATIVE_POLICY_SELECTED':
            raise RuntimeError('No selected policy authorizes confirmation input')
    if shutil.disk_usage(ROOT).free < 30 * 1024**3 + 384 * 1024**2:
        raise RuntimeError('Complete history capture reserve')
    output = RAW / 'history-observations' / (phase + '.json')
    if output.exists():
        raise RuntimeError('The history observation is immutable')
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9 if confirmation else 1, 1, tzinfo=timezone.utc)
    initialized = False
    try:
        initialized = mt5.initialize(str(RUNTIME / 'terminal64.exe'), portable=True, timeout=60000)
        if not initialized:
            raise RuntimeError('Own history SDK initialization failed: ' + str(mt5.last_error()))
        info = mt5.terminal_info()
        if info is None or Path(info.path).resolve() != RUNTIME.resolve() or Path(info.data_path).resolve() != RUNTIME.resolve():
            raise RuntimeError('SDK is not bound to the own physical Portable')
        files = []
        for symbol in ('US30', 'US100', 'US500'):
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
            if rates is None or len(rates) == 0:
                raise RuntimeError('Missing complete required history: ' + symbol)
            rates = rates[(rates['time'] >= int(start.timestamp())) & (rates['time'] < int(end.timestamp()))]
            if len(rates) == 0 or np.any(np.diff(rates['time']) <= 0):
                raise RuntimeError('Unordered required history: ' + symbol)
            blob = io.BytesIO()
            np.save(blob, rates, allow_pickle=False)
            data = blob.getvalue()
            digest = hashlib.sha256(data).hexdigest().upper()
            path = RAW / 'native-price-input' / (symbol + '-' + digest + '.npy')
            if not path.exists():
                path.write_bytes(data)
            files.append(dict(symbol=symbol, path=path.relative_to(ROOT).as_posix(), rows=len(rates),
                              bytes=len(data), sha256=digest, first=int(rates['time'][0]),
                              last=int(rates['time'][-1]), fields=list(rates.dtype.names)))
        result = dict(utc=datetime.now(timezone.utc).isoformat(), phase=phase,
                      status='FULL_NATIVE_POLICY_WARMUP_AND_ECONOMIC_PERIOD_M1_CAPTURED',
                      period_start=start.isoformat(), period_end_exclusive=end.isoformat(),
                      clock='Unshifted raw native server-wall scalar labels; no inferred physical UTC conversion',
                      runtime=RUNTIME.relative_to(ROOT).as_posix(), build=info.build, files=files,
                      account_position_order_deal_api_calls=0, live_changes=False,
                      free_bytes=shutil.disk_usage(ROOT).free)
        output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally:
        if initialized:
            mt5.shutdown()


if __name__ == '__main__':
    capture(sys.argv[1])
