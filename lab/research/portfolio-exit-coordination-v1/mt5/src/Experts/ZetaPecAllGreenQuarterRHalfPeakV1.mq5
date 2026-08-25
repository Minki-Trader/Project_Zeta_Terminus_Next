#property strict
#property version "1.00"
#property description "Lab-only PEC V1 all-green quarter-R half-peak trail"

#define PEC_POLICY_KIND 3
#define PEC_POLICY_LABEL "ALL_GREEN_QUARTER_R_HALF_PEAK"
#define PEC_EXECUTION_VERSION "zt-lab-pec-v1-all-green-quarter-r-half-peak"
#define PEC_RELEASE_ID "NEXT-LAB-PEC-V1-ALL-GREEN-QUARTER-R-HALF-PEAK"
#define PEC_PORTFOLIO_ID "ZT-LAB-PEC-V1-ALL-GREEN-QUARTER-R-HALF-PEAK"
#define PEC_ECONOMIC_FINGERPRINT "ref100-base0.01-step150-margin0.45-delay2-deviation100-inert-market-execution-quote-age3s-pre500-components6-passive-fixed0.01-always-m15-lb12-en1-ex0.25-offset0.25-activation4-hold16-posrisk0.04-aggrisk0.12-reserve0.25-headroom0.25-admission-reserved-broker-sl-session-clock-eet-v1-calendar2022-2028-rc4-check8-three-frozen-ordinal-heads-votesum-le-minus2-retain-original-loss0.25-one-shot-shadow-accepted-occupancy-pec-all-green-quarter-r-half-peak"
#define PEC_EXECUTION_FINGERPRINT "pec-v1-all-green-quarter-r-half-peak-every-real-tick-tester-only"
#define PEC_STATE_MARKER "ZT_LAB_PEC_V1_ALL_GREEN_QUARTER_R_HALF_PEAK_STATE"
#define PEC_FOLDER "ZetaPec\\all-green-quarter-r-half-peak"
#define PEC_STATE_PATH_A "ZetaPec\\all-green-quarter-r-half-peak\\state-a.csv"
#define PEC_STATE_PATH_B "ZetaPec\\all-green-quarter-r-half-peak\\state-b.csv"
#define PEC_EVENT_PATH_A "ZetaPec\\all-green-quarter-r-half-peak\\events-a.csv"
#define PEC_EVENT_PATH_B "ZetaPec\\all-green-quarter-r-half-peak\\events-b.csv"
#define PEC_CURRENT_SNAPSHOT_PATH_A "ZetaPec\\all-green-quarter-r-half-peak\\current-a.csv"
#define PEC_CURRENT_SNAPSHOT_PATH_B "ZetaPec\\all-green-quarter-r-half-peak\\current-b.csv"
#define PEC_OWNERSHIP_PATH "ZetaPec\\all-green-quarter-r-half-peak\\ownership.lock"
#define PEC_MAGIC_BASE 260825330

#include <ZetaPec\ZetaPecAssembly.mqh>
