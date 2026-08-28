# Portfolio Risk-Cap Envelope V1

Active continuous-optimization campaign derived once from the frozen optimization copy of Live release NEXT-E01-V7-RLO1-b32e7e176f2e.

## Economic question

With all six parent signals, clocks, directions, orders, costs, stops, holds, sizing ladder and portfolio ordering unchanged, does a different pair of per-position and aggregate planned-risk caps improve the whole portfolio?

The complete selection grid is:

- InpMaximumPositionRiskFraction: 0.03 / 0.04 / 0.05
- InpMaximumAggregateRiskFraction: 0.10 / 0.12 / 0.14 / 0.16 / 0.18
- 15 exhaustive combinations, including the parent 0.04 / 0.12

Selection uses 2022-08-01 through 2026-06-01, the first month for which all three required symbols have complete local real-tick files. The latest two completed months, 2026-06-01 through 2026-08-01, are the MT5 custom forward interval and do not select parameters.

The custom economic criterion is robust recovery: the lesser of actual and doubled-cost stressed net divided by the greater of actual equity and stressed closed drawdown. The full result also retains actual/stressed net, both drawdowns, lifecycle count, risk skips, stop exits and component economics.

## Decision

A candidate can replace the parent risk caps only if its selection economics are not dominated by 0.04 / 0.12, its robust recovery improves by at least 5%, it retains at least 90% of parent lifecycles, no parent-positive component becomes nonpositive, and the isolated latest interval improves robust net without worsening robust drawdown. Otherwise retain the parent caps and continue to the next optimization stage.

Only valid complete economic output can reach that decision. Runtime, history, compilation, report, logging, design or engineering faults are CORRECTION_REQUIRED, repaired without an arbitrary count limit and never classified as optimization failure.

This EA is tester-only, owns Magic 260828801..260828806, and uses only the dedicated optimization/runtime/portfolio-risk-cap-envelope-v1-portable/ terminal. It has no Live or Lab authority.

## Result

All 15 selection and all 15 isolated-forward passes completed normally on the frozen implementation and real-tick inputs. The highest custom-score candidate was `0.04 / 0.10`: selection robust recovery improved `11.445184%`, all six parent-positive components stayed positive, and isolated-forward robust net/drawdown improved from `-$2.819 / $18.82` to `+$3.9943 / $14.66`. It retained only `1,902 / 2,119 = 89.759320%` of parent closed lifecycles, below the frozen `90%` gate. The original contract therefore closes `NO_REPLACEMENT_RETAIN_PARENT_0.04_0.12`; this is a valid economic non-replacement, not an environment or engineering failure.

The maximum-profit point was `0.04 / 0.18`: selection actual/stressed net was `$1,166.89 / $1,085.408`, `18.50%` above the parent, with `11.3757%` MT5 equity drawdown and `2,177` lifecycles. Its higher absolute robust drawdown and weaker custom score kept it from replacing the parent under this campaign's original objective, but it remains a non-dominated high-profit frontier observation.

After the result, the user stated a prospective preference for explosive profit under a hard `20%` equity-drawdown budget and requested proxy exploration before any further MT5 run. That new objective does not retroactively change this campaign's frozen gate. The completed 15 combinations will not be rerun. Exact matrices, gate arithmetic and retained frontier evidence are recorded in `evidence/PORTFOLIO_RISK_CAP_ENVELOPE_RESULT_V1.json`.
