#define ZETA_EXECUTION_VERSION "zt-next-frontier-unfilled-distance-field-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-censored-limit-path-measurement-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-UNFILLED-DISTANCE-FIELD-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-UNFILLED-DISTANCE-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-passive-expiration-censored-tick-path-measurement-parent-economics"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-measurement-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_UNFILLED_DISTANCE_FIELD_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\unfilled-distance-field-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260824980
#define ZETA_MAGIC_RC4_BOTH 260824981
#define ZETA_MAGIC_US100_CROSS 260824982
#define ZETA_MAGIC_US30_PRESSURE 260824983
#define ZETA_MAGIC_US30_RETURN 260824984
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260824985

bool UnfilledDistanceFieldInitialize();
void UnfilledDistanceFieldReset();
void UnfilledDistanceFieldObserveExpiration(const int direction,
                                            const datetime expiration);
void UnfilledDistanceFieldReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE UnfilledDistanceFieldInitialize
#define ZETA_FRONTIER_RESET UnfilledDistanceFieldReset
#define ZETA_FRONTIER_PASSIVE_EXPIRED UnfilledDistanceFieldObserveExpiration
#define ZETA_FRONTIER_REPORT UnfilledDistanceFieldReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\UnfilledDistanceFieldAdapter.mqh>
