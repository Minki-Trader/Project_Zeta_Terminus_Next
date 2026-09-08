"""Publish the frozen metadata census from the completed original-V7 source run."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import csv
import io
import json
from pathlib import Path
import re

from native_run import FAMILY, RAW, ref, save

TAG = 'source-2024-v1'
SOURCE = RAW / 'native' / TAG / 'files/Files/ZetaV7RC4ConsensusControl' / TAG
COMPONENT = 'ZT-M30-US30-RANGE-COMP-64efb16616'
BEGIN, END = '2024.01.01 00:00:00', '2025.01.01 00:00:00'
IDENTITY = {
    'release_id': 'OPT-V7-RC4-CONSENSUS-CONTROL-V1',
    'execution_version': 'zt-opt-v7-rc4-consensus-control-v1',
    'portfolio_id': 'ZT-OPT-V7-RC4-CONSENSUS-CONTROL-20260908',
}


def rows(path):
    data = path.read_bytes()
    encoding = 'utf-16' if data[:2] == b'\xff\xfe' else 'utf-8-sig'
    return csv.DictReader(io.StringIO(data.decode(encoding)))


def main():
    event_paths = sorted((SOURCE / 'state').glob('events-*.csv'))
    lifecycle_path = SOURCE / 'research/research-lifecycles.csv'
    paths = event_paths + [lifecycle_path]
    before = [ref(p) for p in paths]
    lifecycle_fields = ('schema', 'server_time', 'release_id', 'execution_version',
                        'portfolio_id', 'event', 'component_id', 'symbol',
                        'position_identifier', 'entry_time_server', 'direction',
                        'partial_observation', 'research_dropped_records')
    parents = defaultdict(list)
    source_events = []
    for row in rows(lifecycle_path):
        if not BEGIN <= row['server_time'] < END:
            continue
        if row['component_id'] != COMPONENT or row['event'] not in ('BIRTH', 'CLOSE'):
            continue
        item = {k: row[k] for k in lifecycle_fields}
        parents[(item['position_identifier'], item['entry_time_server'])].append(item)
    complete, rejected_parents = [], []
    for key, records in parents.items():
        births = [x for x in records if x['event'] == 'BIRTH']
        closes = [x for x in records if x['event'] == 'CLOSE']
        reason = None
        if len(births) != 1 or len(closes) != 1:
            reason = 'BIRTH_CLOSE_NOT_ONE_TO_ONE'
        elif any(x['schema'] != 'zeta-next-v7r-rlo1-observation-v1'
                 or any(x[k] != v for k, v in IDENTITY.items())
                 or x['symbol'] != 'US30' or x['direction'] not in ('-1', '1')
                 or x['partial_observation'] != '0' or x['research_dropped_records'] != '0'
                 for x in records):
            reason = 'INVALID_IDENTITY_OR_PARTIAL_DROPPED_METADATA'
        elif births[0]['direction'] != closes[0]['direction'] or not (
                key[1] <= births[0]['server_time'] < closes[0]['server_time']):
            reason = 'INVALID_LIFECYCLE_ORDER_OR_DIRECTION'
        if reason:
            rejected_parents.append({'key': key, 'reason': reason, 'records': records})
        else:
            complete.append({'key': key, 'birth': births[0], 'close': closes[0]})
    for path in event_paths:
        for number, row in enumerate(rows(path), 2):
            if not BEGIN <= row['server_time'] < END:
                continue
            item = {k: row[k] for k in ('server_time', 'event', 'schema_version',
                                        'release_id', 'execution_version', 'portfolio_id', 'component_id')}
            item['line'] = number
            item['source'] = path.name
            if item['event'] == 'ARC_CHECKPOINT' and item['component_id'] == COMPONENT:
                # The full detail also contains numeric price-derived heads: never decode those fields.
                held = re.search(r'(?:^|\s)held=(\d+)(?:\s|$)', row['detail'])
                votes = re.search(r'(?:^|\s)votes=(-?\d+)/(-?\d+)/(-?\d+)(?:\s|$)', row['detail'])
                item['held'] = int(held[1]) if held else None
                item['votes'] = [int(votes[i]) for i in (1, 2, 3)] if votes else None
                item['recorded_vote_sum'] = row['value_a']
            source_events.append(item)
    eligible, excluded, seen = [], [], set()
    for item in source_events:
        if item['event'] != 'ARC_CHECKPOINT' or item['component_id'] != COMPONENT:
            continue
        reason = None
        if item['schema_version'] != 'RC4C1CONTROL' or any(item[k] != v for k, v in IDENTITY.items()):
            reason = 'INVALID_CORE_IDENTITY'
        elif item['held'] is None or item['held'] < 8 or item['votes'] is None or any(v not in (-1, 0, 1) for v in item['votes']):
            reason = 'INVALID_OR_EARLY_ORDINAL_DECISION'
        elif Decimal(item['recorded_vote_sum']) != sum(item['votes']):
            reason = 'INVALID_RECORDED_VOTE_SUM'
        matches = [p for p in complete if p['birth']['server_time'] <= item['server_time'] < p['close']['server_time']]
        if reason is None and len(matches) != 1:
            reason = 'NO_UNIQUE_STRICT_BIRTH_CHECKPOINT_CLOSE_JOIN'
        if reason is None and matches[0]['key'] in seen:
            reason = 'DUPLICATE_LIFECYCLE_DECISION'
        if reason:
            excluded.append({**item, 'reason': reason, 'matching_keys': [p['key'] for p in matches]})
            continue
        parent = matches[0]
        seen.add(parent['key'])
        eligible.append({**item, 'position_identifier': parent['key'][0],
                         'entry_time_server': parent['key'][1], 'direction': int(parent['birth']['direction']),
                         'birth': parent['birth']['server_time'], 'close': parent['close']['server_time'],
                         'half': 'H1' if item['server_time'] < '2024.07.01' else 'H2',
                         'nonunanimous': len(set(item['votes'])) > 1})
    halves = Counter(x['half'] for x in eligible)
    directions = Counter('long' if x['direction'] == 1 else 'short' for x in eligible)
    patterns = Counter('/'.join(str(v) for v in x['votes']) for x in eligible)
    disagreements = Counter(x['half'] for x in eligible if x['nonunanimous'])
    gates = {
        'eligible_at_least_48': len(eligible) >= 48,
        'each_half_at_least_16': all(halves[h] >= 16 for h in ('H1', 'H2')),
        'each_direction_at_least_12': all(directions[d] >= 12 for d in ('long', 'short')),
        'patterns_at_least_6': len(patterns) >= 6,
        'nonunanimous_at_least_24': sum(disagreements.values()) >= 24,
        'nonunanimous_each_half_at_least_8': all(disagreements[h] >= 8 for h in ('H1', 'H2')),
    }
    after = [ref(p) for p in paths]
    if before != after:
        raise RuntimeError('Source changed during completed-result publication')
    result = {'utc': datetime.now(timezone.utc).isoformat(),
              'status': 'SOURCE_READY_FOR_PROSPECTIVE_MODEL_DECLARATION' if all(gates.values()) else 'COMPLETE_SOURCE_UNREADY_NO_MODEL',
              'report_source': ref(Path(__file__).resolve()),
              'declaration': ref(FAMILY / 'evidence/DECLARATION_V1.json'),
              'completed_native_attempt': ref(RAW / 'native' / TAG / 'complete.json'),
              'sources_before': before, 'sources_after': after,
              'source_events': len(source_events), 'first_event': source_events[0], 'last_event': source_events[-1],
              'event_counts': dict(Counter(x['event'] for x in source_events)),
              'complete_rc4_parents': len(complete), 'rejected_parents': rejected_parents,
              'eligible': len(eligible), 'half_counts': dict(halves), 'direction_counts': dict(directions),
              'ordinal_patterns': dict(sorted(patterns.items())), 'nonunanimous': sum(disagreements.values()),
              'nonunanimous_halves': dict(disagreements), 'gates': gates,
              'eligible_metadata': eligible, 'excluded': excluded,
              'interpretation': 'Actual complete original2024 metadata supply only. No target, model, candidate economics, growth or restart claim. Original fixed readiness gates remain unchanged.'}
    target = FAMILY / 'evidence/COMPLETE_SOURCE_METADATA_RESULT_V1.json'
    save(target, result)
    print(json.dumps({k: result[k] for k in ('status', 'eligible', 'half_counts', 'direction_counts',
                    'nonunanimous', 'nonunanimous_halves', 'gates')}, indent=2))
    print('PATTERNS', len(patterns), 'EXCLUDED', len(excluded), 'BAD_PARENTS', len(rejected_parents))


if __name__ == '__main__':
    main()
