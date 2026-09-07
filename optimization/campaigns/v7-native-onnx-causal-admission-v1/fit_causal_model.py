"""Fit the fixed causal-effect ONNX coefficient state from all native episodes."""
from pathlib import Path
import csv
import hashlib
import json
from datetime import datetime, timezone

import numpy as np

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / 'optimization/artifacts/raw/v7-native-onnx-causal-admission-v1'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest().upper()


def native_time(value):
    # MQL datetime-to-string preserves the native server-wall label. UTC here
    # only encodes that unshifted calendar label as the same scalar clock used
    # for period boundaries; it does not assert a physical UTC bridge.
    return int(datetime.strptime(value, '%Y.%m.%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())


def fit():
    result_path = FAMILY / 'evidence/INITIAL_CAUSAL_FIT_V1.json'
    if result_path.exists():
        raise RuntimeError('The fixed fit is already recorded')
    contract = json.loads((FAMILY / 'evidence/TRAINING_MATRIX_COMPLETION_V1.json').read_text(encoding='utf-8'))
    if contract['status'] != 'COMPLETE_VALID_UNCHANGED_CONTROL_AND_ALL_EIGHT_NATIVE_TRAINING_TRAJECTORIES':
        raise RuntimeError('The complete native training matrix is not ready')
    samples = []
    sources = []
    counts = np.zeros((5, 2), dtype=int)
    limit = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
    for episode in range(1, 9):
        run = RAW / 'training' / ('episode-%02d' % episode)
        files = list(run.rglob('learning/decisions.csv'))
        if len(files) != 1:
            raise RuntimeError('An episode must have exactly one own decision ledger')
        decisions_path = files[0]
        labels_path = decisions_path.with_name('labels.csv')
        sources.extend(dict(path=p.relative_to(ROOT).as_posix(), sha256=digest(p), bytes=p.stat().st_size)
                       for p in (decisions_path, labels_path))
        with decisions_path.open(encoding='utf-8-sig', newline='') as stream:
            decisions = {int(v['id']): v for v in csv.DictReader(stream)}
        with labels_path.open(encoding='utf-8-sig', newline='') as stream:
            labels = list(csv.DictReader(stream))
        for label in labels:
            available = native_time(label['available'])
            if available >= limit:
                continue
            row = decisions[int(label['id'])]
            raw = np.array([float(v) for v in row['raw'].split(';')], dtype=float)
            if raw.shape != (16,) or not np.isfinite(raw).all():
                raise RuntimeError('Native context schema')
            action = int(row['action'])
            propensity = float(row['propensity'])
            decision = native_time(row['decision'])
            if action not in (0, 1) or propensity != .5 or available <= decision:
                raise RuntimeError('Native treatment/availability contract')
            component = int(np.argmax(raw[:5]))
            counts[component, action] += 1
            samples.append(dict(episode=episode, id=int(row['id']), decision=decision,
                                available=available, action=action, propensity=propensity,
                                reward=float(label['reward']), raw=raw.tolist()))
    if len(samples) < 512 or np.min(counts) < 32:
        result = dict(status='FIT_READINESS_NONCONFIRMATION', labels=len(samples), counts=counts.tolist(),
                      sources=sources, model=None, candidate_2026_opened=False)
        result_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2))
        return
    raw = np.array([v['raw'] for v in samples])
    y = np.array([v['reward'] for v in samples])
    a = np.array([v['action'] for v in samples])
    if not np.isfinite(y).all():
        raise RuntimeError('Native economic reward is not finite')
    mean = raw.mean(axis=0)
    std = raw.std(axis=0)
    std[std < 1e-12] = 1
    x = np.column_stack([np.ones(len(raw)), (raw - mean) / std])
    gram = x.T @ x
    beta = np.linalg.solve(gram + 10 * np.eye(17), x.T @ y)
    z = (a - .5) * (y - x @ beta) / .25
    inverse = np.linalg.inv(gram + 100 * np.eye(17))
    theta = inverse @ (x.T @ z)
    state = dict(mean=mean.tolist(), std=std.tolist(), baseline=beta.tolist(), effect=theta.tolist(),
                 covariance=inverse.tolist(), gram=gram.tolist(), baseline_rhs=(x.T @ y).tolist(),
                 effect_rhs=(x.T @ z).tolist(), counts=counts.tolist(), labels=len(samples))
    models = FAMILY / 'models'
    state_path = models / 'initial-causal-state.json'
    if state_path.exists():
        raise RuntimeError('Initial model state is immutable')
    state_path.write_text(json.dumps(state, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    header = '#ifndef ZETA_CAUSAL_PARAMETERS_MQH\n#define ZETA_CAUSAL_PARAMETERS_MQH\nconst bool CAUSAL_FIT_READY=true;\n'
    for name, values in [('MEAN', mean), ('SD', std), ('BASELINE', beta), ('EFFECT', theta), ('COVARIANCE', inverse.ravel())]:
        header += 'const double CAUSAL_INITIAL_' + name + '[' + str(len(values)) + ']={' + ','.join(format(v, '.17g') for v in values) + '};\n'
    header += '#endif\n'
    # Learned constants are installed only in the learner. The exact control
    # retains its original inert observer constants and no learned decisions.
    parameters = FAMILY / 'learner/MQL5/Include/ZetaV7CALearner/Learning/ZetaCausalParameters.mqh'
    parameters.write_text(header, encoding='utf-8')
    sample_path = RAW / 'training/complete-fit-labels.json'
    sample_path.write_text(json.dumps(samples, allow_nan=False) + '\n', encoding='utf-8')
    result = dict(utc=datetime.now(timezone.utc).isoformat(), status='FIXED_ALL_EIGHT_NATIVE_CAUSAL_FIT_COMPLETE',
                  labels=len(samples), counts=counts.tolist(), sources=sources,
                  initial_state_sha256=digest(state_path), own_graph_sha256=digest(models / 'causal-effect.onnx'),
                  all_fit_labels_sha256=digest(sample_path), beta=beta.tolist(), theta=theta.tolist(),
                  candidate_2026_opened=False, live_changes=False)
    result_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    fit()
