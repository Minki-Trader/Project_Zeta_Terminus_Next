# DD20 V8 Clean Monotone Microfrontier Proxy V1

This is the first serial family in the exact-V8 long-horizon rehabilitation program. It asks whether the clean V8 accepted lifecycle path contains a broad, locally stable risk/composition region that materially reduces closed-balance drawdown while retaining most of V8's stressed profit.

## Why this family opens first

The valid clean V2 path earned actual/stressed `+$409.81 / +$367.818`, but its native relative balance/equity drawdown was `35.46% / 37.39%`. The maximum closed-balance drawdown formed early, and the drawdown-window contribution was not a single Cross defect: Return `-$20.68`, Intraday `-$13.37`, RC61 `-$9.16`, Cross `-$2.69`, and RC64 `+$10.44`. A bounded portfolio-risk microfrontier is therefore more attributable than deleting one component after seeing its aggregate result.

## Frozen source and limitation

- The sole economic input is the clean V2 candidate `research-lifecycles.csv`: `1,753,587` bytes, SHA-256 `7C8405F487A0DE96737A22587D0EB2471029CFA337FD4C47C3E1B5E6D62C1791`.
- It contains `965` matched BIRTH/CLOSE lifecycles from `2024-01-02` through `2026-07-31`, actual/stressed `+$409.81 / +$367.818`.
- The campaign stages one byte-equal copy under its own ignored raw-artifact root after this declaration reaches `origin/main`.
- The input contains only lifecycles accepted by exact V8. A lower-risk candidate may have admitted opportunities that V8 blocked, but their economic outcomes are absent. This proxy therefore never credits newly freed capacity and cannot prove native equity drawdown, complete turnover, or MT5 profit.

## Frozen monotone lattice

Component order is RC61 / RC64 / Cross / Intraday / Return / Passive. Passive stays disabled.

- RC61: `1.25 / 1.50 / 1.75 / 2.00`
- RC64: `0.75 / 1.00 / 1.25 / 1.50`
- Cross: `0 / 0.25 / 0.50 / 0.75 / 1.00 / 1.25 / 1.50 / 1.75 / 2.00`
- Intraday: `1.50 / 1.75 / 2.00 / 2.25 / 2.50`
- Return: `0.75 / 1.00 / 1.25 / 1.50`
- Base position-risk fraction: `0.025 / 0.030 / 0.035 / 0.040`
- Aggregate-risk fraction: `0.12 / 0.15 / 0.18`

The Cartesian lattice has exactly `34,560` declared parameterizations. Each component's effective risk is never above exact V8. Volume is a monotone rescaling of the observed source volume, normalized to the `0.01`-lot lattice and capped at the source volume. Planned risk scales with that executable volume, and aggregate admission uses the smaller of replay actual/stressed balance. No candidate receives an unobserved trade.

## Frozen temporal and robustness contract

- Development: close-attributed `2024-01-01 <= time < 2026-01-01`, with 2024 and 2025 separately positive.
- Validation: fresh `$100`, `2026-01-01 <= time < 2026-06-01`.
- Locked holdout: fresh `$100`, `2026-06-01 <= time < 2026-08-01`.
- The exact V8 point must reproduce `965` accepted lifecycles, actual/stressed `+$409.81 / +$367.818`, and the clean closed-balance drawdown within declared tolerance before any candidate outcome is valid.
- Primary development eligibility requires at least `80%` of V8 stressed net, raw closed-balance drawdown at or below `27%`, positive actual/stressed net and positive balance. If no primary point exists, the predeclared rehabilitation tier requires at least `75%` of V8 stressed net and at least `5.0` percentage points less drawdown than V8.
- A robust point needs at least four immediately adjacent eligible lattice neighbors spanning at least three parameter axes. Ranking uses the worst local stressed-net-to-drawdown efficiency first, then own stressed net, lower drawdown and smaller distance from exact V8. At most three separated plateau centers enter validation.
- Validation chooses one winner only if it stays actual/stressed positive, balance-positive and at or below `30%` raw closed-balance drawdown. The locked holdout then confirms or rejects that same winner; no alternate is substituted after holdout.
- One MT5 finalist exists only if the unchanged winner is positive in validation and holdout, retains at least `75%` of exact-V8 whole-path stressed net, and improves whole-path closed-balance drawdown by at least `5.0` percentage points. Otherwise MT5 count is zero.

## MT5 budget and authority

This family may consume at most two valid MT5 economic paths: one exact contemporaneous V8-derived control and one unchanged proxy finalist. Proxy nonconfirmation consumes none. Environment or engineering correction does not expand the economic lattice. No output changes or restarts Live, and Optimization has no direct Live promotion authority.

At this declaration boundary source, configuration, staged input, proxy implementation and outcomes remain unopened. They may begin only after the declaration commit reaches `origin/main`.
