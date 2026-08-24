#property strict
#property version "1.00"
#property description "Lab-only deposit lot tranches with fixed plus-150-dollar 0.01 increments"

#define DCRC_POLICY_KIND 3
#define DCRC_POLICY_LABEL "FIXED_LOT_LADDER"
#define DCRC_EXECUTION_VERSION "zt-dcrc-v1-fixed-lot-ladder"
#define DCRC_RELEASE_ID "DCRC-V1-FIXED-LOT-LADDER"
#define DCRC_PORTFOLIO_ID "ZT-LAB-DCRC-V1-FIXED-LOT-LADDER"
#define DCRC_ECONOMIC_FINGERPRINT "dcrc-v1-initial-deposit-lot-units-fixed-plus150usd-plus001-position4pct-aggregate12pct"
#define DCRC_EXECUTION_FINGERPRINT "dcrc-v1-tester-only-frozen-v7-order-lifecycle-sira-observation-fixed-lot-ladder"
#define DCRC_STATE_MARKER "ZT_DCRC_V1_FIXED_LOT_LADDER_STATE"
#define DCRC_STATE_PATH_A "ZetaDcrc\\dcrc\\ladder-state-a.csv"
#define DCRC_STATE_PATH_B "ZetaDcrc\\dcrc\\ladder-state-b.csv"
#define DCRC_EVENT_PATH_A "ZetaDcrc\\dcrc\\ladder-events-a.csv"
#define DCRC_EVENT_PATH_B "ZetaDcrc\\dcrc\\ladder-events-b.csv"
#define DCRC_CURRENT_SNAPSHOT_PATH_A "ZetaDcrc\\dcrc\\ladder-current-a.csv"
#define DCRC_CURRENT_SNAPSHOT_PATH_B "ZetaDcrc\\dcrc\\ladder-current-b.csv"
#define DCRC_OWNERSHIP_PATH "ZetaDcrc\\dcrc\\ladder.lock"
#define DCRC_MAGIC_BASE 260824930

#include <ZetaDcrc\ZetaDcrcAssembly.mqh>
