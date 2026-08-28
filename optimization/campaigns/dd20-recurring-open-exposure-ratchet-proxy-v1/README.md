# DD20 Recurring Open-Exposure Ratchet Proxy V1

This proxy follows the valid empty one-shot release frontier without rerunning it. The rejected accelerator's weights, growth schedule, original births and natural exits remain fixed. The new mechanism can release the open book again after each affected lifecycle bundle has cleared, so later independent drawdown episodes are governed without permanently terminating the portfolio.

## Why this is distinct

The one-shot family kept conservative actual/stressed profit at `+$2,138.60 / +$2,048.874`, but its best and minimum-DD path still budgeted `30.248564%`. It acted on only two positions at the first `17.5%` trigger; every later original birth then returned at full exposure and recreated the damaging path. This successor changes the state machine rather than retuning that trigger/fraction grid: each release enters a lifecycle-clear cooldown, then resets a new local equity high-watermark and may act again on a later book.

## Frozen proxy

- Candidate local stressed sampled-equity DD triggers are exactly `2 / 4 / 6 / 8 / 10 / 12 / 14 / 16 / 18%`. Retained fractions of the currently open book are exactly `0 / 0.25 / 0.50`, producing `27` new paths.
- The governor first arms only when fixed doubled-cost-stressed closed balance reaches `$550`, observed at `2025.04.23 17:30:00`. The independent forward never arms because its maximum stressed closed balance is only `$129.946`.
- In an armed episode, the first sampled snapshot at or above the candidate's local DD trigger with nonzero open exposure realizes the released fraction of aggregate marked floating P/L, retains the declared fraction of every currently open lifecycle and subtracts `$25`.
- The governor cannot act again until the last affected original lifecycle closes. Every later original birth still enters at full exposure during that cooldown, and freed capacity creates no synthetic birth.
- At the first sampled snapshot strictly after cooldown, the candidate resets its local stressed-equity high-watermark to current equity and rearms. A trigger observed while flat waits causally for later open exposure instead of inventing an action.
- Each affected lifecycle later contributes only its retained fraction of frozen actual/stressed close economics. Doubled-cost stress preserves the full observed cost drag across released and retained fractions.
- During each cooldown, the sampled-equity envelope adds the settled prior shift plus the worse of immediate `-$25` or that episode's final candidate-versus-baseline delta. After the affected bundle clears, the exact episode delta settles before the next local high-watermark begins.
- The already completed accelerator MT5 selection/forward, one-shot release, future-birth scaling, profit-realization, terminal-lock and risk-ceiling paths, the qualified anchor, all other prior candidates and the original 15 combinations remain closed and are not rerun.

## Economic gates

Selection actual and stressed net already include `$25` for every release episode, then each subtract another `$75` recurring-path uncertainty reserve. Both conservative totals must strictly exceed the qualified observed MT5 anchor `+$1,691.54 / +$1,626.26`. All four modified epochs, both closed-balance paths and both sampled-equity envelopes must remain positive.

Budgeted native DD is the larger of:

- qualified native DD `19.550372%` plus `0.25` points; and
- the worse conservative sampled actual/stressed equity DD plus the observed native-minus-sampled gap `0.193562` points plus a `0.50`-point recurring state/transition/execution reserve.

Budgeted DD must remain at or below the hard `20%` limit. The sole role, if any, maximizes conservative stressed selection profit, then conservative actual profit and recent-epoch stressed profit, before preferring lower budgeted DD, the larger trigger and retained fraction.

The independent forward must remain exact and unarmed at actual/stressed `+$23.01 / +$21.256`, native DD `12.436759%`, June `+$19.79 / +$18.976`, and July `+$3.22 / +$2.280`. No MT5 may launch during this proxy, and at most one role may be shortlisted afterward.

## Declared boundary

All `27` candidate economics are unopened. The copied raw input contains `8` files / `12,155,742` bytes with canonical manifest `F0FEF6A4A6029ED9B55534EC1AA3031321FFD2B1FF16B59A16A76D37F48D339A`. Freeze and push this declaration before exactly one proxy process opens the candidate frontier.
