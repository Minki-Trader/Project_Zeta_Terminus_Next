# Order-Type Realized Entry Cost V1

This frozen source-free Lab family owns closed Program 3 / micro→meso Unit 073. It compared Passive limit fills with same-symbol Cross market fills on the exact frozen P4 current-spec lifecycle path, using only recorded entry commission/fee, adverse slippage, fill-time spread context and stressed outcome.

The bundle keeps all 119 Passive placed orders in the transfer denominator: 92 became lifecycles and 27 expired without imputed price, cost or P/L. Fill-time quoted spread is descriptive only because the ledger does not preserve every placement-time executable quote or unfilled counterfactual. The unit therefore cannot call literal spread capture or adverse selection from spread alone.

The frozen verdict is `NO_RECORDED_ORDER_TYPE_COST_SEPARATION_NO_ADVERSE_SELECTION_IDENTIFICATION`. All 221 target fills were cost-known, but recorded commission/fee plus adverse-slippage burden was exactly `0R` for both Cross and Passive. Passive fill-time spread was narrower, while filled mean stressed R was slightly higher and placed-order net slightly lower after 27 expiries; none identifies order-type cost, spread capture or adverse selection. Preserve both order constructions and retain no candidate.

Declaration/result/closure SHA-256 values are `56A22ADFFBA84DD53DB7010C445FA01EB3CADCAD1833C6329DA11D993ADE9708` / `1AA0AA9D3D205DA7A3A91576E2F102BB80109435A74C2ED41A583785D41DB0C3` / `857D4D5CAA256F0C7B8096173B3C97AF74B0661CE4531A0D2E7EE4B41DC15BC1`. One aggregation, zero correction and zero rerun; no new data, runtime, MQL, Tester, broker/account query or Live action occurred.
