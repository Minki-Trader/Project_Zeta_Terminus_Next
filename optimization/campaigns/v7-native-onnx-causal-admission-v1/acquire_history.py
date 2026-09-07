"""Capture the full declared native training price input from this own Portable.

Uses only initialize, terminal_info, copy_rates_range and shutdown. No account,
position, order, deal, or current-quote API is used by this history producer.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import io
import json
import shutil
import sys

import MetaTrader5 as mt5
import numpy as np

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / 'optimization/runtime/v7-native-onnx-causal-admission-v1-portable'
RAW = ROOT / 'optimization/artifacts/raw/v7-native-onnx-causal-admission-v1'


def capture(phase):
    if not phase or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in phase):
        raise ValueError('Invalid acquisition phase')
    if shutil.disk_usage(ROOT).free < 30 * 1024**3 + 256 * 1024**2:
        raise RuntimeError('Input acquisition reserve')
    evidence = RAW / 'history-observations'
    evidence.mkdir(parents=True, exist_ok=True)
    output = evidence / (phase + '.json')
    if output.exists():
        raise RuntimeError('An acquisition observation is immutable')
    initialized = False
    try:
        initialized = mt5.initialize(str(RUNTIME / 'terminal64.exe'), portable=True, timeout=60000)
        if not initialized:
            raise RuntimeError('Own SDK initialization failed: ' + str(mt5.last_error()))
        info = mt5.terminal_info()
        if info is None or Path(info.path).resolve() != RUNTIME.resolve() or Path(info.data_path).resolve() != RUNTIME.resolve():
            raise RuntimeError('SDK is not attached to the declared own Portable')
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)
        records = []
        for symbol in ('US30', 'US100', 'US500'):
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
            if rates is None or len(rates) == 0:
                raise RuntimeError('No declared native history: ' + symbol)
            rates = rates[(rates['time'] >= int(start.timestamp())) & (rates['time'] < int(end.timestamp()))]
            if len(rates) == 0 or np.any(np.diff(rates['time']) <= 0):
                raise RuntimeError('Invalid native history ordering: ' + symbol)
            blob = io.BytesIO()
            np.save(blob, rates, allow_pickle=False)
            data = blob.getvalue()
            digest = hashlib.sha256(data).hexdigest().upper()
            folder = RAW / 'native-price-input'
            folder.mkdir(exist_ok=True)
            path = folder / (symbol + '-' + digest + '.npy')
            if not path.exists():
                path.write_bytes(data)
            records.append(dict(symbol=symbol, path=path.relative_to(ROOT).as_posix(),
                                rows=len(rates), bytes=len(data), sha256=digest,
                                first=int(rates['time'][0]), last=int(rates['time'][-1]),
                                fields=list(rates.dtype.names)))
        result = dict(utc=datetime.now(timezone.utc).isoformat(), phase=phase,
                      status='FULL_NATIVE_2023_WARMUP_AND_2024_M1_CAPTURED',
                      runtime=RUNTIME.relative_to(ROOT).as_posix(), build=info.build,
                      period_start=start.isoformat(), period_end_exclusive=end.isoformat(),
                      files=records, free_bytes=shutil.disk_usage(ROOT).free,
                      account_position_order_deal_api_calls=0, live_changes=False)
        output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2), flush=True)
    finally:
        if initialized:
            mt5.shutdown()


if __name__ == '__main__':
    capture(sys.argv[1])
