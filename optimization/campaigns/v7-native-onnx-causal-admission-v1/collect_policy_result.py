"""Preserve a whole native V7 policy-selection or confirmation result.

This ordinary economic report producer reads this campaign's completed native
output. It does not launch MT5, change a policy, fit a model or waive quality.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import sys

from collect_native_result import FAMILY, ROOT, RUNTIME, RAW, NativeTables, decode, fields, record


def native_time(value):
    return int(datetime.strptime(value, '%Y.%m.%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def collect(run_tag):
    match = re.fullmatch(r'(selection|confirmation)-(control|static|online)-v[1-9][0-9]*', run_tag)
    if not match:
        raise ValueError('Only this declared native policy matrix is supported')
    phase, role = match.groups()
    role_number = {'control': 0, 'static': 2, 'online': 3}[role]
    name = 'ZetaV7CAControl' if role == 'control' else 'ZetaV7CALearner'
    if phase == 'confirmation':
        finalist = json.loads((FAMILY / 'evidence/POLICY_FINALIST_FREEZE_V1.json').read_text(encoding='utf-8'))
        if finalist['status'] != 'ONE_FIXED_2025_NATIVE_POLICY_SELECTED' or role not in ('control', finalist['role']):
            raise RuntimeError('Only the declared control and selected unchanged policy may confirm')
    destination = RAW / phase / run_tag
    if destination.exists():
        raise RuntimeError('This native result is already preserved')
    if shutil.disk_usage(ROOT).free < 30 * 1024**3 + 256 * 1024**2:
        raise RuntimeError('Native result storage reserve')
    candidates = [(p, p / 'MQL5/Files' / name / 'ca' / run_tag)
                  for p in (RUNTIME / 'Tester').glob('Agent-*') if p.is_dir()]
    candidates = [(p, q) for p, q in candidates if q.is_dir()]
    if len(candidates) != 1:
        raise RuntimeError('Exactly one own native output tree is required')
    agent, own = candidates[0]
    logs = [(p, decode(p)) for p in sorted((agent / 'logs').glob('*.log'))]
    logs = [(p, text) for p, text in logs if 'InpCausalRunTag=' + run_tag in text]
    if len(logs) != 1:
        raise RuntimeError('A unique native run log is required')
    agent_log, text = logs[0]
    anchor = text.rfind('InpCausalRunTag=' + run_tag)
    start = text.rfind('testing of Experts\\', 0, anchor)
    if start < 0:
        raise RuntimeError('Missing native run header')
    start = text.rfind('\n', 0, start) + 1
    next_start = text.find('testing of Experts\\', anchor + 1)
    end = text.rfind('\n', anchor, next_start) if next_start >= 0 else len(text)
    episode = text[start:end]
    if ' thread finished' not in episode:
        raise RuntimeError('Native execution has not completed')
    destination.mkdir(parents=True)
    archived = destination / 'Files' / name / 'ca' / run_tag
    shutil.copytree(own, archived)
    shutil.copytree(RUNTIME / 'reports' / run_tag, destination / 'report')
    (destination / 'agent-episode.log').write_text(episode, encoding='utf-8')
    reports = list((destination / 'report').glob('*.htm'))
    if len(reports) != 1:
        raise RuntimeError('A single complete native HTML report is required')
    table = NativeTables()
    table.feed(decode(reports[0]))
    report_labels = defaultdict(list)
    for row in table.rows:
        for i, value in enumerate(row[:-1]):
            if value.endswith(':'):
                report_labels[value].append(row[i + 1])
    quality = report_labels.get('히스토리 품질:', report_labels.get('History Quality:', []))
    reasons = []
    if not quality or not all(re.search(r'^100%\s', v) and ('실제' in v or 'real' in v.lower()) for v in quality):
        reasons.append('Final policy economics require 100% real ticks; the training exception does not apply')
    summaries = [[fields(line) for line in episode.splitlines() if marker in line]
                 for marker in ('V7CA_NATIVE profit=', 'V7CA_RESULT status=', 'CAUSAL_RESULT role=')]
    if any(len(v) != 1 for v in summaries):
        reasons.append('Native/core/learning completion records are not unique')
    contracts = defaultdict(dict)
    for line in episode.splitlines():
        if 'V7CA_CONTRACT stage=' in line:
            item = fields(line)
            stage, symbol = item.pop('stage'), item.pop('symbol')
            contracts[stage][symbol] = item
    if set(contracts.get('START', {})) != {'US30', 'US100', 'US500'} or contracts.get('START') != contracts.get('END'):
        reasons.append('Complete stable native contract and swap observations are missing')
    economics = None
    learning = None
    periods = {}
    if all(len(v) == 1 for v in summaries):
        native, core, learning = (v[0] for v in summaries)
        if int(learning['role']) != role_number or learning['tag'] != run_tag:
            reasons.append('Native policy identity is inconsistent')
        if core['status'] != 'ECONOMIC' or int(learning['faults']) != 0 or int(learning['open']) != 0 or int(learning['mark_known']) != 1:
            reasons.append('Native accounting, trading or learning is incomplete')
        if core['status'] == 'ECONOMIC':
            life = rows(archived / 'research/research-lifecycles.csv')
            births = [v for v in life if v['event'] == 'BIRTH']
            closes = [v for v in life if v['event'] == 'CLOSE']
            birth_ids = Counter((v['component_id'], v['position_identifier']) for v in births)
            close_ids = Counter((v['component_id'], v['position_identifier']) for v in closes)
            if birth_ids != close_ids or any(v != 1 for v in birth_ids.values()) or any(v['partial_observation'] != '0' for v in life):
                reasons.append('Native lifecycles are not one-to-one complete')
            decisions = rows(archived / 'learning/decisions.csv')
            labels = rows(archived / 'learning/labels.csv')
            updates = rows(archived / 'learning/updates.csv')
            path = rows(archived / 'learning/equity.csv')
            ids = [int(v['id']) for v in decisions]
            label_ids = [int(v['id']) for v in labels]
            if ids != list(range(1, len(ids) + 1)) or label_ids != ids[:len(labels)]:
                reasons.append('Decision/reward population is incomplete or duplicated')
            if len(decisions) != int(learning['records']) or len(labels) != int(learning['completed']) or len(updates) != int(learning['updates']) or len(decisions) - len(labels) != int(learning['pending']):
                reasons.append('Complete learning ledgers do not match native totals')
            if any(native_time(v['available']) >= native_time(v['consumed']) for v in updates):
                reasons.append('An online update consumed a same-time or future label')
            if role != 'online' and updates:
                reasons.append('A frozen policy unexpectedly updated coefficients')
            if role == 'control' and decisions:
                reasons.append('The exact control unexpectedly used learned admission')
            abstentions = sum(int(v['action']) == 0 for v in decisions)
            if abstentions != int(learning['abstentions']):
                reasons.append('Abstention population differs from native totals')
            actual, stress = float(core['actual_net']), float(core['stressed_net'])
            conservative = stress - float(learning['positive_closed_swap'])
            dd_cash, dd_pct = float(native['equity_dd']), float(native['equity_dd_relative_pct'])
            if len(closes) != int(core['closed']) or abs(sum(float(v['actual_net_usd']) for v in closes) - actual) > 1e-5 or abs(sum(float(v['stressed_net_usd']) for v in closes) - stress) > 1e-5:
                reasons.append('Complete lifecycle economics do not match native totals')
            bounds = [('2025-H1', '2025.01.01', '2025.07.01'), ('2025-H2', '2025.07.01', '2026.01.01')]
            if phase == 'confirmation':
                bounds += [('2026-H1', '2026.01.01', '2026.07.01'), ('2026-JulAug', '2026.07.01', '2026.09.01')]
            previous_actual = previous_conservative = 100.0
            for label, begin, finish in bounds:
                selected = [v for v in closes if begin <= v['server_time'] < finish]
                policy_rows = [v for v in decisions if begin <= v['decision'] < finish]
                marks = [v for v in path if begin <= v['server'] < finish]
                if not marks:
                    reasons.append('Missing full epoch account path: ' + label)
                    continue
                last_actual = float(marks[-1]['actual_equity'])
                last_conservative = float(marks[-1]['conservative_stress_equity'])
                periods[label] = dict(closed=len(selected), actual_closed=sum(float(v['actual_net_usd']) for v in selected),
                                      stressed_closed=sum(float(v['stressed_net_usd']) for v in selected),
                                      actual_marked_change=last_actual - previous_actual,
                                      conservative_marked_change=last_conservative - previous_conservative,
                                      ending_actual_equity=last_actual, ending_conservative_equity=last_conservative,
                                      model_decisions=len(policy_rows), abstentions=sum(int(v['action']) == 0 for v in policy_rows),
                                      path_rows=len(marks), first_observation=marks[0]['server'], last_observation=marks[-1]['server'])
                previous_actual, previous_conservative = last_actual, last_conservative
            economics = dict(actual_net=actual, original_stressed_net=stress, no_positive_swap_stressed_net=conservative,
                             actual_wealth=100 + actual, original_stressed_wealth=100 + stress, conservative_stressed_wealth=100 + conservative,
                             actual_log_growth=math.log1p(actual / 100) if actual > -100 else None,
                             conservative_log_growth=math.log1p(conservative / 100) if conservative > -100 else None,
                             native_equity_DD_cash=dd_cash, native_equity_DD_percent=dd_pct,
                             conservative_recovery=conservative / max(.01, dd_cash, float(core['stressed_dd'])),
                             closed_lifecycles=len(closes), native_trade_count=float(native['trades']),
                             per_component=dict(Counter(v['component_id'] for v in closes)),
                             model_decisions=len(decisions), completed_labels=len(labels), online_updates=len(updates),
                             abstentions=abstentions, path_rows=len(path),
                             daily_lot_multipliers=sorted(set(int(v['day_multiplier']) for v in path)))
    result = dict(utc=datetime.now(timezone.utc).isoformat(),
                  status='COMPLETE_NATIVE_POLICY_RUN_REQUIRES_ADJACENT_MATRIX_BINDING' if not reasons else 'CORRECTION_REQUIRED_NO_ECONOMIC_VERDICT',
                  run_tag=run_tag, phase=phase, role=role, reasons=reasons, economics=economics, epochs=periods,
                  native_learning=learning, contracts=dict(contracts), report_labels=dict(report_labels),
                  source_agent_log=record(agent_log), archived_files=[record(p) for p in sorted(destination.rglob('*')) if p.is_file()],
                  scope='Full native V7 economic observation only. The complete immediately adjacent unchanged-input matrix must qualify before role selection or confirmation judgment.',
                  training_quality_exception_applies=False, live_changes=False, free_bytes=shutil.disk_usage(ROOT).free)
    (destination / 'NATIVE_POLICY_RESULT_V1.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'run_tag', 'reasons', 'economics', 'epochs')}, indent=2))


if __name__ == '__main__':
    collect(sys.argv[1])
