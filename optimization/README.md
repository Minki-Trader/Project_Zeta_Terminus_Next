# Independent Live-Dev Optimization

This root owns continuous economic optimization of the exact active Live-Dev behavior. It is physically and logically separate from both `live-dev/` and `lab/`.

## Fixed parent

- Source release: `NEXT-E01-V7-RLO1-b32e7e176f2e`
- Source root at derivation: `live-dev/package/active/`
- Local frozen copy: `baseline/NEXT-E01-V7-RLO1-b32e7e176f2e/`
- Source commit at derivation: `f4e1effb647d5ef81921eddc64fcd6bef2289f57`
- Frozen manifest: `7A968666241AD90629F14ADF48E983AB04A4DD88053F1413EBB209FB51976698`
- Status: exact 20-file baseline frozen; first 15-point risk-cap campaign completed with valid economics

The local baseline is never compiled or executed with Live identity. It is copied once so later campaign work no longer depends on a Live or Lab path.

## Root roles

- `baseline/`: byte-pinned, read-only copy of the active Live package used only for campaign derivation.
- `campaigns/<family>/`: one self-contained active or frozen optimization campaign, including source, configuration and small durable evidence.
- `runtime/<family>-portable/`: Git-ignored dedicated physical MT5 Portable; never the Master, Live or Lab terminal.
- `artifacts/raw/<family>/`: Git-ignored large optimization reports, logs and caches that durable evidence may pin and preserve.
- `artifacts/temp/`: replaceable staging only.

## Operating rules

Only one optimization judgment stream is active. A complete valid economic comparison may judge improvement; missing history, runtime/configuration failure, design defect or engineering defect is corrected and rerun without an arbitrary retry cap and without an economic verdict. The latest two completed months remain isolated from search by default.

Optimization candidates are not Live EA edits and may be economically radical: a campaign may remove or replace strategies, reconstruct portfolio membership or coordination, and run destructive variants. Every such comparison retains an exact Live-derived control, owns separate source/identity/runtime/output, remains distinct from Lab research, and has no Live authority.

One completed campaign does not pause the Goal. After each economic stage, freeze its evidence, choose the next economically distinct optimization stage and continue until the user pauses. A temporary Lab Unit is optional when a new clue needs research or engineering, but it pauses this stream and closes before optimization resumes.

No optimization result changes Live automatically. Any later promotion requires explicit user authorization and a separately named Lab engineering handoff under `docs/OPERATING_DIRECTION.md`.

## Active campaign

`campaigns/portfolio-risk-cap-envelope-v1/` is closed `NO_REPLACEMENT_RETAIN_PARENT_0.04_0.12`. Its 15 selection and 15 isolated-forward passes are preserved without rerun. The same result retained `0.04 / 0.18` as a non-dominated maximum-profit frontier point: selection actual/stressed net `$1,166.89 / $1,085.408`, MT5 equity drawdown `11.3757%`.

The user's prospective objective is now maximum actual and doubled-cost-stressed profit inside a hard `20%` MT5 equity-drawdown budget. `campaigns/dd20-profit-frontier-proxy-v1/` is the active serial stage. It exhaustively explores six-component allocation weights over the copied `0.04 / 0.18` lifecycle stream and may produce at most three candidates before any further MT5 real-tick execution.
