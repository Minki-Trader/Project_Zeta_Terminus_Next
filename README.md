# Project Zeta Terminus Next

Project Zeta Terminus Next is the continuity successor to Project Zeta Terminus. It does not restart the research program: it inherits the frozen economic contracts, evidence boundaries, and executable lineage from legacy commit `4c0899255c701e2c6b53e7f44457c431aef2ad76` while replacing the oversized working surface with a concise lineage index and physically isolated Live-Dev and Lab lanes.

`NEXT-E01/V7` is now compiled and fixed-window real-tick equivalent to frozen B70 V6R6. The old Terminus repository remains the sole B70 Live-Dev operator until connected entries-disabled restart evidence, a natural flat handoff boundary, and separate explicit user authorization are complete.

## Start here

Read, in order:

1. [`docs/OPERATING_DIRECTION.md`](docs/OPERATING_DIRECTION.md)
2. [`CONTINUITY.md`](CONTINUITY.md)
3. [`CURRENT_STATE.md`](CURRENT_STATE.md)
4. the active numbered state chunk named by `CURRENT_STATE.md`

## Working surfaces

- `live-dev/`: frozen release packages and Next-only operator tooling. It never imports Lab code.
- `lab/`: modular source, the frozen V6R6 control, tester configuration, research, and economic evidence.
- `lineage/`: complete machine-readable legacy and executable indexes.
- `docs/lineage/`: short human summaries organized by economic research family rather than internal Axis names.

The exact filesystem and Portable-terminal boundary is documented in [`docs/RUNTIME_ISOLATION.md`](docs/RUNTIME_ISOLATION.md).

The equivalence verdict is in [`docs/V7_EQUIVALENCE.md`](docs/V7_EQUIVALENCE.md). The only permitted Live transition sequence is in [`docs/LIVE_HANDOFF_RUNBOOK.md`](docs/LIVE_HANDOFF_RUNBOOK.md).

Live-Dev in this repository is currently `DISABLED`. Running or compiling Lab material does not authorize a real order.
