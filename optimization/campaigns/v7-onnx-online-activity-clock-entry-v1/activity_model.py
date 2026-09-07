"""Own historical input, fixed HMM production and quote-path selection.

This normal research producer does not operate a terminal, query broker state,
execute an EA or claim native account economics from its M1 quote approximation.
"""
from collections import deque, Counter
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math
import shutil
import sys
import numpy as np
import onnx
from onnx import helper, TensorProto
import onnxruntime as ort
from scipy.special import logsumexp

FAMILY = Path(__file__).resolve().parent
ROOT = FAMILY.parents[2]
RAW = ROOT / 'optimization/artifacts/raw/v7-onnx-online-activity-clock-entry-v1'
EVIDENCE = FAMILY / 'evidence'
MODEL = FAMILY / 'models'
MARKET_SOURCE = ROOT / 'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/market-before-control/US100-M1.npy'
LIFE_SOURCE = ROOT / 'lab/artifacts/raw/v7-rlo1-return-requalification-v1/long/candidate-final/Files/research/research-lifecycles.csv'
PASSIVE = 'ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8'


def epoch(label):
    return int(datetime.fromisoformat(label).replace(tzinfo=timezone.utc).timestamp())


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest().upper()


def save_json(path, value):
    if path.exists():
        raise RuntimeError('Production artifact already exists: ' + str(path))
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def reserve():
    if shutil.disk_usage(ROOT).free < 30 * 1024**3 + 384 * 1024**2:
        raise RuntimeError('Storage reserve')


def prepare():
    reserve()
    dest = RAW / 'input'
    dest.mkdir(parents=True, exist_ok=False)
    expected = {MARKET_SOURCE: 'EF5DEA36AF11B67B6C34D79BADD713E1F9167A0009D10A5AFB01AACF46ED856B',
                LIFE_SOURCE: '6455361C78BF9227247860E85CB01C0A611CE725E636C28082ED8B505529B78B'}
    for path, value in expected.items():
        if sha(path) != value:
            raise RuntimeError('Original input binding changed: ' + str(path))
    original = np.load(MARKET_SOURCE, mmap_mode='r', allow_pickle=False)
    times = original['time']
    left = np.searchsorted(times, epoch('2023-11-01'))
    right = np.searchsorted(times, epoch('2026-01-01'))
    own = np.array(original[left:right], copy=True)
    np.save(dest / 'US100-M1.npy', own, allow_pickle=False)
    with LIFE_SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        names = reader.fieldnames
        rows = [row for row in reader if row['component_id'] == PASSIVE and
                row['event'] in ('BIRTH', 'CLOSE') and
                '2025.01.01' <= row['entry_time_server'] < '2026.01.01']
    with (dest / 'original-passive-2025.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, names)
        writer.writeheader()
        writer.writerows(rows)
    for path, value in expected.items():
        if sha(path) != value:
            raise RuntimeError('Source changed during physical copy')
    receipt = dict(utc=datetime.now(timezone.utc).isoformat(), status='COMPLETE_ORIGINAL_INPUT_COPY_BEFORE_FEATURES',
                   source_hashes={p.relative_to(ROOT).as_posix(): v for p, v in expected.items()},
                   rows=len(own), first=int(own['time'][0]), last=int(own['time'][-1]), lifecycle_rows=len(rows),
                   files=[dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p)) for p in dest.iterdir()],
                   free_bytes=shutil.disk_usage(ROOT).free, live_changes=False)
    save_json(EVIDENCE / 'INPUT_COPY_V1.json', receipt)
    print(json.dumps(receipt, indent=2), flush=True)


def buckets(rates):
    times = rates['time']
    if np.any(np.diff(times) <= 0) or np.any(rates['low'] <= 0) or np.any(rates['high'] < rates['low']) or np.any(rates['spread'] < 0):
        raise RuntimeError('Original source ordering/price fault')
    day_values = times // 86400
    starts = np.r_[0, np.flatnonzero(np.diff(day_values)) + 1]
    ends = np.r_[starts[1:], len(times)]
    past_day_volume, past_ranges = deque(maxlen=20), deque(maxlen=20)
    result, calendar = [], []
    for start, end in zip(starts, ends):
        day = int(day_values[start])
        total_volume = int(np.sum(rates['tick_volume'][start:end], dtype=np.uint64))
        item = dict(day=day, rows=int(end-start), total_volume=total_volume, target=None, completed=0, remainder_rows=0, missing_prefix=0)
        if len(past_day_volume) == 20:
            target = max(1, math.ceil(float(np.median(past_day_volume)) / 48))
            item['target'] = target
            cumulative = np.cumsum(rates['tick_volume'][start:end], dtype=np.uint64)
            cursor, consumed = int(start), 0
            while cursor < end:
                last = int(start + np.searchsorted(cumulative, consumed + target, side='left'))
                if last >= end:
                    item['remainder_rows'] = int(end-cursor)
                    break
                sub = rates[cursor:last+1]
                high, low = float(np.max(sub['high'])), float(np.min(sub['low']))
                opening, closing = float(sub['open'][0]), float(sub['close'][-1])
                volume = int(np.sum(sub['tick_volume'], dtype=np.uint64))
                impact = np.sign(np.diff(sub['close'], prepend=opening))
                imbalance = float(np.sum(impact * sub['tick_volume']) / max(1, volume))
                available = int(times[last]) + 60
                duration = (available-int(times[cursor])) / 60
                scale = max(.01, float(np.median(past_ranges))) if len(past_ranges) == 20 else None
                row = dict(day=day, D=available, first=int(times[cursor]), last=int(times[last]),
                           rows=int(last-cursor+1), open=opening, close=closing, high=high, low=low,
                           volume=volume, target=target, scale=scale,
                           spread=.01*int(sub['spread'][-1]), duration=duration,
                           x=None if scale is None else [math.log1p(duration), (closing-opening)/scale, imbalance])
                result.append(row)
                item['completed'] += 1
                item['missing_prefix'] += scale is None
                past_ranges.append(high-low)
                consumed = int(cumulative[last-start])
                cursor = last+1
        else:
            item['remainder_rows'] = int(end-start)
        calendar.append(item)
        past_day_volume.append(total_volume)
    return result, calendar


def emissions(x, means, variances):
    return -.5 * np.sum(np.log(2*np.pi*variances)[None, :, :] +
                        (x[:, None, :] - means[None, :, :])**2 / variances[None, :, :], axis=2)


def fit_hmm(x, days):
    groups = np.array_split(np.argsort(x[:, 1], kind='stable'), 3)
    means = np.array([x[group].mean(axis=0) for group in groups])
    variances = np.tile(np.maximum(.05, x.var(axis=0)), (3, 1))
    transition = np.full((3, 3), .1)
    np.fill_diagonal(transition, .8)
    cuts = np.r_[0, np.flatnonzero(np.diff(days)) + 1, len(days)]
    likelihoods = []
    for iteration in range(20):
        occupancy, first_moment, second_moment = np.zeros(3), np.zeros((3,3)), np.zeros((3,3))
        counts, total_likelihood = np.zeros((3,3)), 0.
        log_a = np.log(transition)
        for left, right in zip(cuts[:-1], cuts[1:]):
            seq = x[left:right]
            emit = emissions(seq, means, variances)
            forward = np.empty((len(seq),3)); backward = np.zeros((len(seq),3))
            forward[0] = -math.log(3) + emit[0]
            for t in range(1, len(seq)):
                forward[t] = emit[t] + logsumexp(forward[t-1, :, None] + log_a, axis=0)
            likelihood = float(logsumexp(forward[-1]))
            for t in range(len(seq)-2, -1, -1):
                backward[t] = logsumexp(log_a + emit[t+1][None,:] + backward[t+1][None,:], axis=1)
            gamma = np.exp(forward + backward - likelihood)
            occupancy += gamma.sum(axis=0)
            first_moment += gamma.T @ seq
            second_moment += gamma.T @ (seq**2)
            for t in range(len(seq)-1):
                counts += np.exp(forward[t,:,None] + log_a + emit[t+1][None,:] + backward[t+1][None,:] - likelihood)
            total_likelihood += likelihood
        means = np.clip(first_moment / np.maximum(1e-12, occupancy[:,None]), -6, 6)
        variances = np.maximum(.05, second_moment / np.maximum(1e-12, occupancy[:,None]) - means**2)
        transition = (counts+1) / (counts+1).sum(axis=1, keepdims=True)
        if not all(np.isfinite(v).all() for v in (means, variances, transition)):
            raise RuntimeError('HMM fit arithmetic fault')
        likelihoods.append(total_likelihood)
        print(json.dumps(dict(fit_pass=iteration+1, log_likelihood=total_likelihood)), flush=True)
    return means, variances, transition, likelihoods


def make_graph(path):
    inputs = [helper.make_tensor_value_info(name, TensorProto.FLOAT, shape) for name, shape in
              [('x',[1,3]), ('means',[3,3]), ('variances',[3,3]), ('prior',[1,3])]]
    output = helper.make_tensor_value_info('posterior', TensorProto.FLOAT, [1,3])
    tensors = [helper.make_tensor('axes', TensorProto.INT64, [1], [1]),
               helper.make_tensor('negative_half', TensorProto.FLOAT, [], [-.5])]
    nodes = [helper.make_node('Sub',['x','means'],['delta']),
             helper.make_node('Mul',['delta','delta'],['square']),
             helper.make_node('Div',['square','variances'],['quadratic']),
             helper.make_node('Log',['variances'],['log_var']),
             helper.make_node('Add',['quadratic','log_var'],['terms']),
             helper.make_node('ReduceSum',['terms','axes'],['sum_terms'],keepdims=0),
             helper.make_node('Mul',['sum_terms','negative_half'],['log_emission']),
             helper.make_node('Log',['prior'],['log_prior']),
             helper.make_node('Add',['log_emission','log_prior'],['log_joint']),
             helper.make_node('Softmax',['log_joint'],['posterior'],axis=1)]
    model = helper.make_model(helper.make_graph(nodes,'ActivityClockGaussianFilter',inputs,[output],tensors),
                              opset_imports=[helper.make_opsetid('',17)], producer_name='own-activity-clock')
    model.ir_version = 8
    onnx.save(model, path)


def forecast_role(role, events, initial, session, dest):
    means, variances, transition = [np.array(initial[k], dtype=float) for k in ('means','variances','transition')]
    feature_mean, feature_std = np.array(initial['feature_mean']), np.array(initial['feature_std'])
    mass = np.full(3, 1/3)
    first = mass[:,None] * means
    second = mass[:,None] * (variances+means**2)
    transitions = transition / 3
    previous, previous_day, pending = np.full(3,1/3), None, None
    rows, updates, observation_log_likelihood = [], 0, 0.
    with (dest / (role+'-forecasts.csv')).open('w',encoding='utf-8',newline='') as handle:
        names = ['D','source_day','scale','spread','prediction_points','direction','eligible','p0','p1','p2','updates','used_label_end_max','observation_log_likelihood']
        writer = csv.DictWriter(handle,names); writer.writeheader()
        update_end = 0
        for event in events:
            D, day = event['D'], event['day']
            if event['x'] is None:
                raise RuntimeError('2025 incomplete scale prefix retained; input correction required')
            if role == 'online' and pending is not None:
                if pending['D'] >= D:
                    raise RuntimeError('Non-strict online observation ordering')
                gamma, x0 = pending['gamma'], pending['x']
                mass = .995*mass + .005*gamma
                first = .995*first + .005*gamma[:,None]*x0
                second = .995*second + .005*gamma[:,None]*(x0**2)
                if pending['xi'] is not None:
                    transitions = .995*transitions + .005*pending['xi']
                means = np.clip(first/np.maximum(1e-12,mass[:,None]),-6,6)
                variances = np.maximum(.05,second/np.maximum(1e-12,mass[:,None])-means**2)
                transition = (transitions+1e-6)/(transitions+1e-6).sum(axis=1,keepdims=True)
                updates += 1; update_end = pending['D']
            x = np.clip((np.array(event['x'])-feature_mean)/feature_std,-6,6)
            same_day = previous_day == day
            prior = previous @ transition if same_day else np.full(3,1/3)
            prior = np.maximum(1e-12,prior); prior /= prior.sum()
            log_likelihood = float(logsumexp(emissions(x[None,:],means,variances)[0]+np.log(prior)))
            observation_log_likelihood += log_likelihood
            posterior = session.run(None, {'x':x.astype(np.float32)[None,:],
                'means':means.astype(np.float32),'variances':variances.astype(np.float32),
                'prior':prior.astype(np.float32)[None,:]})[0][0].astype(float)
            if not np.isfinite(posterior).all() or posterior.min()<0 or posterior.sum()<=0:
                raise RuntimeError('ONNX filter arithmetic fault')
            posterior /= posterior.sum()
            xi = previous[:,None] * transition * (posterior/prior)[None,:] if same_day else None
            if xi is not None: xi /= xi.sum()
            impact_means = means[:,1]*feature_std[1] + feature_mean[1]
            predicted = float((posterior @ transition) @ impact_means * event['scale'])
            direction = int(np.sign(predicted)) if abs(predicted)>2*max(.01,event['spread']) else 0
            eligible = 8*3600 <= D%86400 < 21*3600
            row = dict(D=D,source_day=day,scale=event['scale'],spread=event['spread'],prediction_points=predicted,
                       direction=direction,eligible=int(eligible),p0=posterior[0],p1=posterior[1],p2=posterior[2],
                       updates=updates,used_label_end_max=update_end,observation_log_likelihood=log_likelihood)
            writer.writerow(row); rows.append(row)
            previous, previous_day = posterior, day
            pending = dict(D=D,gamma=posterior.copy(),x=x.copy(),xi=xi) if role=='online' else None
    state = dict(means=means.tolist(),variances=variances.tolist(),transition=transition.tolist(),updates=updates,
                 last_day=previous_day,last_posterior=previous.tolist(),pending_end=None if pending is None else pending['D'],
                 pending_observation=None if pending is None else dict(D=pending['D'],gamma=pending['gamma'].tolist(),
                 x=pending['x'].tolist(),xi=None if pending['xi'] is None else pending['xi'].tolist()),
                 mass=mass.tolist(),first_moment=first.tolist(),second_moment=second.tolist(),transition_mass=transitions.tolist(),
                 observation_log_likelihood=observation_log_likelihood)
    save_json(MODEL / ('final-'+role+'-state.json'),state)
    return rows,state


def quote_selection(role, forecasts, rates, dest):
    pos, cursor, trades = None, 0, []
    misses = Counter()
    active_calendar = sorted(set((rates['time']//86400).tolist()))
    def close(t, quote, spread, reason, gap=0.):
        nonlocal pos
        actual = pos['direction']*(quote-pos['entry'])*.01
        stressed = actual-(max(pos['spread'],spread)+gap)*.01
        trades.append(dict(**pos,exit_time=int(t),exit_price=quote,exit_spread=spread,reason=reason,
                           actual=actual,stress=stressed,adverse_gap=gap))
        pos = None
    for bar in rates:
        t, spread = int(bar['time']), .01*int(bar['spread'])
        opening = float(bar['open'])
        new = []
        while cursor < len(forecasts) and forecasts[cursor]['D'] <= t:
            new.append(forecasts[cursor]); cursor += 1
        if pos:
            quote = opening + (spread if pos['direction']<0 else 0)
            gap = max(0.,pos['direction']*(pos['stop']-quote))
            if pos['direction']*(quote-pos['stop']) <= 0:
                close(t,quote,spread,'STOP_OPEN',gap)
            elif t>=pos['deadline'] or any(x['D']>pos['D'] for x in new):
                close(t,quote,spread,'TIME' if t>=pos['deadline'] else 'NEXT_ACTIVITY_BUCKET')
        for event in new:
            if not event['eligible'] or not event['direction']:
                misses['ineligible_or_hurdle'] += 1; continue
            if t>=event['D']+60:
                misses['no_observed_entry_quote_before_deadline'] += 1; continue
            if pos is not None:
                misses['occupied'] += 1; continue
            direction = event['direction']
            entry = opening + (spread if direction>0 else 0)
            raw_stop = entry - direction*200
            stop = (math.floor(raw_stop*100+1e-8) if direction>0 else math.ceil(raw_stop*100-1e-8))/100
            pos = dict(D=event['D'],entry_time=t,direction=direction,entry=entry,spread=spread,stop=stop,
                       deadline=(event['D']//900)*900+3600,prediction_points=event['prediction_points'])
        if pos:
            touched = float(bar['low'])<=pos['stop'] if pos['direction']>0 else float(bar['high'])+spread>=pos['stop']
            if touched:
                quote = min(opening,pos['stop']) if pos['direction']>0 else max(opening+spread,pos['stop'])
                gap = max(0.,pos['direction']*(pos['stop']-quote))
                close(t,quote,spread,'STOP_MINUTE',gap)
    if pos is not None:
        raise RuntimeError('Incomplete selected lifecycle at source end; retain and correct input')
    with (dest / (role+'-quote-trades.csv')).open('w',encoding='utf-8',newline='') as handle:
        names = list(trades[0]) if trades else ['D','actual','stress']
        writer = csv.DictWriter(handle,names); writer.writeheader(); writer.writerows(trades)
    def totals(rows):
        return dict(starts=len(rows),actual=sum(r['actual'] for r in rows),stress=sum(r['stress'] for r in rows))
    halves = {key:totals([r for r in trades if (r['entry_time']<epoch('2025-07-01'))==first])
              for key,first in [('2025-H1',True),('2025-H2',False)]}
    stressed, actual = 100., 100.
    peak, dd, relative_dd, minimum_actual, minimum_stress = 100., 0., 0., 100., 100.
    for trade in trades:
        stressed += trade['stress']; actual += trade['actual']; peak=max(peak,stressed)
        dd=max(dd,peak-stressed); relative_dd=max(relative_dd,(peak-stressed)/max(.01,peak))
        minimum_actual=min(minimum_actual,actual);minimum_stress=min(minimum_stress,stressed)
    result = dict(**totals(trades),halves=halves,observed_source_days=len(active_calendar),
                  starts_per_source_day=len(trades)/len(active_calendar),misses=dict(misses),
                  stop_exits=sum(r['reason'].startswith('STOP') for r in trades),
                  fixed_quote_stressed_max_cash_dd=dd,fixed_quote_stressed_relative_cash_dd=relative_dd,
                  fixed_quote_min_actual_cash=minimum_actual,fixed_quote_min_stressed_cash=minimum_stress)
    result['daily'] = {str(datetime.fromtimestamp(day*86400,timezone.utc).date()):
                      dict(**totals([r for r in trades if r['exit_time']//86400==day]),
                           source_trading_date=day in active_calendar)
                      for day in range(epoch('2025-01-01')//86400,epoch('2026-01-01')//86400)}
    result['gates'] = dict(stress_exceeds_original_passive_actual=result['stress']>9.66,
        both_halves_stress_positive=all(v['stress']>0 for v in halves.values()),
        at_least3_starts_per_original_trading_date=result['starts_per_source_day']>=3,
        source_population_complete=True)
    return result


def run():
    reserve()
    output = RAW / 'selection-v1'
    output.mkdir(exist_ok=False)
    MODEL.mkdir(exist_ok=False)
    rates = np.load(RAW/'input/US100-M1.npy',allow_pickle=False)
    events, calendar = buckets(rates)
    save_json(output/'clock-calendar.json',calendar)
    train = [e for e in events if epoch('2024-01-01')<=e['D']<epoch('2025-01-01') and e['x'] is not None]
    selection = [e for e in events if epoch('2025-01-01')<=e['D']<epoch('2026-01-01')]
    raw_x = np.array([e['x'] for e in train]); days=np.array([e['day'] for e in train])
    feature_mean, feature_std = raw_x.mean(axis=0),np.maximum(1e-6,raw_x.std(axis=0))
    x = np.clip((raw_x-feature_mean)/feature_std,-6,6)
    means, variances, transition, likelihood = fit_hmm(x,days)
    initial=dict(feature_mean=feature_mean.tolist(),feature_std=feature_std.tolist(),means=means.tolist(),
                 variances=variances.tolist(),transition=transition.tolist(),fit_rows=len(x),fit_days=len(set(days.tolist())),
                 likelihoods=likelihood,fit_start=int(train[0]['D']),fit_last=int(train[-1]['D']))
    save_json(MODEL/'initial-state.json',initial)
    graph=MODEL/'activity-filter.onnx';make_graph(graph)
    session=ort.InferenceSession(str(graph),providers=['CPUExecutionProvider'])
    selected_rates=rates[(rates['time']>=epoch('2025-01-01'))&(rates['time']<epoch('2026-01-01'))]
    roles={}
    for role in ('static','online'):
        forecasts,state=forecast_role(role,selection,initial,session,output)
        result=quote_selection(role,forecasts,selected_rates,output)
        result.update(forecasts=len(forecasts),updates=state['updates'],pending_observations=int(state['pending_end'] is not None),
                      mean_observation_log_likelihood=state['observation_log_likelihood']/len(forecasts))
        roles[role]=result
    qualified=[role for role in roles if all(roles[role]['gates'].values())]
    survivor=max(qualified,key=lambda role:(roles[role]['stress'],role=='static')) if qualified else None
    result=dict(utc=datetime.now(timezone.utc).isoformat(),status='COMPLETE_FIXED_BUNDLE_SELECTION_ONLY',roles=roles,
                survivor=survivor,fit=initial,model_sha256=sha(graph),calendar_dates=365,
                clock_events=len(events),selection_events=len(selection),source_rows=len(rates),
                scope='Fixed-volume M1 quote approximation; no shared account, actual native fees/financing, compounding or native equity DD claim.',
                files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                       for base in (output,MODEL) for p in sorted(base.iterdir()) if p.is_file()],
                free_bytes=shutil.disk_usage(ROOT).free,live_changes=False)
    save_json(EVIDENCE/'MODEL_SELECTION_V1.json',result)
    print(json.dumps(dict(status=result['status'],survivor=survivor,
                         roles={role:{k:v for k,v in data.items() if k!='daily'} for role,data in roles.items()}),indent=2),flush=True)


if __name__ == '__main__':
    command=sys.argv[1]
    if command=='prepare': prepare()
    elif command=='run': run()
    else: raise ValueError('Use the normal prepare or run production phase')
