# DD20 Drawdown-Responsive Exposure Proxy V1

This proxy follows the valid empty uniform profit-realization frontier without rerunning any closed path. The rejected accelerator's weights and causal `$150 → $50 after +$450`, cap-`14` schedule remain fixed. The new mechanism changes only the exposure of a newly born post-activation position when the candidate's own doubled-cost-stressed closed balance is already in drawdown.

## Why this is distinct

Uniform per-position profit realization improved maximum proxy profit to `+$2,321.208959 / +$2,231.482959`, but every one of its `49` targets missed budgeted DD. The lowest-DD target still budgeted `21.270438%` while destroying required profit. The next control therefore does not retune exits, components or R targets. It keeps every natural exit and applies a reversible state-dependent risk multiplier only at subsequent births during an existing closed-balance drawdown.

The accelerator path's `458` post-activation births span stressed closed-balance DD `0%..22.961218%`; median is `4.741408%` and the 90th percentile is `14.623301%`. This supplies a broad causal state range without using future trade outcomes at admission time.

## Frozen proxy

- Candidate triggers are exactly `1%..18%` by `1` point. Candidate new-position risk multipliers are exactly `0.10 / 0.25 / 0.50 / 0.75`, producing `72` new paths.
- The control latches only when fixed doubled-cost-stressed closed balance first reaches `$550`, observed at `2025.04.23 17:30:00`. The forward never arms because its maximum stressed closed balance is only `$129.946`.
- At each already observed post-activation birth, calculate the candidate's current stressed closed-balance drawdown from its own all-time stressed closed-balance high. At or above the trigger, multiply only that new position's frozen planned risk and actual/stressed lifecycle economics by the candidate risk multiplier.
- Existing positions are never resized or closed. At a later birth below the trigger, full frozen exposure resumes automatically; there is no terminal stop, cooldown clock or manually tuned release threshold.
- Every original later birth remains available, while reduced risk creates no synthetic opportunity. Each scaled position pays a further `$0.10` modeling reserve on actual and stressed net.
- The already completed accelerator MT5 selection/forward, uniform profit-realization, terminal-lock and risk-ceiling grids, qualified MT5 anchor, all prior candidates and the original 15 combinations remain closed and are not rerun.

## Economic gates

Selection actual and stressed net include every per-scaled-position reserve and then each subtract another `$100` global path/lattice uncertainty reserve. Both conservative totals must strictly exceed the qualified observed MT5 anchor `+$1,691.54 / +$1,626.26`. All four chronological epochs and both candidate closed-balance paths must remain positive.

Budgeted native DD is the larger of:

- qualified native DD `19.550372%` plus `0.25` points; and
- the worse actual/stressed candidate closed-balance DD plus the rejected accelerator's observed native-minus-raw gap `5.126601` points plus a `0.5`-point state/lattice reserve.

Budgeted DD must remain at or below the hard `20%` limit. The sole role, if any, maximizes conservative stressed selection profit, then conservative actual profit and recent-epoch stressed profit, before preferring lower budgeted DD, the larger trigger and the larger multiplier.

All `72` candidates must preserve the exact unarmed forward at actual/stressed `+$23.01 / +$21.256`, native DD `12.436759%`, June `+$19.79 / +$18.976`, and July `+$3.22 / +$2.280`. No MT5 may launch during this proxy, and at most one role may be shortlisted afterward.

## Declared boundary

All `72` candidate economics are unopened. The copied raw input contains `8` files / `4,083,815` bytes with canonical manifest `FE8C6D3A282B7AAF883463FE843156EB6BA1D79F7F7CF0C166B3FF18A6F2C5D3`. Freeze and push this declaration before exactly one proxy process opens the candidate frontier.

## Proxy result

Declaration commit `32c95f07d7e2c9c1f4b6152d1d31d2d7c83756a6` reached `origin/main` before one process evaluated all `72` paths in `0.1653041` seconds. Every copied input, lifecycle/native anchor, predecessor identity, drawdown-state structure and forward non-arming check passed. All candidates bound, stayed positive, retained positive capital and kept all four epochs positive. Conservative profit passed `32`; **budgeted DD passed zero**, so no MT5 shortlist exists.

Maximum conservative profit comes from trigger `7%` and multiplier `0.75`. It scales `202` of `458` post-activation births across five risk-off episodes and earns actual/stressed `+$2,099.9125 / +$2,016.883375`, conservative `+$1,999.9125 / +$1,916.883375`. Its raw/budgeted DD is `20.001912% / 25.628513%`.

The economically nearest DD boundary is trigger `8%`, multiplier `0.25`. It scales `305` births across seven episodes, earns actual/stressed `+$1,851.785 / +$1,786.828875` and remains above the qualified floor after the `$100` reserve at `+$1,751.785 / +$1,686.828875`. Its raw DD reaches the family minimum `15.643837%`, but budgeted DD is `21.270438%`, still `1.270438` points over the hard budget. Thirteen paths tie that raw/budgeted floor, but none supplies higher conservative stressed profit than this one.

This is a valid economic empty frontier, not an environment or engineering failure. Reducing only future births cannot cut through the existing-exposure/pre-activation DD floor. Forward remains exact and unarmed at `+$23.01 / +$21.256`, native DD `12.436759%`, with positive June and July. Freeze this family without MT5. Continue proxy-first with an economically distinct nonterminal release of already-open aggregate exposure that still permits later original births; do not retune this trigger/multiplier grid or rerun any closed path.
