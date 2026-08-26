# Intraday Sizing Risk Clock Ratchet V1

This source-free Lab family owns active Unit 067. It asks whether the once-per-server-day lot multiplier and the per-admission conservative risk-capital calculation materially diverge inside a day, creating a state-dependent ratchet that changes later entry risk and outcomes.

The unit has one finite three-lens bundle: exact source-contract reconstruction at durable `ORDER_ATTEMPTED` decisions, same-day ordinal/floating-state comparison, and downstream filled-lifecycle stop/stressed-R transmission. It uses the full CP2 evidence and the causally complete retained binding journal window independently. It does not select an entry order, time, component or outcome subgroup.

The authoritative pre-outcome contract is `evidence/INTRADAY_SIZING_RISK_CLOCK_RATCHET_DECLARATION_V1.json`. No MQL, runtime, acquisition, Tester path, reusable CLI, broker/account query or Live action is added.

Premetric source review froze one scope correction: the five market components use the once-daily multiplier, while Passive always requests base `0.01` lot. All admissions remain in risk-clock, ordinal, floating-state and outcome views, but only market admissions enter multiplier-divergence metrics and their fixed gate. No result has opened. A complete pass may retain one later separately declared Lab clock-alignment candidate; it cannot change sizing, risk, lot, stop, priority, admission or Live behavior by itself.
