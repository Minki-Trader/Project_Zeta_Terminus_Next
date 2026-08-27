# Prior Cash Breadth Book Rotation v1

Unit 091 asks whether leadership in the last completed U.S. cash session—equal-weight S&P 500 exposure (`RSP`) versus capitalization-weighted S&P 500 exposure (`SPY`)—changes the next native server day's relative economic value of the existing US30 and US100 books.

This is a source-free Program 1 / meso-to-macro research family. It uses only official public daily ETF OHLC snapshots and the six immutable CP2 event files. It creates no MQL source, runtime, Tester path, execution rule, allocation rule, or Live change.

The fixed state is the sign of prior-session `log(RSP close / RSP open) - log(SPY close / SPY open)`. A directional result can retain exactly one later, non-automatic whole-portfolio risk-or-slot question; it cannot change current behavior. Null, ambiguous, or invalid results retain no seed. Same-family threshold, magnitude, lookback, alternate-index, subgroup, or implementation rescue is forbidden.
