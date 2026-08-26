# Portfolio Drift Benchmark Attribution V1

This source-free Lab family owns active Unit 065. It asks whether the frozen six-strategy portfolio retains material economic value after its exact lifecycle exposure geometry is translated into a causal US30/US100 market benchmark and that benchmark is scaled to the portfolio's actual Tester equity drawdown.

The unit has one finite bundle: exact entry-notional exposure integration, daily signed-market attribution, and drawdown-matched signed/gross passive hurdles. It also reports the exact Tester equity-versus-balance drawdown gap because the benchmark is matched to equity risk rather than the previously used closed-balance path.

The authoritative pre-outcome contract is `evidence/PORTFOLIO_DRIFT_BENCHMARK_ATTRIBUTION_DECLARATION_V1.json`. All lifecycle, report and H1 inputs are immutable previously consumed exploratory evidence. The unit adds no MQL, runtime, market-data acquisition, Tester path, reusable analysis CLI, account/broker query or Live action.

The first aggregation invocation stopped before any economic metric because the implementation treated Passive like a market `OPEN` lifecycle. `PORTFOLIO_DRIFT_BENCHMARK_ATTRIBUTION_PREMETRIC_CORRECTION_V1.json` freezes the single permitted correction: market components still begin at `OPEN`, while Passive begins at `PASSIVE_FILL` using its matched `PASSIVE_PLACE` direction, stop and planned risk; `PASSIVE_EXPIRE` clears the pending record without exposure. The declaration, population, formulas, gates and verdict rules are unchanged, and all Unit 065 metrics remain unopened.

No result has opened. The family may change only future research interpretation if the frozen benchmark gate passes; it cannot revise a prior source unit, select a trade, remove a component, create a passive sleeve or authorize promotion.
