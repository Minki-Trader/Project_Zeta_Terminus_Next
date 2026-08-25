# Protective Exit Order Reconciliation V1

Verified and source-frozen self-contained Lab engineering family derived once from the frozen CP2 baseline; controlled Live promotion is pending.

- Unit: `protective-exit-order-reconciliation-019`
- Trigger: Live Pressure stop-loss execution at server `2026.08.25 16:32:01`
- Scope: current-order ownership classification only
- Economic, entry, sizing, risk, protection and exit rules: unchanged
- Live authority: candidate validation first; promotion only after the frozen gate passes

The observed broker-generated stop-loss market order briefly appeared in `OrdersTotal()` before its closing deal. The frozen owner audit treated every owned non-Passive current order as an impossible pending order and latched a false safety stop.

The candidate may recognize only an exact owned stop-loss transit: component Magic and symbol match, order type is market BUY/SELL, reason is SL, a matching local position lifecycle is active, close direction is opposite, volume is exact, and any nonzero `ORDER_POSITION_ID` matches. Every other unexpected order remains fail-closed.

Validation passed: build 6140 compiled at `0 errors / 0 warnings`, and the single frozen P4 real-tick path matched CP2 exactly at `+$96.30` actual, `+$90.4732` stressed, 356 trades, 712 deals, 14 risk skips and 42 stop exits with zero fault.
