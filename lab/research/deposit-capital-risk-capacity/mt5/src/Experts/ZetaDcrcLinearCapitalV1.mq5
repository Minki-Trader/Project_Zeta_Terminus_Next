#property strict
#property version "1.00"
#property description "Lab-only deposit-proportional capital, volume and risk anchor"

#define DCRC_POLICY_KIND 1
#define DCRC_POLICY_LABEL "LINEAR_CAPITAL"
#define DCRC_EXECUTION_VERSION "zt-dcrc-v1-linear-capital"
#define DCRC_RELEASE_ID "DCRC-V1-LINEAR-CAPITAL"
#define DCRC_PORTFOLIO_ID "ZT-LAB-DCRC-V1-LINEAR-CAPITAL"
#define DCRC_ECONOMIC_FINGERPRINT "dcrc-v1-linear-deposit-units-base-volume-proportional-step150pct-position4pct-aggregate12pct"
#define DCRC_EXECUTION_FINGERPRINT "dcrc-v1-tester-only-frozen-v7-order-lifecycle-sira-observation-linear-capital"
#define DCRC_STATE_MARKER "ZT_DCRC_V1_LINEAR_CAPITAL_STATE"
#define DCRC_STATE_PATH_A "ZetaDcrc\\dcrc\\linear-state-a.csv"
#define DCRC_STATE_PATH_B "ZetaDcrc\\dcrc\\linear-state-b.csv"
#define DCRC_EVENT_PATH_A "ZetaDcrc\\dcrc\\linear-events-a.csv"
#define DCRC_EVENT_PATH_B "ZetaDcrc\\dcrc\\linear-events-b.csv"
#define DCRC_CURRENT_SNAPSHOT_PATH_A "ZetaDcrc\\dcrc\\linear-current-a.csv"
#define DCRC_CURRENT_SNAPSHOT_PATH_B "ZetaDcrc\\dcrc\\linear-current-b.csv"
#define DCRC_OWNERSHIP_PATH "ZetaDcrc\\dcrc\\linear.lock"
#define DCRC_MAGIC_BASE 260824910

#include <ZetaDcrc\ZetaDcrcAssembly.mqh>
