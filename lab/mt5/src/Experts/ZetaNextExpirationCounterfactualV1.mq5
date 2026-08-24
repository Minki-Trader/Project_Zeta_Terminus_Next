#define ZETA_EXECUTION_VERSION "zt-next-frontier-expiration-counterfactual-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-expiration-shadow-path-label-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-EXPIRATION-COUNTERFACTUAL-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-EXPIRATION-COUNTERFACTUAL-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-passive-expiration-deferred-shadow-path-measurement-parent-economics"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-deferred-label-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_EXPIRATION_COUNTERFACTUAL_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\expiration-counterfactual-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825010
#define ZETA_MAGIC_RC4_BOTH 260825011
#define ZETA_MAGIC_US100_CROSS 260825012
#define ZETA_MAGIC_US30_PRESSURE 260825013
#define ZETA_MAGIC_US30_RETURN 260825014
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825015

bool ExpirationCounterfactualInitialize();
void ExpirationCounterfactualReset();
void ExpirationCounterfactualObserveExpiration(const int direction,
                                               const datetime expiration);
void ExpirationCounterfactualReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE ExpirationCounterfactualInitialize
#define ZETA_FRONTIER_RESET ExpirationCounterfactualReset
#define ZETA_FRONTIER_PASSIVE_EXPIRED ExpirationCounterfactualObserveExpiration
#define ZETA_FRONTIER_REPORT ExpirationCounterfactualReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\ExpirationCounterfactualAdapter.mqh>
