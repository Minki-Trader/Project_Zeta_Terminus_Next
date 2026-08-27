# Federal Reserve Reserve-Balance Book State V1

This source-free Program 2 family owns Unit 092. It asks whether the sign of the
latest causally available weekly change in `Reserve balances with Federal
Reserve Banks`, as published in the Federal Reserve Board's archived H.4.1
release, materially rotates stressed lifecycle value and stop quality between
the existing US100 and US30 books.

The state is threshold-free. `RESERVE_EXPAND` means the archived release's
week-over-week change is strictly positive and `RESERVE_CONTRACT` means it is
strictly negative. A release is usable only on a portfolio server date strictly
later than its official release date, because H.4.1 is normally published at
16:30 U.S. Eastern time after every frozen native decision on that date.

The unit has one connected bundle:

- official H.4.1 archive and causal-state integrity;
- native signal and durable-birth supply transmission, descriptive only; and
- component-period-centered US100-minus-US30 stressed-R and stop-rate
  difference-in-differences.

Outcome-free feasibility covered 214 releases, 1,051 normal portfolio days,
2,429 native signals and 2,233 durable births. The two reserve states are dense
in every period and book. No close value, planned risk, stressed return, stop
reason or conditional economic verdict was read before declaration.

The family creates no MQL, runtime, compile, Tester, order, account query or
Live change. A complete directional pass may retain only one later,
non-automatic whole-portfolio real-tick book-risk question. Null, ambiguous or
invalid closure retains no seed, and no magnitude, lag, smoothing, balance-sheet
component, period, book or component rescue follows.

Implementation governance follows `docs/OPERATING_DIRECTION.md`: economic
contract changes and metric reruns remain zero, while a demonstrable parser,
serialization, invocation or deterministic aggregation defect is recorded,
corrected and rerun as needed to execute that unchanged contract. The original
declaration's arbitrary one-correction cap is superseded only procedurally by
`evidence/FEDERAL_RESERVE_RESERVE_BALANCE_BOOK_STATE_IMPLEMENTATION_POLICY_ALIGNMENT_V1.json`;
the original declaration and first failed-invocation record remain byte-frozen.

The corrected official acquisition is frozen before economic outcomes. It
persisted the official schedule page, release-date index, a 214-row normalized
release CSV and a receipt containing each full-page and target-row hash. All
archive dates and target rows passed, including 36 legacy-title dates, and the
state split is 108 expansion versus 106 contraction. The acquisition artifacts
must reach `origin/main` before the one fixed CP2 aggregation opens.

The first fixed-aggregation invocation was rejected by PowerShell parsing
before its body executed because five diagnostic strings used an undelimited
`$period:` interpolation. The recorded correction changes those strings only to
`${period}:`; no input, reconstruction, metric, gate or verdict changes, and no
economic field or output was opened by the rejected invocation.
