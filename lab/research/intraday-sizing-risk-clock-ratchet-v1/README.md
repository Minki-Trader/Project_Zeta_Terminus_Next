# Intraday Sizing Risk Clock Ratchet V1

This frozen source-free Lab family owns closed Unit 067. It asked whether the once-per-server-day lot multiplier and the per-admission conservative risk-capital calculation materially diverge inside a day, creating a state-dependent ratchet that changes later entry risk and outcomes.

The unit has one finite three-lens bundle: exact source-contract reconstruction at durable `ORDER_ATTEMPTED` decisions, same-day ordinal/floating-state comparison, and downstream filled-lifecycle stop/stressed-R transmission. It uses the full CP2 evidence and the causally complete retained binding journal window independently. It does not select an entry order, time, component or outcome subgroup.

The authoritative pre-outcome contract is `evidence/INTRADAY_SIZING_RISK_CLOCK_RATCHET_DECLARATION_V1.json`. The canonical result and closure are `evidence/INTRADAY_SIZING_RISK_CLOCK_RATCHET_RESULT_V1.json` and `evidence/INTRADAY_SIZING_RISK_CLOCK_RATCHET_CLOSURE_V1.json`. No MQL, runtime, acquisition, Tester path, reusable CLI, broker/account query or Live action was added.

Premetric source review froze one scope correction: the five market components use the once-daily multiplier, while Passive always requests base `0.01` lot. All admissions remained in risk-clock, ordinal, floating-state and outcome views, but only market admissions entered multiplier-divergence metrics and their fixed gate.

The exact capital identity passed in both cohorts, yet the proposed mechanism did not. Median later same-day risk-capital movement was `0` in CP2 and the compounded binding tail; definite equity binding was only `2.46%` and `0%`. Current versus hypothetical market multiplier differed in `0/1,102` CP2 and `4/294` binding later decisions, below the fixed density gate. Negative-floating later decisions were not worse by stressed R or stop rate in either cohort, and no CP2 period passed an adverse transmission path.

Closed `NO_MATERIAL_INTRADAY_CLOCK_RATCHET_PRESERVE_DAILY_SIZING`. Preserve daily sizing, per-admission conservative risk, Passive fixed-volume semantics and current order sequence. Retain no clock-alignment seed, candidate, selector, sizing/risk change or Live action; do not open an ordinal, state, component, time, day-boundary or lot-step rescue.
