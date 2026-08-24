#define ZETA_EXECUTION_VERSION "zt-next-frontier-censored-path-receiver-v1"
#define ZETA_ECONOMIC_VERSION "zt-next-frontier-censored-path-selective-maturity-v1"
#define ZETA_PROJECT_ID "project-zeta-terminus-next-frontier"
#define ZETA_SCHEMA_VERSION "frontier-1"
#define ZETA_RELEASE_ID "NEXT-FRONTIER-CENSORED-PATH-RECEIVER-V1"
#define ZETA_PORTFOLIO_ID "ZT-NEXT-FRONTIER-CENSORED-PATH-RECEIVER-V1"
#define ZETA_ECONOMIC_FINGERPRINT "components6-expired-passive-censored-path-selective-return-release-cross-gate-entry-risk-fixed"
#define ZETA_EXECUTION_FINGERPRINT "tester-only-adapter-parent-assembly-distinct-magic-state-and-journal"
#define ZETA_STATE_MARKER "ZT_NEXT_FRONTIER_CENSORED_PATH_RECEIVER_STATE_V1"
#define ZETA_STATE_PATH_A "ZetaTerminusNext\\frontier\\censored-path-receiver-v1-state-a.csv"
#define ZETA_STATE_PATH_B "ZetaTerminusNext\\frontier\\censored-path-receiver-v1-state-b.csv"
#define ZETA_EVENT_PATH_A "ZetaTerminusNext\\frontier\\censored-path-receiver-v1-events-a.csv"
#define ZETA_EVENT_PATH_B "ZetaTerminusNext\\frontier\\censored-path-receiver-v1-events-b.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_A "ZetaTerminusNext\\frontier\\censored-path-receiver-v1-current-a.csv"
#define ZETA_CURRENT_SNAPSHOT_PATH_B "ZetaTerminusNext\\frontier\\censored-path-receiver-v1-current-b.csv"
#define ZETA_OWNERSHIP_PATH "ZetaTerminusNext\\frontier\\censored-path-receiver-v1.lock"
#define ZETA_MAGIC_RC16_LONG 260825000
#define ZETA_MAGIC_RC4_BOTH 260825001
#define ZETA_MAGIC_US100_CROSS 260825002
#define ZETA_MAGIC_US30_PRESSURE 260825003
#define ZETA_MAGIC_US30_RETURN 260825004
#define ZETA_MAGIC_US100_PASSIVE_LIMIT 260825005

enum ENUM_CENSORED_PATH_RECEIVER_MODE
  {
   CENSORED_RETURN_LOW_EFFICIENCY = 0,
   CENSORED_RETURN_WIDE_LOW_EFFICIENCY = 1,
   CENSORED_PAIRED_NON_APPROACH_GATE = 2
  };

input ENUM_CENSORED_PATH_RECEIVER_MODE InpCensoredPathReceiverMode =
   CENSORED_PAIRED_NON_APPROACH_GATE;

bool CensoredPathReceiverInitialize();
void CensoredPathReceiverReset();
void CensoredPathReceiverObserveSignal(const int component,
                                       const double value,
                                       const bool passed,
                                       const int direction);
void CensoredPathReceiverObserveExpiration(const int direction,
                                           const datetime expiration);
int CensoredPathReceiverHoldBars(const int component,
                                const ulong ticket,
                                const datetime opened_at,
                                const int held_bars,
                                const int native_hold_bars);
bool CensoredPathReceiverShouldClose(const int component,
                                    const ulong ticket,
                                    const datetime opened_at,
                                    const int held_bars);
void CensoredPathReceiverReport();

#define ZETA_FRONTIER_TESTER_ONLY 1
#define ZETA_FRONTIER_INITIALIZE CensoredPathReceiverInitialize
#define ZETA_FRONTIER_RESET CensoredPathReceiverReset
#define ZETA_FRONTIER_OBSERVE_SIGNAL CensoredPathReceiverObserveSignal
#define ZETA_FRONTIER_PASSIVE_EXPIRED CensoredPathReceiverObserveExpiration
#define ZETA_FRONTIER_HOLD_BARS CensoredPathReceiverHoldBars
#define ZETA_FRONTIER_SHOULD_CLOSE CensoredPathReceiverShouldClose
#define ZETA_FRONTIER_REPORT CensoredPathReceiverReport

#include "ZetaNextPre500FiniteRiskPortfolioV7.mq5"
#include <ZetaTerminusNext\Frontier\CensoredPathReceiverAdapter.mqh>
