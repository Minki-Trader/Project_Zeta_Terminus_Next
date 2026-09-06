# Family 011 — complete adverse proxy closure

All three frozen exit paths fail development. The normal adapter ran once from the committed preoutcome implementation and reconciled every accepted intent to one close. No role opened 2026 confirmation, an EA or a native runtime.

| Exit rule | Actual profit | Doubled-spread profit | Proxy marked DD | First fills/day |
| --- | ---: | ---: | ---: | ---: |
| HOLD8_CONTROL | $-56.99 | $-65.07 | 70.46% | 1.390 |
| CLOSE_TRAIL_2ATR | $-40.71 | $-84.09 | 73.69% | 2.623 |
| NO_PROGRESS_3B | $-43.95 | $-69.19 | 69.68% | 2.462 |

The three paths use the same 21,573 price-independent hash intents over 520 broker dates. HOLD8, trailing and no-progress paths accept 723, 1,364 and 1,280 first fills respectively; each ends flat. All fail total actual/stressed profit, positive years, drawdown and turnover. Yearly counts, symbol breadth and both directions pass.

The trailing path earns an unstressed $31.247 in 2024, but doubled-spread profit is already -$4.8455, followed by -$79.2417 stressed in 2025. Its greater activity incurs $43.3747 of extra spread stress. The no-progress rule lowers snapshot financing but still loses in both years. The fixed $100 and minimum-lot hard cap reject many FX intents; widening risk or changing symbols after seeing this is outside the frozen bundle.

These are proxy account paths with explicit limitations: historical margin rates and commissions are unavailable, swaps use an attributable snapshot, and H4 open/close marked drawdown does not certify native intrabar equity DD. Those limitations never permit a victory claim. The separate midquote stress also loses for every path. There is no retained seed, alternate hash, horizon sweep, neighboring trail threshold or native allocation.

The frozen [contract](config/contract.json), [binding declaration](evidence/DECLARATION_V2_BINDING.json), [implementation](adapter/run_adapter.py) and [complete closure](evidence/CLOSURE_V1.json) retain all rules and exact artifact hashes. Raw intent, trade, equity and summary files total about 18.4 MB; free space remains above 78 GiB, well above the 30 GiB reserve. Recompare all active macro programs before the next unit.
