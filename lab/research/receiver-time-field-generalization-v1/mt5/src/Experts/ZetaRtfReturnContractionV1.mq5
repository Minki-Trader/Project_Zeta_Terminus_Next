#property strict
#property version "1.00"
#property description "Lab-only RTF generalization V1 Return contraction"

#define RTF_PATH_KIND 1
#define RTF_PATH_LABEL "RETURN_CONTRACTION"
#define RTF_EXECUTION_VERSION "zt-lab-rtf-v1-return-contraction"
#define RTF_RELEASE_ID "NEXT-LAB-RTF-V1-RETURN-CONTRACTION"
#define RTF_PORTFOLIO_ID "ZT-LAB-RTF-V1-RETURN-CONTRACTION"
#define RTF_ECONOMIC_FINGERPRINT "ref100-base0.01-step150-margin0.45-delay2-deviation100-inert-market-execution-quote-age3s-pre500-components6-passive-fixed0.01-always-m15-lb12-en1-ex0.25-offset0.25-activation4-hold16-posrisk0.04-aggrisk0.12-reserve0.25-headroom0.25-admission-reserved-broker-sl-session-clock-eet-v1-calendar2022-2028-rc4-check8-three-frozen-ordinal-heads-votesum-le-minus2-retain-original-loss0.25-one-shot-shadow-accepted-occupancy-return-expired-passive-decay-h2880-e0.25-d0.25-hold3"
#define RTF_EXECUTION_FINGERPRINT "rtf-v1-return-contraction-observed-expiration-strict-prior-tester-only"
#define RTF_STATE_MARKER "ZT_LAB_RTF_V1_RETURN_CONTRACTION_STATE"
#define RTF_FOLDER "ZetaRtf\\return-contraction"
#define RTF_STATE_PATH_A "ZetaRtf\\return-contraction\\state-a.csv"
#define RTF_STATE_PATH_B "ZetaRtf\\return-contraction\\state-b.csv"
#define RTF_EVENT_PATH_A "ZetaRtf\\return-contraction\\events-a.csv"
#define RTF_EVENT_PATH_B "ZetaRtf\\return-contraction\\events-b.csv"
#define RTF_CURRENT_SNAPSHOT_PATH_A "ZetaRtf\\return-contraction\\current-a.csv"
#define RTF_CURRENT_SNAPSHOT_PATH_B "ZetaRtf\\return-contraction\\current-b.csv"
#define RTF_OWNERSHIP_PATH "ZetaRtf\\return-contraction\\ownership.lock"
#define RTF_MAGIC_BASE 260825410

#include <ZetaRtf\ZetaRtfAssembly.mqh>
