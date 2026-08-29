# US500 EPU / volatility disconnect cash-session transfer

Status: Unit 110 declared; economic outcomes unopened.

This is one serial Program 2 / meso-to-macro Lab detour from the active
Optimization Goal. It asks whether the Federal Reserve paper's high
uncertainty-to-realized-volatility disconnect with low realized volatility
transfers, after a publication-safe five-week lag, to a cost-resilient US500
09:30..16:00 ET LONG cash-session path.

The primary state is `HIGH_D_LOW_V`, where weekly disconnect is the five-day
mean U.S. daily EPU index divided by weekly US500 cash-session realized
volatility. Both high/low thresholds use only prior complete source weeks and
the paper's fixed mean-plus-0.5-standard-deviation rule. A 26-week causal
warmup and a five-calendar-week source-to-target lag leave the newest source
date 31 days old at the target Monday, beyond the publisher's disclosed
30-day revision window.

The family owns a byte-frozen U.S. daily EPU snapshot, a physical byte-equal
copy of the closed US500 M15 surface and its contract specification. The one
formal source-free process may open economics only after the declaration
commit reaches `origin/main`. It will simulate one 0.01-lot LONG from 09:30 ET
to the 16:00 ET cash close on every complete target session and bind to doubled
entry-plus-exit spread cost. No overnight position, swap, commission, MQL,
Tester, runtime, Master, broker/account query or Live surface is involved.

The exact declaration and stop rules are in
`evidence/US500_EPU_VOLATILITY_DISCONNECT_CASH_SESSION_DECLARATION_V1.json`.
No threshold, lag, warmup, state, clock, direction, symbol, period, cost,
subgroup, portfolio-integration or sizing rescue follows this family.
