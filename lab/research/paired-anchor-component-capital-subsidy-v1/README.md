# Paired-anchor component capital subsidy V1

Status: closed `VALID_COMPONENT_CAPITAL_SUBSIDY_NONCONFIRMATION_NO_SEED` as
source-free Frontier Unit 101 under Program 5 `portfolio_capital_risk` at
meso-to-macro height.

The paired-month Optimization anchor freezes one shared daily volume multiplier
from total doubled-cost closed balance. This unit asks whether that global
ladder economically harms the portfolio by letting profit made by one active
component enlarge later volume in another component.

The sole candidate is `COMPONENT_LOCAL_NO_ADD`. It keeps the exact `$150`
addition step, the five paired-anchor weights, every observed admission, entry,
stop and exit, and the shared account. For each component it computes a causal
daily multiplier from only that component's already-realized candidate stressed
profit. Candidate volume is the lesser of that local target and the volume that
actually traded in the anchor. It may remove cross-subsidized volume but may not
invent a fill, enlarge an observed position, free and reuse capacity, or change
any threshold.

The complete selection lifecycle ledger is copied once into the Lab-owned,
Git-ignored input root. June and July forward economics remain unopened. A
later Optimization information seed survives only if this conservative fixed
path materially improves both actual and stressed profit, does not worsen raw
closed-balance drawdown, remains positive in every frozen epoch, and has broad
component and epoch support. Otherwise the component-local, book-local,
component-specific and addition-step neighborhoods close together with no
seed.

This unit creates no MQL, SET, runtime, compile, Tester, validator, test, broker
query or Live change.

## Result

The first invocation stopped at the integrity boundary before serializing any
economic metric because it incorrectly equated normalized requested volume
with the adopted aggregate fill. The exact 2025-05-12 Pressure request was
`0.23` lot and the durable fill was `0.22`. The corrected contract preserves a
positive fill at or below its request; the hypothesis, input, candidate and all
economic gates remained unchanged. The one valid process then reproduced all
`1,428` births and closes, both anchor totals, and found nine one-step fill
shortfalls with no fill above its request.

`COMPONENT_LOCAL_NO_ADD` materially bound: it reduced `1,249` lifecycles and
removed `15,153 / 18,271` source lot steps (`82.934705%`). Raw closed-balance DD
fell from `20.401029%` to `17.815650%`, and every epoch remained positive.
Profit, however, collapsed from actual/stressed `+$5,786.63 / +$5,477.524` to
only `+$837.206701 / +$784.255010`. All five components and all four epochs had
negative actual and stressed deltas; no positive-improvement breadth existed.

This is complete valid economic nonconfirmation. Cross-component sharing of
the realized-profit ladder is a material profit engine in the paired anchor,
not an identified harmful subsidy. No forward row, Optimization candidate,
MQL, Tester or adjacent component/book/step/cap/admission rescue opens.
