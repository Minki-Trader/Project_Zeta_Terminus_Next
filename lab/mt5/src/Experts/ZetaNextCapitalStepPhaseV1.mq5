#define ZETA_EXECUTION_VERSION "zt-next-frontier-capital-step-phase-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-causal-capital-step-phase-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-CAPITAL-STEP-PHASE-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-CAPITAL-STEP-PHASE-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-receiver-time-field-capital-step-downside-escrow-or-confirmation-with-optional-slot-exchange"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-sizing-phase-adapter-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_CAPITAL_STEP_PHASE_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\capital-step-phase-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\capital-step-phase-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\capital-step-phase-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\capital-step-phase-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\capital-step-phase-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\capital-step-phase-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\capital-step-phase-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825060
#define ZETA_MAGIC_RC4_BOTH 260825061
#define ZETA_MAGIC_US100_CROSS 260825062
#define ZETA_MAGIC_US30_PRESSURE 260825063
#define ZETA_MAGIC_US30_RETURN 260825064
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825065

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

enum ENUM_CAPITAL_STEP_PHASE_MODE
  {
   CAPITAL_STEP_DOWNSIDE_ESCROW_25 = 0,
   CAPITAL_STEP_CONFIRM_TWO = 1
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;
input ENUM_CAPITAL_STEP_PHASE_MODE InpCapitalStepPhaseMode =
   CAPITAL_STEP_DOWNSIDE_ESCROW_25;
input bool InpCapitalStepUseSlotExchange = false;
input bool InpCapitalStepQuarantineExchange = false;
input ENUM_SLOT_SHADOW_EXCHANGE_MODE InpSlotShadowExchangeMode =
   SLOT_SHADOW_LOSER_RESIDUAL;

bool CapitalStepExchangeFieldInitialize();
void CapitalStepExchangeFieldReset();
void CapitalStepExchangeFieldObserveSignal(const int component,
                                           const double value,
                                           const bool passed,
                                           const int direction);
void CapitalStepExchangeFieldObserveExpiration(const int direction,
                                               const datetime expiration);
int CapitalStepExchangeFieldHoldBars(const int component,
                                     const ulong ticket,
                                     const datetime opened_at,
                                     const int held_bars,
                                     const int native_hold_bars);
bool CapitalStepExchangeFieldShouldClose(const int component,
                                         const ulong ticket,
                                         const datetime opened_at,
                                         const int held_bars);
bool CapitalStepExchangeFieldTryRelease(const int component,
                                        const string symbol,
                                        const int direction,
                                        const double volume,
                                        const double entry_price,
                                        const double position_budget,
                                        const double aggregate_after,
                                        const double aggregate_budget);
void CapitalStepExchangeFieldObserveExit(const int component,
                                         const ulong identifier,
                                         const double stressed_net,
                                         const double admitted_planned_risk,
                                         const bool completed);
int CapitalStepExchangeFieldMultiplier(const datetime current_day,
                                       const double stressed_balance,
                                       const int raw_multiplier,
                                       const int current_multiplier);
void CapitalStepExchangeFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE CapitalStepExchangeFieldInitialize
#define ZETA_FRONTIER_RESET CapitalStepExchangeFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL CapitalStepExchangeFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED CapitalStepExchangeFieldObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS CapitalStepExchangeFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE CapitalStepExchangeFieldShouldClose
#define ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE CapitalStepExchangeFieldTryRelease
#define ZETA_FRONTIER_OBSERVE_EXIT CapitalStepExchangeFieldObserveExit
#define ZETA_FRONTIER_VOLUME_MULTIPLIER CapitalStepExchangeFieldMultiplier
#define ZETA_FRONTIER_REPORT CapitalStepExchangeFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowExchangeAdapter.mqh>
#include <ZetaTerminusNext\Frontier\CapitalStepPhaseAdapter.mqh>
#include <ZetaTerminusNext\Frontier\CapitalStepExchangeFieldAdapter.mqh>
