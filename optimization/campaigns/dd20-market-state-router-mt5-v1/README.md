# DD20 Market-State Router MT5 V1

This tester-only Optimization campaign materializes the one exact seed retained by Lab Unit 099, `EXACT_QUARTERLY_POOLED_RIDGE_ROUTER_ON_PAIRED_MONTH_ANCHOR`. The seed came from Live-derived legacy evidence pinned through the permitted lineage, but its implementation, runtime, state and outputs are wholly owned by this campaign. It has no promotion authority over Live or Lab.

## Why native MT5 is required

The qualified anchor candidate ledger contains `12,265` rows, of which `7,352` are `GATE/EXISTING_EXPOSURE` rows with no observable signal. Blocking an earlier entry changes later component occupancy, exposes previously hidden signals, changes the virtual labels and quarterly model, and changes later admission ranks. A source-free subtraction cannot preserve that recursive path. Unit 099 therefore retained exactly one native-path seed rather than inventing proxy economics.

## Frozen control and candidate

- Frozen Optimization baseline: `optimization/baseline/NEXT-E01-V7-RLO1-b32e7e176f2e/`.
- Qualified control: `dd20-paired-month-stability-mt5-v1`, with selection actual/stressed `+$5,786.63 / +$5,477.524`, native maximum relative equity DD `20.256887565%`, and all four selection epochs positive.
- Control full pair: actual/stressed `+$32.74 / +$30.626`, native maximum relative equity DD `18.675302130%`; June `+$33.33 / +$32.109`, July `-$0.59 / -$1.483`.
- Reference capital `$100`, base volume `0.01`, addition step `$150`, maximum position/aggregate planned-risk fractions `0.04 / 0.18`, unmodelled-risk reserve `0.25`, stop-placement headroom `0.25`.
- Component multipliers remain `2 / 1.5 / 2 / 2.5 / 1.5 / 0` for range-16 / range-4 / US100 cross / US30 pressure / US30 return / US100 passive. Passive stays disabled and is not routed.
- The router owns independent virtual books for the five active components. Their fixed bar holds are `8 / 12 / 4 / 8 / 6` on `M30 / M30 / H1 / M30 / H1`.
- Every virtual label uses a fixed `0.01` volume and entry/exit spread stress. Ten features comprise clipped signal magnitude, absolute magnitude, direction, weekday sine/cosine and five component indicators.
- One expanding pooled Ridge model uses alpha `10`, labels clipped at the expanding `2% / 98%` quantiles, minimum `80` total and `8` per-component samples, and calendar-quarter refits. A signal is admitted at its component-relative predicted-net percentile `>=0.25`; pre-fit warmup admits it.
- Router and core must agree on component, bar, direction and feature. A mismatch engages the existing safety stop and invalidates the run.

No grid, nearby percentile, hold, feature, alpha, component, direction, threshold, risk, volume or retained-seed rescue belongs to this campaign.

## Isolation and identity

Source is a one-time physical derivation from the frozen Optimization baseline into this campaign's own `mt5/` tree. It does not include or link Live, Lab, the legacy repository or another Optimization campaign.

- EA and Include root: `ZetaDD20MSR1` / `ZetaOptimizationDD20MSR1`.
- Execution/release/portfolio: `zt-opt-live-v7-dd20-market-state-router-mt5-v1` / `OPT-LIVE-V7-DD20MSR1-20260829` / `ZT-OPT-LIVE-V7-DD20MSR1-20260829`.
- Schema and Magic: `opt-dd20-msr-mt5-1`, `260829921..260829926`.
- State, research, router ledger, SET, report and physical Portable paths are unique to this campaign.
- The dedicated runtime is `optimization/runtime/msr1-portable/`; it is never the Master terminal.

## Frozen economic path

Run exactly one build-6140 real-tick selection from `2022-08-01` through `2026-06-01`. A valid run must stop normally, report `100% real ticks`, produce complete native and EA economics, and end with zero safety, persistence, broker, foreign-exposure, protection, research-output, router-output or router/core mismatch fault.

Selection must strictly exceed both control profit figures, keep actual and stressed net positive in all four chronological epochs, and remain balance-positive. Nominal DD20 qualification requires native maximum relative equity DD `<=20%`. Under the user's pragmatic DD instruction, a result above `20%` but no higher than the currently accepted `20.256887565%` control may still proceed only if both profit measures strictly improve; anything above the accepted control DD cannot qualify.

Only a selection result passing that frozen effective gate may open one forward invocation. The forward invocation starts from `2022-08-01` solely to warm the causal router and keeps the core economically inactive until `2026-06-01`; it then measures one fresh `$100` June-July account through `2026-08-01`. Full-pair and separate June and July actual/stressed net must all be positive, and native maximum relative equity DD must be `<=20%`. The exact comparison to the control months must be disclosed.

Compilation, invocation, history, output or design defects are engineering correction states with no economic verdict and no arbitrary retry limit.

## Implementation freeze before economics

The campaign owns `17` MQ5/MQH source files totaling `451,264` bytes with canonical manifest `06D55DF682E6FCAB658581E5EBC5D9FBF1A2FB36370543A8A2680D524C55CD9A`. Its two SET and two INI files total `3,817` bytes with manifest `20A04ABBF6EA396C0658EBF9E8FA25EA9AAAFCADB609D31602D4191BD3E54A3C`.

All `19` source/SET files and both INIs match their dedicated runtime overlays byte-for-byte. One MetaEditor build 6140 invocation completed in `2,843 ms` with `0 errors / 0 warnings`; the launcher returned `1` while the same invocation wrote the complete log and expected EX5, so no recompile was performed. The compile log is `17,712` bytes with SHA-256 `B4A8F6F40B655A80D9472B65CB1452EE96F2FEF0BEBCD6BFD0D7424BA88B6B16`. The EX5 is `248,878` bytes with SHA-256 `30571A969D52EBBDA006B9606ED69BA44EC7F41DD05296599C8B539A0ABE6FE5` and matches the runtime copy.

At freeze time the dedicated report directory was empty and no terminal or MetaEditor process owned the runtime. Economic output remained unopened.

## Closed result

Exactly one selection invocation completed normally in `1,423.98` wall seconds. It used build 6140 real ticks, reported `100% 실제 틱`, generated `45,160` bars and `132,257,500` primary-symbol ticks, and preserved complete report, native cache, EA lifecycle/candidate/state, router and log evidence. Safety, persistence, broker, foreign-exposure, protection, research-drop, router fit, router/core mismatch and router-output faults are all zero.

The router completed `1,620` independent virtual lifecycles and made `16` quarterly fit attempts, of which `14` produced a model and zero failed. Warmup covered `171` signal rows; `1,449` later rows used a fitted model. It allowed `1,243` and blocked `377` signals, a `23.271605%` block rate. The core consulted the same `1,620` decisions with zero missing, occupied or mismatched decision.

Selection actual/stressed net is only `+$914.29 / +$869.242` across `1,242` closed lifecycles. That trails the qualified control by `$4,872.34 / $4,608.282`, or `84.199957% / 84.130750%`, retaining only `15.800043% / 15.869250%` of control profit. All four epochs remain positive—E1 `+$111.50 / +$104.9875`, E2 `+$49.82 / +$44.1675`, E3 `+$254.50 / +$243.841`, E4 `+$498.47 / +$476.246`—and all five active components remain positive.

Reported maximum relative MT5 equity DD falls to `12.52%`, `7.736887565` percentage points below the control. Both DD gates therefore pass, but both mandatory profit-improvement gates fail by a very large margin. This is valid economic nonconfirmation: the fixed-hold pooled rank removes too much shared-account contribution even though its virtual books are positive. No threshold, label, hold, feature, model, component or percentile rescue is permitted inside this family.

The conditional forward was not authorized and ran zero times. Status is `VALID_MT5_COMPLETE_SELECTION_PROFIT_GATES_FAIL_FORWARD_NOT_OPENED`; classification is `MT5_VALID_MARKET_STATE_ROUTER_DRAWDOWN_REDUCTION_WITH_SEVERE_PROFIT_DESTRUCTION`. The paired-month campaign remains the qualified Optimization anchor with no automatic Live authority.

The new router itself uses only the five US30/US100 active components. The inherited baseline nevertheless still loads US500 history for its existing read-only market-data dependency, so this campaign is not a two-symbol data-runtime speed split. The Tester generated `77,891,267` US500 ticks while reporting only two traded instruments; this corrects the narrower wording used during the run and is consistent with the previously closed separation finding.

Useful selection evidence is preserved as `22` files / `33,567,114` bytes / canonical manifest `3082CEAE7C13E06EFF7EECCF308FE89FBA7F6F8B47679748CDF0D19A1F189256`. The exact candidate and every adjacent router modification are frozen without rerun.
