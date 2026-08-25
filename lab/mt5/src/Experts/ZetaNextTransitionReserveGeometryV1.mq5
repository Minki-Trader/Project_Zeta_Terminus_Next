#define ZETA_EXECUTION_VERSION "zt-next-frontier-transition-reserve-geometry-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-risk-capacity-transition-reserve-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-TRANSITION-RESERVE-GEOMETRY-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-TRANSITION-RESERVE-GEOMETRY-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-receiver-time-field-loser-residual-slot-exchange-linear-capital-transition-reserve-geometry"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-scaled-capital-adapter-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_TRANSITION_RESERVE_GEOMETRY_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\transition-reserve-geometry-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825080
#define ZETA_MAGIC_RC4_BOTH 260825081
#define ZETA_MAGIC_US100_CROSS 260825082
#define ZETA_MAGIC_US30_PRESSURE 260825083
#define ZETA_MAGIC_US30_RETURN 260825084
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825085

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

enum ENUM_TRANSITION_RESERVE_MODE
  {
   TRANSITION_RESERVE_NONE = 0,
   TRANSITION_RESERVE_FIXED_20 = 1,
   TRANSITION_RESERVE_POSITION_BUDGET_1_25 = 2
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;
input ENUM_SLOT_SHADOW_EXCHANGE_MODE InpSlotShadowExchangeMode =
   SLOT_SHADOW_LOSER_RESIDUAL;
input ENUM_TRANSITION_RESERVE_MODE InpTransitionReserveMode =
   TRANSITION_RESERVE_POSITION_BUDGET_1_25;

bool TransitionReserveCapitalInputsValid();
bool TransitionReserveFieldInitialize();
void TransitionReserveFieldReset();
void TransitionReserveFieldObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction);
void TransitionReserveFieldObserveExpiration(const int direction,
                                             const datetime expiration);
int TransitionReserveFieldHoldBars(const int component,
                                   const ulong ticket,
                                   const datetime opened_at,
                                   const int held_bars,
                                   const int native_hold_bars);
bool TransitionReserveFieldShouldClose(const int component,
                                       const ulong ticket,
                                       const datetime opened_at,
                                       const int held_bars);
bool TransitionReserveFieldTryRelease(const int component,
                                      const string symbol,
                                      const int direction,
                                      const double volume,
                                      const double entry_price,
                                      const double position_budget,
                                      const double aggregate_after,
                                      const double aggregate_budget);
void TransitionReserveFieldObserveExit(const int component,
                                       const ulong identifier,
                                       const double stressed_net,
                                       const double admitted_planned_risk,
                                       const bool completed);
int TransitionReserveFieldObserveSizing(const datetime current_day,
                                        const double stressed_balance,
                                        const int raw_multiplier,
                                        const int current_multiplier);
double TransitionReserveFieldEntryVolume(const int component,
                                         const string symbol);
void TransitionReserveFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_CAPITAL_INPUTS_VALID TransitionReserveCapitalInputsValid
#define ZETA_FRONTIER_INITIALIZE TransitionReserveFieldInitialize
#define ZETA_FRONTIER_RESET TransitionReserveFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL TransitionReserveFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED TransitionReserveFieldObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS TransitionReserveFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE TransitionReserveFieldShouldClose
#define ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE TransitionReserveFieldTryRelease
#define ZETA_FRONTIER_OBSERVE_EXIT TransitionReserveFieldObserveExit
#define ZETA_FRONTIER_VOLUME_MULTIPLIER TransitionReserveFieldObserveSizing
#define ZETA_FRONTIER_ENTRY_VOLUME TransitionReserveFieldEntryVolume
#define ZETA_FRONTIER_REPORT TransitionReserveFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowExchangeAdapter.mqh>
#include <ZetaTerminusNext\Frontier\TransitionReserveGeometryAdapter.mqh>
#include <ZetaTerminusNext\Frontier\TransitionReserveFieldAdapter.mqh>
