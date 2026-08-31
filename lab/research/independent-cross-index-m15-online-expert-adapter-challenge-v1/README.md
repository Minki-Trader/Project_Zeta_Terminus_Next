# Independent Cross-Index M15 Online Expert Adapter Challenge V1

This is Independent V8 Challenge Family 004, allocated to Program 1 (`entry_signal_market_structure`). It asks whether a causal online selector over fixed M15 momentum and reversion experts can create a standalone three-index strategy that beats V8 after observed and doubled cost.

The architecture is mandatory `Python adapter + EA`:

- Python constructs synchronized M15 bars, maintains the frozen expert population, updates each score only after its virtual outcome has fully matured, and emits at most one symbol and direction while the global slot is flat.
- A separate EA must validate adapter freshness and exact symbol contracts, size and submit the selected order, own protection and the four-M15 close, recover state and write bounded evidence.
- A single EA may not own the novel expert decision, and a Python-only proxy cannot claim a V8 Challenge victory.

Families 001-003 features, models, pair states, decisions and outcomes are excluded. Development is 2024-2025; locked 2026 January-July could have confirmed at most one unchanged role. The authoritative contract is `config/challenge-contract.json`.

## Closed verdict

Family 004 is frozen closed as `VALID_DEVELOPMENT_ALL_ROLES_ECONOMICALLY_ADVERSE_NO_CONFIRMATION_NO_EA_NO_MT5_FAMILY_CLOSED`.

The one complete development process evaluated `46,574` candidate decision rows per role over `516` normal days. `ONLINE_HL32 / HL96 / HL256` started `2,063 / 2,234 / 1,625` lifecycles (`3.9981 / 4.3295 / 3.1492` per day), so every role passed turnover and three-symbol breadth. Actual/stressed net was `-$99.3989 / -$163.4354`, `-$99.1503 / -$157.2507`, and `-$97.1707 / -$156.1929`; actual closed-balance drawdown was `99.4286% / 99.2593% / 97.8415%`. Every role lost in both 2024 and 2025.

Complete passer count is zero. The expert population, modes, horizons, half-lives, score/materiality, symbol/time subgroup, risk/capacity and exit bundle may not be rescued inside this family. Locked 2026, EA, compile and MT5 remain unopened. Durable result and closure are `9,408 / 4,098` bytes at `8D58AA29...9D167 / 567D4409...AF511`.
