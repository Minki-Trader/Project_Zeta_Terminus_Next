"""Fit and export the declared original-V7 input-density models and calibration."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import onnxruntime as ort

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
RAW = ROOT / 'optimization/artifacts/raw/v7-native-input-density-admission-v1'
SOURCE = ROOT / 'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-candidates.csv'
SOURCE_SHA = 'E48CF89502D259E94F9245572852315BAE3AB68F70CB87FA71CE9D23462B02BD'
COMPONENTS = [
    'ZT-M30-US30-RANGE-COMP-61f61deaba',
    'ZT-M30-US30-RANGE-COMP-64efb16616',
    'ZT-H1-US100-CROSS-IN-14b72317b7',
    'ZT-M30-US30-INTRADAY-R-2eb111fc46',
    'ZT-H1-US30-RETURN-I-c870a788ec',
    'ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8',
]
IDENTITY = {
    'schema': 'zeta-next-v7r-rlo1-observation-v1',
    'release_id': 'NEXT-E03-V7R-RLO1-0bba2ca045fe',
    'execution_version': 'zt-next-v7-rlo1-return-portfolio-v1',
    'portfolio_id': 'ZT-PORT-NEXT-V7R-RLO1-20260907',
}


def ref(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest().upper()}


def save(path, value):
    if path.exists():
        raise RuntimeError('Retain existing artifact: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def responsibilities(z, weights, means, variances):
    logs = np.log(weights) - .5 * (np.log(2*np.pi*variances) + (z[:, None]-means)**2/variances)
    shifted = np.exp(logs-logs.max(axis=1, keepdims=True))
    return shifted/shifted.sum(axis=1, keepdims=True)


def fit(z):
    weights, means, variances = np.array([.5, .5]), np.quantile(z, [.25, .75]), np.ones(2)
    initial = {'weights': weights.tolist(), 'means': means.tolist(), 'variances': variances.tolist()}
    for _ in range(64):
        resp = responsibilities(z, weights, means, variances)
        mass = resp.sum(axis=0)
        if np.any(mass <= 0) or not np.all(np.isfinite(mass)):
            raise RuntimeError('Invalid declared EM mass requires input/engineering correction')
        weights = np.maximum(.05, mass/len(z))
        weights /= weights.sum()
        means = (resp*z[:, None]).sum(axis=0)/mass
        variances = np.maximum(.01, (resp*(z[:, None]-means)**2).sum(axis=0)/mass)
    return initial, weights, means, variances


def export_graph(path):
    constants = [numpy_helper.from_array(np.array([2, 2, 2], dtype=np.int64), 'parts'),
                 numpy_helper.from_array(np.array([1], dtype=np.int64), 'sum_axis'),
                 numpy_helper.from_array(np.array([math.log(2*math.pi)], dtype=np.float32), 'log2pi'),
                 numpy_helper.from_array(np.array([.5], dtype=np.float32), 'half')]
    nodes = [helper.make_node('Split', ['parameters', 'parts'], ['w', 'mu', 'var'], axis=1),
             helper.make_node('Sub', ['z', 'mu'], ['delta']),
             helper.make_node('Mul', ['delta', 'delta'], ['squared']),
             helper.make_node('Div', ['squared', 'var'], ['quadratic']),
             helper.make_node('Log', ['var'], ['logvar']),
             helper.make_node('Add', ['logvar', 'log2pi'], ['normalizer']),
             helper.make_node('Add', ['normalizer', 'quadratic'], ['energy']),
             helper.make_node('Mul', ['energy', 'half'], ['half_energy']),
             helper.make_node('Log', ['w'], ['logweight']),
             helper.make_node('Sub', ['logweight', 'half_energy'], ['logterms']),
             helper.make_node('ReduceMax', ['logterms'], ['maximum'], axes=[1], keepdims=1),
             helper.make_node('Sub', ['logterms', 'maximum'], ['shifted']),
             helper.make_node('Exp', ['shifted'], ['expterms']),
             helper.make_node('ReduceSum', ['expterms', 'sum_axis'], ['total'], keepdims=1),
             helper.make_node('Div', ['expterms', 'total'], ['responsibilities']),
             helper.make_node('Log', ['total'], ['logtotal']),
             helper.make_node('Add', ['maximum', 'logtotal'], ['logdensity']),
             helper.make_node('Neg', ['logdensity'], ['negative_log_density'])]
    graph = helper.make_graph(nodes, 'V7OriginalFeatureDensity',
        [helper.make_tensor_value_info('z', TensorProto.FLOAT, [1, 1]),
         helper.make_tensor_value_info('parameters', TensorProto.FLOAT, [1, 6])],
        [helper.make_tensor_value_info('negative_log_density', TensorProto.FLOAT, [1, 1]),
         helper.make_tensor_value_info('responsibilities', TensorProto.FLOAT, [1, 2])], constants)
    model = helper.make_model(graph, producer_name='V7InputDensityAdmission',
                              opset_imports=[helper.make_opsetid('', 17)], ir_version=8)
    if path.exists():
        raise RuntimeError('Preserve previously exported graph')
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, path)


def main():
    if shutil.disk_usage(ROOT).free < 38*2**30 + 32*2**20:
        raise RuntimeError('Complete prospective storage envelope is not funded')
    target = RAW / 'input/original-v7-candidates.csv'
    source_ref = ref(SOURCE)
    if source_ref['sha256'] != SOURCE_SHA:
        raise RuntimeError('Original input identity changed')
    if target.exists():
        raise RuntimeError('The one-time original input copy already exists')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, target)
    if ref(target)['sha256'] != SOURCE_SHA or ref(SOURCE) != source_ref:
        raise RuntimeError('Original input copy changed')
    save(FAMILY/'evidence/ORIGINAL_INPUT_COPY_V1.json', {'utc': datetime.now(timezone.utc).isoformat(),
         'source': source_ref, 'copy': ref(target), 'source_identity': IDENTITY})
    observations, exclusions, duplicate_count = {}, Counter(), 0
    with target.open(encoding='utf-8-sig', newline='') as stream:
        for line, row in enumerate(csv.DictReader(stream), 2):
            timestamp = row['server_time']
            if not '2024.01.01 00:00:00' <= timestamp < '2025.01.01 00:00:00':
                continue
            if any(row[k] != v for k, v in IDENTITY.items()):
                raise RuntimeError('Original2024row identity differs')
            if row['stage'] not in ('SIGNAL', 'OUTCOME') or row['signal_known'] != '1':
                exclusions['unknown_or_noncomputed_stage'] += 1
                continue
            if row['research_dropped_records'] != '0':
                raise RuntimeError('Original known-feature source has dropped records')
            component = row['component_id']
            if component not in COMPONENTS:
                raise RuntimeError('Unexpected original component identity: ' + component)
            feature = float(row['feature'])
            if not math.isfinite(feature):
                raise RuntimeError('Nonfinite known original feature')
            item = {'source_line': line, 'server_time': timestamp, 'component_id': component,
                    'decision_bar': row['decision_bar'], 'feature': feature,
                    'signal_passed': int(row['signal_passed']), 'direction': int(row['direction'])}
            if item['signal_passed'] not in (0, 1) or item['direction'] not in (-1, 0, 1):
                raise RuntimeError('Invalid known signal metadata')
            key = (component, item['decision_bar'])
            if key in observations:
                old = observations[key]
                if any(item[k] != old[k] for k in ('feature', 'signal_passed', 'direction')):
                    raise RuntimeError('Conflicting duplicate feature decision')
                duplicate_count += 1
                if timestamp < old['server_time']:
                    observations[key] = item
            else:
                observations[key] = item
    population = sorted(observations.values(), key=lambda x: (x['server_time'], COMPONENTS.index(x['component_id']), x['decision_bar']))
    counts = {}
    for component in COMPONENTS:
        first = [x for x in population if x['component_id'] == component and x['server_time'] < '2024.07.01']
        second = [x for x in population if x['component_id'] == component and x['server_time'] >= '2024.07.01']
        counts[component] = {'fit': len(first), 'calibration': len(second),
                             'distinct_fit': len(set(x['feature'] for x in first))}
    enough = all(x['fit'] >= 64 and x['calibration'] >= 64 and x['distinct_fit'] >= 16 for x in counts.values())
    save(FAMILY/'evidence/SOURCE_READINESS_V1.json', {'utc': datetime.now(timezone.utc).isoformat(),
         'status': 'SOURCE_READY' if enough else 'COMPLETE_SOURCE_UNREADY', 'input': ref(target),
         'counts': counts, 'exclusions': dict(exclusions), 'identical_duplicates': duplicate_count,
         'unique_observations': len(population), 'outcome_fields_read': False,
         'source_unchanged': ref(target)['sha256'] == SOURCE_SHA and ref(SOURCE) == source_ref})
    print('SOURCE_COUNTS', json.dumps(counts), flush=True)
    if not enough:
        print('COMPLETE_SOURCE_UNREADY_NO_FIT', flush=True)
        return
    dataset = RAW / 'fit/observed-2024.jsonl'
    dataset.parent.mkdir(parents=True, exist_ok=True)
    with dataset.open('x', encoding='utf-8') as stream:
        for row in population:
            stream.write(json.dumps(row) + '\n')
    graph_path = FAMILY/'models/input_density_v1.onnx'
    export_graph(graph_path)
    session = ort.InferenceSession(str(graph_path), providers=['CPUExecutionProvider'])
    models, calibration_rows = [], []
    for index, component in enumerate(COMPONENTS):
        first = [x for x in population if x['component_id'] == component and x['server_time'] < '2024.07.01']
        second = [x for x in population if x['component_id'] == component and x['server_time'] >= '2024.07.01']
        features = np.array([x['feature'] for x in first])
        transformed = np.sign(features)*np.log1p(np.abs(features))
        mean, scale = float(transformed.mean()), float(transformed.std())
        if scale <= 1e-12:
            raise RuntimeError('Complete original feature is constant under declared transform')
        z = (transformed-mean)/scale
        initial, weights, means, variances = fit(z)
        parameters = np.concatenate((weights, means, variances)).astype(np.float32).reshape(1, 6)
        scores = []
        for row in second:
            x = math.copysign(math.log1p(abs(row['feature'])), row['feature'])
            input_z = np.array([[(x-mean)/scale]], dtype=np.float32)
            score, response = session.run(None, {'z': input_z, 'parameters': parameters})
            value = float(score[0, 0])
            if not math.isfinite(value) or not np.all(np.isfinite(response)):
                raise RuntimeError('Nonfinite ordinary ONNX calibration inference')
            scores.append(value)
            calibration_rows.append({'component': index, 'source_line': row['source_line'],
                                     'server_time': row['server_time'], 'score': value})
        rank = math.ceil(.95*len(scores))
        threshold = sorted(scores)[rank-1]
        models.append({'index': index, 'component_id': component, 'fit_count': len(first),
            'calibration_count': len(second), 'mean': mean, 'scale': scale, 'initial_EM': initial,
            'weights': weights.tolist(), 'means': means.tolist(), 'variances': variances.tolist(),
            'float32_parameters': parameters.ravel().tolist(), 'cutoff': threshold, 'cutoff_rank': rank,
            'initial_N': weights.tolist(), 'initial_S': (weights*means).tolist(),
            'initial_Q': (weights*(variances+means**2)).tolist()})
    scores_path = RAW/'fit/calibration-scores-2024H2.json'
    save(scores_path, calibration_rows)
    fit_path = FAMILY/'models/initial_fit_v1.json'
    save(fit_path, {'utc': datetime.now(timezone.utc).isoformat(),
         'status': 'DECLARED_INPUT_DENSITY_FIT_AND_CALIBRATION_COMPLETE_NO_ECONOMICS',
         'declaration': ref(FAMILY/'evidence/DECLARATION_V1.json'), 'producer': ref(Path(__file__).resolve()),
         'original_input': ref(target), 'observations': ref(dataset), 'calibration_scores': ref(scores_path),
         'onnx': ref(graph_path), 'components': models, 'online_eta': 1/64,
         'versions': {'numpy': np.__version__, 'onnx': onnx.__version__, 'onnxruntime': ort.__version__},
         'limitations': 'Observed original feature-density fit/calibration only, not a profit or causal-treatment model. No2025candidate or2026values used; all economic gates remain open.'})
    save(FAMILY/'evidence/FIT_PUBLICATION_V1.json', {'utc': datetime.now(timezone.utc).isoformat(),
         'status': 'READY_FOR_FRESH_NATIVE_IMPLEMENTATION', 'source_readiness': ref(FAMILY/'evidence/SOURCE_READINESS_V1.json'),
         'fit': ref(fit_path), 'graph': ref(graph_path), 'source_after': ref(SOURCE),
         'copy_after': ref(target), 'free_bytes': shutil.disk_usage(ROOT).free})
    print('FIT_COMPLETE', len(models), ref(fit_path)['sha256'], flush=True)


if __name__ == '__main__':
    main()
