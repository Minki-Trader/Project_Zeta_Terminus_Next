#property strict
#property version   "1.00"
#property description "Zeta Lab strategy independence research - standalone Cross"

#define SIRA_SELECTED_COMPONENT_VALUE 2
#define SIRA_EXECUTION_VERSION "zt-sira-v1-standalone-cross"
#define SIRA_RELEASE_ID "SIRA-V1-CROSS"
#define SIRA_PORTFOLIO_ID "ZT-SIRA-V1-CROSS"
#define SIRA_MAGIC_BASE 260824830
#define SIRA_STATE_MARKER "ZT_SIRA_V1_CROSS_STATE"
#define SIRA_STATE_PATH_A "ZetaSira\\sira\\cross-v1-state-a.csv"
#define SIRA_STATE_PATH_B "ZetaSira\\sira\\cross-v1-state-b.csv"
#define SIRA_EVENT_PATH_A "ZetaSira\\sira\\cross-v1-events-a.csv"
#define SIRA_EVENT_PATH_B "ZetaSira\\sira\\cross-v1-events-b.csv"
#define SIRA_CURRENT_SNAPSHOT_PATH_A "ZetaSira\\sira\\cross-v1-current-a.csv"
#define SIRA_CURRENT_SNAPSHOT_PATH_B "ZetaSira\\sira\\cross-v1-current-b.csv"
#define SIRA_OWNERSHIP_PATH "ZetaSira\\sira\\cross-v1.lock"

#include <ZetaSira\ZetaSiraAssembly.mqh>
