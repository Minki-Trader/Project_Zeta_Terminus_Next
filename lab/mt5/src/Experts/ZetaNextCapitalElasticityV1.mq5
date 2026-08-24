#define ZETA_EXECUTION_VERSION "zt-next-frontier-capital-elasticity-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-adjacent-tier-exposure-dither-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-CAPITAL-ELASTICITY-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-CAPITAL-ELASTICITY-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-receiver-time-field-loser-residual-slot-exchange-third-tier-adjacent-volume-elasticity"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-opportunity-clock-volume-adapter-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_CAPITAL_ELASTICITY_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\capital-elasticity-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\capital-elasticity-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\capital-elasticity-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\capital-elasticity-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\capital-elasticity-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\capital-elasticity-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\capital-elasticity-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825070
#define ZETA_MAGIC_RC4_BOTH 260825071
#define ZETA_MAGIC_US100_CROSS 260825072
#define ZETA_MAGIC_US30_PRESSURE 260825073
#define ZETA_MAGIC_US30_RETURN 260825074
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825075

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

enum ENUM_CAPITAL_ELASTICITY_MODE
  {
   CAPITAL_ELASTICITY_COMPONENT_CLOCK_30 = 0,
   CAPITAL_ELASTICITY_HARD_ESCROW_20 = 1
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;
input ENUM_SLOT_SHADOW_EXCHANGE_MODE InpSlotShadowExchangeMode =
   SLOT_SHADOW_LOSER_RESIDUAL;
input ENUM_CAPITAL_ELASTICITY_MODE InpCapitalElasticityMode =
   CAPITAL_ELASTICITY_COMPONENT_CLOCK_30;
input bool InpCapitalElasticityQuarantineExchange = false;

bool CapitalElasticityFieldInitialize();
void CapitalElasticityFieldReset();
void CapitalElasticityFieldObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction);
void CapitalElasticityFieldObserveExpiration(const int direction,
                                             const datetime expiration);
int CapitalElasticityFieldHoldBars(const int component,
                                   const ulong ticket,
                                   const datetime opened_at,
                                   const int held_bars,
                                   const int native_hold_bars);
bool CapitalElasticityFieldShouldClose(const int component,
                                       const ulong ticket,
                                       const datetime opened_at,
                                       const int held_bars);
bool CapitalElasticityFieldTryRelease(const int component,
                                      const string symbol,
                                      const int direction,
                                      const double volume,
                                      const double entry_price,
                                      const double position_budget,
                                      const double aggregate_after,
                                      const double aggregate_budget);
void CapitalElasticityFieldObserveExit(const int component,
                                       const ulong identifier,
                                       const double stressed_net,
                                       const double admitted_planned_risk,
                                       const bool completed);
int CapitalElasticityFieldObserveSizing(const datetime current_day,
                                        const double stressed_balance,
                                        const int raw_multiplier,
                                        const int current_multiplier);
double CapitalElasticityFieldEntryVolume(const int component,
                                         const string symbol);
void CapitalElasticityFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE CapitalElasticityFieldInitialize
#define ZETA_FRONTIER_RESET CapitalElasticityFieldReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL CapitalElasticityFieldObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED CapitalElasticityFieldObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS CapitalElasticityFieldHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE CapitalElasticityFieldShouldClose
#define ZETA_FRONTIER_RISK_ADMISSION_EXCHANGE CapitalElasticityFieldTryRelease
#define ZETA_FRONTIER_OBSERVE_EXIT CapitalElasticityFieldObserveExit
#define ZETA_FRONTIER_VOLUME_MULTIPLIER CapitalElasticityFieldObserveSizing
#define ZETA_FRONTIER_ENTRY_VOLUME CapitalElasticityFieldEntryVolume
#define ZETA_FRONTIER_REPORT CapitalElasticityFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\SlotShadowExchangeAdapter.mqh>
#include <ZetaTerminusNext\Frontier\CapitalElasticityAdapter.mqh>
#include <ZetaTerminusNext\Frontier\CapitalElasticityFieldAdapter.mqh>
