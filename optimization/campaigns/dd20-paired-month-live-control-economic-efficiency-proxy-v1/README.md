# Paired-Month versus Active Live-Control Economic Efficiency Proxy V1

This isolated Optimization campaign keeps `dd20-paired-month-stability-mt5-v1` fixed as the sole replacement development candidate and asks one same-period economic question: after disclosing its lower turnover and higher native equity drawdown, does it still produce more actual and doubled-cost profit per close and per drawdown percentage point than the exact active Live-derived `0.04 / 0.12` pass-4 control?

The campaign owns byte-pinned copies of the fixed candidate result, the exact control result and the already-closed `4x` cost-resilience result. It performs one source-free aggregation only. There is no parameter grid, forward tuning, MQL or SET change, compile, MT5 run, broker query, candidate promotion or Live mutation.

Two invocations stopped before output: the first exposed a legitimate source-precision mismatch because six control components are displayed to cents while the aggregate retains four decimals; the second exposed a stale config self-pin after that correction. The contract now permits only the mathematical half-cent-per-component rounding envelope, the self-pin is synchronized, and the one valid complete process was not rerun. These were engineering corrections, not economic failures.

The fixed candidate passes every declared efficiency gate. In selection it earns `+$5,786.63 / +$5,477.524` actual / stressed versus control `+$984.69 / +$915.8725`. It closes `1,428` lifecycles versus `2,119`, so full turnover retention is `67.39%`; after excluding the control's `559` Passive closes that the candidate deliberately disables, retention is `91.54%`.

Profit density is materially higher: candidate actual / stressed net per close is `8.72x / 8.87x` control, and net per native equity-DD point is `2.67x / 2.71x` control. All five active candidate components and all six control components are positive on both cost books.

The risk cost is explicit. Candidate selection native equity DD is `20.2569%` versus `9.1948%`, an increase of `11.0621` percentage points (`2.203x`), and its risk-admission skip rate is `11.85%` versus `2.75%`. This unit does not rejudge the already-recorded pragmatic acceptance of the candidate's `0.2569`-point nominal `20%` miss.

In untouched June/July forward the candidate is positive at `+$32.74 / +$30.626` while control is negative at `-$1.11 / -$2.819`. Candidate turnover retention is `64.29%` and its DD is `1.8432` points higher. No ratio is reported against the negative control forward net.

The verdict is `PASS_FIXED_DEVELOPMENT_CANDIDATE_ECONOMIC_EFFICIENCY_WITH_LOWER_TURNOVER_DISCLOSED`. It strengthens the fixed replacement-development case; it does not create a new candidate, authorize another MT5 path or confer Live deployment authority.
