# Project Zeta Terminus Next Current State

Last updated: 2026-08-24

## State record

- Active chunk: [`state/CURRENT_STATE-0001.md`](state/CURRENT_STATE-0001.md)
- Latest state ID: `STATE-0004`
- Legacy migration anchor: `4c0899255c701e2c6b53e7f44457c431aef2ad76`

## Authorization

- Development: `ENABLED`, one serial stream only
- Next Live-Dev authorization: `DISABLED`
- Next V7 entries-disabled preflight: not yet eligible
- Next V7 new-entry authorization: `DISABLED`
- Existing real-account owner: legacy Terminus B70 V6R6 only

No Next EA, Portable Live runtime, Portfolio ID, state namespace, position, order, or deal exists. Running Lab code never changes this authority.

## Active work

- Active engineering boundary: `NEXT-E01` fixed-window V6R6/V7 real-tick equivalence
- Frozen parent: B70 V6R6
- V7 release ID: `NEXT-E01-V7-2db5ef5ead1c`
- V7 Portfolio ID: `ZT-PORT-NEXT-V7-2db5ef5ead1c`
- V7 Magic: `260824701..260824706`
- Required isolation: Live-Dev and Lab share no source Include tree, EX5, settings, Portable runtime, state, or logs
- B75: paused, unopened, and unchanged until migration completion

## Completed migration evidence

- Complete tracked-file manifest: `lineage/legacy-files.jsonl`, 1,475 records
- Complete scoped research index: `lineage/research-lineage.jsonl`, 1,011 records
  - research source: 359
  - human research document: 56
  - summary JSON: 596
- Human economic-family summaries: `docs/lineage/`
- Executable ancestry: `lineage/executable-lineage.json`
- Frozen B70 control: `lab/control-v6r6/`, eight files verified against its manifest
- Lab Portable: local MT5 build 6140 with copied US100/US30/US500 real-tick data
- Live Portable shell: local MT5 build 6140, no account/broker cache and no executable V7 release
- Modular V7: 14 include modules plus assembly EA, MetaEditor build 6140 `0 errors / 0 warnings`
- V7 EX5 SHA-256: `0A722406921F76259E4828D87915C2BA6F2F345A4059CC310EEC4BC446011B53`
- V7 evidence status: economic equivalence not yet established; Live remains disabled

## Required completion evidence

1. concise human lineage summaries and complete hash-anchored legacy indexes
2. independent Live-Dev and Lab runtime/package structure
3. modular V7 compile with zero errors and warnings
4. exact fixed latest and binding real-tick behavior after identity normalization
5. bounded entries-disabled restart, ownership, reconciliation, and dashboard evidence
6. flat handoff and separate user authorization before any V7 real order

## Current verdict

`MIGRATION_IN_PROGRESS; NEXT_LIVE_DISABLED; LEGACY_B70_UNCHANGED`
