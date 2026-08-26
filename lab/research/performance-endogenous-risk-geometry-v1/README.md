# Performance-Endogenous Risk Geometry V1

This source-free Lab family owns active Program 4 / Unit 069. It asks whether cumulative portfolio performance changes the physical and volatility-normalized stop geometry and stressed cost burden enough to create a broad high-capital versus low-capital stop-hazard feedback.

The one finite bundle reconstructs all 2,233 CP2 lifecycles, derives conservative capital from `planned_risk/0.04`, normalizes initial stop distance by prior 24 completed H1 open-to-open volatility, and compares frozen global capital tails plus within-time-block local capital contrasts. Cost/R dilution and stop-hazard transmission are separate lenses; neither can rescue the other.

The authoritative pre-outcome contract is `evidence/PERFORMANCE_ENDOGENOUS_RISK_GEOMETRY_DECLARATION_V1.json`. No MQL, runtime, acquisition, Tester path, reusable validator, broker/account query or Live action is added. A pass may retain only a separately declared future scale-normalization Lab candidate; this unit cannot change the stop, lot ladder, risk fractions, gates or Live.

## Frozen premetric H1 topology correction

- The first invocation stopped at the immutable H1 physical-row assertion before emitting any capital quantile, geometry, cost or outcome metric. The implementation had divided the export's 24,417 synchronized timestamp rows by three.
- Exact premetric inspection established 24,417 strictly increasing unique physical timestamps. Every row carries nonblank US30, US100 and US500 opens, for 73,251 symbol-price cells; the input hash, bytes, time range, selected columns and prior-24 completed-open formula are unchanged.
- Correction receipt SHA-256 is `31A5B7A4490A38FBF62197DB47393B684FA4B9A1DFBF77FC38504ADB86FBDE63`. The single correction budget is consumed. One successful fixed aggregation and zero correction or metric rerun remain.
