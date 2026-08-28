# DD20 Persistent Global Drawdown Regime Proxy V1

This proxy follows the valid empty local-ratchet frontier without rerunning it. The rejected accelerator's weights, growth schedule, original births and natural exits remain fixed. The new mechanism preserves one immutable global equity high-watermark: after a binding drawdown it releases current exposure and keeps every later birth reduced until the account truly recovers near that same global high.

## Why this is distinct

The recurring local-ratchet family retained conservative actual/stressed profit up to `+$1,995.58 / +$1,905.854`, but its minimum budgeted DD was `35.785203%`. Each lifecycle-clear cooldown reset protection to a lower local high, allowing multiple individually bounded episodes to accumulate into a large global drawdown. This successor never resets the high-watermark and couples current-book release with persistent future-birth control inside one risk-off regime.

## Frozen proxy

- Candidate global stressed sampled-equity DD triggers are exactly `6 / 8 / 10 / 12 / 14 / 16 / 18%`. Retained fractions of the current open book are `0 / 0.25`, and future-birth risk multipliers during risk-off are `0.10 / 0.25 / 0.50`, producing `42` new paths.
- The regime first arms only when fixed doubled-cost-stressed closed balance reaches `$550`, observed at `2025.04.23 17:30:00`. The independent forward never arms because its maximum stressed closed balance is only `$129.946`.
- At the first binding global-DD snapshot with nonzero open exposure, realize the released current-book fraction of aggregate marked floating P/L, retain the declared fraction of every open lifecycle and subtract `$25`.
- While risk-off, every later original birth still occurs but enters at the declared multiplier and pays another `$0.10` modeling reserve. Reduced exposure creates no synthetic opportunity.
- Risk-on can resume only when candidate stressed sampled-equity DD is at or below `2%` of the unchanged global high and every released/scaled lifecycle from the episode has naturally cleared. The global high is never rebased downward.
- Released lifecycles later contribute only their retained fraction while preserving the full observed doubled-cost drag. Scaled births multiply their frozen actual/stressed lifecycle economics and observed mark path consistently.
- A release transition applies the worse of immediate `-$25` or its final candidate-versus-baseline delta through the last released close. A scaled birth applies the minimum of `-$0.10`, its final delta and its forfeited positive observed peak mark until its original close. Exact deltas settle afterward.
- The accelerator MT5 selection/forward, local recurring ratchet, one-shot release, future-birth scaling, profit-realization, terminal-lock and risk-ceiling paths, the qualified anchor, all other prior candidates and the original 15 combinations remain closed and are not rerun.

## Economic gates

Selection actual and stressed net already include every `$25` regime-entry reserve and `$0.10` scaled-birth reserve, then each subtract another `$100` persistent-path uncertainty reserve. Both conservative totals must strictly exceed the qualified observed MT5 anchor `+$1,691.54 / +$1,626.26`. All four modified epochs, both closed-balance paths and both sampled-equity envelopes must remain positive.

Budgeted native DD is the larger of:

- qualified native DD `19.550372%` plus `0.25` points; and
- the worse conservative sampled actual/stressed equity DD plus the observed native-minus-sampled gap `0.193562` points plus a `0.50`-point persistent state/transition/execution reserve.

Budgeted DD must remain at or below the hard `20%` limit. The sole role, if any, maximizes conservative stressed selection profit, then conservative actual profit and recent-epoch stressed profit, before preferring lower budgeted DD, the larger trigger, current-book retention and future-birth multiplier.

The independent forward must remain exact and unarmed at actual/stressed `+$23.01 / +$21.256`, native DD `12.436759%`, June `+$19.79 / +$18.976`, and July `+$3.22 / +$2.280`. No MT5 may launch during this proxy, and at most one role may be shortlisted afterward.

## Declared boundary

All `42` candidate economics are unopened. The copied raw input contains `8` files / `12,156,352` bytes with canonical manifest `9457C3041082EDC3973FB8E70A509EB6BFFA621CBF980E2346B3856AC5FA60E8`. Freeze and push this declaration before exactly one proxy process opens the candidate frontier.

## Proxy result

Declaration commit `e19e9778a6d1be6006a68ecf70a892fc40bbabdd` reached `origin/main` before one process evaluated all `42` paths in `1.0245463` seconds. Every copied input, lifecycle/native/sampled anchor, predecessor identity, zero-error balance alignment, modification-delta identity, immutable-global-high, clean-book recovery and forward non-arming check passed. All candidates entered risk-off across `1..4` episodes and scaled `335..430` later births. Every path remained positive with positive capital and four positive epochs. Conservative profit passed only `1`; **budgeted DD passed zero**, so no MT5 shortlist exists.

Maximum conservative profit and minimum family DD coincide at trigger `10%`, current-book retain `0`, future-birth multiplier `0.50`. Two cleanly recovered regimes release four current positions and scale `347` later births. The path earns actual/stressed `+$1,856.42 / +$1,788.52775`, conservative `+$1,756.42 / +$1,688.52775`, so it remains above the qualified anchor after the `$100` reserve.

Closed-balance DD reaches actual/stressed `17.601675% / 18.628193%`, but the declared concurrent open-path envelope lifts worse sampled-equity DD to `27.159394%` and budgeted native DD to `27.852956%`, missing the hard limit by `7.852956` points. Long persistent scaling makes `347` observed positive peak marks unavailable while those lifecycles are open; their conservative transition charges dominate the closed-balance improvement.

This is a valid economic empty frontier, not an environment, design or engineering failure. An immutable global high prevents the predecessor's staircase, and one path preserves the required final profit, but keeping the entire recovery interval at reduced exposure creates too much open-path opportunity loss under the declared envelope. Forward stays exact and unarmed at `+$23.01 / +$21.256`, native DD `12.436759%`, with positive June and July. Freeze this family without MT5. Continue proxy-first with an economically distinct time-bounded drawdown quarantine that isolates the damaging interval and then resumes full original exposure, rather than retuning this trigger/retention/multiplier grid or rerunning any closed path.
