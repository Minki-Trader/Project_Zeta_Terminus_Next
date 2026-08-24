#define ZETA_EXECUTION_VERSION "zt-next-frontier-receiver-time-field-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-paired-receiver-time-field-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-RECEIVER-TIME-FIELD-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-TIME-FIELD-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-expired-passive-polarity-return-contract-cross-extend-entry-risk-fixed"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_RECEIVER_TIME_FIELD_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\receiver-time-field-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\receiver-time-field-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\receiver-time-field-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\receiver-time-field-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\receiver-time-field-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\receiver-time-field-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\receiver-time-field-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260824970
#define ZETA_MAGIC_RC4_BOTH 260824971
#define ZETA_MAGIC_US100_CROSS 260824972
#define ZETA_MAGIC_US30_PRESSURE 260824973
#define ZETA_MAGIC_US30_RETURN 260824974
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260824975

enum ENUM_RECEIVER_TIME_FIELD_MODE
  {
   TIME_FIELD_CROSS_FIXED_6 = 0,
   TIME_FIELD_CROSS_FIXED_8 = 1,
   TIME_FIELD_CROSS_PROFIT_GATE_6 = 2
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;

bool ReceiverTimeFieldInitialize();
void ReceiverTimeFieldReset();
void ReceiverTimeFieldObserveSignal(const int component,
                                    const double value,
                                    const bool passed,
                                    const int direction);
void ReceiverTimeFieldObservePassiveExpiration(const int direction,
                                               const datetime expiration);
int ReceiverTimeFieldHoldBars(const int component,
                             const ulong ticket,
                             const datetime opened_at,
                             const int held_bars,
                             const int native_hold_bars);
bool ReceiverTimeFieldShouldClose(const int component,
                                  const ulong ticket,
                                  const datetime opened_at,
                                  const int held_bars);
void ReceiverTimeFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE ReceiverTimeFieldInitialize
#define ZETA_FRONTIER_RESET ReceiverTimeFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL ReceiverTimeFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED ReceiverTimeFieldObservePassiveExpiration
#define ZETA_FRONTIER_HOLD_BARS ReceiverTimeFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE ReceiverTimeFieldShouldClose
#define ZETA_FRONTIER_REPORT ReceiverTimeFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
