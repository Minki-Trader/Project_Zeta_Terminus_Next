#define ZETA_EXECUTION_VERSION "zt-next-frontier-capital-scale-admission-topology-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-current-cap-three-risk-units-stop-backstop-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-CAPITAL-SCALE-ADMISSION-TOPOLOGY-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-CAPITAL-SCALE-ADMISSION-TOPOLOGY-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-receiver-time-field-loser-residual-slot-exchange-risk-capacity-transition-reserve-current-cap-three-units-stop-backstop"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-scale-consistent-admission-adapter-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_CAPITAL_SCALE_ADMISSION_TOPOLOGY_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\capital-scale-admission-topology-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825090
#define ZETA_MAGIC_RC4_BOTH 260825091
#define ZETA_MAGIC_US100_CROSS 260825092
#define ZETA_MAGIC_US30_PRESSURE 260825093
#define ZETA_MAGIC_US30_RETURN 260825094
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825095

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

bool AdmissionTopologyFieldInitialize();
void AdmissionTopologyFieldReset();
void AdmissionTopologyFieldObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction);
void AdmissionTopologyFieldObserveExpiration(const int direction,
                                             const datetime expiration);
int AdmissionTopologyFieldHoldBars(const int component,
                                   const ulong ticket,
                                   const datetime opened_at,
                                   const int held_bars,
                                   const int native_hold_bars);
bool AdmissionTopologyFieldShouldClose(const int component,
                                       const ulong ticket,
                                       const datetime opened_at,
                                       const int held_bars);
bool AdmissionTopologyFieldTryRelease(const int component,
                                      const string symbol,
                                      const int direction,
                                      const double volume,
                                      const double entry_price,
                                      const double position_budget,
                                      const double aggregate_after,
                                      const double aggregate_budget);
bool AdmissionTopologyFieldAllow(const int component,
                                 const string symbol,
                                 const int direction,
                                 const double volume,
                                 const double entry_price,
                                 const double stop_loss,
                                 const double candidate_actual_stop_risk,
                                 const double position_budget,
                                 const double aggregate_after,
                                 const double aggregate_budget);
bool AdmissionTopologyFieldPostPlacementConfirmed(
   const double aggregate_before,
   const double pending_planned_risk,
   const double admitted_capital);
void AdmissionTopologyFieldObserveExit(const int component,
                                       const ulong identifier,
                                       const double stressed_net,
                                       const double admitted_planned_risk,
                                       const bool completed);
int AdmissionTopologyFieldObserveSizing(const datetime current_day,
                                        const double stressed_balance,
                                        const int raw_multiplier,
                                        const int current_multiplier);
double AdmissionTopologyFieldEntryVolume(const int component,
                                         const string symbol);
void AdmissionTopologyFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_CAPITAL_INPUTS_VALID TransitionReserveCapitalInputsValid
#define ZETA_FRONTIER_INITIALIZE AdmissionTopologyFieldInitialize
#define ZETA_FRONTIER_RESET AdmissionTopologyFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL AdmissionTopologyFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED AdmissionTopologyFieldObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS AdmissionTopologyFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE AdmissionTopologyFieldShouldClose
#define ZETA_FRONTIER_RISK_ADMISSION_OVERRIDE AdmissionTopologyFieldAllow
#define ZETA_FRONTIER_POST_PLACEMENT_RISK_CONFIRMED AdmissionTopologyFieldPostPlacementConfirmed
#define ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE AdmissionTopologyFieldTryRelease
#define ZETA_FRONTIER_OBSERVE_EXIT AdmissionTopologyFieldObserveExit
#define ZETA_FRONTIER_VOLUME_MULTIPLIER AdmissionTopologyFieldObserveSizing
#define ZETA_FRONTIER_ENTRY_VOLUME AdmissionTopologyFieldEntryVolume
#define ZETA_FRONTIER_REPORT AdmissionTopologyFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowExchangeAdapter.mqh>
#include <ZetaTerminusNext\Frontier\TransitionReserveGeometryAdapter.mqh>
#include <ZetaTerminusNext\Frontier\TransitionReserveFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\CapitalScaleAdmissionTopologyAdapter.mqh>
#include <ZetaTerminusNext\Frontier\CapitalScaleAdmissionTopologyFieldAdapter.mqh>
