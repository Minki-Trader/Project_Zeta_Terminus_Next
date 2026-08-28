# DD20 MT5-Calibrated Exposure Margin Proxy V1

This independent fast proxy starts from the highest-profit observed MT5 point, which earned selection actual/stressed `+$5,786.63 / +$5,477.524` and positive full June/July forward economics but missed the hard drawdown budget by only `0.2568876` percentage points. It seeks the smallest economically useful exposure redistribution that preserves explosive profit while adding conservative room below `20%` before another MT5 run is considered.

## Frozen local search

- Component order remains range-61 / range-64 / US100 cross / US30 intraday pressure / US30 return / disabled impulse-passive.
- The five active grids use `0.1` increments around the near-miss point: range-61 `1.6..2.2`, range-64 `1.1..1.7`, cross `1.4..2.0`, intraday `2.2..2.8`, return `1.2..1.8`; impulse stays `0`. This is exactly `16,807` compositions.
- The proxy retains corrected `0.01`-lot materialization, passive reservation volume, the `$150` stressed-balance sizing ladder, `0.04` component position risk and unchanged `0.18` aggregate admission.
- Selection DD uses three real MT5 anchors: preserved unweighted `11.3757%`, the new `20.2568876%` near miss and the prior `27.0728351%` high-exposure rejection. Piecewise projection is never allowed below raw closed-balance DD, then a frozen `0.5` percentage-point uncertainty reserve is added before the `20%` gate.
- Full June/July sequential DD uses the preserved base and new near-miss MT5 forward anchors. Because their raw closed-balance DD moves opposite to observed floating-equity DD, the observed-minus-raw gap is fitted against total exposure weight instead of raw DD; the estimate never falls below raw DD and receives a frozen `0.25` percentage-point reserve before the same hard gate.
- Long selection and all four epochs must remain actual/stressed positive with positive balances. The full paired forward and each independently initialized month must also remain actual/stressed positive and DD-safe.
- One role may freeze: maximum selection stressed profit, then full paired-forward stressed profit, weaker independent-month stressed profit, selection actual profit, recent-selection stressed profit and lower budgeted DD.

The original 15 combinations, the prior high-exposure MT5 point and the exact near-miss MT5 point are anchors only. None can rerun inside this proxy, and no MT5 launches during it. A valid result may nominate at most one new hypothesis.

## Current boundary

The first invocation emitted no economic output because the originally declared paired-forward raw-DD affine assumption was not monotonic between its two anchors. That design condition was corrected to the exposure-weight gap calibration above. Selection, full paired forward, June, July, ranking and shortlist remain unopened. This campaign has no Live or Lab authority and cannot promote anything automatically.
