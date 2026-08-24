#define ZETA_EXECUTION_VERSION "zt-next-frontier-slot-shadow-exchange-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-causal-risk-slot-exchange-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-SLOT-SHADOW-EXCHANGE-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-receiver-time-field-causal-rolling-quality-incumbent-shadow-price"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-risk-admission-exchange-adapter-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_SLOT_SHADOW_EXCHANGE_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\slot-shadow-exchange-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825050
#define ZETA_MAGIC_RC4_BOTH 260825051
#define ZETA_MAGIC_US100_CROSS 260825052
#define ZETA_MAGIC_US30_PRESSURE 260825053
#define ZETA_MAGIC_US30_RETURN 260825054
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825055

enum ENUM_RECEIVER_TIME_FIELD_MODE
  {
   TIME_FIELD_CROSS_FIXED_6 = 0,
   TIME_FIELD_CROSS_FIXED_8 = 1,
   TIME_FIELD_CROSS_PROFIT_GATE_6 = 2
  };

enum ENUM_SLOT_SHADOW_EXCHANGE_MODE
  {
   SLOT_SHADOW_RECEIVER_WOUNDED = 0,
   SLOT_SHADOW_MATURE_WOUNDED = 1,
   SLOT_SHADOW_LOSER_RESIDUAL = 2
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;
input ENUM_SLOT_SHADOW_EXCHANGE_MODE InpSlotShadowExchangeMode =
   SLOT_SHADOW_RECEIVER_WOUNDED;

bool SlotShadowExchangeFieldInitialize();
void SlotShadowExchangeFieldReset();
void SlotShadowExchangeFieldObserveSignal(const int component,
                                          const double value,
                                          const bool passed,
                                          const int direction);
void SlotShadowExchangeFieldObserveExpiration(const int direction,
                                              const datetime expiration);
int SlotShadowExchangeFieldHoldBars(const int component,
                                    const ulong ticket,
                                    const datetime opened_at,
                                    const int held_bars,
                                    const int native_hold_bars);
bool SlotShadowExchangeFieldShouldClose(const int component,
                                        const ulong ticket,
                                        const datetime opened_at,
                                        const int held_bars);
bool SlotShadowExchangeTryRelease(const int component,
                                  const string symbol,
                                  const int direction,
                                  const double volume,
                                  const double entry_price,
                                  const double position_budget,
                                  const double aggregate_after,
                                  const double aggregate_budget);
void SlotShadowExchangeObserveExit(const int component,
                                   const ulong identifier,
                                   const double stressed_net,
                                   const double admitted_planned_risk,
                                   const bool completed);
void SlotShadowExchangeFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE SlotShadowExchangeFieldInitialize
#define ZETA_FRONTIER_RESET SlotShadowExchangeFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL SlotShadowExchangeFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED SlotShadowExchangeFieldObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS SlotShadowExchangeFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE SlotShadowExchangeFieldShouldClose
#define ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE SlotShadowExchangeTryRelease
#define ZETA_FRONTIER_OBSERVE_EXIT SlotShadowExchangeObserveExit
#define ZETA_FRONTIER_REPORT SlotShadowExchangeFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowExchangeAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowExchangeFieldAdapter.mqh>
