#define ZETA_EXECUTION_VERSION "zt-next-frontier-opportunity-afterimage-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-opportunity-afterimage-release-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-OPPORTUNITY-AFTERIMAGE-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-AFTERIMAGE-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-expired-passive-decay-return-receiver-entry-preserved-release-geometry"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_OPPORTUNITY_AFTERIMAGE_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\opportunity-afterimage-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260824960
#define ZETA_MAGIC_RC4_BOTH 260824961
#define ZETA_MAGIC_US100_CROSS 260824962
#define ZETA_MAGIC_US30_PRESSURE 260824963
#define ZETA_MAGIC_US30_RETURN 260824964
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260824965

enum ENUM_OPPORTUNITY_AFTERIMAGE_MODE
  {
   AFTERIMAGE_RETURN_RELEASE_2 = 0,
   AFTERIMAGE_RETURN_RELEASE_3 = 1,
   AFTERIMAGE_RETURN_LOSS_ONLY_RELEASE_3 = 2
  };

input ENUM_OPPORTUNITY_AFTERIMAGE_MODE InpOpportunityAfterimageMode =
   AFTERIMAGE_RETURN_RELEASE_3;

bool OpportunityAfterimageInitialize();
void OpportunityAfterimageReset();
void OpportunityAfterimageObserveSignal(const int component,
                                         const double value,
                                         const bool passed,
                                         const int direction);
void OpportunityAfterimageObservePassiveExpiration(const int direction,
                                                    const datetime expiration);
bool OpportunityAfterimageShouldClose(const int component,
                                      const ulong ticket,
                                      const datetime opened_at,
                                      const int held_bars);
void OpportunityAfterimageReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE OpportunityAfterimageInitialize
#define ZETA_FRONTIER_RESET OpportunityAfterimageReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL OpportunityAfterimageObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED OpportunityAfterimageObservePassiveExpiration
#define ZETA_FRONTIER_SHOULD_CLOSE OpportunityAfterimageShouldClose
#define ZETA_FRONTIER_REPORT OpportunityAfterimageReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\OpportunityAfterimageAdapter.mqh>
