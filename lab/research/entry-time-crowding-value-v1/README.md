# Entry-Time Crowding Value V1

Source-free exploratory diagnostic over the immutable four-period frozen-CP2 event matrix.

- Unit: `entry-time-crowding-value-017`
- Strategies: all six
- MQL change: none
- Tester run: none
- Live authority: none

The family tests whether entering while at least one other portfolio position is already active materially and broadly changes a strategy's native stressed-R and stop-loss incidence. It can justify at most one later strategy-specific, entry-preserving crowding-conditioned management experiment; it cannot filter an entry.

Closed as `NO_ENTRY_TIME_CROWDING_FIELD_PASSED`. Five strategies had dense SOLO/CROWDED groups but pooled stressed-R effects no larger than `|0.046802089R|`. RC4 showed `+0.227281851R` and `-0.133682373` stop-rate difference, but only 15 crowded entries and one period with at least five, so it failed density before selection. No subgroup rescue or management experiment opened.
