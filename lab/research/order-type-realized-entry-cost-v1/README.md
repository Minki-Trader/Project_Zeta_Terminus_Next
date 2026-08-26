# Order-Type Realized Entry Cost V1

This active source-free Lab family owns Program 3 / micro→meso Unit 073. It compares Passive limit fills with same-symbol Cross market fills on the exact frozen P4 current-spec lifecycle path, using only recorded entry commission/fee, adverse slippage, fill-time spread context and stressed outcome.

The bundle keeps all 119 Passive placed orders in the transfer denominator: 92 became lifecycles and 27 expired without imputed price, cost or P/L. Fill-time quoted spread is descriptive only because the ledger does not preserve every placement-time executable quote or unfilled counterfactual. The unit therefore cannot call literal spread capture or adverse selection from spread alone.

The authoritative pre-outcome contract is `evidence/ORDER_TYPE_REALIZED_ENTRY_COST_DECLARATION_V1.json`, SHA-256 `56A22ADFFBA84DD53DB7010C445FA01EB3CADCAD1833C6329DA11D993ADE9708`. One fixed aggregation, one premetric correction and zero reruns are budgeted, with no new data, runtime, MQL, Tester, broker/account query or Live action.
