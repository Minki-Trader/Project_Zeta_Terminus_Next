# Live Research Observation Ledger V1

Verified and frozen serial Lab engineering candidate derived once from the frozen CXR2 forward baseline at commit `0d4032786cecb7d7e8a4c3074609db5b105fa107`. It is selected for a later controlled Live promotion but is not the current Live package or owner.

- Purpose: add separate, local, Codex-readable candidate and lifecycle research ledgers.
- Dashboard: unchanged; no dashboard source, snapshot schema or process change.
- Trading behavior: unchanged; no signal, sizing, admission, protection, management, order or cost decision may depend on research I/O.
- Restart: preserve the exact Live execution version, Portfolio, Magic and core state marker/schema/paths; research recovery uses only its own optional A/B state.
- Storage: canonical candidate/lifecycle ledgers are durable research evidence; transient observer state is fixed-size. Repository-wide cleanup follows `docs/OPERATING_DIRECTION.md`.
- Verification: normal MetaEditor compile and one fixed candidate MT5 100% real-tick path passed. A changed broker symbol-specification blob required one adjacent run of the already frozen parent binary under the same current specification; all `2,676` core payload rows and the HTML report were exact. No candidate rerun, validator, parity checker, test harness or dashboard change was added.
- Live boundary: the current CXR2 terminal and dashboard remain untouched until all current-day entry windows and owned lifecycles are complete, then any promotion still requires stopped-flat, entries-disabled recovery and exact `0/0 -> 1/1` handoff.

The declaration, compile receipt and result under `evidence/` are the authoritative frozen record for this candidate.

Compile boundary: MetaEditor build 6140 reported `0 errors / 0 warnings`; compile receipt SHA-256 is `41D66F94CF775D3182AA189E1F20C2FE4A5E0A81AFE25DF4EAE5C0A6AD8E07BD`.

Result boundary: `4,043` candidate rows and `841` lifecycle rows covered all `356` lifecycles with zero dropped research record or core fault. The current-spec candidate and parent both ended at actual/stressed `+$96.24/+$90.2337`, 356 trades, 712 deals, 14 risk skips and 42 stop exits. Result SHA-256 is `CFEE02835808D717344D2082E7B77B8FFB76B2C6CE1C54C4F43B95F340E55C0B`.
