# US500 turn-of-month cash-session rebalancing

Status: closed `VALID_NO_US500_TURN_OF_MONTH_CASH_SESSION_EFFECT_AFTER_COST_NO_SEED`.

Frontier Unit 111 is one Program 3 / meso-to-macro Lab detour from the
continuous Optimization Goal. A 2026 paper fixes the final four official
trading days of one month plus the first four of the next and attributes the
equity-return pattern to infrequent institutional rebalancing and risk
deferral. The paper sample ends in 2023, leaving 2024 through July 2026 as
chronologically outside-paper confirmation data.

The sole fixed transfer was a 0.01-lot US500 LONG from the exact 09:30 ET M15
open to the exact 15:45 ET M15 close on each PRE4 or POST4 NYSE session.
Gross, executable observed and doubled-spread stressed economics were frozen;
the binding measure was stressed USD on a $100 closed-balance path. Rest-of-
month and unconditional cash-session returns were controls, not candidates.

Two premetric design faults were corrected before any price, spread or return
field opened. Month rank now uses the official NYSE calendar instead of CFD
holiday bars. Trade eligibility now requires the two exact consumed boundary
bars rather than irrelevant completeness of every interior M15 bar. Official
early-close or broker-closed days keep their rank and are excluded only when a
fixed boundary is absent.

The one valid source-free aggregation covered 388 primary days at
`142/95/95/40/16` across P1/P2/P3/P4/latest. Full gross / observed / stressed
net was `-$6.3103 / -$8.0013 / -$9.6923`; binding PF was `0.8334`, closed DD
`13.6166%` and net/DD `-0.7118`. P2, P3 and P4 were all negative even before
cost. P1 was only gross `+$0.1307` and became stressed `-$1.2867`, with two of
three chronological splits and both roles negative.

The economic contrast is decisive. Prelatest primary stressed net and
mean/day were `-$10.5289 / -$0.028303`, versus ROM `+$14.7013 / +$0.024421`
and unconditional `+$4.1723 / +$0.004284`. PRE4 lost `-$9.3889`; POST4 was
nearly flat but still stressed-negative `-$0.3034`. June-July alone gained
`+$0.8366`, supplied almost entirely by June, but every initial,
confirmation, role-breadth, control and full-path gate had already failed.

One post-declaration invocation stopped before P/L because the raw symbol
spec used MetaTrader field names rather than normalized aliases. The mapping
was corrected with no economic output, contract or gate change; one complete
valid aggregation then ran with zero metric rerun. This is an engineering
correction, not the research verdict.

No seed, Optimization candidate or MT5 shortlist survives, so no Strategy
Tester was run. The null applies to this regular-cash-session CFD transfer and
does not refute overnight or close-to-close literature. All neighboring day
counts, partial roles, clocks, directions, symbols, subgroups, costs, sizing
and integration rescues close with the family. Useful raw inputs and complete
outputs remain preserved; the fixed paired-month development candidate and
every Live surface are unchanged. The continuous Goal returns to the
Optimization whole map.
