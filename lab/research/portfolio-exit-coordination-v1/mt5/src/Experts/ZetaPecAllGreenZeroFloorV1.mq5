#property strict
#property version "1.00"
#property description "Lab-only PEC V1 all-green zero-dollar floor"

#define PEC_POLICY_KIND 2
#define PEC_POLICY_LABEL "ALL_GREEN_ZERO_FLOOR"
#define PEC_EXECUTION_VERSION "zt-lab-pec-v1-all-green-zero-floor"
#define PEC_RELEASE_ID "NEXT-LAB-PEC-V1-ALL-GREEN-ZERO-FLOOR"
#define PEC_PORTFOLIO_ID "ZT-LAB-PEC-V1-ALL-GREEN-ZERO-FLOOR"
#define PEC_ECONOMIC_FINGERPRINT "ref100-base0.01-step150-margin0.45-delay2-deviation100-inert-market-execution-quote-age3s-pre500-components6-passive-fixed0.01-always-m15-lb12-en1-ex0.25-offset0.25-activation4-hold16-posrisk0.04-aggrisk0.12-reserve0.25-headroom0.25-admission-reserved-broker-sl-session-clock-eet-v1-calendar2022-2028-rc4-check8-three-frozen-ordinal-heads-votesum-le-minus2-retain-original-loss0.25-one-shot-shadow-accepted-occupancy-pec-all-green-zero-floor"
#define PEC_EXECUTION_FINGERPRINT "pec-v1-all-green-zero-floor-every-real-tick-tester-only"
#define PEC_STATE_MARKER "ZT_LAB_PEC_V1_ALL_GREEN_ZERO_FLOOR_STATE"
#define PEC_FOLDER "ZetaPec\\all-green-zero-floor"
#define PEC_STATE_PATH_A "ZetaPec\\all-green-zero-floor\\state-a.csv"
#define PEC_STATE_PATH_B "ZetaPec\\all-green-zero-floor\\state-b.csv"
#define PEC_EVENT_PATH_A "ZetaPec\\all-green-zero-floor\\events-a.csv"
#define PEC_EVENT_PATH_B "ZetaPec\\all-green-zero-floor\\events-b.csv"
#define PEC_CURRENT_SNAPSHOT_PATH_A "ZetaPec\\all-green-zero-floor\\current-a.csv"
#define PEC_CURRENT_SNAPSHOT_PATH_B "ZetaPec\\all-green-zero-floor\\current-b.csv"
#define PEC_OWNERSHIP_PATH "ZetaPec\\all-green-zero-floor\\ownership.lock"
#define PEC_MAGIC_BASE 260825320

#include <ZetaPec\ZetaPecAssembly.mqh>
