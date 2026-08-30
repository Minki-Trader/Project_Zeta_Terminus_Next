# DD20 Frequency-Lane Core-Growth Quarantine MT5 V1

This open Optimization campaign owns the single native-validation seed retained by Lab Unit 125. It is declaration-only until its declaration reaches `origin/main`.

The campaign keeps the exact paired-month high/mid-frequency core—weights `2 / 1.5 / 2 / 2.5 / 1.5 / 0`, position risk `0.04`, aggregate cap `0.18`, `$150` daily growth step—and the exact fixed US500 H4 candidate `ZT-H4-US500-V2-VOLATILITY-EXP-b4d28831f9`. The sole treatment is accounting ownership: H4 close P/L is tracked in a separate lane ledger and reported in total economics, but does not update core `project_realized_net`, core `stressed_balance`, core stage capital or the core daily lot multiplier. Real account balance, equity, margin, broker/session safety and native equity drawdown remain shared.

Selection must reproduce the paired-control core path, preserve the exact H4 path, strictly improve total actual and doubled-cost-stressed net over the paired control, keep all four selection epochs positive and remain at or below the frozen `21.2%` effective MT5 equity-DD boundary. Only a complete selection pass opens the already-used June–July interval as conditional recent native confirmation; it is not described as untouched or out-of-sample.

This campaign is self-contained, Tester-only and has no Live authority. It may create at most one verified Optimization candidate. Any later Live work still requires a separately named, user-authorized Lab engineering handoff.
