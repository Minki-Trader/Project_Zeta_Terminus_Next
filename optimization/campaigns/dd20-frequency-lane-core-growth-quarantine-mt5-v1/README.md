# DD20 Frequency-Lane Core-Growth Quarantine MT5 V1

This closed Optimization campaign owned the single native-validation seed retained by Lab Unit 125.

The campaign keeps the exact paired-month high/mid-frequency core—weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, position risk `0.04`, aggregate cap `0.18`, `$150` daily growth step—and the exact fixed US500 H4 candidate `ZT-H4-US500-V2-VOLATILITY-EXP-b4d28831f9`. The sole treatment is accounting ownership: H4 close P/L is tracked in a separate lane ledger and reported in total economics, but does not update core `project_realized_net`, core `stressed_balance`, core stage capital or the core daily lot multiplier. Real account balance, equity, margin, broker/session safety and native equity drawdown remain shared.

Selection must reproduce the paired-control core path, preserve the exact H4 path, strictly improve total actual and doubled-cost-stressed net over the paired control, keep all four selection epochs positive and remain at or below the frozen `21.2%` effective MT5 equity-DD boundary. Only a complete selection pass opens the already-used June–July interval as conditional recent native confirmation; it is not described as untouched or out-of-sample.

This campaign is self-contained, Tester-only and has no Live authority. It may create at most one verified Optimization candidate. Any later Live work still requires a separately named, user-authorized Lab engineering handoff.

The final self-contained implementation is frozen before valid economics. Its 17 source files and three fixed configuration files compile on MetaEditor build 6140 at `0 errors / 0 warnings`; the emitted EX5 is byte-identical between the tracked campaign and its dedicated physical Optimization Portable. The sole compiler invocation returned before its requested log and EX5 became visible, then the same invocation completed normally; no duplicate compile was used.

The first Selection attempt stopped normally with a 100% real-tick report, but it synchronized all 18 governing Tester HCS files during first use. It is preserved as `INVALID_FIRST_USE_ENVIRONMENT_SYNCHRONIZATION_NO_ECONOMIC_VERDICT`: its complete output is quarantined and cannot count as a pass, failure or retuning input. The post-synchronization environment was frozen across 18 HCS files and all 138 selection-month TKC files; every one of those 156 files remained exact through the unchanged valid Selection.

## Closed result

The valid Selection reproduced all `12,265` core candidate IDs with zero signal, result, admission or executable-volume mismatch. H4 opened and closed exactly `79 / 79`, left no position or pending state, never mutated either core growth ledger, and earned `+$10.14 / +$8.8217` actual/stressed. Total economics were `+$5,796.78 / +$5,486.3857`; all four epochs remained positive and native MT5 relative equity DD was `20.2568875652%`, within the fixed `21.2%` boundary.

The mandatory exact core-money gate nevertheless failed. Core actual/stressed net was `+$5,786.64 / +$5,477.564`, versus the paired-control requirement `+$5,786.63 / +$5,477.524`. Three stably aligned closes produced the reproducible `+$0.01 / +$0.04` aggregate difference. Exact restoration was all-required, so the fixed verdict is `VALID_QUARANTINE_SELECTION_NONCONFIRMATION_CLOSE_WITHOUT_RECENT_PATH`. Recent confirmation did not open, no candidate survives, and the observed path was not retuned or rescued. Any next rehabilitation unit requires a fresh whole-map re-ranking and exactly one newly named serial successor.
