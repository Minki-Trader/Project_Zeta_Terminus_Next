#property strict
#property version "1.00"
#property description "Lab-only RTF generalization V1 frozen CP2 control"

#define RTF_PATH_KIND 0
#define RTF_PATH_LABEL "CONTROL"
#define RTF_EXECUTION_VERSION "zt-lab-rtf-v1-control"
#define RTF_RELEASE_ID "NEXT-LAB-RTF-V1-CONTROL"
#define RTF_PORTFOLIO_ID "ZT-LAB-RTF-V1-CONTROL"
#define RTF_ECONOMIC_FINGERPRINT "ref100-base0.01-step150-margin0.45-delay2-deviation100-inert-market-execution-quote-age3s-pre500-components6-passive-fixed0.01-always-m15-lb12-en1-ex0.25-offset0.25-activation4-hold16-posrisk0.04-aggrisk0.12-reserve0.25-headroom0.25-admission-reserved-broker-sl-session-clock-eet-v1-calendar2022-2028-rc4-check8-three-frozen-ordinal-heads-votesum-le-minus2-retain-original-loss0.25-one-shot-shadow-accepted-occupancy"
#define RTF_EXECUTION_FINGERPRINT "rtf-v1-control-cp2-inert-afterimage"
#define RTF_STATE_MARKER "ZT_LAB_RTF_V1_CONTROL_STATE"
#define RTF_FOLDER "ZetaRtf\\control"
#define RTF_STATE_PATH_A "ZetaRtf\\control\\state-a.csv"
#define RTF_STATE_PATH_B "ZetaRtf\\control\\state-b.csv"
#define RTF_EVENT_PATH_A "ZetaRtf\\control\\events-a.csv"
#define RTF_EVENT_PATH_B "ZetaRtf\\control\\events-b.csv"
#define RTF_CURRENT_SNAPSHOT_PATH_A "ZetaRtf\\control\\current-a.csv"
#define RTF_CURRENT_SNAPSHOT_PATH_B "ZetaRtf\\control\\current-b.csv"
#define RTF_OWNERSHIP_PATH "ZetaRtf\\control\\ownership.lock"
#define RTF_MAGIC_BASE 260825400

#include <ZetaRtf\ZetaRtfAssembly.mqh>
