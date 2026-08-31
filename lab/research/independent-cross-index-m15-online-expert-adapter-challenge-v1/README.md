# Independent Cross-Index M15 Online Expert Adapter Challenge V1

This is Independent V8 Challenge Family 004, allocated to Program 1 (`entry_signal_market_structure`). It asks whether a causal online selector over fixed M15 momentum and reversion experts can create a standalone three-index strategy that beats V8 after observed and doubled cost.

The architecture is mandatory `Python adapter + EA`:

- Python constructs synchronized M15 bars, maintains the frozen expert population, updates each score only after its virtual outcome has fully matured, and emits at most one symbol and direction while the global slot is flat.
- A separate EA must validate adapter freshness and exact symbol contracts, size and submit the selected order, own protection and the four-M15 close, recover state and write bounded evidence.
- A single EA may not own the novel expert decision, and a Python-only proxy cannot claim a V8 Challenge victory.

Families 001-003 features, models, pair states, decisions and outcomes are excluded. Development is 2024-2025; locked 2026 January-July may confirm at most one unchanged role. The authoritative contract is `config/challenge-contract.json`.
