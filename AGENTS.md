# Project Zeta Terminus Next Instructions

The sole authoritative policy is [`docs/OPERATING_DIRECTION.md`](docs/OPERATING_DIRECTION.md). If this summary differs, that policy governs.

## Session startup

Before project action, read completely and in order:

1. `README.md`
2. `docs/OPERATING_DIRECTION.md`
3. `CONTINUITY.md`
4. `CURRENT_STATE.md`
5. the active numbered state chunk named in `CURRENT_STATE.md`

Then compare Git state and the relevant Next files and local processes. Do not query broker positions, orders, deals, or account state merely to establish context. Review requests do not authorize implementation.

## Boundaries

- Maintain one active development judgment stream. Do not split migration, axes, or candidate development into concurrent or delegated streams.
- Allocate each Frontier research unit to exactly one primary macro Program 1-5 or 7 under `Macro research allocation`; Program 6 is outside the current Goal. Freeze related variants once as one bundle, close them together, then recompare every active program before opening any successor. Do not continue into an adjacent threshold, window, subgroup, symbol, event, exit, sizing or retained-seed follow-up automatically.
- The legacy Terminus repository is the only permitted adjacent-project reference and only for paths anchored in `CONTINUITY.md` or `lineage/`. Do not inspect or import any other adjacent project.
- `live-dev/` and `lab/` share no compiled code, Include tree, settings, state, logs, or Portable runtime. A verified release moves one way from Lab to a frozen Live package.
- Only `CURRENT_STATE.md` can authorize Next Live-Dev. While it says `DISABLED`, never place a real order or poll broker positions, orders, or deals.
- Preserve old economic and execution identities. V7 uses new identity, Magic, state, settings, and evidence and does not adopt V6R6 positions or state.
- Do not create test-only CLIs, CI, unit/integration/regression tests, validators, parity checkers, promotion checkers, test-only infrastructure, or a project-specific Skill. Use correct compilation, normal MT5 real-tick economic runs, and bounded operating evidence.
- At durable boundaries, commit only the current repository's changes to `main` and push `origin/main`.

## Source topology guard

- Before adding or changing any Lab `.mq5` or `.mqh`, read the `Source topology discipline` section of `docs/OPERATING_DIRECTION.md` and the current baseline declaration in `lab/README.md`.
- Never add or modify MQL source under `lab/mt5/`; it is frozen historical material, not the forward baseline.
- Derive a new experiment by a one-time copy into its own `lab/research/<family>/` or `lab/engineering/<family>/` root. Do not include or link source across Lab family roots.
- Do not add experimental EA wrappers or adapters to the baseline. Close and freeze the active family before naming a successor baseline or opening another family.
