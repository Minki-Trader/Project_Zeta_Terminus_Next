#define ZETA_EXECUTION_VERSION "zt-next-frontier-opportunity-phase-portfolio-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-opportunity-memory-plus-expiration-transition-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-OPPORTUNITY-PHASE-PORTFOLIO-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-OPPORTUNITY-PHASE-PORTFOLIO-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-return-contract-cross-profit-extension-passive-persistent-escape-transition"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-composed-adapters-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_OPPORTUNITY_PHASE_PORTFOLIO_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\opportunity-phase-portfolio-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825030
#define ZETA_MAGIC_RC4_BOTH 260825031
#define ZETA_MAGIC_US100_CROSS 260825032
#define ZETA_MAGIC_US30_PRESSURE 260825033
#define ZETA_MAGIC_US30_RETURN 260825034
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825035

enum ENUM_RECEIVER_TIME_FIELD_MODE
  {
   TIME_FIELD_CROSS_FIXED_6 = 0,
   TIME_FIELD_CROSS_FIXED_8 = 1,
   TIME_FIELD_CROSS_PROFIT_GATE_6 = 2
  };

enum ENUM_EXPIRATION_PHASE_TRANSITION_MODE
  {
   PHASE_TRANSITION_EFFICIENCY_Q75 = 0,
   PHASE_TRANSITION_EFFICIENCY_Q50 = 1,
   PHASE_TRANSITION_PERSISTENT_ESCAPE = 2
  };

input ENUM_RECEIVER_TIME_FIELD_MODE InpReceiverTimeFieldMode =
   TIME_FIELD_CROSS_PROFIT_GATE_6;
input ENUM_EXPIRATION_PHASE_TRANSITION_MODE InpExpirationPhaseTransitionMode =
   PHASE_TRANSITION_PERSISTENT_ESCAPE;

bool OpportunityPhasePortfolioInitialize();
void OpportunityPhasePortfolioReset();
void OpportunityPhasePortfolioObserveSignal(const int component,
                                            const double value,
                                            const bool passed,
                                            const int direction);
void OpportunityPhasePortfolioObserveExpiration(const int direction,
                                                const datetime expiration);
void OpportunityPhasePortfolioAfterExpiration(const int direction,
                                              const datetime expiration,
                                              const double feature,
                                              const double limit_price,
                                              const double stop_loss,
                                              const double planned_risk);
int OpportunityPhasePortfolioHoldBars(const int component,
                                      const ulong ticket,
                                      const datetime opened_at,
                                      const int held_bars,
                                      const int native_hold_bars);
bool OpportunityPhasePortfolioShouldClose(const int component,
                                          const ulong ticket,
                                          const datetime opened_at,
                                          const int held_bars);
void OpportunityPhasePortfolioReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE OpportunityPhasePortfolioInitialize
#define ZETA_FRONTIER_RESET OpportunityPhasePortfolioReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL OpportunityPhasePortfolioObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED OpportunityPhasePortfolioObserveExpiration
#define ZETA_FRONTIER_PASSIVE_AFTER_EXPIRATION OpportunityPhasePortfolioAfterExpiration
#define ZETA_FRONTIER_HOLD_BARS OpportunityPhasePortfolioHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE OpportunityPhasePortfolioShouldClose
#define ZETA_FRONTIER_REPORT OpportunityPhasePortfolioReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ReceiverTimeFieldAdapter.mqh>
#include <ZetaTerminusNext\Frontier\ExpirationPhaseTransitionAdapter.mqh>
#include <ZetaTerminusNext\Frontier\OpportunityPhasePortfolioAdapter.mqh>
