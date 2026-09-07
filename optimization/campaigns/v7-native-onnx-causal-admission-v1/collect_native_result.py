"""Preserve and summarize one completed ordinary native economic run.

This collector reads only this campaign's stopped-run artifacts. It does not
start MT5, place trades, generate prices, change a policy or choose a seed.
"""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import re
import shutil
import sys

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RUNTIME = ROOT / 'optimization/runtime/v7-native-onnx-causal-admission-v1-portable'
RAW = ROOT / 'optimization/artifacts/raw/v7-native-onnx-causal-admission-v1'


def decode(path):
    blob = path.read_bytes()
    return blob.decode('utf-16' if blob[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')


def record(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest().upper()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=digest)


def fields(line):
    return dict(re.findall(r'([A-Za-z_][A-Za-z_0-9]*)=([^\s]+)', line))


class NativeTables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def summarize(run_tag, report_name):
    for value in (run_tag, report_name):
        if not re.fullmatch(r'[a-z0-9-]+', value):
            raise ValueError('A run identifier must stay in its own namespace')
    if re.fullmatch(r'training-control-v[0-9]+', run_tag):
        role = 'control'
        name = 'ZetaV7CAControl'
        destination = RAW / 'training/control'
    else:
        match = re.fullmatch(r'training-episode-(0[1-8])-v1', run_tag)
        if not match:
            raise ValueError('This producer currently collects the fixed training matrix only')
        role = 'training'
        name = 'ZetaV7CALearner'
        destination = RAW / 'training' / ('episode-' + match.group(1))
    if destination.exists():
        raise RuntimeError('A native run archive already exists')
    if shutil.disk_usage(ROOT).free < 30 * 1024**3 + 256 * 1024**2:
        raise RuntimeError('Economic artifact reserve')
    agents = [p for p in (RUNTIME / 'Tester').glob('Agent-*') if p.is_dir()]
    namespace = 'optimization/causal-admission' if run_tag == 'training-control-v1' else 'ca'
    paths = [(p, p / 'MQL5/Files' / name / namespace / run_tag) for p in agents]
    paths = [(p, q) for p, q in paths if q.is_dir()]
    if len(paths) != 1:
        raise RuntimeError('Exactly one own episode output tree is required')
    agent, own_files = paths[0]
    logs = sorted((agent / 'logs').glob('*.log'))
    anchored = [(p, decode(p)) for p in logs]
    anchored = [(p, text) for p, text in anchored if 'InpCausalRunTag=' + run_tag in text]
    if len(anchored) != 1:
        raise RuntimeError('An episode must have one attributable native log')
    agent_log, text = anchored[0]
    anchor = text.rfind('InpCausalRunTag=' + run_tag)
    start = text.rfind('testing of Experts\\', 0, anchor)
    if start < 0:
        raise RuntimeError('Native start header is missing')
    # Start at the beginning of that log row and stop at the next run header.
    start = text.rfind('\n', 0, start) + 1
    next_start = text.find('testing of Experts\\', anchor + 1)
    end = text.rfind('\n', anchor, next_start) if next_start >= 0 else len(text)
    episode_text = text[start:end]
    if ' thread finished' not in episode_text:
        raise RuntimeError('The native economic run is not complete')
    destination.mkdir(parents=True)
    archived_own = destination / 'Files' / name / namespace / run_tag
    shutil.copytree(own_files, archived_own)
    shutil.copytree(RUNTIME / 'reports' / report_name, destination / 'report')
    (destination / 'agent-episode.log').write_text(episode_text, encoding='utf-8')
    origin_log = record(agent_log)
    report_paths = list((destination / 'report').glob('*.htm'))
    if len(report_paths) != 1:
        raise RuntimeError('The preserved run must have exactly one native HTML report')
    html = NativeTables()
    html.feed(decode(report_paths[0]))
    summary_labels = defaultdict(list)
    for row in html.rows:
        for i, value in enumerate(row[:-1]):
            if value.endswith(':'):
                summary_labels[value].append(row[i + 1])
    quality = summary_labels.get('히스토리 품질:', summary_labels.get('History Quality:', []))
    native_lines = [fields(v) for v in episode_text.splitlines() if 'V7CA_NATIVE profit=' in v]
    core_lines = [fields(v) for v in episode_text.splitlines() if 'V7CA_RESULT status=' in v]
    causal_lines = [fields(v) for v in episode_text.splitlines() if 'CAUSAL_RESULT role=' in v]
    reasons = []
    if len(native_lines) != 1 or len(core_lines) != 1 or len(causal_lines) != 1:
        reasons.append('Native/core/learning completion summaries are not unique and complete')
    if not quality or not any('100%' in v and ('실제' in v or 'real' in v.lower()) for v in quality):
        reasons.append('The native report does not establish 100% real ticks')
    contracts = defaultdict(dict)
    for line in episode_text.splitlines():
        if 'V7CA_CONTRACT stage=' not in line:
            continue
        item = fields(line)
        stage = item.pop('stage')
        symbol = item.pop('symbol')
        contracts[stage][symbol] = item
    if set(contracts.get('START', {})) != {'US30', 'US100', 'US500'} or contracts.get('START') != contracts.get('END'):
        reasons.append('Complete unchanged three-symbol contract/swaps are missing')
    economic = None
    learning = None
    epochs = {}
    if len(native_lines) == len(core_lines) == len(causal_lines) == 1:
        native, core, learning = native_lines[0], core_lines[0], causal_lines[0]
        if core.get('status') != 'ECONOMIC' or int(learning['faults']) != 0 or int(learning['open']) != 0 or int(learning['mark_known']) != 1:
            reasons.append('The normal native run reports an operating/accounting fault or unfinished position')
        if core.get('status') == 'ECONOMIC':
            lifecycle = archived_own / 'research/research-lifecycles.csv'
            with lifecycle.open(encoding='utf-8-sig', newline='') as stream:
                lives = list(csv.DictReader(stream))
            births = [v for v in lives if v['event'] == 'BIRTH']
            closes = [v for v in lives if v['event'] == 'CLOSE']
            born = Counter((v['component_id'], v['position_identifier']) for v in births)
            closed = Counter((v['component_id'], v['position_identifier']) for v in closes)
            if born != closed or any(v != 1 for v in born.values()) or any(v['partial_observation'] != '0' for v in lives):
                reasons.append('Native lifecycle population is not one-to-one fully closed')
            if len(closes) != int(core['closed']):
                reasons.append('Native closed lifecycle count does not match the core total')
            for label, first in [('2024-H1', True), ('2024-H2', False)]:
                subset = [v for v in closes if (v['server_time'] < '2024.07.01') == first]
                epochs[label] = dict(closed=len(subset), actual=sum(float(v['actual_net_usd']) for v in subset),
                                     stress=sum(float(v['stressed_net_usd']) for v in subset))
            actual = float(core['actual_net'])
            stress = float(core['stressed_net'])
            conservative_stress = stress - float(learning['positive_closed_swap'])
            dd_cash = float(native['equity_dd'])
            dd_relative = float(native['equity_dd_relative_pct'])
            economic = dict(actual_net=actual, original_stressed_net=stress,
                            no_positive_swap_stressed_net=conservative_stress,
                            actual_wealth=100 + actual, original_stressed_wealth=100 + stress,
                            conservative_stressed_wealth=100 + conservative_stress,
                            native_equity_DD_cash=dd_cash, native_equity_DD_percent=dd_relative,
                            conservative_recovery=conservative_stress / max(.01, dd_cash, float(core['stressed_dd'])),
                            actual_log_growth=math.log((100 + actual) / 100) if actual > -100 else None,
                            closed_lifecycles=len(closes), native_trade_count=float(native['trades']),
                            per_component=dict(Counter(v['component_id'] for v in closes)))
            if abs(sum(float(v['actual_net_usd']) for v in closes) - actual) > 1e-5 or abs(sum(float(v['stressed_net_usd']) for v in closes) - stress) > 1e-5:
                reasons.append('Full lifecycle economics do not match core totals')
    outcome = dict(utc=datetime.now(timezone.utc).isoformat(),
                   status='COMPLETE_NATIVE_ECONOMIC_RUN_REQUIRES_MATRIX_INPUT_BINDING' if not reasons else 'CORRECTION_REQUIRED_NO_ECONOMIC_VERDICT',
                   role=role, run_tag=run_tag, reasons=reasons, economics=economic,
                   native_learning=learning, epochs=epochs, contracts=dict(contracts),
                   report_labels=dict(summary_labels), source_agent_log=origin_log,
                   archived_files=[record(p) for p in sorted(destination.rglob('*')) if p.is_file()],
                   scope='One whole native training run. No seed is selected and no improvement is claimed; all eight fixed episodes and the unchanged matrix input are required before fitting.',
                   free_bytes=shutil.disk_usage(ROOT).free, live_changes=False)
    (destination / 'NATIVE_RESULT_V1.json').write_text(json.dumps(outcome, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: outcome[k] for k in ('status', 'run_tag', 'reasons', 'economics', 'native_learning', 'epochs')}, indent=2), flush=True)


if __name__ == '__main__':
    summarize(sys.argv[1], sys.argv[2])
