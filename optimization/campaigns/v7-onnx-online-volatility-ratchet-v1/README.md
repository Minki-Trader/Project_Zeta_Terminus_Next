# V7 learned volatility ratchet — closed

This isolated Program 4 campaign retains the original V7 entries, initial risk,
quantity staircase and mandatory exits. A fresh ONNX model estimates the 90th
percentile of the next completed M30 adverse quote excursion. Favorable quotes
observed after entry can move a protected stop into profit; the stop never moves
backwards and the original admission risk remains reserved.

The model uses only original native US30/US100 price bars. Its 2024 fit and all
static/online update rules were fixed before the 2025 selection. Online labels
become usable strictly after the next M30 interval completes. Both directions
and both symbols retain their full market calendar, including missing inputs.

All 557 original 2025 lifecycles remain in fixed-volume selection. Static
actual/stressed net was $132.6007/$123.3187 against the original
$127.89/$118.609; online was $130.0105/$120.7285. Both qualified, and the declared
ranking selected **static only**. These numbers describe selection at original
volumes and occupancy. They do not establish native compounding or equity DD.

The native comparison uses new tester-only `ZetaV7VRControl` and
`ZetaV7VRStatic` sources, independent identities and mutable paths, and one own
physical Portable. The selected model, compiled source and settings are frozen
before the full 2025-01-01 through 2026-09-01 comparison. There is no alternate
finalist or neighboring parameter rescue after confirmation.

The candidate persists its original stop, favorable peak, expected stop,
pending modification and consumed bar in its own A/B core state. Only the exact
saved or pending stop for that position can use the profit-side protection
branch. Original ARC cannot loosen a tighter ratchet; a previously compressed
RC4 position retains its original shadow semantics.

Both roles record minute equity extrema from every delivered EA tick, account
balance, known stressed cash and the daily quantity multiplier. Full tester DD
is the native `TesterStatistics` value. The extra path is operating evidence
and never feeds an order decision.

The first two complete controls are excluded from comparison because the
current-year HCC and current-month TKC containers refreshed between runs. Their
complete outputs remain under `correction-01-native-history/control-attempt01/`
and `correction-02-native-history/control-attempt02/` in the own raw root.
The second full run reproduced the first economics, but this does not establish
input identity and gives neither run comparison authority.

`NATIVE_HISTORY_CORRECTION_V2.json` prospectively fixes input acquisition over
2024-01-01 through 2026-09-01 exclusive, covering every warmup and test minute.
The normal `acquire_native_history.py` producer records all eight original M1
fields for US30, US100 and US500 before, between and after the unchanged native
pair. It uses the own no-EA reader and historical bars only. Complete fixed-window
values, exercised 202401-202608 monthly tick files, platform, symbol DB and all
source/model/settings must match. Current annual/monthly container fingerprints
remain diagnostic records. No fixed history drift is excused by a calendar
argument, and neither excluded control is retroactively admitted.

This correction changes no selected model, trading behavior, trial interval,
capital, native gate or finalist. The complete unchanged pair is now closed: candidate actual/stressed net
$192.65/$174.449 versus $259.17/$239.7141, with equity DD 14.8971% versus
16.0732%. Lower DD and positive epochs do not compensate for reduced wealth and
recovery. See `RESULTS.md`, `NATIVE_PAIR_BINDING_V1.json` and `CLOSURE_V1.json`.
The whole static/online bundle has no passer or retained seed.

The campaign has no Live authority. All Live files, processes and user-operated
permissions remain outside this work. The 30 GiB storage reserve still applies.
