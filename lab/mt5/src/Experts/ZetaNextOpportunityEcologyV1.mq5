#define ZETA_EXECUTION_VERSION "zt-next-frontier-opportunity-ecology-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-opportunity-ecology-elastic-risk-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-OPPORTUNITY-ECOLOGY-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-ECOLOGY-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-causal-opportunity-ecology-cross-relay-or-single-occupancy-volume2-position-risk-fixed"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_OPPORTUNITY_ECOLOGY_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\opportunity-ecology-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\opportunity-ecology-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\opportunity-ecology-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\opportunity-ecology-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\opportunity-ecology-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\opportunity-ecology-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\opportunity-ecology-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260824950
#define ZETA_MAGIC_RC4_BOTH 260824951
#define ZETA_MAGIC_US100_CROSS 260824952
#define ZETA_MAGIC_US30_PRESSURE 260824953
#define ZETA_MAGIC_US30_RETURN 260824954
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260824955

enum ENUM_OPPORTUNITY_ECOLOGY_MODE
  {
   ECOLOGY_CROSS_SYMBOL_RELAY_120 = 0,
   ECOLOGY_SINGLE_ACTIVE_POSITION = 1,
   ECOLOGY_RETURN_RECEIVER_RELAY_120 = 2
  };

input ENUM_OPPORTUNITY_ECOLOGY_MODE InpOpportunityEcologyMode =
   ECOLOGY_CROSS_SYMBOL_RELAY_120;

bool OpportunityEcologyInitialize();
void OpportunityEcologyReset();
void OpportunityEcologyObserveSignal(const int component,
                                      const double value,
                                      const bool passed,
                                      const int direction);
double OpportunityEcologyEntryVolume(const int component,
                                     const string symbol);
void OpportunityEcologyReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE OpportunityEcologyInitialize
#define ZETA_FRONTIER_RESET OpportunityEcologyReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL OpportunityEcologyObserveSignal
#define ZETA_FRONTIER_ENTRY_VOLUME OpportunityEcologyEntryVolume
#define ZETA_FRONTIER_REPORT OpportunityEcologyReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\OpportunityEcologyAdapter.mqh>
