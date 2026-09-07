"""Acquire the complete fixed native historical input from this family's reader.

Normal input production only: no training, economic judgment, trading, terminal
launch, account/position/order/deal query or current quote query.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys
import MetaTrader5 as mt5
import numpy as np

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / 'optimization/runtime/v7-onnx-online-volatility-ratchet-v1-portable'
RAW = ROOT / 'optimization/artifacts/raw/v7-onnx-online-volatility-ratchet-v1'
START, END = 1704067200, 1788220800  # [2024-01-01, 2026-09-01), source epochs unchanged
DTYPE = np.dtype([('time','<i8'), ('open','<f8'), ('high','<f8'),
                  ('low','<f8'), ('close','<f8'), ('tick_volume','<u8'),
                  ('spread','<i4'), ('real_volume','<u8')])

def main():
    stage = sys.argv[1]
    if stage not in ('market-before-control-v3', 'market-between-v3', 'market-after-candidate-v3'):
        raise ValueError('Undeclared input acquisition stage')
    dest = RAW / stage
    dest.mkdir(exist_ok=False)
    if shutil.disk_usage(ROOT).free < 30 * 1024**3 + 256 * 1024**2:
        raise RuntimeError('Storage reserve would be endangered')
    receipt = dict(utc=datetime.now(timezone.utc).isoformat(), stage=stage,
        runtime=str(RUNTIME.relative_to(ROOT)), status='ACQUIRING', start=START,
        end_exclusive=END, timeframe='M1', schema=DTYPE.descr, files=[],
        source_clock='Original numeric source timestamps; no timezone conversion',
        account_position_order_deal_current_quote_queries=False, live_changes=False)
    try:
        if not mt5.initialize(str(RUNTIME / 'terminal64.exe'), portable=True, timeout=60000):
            raise RuntimeError(f'Own reader IPC initialization failed: {mt5.last_error()}')
        info = mt5.terminal_info()
        if info is None or Path(info.path).resolve() != RUNTIME or Path(info.data_path).resolve() != RUNTIME:
            raise RuntimeError('Reader physical runtime binding mismatch')
        receipt['maxbars'] = info.maxbars
        for symbol in ('US30','US100','US500'):
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, START, END-1)
            if rates is None or len(rates) == 0:
                raise RuntimeError(f'{symbol} historical acquisition failed: {mt5.last_error()}')
            if rates['time'][0] < START or rates['time'][-1] >= END or np.any(np.diff(rates['time']) <= 0):
                raise RuntimeError(f'{symbol} input ordering/window fault')
            packed = np.empty(len(rates), dtype=DTYPE)
            for name in DTYPE.names:
                packed[name] = rates[name]
            path = dest / f'{symbol}-M1.npy'
            np.save(path, packed, allow_pickle=False)
            item = dict(path=str(path.relative_to(ROOT)), rows=len(packed),
                first=int(packed['time'][0]), last=int(packed['time'][-1]),
                bytes=path.stat().st_size, sha256=hashlib.file_digest(path.open('rb'),'sha256').hexdigest().upper())
            receipt['files'].append(item)
            print(json.dumps(item), flush=True)
        receipt['status'] = 'COMPLETE_FIXED_WINDOW_HISTORICAL_INPUT'
    except Exception as error:
        receipt['status'] = 'INPUT_ACQUISITION_CORRECTION_REQUIRED'
        receipt['error'] = str(error)
        raise
    finally:
        mt5.shutdown()
        receipt['completed_utc'] = datetime.now(timezone.utc).isoformat()
        receipt['free_bytes'] = shutil.disk_usage(ROOT).free
        (dest / 'acquisition.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    main()
