# Exact V7 return verification

The unchanged V7-RLO1 economic contract passes the predeclared return criteria. The recommendation is to replace V8 with the new V7R identity after the remaining real-account ownership and operational gates. No source or settings were tuned after outcomes.

| Native $100, 1:100 result | V8 control | Exact V7 |
|---|---:|---:|
| 2024-01-01 to 2026-08-01 actual net | +$409.81 | +$313.36 |
| Doubled-cost stressed net | +$367.818 | +$284.138 |
| Native maximum relative equity drawdown | 37.3919% | 19.5024% |
| Robust recovery | 3.29586 | 4.83392 |
| Closed lifecycles | 965 | 1,434 |
| 2026 July-August actual net | +$29.63 | +$4.66 |
| Recent doubled-cost stressed net | +$27.540 | +$3.209 |
| Recent native relative equity drawdown | 17.4037% | 16.2018% |
| Recent closed lifecycles | 55 | 89 |

V7 retains 76.46% of long actual profit and 77.25% of stressed profit, reduces maximum relative equity drawdown by 17.89 percentage points, and improves long robust recovery by 46.67%. Its 2024, 2025 and partial-2026 actual/stressed results are all positive. No drawdown exception is used.

Recent evidence is much weaker: V7 July is -$8.00 / -$8.832 stressed and August is +$12.66 / +$12.041 stressed. V8 July is +$3.14 / +$2.140 stressed and August is +$26.49 / +$25.400 stressed. V7 recent robust recovery is 0.19147 versus V8 1.59007. The frozen recent criterion was pooled positive results without material risk or execution deterioration, not monthly positivity or profit superiority. Native equity DD and maximum planned risk are lower; stressed closed DD rises by only $0.118 (0.79%). All six V7 components, both traded symbols and both directions are active. US100 has a negative subtotal; both direction subtotals are positive. US500 contributes market inputs. July had already been observed and these months are not described as pristine holdout evidence.

All four binding runs have 100% real ticks, identical required contracts at start/end, pinned whole real-tick files and unchanged exact native M1 payloads. Long runs consume 542,461,165 all-symbol ticks; recent runs 89,723,738. Duplicate/partial/dropped closes and safety, persistence, broker, foreign-exposure and protection faults are zero. The twelve long RC4 unavailable observations are complete zero-range bars; no invalid history class remains. The build-6140 compiled binaries are unchanged and both binding pairs execute on the same pinned build-6182 engine. Earlier nonbinding environment/cache corrections remain recorded.

Evidence: `evidence/RETURN_ECONOMIC_DECISION_V1.json` and the complete four-run `evidence/NATIVE_ECONOMIC_RESULTS_V1.json`. The active family remains open only for the user-authorized engineering handoff. Retired V7 state is never resumed; V8 must first provide a fresh stopped-flat boundary. The new EA/dashboard may start entries-disabled while current market ticks are unavailable. Final real new entries still require the existing fresh-tick, synchronization, recovery and 0/0 to 1/1 gates.
