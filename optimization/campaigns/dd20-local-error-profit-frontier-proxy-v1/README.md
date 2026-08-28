# DD20 Composition-Local Error Profit Frontier Proxy V1

This independent fast proxy replaces the closed global-worst-error contract with a composition-local upper envelope. It does not weaken the qualified MT5 floor or reuse the closed redistribution rows. Error charges increase with each candidate's component-weight distance from the five observed MT5 anchors, so the low-error qualified point informs nearby candidates while the high-exposure error reasserts itself as candidates move toward that region.

## Frozen local-error model

- Distance is the unweighted L1 sum across the six component multipliers in range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / impulse order.
- For each error metric, the frozen slope is the largest absolute error difference divided by L1 distance across every anchor pair. A candidate's upper charge is the nonnegative minimum of `anchor error + slope × distance` over all applicable anchors.
- Selection native-minus-raw DD uses slope `0.8629081267` percentage points per weight and still adds `0.25` points before the hard `20%` gate.
- Selection actual/stressed proxy overstatement uses `$446.1333008658 / $431.4507034632` per weight and still adds a separate `$50` reserve. Both corrected nets must strictly exceed the qualified MT5 anchor's `+$1,691.54 / +$1,626.26`.
- Full June/July native-minus-raw DD uses `1.2249053689` points per weight plus `0.5` points. Continuous-July actual/stressed overstatement uses `$1.9363636364 / $2.155` per weight plus `$1`.
- The same positive selection, four-epoch, full-pair, June, raw July and corrected July gates remain. Only the error geometry changes from one global maximum to a data-consistent local upper envelope.

## Frozen new search

- Range-61 is half-step shifted to `1.55..2.45` by `0.1`, so none of the `204,490` rows is an exact row from the closed integer-tenth grid.
- Range-64 and cross are `0..1.0`, intraday is `2.8..4.0`, return is `0..1.2`, all by `0.1`; impulse remains `0`.
- Executable `0.01`-lot materialization, the `$150` stressed-balance ladder and `0.04 / 0.18` position/aggregate risk admission are unchanged.
- Exactly one role may freeze: maximum composition-local conservative selection stressed profit, then conservative actual, corrected July stressed, full-pair stressed, weaker-month stressed, recent-selection stressed and lower budgeted DD.

The input is another independent physical 19-file copy totaling `34,559,535` bytes with no mutable cross-family link. All five MT5 anchors, the closed global-error grid and the original 15 combinations remain evidence only and will not rerun. The proxy may nominate at most one new MT5 hypothesis and launches no MT5 itself.

## Current boundary

Declaration commit `17212fa8d830ee983310a26907e67597c6c46cb7` reached `origin/main` before exactly one proxy process opened economics. It evaluated all `204,490` new rows plus five external anchors in `97.8265` seconds and exited `0`. Every copied-input, proxy/native anchor and nonnegative local-envelope check passed.

No row passed the combined selection contract. Selection eligibility is `0`; conditional paired-forward, June, raw July and final counts are also `0`. No winner was ranked and the MT5 shortlist is empty. Across the grid, local selection DD charges ranged `1.148018..5.185475` points, actual/stressed profit charges ranged `$94.2485..$1,968.0084 / $88.6346..$1,900.7276`, and the separate reserves remained applied.

Status is `VALID_PROXY_COMPLETE_NO_SELECTION_ELIGIBLE`; classification is `COMPOSITION_LOCAL_STATIC_WEIGHT_FRONTIER_EMPTY_NO_MT5_SHORTLIST`. The raw result is `61,892` bytes at SHA-256 `19D67D594211426D602936F9D089C249FD8469EC757BF079CCD729522C6A4BF4`. The qualified MT5 anchor remains retained without rerun.

This campaign closes without MT5. After two distinct static-weight frontiers produced no conservatively superior candidate, the next proxy changes the profit mechanism by exploring the stressed-balance capital addition ladder rather than opening another neighboring component grid.
