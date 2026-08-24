#define ZETA_EXECUTION_VERSION "zt-next-frontier-slot-shadow-tape-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-causal-slot-opportunity-cost-tape-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-SLOT-SHADOW-TAPE-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-SLOT-SHADOW-TAPE-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-receiver-time-field-unchanged-causal-incumbent-snapshot-tape"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-observation-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_SLOT_SHADOW_TAPE_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\slot-shadow-tape-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825040
#define ZETA_MAGIC_RC4_BOTH 260825041
#define ZETA_MAGIC_US100_CROSS 260825042
#define ZETA_MAGIC_US30_PRESSURE 260825043
#define ZETA_MAGIC_US30_RETURN 260825044
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825045

enum ENUM_RECEIVER_TIME_FIELD_MODE
  {
   TIME_FIELD_CROSS_FIXED_6 = 0,
   TIME_FIELD_CROSS_FIXED_8 = 1,
   TIME_FIELD_CROSS_PROFIT_GATE_6 = 2
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;

bool SlotShadowFieldInitialize();
void SlotShadowFieldReset();
void SlotShadowFieldObserveSignal(const int component,
                                  const double value,
                                  const bool passed,
                                  const int direction);
void SlotShadowFieldObserveExpiration(const int direction,
                                      const datetime expiration);
int SlotShadowFieldHoldBars(const int component,
                            const ulong ticket,
                            const datetime opened_at,
                            const int held_bars,
                            const int native_hold_bars);
bool SlotShadowFieldShouldClose(const int component,
                                const ulong ticket,
                                const datetime opened_at,
                                const int held_bars);
void SlotShadowFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE SlotShadowFieldInitialize
#define ZETA_FRONTIER_RESET SlotShadowFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL SlotShadowFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED SlotShadowFieldObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS SlotShadowFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE SlotShadowFieldShouldClose
#define ZETA_FRONTIER_REPORT SlotShadowFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowTapeAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowFieldAdapter.mqh>
