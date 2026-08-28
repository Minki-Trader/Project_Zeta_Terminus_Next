# DD20 Component Equity-State Allocation Proxy V1

This independent phase-two proxy starts from the fully qualified DD20 MT5 anchor without rerunning it. It keeps the anchor's signals, clocks, directions, exits, execution model and fixed base composition, then lets each nonzero component's own completed admitted stressed-R history change only that component's next exposure. The latest continuous June and July remain fully held out until one selection winner, if any, is frozen.

## Why this is distinct

The closed first phase exhausted static composition, capital ladders, global risk ceilings, terminal locks, profit realization and several account-level drawdown controls. This family instead asks whether candidate-local component performance state can allocate risk more efficiently without changing any market signal or exit. It is a causal portfolio-allocation mechanism, not a new signal hypothesis, so no Lab unit is opened.

## Frozen proxy

- The exact qualified base weights remain `1.6 / 0.8 / 0.4 / 3.2 / 1.2 / 0` in component order range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / disabled impulse-passive.
- Candidate state is a per-component deque of the last `5 / 10 / 20 / 40` admitted closes. Each close appends its candidate doubled-cost-stressed increment divided by its admitted planned risk. Skipped, rejected and disabled births never enter state.
- A component stays at neutral multiplier `1` until its deque is full. Its mean stressed-R below `-0 / -0.05 / -0.10` applies a loss multiplier of `0 / 0.25 / 0.50 / 0.75`; a mean above the symmetric positive band applies a gain multiplier of `1 / 1.125 / 1.25`; otherwise it remains at `1`.
- The Cartesian product is exactly `4 x 3 x 4 x 3 = 144` candidates. Effective weight is the frozen qualified base weight times the current component multiplier. The passive component remains zero.
- Executable positive-MathRound `0.01`-lot materialization, passive reservation basis, daily `$150` stressed-balance ladder, conservative capital `min(actual, stressed)`, `0.04` position risk, `0.18` aggregate admission plus `$0.01`, original births and natural exits remain unchanged. No synthetic birth or capacity replacement is allowed.
- A close scales source actual/stressed lifecycle economics by executable candidate volume divided by source volume. State uses that candidate stressed increment and the planned risk admitted at its birth.
- The long selection segment contains exactly `2,177` births and closes and source actual/stressed `+$1,166.89 / +$1,085.408`. Its four frozen epochs are 2022-08..2023-06, 2023-06..2024-06, 2024-06..2025-06 and 2025-06..2026-06.
- A candidate must make at least 25 non-neutral executable birth decisions across at least three nonzero-anchor components. Full selection and every epoch must keep actual/stressed net and balances positive, and every epoch raw DD must remain at or below 20%.

## Economic gates

The qualified neutral control must reproduce proxy selection actual/stressed `+$1,763.4818571429 / +$1,693.3220714286`, raw DD `17.4282210109%`, and independent forward `+$28.87 / +$27.236`, raw DD `9.208590762%`. Its preserved native cache must reproduce profit and relative-equity-DD at offsets `0xB2C` and `0xBBC`.

Selection profit subtracts only the qualified control's known proxy-minus-native errors `$71.9418571429 / $67.0620714286`, then another `$50` reserve. Both conservative nets must strictly exceed the qualified native `+$1,691.54 / +$1,626.26`. Budgeted selection DD adds the qualified observed native-minus-raw gap `2.1221507541` points and a `0.75`-point state/execution reserve to raw DD and must remain at or below 20%.

Selection ranking maximizes conservative stressed net, then conservative actual net and recent-epoch stressed net, then minimizes budgeted DD before lexicographic lookback / band / loss / gain order. Exactly one winner may freeze. Only after that freeze may the proxy initialize fresh `$100` capital and empty component state, open the continuous 2026-06-01..2026-08-01 lifecycle input, and report full, June and July results.

Forward full, June and July actual/stressed nets and balances must all remain positive. Forward budgeted DD adds `5.6021825077` points and `0.5` points to raw DD and must remain at or below 20%. Conservative July additionally subtracts `$6.82 / $6.8535` and `$1` and must stay actual/stressed positive. No MT5 launches during this proxy, and at most one valid clue may be frozen for a later dedicated single Strategy Tester unit outside the Master terminal.

## Declared boundary

All 144 candidate economics are unopened. The input is an independent physical 19-file copy totaling `34,559,535` bytes with canonical manifest `F79651BAD1CD082DA6E1B3E89BCB59576F4567EC57F1C2C75D7523E8F4475BB8`. The declaration, contract and implementation are frozen locally before exactly one proxy process opens selection economics. They will be committed and pushed together with this whole research unit's economic closure, per the current unit-level Git boundary.

## Proxy result

Exactly one process evaluated all `144` candidate policies in `1.5086225` seconds and exited `0`. All 19 input pins, the qualified selection lifecycle/native cache and the neutral selection proxy calibration passed. Selection gate counts are non-neutral density `93`, positive full economics `144`, conservative profit `14`, positive balances `144`, four positive epochs `105`, all epoch raw-DD `97`, budgeted full DD `21`, and combined `0`.

The maximum-profit policy is lookback `40`, band `0.05R`, loss multiplier `0.25`, gain multiplier `1.25`. It makes `239` non-neutral executable admissions across all five active components and earns proxy actual/stressed `+$1,959.055845 / +$1,882.501631`, conservative `+$1,837.113988 / +$1,765.439560`, exceeding the qualified native floor by `+$145.573988 / +$139.179560`. All four epochs pass, but raw/budgeted DD is `19.626926% / 22.499077%`.

All `14` conservative-profit passes are present in the frozen top-20 output. Their minimum budgeted-DD policy is lookback `40`, band `0.10R`, loss multiplier `0`, gain multiplier `1.125`. It earns proxy actual/stressed `+$1,850.789202 / +$1,778.655702`, conservative `+$1,728.847345 / +$1,661.593631`, and exceeds the qualified native floor by `+$37.307345 / +$35.333631`. Its raw DD exactly matches the neutral control at `17.428221%`, but the declared `2.122151`-point native gap plus `0.75`-point state/execution reserve budgets `20.300372%`, missing the hard cap by `0.300372` points.

This is a valid economic empty selection frontier, not an environment, design, invocation or engineering failure. The conservative-profit and DD-eligible regions are disjoint under the frozen contract, so no selection winner or MT5 shortlist exists. The continuous June/July holdout, qualified forward cache and neutral forward calibration remain unopened exactly as declared. Freeze this grid without rerun; the qualified MT5 anchor remains authoritative.
