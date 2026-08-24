#define ZETA_EXECUTION_VERSION "zt-next-frontier-expiration-phase-transition-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-passive-to-momentum-transition-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-EXPIRATION-PHASE-TRANSITION-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-EXPIRATION-PHASE-TRANSITION-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-expired-passive-efficient-escape-to-market-native-exit-risk-preserved"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-post-expiration-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_EXPIRATION_PHASE_TRANSITION_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\expiration-phase-transition-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825020
#define ZETA_MAGIC_RC4_BOTH 260825021
#define ZETA_MAGIC_US100_CROSS 260825022
#define ZETA_MAGIC_US30_PRESSURE 260825023
#define ZETA_MAGIC_US30_RETURN 260825024
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825025

enum ENUM_EXPIRATION_PHASE_TRANSITION_MODE
  {
   PHASE_TRANSITION_EFFICIENCY_Q75 = 0,
   PHASE_TRANSITION_EFFICIENCY_Q50 = 1,
   PHASE_TRANSITION_PERSISTENT_ESCAPE = 2
  };

input ENUM_EXPIRATION_PHASE_TRANSITION_MODE InpExpirationPhaseTransitionMode =
   PHASE_TRANSITION_EFFICIENCY_Q75;

bool ExpirationPhaseTransitionInitialize();
void ExpirationPhaseTransitionReset();
void ExpirationPhaseTransitionObserveExpiration(const int direction,
                                                const datetime expiration);
void ExpirationPhaseTransitionAfterExpiration(const int direction,
                                              const datetime expiration,
                                              const double feature,
                                              const double limit_price,
                                              const double stop_loss,
                                              const double planned_risk);
void ExpirationPhaseTransitionReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE ExpirationPhaseTransitionInitialize
#define ZETA_FRONTIER_RESET ExpirationPhaseTransitionReset
#define ZETA_FRONTIER_PASSIVE_EXPIRED ExpirationPhaseTransitionObserveExpiration
#define ZETA_FRONTIER_PASSIVE_AFTER_EXPIRATION ExpirationPhaseTransitionAfterExpiration
#define ZETA_FRONTIER_REPORT ExpirationPhaseTransitionReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ExpirationPhaseTransitionAdapter.mqh>
