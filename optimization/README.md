# Independent Live-Dev Optimization

This root owns continuous economic optimization of the exact active Live-Dev behavior. It is physically and logically separate from both `live-dev/` and `lab/`.

## Fixed parent

- Source release: `NEXT-E01-V7-RLO1-b32e7e176f2e`
- Source root at derivation: `live-dev/package/active/`
- Local frozen copy: `baseline/NEXT-E01-V7-RLO1-b32e7e176f2e/`
- Source commit at derivation: `f4e1effb647d5ef81921eddc64fcd6bef2289f57`
- Frozen manifest: `7A968666241AD90629F14ADF48E983AB04A4DD88053F1413EBB209FB51976698`
- Status: exact 20-file baseline frozen; first campaign compiled with economics unopened

The local baseline is never compiled or executed with Live identity. It is copied once so later campaign work no longer depends on a Live or Lab path.

## Root roles

- `baseline/`: byte-pinned, read-only copy of the active Live package used only for campaign derivation.
- `campaigns/<family>/`: one self-contained active or frozen optimization campaign, including source, configuration and small durable evidence.
- `runtime/<family>-portable/`: Git-ignored dedicated physical MT5 Portable; never the Master, Live or Lab terminal.
- `artifacts/raw/<family>/`: Git-ignored large optimization reports, logs and caches that durable evidence may pin and preserve.
- `artifacts/temp/`: replaceable staging only.

## Operating rules

Only one optimization judgment stream is active. A complete valid economic comparison may judge improvement; missing history, runtime/configuration failure, design defect or engineering defect is corrected and rerun without an arbitrary retry cap and without an economic verdict. The latest two completed months remain isolated from search by default.

One completed campaign does not pause the Goal. After each economic stage, freeze its evidence, choose the next economically distinct optimization stage and continue until the user pauses. A temporary Lab Unit is optional when a new clue needs research or engineering, but it pauses this stream and closes before optimization resumes.

No optimization result changes Live automatically. Any later promotion requires explicit user authorization and a separately named Lab engineering handoff under `docs/OPERATING_DIRECTION.md`.

## Active campaign

`campaigns/portfolio-risk-cap-envelope-v1/` owns the first exhaustive 15-point comparison of the existing per-position and aggregate planned-risk caps. Its source, configuration and final build are frozen by `evidence/PORTFOLIO_RISK_CAP_ENVELOPE_IMPLEMENTATION_FREEZE_V1.json`; the dedicated runtime remains Git-ignored under `runtime/portfolio-risk-cap-envelope-v1-portable/`.
