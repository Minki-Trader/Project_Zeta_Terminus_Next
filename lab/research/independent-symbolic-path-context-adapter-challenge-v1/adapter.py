"""Own causal data/model/intent producer for the fixed CH015 research bundle."""
from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

import numpy as np
from numba import njit


FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
ART = ROOT / 'lab/artifacts/raw' / FAMILY.name
EVIDENCE = FAMILY / 'evidence'
CONTRACT_PATH = FAMILY / 'config/contract-v1.json'
DECLARATION_PATH = EVIDENCE / 'DECLARATION_V1.json'
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
DECLARATION = json.loads(DECLARATION_PATH.read_text(encoding='utf-8'))

BAR_DTYPE = np.dtype([
    ('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'),
    ('close', '<f8'), ('spread', '<f8'), ('last_m1', '<i8'),
])
FORECAST_DTYPE = np.dtype([
    ('decision_time', '<i8'), ('source_start', '<i8'), ('source_last_m1', '<i8'),
    ('last_close', '<f8'), ('next_atr', '<f8'), ('prior_spread', '<f8'),
    ('iid_mean', '<f8'), ('ctw_mean', '<f8'),
    ('iid_probability', '<f8', (5,)), ('ctw_probability', '<f8', (5,)),
    ('context_recent_first', '<i4', (5,)), ('trained_outcomes', '<i8'),
    ('iid_intent', '<i1'), ('ctw_intent', '<i1'),
])


def fingerprint(path: Path) -> dict:
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest().upper()
    return {'path': path.absolute().relative_to(ROOT).as_posix(),
            'bytes': path.stat().st_size, 'sha256': sha}


def require_fingerprint(path: Path, expected: dict) -> dict:
    observed = fingerprint(path)
    if any(observed[k] != expected[k] for k in ('bytes', 'sha256')):
        raise RuntimeError(f'Changed declared input: {path.relative_to(ROOT)}')
    return observed


def write_json(path: Path, value: dict) -> dict:
    if path.exists():
        raise RuntimeError(f'Refusing to replace evidence: {path.relative_to(ROOT)}')
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n'
    path.write_text(raw, encoding='utf-8', newline='\n')
    return fingerprint(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def capacity(future_bytes: int = 0) -> int:
    free = shutil.disk_usage(ROOT).free
    if free - future_bytes < CONTRACT['storage']['minimum_free_bytes']:
        raise RuntimeError('Research growth would breach the 30 GiB reserve')
    if ART.exists():
        used = sum(p.stat().st_size for p in ART.rglob('*') if p.is_file())
        if used > CONTRACT['storage']['maximum_new_proxy_input_and_output_bytes']:
            raise RuntimeError('Declared own proxy artifact budget exceeded')
    return free


def require_freeze() -> None:
    frozen = json.loads((EVIDENCE / 'STRUCTURAL_IMPLEMENTATION_FREEZE_V1.json')
                        .read_text(encoding='utf-8'))
    for item in frozen['files']:
        require_fingerprint(ROOT / item['path'], item)


def prepare() -> None:
    require_freeze()
    capacity(CONTRACT['storage']['maximum_new_proxy_input_and_output_bytes'])
    if (EVIDENCE / 'INPUT_COPY_V1.json').exists():
        raise RuntimeError('Own input already sealed; no second copy operation')
    target = ART / 'input'
    copies = []
    items = [(v, target / 'market' / (v['symbol'] + '-M1.npy'))
             for v in DECLARATION['source_provenance']['physical_copies']]
    for key, filename in [('static_contract', 'CURRENT_CONTRACT_CAPTURE_V1.json'),
                          ('price_observations_only_parent_receipt', 'ORIGINAL_M1_PROVENANCE_V1.json')]:
        item = DECLARATION['source_provenance'][key]
        items.append((dict(item, source=item['path']), target / 'provenance' / filename))
    for item, destination in items:
        source = ROOT / item['source']
        before = require_fingerprint(source, item)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            copied = require_fingerprint(destination, item)
        else:
            shutil.copyfile(source, destination)
            copied = require_fingerprint(destination, item)
        after = require_fingerprint(source, item)
        copies.append({'source_before': before, 'source_after': after, 'copy': copied})
    row_metadata = {}
    for item in DECLARATION['source_provenance']['physical_copies']:
        symbol = item['symbol']
        data = np.load(target / 'market' / (symbol + '-M1.npy'), mmap_mode='r', allow_pickle=False)
        times = data['time']
        if (data.shape != (item['rows'],) or np.any(times[1:] <= times[:-1])
                or np.any(times % 60) or times[0] < CONTRACT['raw_period'][0]
                or times[-1] >= CONTRACT['raw_period'][1]):
            raise RuntimeError('Source time/shape/range integrity requires correction')
        row_metadata[symbol] = {'rows': int(len(data)), 'first_raw_epoch': int(times[0]),
                                'last_raw_epoch': int(times[-1]), 'dtype': str(data.dtype)}
    receipt = {'schema': 'zeta-ch015-owned-raw-input-v1', 'recorded_utc': now(),
               'copies': copies, 'row_metadata': row_metadata,
               'total_copy_bytes': sum(v['copy']['bytes'] for v in copies),
               'candidate_features_or_fit_scores_opened': False,
               'candidate_2026_price_decoded': False, 'broker_queries': 0,
               'old_strategy_source_imported_or_executed': False,
               'free_bytes_after': capacity()}
    print(json.dumps({'stage': 'prepare_complete', 'receipt': write_json(EVIDENCE / 'INPUT_COPY_V1.json', receipt)}), flush=True)


@njit(cache=True)
def tree_observe(counts, estimated_log, weighted_log, context, outcome):
    path = np.empty(6, dtype=np.int64)
    path[0] = 0
    for depth in range(5):
        path[depth + 1] = path[depth] * 5 + 1 + context[depth]
    for depth in range(5, -1, -1):
        node = path[depth]
        total = 0
        for j in range(5):
            total += counts[node, j]
        estimated_log[node] += math.log((counts[node, outcome] + 0.5) / (total + 2.5))
        counts[node, outcome] += 1
        if depth == 5:
            weighted_log[node] = estimated_log[node]
        else:
            children = 0.0
            for j in range(5):
                children += weighted_log[node * 5 + 1 + j]
            a = estimated_log[node]
            b = children
            hi = max(a, b)
            weighted_log[node] = hi + math.log(math.exp(a - hi) + math.exp(b - hi)) - math.log(2.0)


@njit(cache=True)
def tree_predict(counts, estimated_log, weighted_log, context):
    path = np.empty(6, dtype=np.int64)
    path[0] = 0
    for depth in range(5):
        path[depth + 1] = path[depth] * 5 + 1 + context[depth]
    probability = np.empty(5, dtype=np.float64)
    iid = np.empty(5, dtype=np.float64)
    for depth in range(5, -1, -1):
        node = path[depth]
        total = 0
        for j in range(5):
            total += counts[node, j]
        if depth == 5:
            for j in range(5):
                probability[j] = (counts[node, j] + 0.5) / (total + 2.5)
        else:
            children = 0.0
            for j in range(5):
                children += weighted_log[node * 5 + 1 + j]
            delta = children - estimated_log[node]
            if delta >= 0.0:
                e = math.exp(-delta)
                stop_weight = e / (1.0 + e)
            else:
                stop_weight = 1.0 / (1.0 + math.exp(delta))
            for j in range(5):
                kt = (counts[node, j] + 0.5) / (total + 2.5)
                probability[j] = stop_weight * kt + (1.0 - stop_weight) * probability[j]
                if depth == 0:
                    iid[j] = kt
    return iid, probability


def complete_bars(data, point: float):
    times = data['time']
    keys = times // CONTRACT['bar_seconds']
    starts = np.concatenate((np.array([0]), np.flatnonzero(keys[1:] != keys[:-1]) + 1))
    ends = np.concatenate((starts[1:], np.array([len(data)])))
    offsets = np.arange(15, dtype=np.int64) * 60
    bars = []
    incomplete = []
    for a, b in zip(starts, ends):
        start = int(keys[a]) * 900
        if b - a != 15 or not np.array_equal(times[a:b], start + offsets):
            incomplete.append(start)
            continue
        chunk = data[a:b]
        values = np.column_stack([chunk[n] for n in ('open', 'high', 'low', 'close')])
        spreads = chunk['spread']
        if (not np.all(np.isfinite(values)) or np.any(values <= 0)
                or np.any(chunk['high'] < np.maximum(chunk['open'], chunk['close']))
                or np.any(chunk['low'] > np.minimum(chunk['open'], chunk['close']))
                or np.any(spreads < 0)):
            raise RuntimeError('Native complete-bar price/spread integrity fault')
        bars.append((start, float(chunk['open'][0]), float(np.max(chunk['high'])),
                     float(np.min(chunk['low'])), float(chunk['close'][-1]),
                     float(np.mean(spreads) * point), int(times[b - 1])))
    return np.array(bars, dtype=BAR_DTYPE), incomplete


def classify(z: float) -> int:
    if z < -0.5:
        return 0
    if z < 0:
        return 1
    if z == 0:
        return 2
    if z <= 0.5:
        return 3
    return 4


def year(raw_epoch: int) -> str:
    return datetime.fromtimestamp(raw_epoch, timezone.utc).strftime('%Y')


def immutable_npy(path: Path, value: np.ndarray) -> dict:
    if path.exists():
        raise RuntimeError(f'Existing producer output: {path.relative_to(ROOT)}')
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, value, allow_pickle=False)
    return fingerprint(path)


def structural():
    require_freeze()
    capacity(CONTRACT['storage']['maximum_structural_output_bytes'])
    result_path = EVIDENCE / 'STRUCTURAL_RESULT_V1.json'
    if result_path.exists() or (ART / 'structural').exists():
        raise RuntimeError('A structural path/output already exists; preserve it for explicit correction')
    input_receipt = json.loads((EVIDENCE / 'INPUT_COPY_V1.json').read_text(encoding='utf-8'))
    for item in input_receipt['copies']:
        require_fingerprint(ROOT / item['copy']['path'], item['copy'])
    specs = json.loads((ART / 'input/provenance/CURRENT_CONTRACT_CAPTURE_V1.json')
                       .read_text(encoding='utf-8'))['symbols']
    out = ART / 'structural'
    out.mkdir(parents=True)
    start, end = CONTRACT['development_period']
    cutoff = CONTRACT['entry_cutoff_raw_epoch']
    normal_days = set()
    by_symbol = {}
    outputs = []
    all_intent_days = [set(), set()]
    role_totals = []
    for role in CONTRACT['roles']:
        role_totals.append({'role': role, 'intent_count': 0,
                            'by_year': {'2024': 0, '2025': 0},
                            'by_symbol': {}, 'by_direction': {'LONG': 0, 'SHORT': 0},
                            'prequential_by_year': {y: {'n': 0, 'log_loss_sum': 0.0}
                                                   for y in ('2024', '2025')}})

    for symbol in CONTRACT['symbols']:
        capacity(CONTRACT['storage']['maximum_structural_output_bytes'])
        data = np.load(ART / 'input/market' / (symbol + '-M1.npy'), mmap_mode='r', allow_pickle=False)
        times = data['time']
        symbol_days = set(int(v) for v in np.unique(times[(times >= start) & (times < end)] // 86400))
        normal_days.update(symbol_days)
        bars, incomplete = complete_bars(data, specs[symbol]['point'])
        outputs.append(immutable_npy(out / (symbol + '-completed-M15.npy'), bars))
        outputs.append(immutable_npy(out / (symbol + '-incomplete-M15-times.npy'),
                                     np.array(incomplete, dtype=np.int64)))
        counts = np.zeros((3906, 5), dtype=np.int64)
        estimated_log = np.zeros(3906, dtype=np.float64)
        weighted_log = np.zeros(3906, dtype=np.float64)
        magnitude_sums = np.array(CONTRACT['magnitude_prior_means'], dtype=np.float64)
        tr_window = deque(maxlen=20)
        spread_window = deque(maxlen=20)
        history = deque(maxlen=5)
        previous_time = None
        previous_close = None
        pending_prediction = None
        forecasts = []
        resets = 0
        matured_symbols = 0
        conditioning_symbols = 0
        trained = 0
        warmup_saved = False
        for totals in role_totals:
            totals['by_symbol'][symbol] = 0

        def checkpoint(name: str):
            path = out / (symbol + '-' + name + '-model.npz')
            if path.exists():
                raise RuntimeError('Existing model checkpoint')
            np.savez(path, counts=counts, estimated_log=estimated_log, weighted_log=weighted_log,
                     magnitude_sums=magnitude_sums, context=np.array(history, dtype=np.int64),
                     true_range_window=np.array(tr_window, dtype=np.float64),
                     spread_window=np.array(spread_window, dtype=np.float64),
                     previous_time=np.array([-1 if previous_time is None else previous_time], dtype=np.int64),
                     previous_close=np.array([0.0 if previous_close is None else previous_close], dtype=np.float64))
            outputs.append(fingerprint(path))

        for bar in bars:
            t = int(bar['time'])
            if not warmup_saved and t >= start:
                checkpoint('end-warmup')
                warmup_saved = True
            if previous_time is None or t != previous_time + 900:
                tr_window.clear()
                spread_window.clear()
                history.clear()
                pending_prediction = None
                previous_close = None
                resets += 1
            close = float(bar['close'])
            if previous_close is None:
                previous_close = close
                previous_time = t
                continue
            current_tr = max(float(bar['high']) - float(bar['low']),
                             abs(float(bar['high']) - previous_close),
                             abs(float(bar['low']) - previous_close))
            label_ready = len(tr_window) == 20 and sum(tr_window) > 0.0
            if label_ready:
                atr_before = sum(tr_window) / 20.0
                tick = specs[symbol]['trade_tick_size']
                close_ticks = round(close / tick)
                previous_ticks = round(previous_close / tick)
                z = ((close_ticks - previous_ticks) * tick) / atr_before
                outcome = classify(z)
                matured_symbols += 1
                if pending_prediction is not None:
                    prediction_time, predictions, predicted_scale = pending_prediction
                    if prediction_time != t or abs(predicted_scale - atr_before) > 1e-10:
                        raise RuntimeError('Prediction target/scale chronology mismatch')
                    if start <= prediction_time < end:
                        epoch = year(prediction_time)
                        for role_index, probability in enumerate(predictions):
                            bucket = role_totals[role_index]['prequential_by_year'][epoch]
                            bucket['n'] += 1
                            bucket['log_loss_sum'] -= math.log(float(probability[outcome]))
                if len(history) == 5:
                    context_before = np.array(history, dtype=np.int64)
                    tree_observe(counts, estimated_log, weighted_log, context_before, outcome)
                    magnitude_sums[outcome] += float(np.clip(z, -4.0, 4.0))
                    trained += 1
                else:
                    conditioning_symbols += 1
                history.appendleft(outcome)
            else:
                history.clear()
            pending_prediction = None
            tr_window.append(current_tr)
            spread_window.append(float(bar['spread']))
            if (label_ready and len(history) == 5 and len(tr_window) == 20
                    and trained >= CONTRACT['minimum_full_context_training_outcomes']):
                next_atr = sum(tr_window) / 20.0
                if next_atr > 0:
                    context = np.array(history, dtype=np.int64)
                    iid, ctw = tree_predict(counts, estimated_log, weighted_log, context)
                    for probability in (iid, ctw):
                        if (not np.all(np.isfinite(probability)) or np.any(probability <= 0)
                                or abs(float(np.sum(probability)) - 1.0) > 1e-10):
                            raise RuntimeError('Nonfinite or unnormalized predictive distribution')
                    if int(np.sum(counts[0])) != trained:
                        raise RuntimeError('Training/root observation accounting mismatch')
                    means = magnitude_sums / (counts[0] + 1.0)
                    iid_mean = float(np.dot(iid, means))
                    ctw_mean = float(np.dot(ctw, means))
                    decision = t + 900
                    pending_prediction = (decision, (iid.copy(), ctw.copy()), next_atr)
                    if start <= decision < end:
                        intents = []
                        for role_index, mean in enumerate((iid_mean, ctw_mean)):
                            intent = 0
                            if decision < cutoff and abs(mean) > 0.05:
                                intent = 1 if mean > 0 else -1
                                totals = role_totals[role_index]
                                totals['intent_count'] += 1
                                totals['by_year'][year(decision)] += 1
                                totals['by_symbol'][symbol] += 1
                                totals['by_direction']['LONG' if intent > 0 else 'SHORT'] += 1
                                all_intent_days[role_index].add(decision // 86400)
                            intents.append(intent)
                        forecasts.append((decision, t, int(bar['last_m1']), close, next_atr,
                                          sum(spread_window) / 20.0, iid_mean, ctw_mean,
                                          iid.copy(), ctw.copy(), context.astype(np.int32),
                                          trained, intents[0], intents[1]))
            previous_time = t
            previous_close = close
        if not warmup_saved:
            raise RuntimeError('Declared development period was not traversed')
        checkpoint('end-development')
        tape = np.array(forecasts, dtype=FORECAST_DTYPE)
        outputs.append(immutable_npy(out / (symbol + '-forecasts.npy'), tape))
        by_symbol[symbol] = {'raw_rows': int(len(data)), 'source_days': len(symbol_days),
                             'complete_m15_bars': int(len(bars)), 'incomplete_m15_groups': len(incomplete),
                             'continuity_resets': resets, 'matured_symbols': matured_symbols,
                             'conditioning_only_symbols': conditioning_symbols, 'training_outcomes': trained,
                             'root_class_counts': [int(v) for v in counts[0]],
                             'development_forecasts': int(len(tape)),
                             'final_root_estimated_log': float(estimated_log[0]),
                             'final_root_weighted_log': float(weighted_log[0])}
        print(json.dumps({'stage': 'symbol_complete', 'symbol': symbol,
                          'forecasts': len(tape), 'trained': trained, 'free_bytes': capacity()}), flush=True)

    day_labels = [datetime.fromtimestamp(day * 86400, timezone.utc).strftime('%Y-%m-%d')
                  for day in sorted(normal_days)]
    by_year_days = {y: sum(d.startswith(y) for d in day_labels) for y in ('2024', '2025')}
    for role_index, totals in enumerate(role_totals):
        totals['optimistic_intents_per_all_source_date'] = totals['intent_count'] / len(normal_days)
        totals['zero_intent_source_dates'] = len(normal_days - all_intent_days[role_index])
        pooled_n = 0
        pooled_loss = 0.0
        for bucket in totals['prequential_by_year'].values():
            bucket['mean_log_loss'] = bucket['log_loss_sum'] / bucket['n'] if bucket['n'] else None
            pooled_n += bucket['n']
            pooled_loss += bucket['log_loss_sum']
        totals['pooled_prequential'] = {'n': pooled_n, 'log_loss_sum': pooled_loss,
                                      'mean_log_loss': pooled_loss / pooled_n if pooled_n else None}
    candidate = role_totals[1]
    gates = {
        'optimistic_ctw_supply': candidate['optimistic_intents_per_all_source_date'] >= 3.0,
        'yearly_minimum': all(v >= 150 for v in candidate['by_year'].values()),
        'three_symbol_breadth': all(v > 0 for v in candidate['by_symbol'].values()),
        'both_directions': all(v > 0 for v in candidate['by_direction'].values()),
    }
    if role_totals[0]['pooled_prequential']['n'] != role_totals[1]['pooled_prequential']['n']:
        raise RuntimeError('Reference/candidate predictive sample counts differ')
    output_bytes = sum(v['bytes'] for v in outputs)
    if output_bytes > CONTRACT['storage']['maximum_structural_output_bytes']:
        raise RuntimeError('Structural output exceeded its declared budget')
    require_freeze()
    for item in input_receipt['copies']:
        require_fingerprint(ROOT / item['copy']['path'], item['copy'])
    result = {
        'schema': 'zeta-ch015-complete-causal-structural-result-v1', 'recorded_utc': now(),
        'status': ('NECESSARY_CTW_SUPPLY_PASSED_ECONOMICS_UNOPENED' if all(gates.values())
                   else 'NECESSARY_CTW_SUPPLY_FAILED_CLOSE_FIXED_BUNDLE_BEFORE_ECONOMICS'),
        'input_receipt': fingerprint(EVIDENCE / 'INPUT_COPY_V1.json'),
        'implementation_freeze': fingerprint(EVIDENCE / 'STRUCTURAL_IMPLEMENTATION_FREEZE_V1.json'),
        'all_source_dates': day_labels, 'all_source_date_count': len(normal_days),
        'source_dates_by_year': by_year_days, 'per_symbol': by_symbol,
        'roles': role_totals, 'necessary_gates': gates, 'all_necessary_gates_pass': all(gates.values()),
        'output_files': outputs, 'output_bytes': output_bytes,
        'trade_execution_or_monetary_path_calculated': False,
        'candidate_2026_prices_opened': False, 'old_strategy_executed': False,
        'broker_queries': 0, 'free_bytes_after': capacity(),
        'interpretation': 'Full prospective causal online prediction and an optimistic intention upper bound. Scores are prequential matched-label information, not trade profits or a native result. No outcome-selected depth, alphabet, scale, threshold or temporal subset.',
    }
    receipt = write_json(result_path, result)
    print(json.dumps({'stage': 'structural_complete', 'status': result['status'],
                      'necessary_gates': gates, 'receipt': receipt}), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('prepare', 'structural'):
        raise SystemExit('Usage: adapter.py prepare|structural (normal own input/forecast production)')
    {'prepare': prepare, 'structural': structural}[sys.argv[1]]()
