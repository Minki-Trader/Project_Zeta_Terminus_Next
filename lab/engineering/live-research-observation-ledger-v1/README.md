# Live Research Observation Ledger V1

Active serial Lab engineering family declared before implementation. It will be derived once from the frozen CXR2 forward baseline at commit `0d4032786cecb7d7e8a4c3074609db5b105fa107`.

- Purpose: add separate, local, Codex-readable candidate and lifecycle research ledgers.
- Dashboard: unchanged; no dashboard source, snapshot schema or process change.
- Trading behavior: unchanged; no signal, sizing, admission, protection, management, order or cost decision may depend on research I/O.
- Restart: preserve the exact Live execution version, Portfolio, Magic and core state marker/schema/paths; research recovery uses only its own optional A/B state.
- Storage: canonical candidate/lifecycle ledgers are durable research evidence; transient observer state is fixed-size. Repository-wide cleanup follows `docs/OPERATING_DIRECTION.md`.
- Verification: normal MetaEditor compile, one fixed normal MT5 100% real-tick path and later bounded entries-disabled restart observation only. No validator, parity checker, test harness or dashboard change.
- Live boundary: the current CXR2 terminal and dashboard remain untouched until all current-day entry windows and owned lifecycles are complete, then any promotion still requires stopped-flat, entries-disabled recovery and exact `0/0 -> 1/1` handoff.

The declaration under `evidence/` is authoritative for this family until its closure.
