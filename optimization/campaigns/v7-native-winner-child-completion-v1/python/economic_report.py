"""Publish complete owned native economics and the frozen whole-bundle judgment."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import io
import json
import math
import re

from native_run import FAMILY, ROOT, RAW, digest, receipt

START, MID, END = 1735689600, 1751328000, 1767225600


def read_text(path):
    data = path.read_bytes()
    encoding = 'utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else ('utf-16-le' if b'\x00' in data[:2000] else 'utf-8-sig')
    return data.decode(encoding, errors='replace')


def table(path):
    text = read_text(path)
    return list(csv.DictReader(io.StringIO(text), delimiter='\t' if '\t' in text.splitlines()[0] else ','))


def fields(text):
    return dict(re.findall(r'([a-zA-Z_][a-zA-Z_0-9]*)=([^\s;]+)', text))


def marker(log, name):
    lines = [line.split(name, 1)[1].strip() for line in log.splitlines() if name in line]
    unique = list(dict.fromkeys(lines))
    if len(unique) != 1:
        raise RuntimeError(f'Complete unique {name} unavailable: {len(unique)}')
    return fields(unique[0])


def drawdown(values):
    peak = values[0]
    largest = 0.0
    for value in values:
        peak = max(peak, value)
        largest = max(largest, peak - value)
    return largest


def publish_run(tag, output):
    folder = RAW / 'native' / tag
    completion = json.loads((folder / 'complete.json').read_bytes())
    archive = folder / 'files'
    log = '\n'.join(read_text(p) for p in sorted((archive / 'logs').rglob('*.log')))
    native, core, child = [marker(log, name) for name in ('V7RR1_NATIVE ', 'V7RR1_RESULT ', 'WC_RESULT ')]
    html_paths = list(archive.glob('*.htm*'))
    if len(html_paths) != 1:
        raise RuntimeError('Complete unique native HTML unavailable')
    html = read_text(html_paths[0])
    clean_html = re.sub(r'<[^>]*>', ' ', html)
    clean_html = re.sub(r'\s+', ' ', clean_html)
    quality = bool(re.search(r'(?:히스토리 품질|History Quality)\s*:\s*100%\s*(?:실제 틱|real ticks)', clean_html, re.I))
    equities = list(archive.rglob('equity.csv'))
    events_paths = list(archive.rglob('child-events.csv'))
    if len(equities) != 1 or len(events_paths) != 1:
        raise RuntimeError('Unique complete own ledgers unavailable')
    equity = [{k: float(v) for k, v in row.items()} for row in table(equities[0])]
    events = table(events_paths[0])
    if not equity or any(equity[i]['server'] < equity[i-1]['server'] for i in range(1, len(equity))):
        raise RuntimeError('Missing chronological native equity ledger')
    if any(not math.isfinite(v) for row in equity for v in row.values()):
        raise RuntimeError('Nonfinite native monetary observation')
    actual = float(native['profit'])
    conservative = float(core.get('stressed_net', 'nan')) - float(child['positive_swap'])
    mark_dd = drawdown([100.0] + [x['conservative_equity'] for x in equity])
    denominator = max(float(native['equity_dd']), float(core.get('stressed_dd', 'nan')), mark_dd, .01)
    opens = [x for x in events if x['event'] == 'CHILD_OPEN']
    closes = [x for x in events if x['event'] == 'CHILD_CLOSE']
    child_entries = {fields(x['detail'])['child']: fields(x['detail']) for x in opens}
    def child_stress_exit(row):
        detail = fields(row['detail'])
        entry = child_entries[detail['child']]
        allocated_positive = float(entry['positive_entry_swap']) * float(detail['volume']) / float(entry['volume'])
        return float(row['b']) - float(row['c']) - allocated_positive
    eligibility = [x for x in events if x['event'] == 'NATIVE_ELIGIBILITY' and float(x['a']) == 1]
    forecasts = list(archive.rglob('forecasts.csv'))
    forecasts_rows = table(forecasts[0]) if len(forecasts) == 1 else []
    updates = [x for x in events if x['event'] == 'UPDATE']
    update_causal = all(float(x['b']) < float(x['c']) and float(x['c']) <= float(x['server']) for x in updates)
    forecast_causal = all(float(x['D']) <= float(x['server']) for x in forecasts_rows)
    epochs = []
    previous = {'project_realized': 0., 'stress_balance': 100., 'positive_swap': 0., 'equity': 100., 'conservative_equity': 100.}
    for lo, hi in ((START, MID), (MID, END)):
        rows = [x for x in equity if lo <= x['server'] < hi]
        if not rows:
            raise RuntimeError('Complete declared half unavailable')
        last = rows[-1]
        child_exits = [x for x in closes if lo <= int(fields(x['detail'])['msc']) / 1000 < hi]
        child_opens = [x for x in opens if lo <= int(x['server']) < hi]
        epochs.append({'start': lo, 'end_exclusive': hi, 'last_mark': last['server'],
            'actual_closed': last['project_realized'] - previous['project_realized'],
            'conservative_closed': last['stress_balance'] - last['positive_swap'] - previous['stress_balance'] + previous['positive_swap'],
            'actual_marked': last['equity'] - previous['equity'],
            'conservative_marked': last['conservative_equity'] - previous['conservative_equity'],
            'children_opened': len(child_opens),
            'child_actual': sum(float(x['a']) for x in child_exits),
            'child_conservative': sum(child_stress_exit(x) for x in child_exits)})
        previous = last
    child_positive_entry_swap = sum(float(fields(x['detail'])['positive_entry_swap']) for x in opens)
    money_matches = abs(actual - float(core.get('actual_net', 'nan'))) < 1e-5 and abs(100 + actual - equity[-1]['balance']) < 1e-5
    tick_evidence = {}
    for symbol in ('US30', 'US100', 'US500'):
        generated = re.findall(re.escape(symbol) + r'[^\r\n]*?([\d]+) ticks[^\r\n]*?generated', log)
        tick_evidence[symbol] = sorted(set(int(x) for x in generated))
    valid = (completion['returncode'] == 0 and core['status'] == 'ECONOMIC' and quality and money_matches
        and all(int(child[k]) == 0 for k in ('faults', 'shadow_open', 'unresolved'))
        and int(child['children']) == int(child['closed_children']) == len(opens)
        and int(child['inferences']) == len(forecasts_rows) and int(child['updates']) == len(updates)
        and update_causal and forecast_causal and all(tick_evidence.values())
        and completion['binding']['unchanged'] and completion['capacity']['floor_ok'] and completion['capacity']['caps_ok']
        and not any(not x['floor_ok'] or not x['caps_ok'] for x in completion.get('capacity_events', [])))
    result = {'tag': tag, 'status': 'COMPLETE_NATIVE_ECONOMIC' if valid else 'OPERATING_CORRECTION_REQUIRED',
        'native': native, 'core': core, 'child': child, 'quality_100_real_ticks': quality,
        'tick_evidence': tick_evidence, 'money_matches': money_matches,
        'actual_net': actual, 'actual_wealth': 100 + actual,
        'log_growth': math.log((100 + actual) / 100) if actual > -100 else None,
        'conservative_net': conservative, 'conservative_wealth': 100 + conservative,
        'native_cash_dd': float(native['equity_dd']), 'native_dd_pct': float(native['equity_dd_relative_pct']),
        'closed_stress_dd': float(core.get('stressed_dd', 'nan')), 'conservative_mark_dd': mark_dd,
        'robust_denominator': denominator, 'robust_recovery': min(actual, conservative) / denominator,
        'epochs': epochs, 'children': len(opens), 'child_conservative': sum(float(x['b']) - float(x['c']) for x in closes) - child_positive_entry_swap,
        'otherwise_eligible': len(eligibility), 'eligible_declines': sum(float(x['b']) == 0 for x in eligibility),
        'decline_fraction': sum(float(x['b']) == 0 for x in eligibility) / len(eligibility) if eligibility else 0.,
        'forecast_causal': forecast_causal, 'update_causal': update_causal,
        'multipliers': sorted(set(x['multiplier'] for x in equity)),
        'child_volumes': sorted(set(float(fields(x['detail'])['volume']) for x in opens)),
        'equity_rows': len(equity), 'event_counts': {event: sum(x['event'] == event for x in events) for event in sorted(set(x['event'] for x in events))},
        'source_completion': {'path': (folder / 'complete.json').relative_to(ROOT).as_posix(), 'sha256': digest(folder / 'complete.json')},
        'limit': 'Actual quantity reinvestment is judged separately from additional concurrent exposure; resume behavior is not established by a fresh path.'}
    receipt(FAMILY / 'evidence' / output, result)
    print(json.dumps({k: result[k] for k in ('tag', 'status', 'actual_net', 'conservative_net', 'native_dd_pct', 'children')}), flush=True)


def publish_bundle(names, output):
    paths = [FAMILY / 'evidence' / name for name in names]
    rows = [json.loads(p.read_bytes()) for p in paths]
    if len(rows) != 6 or any(x['status'] != 'COMPLETE_NATIVE_ECONOMIC' for x in rows):
        raise RuntimeError('All six complete valid unchanged native paths are required for economic selection')
    reference = rows[1]
    comparisons = []
    for index in (3, 5):
        control, candidate = rows[index-1], rows[index]
        gates = {
            'actual_and_log_growth': candidate['actual_net'] > control['actual_net'] and candidate['log_growth'] > control['log_growth'],
            'conservative_five_percent': candidate['conservative_net'] >= 1.05 * control['conservative_net'] and candidate['conservative_wealth'] > control['conservative_wealth'],
            'robust_recovery': candidate['robust_recovery'] > control['robust_recovery'],
            'dd_ceiling': candidate['native_dd_pct'] <= min(control['native_dd_pct'] + 1.5, control['native_dd_pct'] * 1.10),
            'positive_halves': all(x[k] > 0 for x in candidate['epochs'] for k in ('actual_closed', 'conservative_closed', 'actual_marked', 'conservative_marked')),
            'child_activity': candidate['children'] >= 20 and all(x['children_opened'] >= 5 for x in candidate['epochs']),
            'child_halves': all(x[k] > 0 for x in candidate['epochs'] for k in ('child_actual', 'child_conservative')),
            'child_reference': candidate['child_conservative'] >= reference['child_conservative'],
            'eligible_decline': candidate['decline_fraction'] >= .05,
        }
        comparisons.append({'tag': candidate['tag'], 'control': control['tag'], 'gates': gates,
            'passes_numeric_gates': all(gates.values()),
            'requires_root_dd_exception': candidate['native_dd_pct'] > control['native_dd_pct'],
            'child_conservative': candidate['child_conservative'],
            'incremental_conservative': candidate['conservative_net'] - control['conservative_net']})
    eligible = sorted([x for x in comparisons if x['passes_numeric_gates']], key=lambda x: (-x['incremental_conservative'], x['tag'] != rows[3]['tag']))
    receipt(FAMILY / 'evidence' / output, {'utc': datetime.now(timezone.utc).isoformat(),
        'status': 'COMPLETE_SIX_PATH_NUMERIC_JUDGMENT', 'comparisons': comparisons,
        'numeric_finalist': eligible[0]['tag'] if eligible else None,
        'finalist_scope': 'Root must finish full causal/execution/input judgment and any DD exception; only then separately fund one unchanged confirmation pair.',
        'sources': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': digest(p)} for p in paths]})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'bundle'))
    parser.add_argument('inputs', nargs='+')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.action == 'run':
        publish_run(args.inputs[0], args.output)
    else:
        publish_bundle(args.inputs, args.output)
