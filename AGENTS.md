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
- The legacy Terminus repository is the only permitted adjacent-project reference and only for paths anchored in `CONTINUITY.md` or `lineage/`. Do not inspect or import any other adjacent project.
- `live-dev/` and `lab/` share no compiled code, Include tree, settings, state, logs, or Portable runtime. A verified release moves one way from Lab to a frozen Live package.
- Only `CURRENT_STATE.md` can authorize Next Live-Dev. While it says `DISABLED`, never place a real order or poll broker positions, orders, or deals.
- Preserve old economic and execution identities. V7 uses new identity, Magic, state, settings, and evidence and does not adopt V6R6 positions or state.
- Do not create test-only CLIs, CI, unit/integration/regression tests, validators, parity checkers, promotion checkers, test-only infrastructure, or a project-specific Skill. Use correct compilation, normal MT5 real-tick economic runs, and bounded operating evidence.
- At durable boundaries, commit only the current repository's changes to `main` and push `origin/main`.

