# DD20 One-Shot Open-Exposure Release Proxy V1

This proxy follows the valid empty drawdown-responsive new-birth frontier without rerunning any closed path. The rejected accelerator's weights, growth schedule, later original births and natural exits remain fixed. The new mechanism acts once on exposure that is already open when sampled equity drawdown first reaches a declared threshold, then leaves the portfolio running.

## Why this is distinct

Reversible scaling of future births found a near joint boundary at trigger `8%`, multiplier `0.25`: conservative actual/stressed `+$1,751.785 / +$1,686.828875`, but budgeted DD remained `21.270438%`. Thirteen paths shared the same raw DD floor because future-birth control cannot remove risk already open when the damaging move begins. The next mechanism therefore releases a fraction of the current aggregate open book exactly once and preserves every later original opportunity.

This is not a terminal-lock reset or retune. The terminal-lock family closed the entire portfolio and disabled all future entries; this family changes only positions open at the recorded trigger and immediately returns to the unchanged later path.

## Frozen proxy

- Candidate sampled-equity DD triggers are exactly `1.0%..17.5%` by `0.5` points. Retained fractions of the open book are exactly `0 / 0.25 / 0.50 / 0.75`, producing `136` new paths.
- The already recorded terminal-lock result supplies each first-trigger snapshot without recomputing that closed grid. Structural reconstruction proves every `1.0%..17.5%` trigger has at least one open lifecycle. The `18%..19%` first-trigger snapshot has zero open exposure and is excluded as nonbinding.
- At the trigger, realize the released fraction of aggregate marked floating P/L, retain the declared fraction of every currently open position, and subtract a fixed `$25` release/action proxy reserve.
- Each affected lifecycle later contributes only its retained fraction of frozen actual/stressed close economics. Doubled-cost stress preserves the full observed lifecycle cost drag across released and retained fractions.
- Every later birth already observed on the accelerator path enters at full frozen exposure. Freed capacity creates no synthetic birth. The release is one-shot, never rearms and never terminates the portfolio.
- During the short transition until the last affected original close, sampled equity uses a conservative envelope: charge the worse of the immediate `$25` action reserve or the final candidate-versus-baseline equity delta. Afterward, apply the exact final delta to the observed sampled actual/stressed equity path.
- The already completed accelerator MT5 selection/forward and every closed proxy/MT5 path, including the original 15 combinations, remain closed and are not rerun.

## Economic gates

Selection actual and stressed net already include the `$25` action reserve, then each subtract another `$50` path uncertainty reserve. Both conservative totals must strictly exceed the qualified observed MT5 anchor `+$1,691.54 / +$1,626.26`. All four modified epochs, both closed-balance paths and both sampled-equity envelopes must remain positive.

Budgeted native DD is the larger of:

- qualified native DD `19.550372%` plus `0.25` points; and
- the worse conservative sampled actual/stressed equity DD plus the observed native-minus-sampled gap `0.193562` points plus a `0.25`-point release detection/transition/execution reserve.

Budgeted DD must remain at or below the hard `20%` limit. The sole role, if any, maximizes conservative stressed selection profit, then conservative actual profit and recent-epoch stressed profit, before preferring lower budgeted DD, the larger trigger and retained fraction.

The independent forward cannot arm because maximum stressed closed balance is only `$129.946`; all candidates must preserve exact actual/stressed `+$23.01 / +$21.256`, native DD `12.436759%`, June `+$19.79 / +$18.976`, and July `+$3.22 / +$2.280`. No MT5 may launch during this proxy, and at most one role may be shortlisted afterward.

## Declared boundary

All `136` candidate economics are unopened. The copied raw input contains `10` files / `12,310,256` bytes with canonical manifest `878768593041D6B2FFD5C0ECE7D06A1DA6D9493CD4955703C2A0120677A7C314`. Freeze and push this declaration before exactly one proxy process opens the candidate frontier.

## Proxy result

Declaration commit `d0c7bf324cc8c1dd8ec34da4a18d9ae688ac17d6` reached `origin/main` before one process evaluated all `136` paths in `1.0713894` seconds. Every copied input, lifecycle/native/sampled anchor, predecessor identity, terminal-lock snapshot identity, zero-error balance alignment, binding-open-exposure exclusion and forward non-arming check passed. All candidates released open exposure, stayed positive, exceeded the qualified profit floor after reserves and retained four positive epochs. **Budgeted DD passed zero**, so no MT5 shortlist exists.

Maximum conservative profit and minimum family DD coincide in the trigger `17.0% / 17.5%`, retain-`0` tie; the declared ordering selects `17.5%`. At `2026.03.10 14:30:00` it releases two open positions, pays the `$25` action reserve and earns actual/stressed `+$2,188.60 / +$2,098.874`, or conservative `+$2,138.60 / +$2,048.874` after the additional `$50` reserve. That is `+$3.21 / +$3.21` above the rejected accelerator before the uncertainty reserve.

Its worse sampled-equity DD is `29.805002%` and budgeted native DD is `30.248564%`, missing the hard limit by `10.248564` points. Even the family minimum is worse than the untouched accelerator's `27.894257%` sampled DD: a one-time release changes only the small book present at its first trigger, while later full-exposure births recreate the independent damaging path. Earlier or partial releases retain less profit and do not produce a lower DD candidate.

This is a valid economic empty frontier, not an environment, design or engineering failure. Forward remains exact and unarmed at actual/stressed `+$23.01 / +$21.256`, native DD `12.436759%`, with positive June and July. Freeze this family without MT5. Continue proxy-first with an economically distinct recurring open-exposure governor that can act again after recovery and later births; do not retune this one-shot grid or rerun any closed path.
