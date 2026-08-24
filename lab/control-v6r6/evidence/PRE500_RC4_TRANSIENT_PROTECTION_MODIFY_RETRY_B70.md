# RC4 Transient Protection-Modify Retry B70

Date: 2026-08-23

Decision: `PASS_AS_INDEPENDENT_V6R6_DEV_OPERATIONAL_HARDENING; LIVE_DEPLOYMENT_NOT_AUTHORIZED; NORMAL_HISTORY_EXACT_B67_REGRESSION; TRANSIENT_RETRY_BRANCH_NOT_NATURALLY_EXERCISED`

## Result

B70 makes the accepted B48 RC4 stop compression resilient to one closed set of transient or outcome-ambiguous synchronous broker failures. It first reconciles the same V6R6-owned position and broker stop. If the exact target is already present, it adopts it without another request. If the unchanged original stop remains, it durably records one retry right and consumes that budget before submitting the identical target once on the first strictly later fresh causal US30 tick. It never recalculates, widens or repeats the target.

This is an independent V6R6 DEV operational successor, not a new economic action. B48's votes, eight-M30 checkpoint, 25%-remaining-loss target, original stop and deadline stay frozen. B67's activation seal, cursor, shadow occupancy and gap recovery also stay frozen.

## Frozen cycle contract

- Strategy: RC4 only.
- Checkpoint: the first non-successful synchronous result after the durably journaled B48 `PositionModify` request.
- Retryable closed set: `REQUOTE`, `TIMEOUT`, `PRICE_CHANGED`, `PRICE_OFF`, `TOO_MANY_REQUESTS`, `LOCKED`, `CONNECTION`.
- Reconciliation: require exactly one same-identifier V6R6 RC4 position and classify the broker stop as exact target, unchanged original or mismatch.
- Sole action: one exact-target resubmission on the first strictly later fresh causal US30 tick after ownership, session and stop-legality recheck.
- Target already applied: adopt without another request.
- Nonretryable result, failed retry or illegal first later tick: preserve original protection as explicit `HOLD`.
- Position closes while a request is unresolved: reconcile the owned deal sequence; never resurrect the retry.
- Ownership or stop mismatch: fail closed.
- Excluded changes: entry signal, opportunity, timestamp, direction, volume, vote, compression fraction, original stop, deadline, shadow economics, order cost and every other strategy.

The one execution-time precheck found zero future leakage, quote mixing in retry eligibility, entry change, cost error or ownership conflict. It found and corrected unresolved-position close reconciliation, target-stop shadow recognition while retry intent is pending, and missing bounded retry telemetry before the final compile and before either tester run. The later combined result check was performed once.

## Independent identity

- Execution version: `zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry`
- Portfolio ID: `ZT-PORT-PRE500-FR6R6-RC4MR-cda6e28b13f4`
- Magic Numbers: `260823301..260823306`
- Source SHA-256: `7B98E33E093502DD1E582FA53260E06AD6BEA5820C74CDEEC691239F701446AA`
- EX5 SHA-256: `C5E569092B492F350A0B47DBF060A82293A302002F73A842FA52465BE2716E92`
- SET SHA-256: `BEBA34FE89B01EC4F1582C2C1EA4BC02E8FB73E0D78B78BAB833EEC63F8065E8`
- Latest/binding INI SHA-256: `0D941C08E240FCBE4546E0378D7DC42A54957487AC5578438C4A3F2734A0942D` / `6782F85ED9A0E3934FFF4891860669AEFC0C6CF74DC89E6FB4F953E7576F757F`
- Declaration SHA-256: `C0011C3AEDF00385B55E55AF87B89DA686672D3EBFF8BA9C52C2AED7596D476F`
- Validation SHA-256: `43EB5050C756CCBBD4861618C1D2F565B0E3DBBC7117F605709F4E293F0136E5`
- MetaEditor build 6090: `0 errors, 0 warnings`

V5, B48, B49, B52, B66, B67 and B70 retain separate source, EX5, Portfolio ID, Magic range, state/current/event/lock paths, settings and evidence. B70 imports or adopts none of their state or positions.

## Paired real-tick regression

| Evidence | Latest two completed months | Binding long |
|---|---:|---:|
| Period | 2026-06-01..2026-07-31 | 2022-08-01..2026-08-20 |
| First fills / trading deal rows | 84 / 168 | 2,235 / 4,470 |
| Actual net / final balance | `-$1.1100 / $98.89` | `+$1,019.0400 / $1,119.04` |
| Balance / equity max DD | `$15.25 / $20.01` | `$146.04 / $153.59` |
| Fixed-2x net / closed DD | `-$2.8190 / $16.6700` | `+$940.6585 / $149.1695` |
| RC4 checkpoints / adverse / compression / refusal | `5 / 3 / 2 / 1` | `189 / 70 / 47 / 23` |
| Retry intent / attempt / success / adoption / HOLD | `0 / 0 / 0 / 0 / 0` | `0 / 0 / 0 / 0 / 0` |
| Retry pending / consumed at end | `false / false` | `false / false` |
| Activation seal eligible / sealed | `1 / 1` | `25 / 25` |
| Cursor checkpoint eligible / persisted | `2 / 2` | `89 / 89` |
| Safety/persistence/broker/ownership/protection fault | `0` | `0` |

After normalizing only the intended system identity row, the complete B70 reports are exact to B67: `411/411` latest rows and `9,118/9,118` binding rows. Normalized order/deal sections remain `179/171` and `4,584/4,473`, with zero nonidentity difference. Entry identities, order and deal paths, actual after-cost results, fixed-2x results, and balance/equity/stressed drawdowns therefore remain exact.

Latest processed `14,245,014` US30 ticks and `137,630,654` all-required-symbol ticks in `1:07.353`. Binding processed `148,594,189` US30 ticks, `47,858` bars and `678,568,654` all-required-symbol ticks in `20:02.860`. Both used isolated writable build-6140 portable runtimes with `Model=4` and `AllowLiveTrading=0`. All B70 processes exited naturally; user PID `28556` was untouched.

## Decision and direct-evidence limit

B70 supersedes B67 only as the leading independent RC4 DEV operational implementation. B67 remains the frozen causal parent, B48 remains the economic parent, and accepted V5 remains the sole operational identity and is stopped. B70 is not attached, combined, deployed or authorized for Live management.

The frozen histories contained no qualifying transient modify failure. The clean `0/0/0/0/0` retry counters prove that the added state machine is economically inert on the normal paths and terminates cleanly, but they do not prove a live broker retry success. No failure was synthesized, and the unchanged economic runs will not be repeated to manufacture one.

Machine evidence: [`../mt5/artifacts/summaries/pre500_rc4_transient_protection_modify_retry_validation_v1.json`](../mt5/artifacts/summaries/pre500_rc4_transient_protection_modify_retry_validation_v1.json)

## Current six-strategy management table

| Strategy | Current management |
|---|---|
| RC16 | Accepted-V5 `HOLD`; B65 release-risk and B68 unmasking actions ended |
| RC4 | B70 V6R6 DEV-only transient-modify retry retaining frozen B48/B67 economics; B67 is the frozen predecessor |
| Cross | Accepted-V5 `HOLD`; B64 Treasury handoff action ended |
| Pressure | Accepted-V5 `HOLD`; B63 claims-release action ended |
| Return | Accepted-V5 `HOLD`; B61 EIA repricing action ended |
| Passive | Accepted-V5 state-responsive `HOLD`; B69 same-direction handoff extension ended |

## Next single task

B71 is `Pressure Half-Life Cross-Index Breadth Contradiction Exit`.

Freeze every accepted Pressure opportunity, entry identity and timestamp, Long/Short direction, source volume, catastrophic stop and fixed eight-M30 exit. At the first synchronized completed US100/US30/US500 H1 boundary at or after four held Pressure-native M30 bars, compare US100 and US500 displacement from the last synchronized completed H1 close no later than the frozen entry. If both peer displacements are strictly opposite the held Pressure direction, close Pressure once at the first valid US30 executable-side quote strictly later and within five seconds; otherwise explicit `HOLD`. The paired control preserves the identical accepted path and costs.

This is a single cross-market breadth invalidation, not Pressure's own native-feature compression, opening-auction escape, peer realized-loss event, scheduled claims exit or a renamed magnitude threshold. P/L, MFE, MAE, US30 native state, peer weights, contradiction magnitude, persistence, volatility, session, direction subset, later H1 checkpoints and alternate actions are excluded. A support cell below three actions ends before marks or outcomes; any supported cell with nonpositive actual or fixed-2x delta or worsened actual or stressed closed DD ends the right without rescue.
