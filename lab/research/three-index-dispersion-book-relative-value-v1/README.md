# Three-Index Dispersion and Book Relative Value V1

This frozen source-free Frontier family tests whether a pre-decision internal
dispersion state across US100, US30 and US500 changes the relative economic value
of the existing US100 and US30 books.

The regime is computed at the exact server-calendar 12:00 H1 row from the prior
24 physical H1 intervals, before the earliest 12:15 portfolio decision. Outcomes
come only from the complete fixed-0.01 CP2 lifecycle population. No signal,
session, component, order, exit, allocation, lot, risk, slot, EA or Live behavior
is changed.

The family closes after one bounded aggregation. It does not automatically open
an alternate lookback, regime threshold, period, symbol, component or dynamic
allocation successor.
