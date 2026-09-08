"""Publish completed native account and learning ledgers; never execute a strategy."""
from __future__ import annotations

import argparse
import collections
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import re

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
RAW = ROOT / 'optimization/artifacts/raw/v7-native-input-density-admission-v1'


def reference(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
            'sha256': digest.hexdigest().upper()}


def read_text(path):
    data = path.read_bytes()
    encoding = ('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else
                'utf-16-le' if data[:200].count(b'\x00') > 25 else 'utf-8-sig')
    return data.decode(encoding, errors='strict')


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite native economic value')
    return result


def stamp(value):
    try:
        return int(value)
    except ValueError:
        return int(datetime.strptime(value, '%Y.%m.%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())


def fields(line, marker):
    return dict(re.findall(r'(\w+)=([^\s]+)', line.split(marker, 1)[1]))


def publish(path, payload):
    if path.exists():
        raise FileExistsError('Preserve earlier published result: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def path_report(tag, history_tag, output):
    folder = RAW / 'native' / tag
    complete_path = folder / 'complete.json'
    complete = json.loads(complete_path.read_bytes())
    start = json.loads((folder / 'start.json').read_bytes())
    frozen_path = ROOT / start['freeze']['path']
    frozen = json.loads(frozen_path.read_bytes())
    history_path = RAW / 'history' / history_tag / 'observation.json'
    after_history = json.loads(history_path.read_bytes())
    issues = []
    if complete['returncode'] != 0 or not complete['binding']['unchanged']:
        issues.append('Native completion or frozen consumed inputs changed')
    if not start['binding']['unchanged'] or reference(frozen_path) != start['freeze']:
        issues.append('Initial whole input identity differs')
    retained = [reference(ROOT / item['path']) == item for item in complete['files']]
    if not all(retained):
        issues.append('Native archive retention differs')
    final_input_changes = [item['path'] for item in frozen['files']
                           if not (ROOT/item['path']).is_file() or reference(ROOT/item['path']) != item]
    if final_input_changes:
        issues.append('Whole consumed input bytes changed after history observation')
    past = frozen['history']
    history_equal = {}
    for name in ('streams', 'contracts', 'build', 'terminal_path', 'data_path'):
        history_equal[name] = past[name] == after_history[name]
    # Terminal metadata also contains current connection information; only build is economic platform identity.
    history_equal['symbol_db'] = (past['symbol_db_after'] == after_history['symbol_db_before']
                                  == after_history['symbol_db_after'])
    if not all(history_equal.values()):
        issues.append('Past stream/contract/symbol database changed')
    logs = list((folder / 'files' / 'logs' / 'Tester').glob('Agent-*/logs/*.log'))
    if len(logs) != 1:
        raise ValueError('Expected one complete owned native agent log')
    log = read_text(logs[0])
    summaries = {}
    for key in ('DENSITY_RESULT', 'V7RR1_NATIVE', 'V7RR1_RESULT', 'V7RR1_UNAVAILABLE_SUMMARY'):
        lines = [line for line in log.splitlines() if key + ' ' in line]
        if len(lines) != 1:
            raise ValueError('Missing or duplicate native final summary ' + key)
        summaries[key] = fields(lines[0], key)
    native = summaries['V7RR1_NATIVE']
    density = summaries['DENSITY_RESULT']
    original = summaries['V7RR1_RESULT']
    unavailable = summaries['V7RR1_UNAVAILABLE_SUMMARY']
    if density['status'] != 'COMPLETE' or original['status'] != 'ECONOMIC':
        issues.append('Native engine requires correction')
    fault_lines = [line for line in log.splitlines() if 'DENSITY_FAULT' in line]
    if fault_lines:
        issues.append('Native density fault')
    for key in ('invalid_direction', 'short_copy', 'invalid_price', 'invalid_tick', 'nonfinite', 'unclassified'):
        if int(unavailable[key]):
            issues.append('Invalid native unavailable class: ' + key)
    if int(density['open_positions']) or int(density['open_orders']):
        issues.append('Native account is not flat')
    report_files = list((folder / 'files').glob('*.htm*'))
    if len(report_files) != 1:
        raise ValueError('Expected one complete native HTML report')
    report = read_text(report_files[0])
    visible = html.unescape(re.sub(r'<[^>]*>', ' ', report))
    quality = re.search(r'(?:History Quality|히스토리 품질):\s*([\d.]+)%', visible)
    if not quality:
        raise ValueError('Native history quality label unavailable')
    history_quality = float(quality.group(1))
    if history_quality != 100.0:
        issues.append('Native history is not 100 percent')
    tick_evidence = [line for line in log.splitlines() if
                     ('real ticks' in line.lower() or 'ticks generated' in line.lower())]
    roots = list((folder / 'files' / 'Files').glob('*/' + tag))
    if len(roots) != 1:
        raise ValueError('Expected one exact native artifact namespace')
    own = roots[0]
    equity = rows(own / 'learning/equity.csv')
    exits = rows(own / 'learning/exits.csv')
    lifecycle = rows(own / 'research/research-lifecycles.csv')
    candidates = rows(own / 'research/research-candidates.csv')
    learning_file = own / 'learning/learning.csv'
    learning = rows(learning_file) if learning_file.exists() else []
    if not equity or not exits:
        raise ValueError('Missing full native economic trajectory')
    for row in equity:
        for key in ('actual_equity', 'native_balance', 'conservative_mark', 'conservative_closed_balance'):
            number(row[key])
    closed = [row for row in lifecycle if row['event'] == 'CLOSE']
    lifecycle_events = dict(collections.Counter(row['event'] for row in lifecycle))
    actual = number(original['actual_net'])
    conservative = number(density['conservative_net'])
    original_stressed = number(original['stressed_net'])
    exit_actual = sum(number(row['actual_net']) for row in exits)
    exit_stressed = sum(number(row['original_stressed_net']) for row in exits)
    positive_swap = sum(max(0, number(row['swap'])) for row in exits)
    reconciliation = {
        'actual_exit_sum': exit_actual, 'original_stressed_exit_sum': exit_stressed,
        'positive_swap_sum': positive_swap,
        'conservative_exit_sum': exit_stressed-positive_swap,
        'final_actual_equity': number(equity[-1]['actual_equity']),
        'final_conservative_mark': number(equity[-1]['conservative_mark']),
        'native_mark_rows': int(density['marks']) == len(equity),
        'native_exit_rows': int(density['exits']) == len(exits),
        'actual_matches': abs(exit_actual-actual) < 1e-5,
        'stressed_matches': abs(exit_stressed-original_stressed) < 1e-5,
        'conservative_matches': abs(exit_stressed-positive_swap-conservative) < 1e-5,
        'final_actual_matches': abs(number(equity[-1]['actual_equity'])-100-actual) < 1e-5,
        'final_conservative_matches': abs(number(equity[-1]['conservative_mark'])-100-conservative) < 1e-5,
        'full_lifecycles': all(row['partial_observation'] == '0' and row['research_dropped_records'] == '0' for row in lifecycle),
        'undropped_candidates': all(row['research_dropped_records'] == '0' for row in candidates),
        'closed_count_matches': int(original['closed']) == len(closed),
        'unique_closed_lifecycles': len({row['position_identifier'] for row in closed}) == len(closed),
        'full_start_and_end': int(equity[0]['server_time']) < 1735862400 and int(equity[-1]['server_time']) >= 1767139200,
    }
    if any(value is False for value in reconciliation.values()):
        issues.append('Native economic ledger reconciliation incomplete')
    forecasts = [row for row in learning if row['event'] == 'FORECAST']
    observations = [row for row in learning if row['event'] == 'OBSERVATION']
    updates = [row for row in learning if row['event'] == 'UPDATE']
    abstentions = [row for row in forecasts if row['allow'] == '0']
    known = {}
    used = set()
    ordering_issues = []
    sequences = [int(row['sequence']) for row in learning]
    if sequences != list(range(1, len(learning)+1)):
        ordering_issues.append('Noncontiguous learning sequence')
    for row in learning:
        oid = int(row['observation_id'])
        if row['event'] == 'OBSERVATION':
            if oid in known:
                ordering_issues.append('Duplicate observation id')
            known[oid] = row
        elif row['event'] == 'UPDATE':
            source = known.get(oid)
            if source is None or oid in used:
                ordering_issues.append('Unknown or repeated completed observation update')
            elif (int(source['server_time']) >= int(row['server_time'])
                  or any(source[k] != row[k] for k in ('component', 'decision_bar', 'z', 'available_time'))):
                ordering_issues.append('Observation update identity or strict maturity differs')
            used.add(oid)
        elif row['event'] == 'FORECAST':
            if int(row['last_applied_observation']) >= int(row['server_time']):
                ordering_issues.append('Forecast used current or future observation')
            if (number(row['score']) <= number(row['cutoff'])) != (row['allow'] == '1'):
                ordering_issues.append('Forecast and declared cutoff decision differ')
    counters = {'forecasts': len(forecasts), 'observations': len(observations),
                'updates': len(updates), 'abstentions': len(abstentions)}
    if any(int(density[key]) != value for key, value in counters.items()):
        ordering_issues.append('Native learning counters differ from complete ledger')
    if ordering_issues:
        issues.append('Learning causal ledger incomplete')
    settings = (FAMILY/'settings'/(tag+'.set')).read_text(encoding='utf-8')
    binding_value = re.search(r'^InpNativeBinding=([A-F0-9]{64})$', settings, re.MULTILINE).group(1)
    fit_hash = reference(FAMILY/'models/initial_fit_v1.json')['sha256']
    if any(row['fit_sha'] != fit_hash or row['run_binding'] != binding_value for row in learning):
        issues.append('Learning row model/run identity differs')
    pending_ids = sorted(set(known)-used) if int(density['role']) == 2 else []
    if int(density['pending']) != len(pending_ids):
        issues.append('Final pending observations do not reconcile')
    source_known = {}
    for row in candidates:
        if row['stage'] in ('SIGNAL', 'OUTCOME') and row['signal_known'] == '1':
            key = (row['component_id'], row['decision_bar'])
            values = tuple(row[k] for k in ('feature', 'signal_passed', 'direction'))
            if key in source_known and source_known[key] != values:
                issues.append('Conflicting original known feature observation')
            source_known[key] = values
    if int(density['role']) != 0 and len(source_known) != len(observations):
        issues.append('Original known decision population differs from own observation count')
    if int(density['checkpoints']) != int(density['readbacks']):
        issues.append('Checkpoint count does not match successful native readbacks')
    if int(density['role']) == 2 and int(density['update_inferences']) != len(updates):
        issues.append('Online updates differ from actual ONNX update inferences')
    periods = {}
    for name, begin, end in [('2025H1', '2025-01-01', '2025-07-01'),
                              ('2025H2', '2025-07-01', '2026-01-01')]:
        lo = int(datetime.fromisoformat(begin).replace(tzinfo=timezone.utc).timestamp())
        hi = int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp())
        selected = [row for row in exits if lo <= int(row['deal_msc'])/1000 < hi]
        marks = [row for row in equity if lo <= int(row['server_time']) < hi]
        prior = [row for row in equity if int(row['server_time']) < lo]
        initial_actual = number(prior[-1]['actual_equity']) if prior else 100.0
        initial_conservative = number(prior[-1]['conservative_mark']) if prior else 100.0
        periods[name] = {
            'actual_realized': sum(number(row['actual_net']) for row in selected),
            'conservative_realized': sum(number(row['original_stressed_net'])-max(0,number(row['swap'])) for row in selected),
            'actual_marked_change': number(marks[-1]['actual_equity'])-initial_actual,
            'conservative_marked_change': number(marks[-1]['conservative_mark'])-initial_conservative,
            'closed_lifecycles': sum(lo <= stamp(row['server_time']) < hi for row in closed),
            'abstentions': sum(lo <= int(row['server_time']) < hi for row in abstentions),
            'last_mark_server': int(marks[-1]['server_time']),
        }
    monthly = {}
    prior_actual = prior_conservative = 100.0
    month_last = {}
    for row in equity:
        month = datetime.fromtimestamp(int(row['server_time']), timezone.utc).strftime('%Y-%m')
        month_last[month] = row
    for month, row in sorted(month_last.items()):
        actual_end, conservative_end = number(row['actual_equity']), number(row['conservative_mark'])
        monthly[month] = {'actual_change': actual_end-prior_actual,
                          'conservative_change': conservative_end-prior_conservative,
                          'actual_return_percent': 100*(actual_end/prior_actual-1) if prior_actual > 0 else None,
                          'conservative_return_percent': 100*(conservative_end/prior_conservative-1) if prior_conservative > 0 else None,
                          'actual_end': actual_end, 'conservative_end': conservative_end}
        prior_actual, prior_conservative = actual_end, conservative_end
    storage = [json.loads(line) for line in (folder/'storage.jsonl').read_text().splitlines()]
    storage.append(complete['capacity'])
    if not all(row['floor_ok'] and row['caps_ok'] and row['funded'] for row in storage):
        issues.append('Capacity reserve or full remaining funding not maintained')
    result = {
        'utc': datetime.now(timezone.utc).isoformat(), 'tag': tag,
        'status': 'COMPLETE_NATIVE_ECONOMIC_PATH' if not issues else 'CORRECTION_REQUIRED',
        'issues': issues, 'producer': reference(Path(__file__)), 'native_complete': reference(complete_path),
        'freeze': reference(frozen_path), 'post_history': reference(history_path),
        'history_equal': history_equal, 'history_quality_percent': history_quality,
        'post_history_whole_input_changes': final_input_changes,
        'native_tick_evidence': tick_evidence, 'summaries': summaries, 'fault_lines': fault_lines,
        'retention': {'files': len(retained), 'all_bytes_hashes_match': all(retained)},
        'economics': {'actual_net': actual, 'original_stressed_net': original_stressed,
                      'conservative_net': conservative, 'actual_wealth': 100+actual,
                      'conservative_wealth': 100+conservative,
                      'actual_log_growth': math.log((100+actual)/100) if actual > -100 else None,
                      'conservative_log_growth': math.log((100+conservative)/100) if conservative > -100 else None,
                      'native_equity_dd_percent': number(density['native_equity_dd_percent']),
                      'native_equity_dd_usd': number(density['native_equity_dd']),
                      'conservative_closed_dd_usd': number(density['conservative_closed_dd']),
                      'robust_recovery': number(density['robust_recovery']),
                      'closed_lifecycles': len(closed)},
        'periods': periods, 'monthly': monthly, 'reconciliation': reconciliation, 'lifecycle_events': lifecycle_events,
        'learning': {**counters, 'causal_issues': ordering_issues,
                     'completed_observations_unapplied': pending_ids,
                     'original_known_decision_population': len(source_known),
                     'native_pending': int(density['pending']),
                     'checkpoints': int(density['checkpoints']), 'readbacks': int(density['readbacks']),
                     'actual_restart_demonstrated': False},
        'quantity': {'daily_multipliers': sorted(set(int(row['day_multiplier']) for row in equity)),
                     'lifecycle_volumes': sorted(set(number(row['volume']) for row in lifecycle)),
                     'lot_compounding_observed': any(int(row['day_multiplier']) > 1 for row in equity)},
        'capacity': {'observations': len(storage), 'minimum_free_bytes': min(row['free'] for row in storage),
                     'all_floor_caps_funded': all(row['floor_ok'] and row['caps_ok'] and row['funded'] for row in storage)},
        'limits': ['Native equity DD uses MT5 intratick statistics; the conservative marked trajectory is sampled once per available minute and is not a claim of intratick stressed DD.',
                   'Epoch marked change uses final available mark before its boundary, without synthetic interpolation. Realized exit attribution is also reported.',
                   'This report does not run a model, replay economic outcomes or demonstrate an actual restart. Root interprets full tick/platform/input and causal evidence before economic judgment.'],
    }
    publish(FAMILY/'evidence'/output, result)
    print(json.dumps({'tag': tag, 'status': result['status'], 'issues': issues, 'economics': result['economics'],
                      'periods': periods, 'learning': counters}, indent=2))


def bundle_report(names, output):
    if len(names) != 4:
        raise ValueError('Whole fixed bundle needs control/static/control/online reports')
    paths = [FAMILY/'evidence'/name for name in names]
    reports = [json.loads(path.read_bytes()) for path in paths]
    if any(report['status'] != 'COMPLETE_NATIVE_ECONOMIC_PATH' for report in reports):
        raise ValueError('Only complete valid native paths can enter economic selection')
    if [int(report['summaries']['DENSITY_RESULT']['role']) for report in reports] != [0,1,0,2]:
        raise ValueError('Role bundle does not match prospective comparison order')
    if len({report['freeze']['sha256'] for report in reports}) != 1:
        raise ValueError('Whole bundle does not have one common input freeze')
    candidates = []
    for control, candidate in ((reports[0], reports[1]), (reports[2], reports[3])):
        c, x = control['economics'], candidate['economics']
        periods = list(candidate['periods'].values())
        nominal = x['native_equity_dd_percent'] <= c['native_equity_dd_percent']
        limit = min(c['native_equity_dd_percent']+1.5, c['native_equity_dd_percent']*1.10)
        positive = all(period[key] > 0 for period in periods for key in
                       ('actual_realized', 'conservative_realized', 'actual_marked_change', 'conservative_marked_change'))
        gates = {
            'actual_wealth_and_log_growth': x['actual_wealth'] > c['actual_wealth'],
            'conservative_net_at_least_105_percent': x['conservative_net'] >= 1.05*c['conservative_net'],
            'robust_recovery_improves': x['robust_recovery'] > c['robust_recovery'],
            'effective_drawdown_limit': x['native_equity_dd_percent'] <= limit,
            'positive_both_halves_actual_and_conservative': positive,
            'closed_whole_at_least_100': x['closed_lifecycles'] >= 100,
            'closed_each_half_at_least_25': all(period['closed_lifecycles'] >= 25 for period in periods),
            'actual_abstentions_at_least_20': candidate['learning']['abstentions'] >= 20,
            'abstentions_each_half_at_least_5': all(period['abstentions'] >= 5 for period in periods),
        }
        candidates.append({'tag': candidate['tag'], 'control': control['tag'], 'gates': gates,
                           'eligible': all(gates.values()), 'nominal_dd_pass': nominal,
                           'effective_dd_limit_percent': limit,
                           'dd_exception_needed': not nominal,
                           'dd_exception_used': not nominal and all(gates.values()),
                           'economics': x, 'periods': candidate['periods'],
                           'quantity': candidate['quantity']})
    eligible = sorted((candidate for candidate in candidates if candidate['eligible']),
                      key=lambda x: (-x['economics']['conservative_wealth'],
                                     x['economics']['native_equity_dd_percent'],
                                     0 if x['tag'].startswith('static') else 1))
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'status': 'COMPLETE_FIXED_NATIVE_SELECTION',
              'producer': reference(Path(__file__)), 'reports': [reference(path) for path in paths],
              'candidates': candidates, 'finalist': eligible[0]['tag'] if eligible else None,
              'confirmation_opened': False, 'actual_restart_demonstrated': False,
              'compounding_not_inferred_from_profit_alone': True,
              'temporal_interpretation': 'Report and require positive native marked changes and realized exit attribution in each predeclared half; no synthetic prices, boundary interpolation or saved-profit scaling.',
              'closed_neighborhood_rescue_authorized': False}
    publish(FAMILY/'evidence'/output, result)
    print(json.dumps(result, indent=2))


def figure_report(names, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    output_path = FAMILY/'results'/output
    if output_path.exists():
        raise FileExistsError('Preserve previous native figure')
    reports = [json.loads((FAMILY/'evidence'/name).read_bytes()) for name in names]
    if any(report['status'] != 'COMPLETE_NATIVE_ECONOMIC_PATH' for report in reports):
        raise ValueError('Only complete native economic reports can be plotted')
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    colors = ['#718096', '#167c91', '#a9adb5', '#b05b2d']
    for index, report in enumerate(reports):
        root = ROOT / report['native_complete']['path']
        equity_path = next((root.parent/'files/Files').glob('*/'+report['tag']+'/learning/equity.csv'))
        columns = ([], [], [], [], [])
        with equity_path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                for target, key in zip(columns, ('server_time','actual_equity','conservative_mark','day_multiplier','lots')):
                    target.append(float(row[key]))
        time, actual, conservative, units, lots = (np.asarray(column) for column in columns)
        time = time.astype('datetime64[s]')
        style = '--' if index == 2 else '-'
        label = report['tag']
        options = dict(color=colors[index], label=label, linestyle=style, linewidth=1.1)
        axes[0,0].plot(time, actual, **options)
        axes[0,1].plot(time, actual, **options)
        axes[0,2].plot(time, conservative, **options)
        sampled_dd = 100*(actual/np.maximum.accumulate(np.r_[100,actual])[1:]-1)
        axes[1,0].plot(time, sampled_dd, **options)
        months = list(report['monthly'])
        axes[1,1].plot(range(len(months)), [report['monthly'][month]['actual_return_percent'] for month in months], marker='.', **options)
        axes[1,2].step(time, units, where='post', **options)
    axes[0,0].set_title('Actual native account equity')
    axes[0,1].set_title('Same actual equity, logarithmic scale')
    axes[0,1].set_yscale('log')
    axes[0,2].set_title('Conservative doubled-cost equity marks')
    axes[1,0].set_title('Drawdown at available minute marks')
    axes[1,1].set_title('Actual monthly marked return (%)')
    axes[1,1].set_xticks(range(12), [str(i) for i in range(1,13)])
    axes[1,1].set_xlabel('2025 month')
    axes[1,2].set_title('Original daily volume multiplier')
    axes[1,2].set_ylim(bottom=0.8)
    for ax in axes.flat:
        ax.grid(alpha=.22)
        ax.legend(fontsize=8)
        ax.tick_params(axis='x', labelsize=8)
    for ax in axes[0]:
        ax.set_ylabel('USD; initial capital 100')
    axes[1,0].set_ylabel('% below sampled running peak')
    axes[1,2].set_ylabel('Multiplier')
    fig.suptitle('Original V7 input-density admission | full 2025 native real ticks\n'
                 'Native intratick DD belongs to the numeric reports; marked curves do not establish future growth.', fontsize=14)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(json.dumps(reference(output_path)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', help='Native path tag, or bundle for complete four-path economic selection')
    parser.add_argument('--history')
    parser.add_argument('--reports', nargs=4)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.tag == 'figure':
        figure_report(args.reports, args.output)
    elif args.tag == 'bundle':
        bundle_report(args.reports, args.output)
    else:
        path_report(args.tag, args.history, args.output)
