# V7 joint log-growth capital allocation

Closed after both unchanged 2025 roles failed the declared drawdown screen. See `REPORT.md` and `evidence/CLOSURE_V1.json`. No confirmation or native path opened; source/model/configuration are frozen.

One serial portfolio question from exact original V7: learn constrained component capital weights from joint calendar-day realized return vectors, then optionally adapt them online. This models simultaneous component losses and geometric wealth directly. The preceding entry-score and continuation-exit bundles remain closed and provide no model, code, parameter or selected seed.

`evidence/DECLARATION_V1.json` owns the full prospective contract. A fitted ONNX graph converts the frozen learned log allocation plus online state into positive allocation scores; an explicit capped normalization enforces the common budget. Online exponentiated-gradient updates use only matured previous-day outcomes. Passive stays at its original size; the other five components share constrained weights.

The first fixed-source-volume/occupancy screen is selection information. It cannot reproduce altered lot rounding, stop geometry, risk admission or compound equity. Only an unchanged survivor may receive its own tester-only V7-derived EA and an adjacent complete real-tick control comparison. Live-Dev is untouched, all state/runtime is isolated and at least 30 GiB stays free.
