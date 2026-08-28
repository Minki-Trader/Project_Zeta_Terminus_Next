# DD20 Equity High-Watermark Terminal Lock Proxy V1

This proxy follows the valid empty fixed-dollar risk-ceiling frontier without rerunning any closed path. The rejected accelerator's component weights and causal `$150 → $50 after +$450` schedule with cap `14` remain fixed. The new economic mechanism protects accumulated equity by permanently ending the path when post-arming sampled equity gives back a declared percentage from its all-time sampled high-watermark.

## Why this is distinct

The rejected accelerator earned selection actual/stressed `+$2,185.39 / +$2,095.664`, but native maximum relative equity DD reached `28.087819%`. Aggregate planned-risk caps could not join the profit and DD regions: even the lowest-DD `$30` cap budgeted `20.679738%` and lost too much profit. This family does not reject individual births or rescale exposure. It instead attempts to retain the accelerated profit path and crystallize marked equity before the later giveback breaches the hard budget.

The lock can arm only after doubled-cost-stressed closed balance reaches `$550`, the same causal `+$450` profit threshold that activates the fixed accelerator. Before that threshold it cannot inspect or act on future economics.

## Frozen proxy

- Candidate drawdown triggers are exactly `1.0%..19.0%` by `0.5` percentage points, or `37` new values.
- The equity high-watermark is the maximum sampled account equity from the `$100` selection start through the current candidate snapshot.
- After arming, the first snapshot whose drawdown from that high-watermark reaches the candidate trigger liquidates every owned position at marked equity, subtracts a fixed `$25` liquidation/proxy reserve, disables every future entry and ends that economic path permanently.
- The trigger has no reset or re-entry. Fixed accelerator weights, steps, activation threshold, volume cap, lifecycle source and sampled candidate path do not vary.
- Candidate snapshots are aligned to the nearest before/after lifecycle close state within the same server timestamp. The maximum permitted account-balance alignment error is `$0.011`; the matched cumulative doubled-cost drag transfers actual sampled equity to stressed sampled equity.
- The already completed accelerated MT5 selection and forward, the risk-ceiling proxy, the qualified MT5 anchor, all prior candidates and the original 15 combinations remain closed and are not rerun.

## Economic gates

Selection actual terminal net is marked account equity less the `$100` start and `$25` reserve. Stressed terminal net additionally subtracts cumulative doubled-cost close drag. Both must strictly exceed the qualified observed MT5 anchor `+$1,691.54 / +$1,626.26`, and every one of the four chronological selection epochs must retain positive actual and stressed net through the lock.

Budgeted native DD is the larger of:

- qualified native DD `19.550372%` plus `0.25` points; and
- maximum sampled equity DD through the lock plus the rejected accelerator's observed native-minus-sampled gap `0.193562` points plus a `0.25`-point terminal-detection/liquidation reserve.

Budgeted DD must stay at or below the hard `20%` limit. The sole role, if any, maximizes stressed terminal profit, then actual terminal profit and recent-epoch stressed profit, before preferring lower budgeted DD and the larger trigger.

The independent forward cannot arm because its maximum stressed closed balance is only `$129.946`, below `$550`. Every candidate must therefore preserve exact forward actual/stressed `+$23.01 / +$21.256`, native DD `12.436759%`, June `+$19.79 / +$18.976`, and July `+$3.22 / +$2.280`. No MT5 may launch during this proxy, and at most one role may be shortlisted afterward.

## Declared boundary

All `37` candidate economics are unopened. The copied raw input contains `9` files / `12,427,130` bytes with canonical manifest `56F47DC1965561C14564799F8115D116181AAB156FF92858639D5D9487B790F6`. Freeze and push this declaration before exactly one proxy process opens the candidate frontier.

## Proxy result

Declaration commit `18196eef5f1b21191efe9090aad48d6383e3a9af` reached `origin/main` before one process evaluated all `37` triggers in `0.5007635` seconds. Every copied input, lifecycle/native anchor, predecessor identity, zero-error snapshot alignment and forward non-arming check passed. All candidates fired in selection, all `37` stayed positive and passed the budgeted DD gate, and `24` retained all four positive epochs. **Zero** strictly exceeded the qualified actual and stressed profit floor, so the intersection and MT5 shortlist are empty.

The maximum-profit terminal result is the economically tied `14.5%..16.5%` lock at `2026.03.06 15:30:00`; ranking selects `16.5%`. It liquidates marked equity with `1,191` lifecycles already closed and earns actual/stressed `+$1,428.82 / +$1,373.40` after the `$25` reserve. Budgeted DD is `19.800372%` and all epochs remain positive, but it falls short of the qualified anchor by `$262.72 / $252.86`. Higher `17%..19%` triggers lock four days later at still lower profit, while earlier locks discard still more of the later profit path.

The permanent terminal response therefore solves the declared DD side but exits before the subsequent profitable recovery and cannot preserve enough explosive profit. This is a valid economic empty frontier, not an environment or engineering failure. Forward remains invariant at `+$23.01 / +$21.256`, native DD `12.436759%`, with positive June and July. No MT5 shortlist exists. Freeze this entire terminal-lock family and continue proxy-first with a distinct nonterminal open-profit realization or temporary exposure-release mechanism that can retain later entries; do not retune this trigger grid or rerun any closed path.
