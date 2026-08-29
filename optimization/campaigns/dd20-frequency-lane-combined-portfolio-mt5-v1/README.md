# DD20 Frequency-Lane Combined Portfolio MT5 V1

This independent tester-only campaign confirms one frozen execution-lane combination selected by `dd20-frequency-execution-lane-combination-proxy-v1`. It does not reopen a grid.

## Frozen candidate

- High/mid-frequency execution lane: the qualified paired-month core at position risk `0.04`, aggregate risk `0.18`, and component multipliers `2.0 / 1.5 / 2.0 / 2.5 / 1.5 / 0.0`.
- Low-frequency execution lane: exact lineage-pinned `ZT-H4-US500-V2-VOLATILITY-EXP-b4d28831f9`, trading US500 H4 at fixed volume `0.01` after the shared closed-balance gate reaches `$500`.
- H4 settings: lookback `12`, entry strength `1.5`, exit strength `0.6`, maximum hold `30` H4 bars, no SL/TP, and used plus required margin no greater than `20%` of equity.
- The H4 lane has its own Magic and position ownership and remains outside the six-component slot, planned-risk, and persistent-state accounting. It still shares account balance, equity, margin, and downstream sizing state.
- US100 Cross continues to read synchronized US100, US30, and US500 H1 closes. US500 H1 is therefore a read-only signal dependency of the high/mid lane, not US500 trade ownership.

The proxy projected selection actual/stressed net `+$5,829.67 / +$5,519.3732`, four positive selection epochs, and `20.861542647%` maximum DD. That DD exceeds the nominal `20%` line by `0.861542647` percentage points, or `4.307713235%` proportionally, inside the conservative `6%` practical overshoot boundary declared for this confirmation. Proxy values select the one MT5 candidate; they cannot decide it.

## Economic run

One real-tick selection covers 2022-08-01 through 2026-06-01. If the selection is complete and valid and passes the declared effective gate, one separately initialized real-tick forward covers 2026-06-01 through 2026-08-01.

The current qualified comparator is the exact paired-month control: selection actual/stressed net `+$5,786.63 / +$5,477.524`, maximum DD `20.256887565%`, with all four selection epochs positive; full forward actual/stressed net `+$32.74 / +$30.626` at `18.675302%` DD. The combined candidate must improve both selection nets, retain positive selection epochs, keep maximum DD within the declared practical boundary, and retain positive full-forward actual/stressed net with acceptable DD.

Only complete valid MT5 economic numbers decide the hypothesis. Compilation, runtime, history, configuration, logging, report, design, or engineering defects are correction states without a retry cap or economic verdict.

The campaign owns unique Optimization source, Include, settings, state, research, release, portfolio, Magic, report, and dedicated Portable runtime namespaces. It has no Live or Lab authority and never uses the Master terminal.

## Current boundary

The candidate completed a valid real-tick selection after two non-economic corrections. A user-requested machine reboot interrupted the first invocation, and the first full completion lacked an HTML report because its new nested report directory had not been created. Both were preserved without verdict; the unchanged third invocation reproduced the full EA economics exactly and generated the report bundle.

Final selection actual/stressed net was `+$5,546.61 / +$5,237.2907`, trailing the qualified control by `$240.02 / $240.2333`. All four epochs remained positive and reported maximum relative equity DD was `20.26%`, inside the declared practical `21.2%` boundary, but both mandatory profit-improvement gates failed. The conditional forward was therefore not opened.

The low-frequency lane itself earned `+$10.14 / +$8.8217` across `79 / 79` completed lifecycles with no margin skip or fault. The combined core nevertheless lost `$250.16 / $249.055` versus the control, with almost the entire dilution concentrated in E4. Shared downstream sizing and executable-volume quantization changed the core path enough to overwhelm the additive H4 gain.

This exact candidate is closed as `MT5_VALID_NONCONFIRMATION_OF_FREQUENCY_LANE_COMBINED_PORTFOLIO_REPLACEMENT`. The paired-month control remains the qualified Optimization anchor. Lane separation remains the preferred fast proxy and ownership-staging workflow, while a shortlisted account-level combination still requires one complete three-symbol MT5 run because US100 Cross keeps its read-only US500 H1 dependency and both lanes share account economics.
