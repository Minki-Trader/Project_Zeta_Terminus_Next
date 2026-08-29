# US500 earnings-extrapolation monthly signal

Status: closed valid ambiguous temporal instability; no seed.

Frontier Unit 112 was one Program 1 / macro-to-meso Lab detour from the
continuous Optimization Goal. Hongye Guo's 2025 *Review of Financial Studies*
paper fixes January, April, July and October as earnings-news-heavy months and
finds that their aggregate market returns reverse in future newsy months but
continue in future non-newsy months. The author's version-1.0 CC0 replication
data and implementation code froze the formula before this family's target
cash-session outcomes opened.

For target month `t+1`, the source path sums the latest four newsy-month returns
known at the end of `t`, subtracts the strictly prior expanding mean, flips the
signal when `t+1` is newsy, and multiplies it by a causally expanding OLS slope.
This unit took only the sign of that paper excess weight. Author history through
June 2021 was spliced once to last-close US500 D1 price returns from July 2021;
every July 2022-July 2026 target was strictly causal.

The sole actionable transfer held the source-fixed monthly LONG or SHORT
direction from the exact 09:30 ET M15 open to the exact 15:45 ET M15 close on
every eligible official NYSE session. Volume was always 0.01. Gross, executable
observed and doubled-spread stressed economics were measured on a $100 closed-
balance path. A same-beta signal without the target-newsy flip and an
unconditional LONG cash sleeve remained controls only.

One complete valid aggregation produced full gross / observed / stressed net
`+$4.16985 / -$0.24600 / -$4.66185`. Stressed PF is `0.96641`, closed DD
`17.5947%` and net/DD `-0.26496`. Observed executable burden consumes `105.90%`
of gross net; doubled burden consumes `211.80%`. Cost flips the small full gross
edge, but cost is not the whole diagnosis: P2, P4 and latest are already gross-
negative.

P1 is materially broad at stressed `+$10.0534`, PF `1.2569`, DD `5.5248%` and
net/DD `1.8197`; both target types, both directions and both control comparisons
are positive. Its required 2022H2 / 2023H1 / 2023H2 splits are `+$7.88825 /
+$2.80660 / -$0.64145`, so P1 still fails. Later P2 / P3 / P4 / latest stressed
nets are `-$7.83105 / -$1.38520 / -$3.57850 / -$1.92050`; confirmation passes
zero of three period gates and one of six target-type cells. Prelatest is
`-$2.74135`, only `21/47` months are positive, and latest June and July both
lose.

The full LONG leg remains `+$3.4483` stressed while SHORT loses `-$8.11015`,
but both directions were positive in P1. Full `NO_FLIP` is `-$3.85255` and
`LONG_ONLY` is `+$2.52345`; in P4 both controls earn `+$5.7863` while primary
loses. This is evidence of chronological mechanism breakdown, not authority to
rewrite the declared source into long-only, short suppression or no-flip.

The valid verdict is
`AMBIGUOUS_RFS_NEWSY_MONTH_US500_CASH_SESSION_DIRECTION_NO_SEED`: a broad
2022H2-through-2023H1 historical effect decays by 2023H2 and reverses afterward.
It is not a uniform null, but it has no stable executable continuation. No
information seed, Optimization candidate, MT5 shortlist, Strategy Tester path,
implementation candidate or Live authority survives. The fixed
`dd20-paired-month-stability-mt5-v1` development candidate is unchanged.

This closes the exact author-history/broker splice, expanding-beta/newsy-flip,
sign-only FPMarkets US500 09:30-16:00 cash-session transfer. It does not refute
the paper's aggregate total-return, overnight, full-month, futures, cash-equity,
industry, country or source-sample results. Every adjacent formula, direction,
calendar, clock, carrier, cost, sizing and integration rescue closes with the
family. Useful source, market and complete raw outputs are preserved; disposable
Python bytecode was removed. Optimization whole-map discovery resumes without a
reporting pause.
