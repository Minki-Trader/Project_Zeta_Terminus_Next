# Joint log-growth allocation: closed on drawdown nonconfirmation

One 2024 fit used 554 completed trades across all 366 calendar days, including 118 days without a close. SLSQP converged in 25 iterations. Learned weights in RC16/RC4/Cross/Pressure/Return/Passive order are 1.047455/1.452545/2/0.25/0.25/1. Both static and daily online roles completed all 557 original 2025 trades without retuning.

| Fixed original basket selection | Equal V7 | Frozen ONNX | Online ONNX |
|---|---:|---:|---:|
| Actual net | $127.8900 | $138.0381 | $134.5873 |
| Stressed net | $118.6090 | $126.4273 | $123.0054 |
| Closed-balance DD | 15.5200% | 19.3931% | 19.2072% |

Both calendar halves remain positive. Frozen allocation increases stressed net by about 6.59%, but its closed DD rises about 24.96%, above the fixed 10% relative tolerance. Online allocation increases stressed net by about 3.71%, below its 5% gate, and also exceeds the DD tolerance. Both roles close without a survivor, adjacent cap/penalty/gradient rescue or retained seed.

These are fixed-source basket screening numbers, not a native candidate equity path. Scaling historical cash cannot establish actual volume rounding, risk admission, stop geometry, own-label evolution or compound profit. No 2026 candidate values, candidate EA, native path or Live change occurred. Preserve model, daily allocations, original input and both complete trade tapes. The user's broader V7 work remains active with more than 56 GiB free.
