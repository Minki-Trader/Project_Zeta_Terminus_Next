#property strict
#property version "1.00"
#property description "Lab-only fixed-dollar risk units using deposit-funded aggregate breadth"

#define DCRC_POLICY_KIND 2
#define DCRC_POLICY_LABEL "BREADTH_DOLLAR_SLOTS"
#define DCRC_EXECUTION_VERSION "zt-dcrc-v1-breadth-dollar-slots"
#define DCRC_RELEASE_ID "DCRC-V1-BREADTH-DOLLAR-SLOTS"
#define DCRC_PORTFOLIO_ID "ZT-LAB-DCRC-V1-BREADTH-DOLLAR-SLOTS"
#define DCRC_ECONOMIC_FINGERPRINT "dcrc-v1-breadth-base001-position4usd-aggregate12pct-deposit-capacity-no-volume-growth"
#define DCRC_EXECUTION_FINGERPRINT "dcrc-v1-tester-only-frozen-v7-order-lifecycle-sira-observation-breadth-dollar-slots"
#define DCRC_STATE_MARKER "ZT_DCRC_V1_BREADTH_DOLLAR_SLOTS_STATE"
#define DCRC_STATE_PATH_A "ZetaDcrc\\dcrc\\breadth-state-a.csv"
#define DCRC_STATE_PATH_B "ZetaDcrc\\dcrc\\breadth-state-b.csv"
#define DCRC_EVENT_PATH_A "ZetaDcrc\\dcrc\\breadth-events-a.csv"
#define DCRC_EVENT_PATH_B "ZetaDcrc\\dcrc\\breadth-events-b.csv"
#define DCRC_CURRENT_SNAPSHOT_PATH_A "ZetaDcrc\\dcrc\\breadth-current-a.csv"
#define DCRC_CURRENT_SNAPSHOT_PATH_B "ZetaDcrc\\dcrc\\breadth-current-b.csv"
#define DCRC_OWNERSHIP_PATH "ZetaDcrc\\dcrc\\breadth.lock"
#define DCRC_MAGIC_BASE 260824920

#include <ZetaDcrc\ZetaDcrcAssembly.mqh>
