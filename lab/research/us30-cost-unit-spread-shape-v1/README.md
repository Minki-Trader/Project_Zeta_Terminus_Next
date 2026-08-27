# US30 Cost Unit and Spread Shape V1

This frozen source-free Frontier family tests whether Unit 039's lifecycle-level
observed cost unit already follows the time-varying US30 spread structure at the
actual entry and exit endpoints.

The population is every complete 2026 US30 lifecycle through the immutable M30
export boundary. Each lifecycle's `actual_net - stressed_2x_net` is compared to
the sum of the M30 quoted-spread snapshots containing its birth and final event.
Pooled and two-calendar-segment rank association plus component ratio alignment
distinguish a time-responsive base cost unit from a shape-blind scalar envelope.

The bar spread is a context proxy, not an executed spread. This family cannot
make a US100 or whole-portfolio claim, decompose broker costs, change Unit 039's
books, or touch MQL, Tester, broker, account, runtime, or Live surfaces. It closes
after one bounded aggregation with no automatic cost-model or logger successor.
