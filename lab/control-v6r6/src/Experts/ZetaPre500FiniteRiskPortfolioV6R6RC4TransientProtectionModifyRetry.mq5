#property strict
#property version   "6.60"
#property description "Zeta Axis B RC4 transient protection modify retry portfolio"
#property description "Execution version: zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry"

#include <Trade\Trade.mqh>

input double InpReferenceCapitalUSD  = 100.0;
input double InpPriorProjectRealizedNetUSD = 0.0;
input double InpBaseVolume           = 0.01;
input double InpAdditionStepUSD      = 150.0;
input double InpMaximumMarginFraction = 0.45;
input double InpMaximumPositionRiskFraction = 0.04;
input double InpMaximumAggregateRiskFraction = 0.12;
input double InpUnmodelledRiskReserveFraction = 0.25;
input double InpStopPlacementHeadroomFraction = 0.25;
input int    InpMaxEntryDelayMinutes = 2;
input int    InpDeviationPoints      = 100;
input bool   InpAllowNewEntries       = false;
input long   InpExpectedLiveAccountLogin = 0;
input int    InpEventCapacity         = 4096;
input int    InpSnapshotSeconds       = 60;

const string EXECUTION_VERSION =
   "zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry";
const string ECONOMIC_VERSION =
   "zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-axis-b";
const string PORTFOLIO_ID = "ZT-PORT-PRE500-FR6R6-RC4MR-cda6e28b13f4";
const string ECONOMIC_FINGERPRINT =
   "ref100-base0.01-step150-margin0.45-delay2-deviation100-inert-market-execution-quote-age3s-pre500-components6-passive-fixed0.01-always-m15-lb12-en1-ex0.25-offset0.25-activation4-hold16-posrisk0.04-aggrisk0.12-reserve0.25-headroom0.25-admission-reserved-broker-sl-session-clock-eet-v1-calendar2022-2028-rc4-check8-three-frozen-ordinal-heads-votesum-le-minus2-retain-original-loss0.25-one-shot-shadow-accepted-occupancy";
const string EXECUTION_FINGERPRINT =
   "account-bound-runtime-pre500-fr6r6-rc4-transient-protection-modify-retry-fresh3s-market-protection-recovery-multideal-lifecycle-at-most-once-decision-journal-required-market-execution-session-clock-contract-global-foreign-exposure-block-common-cross-terminal-lock-authoritative-position-reconciliation5000ms-operational-entry-gate-connection-deferred-passive-cancel-recovery-shadow-accepted-rc4-occupancy-prejournalled-stop-modify-recovery-persisted-shadow-millisecond-ordinal-cursor-complete-causal-copyticksrange-fail-closed-native-m30-boundary-synchronous-state-readback-every-notification-exact-deal-ms-activation-seal-same-ms-tail-outcome-excluded-single-transient-modify-retry-first-strictly-later-fresh-tick";
const string STATE_MARKER =
   "ZT_PRE500_FINITE_RISK_PORTFOLIO_STATE_V6R6_RC4_TRANSIENT_PROTECTION_MODIFY_RETRY";
const string STATE_PATH_A =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-state-a.csv";
const string STATE_PATH_B =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-state-b.csv";
const string EVENT_PATH_A =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-events-a.csv";
const string EVENT_PATH_B =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-events-b.csv";
const string CURRENT_SNAPSHOT_PATH_A =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-current-a.csv";
const string CURRENT_SNAPSHOT_PATH_B =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry-current-b.csv";
const string OWNERSHIP_PATH =
   "ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v6r6-rc4-transient-protection-modify-retry.lock";
const int FILE_OPEN_ATTEMPTS = 5;
const int FILE_RETRY_DELAY_MS = 100;
const ulong COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS = 5000;
const int COMPLETED_DEAL_RECONCILIATION_POLL_MS = 10;
const double MAX_EXECUTABLE_TICK_AGE_SECONDS = 3.0;
const int SESSION_CONTRACT_FIRST_YEAR = 2022;
const int SESSION_CONTRACT_LAST_YEAR = 2028;
const int SERVER_UTC_OFFSET_TOLERANCE_SECONDS = 120;
const string US_EQUITY_CALENDAR_VERSION =
   "NYSE-2022-2028-reviewed-20260818-v1";

#define COMPONENT_COUNT 6
const int RC16_LONG = 0;
const int RC4_BOTH = 1;
const int US100_CROSS = 2;
const int US30_PRESSURE = 3;
const int US30_RETURN_REV_LONG = 4;
const int US100_PASSIVE_LIMIT = 5;
const int PASSIVE_LOOKBACK = 12;
const int PASSIVE_SCALE_RETURNS = 96;
const double PASSIVE_ENTRY_STRENGTH = 1.0;
const double PASSIVE_EXIT_STRENGTH = 0.25;
const double PASSIVE_LIMIT_OFFSET_RANGE_SCALE = 0.25;
const int PASSIVE_ACTIVATION_BARS = 4;
const int PASSIVE_MAXIMUM_HOLD_BARS = 16;
const int PASSIVE_BAR_SECONDS = 15 * 60;
const int JOURNAL_NONE = 0;
const int JOURNAL_SIGNAL_DECIDED = 1;
const int JOURNAL_ORDER_ATTEMPTED = 2;
const int JOURNAL_BROKER_STATE_ADOPTED = 3;
const ulong MAGIC_RC16_LONG = 260823301;
const ulong MAGIC_RC4_BOTH = 260823302;
const ulong MAGIC_US100_CROSS = 260823303;
const ulong MAGIC_US30_PRESSURE = 260823304;
const ulong MAGIC_US30_RETURN = 260823305;
const ulong MAGIC_US100_PASSIVE_LIMIT = 260823306;

string COMPONENT_IDS[COMPONENT_COUNT] =
  {
   "ZT-M30-US30-RANGE-COMP-61f61deaba",
   "ZT-M30-US30-RANGE-COMP-64efb16616",
   "ZT-H1-US100-CROSS-IN-14b72317b7",
   "ZT-M30-US30-INTRADAY-R-2eb111fc46",
   "ZT-H1-US30-RETURN-I-c870a788ec",
   "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8"
  };

string COMPONENT_SYMBOLS[COMPONENT_COUNT] =
  {
   "US30", "US30", "US100", "US30", "US30", "US100"
  };

ENUM_TIMEFRAMES COMPONENT_TIMEFRAMES[COMPONENT_COUNT] =
  {
   PERIOD_M30, PERIOD_M30, PERIOD_H1, PERIOD_M30, PERIOD_H1, PERIOD_M15
  };

int COMPONENT_HOLD_BARS[COMPONENT_COUNT] = {8, 12, 4, 8, 6, 16};
ulong COMPONENT_MAGICS[COMPONENT_COUNT] =
  {
   MAGIC_RC16_LONG,
   MAGIC_RC4_BOTH,
   MAGIC_US100_CROSS,
   MAGIC_US30_PRESSURE,
   MAGIC_US30_RETURN,
   MAGIC_US100_PASSIVE_LIMIT
  };

const int ARC_RC4_CHECKPOINT_BARS = 8;
const long RC4_NATIVE_M30_BUCKET_MSC = 1800000;
const double ARC_RC4_RETAINED_LOSS_FRACTION = 0.25;
const double ARC_MARKET_LOWER = -0.24107458;
const double ARC_MARKET_UPPER = 0.31112079;
const double ARC_DECISION_LOWER = -0.42656390;
const double ARC_DECISION_UPPER = 0.24808705;
const double ARC_CONFIRM_LOWER = -0.07240202;
const double ARC_CONFIRM_UPPER = 0.33558626;
const int ARC_ADVERSE_VOTE_THRESHOLD = -2;

struct EntryDealAggregate
  {
   ulong first_deal;
   ulong last_deal;
   ulong order_ticket;
   long first_time_msc;
   long last_time_msc;
   datetime first_time_server;
   int direction;
   long volume_steps;
   double volume;
   double price;
   double transaction_cost;
   double spread_price;
   double adverse_slippage;
   bool cost_known;
   int deal_count;
  };

struct SequencedExitDeal
  {
   ulong ticket;
   long time_msc;
  };

CTrade trade;
datetime last_decision_bar[COMPONENT_COUNT];
datetime entry_check_bar[COMPONENT_COUNT];
int entry_check_signal_known[COMPONENT_COUNT];
int entry_check_signal_passed[COMPONENT_COUNT];
double entry_check_signal_value[COMPONENT_COUNT];
int entry_check_direction[COMPONENT_COUNT];
double entry_check_order_price[COMPONENT_COUNT];
double entry_check_volume[COMPONENT_COUNT];
double entry_check_stop_loss[COMPONENT_COUNT];
double entry_check_planned_risk_usd[COMPONENT_COUNT];
string entry_check_result[COMPONENT_COUNT];
datetime last_close_attempt_server[COMPONENT_COUNT];
double entry_spread_price[COMPONENT_COUNT];
double entry_transaction_cost[COMPONENT_COUNT];
double entry_adverse_slippage[COMPONENT_COUNT];
long closed_trades[COMPONENT_COUNT];
double component_stressed_net[COMPONENT_COUNT];
datetime sizing_server_day = 0;
int day_volume_multiplier = 1;
bool safety_stopped = false;
double stressed_balance = 100.0;
double stressed_peak = 100.0;
double stressed_maximum_closed_drawdown = 0.0;
double project_realized_net = 0.0;
ulong tracked_position_identifier[COMPONENT_COUNT];
ulong last_processed_exit_deal[COMPONENT_COUNT];
long last_processed_exit_time_msc[COMPONENT_COUNT];
bool lifecycle_stop_loss_seen[COMPONENT_COUNT];
datetime entry_time_server[COMPONENT_COUNT];
int entry_direction[COMPONENT_COUNT];
double entry_volume[COMPONENT_COUNT];
double entry_feature[COMPONENT_COUNT];
double entry_stop_loss[COMPONENT_COUNT];
double entry_planned_risk_usd[COMPONENT_COUNT];
bool entry_cost_known[COMPONENT_COUNT];
long state_sequence = 0;
long event_records = 0;
long event_segment_records = 0;
int event_segment = 0;
datetime started_utc = 0;
datetime last_snapshot_utc = 0;
datetime last_reconcile_server = 0;
double account_peak_equity = 0.0;
double account_maximum_drawdown = 0.0;
bool persistence_failed = false;
bool persistence_error_logged = false;
bool broker_mismatch = false;
bool foreign_exposure = false;
bool foreign_exposure_logged = false;
bool runtime_ready = false;
bool runtime_error_logged = false;
bool trade_operation_active = false;
bool pending_reconcile = false;
bool tester_mode = false;
bool server_clock_contract_logged = false;
bool server_clock_mismatch_logged = false;
datetime unverified_calendar_logged_day = 0;
long bound_account_login = 0;
int ownership_handle = INVALID_HANDLE;
ulong tracked_passive_pending_order = 0;
bool passive_cancel_pending = false;
datetime passive_pending_expiration = 0;
int passive_pending_direction = 0;
double passive_pending_feature = 0.0;
double passive_pending_limit_price = 0.0;
double passive_pending_stop_loss = 0.0;
double passive_pending_planned_risk_usd = 0.0;
datetime passive_next_entry_current_bar = 0;
datetime passive_last_feature_attempt_bar = 0;
datetime passive_last_feature_attempt_server = 0;
long passive_pending_placements = 0;
long passive_cancel_connection_deferrals = 0;
long passive_pending_expirations = 0;
long passive_completed_entries = 0;
long passive_placement_failures = 0;
long passive_stale_price_rejections = 0;
long passive_unexpected_order_outcomes = 0;
long passive_margin_calculation_failures = 0;
long passive_margin_skips = 0;
long passive_price_constraint_skips = 0;
long protection_calculation_failures = 0;
long risk_admission_skips = 0;
long protection_mismatches = 0;
long stop_loss_exits = 0;
double maximum_aggregate_planned_risk_usd = 0.0;
int decision_journal_stage = JOURNAL_NONE;
int decision_journal_component = -1;
datetime decision_journal_bar = 0;
int decision_journal_direction = 0;
double decision_journal_feature = 0.0;
datetime decision_journal_deadline = 0;
datetime decision_journal_attempted_server = 0;
ulong decision_journal_adopted_ticket = 0;
long journal_signal_decisions = 0;
long journal_order_attempts = 0;
long journal_broker_adoptions = 0;
long journal_restart_resolutions = 0;
ulong arc_lifecycle_identifier = 0;
datetime arc_last_attempt_bar = 0;
bool arc_checkpoint_evaluated = false;
bool arc_lifecycle_compressed = false;
double arc_original_stop_loss = 0.0;
bool arc_modify_pending = false;
double arc_pending_stop_loss = 0.0;
bool arc_modify_retry_pending = false;
bool arc_modify_retry_consumed = false;
long arc_modify_retry_after_msc = 0;
uint arc_modify_retry_initial_retcode = 0;
long arc_modify_retry_intents = 0;
long arc_modify_retry_attempts = 0;
long arc_modify_retry_successes = 0;
long arc_modify_retry_adoptions = 0;
long arc_modify_retry_holds = 0;
long arc_checkpoints = 0;
long arc_adverse_triggers = 0;
long arc_compressions_placed = 0;
long arc_compression_refusals = 0;
long arc_data_unavailable = 0;
bool rc4_shadow_occupied = false;
ulong rc4_shadow_source_identifier = 0;
datetime rc4_shadow_entry_time = 0;
int rc4_shadow_direction = 0;
double rc4_shadow_original_stop_loss = 0.0;
long rc4_shadow_last_observed_msc = 0;
long rc4_shadow_cursor_ordinal = 0;
long rc4_shadow_activations = 0;
long rc4_shadow_stop_releases = 0;
long rc4_shadow_deadline_releases = 0;
long rc4_shadow_entry_blocks = 0;
long rc4_shadow_catchup_scans = 0;
long rc4_shadow_catchup_ticks = 0;
long rc4_shadow_catchup_stop_releases = 0;
long rc4_shadow_catchup_failures = 0;
bool rc4_shadow_catchup_required = false;
bool rc4_shadow_catchup_failure_logged = false;
long rc4_shadow_cursor_checkpoint_observation_bucket = 0;
long rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
long rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
long rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
long rc4_shadow_cursor_checkpoint_eligible = 0;
long rc4_shadow_cursor_checkpoint_persisted = 0;
long rc4_shadow_cursor_checkpoint_save_failures = 0;
long rc4_shadow_cursor_checkpoint_readback_failures = 0;
long rc4_shadow_cursor_checkpoint_event_failures = 0;
long rc4_shadow_cursor_checkpoint_duplicate_bucket_failures = 0;
long rc4_shadow_cursor_checkpoint_regressions = 0;
bool rc4_shadow_cursor_checkpoint_pending = false;
bool rc4_shadow_activation_sealed = false;
bool rc4_shadow_activation_seal_pending = false;
bool rc4_shadow_activation_seal_failure_logged = false;
ulong rc4_shadow_activation_deal_ticket = 0;
long rc4_shadow_activation_deal_time_msc = 0;
double rc4_shadow_activation_deal_price = 0.0;
int rc4_shadow_activation_deal_reason = 0;
double rc4_shadow_activation_protected_stop = 0.0;
bool rc4_shadow_activation_sampled_tick_known = false;
datetime rc4_shadow_activation_sampled_time = 0;
long rc4_shadow_activation_sampled_time_msc = 0;
double rc4_shadow_activation_sampled_bid = 0.0;
double rc4_shadow_activation_sampled_ask = 0.0;
double rc4_shadow_activation_sampled_last = 0.0;
ulong rc4_shadow_activation_sampled_volume = 0;
double rc4_shadow_activation_sampled_volume_real = 0.0;
uint rc4_shadow_activation_sampled_flags = 0;
long rc4_shadow_activation_boundary_msc = 0;
long rc4_shadow_activation_boundary_ordinal = 0;
long rc4_shadow_activation_seal_eligible = 0;
long rc4_shadow_activation_seal_sealed = 0;
long rc4_shadow_activation_seal_pending_count = 0;
long rc4_shadow_activation_seal_save_attempts = 0;
long rc4_shadow_activation_seal_save_failures = 0;
long rc4_shadow_activation_seal_readbacks = 0;
long rc4_shadow_activation_seal_readback_failures = 0;
long rc4_shadow_activation_seal_failures = 0;
long rc4_shadow_activation_seal_ambiguities = 0;
long rc4_shadow_activation_last_sealed_msc = 0;
long rc4_shadow_activation_last_sealed_ordinal = 0;
long rc4_shadow_activation_pre_boundary_consumed = 0;
long tester_dispatched_ticks = 0;
long tester_transaction_dispatches = 0;
long tester_clock_dispatches = 0;
long tester_retry_dispatches = 0;
long tester_last_m15_slot = -1;
bool tester_data_retry_active = false;

bool SaveState();
bool RecordEvent(const int component,
                 const string event_name,
                 const double value_a,
                 const double value_b,
                 const string detail);
bool ReconcileBrokerState(const bool startup);
bool NewEntriesAuthorized();
bool NewEntriesOperationallyAllowed();
bool BufferedPlannedRisk(const string symbol,
                         const int direction,
                         const double volume,
                         const double entry_price,
                         const double stop_loss,
                         double &planned_risk);
bool CloseComponent(const int component, const ulong ticket);
bool CancelPassivePendingOrder(const ulong order_ticket,
                               const string reason);
void MakeExistingRiskSafe(const string reason);
void ClearArcLifecycleState();
void ClearRC4ShadowState();
bool ArcOriginalStopReached(const int direction,
                            const double original_stop,
                            const MqlTick &tick);
void ActivateRC4ShadowAfterCompressedExit(const ulong identifier,
                                          const datetime entered_at,
                                          const int direction,
                                          const double original_stop,
                                          const ulong deal_ticket,
                                          const long exit_time_msc,
                                          const double deal_price,
                                          const ENUM_DEAL_REASON deal_reason,
                                          const double protected_stop,
                                          const MqlTick &sampled_tick,
                                          const bool sampled_tick_known);
bool ResolveAndPersistRC4ShadowActivationSeal();
void ProcessRC4ShadowOccupancy();
bool PersistRC4ShadowCursorCheckpointIfEligible(const long prior_msc,
                                                const long prior_ordinal);
void ProcessRC4AdverseRiskCompression();
bool ReconcileArcPendingModify(const bool restart_recovery);
bool IsArcTransientModifyRetcode(const uint retcode);
void ProcessArcModifyRetry();


bool IsCompletedTradeRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_DONE);
  }


bool IsCompletedMarketTradeRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_DONE ||
          retcode == TRADE_RETCODE_DONE_PARTIAL);
  }


bool IsPendingPlacementRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_PLACED ||
          retcode == TRADE_RETCODE_DONE);
  }


bool WaitForSingleOwnedPosition(const int component,
                                ulong &ticket,
                                datetime &opened_at)
  {
   const ulong started = GetTickCount64();
   while(true)
     {
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count == 1 && PositionSelectByTicket(ticket))
         return(true);
      if(count > 1 || tester_mode ||
         GetTickCount64() - started >=
         COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
         return(false);
      Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
     }
   return(false);
  }


datetime ServerMidnight()
  {
   MqlDateTime parts = {};
   TimeCurrent(parts);
   parts.hour = 0;
   parts.min = 0;
   parts.sec = 0;
   return(StructToTime(parts));
  }


datetime CalendarDate(const int year, const int month, const int day)
  {
   MqlDateTime parts = {};
   parts.year = year;
   parts.mon = month;
   parts.day = day;
   return(StructToTime(parts));
  }


bool SameCalendarDate(const datetime left, const datetime right)
  {
   MqlDateTime left_parts = {};
   MqlDateTime right_parts = {};
   TimeToStruct(left, left_parts);
   TimeToStruct(right, right_parts);
   return(left_parts.year == right_parts.year &&
          left_parts.mon == right_parts.mon &&
          left_parts.day == right_parts.day);
  }


datetime NthWeekday(const int year,
                    const int month,
                    const int weekday,
                    const int occurrence)
  {
   const datetime first = CalendarDate(year, month, 1);
   MqlDateTime parts = {};
   TimeToStruct(first, parts);
   const int offset = (weekday - parts.day_of_week + 7) % 7;
   return(first + (offset + 7 * (occurrence - 1)) * 86400);
  }


datetime LastWeekday(const int year,
                     const int month,
                     const int weekday)
  {
   const int next_month = (month == 12 ? 1 : month + 1);
   const int next_year = (month == 12 ? year + 1 : year);
   datetime day = CalendarDate(next_year, next_month, 1) - 86400;
   MqlDateTime parts = {};
   TimeToStruct(day, parts);
   const int offset = (parts.day_of_week - weekday + 7) % 7;
   return(day - offset * 86400);
  }


datetime ObservedFixedHoliday(const int year,
                              const int month,
                              const int day)
  {
   datetime holiday = CalendarDate(year, month, day);
   MqlDateTime parts = {};
   TimeToStruct(holiday, parts);
   if(parts.day_of_week == 6)
      holiday -= 86400;
   else if(parts.day_of_week == 0)
      holiday += 86400;
   return(holiday);
  }


datetime EasterSunday(const int year)
  {
   const int a = year % 19;
   const int b = year / 100;
   const int c = year % 100;
   const int d = b / 4;
   const int e = b % 4;
   const int f = (b + 8) / 25;
   const int g = (b - f + 1) / 3;
   const int h = (19 * a + b - d - g + 15) % 30;
   const int i = c / 4;
   const int k = c % 4;
   const int l = (32 + 2 * e + 2 * i - h - k) % 7;
   const int m = (a + 11 * h + 22 * l) / 451;
   const int month = (h + l - 7 * m + 114) / 31;
   const int day = ((h + l - 7 * m + 114) % 31) + 1;
   return(CalendarDate(year, month, day));
  }


bool SessionContractYearVerified(const int year)
  {
   return(year >= SESSION_CONTRACT_FIRST_YEAR &&
          year <= SESSION_CONTRACT_LAST_YEAR);
  }


int ExpectedFPMarketsUTCOffsetSeconds(const datetime utc_now)
  {
   MqlDateTime parts = {};
   TimeToStruct(utc_now, parts);
   const datetime summer_start =
      LastWeekday(parts.year, 3, 0) + 3600;
   const datetime summer_end =
      LastWeekday(parts.year, 10, 0) + 3600;
   return(utc_now >= summer_start && utc_now < summer_end
          ? 3 * 3600
          : 2 * 3600);
  }


int ExpectedNewYorkUTCOffsetSeconds(const datetime utc_now)
  {
   MqlDateTime parts = {};
   TimeToStruct(utc_now, parts);
   const datetime summer_start =
      NthWeekday(parts.year, 3, 0, 2) + 7 * 3600;
   const datetime summer_end =
      NthWeekday(parts.year, 11, 0, 1) + 6 * 3600;
   return(utc_now >= summer_start && utc_now < summer_end
          ? -4 * 3600
          : -5 * 3600);
  }


bool FPMarketsServerClockCompatible()
  {
   // Entry hours are frozen FPMarkets server-wall economic variables.  This
   // contract blocks an offset-convention change; it does not remap them to
   // New York time during the US/Europe DST mismatch weeks.
   const datetime server_now = TimeTradeServer();
   MqlDateTime server_parts = {};
   TimeToStruct(server_now, server_parts);
   if(server_now <= 0 || !SessionContractYearVerified(server_parts.year))
     {
      if(!server_clock_mismatch_logged)
        {
         PrintFormat("%s session-clock contract unavailable server_year=%d "
                     "verified=%d-%d; new entries blocked",
                     EXECUTION_VERSION,
                     server_parts.year,
                     SESSION_CONTRACT_FIRST_YEAR,
                     SESSION_CONTRACT_LAST_YEAR);
         server_clock_mismatch_logged = true;
        }
      return(false);
     }

   if(tester_mode)
     {
      if(!server_clock_contract_logged)
        {
         PrintFormat("%s session-clock contract tester_mode=true "
                     "calendar=%s; TimeGMT offset is not observable in "
                     "Strategy Tester, fixed server-hour economics retained",
                     EXECUTION_VERSION,
                     US_EQUITY_CALENDAR_VERSION);
         server_clock_contract_logged = true;
        }
      return(true);
     }

   const datetime utc_now = TimeGMT();
   if(utc_now <= 0)
     {
      if(!server_clock_mismatch_logged)
        {
         PrintFormat("%s session-clock UTC unavailable; new entries blocked",
                     EXECUTION_VERSION);
         server_clock_mismatch_logged = true;
        }
      return(false);
     }
   const int expected_server_offset =
      ExpectedFPMarketsUTCOffsetSeconds(utc_now);
   const int expected_new_york_offset =
      ExpectedNewYorkUTCOffsetSeconds(utc_now);
   const long observed_server_offset =
      (long)server_now - (long)utc_now;
   const bool compatible =
      MathAbs((double)(observed_server_offset - expected_server_offset)) <=
      SERVER_UTC_OFFSET_TOLERANCE_SECONDS;
   if(!compatible)
     {
      if(!server_clock_mismatch_logged)
        {
         PrintFormat("%s session-clock mismatch observed_server_utc=%I64d "
                     "expected_server_utc=%d tolerance=%d; new entries blocked",
                     EXECUTION_VERSION,
                     observed_server_offset,
                     expected_server_offset,
                     SERVER_UTC_OFFSET_TOLERANCE_SECONDS);
         server_clock_mismatch_logged = true;
        }
      return(false);
     }

   if(server_clock_mismatch_logged)
      PrintFormat("%s session-clock contract restored", EXECUTION_VERSION);
   server_clock_mismatch_logged = false;
   if(!server_clock_contract_logged)
     {
      PrintFormat("%s session-clock contract observed_server_utc=%I64d "
                  "expected_server_utc=%d expected_new_york_utc=%d "
                  "server_new_york_gap_hours=%d calendar=%s",
                  EXECUTION_VERSION,
                  observed_server_offset,
                  expected_server_offset,
                  expected_new_york_offset,
                  (expected_server_offset - expected_new_york_offset) / 3600,
                  US_EQUITY_CALENDAR_VERSION);
      server_clock_contract_logged = true;
     }
   return(true);
  }


bool IsExtraordinaryUSEquityClosureDate(const datetime today)
  {
   // Published calendars are supplemented by known extraordinary closures as
   // of this calendar version's 2026-08-18 review date.
   MqlDateTime parts = {};
   TimeToStruct(today, parts);
   return(parts.year == 2025 && parts.mon == 1 && parts.day == 9);
  }


bool IsUSEquityClosureDate()
  {
   const datetime today = ServerMidnight();
   MqlDateTime parts = {};
   TimeToStruct(today, parts);
   const int year = parts.year;
   if(!SessionContractYearVerified(year))
     {
      if(unverified_calendar_logged_day != today)
        {
         PrintFormat("%s US-equity calendar unverified date=%s version=%s; "
                     "calendar-dependent entry blocked",
                     EXECUTION_VERSION,
                     TimeToString(today, TIME_DATE),
                     US_EQUITY_CALENDAR_VERSION);
         unverified_calendar_logged_day = today;
        }
      return(true);
     }
   if(IsExtraordinaryUSEquityClosureDate(today))
      return(true);
   datetime holidays[];
   ArrayResize(holidays, 10);
   holidays[0] = ObservedFixedHoliday(year, 1, 1);
   holidays[1] = NthWeekday(year, 1, 1, 3);
   holidays[2] = NthWeekday(year, 2, 1, 3);
   holidays[3] = EasterSunday(year) - 2 * 86400;
   holidays[4] = LastWeekday(year, 5, 1);
   holidays[5] = ObservedFixedHoliday(year, 6, 19);
   holidays[6] = ObservedFixedHoliday(year, 7, 4);
   holidays[7] = NthWeekday(year, 9, 1, 1);
   holidays[8] = NthWeekday(year, 11, 4, 4);
   holidays[9] = ObservedFixedHoliday(year, 12, 25);
   for(int index = 0; index < ArraySize(holidays); ++index)
      if(holidays[index] > 0 && SameCalendarDate(today, holidays[index]))
         return(true);

   const datetime thanksgiving = NthWeekday(year, 11, 4, 4);
   if(SameCalendarDate(today, thanksgiving + 86400))
      return(true);
   if(parts.mon == 7 && parts.day == 3 &&
      parts.day_of_week >= 1 && parts.day_of_week <= 5)
      return(true);
   if(parts.mon == 12 && parts.day == 24 &&
      parts.day_of_week >= 1 && parts.day_of_week <= 5)
      return(true);
   return(false);
  }


bool IsOwnedMagic(const ulong magic)
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(COMPONENT_MAGICS[component] == magic)
         return(true);
   return(false);
  }


void EngageSafetyStop(const string reason)
  {
   if(safety_stopped)
      return;
   safety_stopped = true;
   PrintFormat("%s SAFETY_STOP %s", EXECUTION_VERSION, reason);
   if(runtime_ready)
     {
      RecordEvent(-1, "SAFETY_STOP", 0.0, 0.0, reason);
      SaveState();
     }
  }


bool LiveAccountIdentityCompatible()
  {
   if(tester_mode)
      return(true);
   const long current_login =
      (long)AccountInfoInteger(ACCOUNT_LOGIN);
   if(bound_account_login <= 0 || current_login != bound_account_login)
      return(false);
   if(!InpAllowNewEntries)
      return(true);
   return(InpExpectedLiveAccountLogin > 0 &&
          current_login == InpExpectedLiveAccountLogin);
  }


bool EnforceLiveAccountIdentity()
  {
   if(LiveAccountIdentityCompatible())
      return(true);
   broker_mismatch = true;
   EngageSafetyStop("live account identity mismatch");
   return(false);
  }


bool SelectedPositionProtectionMatches(const int component,
                                       string &detail)
  {
   detail = "";
   const string symbol = PositionGetString(POSITION_SYMBOL);
   const ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const int direction =
      (type == POSITION_TYPE_BUY ? 1 :
       (type == POSITION_TYPE_SELL ? -1 : 0));
   const double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
   const double volume = PositionGetDouble(POSITION_VOLUME);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   double expected_stop = entry_stop_loss[component];
   double admitted_risk = entry_planned_risk_usd[component];
   if(component == US100_PASSIVE_LIMIT && expected_stop <= 0.0 &&
      tracked_passive_pending_order > 0)
     {
      expected_stop = passive_pending_stop_loss;
      admitted_risk = passive_pending_planned_risk_usd;
     }
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const bool pending_arc_modify =
      (component == RC4_BOTH &&
       (arc_modify_pending || arc_modify_retry_pending) &&
       arc_pending_stop_loss > 0.0);
   const bool stop_matches_saved =
      (tick_size > 0.0 && expected_stop > 0.0 &&
       MathAbs(broker_stop - expected_stop) <=
       0.5 * tick_size + 1.0e-9);
   const bool stop_matches_pending =
      (pending_arc_modify && tick_size > 0.0 &&
       MathAbs(broker_stop - arc_pending_stop_loss) <=
       0.5 * tick_size + 1.0e-9);
   if(direction == 0 || open_price <= 0.0 || volume <= 0.0 ||
      tick_size <= 0.0 || broker_stop <= 0.0 || expected_stop <= 0.0 ||
      admitted_risk <= 0.0 ||
      (direction > 0 && broker_stop >= open_price) ||
      (direction < 0 && broker_stop <= open_price) ||
      (!stop_matches_saved && !stop_matches_pending))
     {
      detail = StringFormat("invalid stop component=%d open=%.5f broker=%.5f expected=%.5f pending=%.5f",
                            component,
                            open_price,
                            broker_stop,
                            expected_stop,
                            arc_pending_stop_loss);
      return(false);
     }
   double actual_risk = 0.0;
   if(!BufferedPlannedRisk(symbol,
                           direction,
                           volume,
                           open_price,
                           broker_stop,
                           actual_risk) ||
      actual_risk > admitted_risk + MathMax(0.01, admitted_risk * 0.01))
     {
      detail = StringFormat("risk mismatch component=%d actual=%.4f admitted=%.4f",
                            component,
                            actual_risk,
                            admitted_risk);
      return(false);
     }
   return(true);
  }


bool SelectedPassiveOrderProtectionMatches(string &detail)
  {
   detail = "";
   const ENUM_ORDER_TYPE type =
      (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   const int direction =
      (type == ORDER_TYPE_BUY_LIMIT ? 1 :
       (type == ORDER_TYPE_SELL_LIMIT ? -1 : 0));
   const double price = OrderGetDouble(ORDER_PRICE_OPEN);
   const double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
   const double broker_stop = OrderGetDouble(ORDER_SL);
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   if(direction == 0 || price <= 0.0 || volume <= 0.0 || tick_size <= 0.0 ||
      broker_stop <= 0.0 || passive_pending_stop_loss <= 0.0 ||
      passive_pending_planned_risk_usd <= 0.0 ||
      (direction > 0 && broker_stop >= price) ||
      (direction < 0 && broker_stop <= price) ||
      MathAbs(broker_stop - passive_pending_stop_loss) >
      0.5 * tick_size + 1.0e-9)
     {
      detail = StringFormat("invalid pending stop price=%.5f broker=%.5f expected=%.5f",
                            price,
                            broker_stop,
                            passive_pending_stop_loss);
      return(false);
     }
   double actual_risk = 0.0;
   if(!BufferedPlannedRisk("US100",
                           direction,
                           volume,
                           price,
                           broker_stop,
                           actual_risk) ||
      actual_risk > passive_pending_planned_risk_usd +
                    MathMax(0.01,
                            passive_pending_planned_risk_usd * 0.01))
     {
      detail = StringFormat("pending risk mismatch actual=%.4f admitted=%.4f",
                            actual_risk,
                            passive_pending_planned_risk_usd);
      return(false);
     }
   return(true);
  }


bool AuditPositionOwnership()
  {
   foreign_exposure = false;
   int owned_counts[COMPONENT_COUNT];
   ArrayInitialize(owned_counts, 0);
   int passive_order_count = 0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong ticket = PositionGetTicket(index);
      if(ticket == 0)
         continue;
      const string symbol = PositionGetString(POSITION_SYMBOL);
      const ulong magic = (ulong)PositionGetInteger(POSITION_MAGIC);
      bool matched = false;
      for(int component = 0; component < COMPONENT_COUNT; ++component)
        {
          if(magic == COMPONENT_MAGICS[component] &&
             symbol == COMPONENT_SYMBOLS[component])
            {
             ++owned_counts[component];
             matched = true;
             if(tracked_position_identifier[component] == 0)
                pending_reconcile = true;
             else
               {
                string protection_detail = "";
                if(!SelectedPositionProtectionMatches(component,
                                                      protection_detail))
                  {
                   ++protection_mismatches;
                   broker_mismatch = true;
                   EngageSafetyStop("owned position protection mismatch: " +
                                    protection_detail);
                   return(false);
                  }
               }
             break;
           }
        }
      if(!matched)
        {
         if(IsOwnedMagic(magic))
           {
            broker_mismatch = true;
            EngageSafetyStop("owned Magic Number on mismatched symbol");
            return(false);
           }
         foreign_exposure = true;
        }
     }
   for(int index = OrdersTotal() - 1; index >= 0; --index)
     {
      const ulong ticket = OrderGetTicket(index);
      if(ticket == 0)
         continue;
      const string symbol = OrderGetString(ORDER_SYMBOL);
      const ulong magic = (ulong)OrderGetInteger(ORDER_MAGIC);
      if(magic == MAGIC_US100_PASSIVE_LIMIT && symbol == "US100")
        {
         const ENUM_ORDER_TYPE type =
            (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
          if(type != ORDER_TYPE_BUY_LIMIT && type != ORDER_TYPE_SELL_LIMIT)
           {
            broker_mismatch = true;
            EngageSafetyStop("unexpected passive pending-order type");
             return(false);
            }
          string protection_detail = "";
          if(!SelectedPassiveOrderProtectionMatches(protection_detail))
            {
             ++protection_mismatches;
             broker_mismatch = true;
             EngageSafetyStop("pending-order protection mismatch: " +
                              protection_detail);
             return(false);
            }
          ++passive_order_count;
        }
      else if(IsOwnedMagic(magic))
        {
         broker_mismatch = true;
         EngageSafetyStop("owned pending order on mismatched component");
         return(false);
        }
      else
         foreign_exposure = true;
     }
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(owned_counts[component] > 1)
        {
         broker_mismatch = true;
         EngageSafetyStop("duplicate owned positions");
         return(false);
        }
     }
   if(passive_order_count > 1)
     {
      broker_mismatch = true;
      EngageSafetyStop("duplicate owned passive pending orders");
      return(false);
     }
   if(passive_order_count == 1 && owned_counts[US100_PASSIVE_LIMIT] == 1)
     {
      broker_mismatch = true;
      EngageSafetyStop("passive position and pending order coexist");
      return(false);
     }
   if(foreign_exposure && !foreign_exposure_logged)
     {
      PrintFormat("%s foreign account exposure present; new entries blocked",
                  EXECUTION_VERSION);
      foreign_exposure_logged = true;
     }
   else if(!foreign_exposure && foreign_exposure_logged)
     {
      PrintFormat("%s foreign account exposure cleared", EXECUTION_VERSION);
      foreign_exposure_logged = false;
     }
   return(true);
  }


int CountOwnedPositions(const int component,
                        ulong &ticket,
                        datetime &opened_at)
  {
   int count = 0;
   ticket = 0;
   opened_at = 0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong position_ticket = PositionGetTicket(index);
      if(position_ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != COMPONENT_SYMBOLS[component] ||
         (ulong)PositionGetInteger(POSITION_MAGIC) !=
         COMPONENT_MAGICS[component])
         continue;
      ++count;
      ticket = position_ticket;
      opened_at = (datetime)PositionGetInteger(POSITION_TIME);
     }
   return(count);
  }


int CountOwnedPassiveOrders(ulong &ticket)
  {
   int count = 0;
   ticket = 0;
   for(int index = OrdersTotal() - 1; index >= 0; --index)
     {
      const ulong order_ticket = OrderGetTicket(index);
      if(order_ticket == 0)
         continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC) !=
         MAGIC_US100_PASSIVE_LIMIT)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != "US100")
        {
         broker_mismatch = true;
         EngageSafetyStop("passive Magic Number on mismatched order symbol");
         continue;
        }
      const ENUM_ORDER_TYPE type =
         (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type != ORDER_TYPE_BUY_LIMIT && type != ORDER_TYPE_SELL_LIMIT)
        {
         broker_mismatch = true;
         EngageSafetyStop("unexpected passive pending-order type");
         continue;
        }
      ++count;
      ticket = order_ticket;
     }
   if(count > 1)
     {
      broker_mismatch = true;
      EngageSafetyStop("duplicate owned passive pending orders");
     }
   return(count);
  }


void ClearEntryTracking(const int component)
  {
   tracked_position_identifier[component] = 0;
   entry_time_server[component] = 0;
   entry_direction[component] = 0;
   entry_volume[component] = 0.0;
   entry_feature[component] = 0.0;
   entry_stop_loss[component] = 0.0;
   entry_planned_risk_usd[component] = 0.0;
   entry_spread_price[component] = 0.0;
   entry_transaction_cost[component] = 0.0;
   entry_adverse_slippage[component] = 0.0;
   entry_cost_known[component] = false;
   lifecycle_stop_loss_seen[component] = false;
  }


void ClearPassivePendingTracking()
  {
   tracked_passive_pending_order = 0;
   passive_cancel_pending = false;
   passive_pending_expiration = 0;
   passive_pending_direction = 0;
   passive_pending_feature = 0.0;
   passive_pending_limit_price = 0.0;
   passive_pending_stop_loss = 0.0;
   passive_pending_planned_risk_usd = 0.0;
  }


void ClearDecisionJournalState()
  {
   decision_journal_stage = JOURNAL_NONE;
   decision_journal_component = -1;
   decision_journal_bar = 0;
   decision_journal_direction = 0;
   decision_journal_feature = 0.0;
   decision_journal_deadline = 0;
   decision_journal_attempted_server = 0;
   decision_journal_adopted_ticket = 0;
  }


void BeginEntryCheck(const int component,
                     const datetime bar,
                     const string result)
  {
   entry_check_bar[component] = bar;
   entry_check_signal_known[component] = 0;
   entry_check_signal_passed[component] = -1;
   entry_check_signal_value[component] = 0.0;
   entry_check_direction[component] = 0;
   entry_check_order_price[component] = 0.0;
   entry_check_volume[component] = 0.0;
   entry_check_stop_loss[component] = 0.0;
   entry_check_planned_risk_usd[component] = 0.0;
   entry_check_result[component] = result;
  }


void SetEntrySignalCheck(const int component,
                         const double value,
                         const bool passed,
                         const int direction,
                         const string result)
  {
   entry_check_signal_known[component] = 1;
   entry_check_signal_passed[component] = (passed ? 1 : 0);
   entry_check_signal_value[component] = value;
   entry_check_direction[component] = direction;
   entry_check_result[component] = result;
  }


void ResetRuntimeState()
  {
   ArrayInitialize(last_decision_bar, 0);
   ArrayInitialize(last_close_attempt_server, 0);
   ArrayInitialize(last_processed_exit_deal, 0);
   ArrayInitialize(last_processed_exit_time_msc, 0);
   ArrayInitialize(lifecycle_stop_loss_seen, false);
   ArrayInitialize(closed_trades, 0);
   ArrayInitialize(component_stressed_net, 0.0);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ClearEntryTracking(component);
      BeginEntryCheck(component, 0, "NOT_EVALUATED_SINCE_START");
     }
   state_sequence = 0;
   event_records = 0;
   event_segment_records = 0;
   event_segment = 0;
   started_utc = TimeGMT();
   last_snapshot_utc = 0;
   last_reconcile_server = 0;
   sizing_server_day = 0;
   day_volume_multiplier = 1;
   safety_stopped = false;
   stressed_balance = InpReferenceCapitalUSD;
   stressed_peak = InpReferenceCapitalUSD;
   stressed_maximum_closed_drawdown = 0.0;
   project_realized_net = InpPriorProjectRealizedNetUSD;
   account_peak_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   account_maximum_drawdown = 0.0;
   persistence_failed = false;
   persistence_error_logged = false;
   broker_mismatch = false;
    foreign_exposure = false;
    pending_reconcile = false;
    bound_account_login = 0;
    ClearPassivePendingTracking();
   ClearDecisionJournalState();
   passive_next_entry_current_bar = 0;
   passive_last_feature_attempt_bar = 0;
   passive_last_feature_attempt_server = 0;
   passive_pending_placements = 0;
   passive_cancel_connection_deferrals = 0;
   passive_pending_expirations = 0;
   passive_completed_entries = 0;
   passive_placement_failures = 0;
   passive_stale_price_rejections = 0;
   passive_unexpected_order_outcomes = 0;
   passive_margin_calculation_failures = 0;
   passive_margin_skips = 0;
   passive_price_constraint_skips = 0;
   protection_calculation_failures = 0;
   risk_admission_skips = 0;
   protection_mismatches = 0;
   stop_loss_exits = 0;
   maximum_aggregate_planned_risk_usd = 0.0;
   journal_signal_decisions = 0;
   journal_order_attempts = 0;
   journal_broker_adoptions = 0;
   journal_restart_resolutions = 0;
   ClearArcLifecycleState();
   ClearRC4ShadowState();
   arc_checkpoints = 0;
   arc_adverse_triggers = 0;
   arc_compressions_placed = 0;
   arc_compression_refusals = 0;
   arc_data_unavailable = 0;
   arc_modify_retry_intents = 0;
   arc_modify_retry_attempts = 0;
   arc_modify_retry_successes = 0;
   arc_modify_retry_adoptions = 0;
   arc_modify_retry_holds = 0;
   rc4_shadow_activations = 0;
   rc4_shadow_stop_releases = 0;
   rc4_shadow_deadline_releases = 0;
   rc4_shadow_entry_blocks = 0;
   rc4_shadow_catchup_scans = 0;
   rc4_shadow_catchup_ticks = 0;
   rc4_shadow_catchup_stop_releases = 0;
   rc4_shadow_catchup_failures = 0;
   rc4_shadow_catchup_required = false;
   rc4_shadow_catchup_failure_logged = false;
   rc4_shadow_cursor_checkpoint_observation_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
   rc4_shadow_cursor_checkpoint_eligible = 0;
   rc4_shadow_cursor_checkpoint_persisted = 0;
   rc4_shadow_cursor_checkpoint_save_failures = 0;
   rc4_shadow_cursor_checkpoint_readback_failures = 0;
   rc4_shadow_cursor_checkpoint_event_failures = 0;
   rc4_shadow_cursor_checkpoint_duplicate_bucket_failures = 0;
   rc4_shadow_cursor_checkpoint_regressions = 0;
   rc4_shadow_cursor_checkpoint_pending = false;
   rc4_shadow_activation_seal_eligible = 0;
   rc4_shadow_activation_seal_sealed = 0;
   rc4_shadow_activation_seal_pending_count = 0;
   rc4_shadow_activation_seal_save_attempts = 0;
   rc4_shadow_activation_seal_save_failures = 0;
   rc4_shadow_activation_seal_readbacks = 0;
   rc4_shadow_activation_seal_readback_failures = 0;
   rc4_shadow_activation_seal_failures = 0;
   rc4_shadow_activation_seal_ambiguities = 0;
   rc4_shadow_activation_last_sealed_msc = 0;
   rc4_shadow_activation_last_sealed_ordinal = 0;
   rc4_shadow_activation_pre_boundary_consumed = 0;
   tester_dispatched_ticks = 0;
   tester_transaction_dispatches = 0;
   tester_clock_dispatches = 0;
   tester_retry_dispatches = 0;
   tester_last_m15_slot = -1;
   tester_data_retry_active = false;
  }


void MarkPersistenceFailure(const string detail)
  {
   persistence_failed = true;
   if(persistence_error_logged)
      return;
   persistence_error_logged = true;
   PrintFormat("%s persistence failure; new entries blocked: %s error=%d",
               EXECUTION_VERSION, detail, GetLastError());
  }


void WriteComponentState(const int handle, const int component)
  {
   FileWrite(handle,
             COMPONENT_IDS[component],
             (long)last_decision_bar[component],
             (long)last_processed_exit_deal[component],
             last_processed_exit_time_msc[component],
             (lifecycle_stop_loss_seen[component] ? 1 : 0),
             (long)tracked_position_identifier[component],
             (long)entry_time_server[component],
             entry_direction[component],
              entry_volume[component],
              entry_feature[component],
              entry_stop_loss[component],
              entry_planned_risk_usd[component],
              entry_spread_price[component],
             entry_transaction_cost[component],
             entry_adverse_slippage[component],
             (entry_cost_known[component] ? 1 : 0),
             closed_trades[component],
             component_stressed_net[component]);
  }


void ReadComponentState(const int handle,
                        const int component,
                        string &component_id)
  {
   component_id = FileReadString(handle);
   last_decision_bar[component] =
      (datetime)((long)FileReadNumber(handle));
   last_processed_exit_deal[component] =
      (ulong)((long)FileReadNumber(handle));
   last_processed_exit_time_msc[component] =
      (long)FileReadNumber(handle);
   lifecycle_stop_loss_seen[component] =
      ((int)FileReadNumber(handle) == 1);
   tracked_position_identifier[component] =
      (ulong)((long)FileReadNumber(handle));
   entry_time_server[component] =
      (datetime)((long)FileReadNumber(handle));
   entry_direction[component] = (int)FileReadNumber(handle);
   entry_volume[component] = FileReadNumber(handle);
   entry_feature[component] = FileReadNumber(handle);
   entry_stop_loss[component] = FileReadNumber(handle);
   entry_planned_risk_usd[component] = FileReadNumber(handle);
   entry_spread_price[component] = FileReadNumber(handle);
   entry_transaction_cost[component] = FileReadNumber(handle);
   entry_adverse_slippage[component] = FileReadNumber(handle);
   entry_cost_known[component] = ((int)FileReadNumber(handle) == 1);
   closed_trades[component] = (long)FileReadNumber(handle);
   component_stressed_net[component] = FileReadNumber(handle);
  }


bool ValidateLoadedState()
  {
   if(state_sequence < 0 || event_records < 0 ||
      event_segment_records < 0 ||
      event_segment_records > InpEventCapacity ||
      (event_segment != 0 && event_segment != 1) ||
      started_utc <= 0 || day_volume_multiplier < 1 ||
       !MathIsValidNumber(stressed_balance) ||
       !MathIsValidNumber(stressed_peak) ||
       !MathIsValidNumber(stressed_maximum_closed_drawdown) ||
       !MathIsValidNumber(project_realized_net) ||
       MathAbs(project_realized_net) > 1.0e9 ||
      !MathIsValidNumber(account_peak_equity) ||
      !MathIsValidNumber(account_maximum_drawdown) ||
      stressed_peak <= 0.0 || stressed_maximum_closed_drawdown < 0.0 ||
      account_peak_equity < 0.0 || account_maximum_drawdown < 0.0 ||
       passive_pending_expiration < 0 ||
       passive_next_entry_current_bar < 0 ||
       !MathIsValidNumber(passive_pending_feature) ||
       !MathIsValidNumber(passive_pending_limit_price) ||
       !MathIsValidNumber(passive_pending_stop_loss) ||
       !MathIsValidNumber(passive_pending_planned_risk_usd) ||
       passive_pending_stop_loss < 0.0 ||
       passive_pending_planned_risk_usd < 0.0 ||
       passive_pending_placements < 0 ||
       passive_cancel_connection_deferrals < 0 ||
       passive_pending_expirations < 0 ||
      passive_completed_entries < 0 || passive_placement_failures < 0 ||
      passive_stale_price_rejections < 0 ||
      passive_unexpected_order_outcomes < 0 ||
      passive_margin_calculation_failures < 0 || passive_margin_skips < 0 ||
       passive_price_constraint_skips < 0 ||
       protection_calculation_failures < 0 || risk_admission_skips < 0 ||
       protection_mismatches < 0 || stop_loss_exits < 0 ||
       !MathIsValidNumber(maximum_aggregate_planned_risk_usd) ||
       maximum_aggregate_planned_risk_usd < 0.0 ||
       !MathIsValidNumber(decision_journal_feature) ||
       decision_journal_stage < JOURNAL_NONE ||
       decision_journal_stage > JOURNAL_BROKER_STATE_ADOPTED ||
       journal_signal_decisions < 0 || journal_order_attempts < 0 ||
       journal_broker_adoptions < 0 || journal_restart_resolutions < 0 ||
       arc_last_attempt_bar < 0 ||
       !MathIsValidNumber(arc_original_stop_loss) ||
       arc_original_stop_loss < 0.0 ||
       !MathIsValidNumber(arc_pending_stop_loss) ||
       arc_pending_stop_loss < 0.0 ||
       arc_modify_retry_after_msc < 0 ||
       arc_modify_retry_intents < 0 || arc_modify_retry_attempts < 0 ||
       arc_modify_retry_successes < 0 ||
       arc_modify_retry_adoptions < 0 || arc_modify_retry_holds < 0 ||
       arc_modify_retry_attempts > arc_modify_retry_intents ||
       arc_modify_retry_successes > arc_modify_retry_attempts ||
       arc_checkpoints < 0 || arc_adverse_triggers < 0 ||
       arc_compressions_placed < 0 || arc_compression_refusals < 0 ||
       arc_data_unavailable < 0 ||
       rc4_shadow_entry_time < 0 ||
       !MathIsValidNumber(rc4_shadow_original_stop_loss) ||
       rc4_shadow_original_stop_loss < 0.0 ||
       rc4_shadow_last_observed_msc < 0 ||
       rc4_shadow_cursor_ordinal < 0 ||
       rc4_shadow_activations < 0 || rc4_shadow_stop_releases < 0 ||
       rc4_shadow_deadline_releases < 0 || rc4_shadow_entry_blocks < 0 ||
       rc4_shadow_catchup_scans < 0 || rc4_shadow_catchup_ticks < 0 ||
       rc4_shadow_catchup_stop_releases < 0 ||
       rc4_shadow_catchup_failures < 0 ||
       rc4_shadow_cursor_checkpoint_observation_bucket < 0 ||
       rc4_shadow_cursor_checkpoint_last_completed_bucket < 0 ||
       rc4_shadow_cursor_checkpoint_last_persisted_msc < 0 ||
       rc4_shadow_cursor_checkpoint_last_persisted_ordinal < 0 ||
       rc4_shadow_cursor_checkpoint_eligible < 0 ||
       rc4_shadow_cursor_checkpoint_persisted < 0 ||
       rc4_shadow_cursor_checkpoint_persisted >
          rc4_shadow_cursor_checkpoint_eligible ||
       rc4_shadow_cursor_checkpoint_save_failures < 0 ||
       rc4_shadow_cursor_checkpoint_readback_failures < 0 ||
       rc4_shadow_cursor_checkpoint_event_failures < 0 ||
       rc4_shadow_cursor_checkpoint_duplicate_bucket_failures < 0 ||
       rc4_shadow_cursor_checkpoint_regressions < 0 ||
       rc4_shadow_activation_deal_time_msc < 0 ||
       !MathIsValidNumber(rc4_shadow_activation_deal_price) ||
       rc4_shadow_activation_deal_price < 0.0 ||
       !MathIsValidNumber(rc4_shadow_activation_protected_stop) ||
       rc4_shadow_activation_protected_stop < 0.0 ||
       rc4_shadow_activation_sampled_time < 0 ||
       rc4_shadow_activation_sampled_time_msc < 0 ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_bid) ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_ask) ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_last) ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_volume_real) ||
       rc4_shadow_activation_sampled_bid < 0.0 ||
       rc4_shadow_activation_sampled_ask < 0.0 ||
       rc4_shadow_activation_sampled_last < 0.0 ||
       rc4_shadow_activation_sampled_volume_real < 0.0 ||
       rc4_shadow_activation_boundary_msc < 0 ||
       rc4_shadow_activation_boundary_ordinal < 0 ||
       rc4_shadow_activation_seal_eligible < 0 ||
       rc4_shadow_activation_seal_sealed < 0 ||
       rc4_shadow_activation_seal_sealed >
          rc4_shadow_activation_seal_eligible ||
       rc4_shadow_activation_seal_pending_count < 0 ||
       rc4_shadow_activation_seal_pending_count >
          rc4_shadow_activation_seal_eligible ||
       rc4_shadow_activation_seal_save_attempts < 0 ||
       rc4_shadow_activation_seal_save_failures < 0 ||
       rc4_shadow_activation_seal_save_failures >
          rc4_shadow_activation_seal_save_attempts ||
       rc4_shadow_activation_seal_readbacks < 0 ||
       rc4_shadow_activation_seal_readbacks >
          rc4_shadow_activation_seal_save_attempts ||
       rc4_shadow_activation_seal_readback_failures < 0 ||
       rc4_shadow_activation_seal_readback_failures >
          rc4_shadow_activation_seal_readbacks ||
       rc4_shadow_activation_seal_failures < 0 ||
       rc4_shadow_activation_seal_ambiguities < 0 ||
       rc4_shadow_activation_last_sealed_msc < 0 ||
       rc4_shadow_activation_last_sealed_ordinal < 0 ||
       ((rc4_shadow_activation_last_sealed_msc == 0) !=
        (rc4_shadow_activation_last_sealed_ordinal == 0)) ||
       rc4_shadow_activation_pre_boundary_consumed != 0 ||
       (tester_mode && bound_account_login != 0) ||
       (!tester_mode && bound_account_login <= 0))
      return(false);
   if(arc_lifecycle_identifier == 0)
     {
      if(arc_last_attempt_bar != 0 || arc_checkpoint_evaluated ||
         arc_lifecycle_compressed || arc_original_stop_loss != 0.0 ||
         arc_modify_pending || arc_pending_stop_loss != 0.0 ||
         arc_modify_retry_pending || arc_modify_retry_consumed ||
         arc_modify_retry_after_msc != 0 ||
         arc_modify_retry_initial_retcode != 0)
         return(false);
     }
   else
     {
      if(tracked_position_identifier[RC4_BOTH] !=
         arc_lifecycle_identifier || arc_original_stop_loss <= 0.0 ||
         (arc_lifecycle_compressed && !arc_checkpoint_evaluated))
         return(false);
      if(arc_modify_pending)
        {
         if(!arc_checkpoint_evaluated || arc_lifecycle_compressed ||
            arc_pending_stop_loss <= 0.0)
            return(false);
        }
      if(arc_modify_retry_pending)
        {
         if(arc_modify_pending || arc_modify_retry_consumed ||
            !arc_checkpoint_evaluated || arc_lifecycle_compressed ||
            arc_pending_stop_loss <= 0.0 ||
            arc_modify_retry_after_msc <= 0 ||
            !IsArcTransientModifyRetcode(arc_modify_retry_initial_retcode))
            return(false);
        }
      else if(!arc_modify_pending && arc_pending_stop_loss != 0.0)
         return(false);
      if(!arc_modify_retry_pending &&
         (arc_modify_retry_after_msc != 0 ||
          arc_modify_retry_initial_retcode != 0))
         return(false);
      if(arc_modify_retry_consumed && arc_modify_retry_pending)
         return(false);
     }
   if(rc4_shadow_occupied)
     {
      if(rc4_shadow_source_identifier == 0 ||
         rc4_shadow_entry_time <= 0 ||
         MathAbs(rc4_shadow_direction) != 1 ||
         rc4_shadow_original_stop_loss <= 0.0 ||
         rc4_shadow_last_observed_msc <= 0 ||
         rc4_shadow_cursor_ordinal < 0 ||
         rc4_shadow_activation_deal_ticket == 0 ||
         rc4_shadow_activation_deal_time_msc <= 0 ||
         rc4_shadow_activation_deal_price <= 0.0 ||
         rc4_shadow_activation_deal_reason != (int)DEAL_REASON_SL ||
         rc4_shadow_activation_protected_stop <= 0.0 ||
         (rc4_shadow_activation_sealed ==
          rc4_shadow_activation_seal_pending) ||
         (rc4_shadow_activation_seal_pending &&
          (rc4_shadow_activation_boundary_msc != 0 ||
           rc4_shadow_activation_boundary_ordinal != 0 ||
           rc4_shadow_last_observed_msc !=
              rc4_shadow_activation_deal_time_msc ||
           rc4_shadow_cursor_ordinal != 0)) ||
         (rc4_shadow_activation_sealed &&
          (rc4_shadow_activation_boundary_msc !=
              rc4_shadow_activation_deal_time_msc ||
           rc4_shadow_activation_boundary_ordinal <= 0 ||
           rc4_shadow_last_observed_msc <
              rc4_shadow_activation_boundary_msc ||
           (rc4_shadow_last_observed_msc ==
               rc4_shadow_activation_boundary_msc &&
            rc4_shadow_cursor_ordinal <
               rc4_shadow_activation_boundary_ordinal))) ||
         (rc4_shadow_activation_sampled_tick_known &&
          (rc4_shadow_activation_sampled_time <= 0 ||
           rc4_shadow_activation_sampled_time_msc <= 0 ||
           rc4_shadow_activation_sampled_bid <= 0.0 ||
           rc4_shadow_activation_sampled_ask <
              rc4_shadow_activation_sampled_bid)) ||
         rc4_shadow_cursor_checkpoint_observation_bucket <= 0 ||
         (rc4_shadow_cursor_checkpoint_last_completed_bucket > 0 &&
          rc4_shadow_cursor_checkpoint_last_completed_bucket >=
             rc4_shadow_cursor_checkpoint_observation_bucket) ||
         ((rc4_shadow_cursor_checkpoint_last_persisted_msc == 0) !=
          (rc4_shadow_cursor_checkpoint_last_persisted_ordinal == 0)) ||
         rc4_shadow_cursor_checkpoint_last_persisted_msc >
            rc4_shadow_last_observed_msc ||
         (rc4_shadow_cursor_checkpoint_last_persisted_msc ==
             rc4_shadow_last_observed_msc &&
          rc4_shadow_cursor_checkpoint_last_persisted_ordinal >
             rc4_shadow_cursor_ordinal) ||
         tracked_position_identifier[RC4_BOTH] != 0 ||
         arc_lifecycle_identifier != 0)
         return(false);
     }
   else if(rc4_shadow_source_identifier != 0 ||
           rc4_shadow_entry_time != 0 || rc4_shadow_direction != 0 ||
           rc4_shadow_original_stop_loss != 0.0 ||
           rc4_shadow_last_observed_msc != 0 ||
           rc4_shadow_cursor_ordinal != 0 ||
           rc4_shadow_cursor_checkpoint_observation_bucket != 0 ||
           rc4_shadow_cursor_checkpoint_last_completed_bucket != 0 ||
           rc4_shadow_cursor_checkpoint_last_persisted_msc != 0 ||
           rc4_shadow_cursor_checkpoint_last_persisted_ordinal != 0 ||
           rc4_shadow_cursor_checkpoint_pending ||
           rc4_shadow_activation_sealed ||
           rc4_shadow_activation_seal_pending ||
           rc4_shadow_activation_seal_failure_logged ||
           rc4_shadow_activation_deal_ticket != 0 ||
           rc4_shadow_activation_deal_time_msc != 0 ||
           rc4_shadow_activation_deal_price != 0.0 ||
           rc4_shadow_activation_deal_reason != 0 ||
           rc4_shadow_activation_protected_stop != 0.0 ||
           rc4_shadow_activation_sampled_tick_known ||
           rc4_shadow_activation_sampled_time != 0 ||
           rc4_shadow_activation_sampled_time_msc != 0 ||
           rc4_shadow_activation_sampled_bid != 0.0 ||
           rc4_shadow_activation_sampled_ask != 0.0 ||
           rc4_shadow_activation_sampled_last != 0.0 ||
           rc4_shadow_activation_sampled_volume != 0 ||
           rc4_shadow_activation_sampled_volume_real != 0.0 ||
           rc4_shadow_activation_sampled_flags != 0 ||
           rc4_shadow_activation_boundary_msc != 0 ||
           rc4_shadow_activation_boundary_ordinal != 0)
      return(false);
   if(decision_journal_stage == JOURNAL_NONE)
     {
      if(decision_journal_component != -1 || decision_journal_bar != 0 ||
         decision_journal_direction != 0 ||
         decision_journal_feature != 0.0 ||
         decision_journal_deadline != 0 ||
         decision_journal_attempted_server != 0 ||
         decision_journal_adopted_ticket != 0)
         return(false);
     }
   else
     {
      if(decision_journal_component < 0 ||
         decision_journal_component >= COMPONENT_COUNT ||
         decision_journal_bar <= 0 ||
         MathAbs(decision_journal_direction) != 1 ||
         decision_journal_deadline < decision_journal_bar ||
         last_decision_bar[decision_journal_component] <
         decision_journal_bar)
         return(false);
      if(decision_journal_stage == JOURNAL_SIGNAL_DECIDED &&
         (decision_journal_attempted_server != 0 ||
          decision_journal_adopted_ticket != 0))
         return(false);
      if(decision_journal_stage == JOURNAL_ORDER_ATTEMPTED &&
         (decision_journal_attempted_server <= 0 ||
          decision_journal_adopted_ticket != 0))
         return(false);
      if(decision_journal_stage == JOURNAL_BROKER_STATE_ADOPTED &&
         (decision_journal_attempted_server <= 0 ||
          decision_journal_adopted_ticket == 0))
         return(false);
     }
   if(tracked_passive_pending_order > 0)
     {
      if(passive_pending_expiration <= 0 ||
          MathAbs(passive_pending_direction) != 1 ||
          passive_pending_limit_price <= 0.0 ||
          passive_pending_stop_loss <= 0.0 ||
          passive_pending_planned_risk_usd <= 0.0 ||
          (passive_cancel_pending &&
           passive_cancel_connection_deferrals <= 0) ||
          tracked_position_identifier[US100_PASSIVE_LIMIT] > 0)
         return(false);
     }
   else if(passive_cancel_pending ||
            passive_pending_expiration != 0 ||
            passive_pending_direction != 0 ||
            passive_pending_feature != 0.0 ||
            passive_pending_limit_price != 0.0 ||
            passive_pending_stop_loss != 0.0 ||
            passive_pending_planned_risk_usd != 0.0)
      return(false);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(last_decision_bar[component] < 0 ||
         last_processed_exit_time_msc[component] < 0 ||
         entry_time_server[component] < 0 ||
         closed_trades[component] < 0 ||
          !MathIsValidNumber(entry_volume[component]) ||
          !MathIsValidNumber(entry_feature[component]) ||
          !MathIsValidNumber(entry_stop_loss[component]) ||
          !MathIsValidNumber(entry_planned_risk_usd[component]) ||
          !MathIsValidNumber(entry_spread_price[component]) ||
         !MathIsValidNumber(entry_transaction_cost[component]) ||
         !MathIsValidNumber(entry_adverse_slippage[component]) ||
         !MathIsValidNumber(component_stressed_net[component]) ||
          entry_volume[component] < 0.0 ||
          entry_stop_loss[component] < 0.0 ||
          entry_planned_risk_usd[component] < 0.0 ||
          entry_spread_price[component] < 0.0 ||
         entry_adverse_slippage[component] < 0.0)
         return(false);
      if(tracked_position_identifier[component] > 0 &&
         (entry_time_server[component] <= 0 ||
           MathAbs(entry_direction[component]) != 1 ||
           entry_volume[component] <= 0.0 ||
           entry_stop_loss[component] <= 0.0 ||
           entry_planned_risk_usd[component] <= 0.0))
          return(false);
      if(tracked_position_identifier[component] > 0)
        {
         long loaded_steps = 0;
         if(!VolumeToSteps(COMPONENT_SYMBOLS[component],
                           entry_volume[component],
                           loaded_steps))
            return(false);
        }
       if(tracked_position_identifier[component] == 0 &&
          (entry_stop_loss[component] != 0.0 ||
           entry_planned_risk_usd[component] != 0.0 ||
           lifecycle_stop_loss_seen[component]))
          return(false);
     }
   return(true);
  }


int OpenFileWithRetry(const string path,
                      const int flags,
                      const short delimiter)
  {
   for(int attempt = 0; attempt < FILE_OPEN_ATTEMPTS; ++attempt)
     {
      ResetLastError();
      const int handle = FileOpen(path, flags, delimiter);
      if(handle != INVALID_HANDLE)
         return(handle);
      if(attempt + 1 < FILE_OPEN_ATTEMPTS)
         Sleep(FILE_RETRY_DELAY_MS);
     }
   return(INVALID_HANDLE);
  }


bool ReadState(const string path, long &loaded_sequence)
  {
   const int handle = OpenFileWithRetry(path,
                                        FILE_READ | FILE_CSV | FILE_ANSI,
                                        ',');
   if(handle == INVALID_HANDLE)
      return(false);
   const string marker = FileReadString(handle);
   const string execution_version = FileReadString(handle);
    const string economic_version = FileReadString(handle);
    const string portfolio_id = FileReadString(handle);
    const string fingerprint = FileReadString(handle);
    const string execution_fingerprint = FileReadString(handle);
    bound_account_login = (long)FileReadNumber(handle);
   state_sequence = (long)FileReadNumber(handle);
   event_records = (long)FileReadNumber(handle);
   event_segment_records = (long)FileReadNumber(handle);
   event_segment = (int)FileReadNumber(handle);
   stressed_balance = FileReadNumber(handle);
   stressed_peak = FileReadNumber(handle);
   stressed_maximum_closed_drawdown = FileReadNumber(handle);
   const double prior_project_realized_net = FileReadNumber(handle);
   project_realized_net = FileReadNumber(handle);
   sizing_server_day = (datetime)((long)FileReadNumber(handle));
   day_volume_multiplier = (int)FileReadNumber(handle);
   safety_stopped = ((int)FileReadNumber(handle) == 1);
   started_utc = (datetime)((long)FileReadNumber(handle));
   last_snapshot_utc = (datetime)((long)FileReadNumber(handle));
   account_peak_equity = FileReadNumber(handle);
   account_maximum_drawdown = FileReadNumber(handle);
   tracked_passive_pending_order =
      (ulong)((long)FileReadNumber(handle));
   passive_cancel_pending = ((int)FileReadNumber(handle) == 1);
   passive_pending_expiration =
      (datetime)((long)FileReadNumber(handle));
   passive_pending_direction = (int)FileReadNumber(handle);
   passive_pending_feature = FileReadNumber(handle);
   passive_pending_limit_price = FileReadNumber(handle);
   passive_pending_stop_loss = FileReadNumber(handle);
   passive_pending_planned_risk_usd = FileReadNumber(handle);
   passive_next_entry_current_bar =
      (datetime)((long)FileReadNumber(handle));
   passive_pending_placements = (long)FileReadNumber(handle);
   passive_cancel_connection_deferrals = (long)FileReadNumber(handle);
   passive_pending_expirations = (long)FileReadNumber(handle);
   passive_completed_entries = (long)FileReadNumber(handle);
   passive_placement_failures = (long)FileReadNumber(handle);
   passive_stale_price_rejections = (long)FileReadNumber(handle);
   passive_unexpected_order_outcomes = (long)FileReadNumber(handle);
   passive_margin_calculation_failures = (long)FileReadNumber(handle);
   passive_margin_skips = (long)FileReadNumber(handle);
   passive_price_constraint_skips = (long)FileReadNumber(handle);
   protection_calculation_failures = (long)FileReadNumber(handle);
   risk_admission_skips = (long)FileReadNumber(handle);
   protection_mismatches = (long)FileReadNumber(handle);
   stop_loss_exits = (long)FileReadNumber(handle);
   maximum_aggregate_planned_risk_usd = FileReadNumber(handle);
   decision_journal_stage = (int)FileReadNumber(handle);
   decision_journal_component = (int)FileReadNumber(handle);
   decision_journal_bar =
      (datetime)((long)FileReadNumber(handle));
   decision_journal_direction = (int)FileReadNumber(handle);
   decision_journal_feature = FileReadNumber(handle);
   decision_journal_deadline =
      (datetime)((long)FileReadNumber(handle));
   decision_journal_attempted_server =
      (datetime)((long)FileReadNumber(handle));
   decision_journal_adopted_ticket =
      (ulong)((long)FileReadNumber(handle));
   journal_signal_decisions = (long)FileReadNumber(handle);
   journal_order_attempts = (long)FileReadNumber(handle);
   journal_broker_adoptions = (long)FileReadNumber(handle);
   journal_restart_resolutions = (long)FileReadNumber(handle);
   arc_lifecycle_identifier =
      (ulong)((long)FileReadNumber(handle));
   arc_last_attempt_bar =
      (datetime)((long)FileReadNumber(handle));
   arc_checkpoint_evaluated = ((int)FileReadNumber(handle) == 1);
   arc_lifecycle_compressed = ((int)FileReadNumber(handle) == 1);
   arc_original_stop_loss = FileReadNumber(handle);
   arc_checkpoints = (long)FileReadNumber(handle);
   arc_adverse_triggers = (long)FileReadNumber(handle);
   arc_compressions_placed = (long)FileReadNumber(handle);
   arc_compression_refusals = (long)FileReadNumber(handle);
   arc_data_unavailable = (long)FileReadNumber(handle);
   rc4_shadow_occupied = ((int)FileReadNumber(handle) == 1);
   rc4_shadow_source_identifier =
      (ulong)((long)FileReadNumber(handle));
   rc4_shadow_entry_time =
      (datetime)((long)FileReadNumber(handle));
   rc4_shadow_direction = (int)FileReadNumber(handle);
   rc4_shadow_original_stop_loss = FileReadNumber(handle);
   rc4_shadow_last_observed_msc = (long)FileReadNumber(handle);
   rc4_shadow_cursor_ordinal = (long)FileReadNumber(handle);
   rc4_shadow_activations = (long)FileReadNumber(handle);
   rc4_shadow_stop_releases = (long)FileReadNumber(handle);
   rc4_shadow_deadline_releases = (long)FileReadNumber(handle);
   rc4_shadow_entry_blocks = (long)FileReadNumber(handle);
   rc4_shadow_catchup_scans = (long)FileReadNumber(handle);
   rc4_shadow_catchup_ticks = (long)FileReadNumber(handle);
   rc4_shadow_catchup_stop_releases = (long)FileReadNumber(handle);
   rc4_shadow_catchup_failures = (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_observation_bucket =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_last_completed_bucket =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_last_persisted_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_eligible = (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_persisted = (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_save_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_readback_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_event_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_duplicate_bucket_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_regressions =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_pending =
      ((int)FileReadNumber(handle) == 1);
   arc_modify_pending = ((int)FileReadNumber(handle) == 1);
   arc_pending_stop_loss = FileReadNumber(handle);
   arc_modify_retry_pending = ((int)FileReadNumber(handle) == 1);
   arc_modify_retry_consumed = ((int)FileReadNumber(handle) == 1);
   arc_modify_retry_after_msc = (long)FileReadNumber(handle);
   arc_modify_retry_initial_retcode = (uint)FileReadNumber(handle);
   arc_modify_retry_intents = (long)FileReadNumber(handle);
   arc_modify_retry_attempts = (long)FileReadNumber(handle);
   arc_modify_retry_successes = (long)FileReadNumber(handle);
   arc_modify_retry_adoptions = (long)FileReadNumber(handle);
   arc_modify_retry_holds = (long)FileReadNumber(handle);
   rc4_shadow_activation_sealed =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_seal_pending =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_seal_failure_logged =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_deal_ticket =
      (ulong)((long)FileReadNumber(handle));
   rc4_shadow_activation_deal_time_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_deal_price = FileReadNumber(handle);
   rc4_shadow_activation_deal_reason =
      (int)FileReadNumber(handle);
   rc4_shadow_activation_protected_stop = FileReadNumber(handle);
   rc4_shadow_activation_sampled_tick_known =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_sampled_time =
      (datetime)((long)FileReadNumber(handle));
   rc4_shadow_activation_sampled_time_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_sampled_bid = FileReadNumber(handle);
   rc4_shadow_activation_sampled_ask = FileReadNumber(handle);
   rc4_shadow_activation_sampled_last = FileReadNumber(handle);
   rc4_shadow_activation_sampled_volume =
      (ulong)((long)FileReadNumber(handle));
   rc4_shadow_activation_sampled_volume_real =
      FileReadNumber(handle);
   rc4_shadow_activation_sampled_flags =
      (uint)FileReadNumber(handle);
   rc4_shadow_activation_boundary_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_boundary_ordinal =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_eligible =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_sealed =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_pending_count =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_save_attempts =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_save_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_readbacks =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_readback_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_ambiguities =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_last_sealed_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_last_sealed_ordinal =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_pre_boundary_consumed =
      (long)FileReadNumber(handle);
   string component_ids[COMPONENT_COUNT];
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      ReadComponentState(handle, component, component_ids[component]);
   const string end_marker = FileReadString(handle);
   FileClose(handle);
   if(marker != STATE_MARKER || end_marker != STATE_MARKER ||
       execution_version != EXECUTION_VERSION ||
       economic_version != ECONOMIC_VERSION || portfolio_id != PORTFOLIO_ID ||
        fingerprint != ECONOMIC_FINGERPRINT ||
        execution_fingerprint != EXECUTION_FINGERPRINT ||
        (!tester_mode &&
         bound_account_login !=
         (long)AccountInfoInteger(ACCOUNT_LOGIN)) ||
        MathAbs(prior_project_realized_net -
               InpPriorProjectRealizedNetUSD) > 1.0e-8)
      return(false);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_ids[component] != COMPONENT_IDS[component])
         return(false);
   if(!ValidateLoadedState())
      return(false);
   loaded_sequence = state_sequence;
   return(true);
  }


bool LoadState()
  {
   long sequence_a = -1;
   long sequence_b = -1;
   const bool valid_a = ReadState(STATE_PATH_A, sequence_a);
   ResetRuntimeState();
   const bool valid_b = ReadState(STATE_PATH_B, sequence_b);
   ResetRuntimeState();
   const string selected =
      (valid_a && (!valid_b || sequence_a >= sequence_b)
       ? STATE_PATH_A : (valid_b ? STATE_PATH_B : ""));
   if(selected == "")
      return(false);
   long selected_sequence = -1;
   if(!ReadState(selected, selected_sequence))
      return(false);
   rc4_shadow_catchup_required = rc4_shadow_occupied;
   rc4_shadow_catchup_failure_logged = false;
   return(true);
  }


bool WriteCurrentSnapshotFile(const string path)
  {
   const int handle = OpenFileWithRetry(path,
                                        FILE_WRITE | FILE_CSV | FILE_ANSI |
                                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                                        ',');
   if(handle == INVALID_HANDLE)
      return(false);
   FileWrite(handle,
             "utc", "server_time", "execution_version", "economic_version",
              "portfolio_id", "state_sequence", "new_entries_input",
              "new_entries_effective", "safety_stopped",
              "persistence_failed", "broker_mismatch", "foreign_exposure",
              "terminal_connected", "account_binding_configured",
              "account_identity_match",
              "stressed_balance", "stressed_max_closed_drawdown",
             "project_realized_net", "project_stage_balance",
             "account_balance", "account_equity", "account_margin",
              "account_max_drawdown", "passive_pending_order",
              "passive_cancel_pending",
             "passive_pending_expiration", "passive_pending_direction",
              "passive_pending_limit", "passive_pending_stop",
              "passive_pending_planned_risk", "passive_placements",
              "passive_cancel_connection_deferrals",
              "passive_expirations", "passive_entries",
              "passive_stale_rejections", "protection_calc_failures",
              "risk_admission_skips", "protection_mismatches",
              "stop_loss_exits", "aggregate_planned_risk",
              "maximum_aggregate_planned_risk",
              "decision_journal_stage", "decision_journal_component",
              "decision_journal_bar", "decision_journal_direction",
              "decision_journal_feature", "decision_journal_deadline",
              "decision_journal_attempted", "decision_journal_ticket",
              "journal_signal_decisions", "journal_order_attempts",
              "journal_broker_adoptions", "journal_restart_resolutions",
               "arc_lifecycle_identifier", "arc_modify_pending",
               "arc_pending_stop", "arc_lifecycle_compressed",
               "arc_original_stop",
              "rc4_shadow_occupied", "rc4_shadow_source_identifier",
              "rc4_shadow_entry_time", "rc4_shadow_direction",
              "rc4_shadow_original_stop");
   const bool entries_effective = NewEntriesOperationallyAllowed();
   FileWrite(handle,
             TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS),
             TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
             EXECUTION_VERSION,
             ECONOMIC_VERSION,
             PORTFOLIO_ID,
             state_sequence,
             (InpAllowNewEntries ? 1 : 0),
             (entries_effective ? 1 : 0),
             (safety_stopped ? 1 : 0),
              (persistence_failed ? 1 : 0),
              (broker_mismatch ? 1 : 0),
              (foreign_exposure ? 1 : 0),
              (TerminalInfoInteger(TERMINAL_CONNECTED) ? 1 : 0),
              (InpExpectedLiveAccountLogin > 0 ? 1 : 0),
              (LiveAccountIdentityCompatible() ? 1 : 0),
              stressed_balance,
             stressed_maximum_closed_drawdown,
             project_realized_net,
             InpReferenceCapitalUSD + project_realized_net,
             AccountInfoDouble(ACCOUNT_BALANCE),
             AccountInfoDouble(ACCOUNT_EQUITY),
             AccountInfoDouble(ACCOUNT_MARGIN),
             account_maximum_drawdown,
              (long)tracked_passive_pending_order,
              (passive_cancel_pending ? 1 : 0),
             (long)passive_pending_expiration,
              passive_pending_direction,
              passive_pending_limit_price,
              passive_pending_stop_loss,
              passive_pending_planned_risk_usd,
              passive_pending_placements,
              passive_cancel_connection_deferrals,
              passive_pending_expirations,
              passive_completed_entries,
              passive_stale_price_rejections,
              protection_calculation_failures,
              risk_admission_skips,
              protection_mismatches,
              stop_loss_exits,
              TrackedAggregatePlannedRisk(),
              maximum_aggregate_planned_risk_usd,
              decision_journal_stage,
              decision_journal_component,
              (long)decision_journal_bar,
              decision_journal_direction,
              decision_journal_feature,
              (long)decision_journal_deadline,
              (long)decision_journal_attempted_server,
              (long)decision_journal_adopted_ticket,
              journal_signal_decisions,
              journal_order_attempts,
              journal_broker_adoptions,
              journal_restart_resolutions,
              (long)arc_lifecycle_identifier,
              (arc_modify_pending ? 1 : 0),
              arc_pending_stop_loss,
              (arc_lifecycle_compressed ? 1 : 0),
               arc_original_stop_loss,
              (rc4_shadow_occupied ? 1 : 0),
              (long)rc4_shadow_source_identifier,
              (long)rc4_shadow_entry_time,
              rc4_shadow_direction,
               rc4_shadow_original_stop_loss);
   FileWrite(handle,
             "rc4_modify_retry", "pending", "consumed", "after_msc",
             "initial_retcode", "intents", "attempts", "successes",
             "adoptions", "holds");
   FileWrite(handle,
             "rc4_modify_retry",
             (arc_modify_retry_pending ? 1 : 0),
             (arc_modify_retry_consumed ? 1 : 0),
             arc_modify_retry_after_msc,
             (long)arc_modify_retry_initial_retcode,
             arc_modify_retry_intents,
             arc_modify_retry_attempts,
             arc_modify_retry_successes,
             arc_modify_retry_adoptions,
             arc_modify_retry_holds);
   FileWrite(handle,
             "component_id", "magic", "last_decision_bar",
              "entry_check_bar", "entry_check_signal_known",
              "entry_check_signal_passed", "entry_check_signal_value",
              "entry_check_direction", "entry_check_order_price",
              "entry_check_volume", "entry_check_stop_loss",
              "entry_check_planned_risk", "entry_check_result",
              "position_identifier", "last_exit_deal",
              "last_exit_time_msc", "stop_loss_seen", "entry_time",
              "entry_direction", "entry_volume", "entry_stop_loss",
              "entry_planned_risk", "entry_cost_known", "closed",
              "stressed_net");
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      FileWrite(handle,
                COMPONENT_IDS[component],
                (long)COMPONENT_MAGICS[component],
                (long)last_decision_bar[component],
                (long)entry_check_bar[component],
                entry_check_signal_known[component],
                entry_check_signal_passed[component],
                entry_check_signal_value[component],
                entry_check_direction[component],
                entry_check_order_price[component],
                entry_check_volume[component],
                entry_check_stop_loss[component],
                entry_check_planned_risk_usd[component],
                entry_check_result[component],
                (long)tracked_position_identifier[component],
                (long)last_processed_exit_deal[component],
                last_processed_exit_time_msc[component],
                (lifecycle_stop_loss_seen[component] ? 1 : 0),
                (long)entry_time_server[component],
                 entry_direction[component],
                 entry_volume[component],
                 entry_stop_loss[component],
                 entry_planned_risk_usd[component],
                 (entry_cost_known[component] ? 1 : 0),
                closed_trades[component],
                component_stressed_net[component]);
   FileWrite(handle,
             "rc4_shadow_recovery", "last_observed_msc", "cursor_ordinal",
             "catchup_required", "catchup_scans", "catchup_ticks",
             "catchup_stop_releases", "catchup_failures",
             "checkpoint_observation_bucket",
             "checkpoint_last_completed_bucket",
             "checkpoint_last_persisted_msc",
             "checkpoint_last_persisted_ordinal",
             "checkpoint_eligible", "checkpoint_persisted",
             "checkpoint_save_failures", "checkpoint_readback_failures",
             "checkpoint_event_failures",
             "checkpoint_duplicate_bucket_failures",
             "checkpoint_cursor_regressions", "checkpoint_pending");
   FileWrite(handle,
             "rc4_shadow_recovery",
             rc4_shadow_last_observed_msc,
             rc4_shadow_cursor_ordinal,
             (rc4_shadow_catchup_required ? 1 : 0),
             rc4_shadow_catchup_scans,
             rc4_shadow_catchup_ticks,
             rc4_shadow_catchup_stop_releases,
             rc4_shadow_catchup_failures,
             rc4_shadow_cursor_checkpoint_observation_bucket,
             rc4_shadow_cursor_checkpoint_last_completed_bucket,
             rc4_shadow_cursor_checkpoint_last_persisted_msc,
             rc4_shadow_cursor_checkpoint_last_persisted_ordinal,
             rc4_shadow_cursor_checkpoint_eligible,
             rc4_shadow_cursor_checkpoint_persisted,
             rc4_shadow_cursor_checkpoint_save_failures,
             rc4_shadow_cursor_checkpoint_readback_failures,
             rc4_shadow_cursor_checkpoint_event_failures,
             rc4_shadow_cursor_checkpoint_duplicate_bucket_failures,
             rc4_shadow_cursor_checkpoint_regressions,
             (rc4_shadow_cursor_checkpoint_pending ? 1 : 0));
   FileWrite(handle,
             "rc4_shadow_activation_seal",
             "eligible", "sealed", "pending", "save_attempts",
             "save_failures", "readbacks", "readback_failures",
             "failures", "ambiguities", "sealed_msc",
             "sealed_ordinal", "pre_boundary_consumed");
   FileWrite(handle,
             "rc4_shadow_activation_seal",
             rc4_shadow_activation_seal_eligible,
             rc4_shadow_activation_seal_sealed,
             rc4_shadow_activation_seal_pending_count,
             rc4_shadow_activation_seal_save_attempts,
             rc4_shadow_activation_seal_save_failures,
             rc4_shadow_activation_seal_readbacks,
             rc4_shadow_activation_seal_readback_failures,
             rc4_shadow_activation_seal_failures,
             rc4_shadow_activation_seal_ambiguities,
             rc4_shadow_activation_last_sealed_msc,
             rc4_shadow_activation_last_sealed_ordinal,
             rc4_shadow_activation_pre_boundary_consumed);
   FileFlush(handle);
   FileClose(handle);
   return(true);
  }


bool WriteCurrentSnapshot()
  {
   const string preferred =
      ((state_sequence % 2) == 0
       ? CURRENT_SNAPSHOT_PATH_A : CURRENT_SNAPSHOT_PATH_B);
   const string fallback =
      ((state_sequence % 2) == 0
       ? CURRENT_SNAPSHOT_PATH_B : CURRENT_SNAPSHOT_PATH_A);
   if(WriteCurrentSnapshotFile(preferred))
      return(true);
   return(WriteCurrentSnapshotFile(fallback));
  }


bool SaveState()
  {
   const long previous_sequence = state_sequence;
   const datetime previous_snapshot = last_snapshot_utc;
   ++state_sequence;
   last_snapshot_utc = TimeGMT();
   const string path =
      ((state_sequence % 2) == 0 ? STATE_PATH_A : STATE_PATH_B);
   const int handle = OpenFileWithRetry(path,
                                        FILE_WRITE | FILE_CSV | FILE_ANSI,
                                        ',');
   if(handle == INVALID_HANDLE)
     {
      state_sequence = previous_sequence;
      last_snapshot_utc = previous_snapshot;
      MarkPersistenceFailure("cannot open state snapshot");
      return(false);
     }
   FileWrite(handle,
             STATE_MARKER,
             EXECUTION_VERSION,
             ECONOMIC_VERSION,
              PORTFOLIO_ID,
              ECONOMIC_FINGERPRINT,
              EXECUTION_FINGERPRINT,
              bound_account_login,
              state_sequence,
             event_records,
             event_segment_records,
             event_segment,
             stressed_balance,
             stressed_peak,
             stressed_maximum_closed_drawdown,
             InpPriorProjectRealizedNetUSD,
             project_realized_net,
             (long)sizing_server_day,
             day_volume_multiplier,
             (safety_stopped ? 1 : 0),
             (long)started_utc,
             (long)last_snapshot_utc,
             account_peak_equity,
             account_maximum_drawdown,
              (long)tracked_passive_pending_order,
              (passive_cancel_pending ? 1 : 0),
             (long)passive_pending_expiration,
              passive_pending_direction,
              passive_pending_feature,
              passive_pending_limit_price,
              passive_pending_stop_loss,
              passive_pending_planned_risk_usd,
              (long)passive_next_entry_current_bar,
              passive_pending_placements,
              passive_cancel_connection_deferrals,
             passive_pending_expirations,
             passive_completed_entries,
             passive_placement_failures,
             passive_stale_price_rejections,
             passive_unexpected_order_outcomes,
              passive_margin_calculation_failures,
              passive_margin_skips,
              passive_price_constraint_skips,
              protection_calculation_failures,
              risk_admission_skips,
              protection_mismatches,
              stop_loss_exits,
              maximum_aggregate_planned_risk_usd,
              decision_journal_stage,
              decision_journal_component,
              (long)decision_journal_bar,
              decision_journal_direction,
              decision_journal_feature,
              (long)decision_journal_deadline,
              (long)decision_journal_attempted_server,
              (long)decision_journal_adopted_ticket,
              journal_signal_decisions,
              journal_order_attempts,
              journal_broker_adoptions,
              journal_restart_resolutions);
   FileWrite(handle,
              (long)arc_lifecycle_identifier,
              (long)arc_last_attempt_bar,
              (arc_checkpoint_evaluated ? 1 : 0),
              (arc_lifecycle_compressed ? 1 : 0),
              arc_original_stop_loss,
              arc_checkpoints,
              arc_adverse_triggers,
              arc_compressions_placed,
              arc_compression_refusals,
              arc_data_unavailable,
              (rc4_shadow_occupied ? 1 : 0),
              (long)rc4_shadow_source_identifier,
              (long)rc4_shadow_entry_time,
              rc4_shadow_direction,
              rc4_shadow_original_stop_loss,
              rc4_shadow_last_observed_msc,
              rc4_shadow_cursor_ordinal,
              rc4_shadow_activations,
              rc4_shadow_stop_releases,
              rc4_shadow_deadline_releases,
              rc4_shadow_entry_blocks,
              rc4_shadow_catchup_scans,
              rc4_shadow_catchup_ticks,
              rc4_shadow_catchup_stop_releases,
              rc4_shadow_catchup_failures,
              rc4_shadow_cursor_checkpoint_observation_bucket,
              rc4_shadow_cursor_checkpoint_last_completed_bucket,
              rc4_shadow_cursor_checkpoint_last_persisted_msc,
              rc4_shadow_cursor_checkpoint_last_persisted_ordinal,
              rc4_shadow_cursor_checkpoint_eligible,
              rc4_shadow_cursor_checkpoint_persisted,
              rc4_shadow_cursor_checkpoint_save_failures,
              rc4_shadow_cursor_checkpoint_readback_failures,
              rc4_shadow_cursor_checkpoint_event_failures,
              rc4_shadow_cursor_checkpoint_duplicate_bucket_failures,
              rc4_shadow_cursor_checkpoint_regressions,
              (rc4_shadow_cursor_checkpoint_pending ? 1 : 0),
              (arc_modify_pending ? 1 : 0),
              arc_pending_stop_loss,
              (arc_modify_retry_pending ? 1 : 0),
              (arc_modify_retry_consumed ? 1 : 0),
              arc_modify_retry_after_msc,
              (long)arc_modify_retry_initial_retcode,
              arc_modify_retry_intents,
              arc_modify_retry_attempts,
              arc_modify_retry_successes,
              arc_modify_retry_adoptions,
              arc_modify_retry_holds);
   FileWrite(handle,
             (rc4_shadow_activation_sealed ? 1 : 0),
             (rc4_shadow_activation_seal_pending ? 1 : 0),
             (rc4_shadow_activation_seal_failure_logged ? 1 : 0),
             (long)rc4_shadow_activation_deal_ticket,
             rc4_shadow_activation_deal_time_msc,
             rc4_shadow_activation_deal_price,
             rc4_shadow_activation_deal_reason,
             rc4_shadow_activation_protected_stop,
             (rc4_shadow_activation_sampled_tick_known ? 1 : 0),
             (long)rc4_shadow_activation_sampled_time,
             rc4_shadow_activation_sampled_time_msc,
             rc4_shadow_activation_sampled_bid,
             rc4_shadow_activation_sampled_ask,
             rc4_shadow_activation_sampled_last,
             (long)rc4_shadow_activation_sampled_volume,
             rc4_shadow_activation_sampled_volume_real,
             (long)rc4_shadow_activation_sampled_flags,
             rc4_shadow_activation_boundary_msc,
             rc4_shadow_activation_boundary_ordinal,
             rc4_shadow_activation_seal_eligible,
             rc4_shadow_activation_seal_sealed,
             rc4_shadow_activation_seal_pending_count,
             rc4_shadow_activation_seal_save_attempts,
             rc4_shadow_activation_seal_save_failures,
             rc4_shadow_activation_seal_readbacks,
             rc4_shadow_activation_seal_readback_failures,
             rc4_shadow_activation_seal_failures,
             rc4_shadow_activation_seal_ambiguities,
             rc4_shadow_activation_last_sealed_msc,
             rc4_shadow_activation_last_sealed_ordinal,
             rc4_shadow_activation_pre_boundary_consumed);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      WriteComponentState(handle, component);
   FileWrite(handle, STATE_MARKER);
   FileFlush(handle);
   FileClose(handle);
   long verified_sequence = -1;
   if(!ReadState(path, verified_sequence) ||
      verified_sequence != state_sequence)
     {
      MarkPersistenceFailure("state verification failed");
      return(false);
     }
   if(!WriteCurrentSnapshot())
     {
      MarkPersistenceFailure("current snapshot failed");
      return(false);
     }
   return(true);
  }


bool RecordEvent(const int component,
                 const string event_name,
                 const double value_a,
                 const double value_b,
                 const string detail)
  {
   const bool rotate = (event_segment_records >= InpEventCapacity);
   const int target_segment = (rotate ? 1 - event_segment : event_segment);
   const long target_records = (rotate ? 0 : event_segment_records);
   const bool replace_segment = (rotate || target_records == 0);
   const string path = (target_segment == 0 ? EVENT_PATH_A : EVENT_PATH_B);
   const int flags =
      (replace_segment
       ? FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ
       : FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ);
   const int handle = OpenFileWithRetry(path, flags, ',');
   if(handle == INVALID_HANDLE)
     {
      MarkPersistenceFailure("cannot open event segment");
      return(false);
     }
   if(!replace_segment)
      FileSeek(handle, 0, SEEK_END);
   if(FileSize(handle) == 0)
      FileWrite(handle,
                "utc", "server_time", "event", "execution_version",
                "portfolio_id", "component_id", "value_a", "value_b",
                 "detail", "stressed_balance", "project_stage_balance",
                 "account_equity",
                "account_margin", "state_sequence");
   const string component_id =
      (component >= 0 && component < COMPONENT_COUNT
       ? COMPONENT_IDS[component] : "PORTFOLIO");
   FileWrite(handle,
             TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS),
             TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
             event_name,
             EXECUTION_VERSION,
             PORTFOLIO_ID,
             component_id,
             value_a,
             value_b,
             detail,
             stressed_balance,
             InpReferenceCapitalUSD + project_realized_net,
             AccountInfoDouble(ACCOUNT_EQUITY),
             AccountInfoDouble(ACCOUNT_MARGIN),
             state_sequence);
   FileFlush(handle);
   FileClose(handle);
   const int verify = OpenFileWithRetry(path,
                                        FILE_READ | FILE_BIN |
                                        FILE_SHARE_READ,
                                        ',');
   if(verify == INVALID_HANDLE || FileSize(verify) <= 0)
     {
      if(verify != INVALID_HANDLE)
         FileClose(verify);
      MarkPersistenceFailure("event verification failed");
      return(false);
     }
   FileClose(verify);
   event_segment = target_segment;
   event_segment_records = target_records + 1;
   ++event_records;
   return(true);
  }


bool AcquireRuntimeOwnership()
  {
   ResetLastError();
   int ownership_flags = FILE_WRITE | FILE_TXT | FILE_ANSI;
   if(!tester_mode)
      ownership_flags |= FILE_COMMON;
   ownership_handle = FileOpen(OWNERSHIP_PATH,
                               ownership_flags);
   if(ownership_handle == INVALID_HANDLE)
     {
      PrintFormat("%s runtime ownership unavailable; duplicate instance "
                  "or storage failure error=%d",
                  EXECUTION_VERSION, GetLastError());
      return(false);
     }
   FileWriteString(ownership_handle,
                   EXECUTION_VERSION + "," + (string)ChartID() + "," +
                   TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS));
   FileFlush(ownership_handle);
   return(true);
  }


void ReleaseRuntimeOwnership()
  {
   if(ownership_handle == INVALID_HANDLE)
      return;
   FileClose(ownership_handle);
   ownership_handle = INVALID_HANDLE;
  }


void ResetTesterArtifacts()
  {
   FileDelete(STATE_PATH_A);
   FileDelete(STATE_PATH_B);
   FileDelete(EVENT_PATH_A);
   FileDelete(EVENT_PATH_B);
   FileDelete(CURRENT_SNAPSHOT_PATH_A);
   FileDelete(CURRENT_SNAPSHOT_PATH_B);
   FileDelete("ZetaTerminus\\live\\zt-pre500-finite-risk-portfolio-v5-current.csv");
   FileDelete(OWNERSHIP_PATH);
  }


bool NewEntriesAuthorized()
  {
   if(tester_mode)
      return(true);
   return(InpAllowNewEntries &&
          TerminalInfoInteger(TERMINAL_CONNECTED) &&
          LiveAccountIdentityCompatible() &&
          TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
          MQLInfoInteger(MQL_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) &&
          AccountInfoInteger(ACCOUNT_TRADE_EXPERT));
  }


bool NewEntriesOperationallyAllowed()
  {
   return(NewEntriesAuthorized() &&
          !passive_cancel_pending &&
          !safety_stopped &&
          !persistence_failed &&
          !broker_mismatch &&
          !foreign_exposure &&
          FPMarketsServerClockCompatible());
  }


double ProjectStageBalance()
  {
   return(InpReferenceCapitalUSD + project_realized_net);
  }


string DecisionJournalStageName(const int stage)
  {
   if(stage == JOURNAL_SIGNAL_DECIDED)
      return("SIGNAL_DECIDED");
   if(stage == JOURNAL_ORDER_ATTEMPTED)
      return("ORDER_ATTEMPTED");
   if(stage == JOURNAL_BROKER_STATE_ADOPTED)
      return("BROKER_STATE_ADOPTED");
   return("NONE");
  }


bool PersistDecisionUntil(const int component,
                          const datetime bar,
                          const datetime deadline)
  {
   last_decision_bar[component] = bar;
   if(entry_check_signal_passed[component] != 1)
      return(SaveState());
   if(component < 0 || component >= COMPONENT_COUNT || bar <= 0 ||
      deadline < bar || MathAbs(entry_check_direction[component]) != 1 ||
      !MathIsValidNumber(entry_check_signal_value[component]) ||
      decision_journal_stage != JOURNAL_NONE)
     {
      broker_mismatch = true;
      EngageSafetyStop("decision journal cannot begin unambiguously");
      return(false);
     }
   decision_journal_stage = JOURNAL_SIGNAL_DECIDED;
   decision_journal_component = component;
   decision_journal_bar = bar;
   decision_journal_direction = entry_check_direction[component];
   decision_journal_feature = entry_check_signal_value[component];
   decision_journal_deadline = deadline;
   decision_journal_attempted_server = 0;
   decision_journal_adopted_ticket = 0;
   ++journal_signal_decisions;
   // The state write is intentionally first. Once it succeeds, a restart
   // cannot replay this opportunity even if the audit event write is lost.
   if(!SaveState())
      return(false);
   const bool event_saved =
      RecordEvent(component,
                  "SIGNAL_DECIDED",
                  decision_journal_feature,
                  (double)decision_journal_direction,
                  StringFormat("bar=%s deadline=%s replay=0",
                               TimeToString(bar,
                                            TIME_DATE | TIME_MINUTES),
                               TimeToString(deadline,
                                            TIME_DATE | TIME_MINUTES)));
   const bool counters_saved = SaveState();
   return(event_saved && counters_saved);
  }


bool PersistDecision(const int component, const datetime bar)
  {
   return(PersistDecisionUntil(component,
                               bar,
                               bar + InpMaxEntryDelayMinutes * 60));
  }


bool MarkDecisionOrderAttempted(const int component,
                                const int direction,
                                const double feature,
                                const string operation)
  {
   if(decision_journal_stage != JOURNAL_SIGNAL_DECIDED ||
      decision_journal_component != component ||
      decision_journal_bar <= 0 ||
      MathAbs(decision_journal_direction) != 1 ||
      direction != decision_journal_direction ||
      !MathIsValidNumber(feature) ||
      MathAbs(feature - decision_journal_feature) > 1.0e-10 ||
      TimeCurrent() > decision_journal_deadline)
     {
      broker_mismatch = true;
      EngageSafetyStop("order attempt lacks an active decision journal");
      return(false);
     }
   decision_journal_stage = JOURNAL_ORDER_ATTEMPTED;
   decision_journal_attempted_server = TimeCurrent();
   ++journal_order_attempts;
   // ORDER_ATTEMPTED is the durable intent immediately before the
   // synchronous broker call. It does not claim that the broker received it.
   if(!SaveState())
      return(false);
   const bool event_saved =
      RecordEvent(component,
                  "ORDER_ATTEMPTED",
                  (double)decision_journal_direction,
                  (double)decision_journal_bar,
                  StringFormat("operation=%s attempted=%s replay=0",
                               operation,
                               TimeToString(decision_journal_attempted_server,
                                            TIME_DATE | TIME_SECONDS)));
   const bool counters_saved = SaveState();
   return(event_saved && counters_saved);
  }


bool MarkDecisionBrokerStateAdopted(const int component,
                                    const ulong broker_ticket,
                                    const string adoption)
  {
   if(decision_journal_stage != JOURNAL_ORDER_ATTEMPTED ||
      decision_journal_component != component || broker_ticket == 0)
     {
      broker_mismatch = true;
      EngageSafetyStop("broker adoption lacks an attempted decision journal");
      return(false);
     }
   decision_journal_stage = JOURNAL_BROKER_STATE_ADOPTED;
   decision_journal_adopted_ticket = broker_ticket;
   ++journal_broker_adoptions;
   if(!SaveState())
      return(false);
   const bool event_saved =
      RecordEvent(component,
                  "BROKER_STATE_ADOPTED",
                  (double)broker_ticket,
                  (double)decision_journal_bar,
                  adoption);
   const bool counters_saved = SaveState();
   return(event_saved && counters_saved);
  }


bool FinalizeDecisionJournal(const int component,
                             const string outcome)
  {
   if(decision_journal_stage == JOURNAL_NONE)
      return(true);
   if(decision_journal_component != component)
     {
      broker_mismatch = true;
      EngageSafetyStop("decision journal component mismatch at finalization");
      return(false);
     }
   const string stage_name =
      DecisionJournalStageName(decision_journal_stage);
   if(!RecordEvent(component,
                   "DECISION_JOURNAL_FINAL",
                   (double)decision_journal_stage,
                   (double)decision_journal_adopted_ticket,
                   StringFormat("stage=%s outcome=%s replay=0",
                                stage_name,
                                outcome)))
     {
      SaveState();
      return(false);
     }
   ClearDecisionJournalState();
   return(SaveState());
  }


bool ResolveRestartDecisionJournal()
  {
   if(decision_journal_stage == JOURNAL_NONE)
      return(true);
   const int component = decision_journal_component;
   ulong position_ticket = 0;
   datetime opened_at = 0;
   const int positions =
      CountOwnedPositions(component, position_ticket, opened_at);
   ulong order_ticket = 0;
   const int orders =
      (component == US100_PASSIVE_LIMIT
       ? CountOwnedPassiveOrders(order_ticket) : 0);
   const string stage_name =
      DecisionJournalStageName(decision_journal_stage);
   ++journal_restart_resolutions;
   if(!RecordEvent(component,
                   "RESTART_JOURNAL_NO_REPLAY",
                   (double)decision_journal_stage,
                   (double)decision_journal_adopted_ticket,
                   StringFormat("stage=%s positions=%d orders=%d deadline=%s expired=%d automatic_replay=0",
                                stage_name,
                                positions,
                                orders,
                                TimeToString(decision_journal_deadline,
                                             TIME_DATE | TIME_SECONDS),
                                (int)(TimeCurrent() >
                                      decision_journal_deadline))))
     {
      SaveState();
      return(false);
     }
   ClearDecisionJournalState();
   return(SaveState());
  }


void UpdateSizingDay()
  {
   const datetime current_day = ServerMidnight();
   if(current_day == sizing_server_day)
      return;
   sizing_server_day = current_day;
   const double growth = MathMax(0.0,
                                 stressed_balance -
                                 InpReferenceCapitalUSD);
   day_volume_multiplier =
      1 + (int)MathFloor(growth / InpAdditionStepUSD + 1.0e-9);
   day_volume_multiplier = MathMax(1, day_volume_multiplier);
   if(runtime_ready)
     {
      RecordEvent(-1,
                  "SIZE_DAY",
                  stressed_balance,
                  (double)day_volume_multiplier,
                  TimeToString(current_day, TIME_DATE));
      SaveState();
     }
  }


double NormalizedVolume(const string symbol)
  {
   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      return(0.0);
   const double requested = InpBaseVolume * day_volume_multiplier;
   const double normalized = MathRound(requested / step) * step;
   if(normalized < minimum || normalized > maximum)
      return(0.0);
   return(normalized);
  }


double ConservativeRiskCapital()
  {
   double capital = ProjectStageBalance();
   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(capital <= 0.0 || balance <= 0.0 || equity <= 0.0 ||
      stressed_balance <= 0.0)
      return(0.0);
   capital = MathMin(capital, balance);
   capital = MathMin(capital, equity);
   capital = MathMin(capital, stressed_balance);
   return(capital);
  }


double TrackedAggregatePlannedRisk()
  {
   double risk = MathMax(0.0, passive_pending_planned_risk_usd);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      risk += MathMax(0.0, entry_planned_risk_usd[component]);
   return(risk);
  }


double MinimumProtectionDistance(const string symbol)
  {
   const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const long stops_level =
      SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const long freeze_level =
      SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return(MathMax(tick_size,
                  (double)MathMax(stops_level, freeze_level) * point));
  }


bool GrossStopRisk(const string symbol,
                   const int direction,
                   const double volume,
                   const double entry_price,
                   const double stop_loss,
                   double &gross_risk)
  {
   gross_risk = 0.0;
   if(direction == 0 || volume <= 0.0 || entry_price <= 0.0 ||
      stop_loss <= 0.0 ||
      (direction > 0 && stop_loss >= entry_price) ||
      (direction < 0 && stop_loss <= entry_price))
      return(false);
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double direct_usd_risk =
      MathAbs(entry_price - stop_loss) * contract_size * volume;
   if(contract_size <= 0.0 || !MathIsValidNumber(direct_usd_risk) ||
      direct_usd_risk <= 0.0)
      return(false);
   double profit = 0.0;
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const bool broker_risk_known =
      OrderCalcProfit(order_type,
                      symbol,
                      volume,
                      entry_price,
                      stop_loss,
                      profit);
   if(broker_risk_known &&
      (!MathIsValidNumber(profit) || profit > 1.0e-9))
      return(false);
   // FPMarkets' tester can decline or round a one-tick loss calculation.
   // The startup contract fixes a USD profit currency and unit contract size,
   // so the direct linear loss remains valid and is never smaller than a
   // broker value when one is available.
   gross_risk = MathMax(direct_usd_risk,
                        (broker_risk_known ? MathMax(0.0, -profit) : 0.0));
   return(gross_risk > 0.0);
  }


bool BufferedPlannedRisk(const string symbol,
                         const int direction,
                         const double volume,
                         const double entry_price,
                         const double stop_loss,
                         double &planned_risk)
  {
   planned_risk = 0.0;
   double gross_risk = 0.0;
   if(!GrossStopRisk(symbol,
                     direction,
                     volume,
                     entry_price,
                     stop_loss,
                     gross_risk))
      return(false);
   const double modeled_fraction =
      1.0 - InpUnmodelledRiskReserveFraction;
   if(modeled_fraction <= 0.0)
      return(false);
   planned_risk = gross_risk / modeled_fraction;
   return(MathIsValidNumber(planned_risk) && planned_risk > 0.0);
  }


bool StopRiskAtTicks(const string symbol,
                     const int direction,
                     const double volume,
                     const double entry_price,
                     const double tick_size,
                     const int digits,
                     const long ticks,
                     double &candidate_stop,
                     double &gross_risk)
  {
   candidate_stop = 0.0;
   gross_risk = 0.0;
   if(ticks < 1)
      return(false);
   const double raw_stop =
      entry_price - (double)direction * (double)ticks * tick_size;
   const double units = raw_stop / tick_size;
   candidate_stop =
      NormalizeDouble((direction > 0
                       ? MathFloor(units + 1.0e-9) * tick_size
                       : MathCeil(units - 1.0e-9) * tick_size),
                      digits);
   if(candidate_stop <= 0.0 ||
      (direction > 0 && candidate_stop >= entry_price) ||
      (direction < 0 && candidate_stop <= entry_price))
      return(false);
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double direct_usd_risk =
      MathAbs(entry_price - candidate_stop) * contract_size * volume;
   if(contract_size <= 0.0 || !MathIsValidNumber(direct_usd_risk) ||
      direct_usd_risk <= 0.0)
      return(false);
   double profit = 0.0;
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const bool broker_risk_known =
      OrderCalcProfit(order_type,
                      symbol,
                      volume,
                      entry_price,
                      candidate_stop,
                      profit);
   if(broker_risk_known &&
      (!MathIsValidNumber(profit) || profit > 1.0e-9))
      return(false);
   gross_risk = MathMax(direct_usd_risk,
                        (broker_risk_known ? MathMax(0.0, -profit) : 0.0));
   return(true);
  }


bool CalculateProtectiveStop(const int component,
                             const string symbol,
                             const int direction,
                             const double volume,
                             const double entry_price,
                             const double minimum_distance,
                             double &stop_loss,
                             double &planned_risk)
  {
   stop_loss = 0.0;
   planned_risk = 0.0;
   const double capital = ConservativeRiskCapital();
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   const double position_budget =
      capital * InpMaximumPositionRiskFraction;
   const double target_gross_risk =
      position_budget *
      (1.0 - InpUnmodelledRiskReserveFraction -
       InpStopPlacementHeadroomFraction);
   if(capital <= 0.0 || tick_size <= 0.0 || volume <= 0.0 ||
      entry_price <= 0.0 || minimum_distance <= 0.0 ||
      target_gross_risk <= 0.0)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  capital,
                  entry_price,
                  "invalid risk or contract input");
      return(false);
     }

   const long minimum_ticks =
      (long)MathCeil(minimum_distance / tick_size - 1.0e-9);
   double minimum_stop = 0.0;
   double minimum_gross_risk = 0.0;
   if(minimum_ticks < 1 ||
      !StopRiskAtTicks(symbol,
                       direction,
                       volume,
                       entry_price,
                       tick_size,
                       digits,
                       minimum_ticks,
                       minimum_stop,
                       minimum_gross_risk))
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  target_gross_risk,
                  minimum_distance,
                  "minimum stop risk unavailable");
      return(false);
     }
   if(minimum_gross_risk > target_gross_risk + 1.0e-9)
     {
      ++risk_admission_skips;
      RecordEvent(component,
                  "RISK_MIN_LOT_SKIP",
                  position_budget,
                  minimum_gross_risk,
                  StringFormat("min_ticks=%I64d target_gross=%.4f volume=%.2f",
                               minimum_ticks,
                               target_gross_risk,
                               volume));
      return(false);
     }

   long upper_ticks = MathMax((long)1, minimum_ticks);
   double upper_stop = 0.0;
   double upper_gross_risk = 0.0;
   bool bracketed = false;
   for(int expansion = 0; expansion < 50; ++expansion)
     {
      if(!StopRiskAtTicks(symbol,
                          direction,
                          volume,
                          entry_price,
                          tick_size,
                          digits,
                          upper_ticks,
                          upper_stop,
                          upper_gross_risk))
         break;
      if(upper_gross_risk > target_gross_risk + 1.0e-9)
        {
         bracketed = true;
         break;
        }
      if(upper_ticks > 1000000000)
         break;
      upper_ticks *= 2;
     }
   if(!bracketed)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  target_gross_risk,
                  upper_gross_risk,
                  "stop-risk search could not bracket budget");
      return(false);
     }

   long lower_ticks = minimum_ticks;
   long best_ticks = 0;
   while(lower_ticks <= upper_ticks)
     {
      const long middle_ticks =
         lower_ticks + (upper_ticks - lower_ticks) / 2;
      double middle_stop = 0.0;
      double middle_gross_risk = 0.0;
      if(!StopRiskAtTicks(symbol,
                          direction,
                          volume,
                          entry_price,
                          tick_size,
                          digits,
                          middle_ticks,
                          middle_stop,
                          middle_gross_risk))
        {
         upper_ticks = middle_ticks - 1;
         continue;
        }
      if(middle_gross_risk <= target_gross_risk + 1.0e-9)
        {
         best_ticks = middle_ticks;
         stop_loss = middle_stop;
         lower_ticks = middle_ticks + 1;
        }
      else
         upper_ticks = middle_ticks - 1;
     }
   if(best_ticks < minimum_ticks || stop_loss <= 0.0)
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  target_gross_risk,
                  (double)best_ticks,
                  "stop-risk search found no admissible price");
      return(false);
     }
   const double actual_distance =
      (direction > 0 ? entry_price - stop_loss : stop_loss - entry_price);
   if(actual_distance + 0.25 * tick_size < minimum_distance ||
      !BufferedPlannedRisk(symbol,
                           direction,
                           volume,
                           entry_price,
                           stop_loss,
                           planned_risk))
     {
      ++protection_calculation_failures;
      RecordEvent(component,
                  "PROTECTION_CALC_FAIL",
                  stop_loss,
                  actual_distance,
                  "rounded stop invalid");
      stop_loss = 0.0;
      planned_risk = 0.0;
      return(false);
     }

   const double aggregate_after =
      TrackedAggregatePlannedRisk() + position_budget;
   const double aggregate_budget =
      capital * InpMaximumAggregateRiskFraction;
   const double tolerance = 0.01;
   if(planned_risk > position_budget + tolerance ||
      aggregate_after > aggregate_budget + tolerance)
     {
      ++risk_admission_skips;
      RecordEvent(component,
                  "RISK_ADMISSION_SKIP",
                  planned_risk,
                  aggregate_after,
                  StringFormat("position_cap=%.4f aggregate_cap=%.4f",
                               position_budget,
                               aggregate_budget));
      stop_loss = 0.0;
      planned_risk = 0.0;
      return(false);
     }
   if(aggregate_after > maximum_aggregate_planned_risk_usd)
      maximum_aggregate_planned_risk_usd = aggregate_after;
   planned_risk = position_budget;
   return(true);
  }


bool StructurallyValidTick(const string symbol, MqlTick &tick)
  {
   if(!SymbolInfoTick(symbol, tick) || tick.ask <= tick.bid || tick.time <= 0)
      return(false);
   return(true);
  }


bool ExecutableTick(const string symbol, MqlTick &tick)
  {
   if(!StructurallyValidTick(symbol, tick))
      return(false);
   const double age_seconds =
      MathAbs((double)((long)TimeCurrent() - (long)tick.time));
   return(age_seconds <= MAX_EXECUTABLE_TICK_AGE_SECONDS);
  }


bool CurrentTradeSessionStart(const string symbol,
                              const datetime now,
                              datetime &session_start)
  {
   session_start = 0;
   if(now <= 0)
      return(false);
   MqlDateTime parts = {};
   TimeToStruct(now, parts);
   const ulong seconds_per_day = 86400;
   const ulong time_of_day = (ulong)now % seconds_per_day;
   const datetime midnight = now - (datetime)time_of_day;
   for(uint session = 0; session < 16; ++session)
     {
      datetime from = 0;
      datetime to = 0;
      if(!SymbolInfoSessionTrade(symbol,
                                 (ENUM_DAY_OF_WEEK)parts.day_of_week,
                                 session,
                                 from,
                                 to))
         break;
      const ulong session_from = (ulong)from;
       const ulong session_to = (ulong)to;
       if(session_to > session_from &&
          time_of_day >= session_from && time_of_day < session_to)
         {
          session_start = midnight + (datetime)session_from;
          return(true);
         }
       if(session_to < session_from &&
          (time_of_day >= session_from || time_of_day < session_to))
         {
          session_start =
             (time_of_day >= session_from
              ? midnight + (datetime)session_from
              : midnight - 86400 + (datetime)session_from);
          return(true);
         }
     }
   return(false);
  }


bool TradeSessionAllows(const string symbol,
                        const datetime now,
                        const bool opening)
  {
   datetime session_start = 0;
   if(!CurrentTradeSessionStart(symbol, now, session_start))
      return(false);
   const ENUM_SYMBOL_TRADE_MODE mode =
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
   if(opening)
      return(mode == SYMBOL_TRADE_MODE_FULL);
   return(mode != SYMBOL_TRADE_MODE_DISABLED);
  }


bool MarginAllows(const string symbol,
                   const int direction,
                   const double volume)
  {
   MqlTick tick = {};
   if(!ExecutableTick(symbol, tick))
      return(false);
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double price = (direction > 0 ? tick.ask : tick.bid);
   double required_margin = 0.0;
   if(!OrderCalcMargin(order_type,
                       symbol,
                       volume,
                       price,
                       required_margin))
      return(false);
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double projected_margin =
      AccountInfoDouble(ACCOUNT_MARGIN) + required_margin;
   if(equity <= 0.0 ||
      projected_margin > equity * InpMaximumMarginFraction)
     {
      PrintFormat("%s margin skip symbol=%s required=%.2f projected=%.2f "
                  "equity=%.2f limit=%.2f",
                  EXECUTION_VERSION,
                  symbol,
                  required_margin,
                  projected_margin,
                  equity,
                  InpMaximumMarginFraction);
      return(false);
     }
   return(true);
  }


bool PassiveMarginAllows(const int direction, const double limit_price)
  {
   const ENUM_ORDER_TYPE order_type =
      (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double required_margin = 0.0;
   if(!OrderCalcMargin(order_type,
                       "US100",
                       InpBaseVolume,
                       limit_price,
                       required_margin) || required_margin <= 0.0)
     {
      ++passive_margin_calculation_failures;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_MARGIN_CALC_FAIL",
                  (double)direction,
                  limit_price,
                  IntegerToString(GetLastError()));
      return(false);
     }
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double projected_margin =
      AccountInfoDouble(ACCOUNT_MARGIN) + required_margin;
   if(equity <= 0.0 ||
      projected_margin > equity * InpMaximumMarginFraction)
     {
      ++passive_margin_skips;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_MARGIN_SKIP",
                  projected_margin,
                  equity,
                  DoubleToString(required_margin, 4));
      return(false);
     }
   return(true);
  }


int ComponentForMagic(const ulong magic, const string symbol)
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(magic == COMPONENT_MAGICS[component] &&
         symbol == COMPONENT_SYMBOLS[component])
         return(component);
   return(-1);
  }


datetime BarForTime(const int component, const datetime value)
  {
   const int shift = iBarShift(COMPONENT_SYMBOLS[component],
                               COMPONENT_TIMEFRAMES[component],
                               value,
                               false);
   if(shift < 0)
      return(0);
   return(iTime(COMPONENT_SYMBOLS[component],
                COMPONENT_TIMEFRAMES[component],
                shift));
  }


bool QuoteAtMilliseconds(const string symbol,
                         const long target_msc,
                         MqlTick &quote)
  {
   if(target_msc <= 0)
      return(false);
   const ulong from_msc = (ulong)MathMax(0.0, (double)target_msc - 5000.0);
   const ulong to_msc = (ulong)((long)target_msc + 5000);
   MqlTick ticks[];
   const int count = CopyTicksRange(symbol,
                                    ticks,
                                    COPY_TICKS_ALL,
                                    from_msc,
                                    to_msc);
   int selected = -1;
   long selected_distance = LONG_MAX;
   bool selected_preceding = false;
   for(int index = 0; index < count; ++index)
     {
      if(ticks[index].ask <= ticks[index].bid || ticks[index].bid <= 0.0)
         continue;
      const bool preceding = (ticks[index].time_msc <= target_msc);
      const long distance =
         (long)MathAbs((double)(ticks[index].time_msc - target_msc));
      if(selected < 0 ||
         (preceding && !selected_preceding) ||
         (preceding == selected_preceding && distance < selected_distance))
        {
         selected = index;
         selected_distance = distance;
         selected_preceding = preceding;
        }
     }
   if(selected < 0)
      return(false);
   quote = ticks[selected];
   return(true);
  }


bool VolumeToSteps(const string symbol,
                   const double volume,
                   long &steps)
  {
   steps = 0;
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || volume <= 0.0 || !MathIsValidNumber(volume))
      return(false);
   const double raw_steps = volume / step;
   steps = (long)MathRound(raw_steps);
   return(steps > 0 &&
          MathAbs(volume - (double)steps * step) <=
          MathMax(1.0e-8, step * 1.0e-6));
  }


bool DealAfterExitCursor(const int component,
                         const long time_msc,
                         const ulong deal)
  {
   return(time_msc > last_processed_exit_time_msc[component] ||
          (time_msc == last_processed_exit_time_msc[component] &&
           deal > last_processed_exit_deal[component]));
  }


bool AggregateEntryDeals(const int component,
                         const ulong position_identifier,
                         const ulong required_order,
                         const MqlTick &sampled_tick,
                         const bool sampled_tick_known,
                         EntryDealAggregate &aggregate)
  {
   aggregate.first_deal = 0;
   aggregate.last_deal = 0;
   aggregate.order_ticket = 0;
   aggregate.first_time_msc = 0;
   aggregate.last_time_msc = 0;
   aggregate.first_time_server = 0;
   aggregate.direction = 0;
   aggregate.volume_steps = 0;
   aggregate.volume = 0.0;
   aggregate.price = 0.0;
   aggregate.transaction_cost = 0.0;
   aggregate.spread_price = 0.0;
   aggregate.adverse_slippage = 0.0;
   aggregate.cost_known = true;
   aggregate.deal_count = 0;
   if(position_identifier == 0 ||
      !HistorySelectByPosition(position_identifier))
      return(false);
   const string symbol = COMPONENT_SYMBOLS[component];
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(step <= 0.0 || contract_size <= 0.0)
      return(false);
   double price_volume_sum = 0.0;
   double spread_volume_sum = 0.0;
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         COMPONENT_MAGICS[component] ||
         HistoryDealGetString(deal, DEAL_SYMBOL) != symbol ||
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) !=
         position_identifier)
         continue;
      const ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN)
         continue;
      const ENUM_DEAL_TYPE type =
         (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
      const int direction =
         (type == DEAL_TYPE_BUY ? 1 :
          (type == DEAL_TYPE_SELL ? -1 : 0));
      const ulong order =
         (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
      const double volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
      const double price = HistoryDealGetDouble(deal, DEAL_PRICE);
      const long time_msc = HistoryDealGetInteger(deal, DEAL_TIME_MSC);
      long volume_steps = 0;
      if(direction == 0 || order == 0 || price <= 0.0 || time_msc <= 0 ||
         !VolumeToSteps(symbol, volume, volume_steps) ||
         (required_order > 0 && order != required_order) ||
         (aggregate.direction != 0 && aggregate.direction != direction) ||
         (aggregate.order_ticket != 0 && aggregate.order_ticket != order))
         return(false);
      aggregate.direction = direction;
      aggregate.order_ticket = order;
      aggregate.volume_steps += volume_steps;
      price_volume_sum += price * volume;
      aggregate.transaction_cost +=
         HistoryDealGetDouble(deal, DEAL_COMMISSION) +
         HistoryDealGetDouble(deal, DEAL_SWAP) +
         HistoryDealGetDouble(deal, DEAL_FEE);
      MqlTick quote = sampled_tick;
      bool quote_known = sampled_tick_known;
      if(!quote_known)
         quote_known = QuoteAtMilliseconds(symbol, time_msc, quote);
      if(quote_known)
        {
         const double spread = quote.ask - quote.bid;
         const double adverse_price =
            (direction > 0
             ? MathMax(0.0, price - quote.ask)
             : MathMax(0.0, quote.bid - price));
         spread_volume_sum += spread * volume;
         aggregate.adverse_slippage +=
            adverse_price * contract_size * volume;
        }
      else
         aggregate.cost_known = false;
      if(aggregate.first_deal == 0 ||
         time_msc < aggregate.first_time_msc ||
         (time_msc == aggregate.first_time_msc &&
          deal < aggregate.first_deal))
        {
         aggregate.first_deal = deal;
         aggregate.first_time_msc = time_msc;
         aggregate.first_time_server =
            (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
        }
      if(aggregate.last_deal == 0 ||
         time_msc > aggregate.last_time_msc ||
         (time_msc == aggregate.last_time_msc &&
          deal > aggregate.last_deal))
        {
         aggregate.last_deal = deal;
         aggregate.last_time_msc = time_msc;
        }
      ++aggregate.deal_count;
     }
   if(aggregate.deal_count <= 0 || aggregate.volume_steps <= 0 ||
      aggregate.first_deal == 0 || aggregate.last_deal == 0 ||
      aggregate.order_ticket == 0 || aggregate.first_time_server <= 0)
      return(false);
   aggregate.volume = (double)aggregate.volume_steps * step;
   aggregate.price = price_volume_sum / aggregate.volume;
   aggregate.spread_price = spread_volume_sum / aggregate.volume;
   return(MathIsValidNumber(aggregate.price) && aggregate.price > 0.0 &&
          MathIsValidNumber(aggregate.transaction_cost) &&
          MathIsValidNumber(aggregate.spread_price) &&
          aggregate.spread_price >= 0.0 &&
          MathIsValidNumber(aggregate.adverse_slippage) &&
          aggregate.adverse_slippage >= 0.0);
  }


bool EntryPositionIdentifierForOrder(const int component,
                                     const ulong order_ticket,
                                     ulong &position_identifier)
  {
   position_identifier = 0;
   if(order_ticket == 0 || !HistorySelect(0, TimeCurrent()))
      return(false);
   int matches = 0;
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         COMPONENT_MAGICS[component] ||
         HistoryDealGetString(deal, DEAL_SYMBOL) !=
         COMPONENT_SYMBOLS[component] ||
         (ulong)HistoryDealGetInteger(deal, DEAL_ORDER) != order_ticket)
         continue;
      const ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN)
         continue;
      const ulong identifier =
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      if(identifier == 0 ||
         (position_identifier != 0 && position_identifier != identifier))
         return(false);
      position_identifier = identifier;
      ++matches;
     }
   return(matches > 0 && position_identifier > 0);
  }


bool WaitForEntryDealAggregation(const int component,
                                 const ulong position_identifier,
                                 const MqlTick &sampled_tick,
                                 const long requested_steps,
                                 const bool completed_partial,
                                 EntryDealAggregate &aggregate,
                                 ulong &waited_ms)
  {
   waited_ms = 0;
   if(requested_steps <= 0)
      return(false);
   const ulong started = GetTickCount64();
   while(true)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      long position_steps = 0;
      if(count == 1 && PositionSelectByTicket(ticket) &&
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) ==
         position_identifier &&
         VolumeToSteps(COMPONENT_SYMBOLS[component],
                       PositionGetDouble(POSITION_VOLUME),
                       position_steps) &&
         AggregateEntryDeals(component,
                             position_identifier,
                             0,
                             sampled_tick,
                             true,
                             aggregate) &&
         aggregate.volume_steps == position_steps &&
         aggregate.volume_steps <= requested_steps &&
         (completed_partial ||
          aggregate.volume_steps == requested_steps))
        {
         waited_ms = GetTickCount64() - started;
         return(true);
        }
      waited_ms = GetTickCount64() - started;
      if(count > 1 || tester_mode ||
         waited_ms >= COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
         return(false);
      Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
     }
  }


int CollectUnprocessedExitDeals(const int component,
                                const ulong position_identifier,
                                SequencedExitDeal &deals[])
  {
   ArrayResize(deals, 0);
   if(position_identifier == 0 ||
      !HistorySelectByPosition(position_identifier))
      return(-1);
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
         COMPONENT_MAGICS[component] ||
         HistoryDealGetString(deal, DEAL_SYMBOL) !=
         COMPONENT_SYMBOLS[component] ||
         (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) !=
         position_identifier)
         continue;
      const ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         continue;
      const long time_msc = HistoryDealGetInteger(deal, DEAL_TIME_MSC);
      if(time_msc <= 0)
         return(-1);
      if(!DealAfterExitCursor(component, time_msc, deal))
         continue;
      const int count = ArraySize(deals);
      if(ArrayResize(deals, count + 1) != count + 1)
         return(-1);
      deals[count].ticket = deal;
      deals[count].time_msc = time_msc;
     }
   const int count = ArraySize(deals);
   for(int index = 1; index < count; ++index)
     {
      const SequencedExitDeal current = deals[index];
      int cursor = index - 1;
      while(cursor >= 0 &&
            (deals[cursor].time_msc > current.time_msc ||
             (deals[cursor].time_msc == current.time_msc &&
              deals[cursor].ticket > current.ticket)))
        {
         deals[cursor + 1] = deals[cursor];
         --cursor;
        }
      deals[cursor + 1] = current;
     }
   return(count);
  }


bool HasOwnedDealHistory()
  {
   if(!HistorySelect(0, TimeCurrent()))
      return(false);
   for(int index = 0; index < HistoryDealsTotal(); ++index)
     {
      const ulong deal = HistoryDealGetTicket(index);
      if(deal > 0 &&
         IsOwnedMagic((ulong)HistoryDealGetInteger(deal, DEAL_MAGIC)))
         return(true);
     }
   return(false);
  }


bool ReconstructEntryTracking(const int component, const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))
      return(false);
   const ulong identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   MqlTick empty_tick = {};
   EntryDealAggregate aggregate = {};
   if(identifier == 0 ||
      !AggregateEntryDeals(component,
                           identifier,
                           0,
                           empty_tick,
                           false,
                           aggregate))
     {
      broker_mismatch = true;
      EngageSafetyStop("cannot reconstruct entry deal sequence");
      return(false);
     }
   if(!PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      broker_mismatch = true;
      EngageSafetyStop("position changed during entry reconstruction");
      return(false);
     }
   const double volume = PositionGetDouble(POSITION_VOLUME);
   long current_steps = 0;
   long configured_steps = 0;
   if(!VolumeToSteps(COMPONENT_SYMBOLS[component],
                     volume,
                     current_steps) ||
      aggregate.volume_steps < current_steps ||
      (component == US100_PASSIVE_LIMIT &&
       (!VolumeToSteps(COMPONENT_SYMBOLS[component],
                       InpBaseVolume,
                       configured_steps) ||
        aggregate.volume_steps != configured_steps)))
     {
      broker_mismatch = true;
      EngageSafetyStop("entry reconstruction volume mismatch");
      return(false);
     }
   const ENUM_POSITION_TYPE position_type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const int direction = (position_type == POSITION_TYPE_BUY ? 1 : -1);
   const datetime opened_at =
      (datetime)PositionGetInteger(POSITION_TIME);
   const double position_open_price =
      PositionGetDouble(POSITION_PRICE_OPEN);
   const double deal_price = aggregate.price;
   const bool quote_known = aggregate.cost_known;
   if(aggregate.direction != direction)
     {
      broker_mismatch = true;
      EngageSafetyStop("entry reconstruction direction mismatch");
      return(false);
     }
   const double broker_stop_loss = PositionGetDouble(POSITION_SL);
   double recovered_stop_loss = 0.0;
   double recovered_planned_risk = 0.0;
   if(component == US100_PASSIVE_LIMIT)
     {
      if(passive_pending_stop_loss <= 0.0 ||
         passive_pending_planned_risk_usd <= 0.0)
        {
         broker_mismatch = true;
         EngageSafetyStop("passive entry protection state cannot be reconstructed");
         return(false);
        }
      recovered_stop_loss = passive_pending_stop_loss;
      recovered_planned_risk = passive_pending_planned_risk_usd;
     }
   else
     {
      double gross_stop_risk = 0.0;
      const double modeled_target_fraction =
         1.0 - InpUnmodelledRiskReserveFraction -
         InpStopPlacementHeadroomFraction;
      const double current_position_budget =
         ConservativeRiskCapital() * InpMaximumPositionRiskFraction;
      if(broker_stop_loss <= 0.0 || modeled_target_fraction <= 0.0 ||
         !GrossStopRisk(COMPONENT_SYMBOLS[component],
                        direction,
                        aggregate.volume,
                        position_open_price,
                        broker_stop_loss,
                        gross_stop_risk))
        {
         broker_mismatch = true;
         EngageSafetyStop("market entry broker protection cannot be reconstructed");
         return(false);
        }
      recovered_stop_loss = broker_stop_loss;
      recovered_planned_risk =
         MathMax(gross_stop_risk / modeled_target_fraction,
                 current_position_budget);
      if(!MathIsValidNumber(recovered_planned_risk) ||
         recovered_planned_risk <= 0.0)
        {
         broker_mismatch = true;
         EngageSafetyStop("market entry risk reserve cannot be reconstructed");
         return(false);
        }
     }
   tracked_position_identifier[component] = identifier;
   entry_time_server[component] = aggregate.first_time_server;
   entry_direction[component] = direction;
   entry_volume[component] = aggregate.volume;
   entry_feature[component] =
      (component == US100_PASSIVE_LIMIT
       ? passive_pending_feature : 0.0);
   entry_stop_loss[component] = recovered_stop_loss;
   entry_planned_risk_usd[component] = recovered_planned_risk;
   entry_transaction_cost[component] = aggregate.transaction_cost;
   entry_spread_price[component] = aggregate.spread_price;
   entry_adverse_slippage[component] = aggregate.adverse_slippage;
   entry_cost_known[component] = quote_known;
   string protection_detail = "";
   double actual_planned_risk = 0.0;
   if(!SelectedPositionProtectionMatches(component, protection_detail) ||
       !BufferedPlannedRisk(COMPONENT_SYMBOLS[component],
                            direction,
                            volume,
                            position_open_price,
                            PositionGetDouble(POSITION_SL),
                            actual_planned_risk))
     {
      ++protection_mismatches;
      broker_mismatch = true;
      EngageSafetyStop("reconstructed entry protection mismatch: " +
                       protection_detail);
      return(false);
     }
   entry_stop_loss[component] = PositionGetDouble(POSITION_SL);
   const datetime entry_bar = BarForTime(component, opened_at);
   if(entry_bar > last_decision_bar[component])
      last_decision_bar[component] = entry_bar;
   if(component == US100_PASSIVE_LIMIT)
     {
      ++passive_completed_entries;
      ClearPassivePendingTracking();
     }
   const double aggregate_planned_risk = TrackedAggregatePlannedRisk();
   if(aggregate_planned_risk > maximum_aggregate_planned_risk_usd)
      maximum_aggregate_planned_risk_usd = aggregate_planned_risk;
   if(!quote_known)
     {
      broker_mismatch = true;
      EngageSafetyStop("entry quote history unavailable during recovery");
     }
   RecordEvent(component,
                (component == US100_PASSIVE_LIMIT
                 ? "PASSIVE_FILL" : "RECOVER_MARKET_OPEN"),
               deal_price,
               aggregate.volume,
               StringFormat("%s entry_deals=%d current_volume=%.2f",
                            (quote_known ? "cost-known" : "cost-unknown"),
                            aggregate.deal_count,
                            volume));
   if(!SaveState())
      return(false);
   if(aggregate.volume_steps > current_steps)
     {
      ulong waited_ms = 0;
      if(!ReconcileExitDealSequence(component,
                                    empty_tick,
                                    false,
                                    "RECOVER_PARTIAL",
                                    false,
                                    waited_ms))
        {
         broker_mismatch = true;
         EngageSafetyStop("reconstructed partial exits do not match position");
         return(false);
        }
     }
   return(true);
  }


bool ReconstructClosedPassiveEntry(const ulong order_ticket)
  {
   if(order_ticket == 0 ||
      tracked_position_identifier[US100_PASSIVE_LIMIT] > 0)
      return(false);
   ulong identifier = 0;
   MqlTick empty_tick = {};
   EntryDealAggregate aggregate = {};
   long configured_steps = 0;
   if(!EntryPositionIdentifierForOrder(US100_PASSIVE_LIMIT,
                                       order_ticket,
                                       identifier) ||
      !AggregateEntryDeals(US100_PASSIVE_LIMIT,
                           identifier,
                           order_ticket,
                           empty_tick,
                           false,
                           aggregate) ||
      !aggregate.cost_known ||
      !VolumeToSteps("US100", InpBaseVolume, configured_steps) ||
      aggregate.volume_steps != configured_steps)
     {
      broker_mismatch = true;
      EngageSafetyStop("historical passive entry contract mismatch");
      return(false);
     }
   const int direction = aggregate.direction;
   const double volume = aggregate.volume;
   const double deal_price = aggregate.price;
   tracked_position_identifier[US100_PASSIVE_LIMIT] = identifier;
   entry_time_server[US100_PASSIVE_LIMIT] =
      aggregate.first_time_server;
   entry_direction[US100_PASSIVE_LIMIT] = direction;
   entry_volume[US100_PASSIVE_LIMIT] = volume;
   entry_feature[US100_PASSIVE_LIMIT] = passive_pending_feature;
   if(passive_pending_stop_loss <= 0.0 ||
      passive_pending_planned_risk_usd <= 0.0)
     {
      broker_mismatch = true;
      EngageSafetyStop("historical passive protection state missing");
      return(false);
     }
   entry_stop_loss[US100_PASSIVE_LIMIT] = passive_pending_stop_loss;
   entry_planned_risk_usd[US100_PASSIVE_LIMIT] =
      passive_pending_planned_risk_usd;
   entry_transaction_cost[US100_PASSIVE_LIMIT] =
      aggregate.transaction_cost;
   entry_spread_price[US100_PASSIVE_LIMIT] = aggregate.spread_price;
   entry_adverse_slippage[US100_PASSIVE_LIMIT] =
      aggregate.adverse_slippage;
   entry_cost_known[US100_PASSIVE_LIMIT] = aggregate.cost_known;
   double actual_planned_risk = 0.0;
   if(!BufferedPlannedRisk("US100",
                           direction,
                           volume,
                           deal_price,
                           entry_stop_loss[US100_PASSIVE_LIMIT],
                           actual_planned_risk) ||
      actual_planned_risk >
      entry_planned_risk_usd[US100_PASSIVE_LIMIT] +
      MathMax(0.01,
              entry_planned_risk_usd[US100_PASSIVE_LIMIT] * 0.01))
     {
      ++protection_mismatches;
      broker_mismatch = true;
      EngageSafetyStop("historical passive risk exceeds admission");
      return(false);
     }
   const datetime entry_bar =
      BarForTime(US100_PASSIVE_LIMIT,
                 entry_time_server[US100_PASSIVE_LIMIT]);
   if(entry_bar > last_decision_bar[US100_PASSIVE_LIMIT])
      last_decision_bar[US100_PASSIVE_LIMIT] = entry_bar;
   ++passive_completed_entries;
   ClearPassivePendingTracking();
   RecordEvent(US100_PASSIVE_LIMIT,
               "RECOVER_PASSIVE_FILL",
               deal_price,
               volume,
               StringFormat("feature=%.8f entry_deals=%d order=%I64u",
                            entry_feature[US100_PASSIVE_LIMIT],
                            aggregate.deal_count,
                            order_ticket));
   if(!SaveState())
      return(false);
   ulong waited_ms = 0;
   if(!ReconcileExitDealSequence(US100_PASSIVE_LIMIT,
                                 empty_tick,
                                 false,
                                 "RECOVER_PASSIVE_CLOSE",
                                 false,
                                 waited_ms))
     {
      broker_mismatch = true;
      EngageSafetyStop("filled passive order lacks complete exit sequence");
      return(false);
     }
   return(true);
  }


bool HandleMissingPassivePendingOrder()
  {
   if(tracked_passive_pending_order == 0)
      return(true);
   const ulong order_ticket = tracked_passive_pending_order;
   if(!HistorySelect(0, TimeCurrent()) ||
      !HistoryOrderSelect(order_ticket))
      return(false);
   const ENUM_ORDER_STATE state =
      (ENUM_ORDER_STATE)HistoryOrderGetInteger(order_ticket, ORDER_STATE);
   if(state == ORDER_STATE_EXPIRED)
     {
      const datetime expiration = passive_pending_expiration;
      ++passive_pending_expirations;
      passive_next_entry_current_bar =
         expiration + PASSIVE_BAR_SECONDS;
      ClearPassivePendingTracking();
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_EXPIRE",
                  (double)order_ticket,
                  (double)passive_next_entry_current_bar,
                  TimeToString(expiration, TIME_DATE | TIME_MINUTES));
      return(SaveState());
     }
   if(state == ORDER_STATE_FILLED || state == ORDER_STATE_PARTIAL)
     {
      return(ReconstructClosedPassiveEntry(order_ticket));
     }
   if(state == ORDER_STATE_CANCELED && passive_cancel_pending)
     {
      ClearPassivePendingTracking();
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_CANCEL_RECOVERED",
                  (double)order_ticket,
                  0.0,
                  "persisted cancellation completed before reconciliation");
      return(SaveState());
     }
   ++passive_unexpected_order_outcomes;
   broker_mismatch = true;
   EngageSafetyStop("passive pending order disappeared unexpectedly");
   RecordEvent(US100_PASSIVE_LIMIT,
               "PASSIVE_ORDER_MISMATCH",
               (double)order_ticket,
               (double)state,
               "missing order");
   ClearPassivePendingTracking();
   SaveState();
   return(false);
  }


bool DeferPassivePendingCancellation(const ulong order_ticket,
                                     const string reason)
  {
   if(order_ticket == 0 ||
      tracked_passive_pending_order != order_ticket)
      return(false);
   pending_reconcile = true;
   if(passive_cancel_pending)
      return(true);
   passive_cancel_pending = true;
   ++passive_cancel_connection_deferrals;
   const bool event_written =
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_CANCEL_DEFER",
                  (double)order_ticket,
                  (double)passive_cancel_connection_deferrals,
                  reason);
   const bool state_written = SaveState();
   return(event_written && state_written);
  }


bool CancelPassivePendingOrder(const ulong order_ticket,
                               const string reason)
  {
   if(order_ticket == 0)
      return(false);
   if(!tester_mode && !TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      if(tracked_passive_pending_order == order_ticket)
         DeferPassivePendingCancellation(
            order_ticket,
            reason + "; terminal disconnected before cancellation");
      return(false);
     }
   trade.SetExpertMagicNumber(MAGIC_US100_PASSIVE_LIMIT);
   trade.SetAsyncMode(false);
   trade_operation_active = true;
   const bool requested = trade.OrderDelete(order_ticket);
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   trade_operation_active = false;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      if(retcode == TRADE_RETCODE_CONNECTION &&
         tracked_passive_pending_order == order_ticket)
        {
         DeferPassivePendingCancellation(
            order_ticket,
            reason + "; connection lost during cancellation");
         return(false);
        }
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_CANCEL_FAIL",
                  (double)retcode,
                  (double)order_ticket,
                  retcode_description);
      broker_mismatch = true;
      EngageSafetyStop("passive pending order could not be cancelled");
      SaveState();
      return(false);
     }
   RecordEvent(US100_PASSIVE_LIMIT,
               "PASSIVE_CANCEL",
               (double)order_ticket,
               0.0,
               reason);
   if(tracked_passive_pending_order == order_ticket)
      ClearPassivePendingTracking();
   return(SaveState());
  }


bool ReconcilePassivePendingOrder()
  {
   ulong order_ticket = 0;
   const int order_count = CountOwnedPassiveOrders(order_ticket);
   if(order_count > 1)
      return(false);
   if(order_count == 0)
      return(HandleMissingPassivePendingOrder());
   if(!OrderSelect(order_ticket))
      return(false);
   if(tracked_passive_pending_order == 0 ||
      tracked_passive_pending_order != order_ticket)
     {
      broker_mismatch = true;
      EngageSafetyStop("broker passive order lacks matching local state");
      CancelPassivePendingOrder(order_ticket, "unrecoverable local state");
      return(false);
     }
   const ENUM_ORDER_TYPE type =
      (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
   const int direction =
      (type == ORDER_TYPE_BUY_LIMIT ? 1 :
       (type == ORDER_TYPE_SELL_LIMIT ? -1 : 0));
   const datetime expiration =
      (datetime)OrderGetInteger(ORDER_TIME_EXPIRATION);
   const double price = OrderGetDouble(ORDER_PRICE_OPEN);
   const double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
   const double stop_loss = OrderGetDouble(ORDER_SL);
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   const double volume_step =
      SymbolInfoDouble("US100", SYMBOL_VOLUME_STEP);
   if(direction != passive_pending_direction ||
      expiration != passive_pending_expiration ||
       MathAbs(price - passive_pending_limit_price) >
       MathMax(1.0e-8, 0.5 * tick_size) ||
       MathAbs(stop_loss - passive_pending_stop_loss) >
       MathMax(1.0e-8, 0.5 * tick_size) ||
       MathAbs(volume - InpBaseVolume) >
      MathMax(1.0e-8, 0.5 * volume_step))
     {
      broker_mismatch = true;
      EngageSafetyStop("broker passive order differs from local state");
      CancelPassivePendingOrder(order_ticket, "broker/local mismatch");
      return(false);
     }
   return(true);
  }


bool ApplyExitDeal(const int component,
                   const ulong deal,
                   const MqlTick &sampled_tick,
                   const bool sampled_tick_known,
                   const string event_name)
  {
   if(deal == 0 || !HistoryDealSelect(deal))
      return(false);
   const long deal_time_msc =
      HistoryDealGetInteger(deal, DEAL_TIME_MSC);
   if(!DealAfterExitCursor(component, deal_time_msc, deal))
      return(true);
   if(tracked_position_identifier[component] == 0 ||
      entry_volume[component] <= 0.0 ||
      MathAbs(entry_direction[component]) != 1)
     {
      broker_mismatch = true;
      EngageSafetyStop("exit deal lacks recoverable entry state");
      return(false);
     }
   const ENUM_DEAL_ENTRY deal_entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
   const ENUM_DEAL_TYPE deal_type =
      (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
   const bool direction_matches =
      (entry_direction[component] > 0
       ? deal_type == DEAL_TYPE_SELL
       : deal_type == DEAL_TYPE_BUY);
   if(deal_time_msc <= 0 ||
      (ulong)HistoryDealGetInteger(deal, DEAL_MAGIC) !=
      COMPONENT_MAGICS[component] ||
      HistoryDealGetString(deal, DEAL_SYMBOL) !=
      COMPONENT_SYMBOLS[component] ||
      (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) !=
      tracked_position_identifier[component] ||
      (deal_entry != DEAL_ENTRY_OUT && deal_entry != DEAL_ENTRY_OUT_BY) ||
      !direction_matches)
     {
      broker_mismatch = true;
      EngageSafetyStop("exit execution identity mismatch");
      return(false);
     }
   const double executed_volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
   const string symbol = COMPONENT_SYMBOLS[component];
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   long remaining_before_steps = 0;
   long executed_steps = 0;
   if(step <= 0.0 ||
      !VolumeToSteps(symbol,
                     entry_volume[component],
                     remaining_before_steps) ||
      !VolumeToSteps(symbol, executed_volume, executed_steps) ||
      executed_steps > remaining_before_steps)
     {
      broker_mismatch = true;
      EngageSafetyStop("exit execution volume mismatch");
      return(false);
     }
   const long remaining_after_steps =
      remaining_before_steps - executed_steps;
   const double allocation_fraction =
      (remaining_after_steps == 0
       ? 1.0
       : (double)executed_steps / (double)remaining_before_steps);
   const double allocated_entry_transaction_cost =
      (remaining_after_steps == 0
       ? entry_transaction_cost[component]
       : entry_transaction_cost[component] * allocation_fraction);
   const double allocated_entry_adverse_slippage =
      (remaining_after_steps == 0
       ? entry_adverse_slippage[component]
       : entry_adverse_slippage[component] * allocation_fraction);
   MqlTick exit_tick = sampled_tick;
   bool exit_quote_known = sampled_tick_known;
   if(!exit_quote_known)
      exit_quote_known =
         QuoteAtMilliseconds(symbol,
                             deal_time_msc,
                             exit_tick);
   const double exit_transaction_cost =
      HistoryDealGetDouble(deal, DEAL_COMMISSION) +
      HistoryDealGetDouble(deal, DEAL_SWAP) +
      HistoryDealGetDouble(deal, DEAL_FEE);
   const double deal_net =
      HistoryDealGetDouble(deal, DEAL_PROFIT) + exit_transaction_cost +
      allocated_entry_transaction_cost;
   const int direction = entry_direction[component];
   const double execution_price = HistoryDealGetDouble(deal, DEAL_PRICE);
   const double adverse_exit_price =
      (!exit_quote_known ? 0.0 :
       (direction > 0
        ? MathMax(0.0, exit_tick.bid - execution_price)
        : MathMax(0.0, execution_price - exit_tick.ask)));
   const double contract_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double exit_adverse_slippage =
      adverse_exit_price * contract_size * executed_volume;
   const double exit_spread =
      (exit_quote_known ? exit_tick.ask - exit_tick.bid : 0.0);
   const double additional_spread_cost =
      MathMax(entry_spread_price[component], exit_spread) *
      contract_size * executed_volume;
   const double additional_nonspread_cost =
      allocated_entry_adverse_slippage + exit_adverse_slippage +
      MathMax(0.0, -allocated_entry_transaction_cost) +
      MathMax(0.0, -exit_transaction_cost);
   const double additional_cost =
      additional_spread_cost + additional_nonspread_cost;
   const double stressed_net = deal_net - additional_cost;
   const ENUM_DEAL_REASON exit_reason =
      (ENUM_DEAL_REASON)HistoryDealGetInteger(deal, DEAL_REASON);
   const double admitted_stop_loss = entry_stop_loss[component];
   const double admitted_planned_risk = entry_planned_risk_usd[component];
   const ulong completed_identifier = tracked_position_identifier[component];
   const datetime completed_entry_time = entry_time_server[component];
   const int completed_direction = entry_direction[component];
   const double completed_arc_original_stop = arc_original_stop_loss;
   const bool completed_arc_request_unresolved =
      (arc_modify_pending || arc_modify_retry_pending);
   const double completed_arc_protected_stop =
      (component == RC4_BOTH && completed_arc_request_unresolved &&
       arc_pending_stop_loss > 0.0
       ? arc_pending_stop_loss : admitted_stop_loss);
   const bool compressed_rc4_stop_exit =
      (component == RC4_BOTH && remaining_after_steps == 0 &&
       exit_reason == DEAL_REASON_SL &&
       arc_lifecycle_identifier == completed_identifier &&
        (arc_lifecycle_compressed || completed_arc_request_unresolved));
   if(exit_reason == DEAL_REASON_SL)
      lifecycle_stop_loss_seen[component] = true;
   project_realized_net += deal_net;
   stressed_balance += stressed_net;
   component_stressed_net[component] += stressed_net;
   if(stressed_balance > stressed_peak)
      stressed_peak = stressed_balance;
   const double stressed_drawdown = stressed_peak - stressed_balance;
   if(stressed_drawdown > stressed_maximum_closed_drawdown)
      stressed_maximum_closed_drawdown = stressed_drawdown;
   last_processed_exit_time_msc[component] = deal_time_msc;
   last_processed_exit_deal[component] = deal;
   const bool complete_cost =
      (entry_cost_known[component] && exit_quote_known);
   string applied_event = event_name;
   if(remaining_after_steps == 0)
     {
      if(lifecycle_stop_loss_seen[component])
         ++stop_loss_exits;
      ++closed_trades[component];
      last_close_attempt_server[component] = 0;
      if(compressed_rc4_stop_exit)
        {
         if(completed_arc_request_unresolved && !arc_lifecycle_compressed &&
            (!exit_quote_known ||
             !ArcOriginalStopReached(completed_direction,
                                     completed_arc_original_stop,
                                     exit_tick)))
            ++arc_compressions_placed;
        }
      else if(component == RC4_BOTH)
         ClearArcLifecycleState();
      ClearEntryTracking(component);
      if(compressed_rc4_stop_exit)
         ActivateRC4ShadowAfterCompressedExit(completed_identifier,
                                              completed_entry_time,
                                              completed_direction,
                                              completed_arc_original_stop,
                                              deal,
                                              deal_time_msc,
                                              execution_price,
                                              exit_reason,
                                              completed_arc_protected_stop,
                                              sampled_tick,
                                              sampled_tick_known);
     }
   else
     {
      const double remaining_fraction =
         (double)remaining_after_steps / (double)remaining_before_steps;
      entry_volume[component] = (double)remaining_after_steps * step;
      entry_transaction_cost[component] -=
         allocated_entry_transaction_cost;
      entry_adverse_slippage[component] -=
         allocated_entry_adverse_slippage;
      entry_planned_risk_usd[component] *= remaining_fraction;
      if(MathAbs(entry_transaction_cost[component]) < 1.0e-12)
         entry_transaction_cost[component] = 0.0;
      if(entry_adverse_slippage[component] < 1.0e-12)
         entry_adverse_slippage[component] = 0.0;
      applied_event += "_PARTIAL";
     }
   if(!complete_cost)
     {
      broker_mismatch = true;
      EngageSafetyStop("cost reconstruction incomplete after exit");
     }
   RecordEvent(component,
               applied_event,
               deal_net,
               stressed_net,
               StringFormat("%s reason=%s stop=%.5f planned_risk=%.4f executed=%.2f remaining=%.2f deal=%I64u",
                            (complete_cost ? "cost-known" : "cost-unknown"),
                            EnumToString(exit_reason),
                            admitted_stop_loss,
                            admitted_planned_risk,
                            executed_volume,
                            (double)remaining_after_steps * step,
                            deal));
   SaveState();
   return(true);
  }


bool ReconcileExitDealSequence(const int component,
                               const MqlTick &sampled_tick,
                               const bool sampled_tick_known,
                               const string event_name,
                               const bool require_new_exit,
                               ulong &waited_ms)
  {
   waited_ms = 0;
   if(tracked_position_identifier[component] == 0)
      return(!require_new_exit);
   const ulong position_identifier =
      tracked_position_identifier[component];
   const ulong started = GetTickCount64();
   bool applied_exit = false;
   while(true)
     {
      SequencedExitDeal deals[];
      const int deal_count =
         CollectUnprocessedExitDeals(component,
                                     position_identifier,
                                     deals);
      if(deal_count < 0)
         return(false);
      for(int index = 0; index < deal_count; ++index)
        {
         if(!ApplyExitDeal(component,
                           deals[index].ticket,
                           sampled_tick,
                           sampled_tick_known,
                           event_name))
            return(false);
         applied_exit = true;
        }

      ulong ticket = 0;
      datetime opened_at = 0;
      const int position_count =
         CountOwnedPositions(component, ticket, opened_at);
      if(position_count > 1)
         return(false);
      if(position_count == 0 &&
         tracked_position_identifier[component] == 0 &&
         (!require_new_exit || applied_exit))
        {
         waited_ms = GetTickCount64() - started;
         return(true);
        }
      if(position_count == 1 &&
         tracked_position_identifier[component] == position_identifier &&
         PositionSelectByTicket(ticket) &&
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) ==
         position_identifier)
        {
         long broker_steps = 0;
         long local_steps = 0;
         if(VolumeToSteps(COMPONENT_SYMBOLS[component],
                          PositionGetDouble(POSITION_VOLUME),
                          broker_steps) &&
            VolumeToSteps(COMPONENT_SYMBOLS[component],
                          entry_volume[component],
                          local_steps) &&
            broker_steps == local_steps)
           {
            if(require_new_exit && !applied_exit)
              {
               waited_ms = GetTickCount64() - started;
               if(tester_mode ||
                  waited_ms >= COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
                  return(false);
               Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
               continue;
              }
            waited_ms = GetTickCount64() - started;
            return(true);
           }
        }
      waited_ms = GetTickCount64() - started;
      if(tester_mode ||
         waited_ms >= COMPLETED_DEAL_RECONCILIATION_TIMEOUT_MS)
         return(false);
      Sleep(COMPLETED_DEAL_RECONCILIATION_POLL_MS);
     }
   return(false);
  }


bool ReconcileBrokerState(const bool startup)
  {
   if(!AuditPositionOwnership())
     {
      MakeExistingRiskSafe("broker ownership/protection audit failed");
      return(false);
     }
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count > 1)
        {
         broker_mismatch = true;
         EngageSafetyStop("duplicate component position during reconcile");
         return(false);
        }
      if(count == 1)
        {
         if(!PositionSelectByTicket(ticket))
            return(false);
         const ulong identifier =
            (ulong)PositionGetInteger(POSITION_IDENTIFIER);
         if(tracked_position_identifier[component] == 0)
           {
            if(!ReconstructEntryTracking(component, ticket))
               return(false);
           }
         else if(identifier != tracked_position_identifier[component])
           {
            broker_mismatch = true;
            EngageSafetyStop("broker position identity differs from local state");
            return(false);
           }
         else
           {
            long broker_steps = 0;
            long local_steps = 0;
            if(!VolumeToSteps(COMPONENT_SYMBOLS[component],
                              PositionGetDouble(POSITION_VOLUME),
                              broker_steps) ||
               !VolumeToSteps(COMPONENT_SYMBOLS[component],
                              entry_volume[component],
                              local_steps) || broker_steps > local_steps)
              {
               broker_mismatch = true;
               EngageSafetyStop("broker position volume exceeds local lifecycle");
               return(false);
              }
            if(broker_steps < local_steps)
              {
               MqlTick empty_tick = {};
               ulong waited_ms = 0;
               if(!ReconcileExitDealSequence(component,
                                             empty_tick,
                                             false,
                                             (startup ? "RECOVER_PARTIAL" :
                                                        "EXTERNAL_PARTIAL"),
                                             false,
                                             waited_ms))
                 {
                  broker_mismatch = true;
                  EngageSafetyStop("partial exit deals do not match broker volume");
                  return(false);
                 }
               if(tracked_position_identifier[component] == 0)
                  continue;
               ticket = 0;
               opened_at = 0;
               if(CountOwnedPositions(component, ticket, opened_at) != 1 ||
                  !PositionSelectByTicket(ticket) ||
                  (ulong)PositionGetInteger(POSITION_IDENTIFIER) !=
                  tracked_position_identifier[component])
                 {
                  broker_mismatch = true;
                  EngageSafetyStop("position changed after partial reduction");
                  return(false);
                 }
              }
           }
         const datetime bar = BarForTime(component, opened_at);
         if(bar > last_decision_bar[component])
            last_decision_bar[component] = bar;
         continue;
        }
      if(tracked_position_identifier[component] == 0)
         continue;
      MqlTick empty_tick = {};
      ulong waited_ms = 0;
      if(!ReconcileExitDealSequence(component,
                                    empty_tick,
                                    false,
                                    (startup ? "RECOVER_CLOSE" :
                                               "EXTERNAL_CLOSE"),
                                    false,
                                    waited_ms))
        {
         broker_mismatch = true;
         EngageSafetyStop("local open lifecycle has no complete exit sequence");
         return(false);
        }
     }
   if(!ReconcilePassivePendingOrder())
      return(false);
   last_reconcile_server = TimeCurrent();
   pending_reconcile = false;
   return(true);
  }


void UpdateAccountRisk()
  {
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > account_peak_equity)
      account_peak_equity = equity;
   if(account_peak_equity <= 0.0)
      return;
   const double drawdown = account_peak_equity - equity;
   if(drawdown > account_maximum_drawdown)
      account_maximum_drawdown = drawdown;
  }


bool ContractSpecificationsCompatible()
  {
   for(int index = 0; index < 3; ++index)
     {
      const string symbol =
         (index == 0 ? "US100" : (index == 1 ? "US30" : "US500"));
      if(!SymbolSelect(symbol, true))
         return(false);
      const ENUM_SYMBOL_TRADE_EXECUTION execution_mode =
         (ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(
            symbol, SYMBOL_TRADE_EXEMODE);
      if(execution_mode != SYMBOL_TRADE_EXECUTION_MARKET)
        {
         PrintFormat("%s requires market execution symbol=%s actual=%d",
                     EXECUTION_VERSION,
                     symbol,
                     (int)execution_mode);
         return(false);
        }
      if(
         MathAbs(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN) - 0.01) >
         1.0e-9 ||
         MathAbs(SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP) - 0.01) >
         1.0e-9 ||
          MathAbs(SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE) - 1.0) >
          1.0e-9 ||
          SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT) != "USD" ||
          SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE) <= 0.0 ||
          SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE) <= 0.0 ||
          (SymbolInfoInteger(symbol, SYMBOL_ORDER_MODE) & SYMBOL_ORDER_SL) == 0)
         return(false);
      if(symbol == "US100" &&
         (SymbolInfoInteger(symbol, SYMBOL_EXPIRATION_MODE) &
          SYMBOL_EXPIRATION_SPECIFIED) == 0)
         return(false);
     }
   PrintFormat("%s contract execution=MARKET deviation_field=%d",
               EXECUTION_VERSION,
               InpDeviationPoints);
   return(true);
  }


bool ConnectedEnvironmentCompatible()
  {
   if(!TerminalInfoInteger(TERMINAL_CONNECTED) ||
      AccountInfoString(ACCOUNT_SERVER) != "FPMarketsSC-Live" ||
      AccountInfoString(ACCOUNT_CURRENCY) != "USD" ||
      AccountInfoInteger(ACCOUNT_LEVERAGE) != 100 ||
      AccountInfoInteger(ACCOUNT_MARGIN_MODE) !=
      ACCOUNT_MARGIN_MODE_RETAIL_HEDGING ||
       (!tester_mode && AccountInfoInteger(ACCOUNT_TRADE_MODE) !=
        ACCOUNT_TRADE_MODE_REAL) ||
       (!tester_mode && InpAllowNewEntries &&
        (InpExpectedLiveAccountLogin <= 0 ||
         (long)AccountInfoInteger(ACCOUNT_LOGIN) !=
         InpExpectedLiveAccountLogin)) ||
       !ContractSpecificationsCompatible())
      return(false);
   return(true);
  }


bool OpenComponent(const int component,
                   const int direction,
                   const double feature)
  {
   if(direction == 0 || !NewEntriesOperationallyAllowed())
     {
      entry_check_result[component] = "ENTRY_BLOCKED";
      return(false);
     }
   if(!AuditPositionOwnership() || foreign_exposure)
     {
      entry_check_result[component] = "OWNERSHIP_BLOCKED";
      return(false);
     }
   ulong existing_ticket = 0;
   datetime existing_opened_at = 0;
   if(CountOwnedPositions(component,
                          existing_ticket,
                          existing_opened_at) != 0)
     {
      entry_check_result[component] = "EXISTING_EXPOSURE";
      return(false);
     }
   const string symbol = COMPONENT_SYMBOLS[component];
   const double volume = NormalizedVolume(symbol);
   if(volume <= 0.0)
     {
      entry_check_result[component] = "VOLUME_INVALID";
      return(false);
     }
   entry_check_volume[component] = volume;
   MqlTick tick = {};
   if(!ExecutableTick(symbol, tick))
     {
      entry_check_result[component] = "QUOTE_UNAVAILABLE";
      return(false);
     }
   const double entry_price = (direction > 0 ? tick.ask : tick.bid);
   entry_check_order_price[component] = entry_price;
   const double base_protection_distance = MinimumProtectionDistance(symbol);
   const double minimum_protection_distance =
      (direction > 0
       ? entry_price - (tick.bid - base_protection_distance)
       : (tick.ask + base_protection_distance) - entry_price);
   double stop_loss = 0.0;
   double admitted_planned_risk = 0.0;
   if(!CalculateProtectiveStop(component,
                               symbol,
                               direction,
                               volume,
                               entry_price,
                               minimum_protection_distance,
                               stop_loss,
                               admitted_planned_risk))
     {
      entry_check_result[component] = "PROTECTION_OR_RISK_BLOCKED";
      SaveState();
      return(false);
     }
   entry_check_stop_loss[component] = stop_loss;
   entry_check_planned_risk_usd[component] = admitted_planned_risk;
   const double admitted_capital = ConservativeRiskCapital();
   const double aggregate_before = TrackedAggregatePlannedRisk();
   if(!TradeSessionAllows(symbol, TimeCurrent(), true))
     {
      entry_check_result[component] = "TRADE_SESSION_BLOCKED";
      return(false);
     }
   if(!MarginAllows(symbol, direction, volume))
     {
      entry_check_result[component] = "MARGIN_BLOCKED";
      return(false);
     }
   trade.SetExpertMagicNumber(COMPONENT_MAGICS[component]);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(symbol);
   trade.SetMarginMode();
   trade.SetAsyncMode(false);
   const string comment = "ZT " + IntegerToString(component + 1) + " P5FR5";
   if(!MarkDecisionOrderAttempted(component,
                                  direction,
                                  feature,
                                  "MARKET_OPEN"))
     {
      entry_check_result[component] = "PERSISTENCE_FAILED";
      return(false);
     }
   trade_operation_active = true;
   const bool requested =
      (direction > 0
       ? trade.Buy(volume, symbol, 0.0, stop_loss, 0.0, comment)
       : trade.Sell(volume, symbol, 0.0, stop_loss, 0.0, comment));
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   const double returned_entry_volume = trade.ResultVolume();
   const double returned_entry_price = trade.ResultPrice();
   const ulong entry_order = trade.ResultOrder();
   const ulong returned_entry_deal = trade.ResultDeal();
   trade_operation_active = false;
   if(!requested || !IsCompletedMarketTradeRetcode(retcode))
     {
      entry_check_result[component] = "BROKER_REJECTED";
      RecordEvent(component,
                  "OPEN_FAIL",
                  (double)retcode,
                  feature,
                  retcode_description);
      SaveState();
      return(false);
     }
   ulong position_ticket = 0;
   datetime opened_at = 0;
   if(!WaitForSingleOwnedPosition(component, position_ticket, opened_at))
     {
      entry_check_result[component] = "SAFETY_STOP";
      broker_mismatch = true;
      EngageSafetyStop("entry position unavailable after bounded reconciliation");
      pending_reconcile = true;
      MakeExistingRiskSafe("entry broker state mismatch");
      return(true);
     }
   if(!PositionSelectByTicket(position_ticket))
     {
      entry_check_result[component] = "SAFETY_STOP";
      broker_mismatch = true;
      EngageSafetyStop("entry position identity unavailable after bounded reconciliation");
      pending_reconcile = true;
      MakeExistingRiskSafe("entry position identity unavailable");
      return(true);
     }
   const ulong expected_position_identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   EntryDealAggregate entry_aggregate = {};
   ulong entry_deal_wait_ms = 0;
   long requested_steps = 0;
   if(expected_position_identifier == 0 ||
      !VolumeToSteps(symbol, volume, requested_steps) ||
      !WaitForEntryDealAggregation(component,
                                   expected_position_identifier,
                                   tick,
                                   requested_steps,
                                   retcode == TRADE_RETCODE_DONE_PARTIAL,
                                   entry_aggregate,
                                   entry_deal_wait_ms))
     {
      entry_check_result[component] = "SAFETY_STOP";
      broker_mismatch = true;
      EngageSafetyStop("entry deal sequence unavailable after bounded reconciliation");
      pending_reconcile = true;
      MakeExistingRiskSafe("entry deal sequence unavailable");
      return(true);
     }
   if(!PositionSelectByTicket(position_ticket))
     {
      entry_check_result[component] = "SAFETY_STOP";
      broker_mismatch = true;
      EngageSafetyStop("authoritative entry state became unavailable");
      pending_reconcile = true;
      MakeExistingRiskSafe("authoritative entry state unavailable");
      return(true);
     }

   const ulong published_entry_order = entry_aggregate.order_ticket;
   const ulong entry_deal = entry_aggregate.first_deal;
   const double deal_volume = entry_aggregate.volume;
   const double deal_price = entry_aggregate.price;
   const ulong position_identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   const ulong position_magic =
      (ulong)PositionGetInteger(POSITION_MAGIC);
   const string position_symbol = PositionGetString(POSITION_SYMBOL);
   const ENUM_POSITION_TYPE position_type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const double position_volume = PositionGetDouble(POSITION_VOLUME);
   const double position_open_price =
      PositionGetDouble(POSITION_PRICE_OPEN);
   const double broker_stop_loss = PositionGetDouble(POSITION_SL);
   const double volume_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   long position_steps = 0;
   const bool deal_direction_matches =
      (entry_aggregate.direction == direction);
   const bool position_direction_matches =
      (direction > 0 ? position_type == POSITION_TYPE_BUY :
                       position_type == POSITION_TYPE_SELL);
   const bool execution_identity_valid =
      published_entry_order > 0 &&
      position_identifier > 0 &&
      position_identifier == expected_position_identifier &&
      position_magic == COMPONENT_MAGICS[component] &&
      position_symbol == symbol &&
      deal_direction_matches &&
      position_direction_matches &&
      volume_step > 0.0 && deal_volume > 0.0 &&
      position_volume > 0.0 && deal_price > 0.0 &&
      position_open_price > 0.0 &&
      entry_aggregate.cost_known &&
      VolumeToSteps(symbol, position_volume, position_steps) &&
      entry_aggregate.volume_steps == position_steps &&
      position_steps <= requested_steps;

   // Seed the lifecycle from broker-owned position/deal state before any
   // fail-closed action so a protective close can still be reconciled.
   tracked_position_identifier[component] = position_identifier;
   entry_time_server[component] = entry_aggregate.first_time_server;
   entry_direction[component] = direction;
   entry_volume[component] = position_volume;
   entry_feature[component] = feature;
   entry_stop_loss[component] = broker_stop_loss;
   entry_planned_risk_usd[component] = admitted_planned_risk;
   entry_spread_price[component] = entry_aggregate.spread_price;
   entry_transaction_cost[component] =
      entry_aggregate.transaction_cost;
   entry_adverse_slippage[component] =
      entry_aggregate.adverse_slippage;
   entry_cost_known[component] = entry_aggregate.cost_known;

   if(!execution_identity_valid)
     {
      entry_check_result[component] = "SAFETY_STOP";
      broker_mismatch = true;
      RecordEvent(component,
                  "OPEN_EXECUTION_MISMATCH",
                  deal_price,
                  position_volume,
                  StringFormat("result_order=%I64u published_order=%I64u result_deal=%I64u first_deal=%I64u last_deal=%I64u entry_deals=%d result_price=%.5f result_volume=%.2f requested_steps=%I64d position_steps=%I64d broker_position=%I64u magic=%I64u symbol=%s aggregate_direction=%d position_type=%d",
                               entry_order,
                               published_entry_order,
                               returned_entry_deal,
                               entry_deal,
                               entry_aggregate.last_deal,
                               entry_aggregate.deal_count,
                               returned_entry_price,
                               returned_entry_volume,
                               requested_steps,
                               position_steps,
                               position_identifier,
                               position_magic,
                               position_symbol,
                               entry_aggregate.direction,
                               (int)position_type));
      EngageSafetyStop("authoritative entry execution identity mismatch");
      pending_reconcile = true;
      CloseComponent(component, position_ticket);
      return(true);
     }

   double actual_planned_risk = 0.0;
   const double protection_tolerance =
      MathMax(0.01, admitted_planned_risk * 0.01);
   const double tick_size =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const bool stop_present = broker_stop_loss > 0.0;
   const bool stop_direction_valid =
      (direction > 0 ? broker_stop_loss < position_open_price :
                       broker_stop_loss > position_open_price);
   const bool stop_matches_request =
      tick_size > 0.0 &&
      MathAbs(broker_stop_loss - stop_loss) <=
      0.5 * tick_size + 1.0e-9;
   const bool risk_known =
      BufferedPlannedRisk(symbol,
                          direction,
                          position_volume,
                          position_open_price,
                          broker_stop_loss,
                          actual_planned_risk);
   const bool position_risk_within_cap =
      risk_known &&
      actual_planned_risk <=
      admitted_capital * InpMaximumPositionRiskFraction +
      protection_tolerance;
   const bool aggregate_risk_within_cap =
      risk_known &&
      aggregate_before + actual_planned_risk <=
      admitted_capital * InpMaximumAggregateRiskFraction +
      protection_tolerance;
   const bool protection_valid =
      stop_present && stop_direction_valid && stop_matches_request &&
      position_risk_within_cap && aggregate_risk_within_cap;
   if(!protection_valid)
     {
      entry_check_result[component] = "SAFETY_STOP";
      ++protection_mismatches;
      broker_mismatch = true;
      RecordEvent(component,
                  "OPEN_PROTECTION_MISMATCH",
                  entry_stop_loss[component],
                  entry_planned_risk_usd[component],
                  StringFormat("deal_price=%.5f position_open=%.5f result_price=%.5f broker_stop=%.5f requested_stop=%.5f actual_risk=%.4f admitted_risk=%.4f aggregate_before=%.4f stop_present=%d stop_direction=%d stop_exact=%d risk_known=%d position_cap=%d aggregate_cap=%d",
                               deal_price,
                               position_open_price,
                               returned_entry_price,
                               broker_stop_loss,
                               stop_loss,
                               actual_planned_risk,
                               admitted_planned_risk,
                               aggregate_before,
                               (int)stop_present,
                               (int)stop_direction_valid,
                               (int)stop_matches_request,
                               (int)risk_known,
                               (int)position_risk_within_cap,
                               (int)aggregate_risk_within_cap));
      EngageSafetyStop("market entry protection not confirmed");
      CloseComponent(component, position_ticket);
      return(true);
     }
   if(!MarkDecisionBrokerStateAdopted(component,
                                      position_identifier,
                                      "POSITION_ADOPTED"))
     {
      entry_check_result[component] = "SAFETY_STOP";
      EngageSafetyStop("adopted position journal could not be persisted");
      CloseComponent(component, position_ticket);
      return(true);
     }
   entry_check_result[component] = "POSITION_OPEN";
   RecordEvent(component,
               "OPEN",
               deal_price,
               position_volume,
               StringFormat("feature=%.8f position_open=%.5f result_price=%.5f result_volume=%.2f filled_volume=%.2f entry_deals=%d stop=%.5f planned_risk=%.4f deal_wait_ms=%I64u order=%I64u first_deal=%I64u last_deal=%I64u",
                            feature,
                            position_open_price,
                            returned_entry_price,
                            returned_entry_volume,
                            position_volume,
                            entry_aggregate.deal_count,
                            entry_stop_loss[component],
                            entry_planned_risk_usd[component],
                            entry_deal_wait_ms,
                            published_entry_order,
                            entry_deal,
                            entry_aggregate.last_deal));
   if(!SaveState())
      EngageSafetyStop("entry state could not be persisted");
   return(true);
  }


bool CloseComponent(const int component, const ulong ticket)
  {
   const datetime now = TimeCurrent();
   if(last_close_attempt_server[component] > 0 &&
      now - last_close_attempt_server[component] < 60)
      return(false);
   if(!PositionSelectByTicket(ticket))
      return(false);
   const string symbol = PositionGetString(POSITION_SYMBOL);
   if(!TradeSessionAllows(symbol, now, false))
     {
      last_close_attempt_server[component] = now;
      return(false);
     }
   MqlTick tick = {};
   if(!StructurallyValidTick(symbol, tick))
      return(false);
   const double tick_age_seconds =
      MathAbs((double)((long)TimeCurrent() - (long)tick.time));
   const bool sampled_tick_known =
      (tick_age_seconds <= MAX_EXECUTABLE_TICK_AGE_SECONDS);
   last_close_attempt_server[component] = now;
   trade.SetExpertMagicNumber(COMPONENT_MAGICS[component]);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(symbol);
   trade.SetAsyncMode(false);
   trade_operation_active = true;
   const bool requested = trade.PositionClose(ticket, InpDeviationPoints);
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   const ulong close_order = trade.ResultOrder();
   const ulong returned_close_deal = trade.ResultDeal();
   trade_operation_active = false;
   if((!requested || !IsCompletedMarketTradeRetcode(retcode)) &&
      retcode == TRADE_RETCODE_POSITION_CLOSED &&
      !PositionSelectByTicket(ticket))
     {
      MqlTick empty_tick = {};
      ulong waited_ms = 0;
      if(ReconcileExitDealSequence(component,
                                   empty_tick,
                                   false,
                                   "CLOSE_RACE",
                                   true,
                                   waited_ms))
         return(true);
      pending_reconcile = true;
      RecordEvent(component,
                  "CLOSE_RACE_PENDING",
                  (double)retcode,
                  (double)ticket,
                  retcode_description);
      SaveState();
      return(true);
     }
   if(!requested || !IsCompletedMarketTradeRetcode(retcode))
     {
      RecordEvent(component,
                   "CLOSE_FAIL",
                   (double)retcode,
                   0.0,
                   retcode_description);
      SaveState();
      return(false);
     }

   ulong close_deal_wait_ms = 0;
   if(!ReconcileExitDealSequence(component,
                                 tick,
                                 sampled_tick_known,
                                 "CLOSE",
                                 true,
                                 close_deal_wait_ms))
     {
      broker_mismatch = true;
      EngageSafetyStop("close deal sequence unavailable after bounded reconciliation");
      pending_reconcile = true;
      return(false);
     }
   if(close_deal_wait_ms > 0)
      PrintFormat("%s close deals reconciled after %I64u ms component=%s result_order=%I64u result_deal=%I64u remaining=%.2f",
                  EXECUTION_VERSION,
                  close_deal_wait_ms,
                  COMPONENT_IDS[component],
                  close_order,
                  returned_close_deal,
                  entry_volume[component]);
   return(true);
  }


void MakeExistingRiskSafe(const string reason)
  {
   for(int index = OrdersTotal() - 1; index >= 0; --index)
     {
      const ulong order_ticket = OrderGetTicket(index);
      if(order_ticket == 0 ||
         (ulong)OrderGetInteger(ORDER_MAGIC) !=
         MAGIC_US100_PASSIVE_LIMIT)
         continue;
      CancelPassivePendingOrder(order_ticket, reason);
     }
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong position_ticket = PositionGetTicket(index);
      if(position_ticket == 0)
         continue;
      const int component =
         ComponentForMagic((ulong)PositionGetInteger(POSITION_MAGIC),
                           PositionGetString(POSITION_SYMBOL));
      if(component >= 0)
         CloseComponent(component, position_ticket);
     }
  }



void ProcessClosures()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(component == US100_PASSIVE_LIMIT)
         continue;
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count > 1)
        {
         EngageSafetyStop("duplicate component position during close");
         continue;
        }
      if(count != 1)
         continue;
      const int held_bars =
         iBarShift(COMPONENT_SYMBOLS[component],
                   COMPONENT_TIMEFRAMES[component],
                   opened_at,
                   false);
      if(held_bars >= COMPONENT_HOLD_BARS[component])
         CloseComponent(component, ticket);
     }
  }


double Median(double &values[])
  {
   const int count = ArraySize(values);
   if(count <= 0)
      return(0.0);
   ArraySort(values);
   if((count % 2) == 1)
      return(values[count / 2]);
   return(0.5 * (values[count / 2 - 1] + values[count / 2]));
  }


double WindowLogRange(const double &highs[],
                      const double &lows[],
                      const int start,
                      const int count)
  {
   double maximum = highs[start];
   double minimum = lows[start];
   for(int offset = 1; offset < count; ++offset)
     {
      maximum = MathMax(maximum, highs[start + offset]);
      minimum = MathMin(minimum, lows[start + offset]);
     }
   if(maximum <= 0.0 || minimum <= 0.0 || maximum < minimum)
      return(0.0);
   return(MathLog(maximum / minimum));
  }


bool CalculateRangeCompression(const string symbol,
                               const int compression_window,
                               double &signed_tightness)
  {
   const int normal_window = 96;
   const int direction_lookback = MathMax(1, compression_window / 2);
   const int bar_count = normal_window + compression_window;
   double highs[];
   double lows[];
   double closes[];
   if(CopyHigh(symbol, PERIOD_M30, 1, bar_count, highs) != bar_count ||
      CopyLow(symbol, PERIOD_M30, 1, bar_count, lows) != bar_count ||
      CopyClose(symbol, PERIOD_M30, 1, bar_count, closes) != bar_count)
      return(false);
   double prior_ranges[];
   ArrayResize(prior_ranges, normal_window);
   for(int sample = 0; sample < normal_window; ++sample)
     {
      prior_ranges[sample] =
         WindowLogRange(highs, lows, sample, compression_window);
      if(prior_ranges[sample] <= 0.0)
         return(false);
     }
   const double normal_range = Median(prior_ranges);
   const double current_range =
      WindowLogRange(highs, lows, normal_window, compression_window);
   const int latest = bar_count - 1;
   const int earlier = latest - direction_lookback;
   if(normal_range <= 0.0 || current_range <= 0.0 ||
      closes[latest] <= 0.0 || closes[earlier] <= 0.0)
      return(false);
   const double direction_return =
      MathLog(closes[latest] / closes[earlier]);
   if(direction_return == 0.0)
     {
      signed_tightness = 0.0;
      return(true);
     }
   signed_tightness =
      (direction_return > 0.0 ? 1.0 : -1.0) /
      (current_range / normal_range);
   return(MathIsValidNumber(signed_tightness));
  }


bool CopySynchronizedCloses(const string symbol,
                            const int count,
                            const datetime expected_latest,
                            double &closes[])
  {
   if(iTime(symbol, PERIOD_H1, 1) != expected_latest)
      return(false);
   return(CopyClose(symbol, PERIOD_H1, 1, count, closes) == count);
  }


bool CalculateUS100RelativeMomentum(double &zscore)
  {
   const int scale_window = 120;
   const int count = scale_window + 2;
   const datetime expected = iTime("US100", PERIOD_H1, 1);
   if(expected == 0)
      return(false);
   double own[];
   double peer_a[];
   double peer_b[];
   if(!CopySynchronizedCloses("US100", count, expected, own) ||
      !CopySynchronizedCloses("US30", count, expected, peer_a) ||
      !CopySynchronizedCloses("US500", count, expected, peer_b))
      return(false);
   double relative[];
   ArrayResize(relative, scale_window + 1);
   for(int sample = 0; sample <= scale_window; ++sample)
     {
      if(own[sample] <= 0.0 || own[sample + 1] <= 0.0 ||
         peer_a[sample] <= 0.0 || peer_a[sample + 1] <= 0.0 ||
         peer_b[sample] <= 0.0 || peer_b[sample + 1] <= 0.0)
         return(false);
      relative[sample] =
         MathLog(own[sample + 1] / own[sample]) -
         0.5 * (MathLog(peer_a[sample + 1] / peer_a[sample]) +
                MathLog(peer_b[sample + 1] / peer_b[sample]));
     }
   double mean = 0.0;
   for(int sample = 0; sample < scale_window; ++sample)
      mean += relative[sample];
   mean /= scale_window;
   double squared = 0.0;
   for(int sample = 0; sample < scale_window; ++sample)
     {
      const double deviation = relative[sample] - mean;
      squared += deviation * deviation;
     }
   const double standard_deviation =
      MathSqrt(squared / (scale_window - 1));
   if(standard_deviation <= 0.0)
      return(false);
   zscore = relative[scale_window] / standard_deviation;
   return(MathIsValidNumber(zscore));
  }


bool CalculateIntradayRangePressure(const string symbol, double &pressure)
  {
   const datetime day_start = ServerMidnight();
   const datetime current_bar = iTime(symbol, PERIOD_M30, 0);
   if(day_start <= 0 || current_bar <= day_start)
      return(false);
   MqlRates recent[];
   const int copied = CopyRates(symbol, PERIOD_M30, 1, 64, recent);
   if(copied <= 0)
      return(false);
   bool found = false;
   double session_open = 0.0;
   double running_high = 0.0;
   double running_low = 0.0;
   double latest_close = 0.0;
   for(int index = 0; index < copied; ++index)
     {
      if(recent[index].time < day_start ||
         recent[index].time >= current_bar)
         continue;
      if(!found)
        {
         session_open = recent[index].open;
         running_high = recent[index].high;
         running_low = recent[index].low;
         found = true;
        }
      else
        {
         running_high = MathMax(running_high, recent[index].high);
         running_low = MathMin(running_low, recent[index].low);
        }
      latest_close = recent[index].close;
     }
   if(!found || session_open <= 0.0 || latest_close <= 0.0 ||
      running_high <= running_low || running_low <= 0.0)
      return(false);
   double daily_highs[];
   double daily_lows[];
   const int daily_count = 20;
   if(CopyHigh(symbol, PERIOD_D1, 1, daily_count, daily_highs) != daily_count ||
      CopyLow(symbol, PERIOD_D1, 1, daily_count, daily_lows) != daily_count)
      return(false);
   double daily_ranges[];
   ArrayResize(daily_ranges, daily_count);
   for(int index = 0; index < daily_count; ++index)
     {
      if(daily_highs[index] <= daily_lows[index] || daily_lows[index] <= 0.0)
         return(false);
      daily_ranges[index] = MathLog(daily_highs[index] / daily_lows[index]);
     }
   const double range_scale = Median(daily_ranges);
   const double running_log_range = MathLog(running_high / running_low);
   if(range_scale <= 0.0 || running_log_range <= 0.0)
      return(false);
   const double range_location =
      2.0 * ((latest_close - running_low) /
             (running_high - running_low) - 0.5);
   pressure = range_location * (running_log_range / range_scale);
   return(MathIsValidNumber(pressure));
  }


void ClearArcLifecycleState()
  {
   arc_lifecycle_identifier = 0;
   arc_last_attempt_bar = 0;
   arc_checkpoint_evaluated = false;
   arc_lifecycle_compressed = false;
   arc_original_stop_loss = 0.0;
   arc_modify_pending = false;
   arc_pending_stop_loss = 0.0;
   arc_modify_retry_pending = false;
   arc_modify_retry_consumed = false;
   arc_modify_retry_after_msc = 0;
   arc_modify_retry_initial_retcode = 0;
  }


void ClearRC4ShadowState()
  {
   rc4_shadow_occupied = false;
   rc4_shadow_source_identifier = 0;
   rc4_shadow_entry_time = 0;
   rc4_shadow_direction = 0;
   rc4_shadow_original_stop_loss = 0.0;
   rc4_shadow_last_observed_msc = 0;
   rc4_shadow_cursor_ordinal = 0;
   rc4_shadow_catchup_required = false;
   rc4_shadow_catchup_failure_logged = false;
   rc4_shadow_cursor_checkpoint_observation_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
   rc4_shadow_cursor_checkpoint_pending = false;
   rc4_shadow_activation_sealed = false;
   rc4_shadow_activation_seal_pending = false;
   rc4_shadow_activation_seal_failure_logged = false;
   rc4_shadow_activation_deal_ticket = 0;
   rc4_shadow_activation_deal_time_msc = 0;
   rc4_shadow_activation_deal_price = 0.0;
   rc4_shadow_activation_deal_reason = 0;
   rc4_shadow_activation_protected_stop = 0.0;
   rc4_shadow_activation_sampled_tick_known = false;
   rc4_shadow_activation_sampled_time = 0;
   rc4_shadow_activation_sampled_time_msc = 0;
   rc4_shadow_activation_sampled_bid = 0.0;
   rc4_shadow_activation_sampled_ask = 0.0;
   rc4_shadow_activation_sampled_last = 0.0;
   rc4_shadow_activation_sampled_volume = 0;
   rc4_shadow_activation_sampled_volume_real = 0.0;
   rc4_shadow_activation_sampled_flags = 0;
   rc4_shadow_activation_boundary_msc = 0;
   rc4_shadow_activation_boundary_ordinal = 0;
  }


bool ArcOriginalStopReached(const int direction,
                            const double original_stop,
                            const MqlTick &tick)
  {
   if(MathAbs(direction) != 1 || original_stop <= 0.0 ||
      tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid)
      return(false);
   return(direction > 0
          ? tick.bid <= original_stop
          : tick.ask >= original_stop);
  }


bool SameRC4ShadowTick(const MqlTick &left,
                       const MqlTick &right)
  {
   return(left.time == right.time &&
          left.time_msc == right.time_msc &&
          left.bid == right.bid && left.ask == right.ask &&
          left.last == right.last && left.volume == right.volume &&
          left.volume_real == right.volume_real &&
          left.flags == right.flags);
  }


bool CatchUpRC4ShadowToTick(const MqlTick &current_tick,
                            bool &stop_release,
                            long &stop_time_msc)
  {
   stop_release = false;
   stop_time_msc = 0;
   const bool recovery_pending_before = rc4_shadow_catchup_required;
   const long from_msc = rc4_shadow_last_observed_msc;
   const long from_ordinal = rc4_shadow_cursor_ordinal;
   if(!rc4_shadow_occupied || !rc4_shadow_activation_sealed ||
      rc4_shadow_activation_seal_pending ||
      rc4_shadow_activation_boundary_msc <= 0 ||
      rc4_shadow_activation_boundary_ordinal <= 0 ||
      from_msc <= 0 || from_ordinal < 0 ||
      current_tick.time_msc <= 0 || current_tick.time_msc < from_msc)
     {
      rc4_shadow_catchup_required = true;
      ++rc4_shadow_catchup_failures;
      if(!rc4_shadow_catchup_failure_logged)
        {
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_CATCHUP_FAILED",
                     (double)from_msc,
                     (double)current_tick.time_msc,
                     "invalid causal shadow tick range or ordinal");
         rc4_shadow_catchup_failure_logged = true;
        }
      return(false);
     }

   MqlTick ticks[];
   ResetLastError();
   const int copied =
      CopyTicksRange("US30",
                     ticks,
                     COPY_TICKS_ALL,
                     (ulong)from_msc,
                     (ulong)current_tick.time_msc);
   const int history_error = GetLastError();
   if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
     {
      rc4_shadow_catchup_required = true;
      ++rc4_shadow_catchup_failures;
      if(!rc4_shadow_catchup_failure_logged)
        {
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_CATCHUP_FAILED",
                     (double)from_msc,
                     (double)current_tick.time_msc,
                     StringFormat("incomplete CopyTicksRange copied=%d size=%d error=%d",
                                  copied,
                                  ArraySize(ticks),
                                  history_error));
         rc4_shadow_catchup_failure_logged = true;
        }
      return(false);
     }

   long prior_time_msc = from_msc;
   long seen_at_cursor = 0;
   long same_millisecond_ordinal = 0;
   long ordinal_millisecond = -1;
   long selected_ordinal = 0;
   int selected_index = -1;
   long processed_ticks = 0;
   for(int index = 0; index < copied; ++index)
     {
      const MqlTick recovered = ticks[index];
      if(recovered.time_msc < from_msc ||
         recovered.time_msc < prior_time_msc ||
         recovered.time_msc > current_tick.time_msc ||
         recovered.bid <= 0.0 || recovered.ask <= 0.0 ||
         recovered.ask < recovered.bid)
        {
         rc4_shadow_catchup_required = true;
         ++rc4_shadow_catchup_failures;
         if(!rc4_shadow_catchup_failure_logged)
           {
            RecordEvent(RC4_BOTH,
                        "ARC_SHADOW_CATCHUP_FAILED",
                        (double)recovered.time_msc,
                        (double)current_tick.time_msc,
                        "invalid or noncausal recovered tick");
            rc4_shadow_catchup_failure_logged = true;
           }
         return(false);
        }
      prior_time_msc = recovered.time_msc;
      if(recovered.time_msc != ordinal_millisecond)
        {
         ordinal_millisecond = recovered.time_msc;
         same_millisecond_ordinal = 1;
        }
      else
         ++same_millisecond_ordinal;
      if(recovered.time_msc == from_msc)
         ++seen_at_cursor;
      else if(seen_at_cursor < from_ordinal)
        {
         rc4_shadow_catchup_required = true;
         ++rc4_shadow_catchup_failures;
         if(!rc4_shadow_catchup_failure_logged)
           {
            RecordEvent(RC4_BOTH,
                        "ARC_SHADOW_CATCHUP_FAILED",
                        (double)seen_at_cursor,
                        (double)from_ordinal,
                        "persisted cursor ordinal is not reproducible");
            rc4_shadow_catchup_failure_logged = true;
           }
         return(false);
        }

      const bool already_observed =
         (recovered.time_msc == from_msc &&
          seen_at_cursor <= from_ordinal);
      if(already_observed)
         continue;
      const bool at_or_before_activation_boundary =
         (recovered.time_msc < rc4_shadow_activation_boundary_msc ||
          (recovered.time_msc == rc4_shadow_activation_boundary_msc &&
           same_millisecond_ordinal <=
              rc4_shadow_activation_boundary_ordinal));
      if(at_or_before_activation_boundary)
        {
         ++rc4_shadow_activation_pre_boundary_consumed;
         rc4_shadow_catchup_required = true;
         ++rc4_shadow_catchup_failures;
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_ACTIVATION_PRE_BOUNDARY_CONSUMPTION",
                     (double)recovered.time_msc,
                     (double)same_millisecond_ordinal,
                     StringFormat("sealed=%I64d/%I64d consumed=%I64d",
                                  rc4_shadow_activation_boundary_msc,
                                  rc4_shadow_activation_boundary_ordinal,
                                  rc4_shadow_activation_pre_boundary_consumed));
         EngageSafetyStop("RC4 shadow scanner crossed its activation boundary");
         return(false);
        }
      const bool ignored_activation_same_millisecond_tail =
         (recovered.time_msc == rc4_shadow_activation_boundary_msc);
      if(ignored_activation_same_millisecond_tail)
        {
         if(SameRC4ShadowTick(recovered, current_tick))
           {
            selected_index = index;
            selected_ordinal = same_millisecond_ordinal;
            break;
           }
         continue;
        }
      ++processed_ticks;
      if(!stop_release &&
         ArcOriginalStopReached(rc4_shadow_direction,
                                rc4_shadow_original_stop_loss,
                                recovered))
        {
         stop_release = true;
         stop_time_msc = recovered.time_msc;
        }
      if(SameRC4ShadowTick(recovered, current_tick))
        {
         selected_index = index;
         selected_ordinal = same_millisecond_ordinal;
         break;
        }
     }

   if(selected_index < 0 || seen_at_cursor < from_ordinal ||
      selected_ordinal <= 0)
     {
      stop_release = false;
      stop_time_msc = 0;
      rc4_shadow_catchup_required = true;
      ++rc4_shadow_catchup_failures;
      if(!rc4_shadow_catchup_failure_logged)
        {
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_CATCHUP_FAILED",
                     (double)seen_at_cursor,
                     (double)from_ordinal,
                     "current tick boundary or cursor ordinal is incomplete");
         rc4_shadow_catchup_failure_logged = true;
        }
      return(false);
     }

   ++rc4_shadow_catchup_scans;
   rc4_shadow_catchup_ticks += processed_ticks;
   rc4_shadow_last_observed_msc = current_tick.time_msc;
   rc4_shadow_cursor_ordinal = selected_ordinal;
   rc4_shadow_catchup_required = false;
   rc4_shadow_catchup_failure_logged = false;
   if(recovery_pending_before || processed_ticks > 1 || stop_release)
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_GAP_COMPLETE",
                  (double)processed_ticks,
                  (double)stop_time_msc,
                  StringFormat("identifier=%I64u stop_release=%d from=%I64d/%I64d to=%I64d/%I64d",
                               rc4_shadow_source_identifier,
                               (stop_release ? 1 : 0),
                               from_msc,
                               from_ordinal,
                               current_tick.time_msc,
                               selected_ordinal));
   return(true);
  }


bool PersistRC4ShadowCursorCheckpointIfEligible(const long prior_msc,
                                                const long prior_ordinal)
  {
   if(!rc4_shadow_occupied)
      return(true);
   const long observation_bucket =
      rc4_shadow_last_observed_msc / RC4_NATIVE_M30_BUCKET_MSC;
   if(observation_bucket == rc4_shadow_cursor_checkpoint_observation_bucket)
      return(true);
   if(observation_bucket < rc4_shadow_cursor_checkpoint_observation_bucket)
     {
      ++rc4_shadow_cursor_checkpoint_regressions;
      rc4_shadow_cursor_checkpoint_pending = true;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)observation_bucket,
                  (double)rc4_shadow_cursor_checkpoint_observation_bucket,
                  "native M30 observation bucket regressed");
      EngageSafetyStop("RC4 shadow cursor checkpoint bucket regressed");
      return(false);
     }

   const bool cursor_advanced =
      (rc4_shadow_last_observed_msc > prior_msc ||
       (rc4_shadow_last_observed_msc == prior_msc &&
        rc4_shadow_cursor_ordinal > prior_ordinal));
   if(!cursor_advanced)
     {
      ++rc4_shadow_cursor_checkpoint_regressions;
      rc4_shadow_cursor_checkpoint_pending = true;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)prior_msc,
                  (double)rc4_shadow_last_observed_msc,
                  "millisecond-and-ordinal cursor did not advance");
      EngageSafetyStop("RC4 shadow cursor checkpoint did not advance");
      return(false);
     }

   const long completed_bucket = observation_bucket - 1;
   if(rc4_shadow_cursor_checkpoint_last_completed_bucket > 0 &&
      completed_bucket <=
         rc4_shadow_cursor_checkpoint_last_completed_bucket)
     {
      ++rc4_shadow_cursor_checkpoint_duplicate_bucket_failures;
      rc4_shadow_cursor_checkpoint_pending = true;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)completed_bucket,
                  (double)rc4_shadow_cursor_checkpoint_last_completed_bucket,
                  "duplicate or nonmonotone completed M30 bucket");
      EngageSafetyStop("RC4 shadow cursor checkpoint duplicated a native bucket");
      return(false);
     }

   const long previous_observation_bucket =
      rc4_shadow_cursor_checkpoint_observation_bucket;
   const long previous_completed_bucket =
      rc4_shadow_cursor_checkpoint_last_completed_bucket;
   const long previous_persisted_msc =
      rc4_shadow_cursor_checkpoint_last_persisted_msc;
   const long previous_persisted_ordinal =
      rc4_shadow_cursor_checkpoint_last_persisted_ordinal;
   const long expected_msc = rc4_shadow_last_observed_msc;
   const long expected_ordinal = rc4_shadow_cursor_ordinal;
   const long expected_eligible =
      rc4_shadow_cursor_checkpoint_eligible + 1;
   const long expected_persisted =
      rc4_shadow_cursor_checkpoint_persisted + 1;

   rc4_shadow_cursor_checkpoint_observation_bucket = observation_bucket;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = completed_bucket;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = expected_msc;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = expected_ordinal;
   rc4_shadow_cursor_checkpoint_eligible = expected_eligible;
   rc4_shadow_cursor_checkpoint_persisted = expected_persisted;
   rc4_shadow_cursor_checkpoint_pending = false;

   if(!SaveState())
     {
      rc4_shadow_cursor_checkpoint_observation_bucket =
         previous_observation_bucket;
      rc4_shadow_cursor_checkpoint_last_completed_bucket =
         previous_completed_bucket;
      rc4_shadow_cursor_checkpoint_last_persisted_msc =
         previous_persisted_msc;
      rc4_shadow_cursor_checkpoint_last_persisted_ordinal =
         previous_persisted_ordinal;
      rc4_shadow_cursor_checkpoint_persisted = expected_persisted - 1;
      rc4_shadow_cursor_checkpoint_pending = true;
      ++rc4_shadow_cursor_checkpoint_save_failures;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)completed_bucket,
                  (double)expected_msc,
                  "synchronous state save failed");
      EngageSafetyStop("RC4 shadow cursor checkpoint save failed");
      return(false);
     }

   const bool readback_equal =
      (rc4_shadow_last_observed_msc == expected_msc &&
       rc4_shadow_cursor_ordinal == expected_ordinal &&
       rc4_shadow_cursor_checkpoint_observation_bucket ==
          observation_bucket &&
       rc4_shadow_cursor_checkpoint_last_completed_bucket ==
          completed_bucket &&
       rc4_shadow_cursor_checkpoint_last_persisted_msc == expected_msc &&
       rc4_shadow_cursor_checkpoint_last_persisted_ordinal ==
          expected_ordinal &&
       rc4_shadow_cursor_checkpoint_eligible == expected_eligible &&
       rc4_shadow_cursor_checkpoint_persisted == expected_persisted &&
       !rc4_shadow_cursor_checkpoint_pending);
   if(!readback_equal)
     {
      rc4_shadow_cursor_checkpoint_pending = true;
      ++rc4_shadow_cursor_checkpoint_readback_failures;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)completed_bucket,
                  (double)expected_msc,
                  "persisted cursor readback did not match");
      EngageSafetyStop("RC4 shadow cursor checkpoint readback mismatch");
      return(false);
     }

   if(!RecordEvent(RC4_BOTH,
                   "ARC_SHADOW_CURSOR_CHECKPOINT",
                   (double)completed_bucket,
                   (double)expected_msc,
                   StringFormat("identifier=%I64u observation_bucket=%I64d cursor=%I64d/%I64d eligible=%I64d persisted=%I64d",
                                rc4_shadow_source_identifier,
                                observation_bucket,
                                expected_msc,
                                expected_ordinal,
                                expected_eligible,
                                expected_persisted)))
     {
      ++rc4_shadow_cursor_checkpoint_event_failures;
      EngageSafetyStop("RC4 shadow cursor checkpoint event failed");
      return(false);
     }
   return(true);
  }


bool RC4ActivationTickCausalCompatible(const MqlTick &tick)
  {
   if(tick.time_msc != rc4_shadow_activation_deal_time_msc ||
      tick.time <= 0 || tick.bid <= 0.0 || tick.ask <= 0.0 ||
      tick.ask < tick.bid ||
      rc4_shadow_activation_deal_reason != (int)DEAL_REASON_SL ||
      rc4_shadow_activation_deal_price <= 0.0 ||
      rc4_shadow_activation_protected_stop <= 0.0 ||
      MathAbs(rc4_shadow_direction) != 1)
      return(false);
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   if(!MathIsValidNumber(tick_size) || tick_size <= 0.0)
      return(false);
   const double tolerance = MathMax(1.0e-8, 0.5 * tick_size);
   if(rc4_shadow_direction > 0)
      return(tick.bid <=
                rc4_shadow_activation_protected_stop + tolerance &&
             rc4_shadow_activation_deal_price <=
                rc4_shadow_activation_protected_stop + tolerance &&
             rc4_shadow_activation_deal_price <= tick.bid + tolerance);
   return(tick.ask >=
             rc4_shadow_activation_protected_stop - tolerance &&
          rc4_shadow_activation_deal_price >=
             rc4_shadow_activation_protected_stop - tolerance &&
          rc4_shadow_activation_deal_price >= tick.ask - tolerance);
  }


bool ResolveRC4ShadowActivationBoundary(MqlTick &boundary_tick,
                                        long &boundary_ordinal,
                                        bool &sampled_identity_used,
                                        bool &ambiguous,
                                        string &failure_detail)
  {
   ZeroMemory(boundary_tick);
   boundary_ordinal = 0;
   sampled_identity_used = false;
   ambiguous = false;
   failure_detail = "";
   if(!rc4_shadow_occupied || !rc4_shadow_activation_seal_pending ||
      rc4_shadow_activation_deal_ticket == 0 ||
      rc4_shadow_activation_deal_time_msc <= 0)
     {
      failure_detail = "activation seal state is incomplete";
      return(false);
     }
   if(!HistoryDealSelect(rc4_shadow_activation_deal_ticket))
     {
      failure_detail = "exit deal identity is not yet selectable";
      return(false);
     }
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   if(!MathIsValidNumber(tick_size) || tick_size <= 0.0)
     {
      failure_detail = "US30 tick size is unavailable for activation seal";
      return(false);
     }
   const double tolerance = MathMax(1.0e-8, 0.5 * tick_size);
   const long selected_deal_time_msc =
      HistoryDealGetInteger(rc4_shadow_activation_deal_ticket,
                            DEAL_TIME_MSC);
   const double selected_deal_price =
      HistoryDealGetDouble(rc4_shadow_activation_deal_ticket,
                           DEAL_PRICE);
   const ENUM_DEAL_REASON selected_deal_reason =
      (ENUM_DEAL_REASON)HistoryDealGetInteger(
         rc4_shadow_activation_deal_ticket,
         DEAL_REASON);
   const ENUM_DEAL_ENTRY selected_deal_entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(
         rc4_shadow_activation_deal_ticket,
         DEAL_ENTRY);
   const ENUM_DEAL_TYPE selected_deal_type =
      (ENUM_DEAL_TYPE)HistoryDealGetInteger(
         rc4_shadow_activation_deal_ticket,
         DEAL_TYPE);
   const bool selected_direction_matches =
      (rc4_shadow_direction > 0
       ? selected_deal_type == DEAL_TYPE_SELL
       : selected_deal_type == DEAL_TYPE_BUY);
   if(selected_deal_time_msc != rc4_shadow_activation_deal_time_msc ||
      MathAbs(selected_deal_price - rc4_shadow_activation_deal_price) >
         tolerance ||
      (int)selected_deal_reason != rc4_shadow_activation_deal_reason ||
      selected_deal_reason != DEAL_REASON_SL ||
      (selected_deal_entry != DEAL_ENTRY_OUT &&
       selected_deal_entry != DEAL_ENTRY_OUT_BY) ||
      !selected_direction_matches ||
      (ulong)HistoryDealGetInteger(rc4_shadow_activation_deal_ticket,
                                   DEAL_MAGIC) != MAGIC_RC4_BOTH ||
      HistoryDealGetString(rc4_shadow_activation_deal_ticket,
                           DEAL_SYMBOL) != "US30" ||
      (ulong)HistoryDealGetInteger(rc4_shadow_activation_deal_ticket,
                                   DEAL_POSITION_ID) !=
         rc4_shadow_source_identifier)
     {
      failure_detail = "exit deal identity changed or is incompatible";
      return(false);
     }

   MqlTick ticks[];
   ResetLastError();
   const int copied =
      CopyTicksRange("US30",
                     ticks,
                     COPY_TICKS_ALL,
                     (ulong)rc4_shadow_activation_deal_time_msc,
                     (ulong)rc4_shadow_activation_deal_time_msc);
   const int history_error = GetLastError();
   if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
     {
      failure_detail =
         StringFormat("incomplete exact-ms CopyTicksRange copied=%d size=%d error=%d",
                      copied,
                      ArraySize(ticks),
                      history_error);
      return(false);
     }
   for(int index = 0; index < copied; ++index)
     {
      if(ticks[index].time_msc !=
            rc4_shadow_activation_deal_time_msc ||
         ticks[index].time <= 0 || ticks[index].bid <= 0.0 ||
         ticks[index].ask <= 0.0 || ticks[index].ask < ticks[index].bid)
        {
         failure_detail = "invalid exact-ms activation tick sequence";
         return(false);
        }
     }

   MqlTick sampled_tick = {};
   sampled_tick.time = rc4_shadow_activation_sampled_time;
   sampled_tick.time_msc = rc4_shadow_activation_sampled_time_msc;
   sampled_tick.bid = rc4_shadow_activation_sampled_bid;
   sampled_tick.ask = rc4_shadow_activation_sampled_ask;
   sampled_tick.last = rc4_shadow_activation_sampled_last;
   sampled_tick.volume = rc4_shadow_activation_sampled_volume;
   sampled_tick.volume_real = rc4_shadow_activation_sampled_volume_real;
   sampled_tick.flags = rc4_shadow_activation_sampled_flags;
   const bool sampled_candidate =
      (rc4_shadow_activation_sampled_tick_known &&
       sampled_tick.time_msc == rc4_shadow_activation_deal_time_msc &&
       RC4ActivationTickCausalCompatible(sampled_tick));
   int selected_index = -1;
   if(sampled_candidate)
     {
      int sampled_matches = 0;
      for(int index = 0; index < copied; ++index)
         if(SameRC4ShadowTick(ticks[index], sampled_tick) &&
            RC4ActivationTickCausalCompatible(ticks[index]))
           {
            ++sampled_matches;
            selected_index = index;
           }
      if(sampled_matches > 1)
        {
         ambiguous = true;
         failure_detail =
            "sampled full tick identity maps to multiple exact-ms records";
         return(false);
        }
      if(sampled_matches == 0)
        {
         failure_detail =
            "sampled full tick identity is absent from exact-ms records";
         return(false);
        }
      sampled_identity_used = true;
     }
   if(selected_index < 0)
     {
      for(int index = 0; index < copied; ++index)
         if(RC4ActivationTickCausalCompatible(ticks[index]))
           {
            selected_index = index;
            break;
           }
     }
   if(selected_index < 0)
     {
      failure_detail =
         "no causal-compatible exit record exists in the exact deal millisecond";
      return(false);
     }
   boundary_tick = ticks[selected_index];
   boundary_ordinal = (long)selected_index + 1;
   return(boundary_ordinal > 0);
  }


bool ResolveAndPersistRC4ShadowActivationSeal()
  {
   if(!rc4_shadow_occupied)
      return(false);
   if(rc4_shadow_activation_sealed &&
      !rc4_shadow_activation_seal_pending)
      return(true);

   MqlTick boundary_tick = {};
   long boundary_ordinal = 0;
   bool sampled_identity_used = false;
   bool ambiguous = false;
   string failure_detail = "";
   if(!ResolveRC4ShadowActivationBoundary(boundary_tick,
                                          boundary_ordinal,
                                          sampled_identity_used,
                                          ambiguous,
                                          failure_detail))
     {
      rc4_shadow_activation_sealed = false;
      rc4_shadow_activation_seal_pending = true;
      rc4_shadow_last_observed_msc =
         rc4_shadow_activation_deal_time_msc;
      rc4_shadow_cursor_ordinal = 0;
      rc4_shadow_catchup_required = true;
      if(!rc4_shadow_activation_seal_failure_logged)
        {
         ++rc4_shadow_activation_seal_pending_count;
         ++rc4_shadow_activation_seal_failures;
         if(ambiguous)
            ++rc4_shadow_activation_seal_ambiguities;
         rc4_shadow_activation_seal_failure_logged = true;
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_ACTIVATION_SEAL_PENDING",
                     (double)rc4_shadow_activation_deal_time_msc,
                     (double)rc4_shadow_activation_deal_ticket,
                     failure_detail +
                     StringFormat(" deal=%I64u eligible=%I64d sealed=%I64d pending=%I64d save_attempts=%I64d readbacks=%I64d failures=%I64d ambiguities=%I64d pre_boundary_consumed=%I64d",
                                  rc4_shadow_activation_deal_ticket,
                                  rc4_shadow_activation_seal_eligible,
                                  rc4_shadow_activation_seal_sealed,
                                  rc4_shadow_activation_seal_pending_count,
                                  rc4_shadow_activation_seal_save_attempts,
                                  rc4_shadow_activation_seal_readbacks,
                                  rc4_shadow_activation_seal_failures,
                                  rc4_shadow_activation_seal_ambiguities,
                                  rc4_shadow_activation_pre_boundary_consumed));
        }
      ++rc4_shadow_activation_seal_save_attempts;
      ++rc4_shadow_activation_seal_readbacks;
      if(!SaveState())
        {
         --rc4_shadow_activation_seal_readbacks;
         ++rc4_shadow_activation_seal_save_failures;
         EngageSafetyStop("RC4 shadow activation pending state could not be persisted");
        }
      return(false);
     }

   const ulong identifier = rc4_shadow_source_identifier;
   const ulong activation_deal_ticket =
      rc4_shadow_activation_deal_ticket;
   const double original_stop = rc4_shadow_original_stop_loss;
   const int shadow_direction = rc4_shadow_direction;
   const long deal_time_msc = rc4_shadow_activation_deal_time_msc;
   rc4_shadow_activation_sealed = true;
   rc4_shadow_activation_seal_pending = false;
   rc4_shadow_activation_seal_failure_logged = false;
   rc4_shadow_activation_boundary_msc = deal_time_msc;
   rc4_shadow_activation_boundary_ordinal = boundary_ordinal;
   rc4_shadow_last_observed_msc = deal_time_msc;
   rc4_shadow_cursor_ordinal = boundary_ordinal;
   rc4_shadow_catchup_required = true;
   rc4_shadow_catchup_failure_logged = false;
   ++rc4_shadow_activation_seal_sealed;
   rc4_shadow_activation_last_sealed_msc = deal_time_msc;
   rc4_shadow_activation_last_sealed_ordinal = boundary_ordinal;

   const bool original_stop_reached =
      ArcOriginalStopReached(rc4_shadow_direction,
                             rc4_shadow_original_stop_loss,
                             boundary_tick);
   if(original_stop_reached)
      ClearRC4ShadowState();
   else
      ++rc4_shadow_activations;
   ClearArcLifecycleState();

   ++rc4_shadow_activation_seal_save_attempts;
   ++rc4_shadow_activation_seal_readbacks;
   if(!SaveState())
     {
      --rc4_shadow_activation_seal_readbacks;
      ++rc4_shadow_activation_seal_save_failures;
      ++rc4_shadow_activation_seal_failures;
      EngageSafetyStop("RC4 shadow activation seal could not be persisted");
      return(false);
     }
   const bool readback_equal =
      (rc4_shadow_activation_last_sealed_msc == deal_time_msc &&
       rc4_shadow_activation_last_sealed_ordinal == boundary_ordinal &&
       rc4_shadow_activation_pre_boundary_consumed == 0 &&
       (original_stop_reached ||
        (rc4_shadow_occupied && rc4_shadow_activation_sealed &&
         !rc4_shadow_activation_seal_pending &&
         rc4_shadow_activation_boundary_msc == deal_time_msc &&
         rc4_shadow_activation_boundary_ordinal == boundary_ordinal &&
         rc4_shadow_last_observed_msc == deal_time_msc &&
         rc4_shadow_cursor_ordinal == boundary_ordinal)));
   if(!readback_equal)
     {
      ++rc4_shadow_activation_seal_readback_failures;
      ++rc4_shadow_activation_seal_failures;
      EngageSafetyStop("RC4 shadow activation seal readback mismatch");
      return(false);
     }

   RecordEvent(RC4_BOTH,
               (original_stop_reached
                ? "ARC_SHADOW_NOT_REQUIRED"
                : "ARC_SHADOW_ACTIVATION_SEALED"),
               (double)deal_time_msc,
               (double)boundary_ordinal,
               StringFormat("identifier=%I64u deal=%I64u source=%s original_stop=%.5f boundary_side=%.5f eligible=%I64d sealed=%I64d pending=%I64d save_attempts=%I64d save_failures=%I64d readbacks=%I64d readback_failures=%I64d failures=%I64d ambiguities=%I64d sealed_cursor=%I64d/%I64d pre_boundary_consumed=%I64d",
                            identifier,
                            activation_deal_ticket,
                            (sampled_identity_used
                             ? "sampled-full-identity"
                             : "deal-first-causal-compatible"),
                            original_stop,
                            (shadow_direction > 0
                             ? boundary_tick.bid : boundary_tick.ask),
                            rc4_shadow_activation_seal_eligible,
                            rc4_shadow_activation_seal_sealed,
                            rc4_shadow_activation_seal_pending_count,
                            rc4_shadow_activation_seal_save_attempts,
                            rc4_shadow_activation_seal_save_failures,
                            rc4_shadow_activation_seal_readbacks,
                            rc4_shadow_activation_seal_readback_failures,
                            rc4_shadow_activation_seal_failures,
                            rc4_shadow_activation_seal_ambiguities,
                            deal_time_msc,
                            boundary_ordinal,
                            rc4_shadow_activation_pre_boundary_consumed));
   return(!original_stop_reached);
  }


void ActivateRC4ShadowAfterCompressedExit(const ulong identifier,
                                          const datetime entered_at,
                                          const int direction,
                                          const double original_stop,
                                          const ulong deal_ticket,
                                          const long exit_time_msc,
                                          const double deal_price,
                                          const ENUM_DEAL_REASON deal_reason,
                                          const double protected_stop,
                                          const MqlTick &sampled_tick,
                                          const bool sampled_tick_known)
  {
   if(identifier == 0 || entered_at <= 0 || MathAbs(direction) != 1 ||
      original_stop <= 0.0 || deal_ticket == 0 || exit_time_msc <= 0 ||
      deal_price <= 0.0 || deal_reason != DEAL_REASON_SL ||
      protected_stop <= 0.0)
     {
      broker_mismatch = true;
      EngageSafetyStop("compressed RC4 exit lacks shadow identity");
      ClearArcLifecycleState();
      return;
     }
   if(rc4_shadow_occupied)
     {
      broker_mismatch = true;
      EngageSafetyStop("duplicate RC4 shadow occupancy activation");
      ClearArcLifecycleState();
      return;
     }
   rc4_shadow_occupied = true;
   rc4_shadow_source_identifier = identifier;
   rc4_shadow_entry_time = entered_at;
   rc4_shadow_direction = direction;
   rc4_shadow_original_stop_loss = original_stop;
   rc4_shadow_last_observed_msc = exit_time_msc;
   rc4_shadow_cursor_ordinal = 0;
   rc4_shadow_catchup_required = true;
   rc4_shadow_catchup_failure_logged = false;
   rc4_shadow_cursor_checkpoint_observation_bucket =
      exit_time_msc / RC4_NATIVE_M30_BUCKET_MSC;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
   rc4_shadow_cursor_checkpoint_pending = false;
   rc4_shadow_activation_sealed = false;
   rc4_shadow_activation_seal_pending = true;
   rc4_shadow_activation_seal_failure_logged = false;
   rc4_shadow_activation_deal_ticket = deal_ticket;
   rc4_shadow_activation_deal_time_msc = exit_time_msc;
   rc4_shadow_activation_deal_price = deal_price;
   rc4_shadow_activation_deal_reason = (int)deal_reason;
   rc4_shadow_activation_protected_stop = protected_stop;
   rc4_shadow_activation_sampled_tick_known = sampled_tick_known;
   rc4_shadow_activation_sampled_time =
      (sampled_tick_known ? sampled_tick.time : 0);
   rc4_shadow_activation_sampled_time_msc =
      (sampled_tick_known ? sampled_tick.time_msc : 0);
   rc4_shadow_activation_sampled_bid =
      (sampled_tick_known ? sampled_tick.bid : 0.0);
   rc4_shadow_activation_sampled_ask =
      (sampled_tick_known ? sampled_tick.ask : 0.0);
   rc4_shadow_activation_sampled_last =
      (sampled_tick_known ? sampled_tick.last : 0.0);
   rc4_shadow_activation_sampled_volume =
      (sampled_tick_known ? sampled_tick.volume : 0);
   rc4_shadow_activation_sampled_volume_real =
      (sampled_tick_known ? sampled_tick.volume_real : 0.0);
   rc4_shadow_activation_sampled_flags =
      (sampled_tick_known ? sampled_tick.flags : 0);
   rc4_shadow_activation_boundary_msc = 0;
   rc4_shadow_activation_boundary_ordinal = 0;
   ++rc4_shadow_activation_seal_eligible;
   ClearArcLifecycleState();
   ResolveAndPersistRC4ShadowActivationSeal();
  }


void ProcessRC4ShadowOccupancy()
  {
   if(!rc4_shadow_occupied)
      return;
   if(tracked_position_identifier[RC4_BOTH] != 0 ||
      rc4_shadow_source_identifier == 0 ||
      rc4_shadow_entry_time <= 0 ||
      MathAbs(rc4_shadow_direction) != 1 ||
      rc4_shadow_original_stop_loss <= 0.0 ||
      rc4_shadow_last_observed_msc <= 0)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 shadow occupancy state is inconsistent");
      return;
     }
   if(rc4_shadow_activation_seal_pending)
     {
      if(!ResolveAndPersistRC4ShadowActivationSeal())
         return;
      if(!rc4_shadow_occupied)
         return;
     }
   if(!rc4_shadow_activation_sealed ||
      rc4_shadow_activation_boundary_msc <= 0 ||
      rc4_shadow_activation_boundary_ordinal <= 0)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 shadow activation boundary is not sealed");
      return;
     }

   MqlTick tick = {};
   const bool tick_known = StructurallyValidTick("US30", tick);
   const int held_bars =
      iBarShift("US30", PERIOD_M30, rc4_shadow_entry_time, false);
   const bool deadline_release =
      (held_bars >= COMPONENT_HOLD_BARS[RC4_BOTH]);
   const bool recovery_pending_before = rc4_shadow_catchup_required;
   const long cursor_before_msc = rc4_shadow_last_observed_msc;
   const long cursor_before_ordinal = rc4_shadow_cursor_ordinal;
   const bool gap_scan_required = tick_known;
   bool gap_complete = false;
   bool stop_release = false;
   bool catchup_stop_release = false;
   long stop_time_msc = 0;
   if(gap_scan_required)
     {
      gap_complete =
         CatchUpRC4ShadowToTick(tick,
                                catchup_stop_release,
                                stop_time_msc);
      if(!gap_complete)
        {
         if(tick.time_msc > rc4_shadow_activation_boundary_msc &&
            ArcOriginalStopReached(rc4_shadow_direction,
                                   rc4_shadow_original_stop_loss,
                                   tick))
           {
            stop_release = true;
            stop_time_msc = tick.time_msc;
           }
         else if(!deadline_release)
           {
            if(!SaveState())
               EngageSafetyStop("RC4 incomplete shadow gap state could not be persisted");
            return;
           }
        }
      else
        {
         stop_release = catchup_stop_release;
         if(!PersistRC4ShadowCursorCheckpointIfEligible(
               cursor_before_msc,
               cursor_before_ordinal))
            return;
        }
     }
   else if(recovery_pending_before && !deadline_release)
      return;
   if(!stop_release && !deadline_release)
     {
      if(recovery_pending_before && !SaveState())
         EngageSafetyStop("RC4 shadow catch-up state could not be persisted");
      return;
     }

   const ulong identifier = rc4_shadow_source_identifier;
   const double original_stop = rc4_shadow_original_stop_loss;
   const string reason = (stop_release ? "ORIGINAL_STOP" : "ORIGINAL_DEADLINE");
   if(stop_release)
     {
      ++rc4_shadow_stop_releases;
      if(catchup_stop_release)
         ++rc4_shadow_catchup_stop_releases;
     }
   else
      ++rc4_shadow_deadline_releases;
   ClearRC4ShadowState();
   RecordEvent(RC4_BOTH,
               "ARC_SHADOW_RELEASED",
               original_stop,
               (double)held_bars,
               StringFormat("identifier=%I64u reason=%s",
                            identifier,
                            reason) +
               StringFormat(" catchup=%d stop_time_msc=%I64d",
                            (catchup_stop_release ? 1 : 0),
                            stop_time_msc));
   if(!SaveState())
      EngageSafetyStop("RC4 shadow release state could not be persisted");
  }


double ArcBounded(const double value)
  {
   return(MathMax(-8.0, MathMin(8.0, value)));
  }


int ArcOrdinalVote(const double value,
                   const double lower,
                   const double upper)
  {
   if(value <= lower)
      return(-1);
   if(value >= upper)
      return(1);
   return(0);
  }


double ArcSampleStandardDeviation(const double &values[],
                                  const int start,
                                  const int count)
  {
   if(count < 2 || start < 0 || start + count > ArraySize(values))
      return(0.0);
   double mean = 0.0;
   for(int index = start; index < start + count; ++index)
      mean += values[index];
   mean /= (double)count;
   double squared = 0.0;
   for(int index = start; index < start + count; ++index)
     {
      const double deviation = values[index] - mean;
      squared += deviation * deviation;
     }
   return(MathSqrt(squared / (double)(count - 1)));
  }


bool ArcCalculateRangeCompressionAtOffset(const int completed_offset,
                                          double &signed_tightness)
  {
   signed_tightness = 0.0;
   const int compression_window = 4;
   const int normal_window = 96;
   const int direction_lookback = 2;
   const int bar_count = normal_window + compression_window;
   double highs[];
   double lows[];
   double closes[];
   const int start_shift = 1 + completed_offset;
   if(CopyHigh("US30", PERIOD_M30, start_shift, bar_count, highs) != bar_count ||
      CopyLow("US30", PERIOD_M30, start_shift, bar_count, lows) != bar_count ||
      CopyClose("US30", PERIOD_M30, start_shift, bar_count, closes) != bar_count)
      return(false);

   double prior_ranges[];
   ArrayResize(prior_ranges, normal_window);
   for(int sample = 0; sample < normal_window; ++sample)
     {
      prior_ranges[sample] =
         WindowLogRange(highs, lows, sample, compression_window);
      if(prior_ranges[sample] <= 0.0)
         return(false);
     }
   const double normal_range = Median(prior_ranges);
   const double current_range =
      WindowLogRange(highs, lows, normal_window, compression_window);
   const int latest = bar_count - 1;
   const int earlier = latest - direction_lookback;
   if(normal_range <= 0.0 || current_range <= 0.0 ||
      closes[latest] <= 0.0 || closes[earlier] <= 0.0)
      return(false);
   const double direction_return =
      MathLog(closes[latest] / closes[earlier]);
   if(direction_return == 0.0)
      return(true);
   signed_tightness =
      (direction_return > 0.0 ? 1.0 : -1.0) /
      (current_range / normal_range);
   return(MathIsValidNumber(signed_tightness));
  }


bool ArcCalculateUS30M30NativeState(double &ret1_z,
                                    double &efficiency4,
                                    double &close_location,
                                    double &vol_ratio,
                                    double &range_median96)
  {
   ret1_z = 0.0;
   efficiency4 = 0.0;
   close_location = 0.0;
   vol_ratio = 0.0;
   range_median96 = 0.0;
   const int count = 97;
   MqlRates rates[];
   if(CopyRates("US30", PERIOD_M30, 1, count, rates) != count)
      return(false);

   double returns[];
   ArrayResize(returns, count - 1);
   for(int index = 1; index < count; ++index)
     {
      if(rates[index].close <= 0.0 || rates[index - 1].close <= 0.0)
         return(false);
      returns[index - 1] =
         MathLog(rates[index].close / rates[index - 1].close);
     }
   const double prior_std = ArcSampleStandardDeviation(returns, 47, 48);
   const double fast_std = ArcSampleStandardDeviation(returns, 92, 4);
   const double slow_std = ArcSampleStandardDeviation(returns, 71, 24);
   if(prior_std <= 0.0 || slow_std < 0.0)
      return(false);

   const int latest = count - 1;
   ret1_z = returns[95] / prior_std;
   double absolute_path = 0.0;
   for(int index = 92; index <= 95; ++index)
      absolute_path += MathAbs(returns[index]);
   efficiency4 =
      MathAbs(MathLog(rates[latest].close / rates[latest - 4].close)) /
      (absolute_path + 1.0e-12);
   const double latest_range = rates[latest].high - rates[latest].low;
   if(latest_range <= 0.0)
      return(false);
   close_location =
      2.0 * ((rates[latest].close - rates[latest].low) /
             latest_range - 0.5);
   vol_ratio = fast_std / (slow_std + 1.0e-12);

   double prior_ranges[];
   ArrayResize(prior_ranges, 96);
   for(int index = 0; index < 96; ++index)
     {
      prior_ranges[index] = rates[index].high - rates[index].low;
      if(prior_ranges[index] <= 0.0)
         return(false);
     }
   range_median96 = Median(prior_ranges);
   return(MathIsValidNumber(ret1_z) &&
          MathIsValidNumber(efficiency4) &&
          MathIsValidNumber(close_location) &&
          MathIsValidNumber(vol_ratio) &&
          MathIsValidNumber(range_median96) &&
          range_median96 > 0.0);
  }


bool ArcCalculateRC4Heads(const int direction,
                          double &market,
                          double &decision,
                          double &confirmation)
  {
   market = 0.0;
   decision = 0.0;
   confirmation = 0.0;
   if(MathAbs(direction) != 1)
      return(false);

   double current_feature = 0.0;
   double previous_feature = 0.0;
   double two_back_feature = 0.0;
   if(!ArcCalculateRangeCompressionAtOffset(0, current_feature) ||
      !ArcCalculateRangeCompressionAtOffset(1, previous_feature) ||
      !ArcCalculateRangeCompressionAtOffset(2, two_back_feature))
      return(false);

   double ret1_z = 0.0;
   double efficiency4 = 0.0;
   double close_location = 0.0;
   double vol_ratio = 0.0;
   double native_range = 0.0;
   if(!ArcCalculateUS30M30NativeState(ret1_z,
                                      efficiency4,
                                      close_location,
                                      vol_ratio,
                                      native_range))
      return(false);
   double pressure = 0.0;
   if(!CalculateIntradayRangePressure("US30", pressure))
      return(false);
   MqlTick tick = {};
   if(!StructurallyValidTick("US30", tick))
      return(false);

   const double entry_support =
      (double)direction * entry_feature[RC4_BOTH];
   const double current_support = (double)direction * current_feature;
   const double previous_support = (double)direction * previous_feature;
   const double two_back_support = (double)direction * two_back_feature;
   const double scale = MathMax(MathMax(MathAbs(entry_support), 1.5), 0.25);
   const double velocity =
      (current_support - previous_support) / scale;
   const double prior_velocity =
      (previous_support - two_back_support) / scale;
   const double curvature = velocity - prior_velocity;
   const double spread = MathMax(tick.ask - tick.bid, 1.10);
   const double cost_scale =
      MathMax(0.0, MathMin(2.0, spread / native_range));

   market = ArcBounded(
      (double)direction * ret1_z * (0.40 + 0.60 * efficiency4) -
      0.25 * MathMax(0.0, vol_ratio - 1.0) -
      0.20 * cost_scale);
   decision = ArcBounded(
      current_support / scale +
      0.65 * velocity +
      0.35 * curvature -
      (current_support < 0.0 ? 1.25 : 0.0));
   confirmation = ArcBounded(
      0.70 * (double)direction * pressure +
      0.30 * (double)direction * close_location);
   return(MathIsValidNumber(market) &&
          MathIsValidNumber(decision) &&
          MathIsValidNumber(confirmation));
  }


bool ArcRoundedLossSideStop(const double entry,
                            const double original_stop,
                            const int direction,
                            double &new_stop)
  {
   new_stop = 0.0;
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const int digits = (int)SymbolInfoInteger("US30", SYMBOL_DIGITS);
   if(entry <= 0.0 || original_stop <= 0.0 || tick_size <= 0.0 ||
      MathAbs(direction) != 1)
      return(false);
   const double raw =
      entry + ARC_RC4_RETAINED_LOSS_FRACTION * (original_stop - entry);
   const double units = raw / tick_size;
   new_stop = NormalizeDouble(
      (direction > 0
       ? MathFloor(units + 1.0e-12) * tick_size
       : MathCeil(units - 1.0e-12) * tick_size),
      digits);
   return(new_stop > 0.0);
  }


void BeginArcLifecycle(const ulong identifier)
  {
   ClearArcLifecycleState();
   if(identifier == 0)
      return;
   arc_lifecycle_identifier = identifier;
   arc_original_stop_loss = entry_stop_loss[RC4_BOTH];
  }


bool IsArcTransientModifyRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_REQUOTE ||
          retcode == TRADE_RETCODE_TIMEOUT ||
          retcode == TRADE_RETCODE_PRICE_CHANGED ||
          retcode == TRADE_RETCODE_PRICE_OFF ||
          retcode == TRADE_RETCODE_TOO_MANY_REQUESTS ||
          retcode == TRADE_RETCODE_LOCKED ||
          retcode == TRADE_RETCODE_CONNECTION);
  }


void ClearArcRetryIntent()
  {
   arc_modify_retry_pending = false;
   arc_modify_retry_after_msc = 0;
   arc_modify_retry_initial_retcode = 0;
  }


bool ReconcileArcPendingModify(const bool restart_recovery)
  {
   if(!arc_modify_pending && !arc_modify_retry_pending)
      return(true);
   const ulong identifier = tracked_position_identifier[RC4_BOTH];
   if(identifier == 0 || identifier != arc_lifecycle_identifier ||
      !arc_checkpoint_evaluated || arc_lifecycle_compressed ||
      arc_pending_stop_loss <= 0.0)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 pending stop journal is inconsistent");
      return(false);
     }

   ulong ticket = 0;
   datetime opened_at = 0;
   if(CountOwnedPositions(RC4_BOTH, ticket, opened_at) != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 pending stop journal lacks its broker position");
      return(false);
     }
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   const double original_saved_stop = entry_stop_loss[RC4_BOTH];
   const double pending_stop = arc_pending_stop_loss;
   const double tolerance = MathMax(1.0e-9, 0.5 * tick_size);
   const bool broker_applied =
      (tick_size > 0.0 &&
       MathAbs(broker_stop - pending_stop) <= tolerance);
   const bool broker_not_applied =
      (tick_size > 0.0 && original_saved_stop > 0.0 &&
       MathAbs(broker_stop - original_saved_stop) <= tolerance);
   if(!broker_applied && !broker_not_applied)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 pending stop journal differs from broker stop");
      return(false);
     }
   if(arc_modify_retry_pending && broker_not_applied)
      return(true);
   if(!restart_recovery && broker_not_applied)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 completed stop modify was not applied by broker");
      return(false);
     }

   arc_modify_pending = false;
   ClearArcRetryIntent();
   if(broker_applied)
     {
      entry_stop_loss[RC4_BOTH] = broker_stop;
      arc_lifecycle_compressed = true;
      ++arc_compressions_placed;
      arc_pending_stop_loss = 0.0;
      RecordEvent(RC4_BOTH,
                  (restart_recovery ? "ARC_MODIFY_RECOVERED" :
                                      "ARC_COMPRESSED"),
                  original_saved_stop,
                  broker_stop,
                  StringFormat("identifier=%I64u broker_applied=1 recovery=%d",
                               identifier,
                               (restart_recovery ? 1 : 0)));
     }
   else
     {
      arc_pending_stop_loss = 0.0;
      ++arc_modify_retry_holds;
      ++arc_compression_refusals;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_RESTART_HOLD",
                  original_saved_stop,
                  pending_stop,
                  StringFormat("identifier=%I64u ambiguous_request_not_applied=1",
                               identifier));
     }
   if(!SaveState())
     {
      EngageSafetyStop("RC4 pending stop recovery could not be persisted");
      return(false);
     }
   return(true);
  }


bool ResolveArcNonSuccessfulModify(const uint retcode,
                                   const string description,
                                   const long attempt_tick_msc,
                                   const bool retry_attempt)
  {
   const ulong identifier = tracked_position_identifier[RC4_BOTH];
   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned_positions =
      CountOwnedPositions(RC4_BOTH, ticket, opened_at);
   if(identifier != 0 && identifier == arc_lifecycle_identifier &&
      owned_positions == 0)
     {
      pending_reconcile = true;
      if(ReconcileBrokerState(false))
         return(true);
      broker_mismatch = true;
      EngageSafetyStop("RC4 non-successful modify close could not be reconciled");
      return(false);
     }
   if(identifier == 0 || identifier != arc_lifecycle_identifier ||
      owned_positions != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 non-successful modify lost owned position");
      return(false);
     }

   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   const double original_stop = entry_stop_loss[RC4_BOTH];
   const double target_stop = arc_pending_stop_loss;
   const double tolerance = MathMax(1.0e-9, 0.5 * tick_size);
   const bool broker_applied =
      (tick_size > 0.0 && target_stop > 0.0 &&
       MathAbs(broker_stop - target_stop) <= tolerance);
   const bool broker_original =
      (tick_size > 0.0 && original_stop > 0.0 &&
       MathAbs(broker_stop - original_stop) <= tolerance);
   if(!broker_applied && !broker_original)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 non-successful modify broker stop is inconsistent");
      return(false);
     }

   arc_modify_pending = false;
   if(broker_applied)
     {
      ClearArcRetryIntent();
      arc_pending_stop_loss = 0.0;
      entry_stop_loss[RC4_BOTH] = broker_stop;
      arc_lifecycle_compressed = true;
      ++arc_compressions_placed;
      ++arc_modify_retry_adoptions;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_ALREADY_APPLIED",
                  broker_stop,
                  (double)retcode,
                  StringFormat("identifier=%I64u retry=%d %s",
                               identifier,
                               (retry_attempt ? 1 : 0),
                               description));
      if(!SaveState())
        {
         EngageSafetyStop("RC4 applied modify adoption could not be persisted");
         return(false);
        }
      return(true);
     }

   if(!retry_attempt && IsArcTransientModifyRetcode(retcode) &&
      attempt_tick_msc > 0 && !arc_modify_retry_consumed)
     {
      arc_modify_retry_pending = true;
      arc_modify_retry_after_msc = attempt_tick_msc;
      arc_modify_retry_initial_retcode = retcode;
      ++arc_modify_retry_intents;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_RETRY_INTENT",
                  target_stop,
                  (double)retcode,
                  StringFormat("identifier=%I64u strictly_after_msc=%I64d %s",
                               identifier,
                               attempt_tick_msc,
                               description));
      if(!SaveState())
        {
         EngageSafetyStop("RC4 retry intent could not be persisted");
         return(false);
        }
      return(true);
     }

   ClearArcRetryIntent();
   arc_pending_stop_loss = 0.0;
   ++arc_modify_retry_holds;
   ++arc_compression_refusals;
   RecordEvent(RC4_BOTH,
               (retry_attempt ? "ARC_MODIFY_RETRY_HOLD" :
                                "ARC_MODIFY_NONRETRYABLE_HOLD"),
               original_stop,
               (double)retcode,
               StringFormat("identifier=%I64u %s", identifier, description));
   if(!SaveState())
     {
      EngageSafetyStop("RC4 modify HOLD could not be persisted");
      return(false);
     }
   return(true);
  }


void ProcessArcModifyRetry()
  {
   if(!arc_modify_retry_pending || arc_modify_pending ||
      arc_modify_retry_consumed || safety_stopped || broker_mismatch ||
      persistence_failed)
      return;

   MqlTick observed = {};
   if(!SymbolInfoTick("US30", observed) ||
      observed.time_msc <= arc_modify_retry_after_msc)
      return;

   const ulong identifier = tracked_position_identifier[RC4_BOTH];
   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned_positions =
      CountOwnedPositions(RC4_BOTH, ticket, opened_at);
   if(identifier != 0 && identifier == arc_lifecycle_identifier &&
      owned_positions == 0)
     {
      pending_reconcile = true;
      if(!ReconcileBrokerState(false))
        {
         broker_mismatch = true;
         EngageSafetyStop("RC4 retry checkpoint close could not be reconciled");
        }
      return;
     }
   if(identifier == 0 || identifier != arc_lifecycle_identifier ||
      owned_positions != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 retry checkpoint lost owned position");
      return;
     }

   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   const double original_stop = entry_stop_loss[RC4_BOTH];
   const double target_stop = arc_pending_stop_loss;
   const double tolerance = MathMax(1.0e-9, 0.5 * tick_size);
   if(tick_size <= 0.0 || target_stop <= 0.0 || original_stop <= 0.0)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 retry checkpoint has invalid stop state");
      return;
     }
   if(MathAbs(broker_stop - target_stop) <= tolerance)
     {
      arc_modify_pending = true;
      ++arc_modify_retry_adoptions;
      if(!ReconcileArcPendingModify(false))
         return;
      return;
     }
   if(MathAbs(broker_stop - original_stop) > tolerance)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 retry checkpoint broker stop changed");
      return;
     }

   const int direction = entry_direction[RC4_BOTH];
   const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   const double take_profit = PositionGetDouble(POSITION_TP);
   const MqlTick tick = observed;
   const double tick_age_seconds =
      MathAbs((double)((long)TimeCurrent() - (long)tick.time));
   const bool executable_tick =
      (tick.ask > tick.bid && tick.time > 0 &&
       tick_age_seconds <= MAX_EXECUTABLE_TICK_AGE_SECONDS);
   const double required = MinimumProtectionDistance("US30");
   const double executable =
      (executable_tick ? (direction > 0 ? tick.bid : tick.ask) : 0.0);
   const double retained_loss = (double)direction * (entry - target_stop);
   const double tightening = (double)direction * (target_stop - original_stop);
   const double quote_clearance =
      (executable_tick ? (double)direction * (executable - target_stop) : 0.0);
   const double price_tolerance = MathMax(1.0e-10, tick_size * 1.0e-8);
   const bool legal =
      (MathAbs(direction) == 1 && entry > 0.0 && executable_tick &&
       TradeSessionAllows("US30", TimeCurrent(), false) &&
       retained_loss >= tick_size - price_tolerance &&
       tightening >= tick_size - price_tolerance &&
       quote_clearance >= required - price_tolerance);
   if(!legal)
     {
      ClearArcRetryIntent();
      arc_pending_stop_loss = 0.0;
      ++arc_modify_retry_holds;
      ++arc_compression_refusals;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_RETRY_ILLEGAL_HOLD",
                  target_stop,
                  executable,
                  StringFormat("identifier=%I64u retained=%.5f tighten=%.5f clearance=%.5f required=%.5f",
                               identifier,
                               retained_loss,
                               tightening,
                               quote_clearance,
                               required));
      if(!SaveState())
         EngageSafetyStop("RC4 illegal retry HOLD could not be persisted");
      return;
     }

   arc_modify_retry_pending = false;
   arc_modify_retry_consumed = true;
   arc_modify_retry_after_msc = 0;
   arc_modify_retry_initial_retcode = 0;
   arc_modify_pending = true;
   ++arc_modify_retry_attempts;
   if(!SaveState())
     {
      EngageSafetyStop("RC4 consumed retry journal could not be persisted");
      return;
     }

   trade.SetExpertMagicNumber(MAGIC_RC4_BOTH);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol("US30");
   trade.SetAsyncMode(false);
   trade_operation_active = true;
   const bool requested =
      trade.PositionModify(ticket, target_stop, take_profit);
   const uint retcode = trade.ResultRetcode();
   const string description = trade.ResultRetcodeDescription();
   trade_operation_active = false;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      ResolveArcNonSuccessfulModify(retcode,
                                    description,
                                    tick.time_msc,
                                    true);
      return;
     }
   ++arc_modify_retry_successes;
   if(!PositionSelectByTicket(ticket))
     {
      pending_reconcile = true;
      if(!ReconcileBrokerState(false))
         EngageSafetyStop("RC4 retried position disappeared before confirmation");
      return;
     }
   ReconcileArcPendingModify(false);
  }


void ProcessRC4AdverseRiskCompression()
  {
   const ulong identifier = tracked_position_identifier[RC4_BOTH];
   if(identifier == 0)
     {
      if(arc_lifecycle_identifier != 0)
        {
         ClearArcLifecycleState();
         if(!SaveState())
            EngageSafetyStop("stale RC4 management state could not be cleared");
        }
      return;
     }
   if(rc4_shadow_occupied)
     {
      broker_mismatch = true;
      EngageSafetyStop("RC4 position overlaps shadow occupancy");
      return;
     }
   if(arc_modify_retry_pending)
     {
      ProcessArcModifyRetry();
      return;
     }
   if(identifier != arc_lifecycle_identifier)
     {
      BeginArcLifecycle(identifier);
      if(arc_original_stop_loss <= 0.0 || !SaveState())
        {
         EngageSafetyStop("RC4 management lifecycle could not be initialized");
         return;
        }
     }
   if(arc_checkpoint_evaluated || safety_stopped || broker_mismatch ||
      persistence_failed)
      return;

   ulong ticket = 0;
   datetime opened_at = 0;
   if(CountOwnedPositions(RC4_BOTH, ticket, opened_at) != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
      return;
   const int held_bars =
      iBarShift("US30", PERIOD_M30, opened_at, false);
   if(held_bars < ARC_RC4_CHECKPOINT_BARS)
      return;
   const datetime current_bar = iTime("US30", PERIOD_M30, 0);
   if(current_bar <= 0 || current_bar == arc_last_attempt_bar)
      return;
   arc_last_attempt_bar = current_bar;

   double market = 0.0;
   double decision = 0.0;
   double confirmation = 0.0;
   if(!ArcCalculateRC4Heads(entry_direction[RC4_BOTH],
                            market,
                            decision,
                            confirmation))
     {
      ++arc_data_unavailable;
      if(!SaveState())
         EngageSafetyStop("RC4 unavailable-checkpoint state could not be persisted");
      return;
     }

   arc_checkpoint_evaluated = true;
   ++arc_checkpoints;
   const int market_vote =
      ArcOrdinalVote(market, ARC_MARKET_LOWER, ARC_MARKET_UPPER);
   const int decision_vote =
      ArcOrdinalVote(decision, ARC_DECISION_LOWER, ARC_DECISION_UPPER);
   const int confirmation_vote =
      ArcOrdinalVote(confirmation, ARC_CONFIRM_LOWER, ARC_CONFIRM_UPPER);
   const int vote_sum = market_vote + decision_vote + confirmation_vote;
   RecordEvent(RC4_BOTH,
               "ARC_CHECKPOINT",
               (double)vote_sum,
               market,
               StringFormat("held=%d votes=%d/%d/%d heads=%.8f/%.8f/%.8f",
                            held_bars,
                            market_vote,
                            decision_vote,
                            confirmation_vote,
                            market,
                            decision,
                            confirmation));
   if(vote_sum > ARC_ADVERSE_VOTE_THRESHOLD)
     {
      if(!SaveState())
         EngageSafetyStop("RC4 checkpoint state could not be persisted");
      return;
     }
   ++arc_adverse_triggers;

   if(!PositionSelectByTicket(ticket))
     {
      ++arc_compression_refusals;
      SaveState();
      return;
     }
   const int direction = entry_direction[RC4_BOTH];
   const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   const double original_stop = arc_original_stop_loss;
   const double take_profit = PositionGetDouble(POSITION_TP);
   double new_stop = 0.0;
   MqlTick tick = {};
   if(!ArcRoundedLossSideStop(entry, original_stop, direction, new_stop) ||
      !ExecutableTick("US30", tick) ||
      !TradeSessionAllows("US30", TimeCurrent(), false))
     {
      ++arc_compression_refusals;
      SaveState();
      return;
     }
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double required = MinimumProtectionDistance("US30");
   const double executable = (direction > 0 ? tick.bid : tick.ask);
   const double retained_loss = (double)direction * (entry - new_stop);
   const double tightening = (double)direction * (new_stop - original_stop);
   const double quote_clearance = (double)direction * (executable - new_stop);
   const double tolerance = MathMax(1.0e-10, tick_size * 1.0e-8);
   if(retained_loss < tick_size - tolerance ||
      tightening < tick_size - tolerance ||
      quote_clearance < required - tolerance)
     {
      ++arc_compression_refusals;
      RecordEvent(RC4_BOTH,
                  "ARC_REFUSED",
                  new_stop,
                  executable,
                  StringFormat("retained=%.5f tighten=%.5f clearance=%.5f required=%.5f",
                               retained_loss,
                               tightening,
                               quote_clearance,
                               required));
      SaveState();
      return;
     }

   arc_modify_pending = true;
   arc_pending_stop_loss = new_stop;
   if(!SaveState())
     {
      arc_modify_pending = false;
      arc_pending_stop_loss = 0.0;
      EngageSafetyStop("RC4 stop-modify journal could not be persisted");
      return;
     }
   trade.SetExpertMagicNumber(MAGIC_RC4_BOTH);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol("US30");
   trade.SetAsyncMode(false);
   trade_operation_active = true;
   const bool requested = trade.PositionModify(ticket, new_stop, take_profit);
   const uint retcode = trade.ResultRetcode();
   const string result_description = trade.ResultRetcodeDescription();
   trade_operation_active = false;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      ResolveArcNonSuccessfulModify(retcode,
                                    result_description,
                                    tick.time_msc,
                                    false);
      return;
     }
   if(!PositionSelectByTicket(ticket))
     {
      pending_reconcile = true;
      if(!ReconcileBrokerState(false))
         EngageSafetyStop("RC4 modified position disappeared before confirmation");
      return;
     }
   if(!ReconcileArcPendingModify(false))
      return;
  }


bool CalculateUS30ReturnImpulse(double &feature)
  {
   const int lookback = 4;
   const int scale_window = 120;
   double recent[];
   if(CopyClose("US30", PERIOD_H1, 1, lookback + 1, recent) !=
      lookback + 1)
      return(false);
   double prior[];
   if(CopyClose("US30", PERIOD_H1, 2, scale_window + 1, prior) !=
      scale_window + 1)
      return(false);
   double mean = 0.0;
   double returns[];
   ArrayResize(returns, scale_window);
   for(int index = 0; index < scale_window; ++index)
     {
      if(prior[index] <= 0.0 || prior[index + 1] <= 0.0)
         return(false);
      returns[index] = MathLog(prior[index + 1] / prior[index]);
      mean += returns[index];
     }
   mean /= scale_window;
   double squared = 0.0;
   for(int index = 0; index < scale_window; ++index)
     {
      const double deviation = returns[index] - mean;
      squared += deviation * deviation;
     }
   const double standard_deviation =
      MathSqrt(squared / (scale_window - 1));
   if(standard_deviation <= 0.0 ||
      recent[0] <= 0.0 || recent[lookback] <= 0.0)
      return(false);
   feature = MathLog(recent[lookback] / recent[0]) /
             (standard_deviation * MathSqrt((double)lookback));
   return(MathIsValidNumber(feature));
  }


double SampleStandardDeviation(const double &values[],
                               const int start,
                               const int count)
  {
   if(count < 2 || start < 0 || start + count > ArraySize(values))
      return(0.0);
   double mean = 0.0;
   for(int offset = 0; offset < count; ++offset)
      mean += values[start + offset];
   mean /= count;
   double squared = 0.0;
   for(int offset = 0; offset < count; ++offset)
     {
      const double deviation = values[start + offset] - mean;
      squared += deviation * deviation;
     }
   return(MathSqrt(squared / (count - 1)));
  }


bool CalculatePassiveState(double &state,
                           double &range_scale,
                           double &decision_close)
  {
   const int close_count = PASSIVE_SCALE_RETURNS + 2;
   double closes[];
   ArraySetAsSeries(closes, false);
   if(CopyClose("US100", PERIOD_M15, 1, close_count, closes) !=
      close_count)
      return(false);
   double returns[];
   ArrayResize(returns, PASSIVE_SCALE_RETURNS);
   for(int index = 0; index < PASSIVE_SCALE_RETURNS; ++index)
     {
      if(closes[index] <= 0.0 || closes[index + 1] <= 0.0)
         return(false);
      returns[index] = MathLog(closes[index + 1] / closes[index]);
     }
   const double standard_deviation =
      SampleStandardDeviation(returns, 0, PASSIVE_SCALE_RETURNS);
   const int latest = close_count - 1;
   const int earlier = latest - PASSIVE_LOOKBACK;
   if(standard_deviation <= 0.0 || earlier < 0 ||
      closes[earlier] <= 0.0)
      return(false);
   state = MathLog(closes[latest] / closes[earlier]) /
           (standard_deviation * MathSqrt((double)PASSIVE_LOOKBACK));
   decision_close = closes[latest];

   double highs[];
   double lows[];
   ArraySetAsSeries(highs, false);
   ArraySetAsSeries(lows, false);
   if(CopyHigh("US100",
               PERIOD_M15,
               2,
               PASSIVE_SCALE_RETURNS,
               highs) != PASSIVE_SCALE_RETURNS ||
      CopyLow("US100",
              PERIOD_M15,
              2,
              PASSIVE_SCALE_RETURNS,
              lows) != PASSIVE_SCALE_RETURNS)
      return(false);
   double ranges[];
   ArrayResize(ranges, PASSIVE_SCALE_RETURNS);
   for(int index = 0; index < PASSIVE_SCALE_RETURNS; ++index)
     {
      if(highs[index] <= lows[index] || lows[index] <= 0.0)
         return(false);
      ranges[index] = highs[index] - lows[index];
     }
   range_scale = Median(ranges);
   return(range_scale > 0.0 && MathIsValidNumber(state));
  }


double PassiveLimitPrice(const double raw_price, const int direction)
  {
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   const int digits = (int)SymbolInfoInteger("US100", SYMBOL_DIGITS);
   if(tick_size <= 0.0)
      return(0.0);
   const double units = raw_price / tick_size;
   const double rounded =
      (direction > 0
       ? MathFloor(units + 1.0e-10) * tick_size
       : MathCeil(units - 1.0e-10) * tick_size);
   return(NormalizeDouble(rounded, digits));
  }


bool PassiveDecisionSessionAllows(const datetime decision_bar)
  {
   MqlDateTime parts = {};
   TimeToStruct(decision_bar, parts);
   return(parts.hour >= 12 && parts.hour < 16);
  }


bool PlacePassiveLimit(const int direction,
                       const double state,
                       const double limit_price,
                       const datetime expiration)
  {
   if(direction == 0 || expiration <= TimeCurrent() ||
      !NewEntriesOperationallyAllowed())
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "ENTRY_BLOCKED";
      return(false);
     }
   if(!AuditPositionOwnership() || foreign_exposure)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "OWNERSHIP_BLOCKED";
      return(false);
     }
   ulong position_ticket = 0;
   datetime opened_at = 0;
   ulong order_ticket = 0;
   if(CountOwnedPositions(US100_PASSIVE_LIMIT,
                          position_ticket,
                          opened_at) != 0 ||
      CountOwnedPassiveOrders(order_ticket) != 0)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "EXISTING_EXPOSURE";
      return(false);
     }
   MqlTick tick = {};
   if(!ExecutableTick("US100", tick))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "QUOTE_UNAVAILABLE";
      return(false);
     }
   if(!TradeSessionAllows("US100", TimeCurrent(), true))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "TRADE_SESSION_BLOCKED";
      return(false);
     }
   entry_check_order_price[US100_PASSIVE_LIMIT] = limit_price;
   entry_check_volume[US100_PASSIVE_LIMIT] = InpBaseVolume;
   if(!PassiveMarginAllows(direction, limit_price))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "MARGIN_BLOCKED";
      SaveState();
      return(false);
     }
   const double point = SymbolInfoDouble("US100", SYMBOL_POINT);
   const double tick_size =
      SymbolInfoDouble("US100", SYMBOL_TRADE_TICK_SIZE);
   const double stops_distance =
      (double)SymbolInfoInteger("US100", SYMBOL_TRADE_STOPS_LEVEL) * point;
   const double required_distance = MathMax(tick_size, stops_distance);
   if((direction > 0 && tick.bid - limit_price < required_distance) ||
      (direction < 0 && limit_price - tick.ask < required_distance))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "PRICE_DISTANCE_BLOCKED";
      ++passive_price_constraint_skips;
      RecordEvent(US100_PASSIVE_LIMIT,
                  "PASSIVE_PRICE_SKIP",
                  limit_price,
                  required_distance,
                  StringFormat("direction=%d bid=%.2f ask=%.2f",
                               direction,
                               tick.bid,
                               tick.ask));
      SaveState();
      return(false);
     }

   double stop_loss = 0.0;
   double admitted_planned_risk = 0.0;
   if(!CalculateProtectiveStop(US100_PASSIVE_LIMIT,
                               "US100",
                               direction,
                               InpBaseVolume,
                               limit_price,
                               MathMax(required_distance,
                                       MinimumProtectionDistance("US100")),
                               stop_loss,
                               admitted_planned_risk))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "PROTECTION_OR_RISK_BLOCKED";
      SaveState();
      return(false);
     }
   entry_check_stop_loss[US100_PASSIVE_LIMIT] = stop_loss;
   entry_check_planned_risk_usd[US100_PASSIVE_LIMIT] =
      admitted_planned_risk;
   const double admitted_capital = ConservativeRiskCapital();
   const double aggregate_before = TrackedAggregatePlannedRisk();

   trade.SetExpertMagicNumber(MAGIC_US100_PASSIVE_LIMIT);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol("US100");
   trade.SetMarginMode();
   trade.SetAsyncMode(false);
   if(!MarkDecisionOrderAttempted(US100_PASSIVE_LIMIT,
                                  direction,
                                  state,
                                  "PASSIVE_LIMIT"))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "PERSISTENCE_FAILED";
      return(false);
     }
   passive_pending_stop_loss = stop_loss;
   passive_pending_planned_risk_usd = admitted_planned_risk;
   trade_operation_active = true;
   const bool requested =
      (direction > 0
       ? trade.BuyLimit(InpBaseVolume,
                        limit_price,
                        "US100",
                        stop_loss,
                        0.0,
                        ORDER_TIME_SPECIFIED,
                        expiration,
                        "ZT 6 P5FR5")
       : trade.SellLimit(InpBaseVolume,
                         limit_price,
                         "US100",
                         stop_loss,
                         0.0,
                         ORDER_TIME_SPECIFIED,
                         expiration,
                         "ZT 6 P5FR5"));
   const uint retcode = trade.ResultRetcode();
   const string retcode_description = trade.ResultRetcodeDescription();
   const ulong returned_order = trade.ResultOrder();
   trade_operation_active = false;
   if(!requested || !IsPendingPlacementRetcode(retcode))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "BROKER_REJECTED";
      passive_pending_stop_loss = 0.0;
      passive_pending_planned_risk_usd = 0.0;
      if(retcode == TRADE_RETCODE_INVALID_PRICE)
        {
         ++passive_stale_price_rejections;
         RecordEvent(US100_PASSIVE_LIMIT,
                      "PASSIVE_STALE_PRICE",
                      limit_price,
                      state,
                      retcode_description);
        }
      else
        {
         ++passive_placement_failures;
         RecordEvent(US100_PASSIVE_LIMIT,
                      "PASSIVE_PLACE_FAIL",
                      (double)retcode,
                      limit_price,
                      retcode_description);
        }
      SaveState();
      return(false);
     }

   order_ticket = 0;
   position_ticket = 0;
   opened_at = 0;
   const int orders = CountOwnedPassiveOrders(order_ticket);
   const int positions =
      CountOwnedPositions(US100_PASSIVE_LIMIT,
                          position_ticket,
                          opened_at);
   if((orders != 1 || positions != 0) &&
      (orders != 0 || positions != 1))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "SAFETY_STOP";
      broker_mismatch = true;
      EngageSafetyStop("passive placement created invalid broker state");
      pending_reconcile = true;
      return(true);
     }
   tracked_passive_pending_order =
      (orders == 1 ? order_ticket : returned_order);
   passive_pending_expiration = expiration;
   passive_pending_direction = direction;
   passive_pending_feature = state;
   passive_pending_limit_price = limit_price;
   ++passive_pending_placements;
   if(orders == 1 && tracked_passive_pending_order == 0)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "SAFETY_STOP";
      broker_mismatch = true;
      EngageSafetyStop("passive placement lacks order identity");
      pending_reconcile = true;
      return(true);
     }
   if(orders == 1)
     {
      string protection_detail = "";
      if(!OrderSelect(order_ticket) ||
         !SelectedPassiveOrderProtectionMatches(protection_detail) ||
         aggregate_before + passive_pending_planned_risk_usd >
         admitted_capital * InpMaximumAggregateRiskFraction +
         MathMax(0.01, passive_pending_planned_risk_usd * 0.01))
        {
         entry_check_result[US100_PASSIVE_LIMIT] = "SAFETY_STOP";
         ++protection_mismatches;
         broker_mismatch = true;
         EngageSafetyStop("placed passive protection not confirmed: " +
                          protection_detail);
         CancelPassivePendingOrder(order_ticket,
                                   "post-placement protection mismatch");
         return(true);
        }
     }
   entry_check_result[US100_PASSIVE_LIMIT] =
      (positions == 1 ? "POSITION_OPEN" : "PENDING_ORDER");
   if(positions == 1 &&
      !ReconstructEntryTracking(US100_PASSIVE_LIMIT, position_ticket))
      return(false);
   const ulong adopted_ticket =
      (positions == 1
       ? tracked_position_identifier[US100_PASSIVE_LIMIT]
       : tracked_passive_pending_order);
   if(!MarkDecisionBrokerStateAdopted(US100_PASSIVE_LIMIT,
                                      adopted_ticket,
                                      (positions == 1
                                       ? "POSITION_ADOPTED" :
                                         "PENDING_ORDER_ADOPTED")))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "SAFETY_STOP";
      EngageSafetyStop("adopted passive broker state could not be persisted");
      MakeExistingRiskSafe("passive adoption journal failure");
      return(true);
     }
   RecordEvent(US100_PASSIVE_LIMIT,
               "PASSIVE_PLACE",
               limit_price,
               state,
               StringFormat("direction=%d expiration=%s order=%I64u stop=%.5f planned_risk=%.4f",
                            direction,
                            TimeToString(expiration,
                                         TIME_DATE | TIME_MINUTES),
                            (positions == 1
                             ? returned_order :
                               tracked_passive_pending_order),
                            stop_loss,
                            admitted_planned_risk));
   return(SaveState());
  }


void ProcessPassiveLimit()
  {
   const datetime current_bar = iTime("US100", PERIOD_M15, 0);
   if(current_bar == 0)
      return;
   ulong position_ticket = 0;
   datetime opened_at = 0;
   ulong order_ticket = 0;
   const int positions =
      CountOwnedPositions(US100_PASSIVE_LIMIT,
                          position_ticket,
                          opened_at);
   const int orders = CountOwnedPassiveOrders(order_ticket);
   if(positions > 1 || orders > 1 ||
      (positions == 1 && orders == 1))
     {
      broker_mismatch = true;
      EngageSafetyStop("invalid passive broker multiplicity");
      return;
     }
   if(positions == 1)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "POSITION_OPEN";
      if(tracked_position_identifier[US100_PASSIVE_LIMIT] == 0 &&
         !ReconstructEntryTracking(US100_PASSIVE_LIMIT, position_ticket))
         return;
      if(last_decision_bar[US100_PASSIVE_LIMIT] == current_bar)
         return;
      double state = 0.0;
      double range_scale = 0.0;
      double decision_close = 0.0;
      if(!CalculatePassiveState(state, range_scale, decision_close))
         return;
      if(!PositionSelectByTicket(position_ticket))
         return;
      const ENUM_POSITION_TYPE position_type =
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      const int direction =
         (position_type == POSITION_TYPE_BUY ? 1 : -1);
      const int desired_direction =
         (state > 0.0 ? -1 : (state < 0.0 ? 1 : 0));
      const int held_bars =
         iBarShift("US100", PERIOD_M15, opened_at, false);
      const bool should_close =
         (held_bars >= PASSIVE_MAXIMUM_HOLD_BARS ||
          MathAbs(state) <= PASSIVE_EXIT_STRENGTH ||
          (desired_direction != 0 && desired_direction != direction));
      if(!should_close)
        {
         last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
         return;
        }
      if(CloseComponent(US100_PASSIVE_LIMIT, position_ticket))
        {
         last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
         passive_next_entry_current_bar =
            current_bar + 2 * PASSIVE_BAR_SECONDS;
         SaveState();
        }
      return;
     }

   if(orders == 1)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "PENDING_ORDER";
      if(tracked_passive_pending_order == 0 ||
         tracked_passive_pending_order != order_ticket)
        {
         broker_mismatch = true;
         EngageSafetyStop("passive broker order lacks local state");
         CancelPassivePendingOrder(order_ticket,
                                   "missing or mismatched local state");
         return;
        }
      if(!NewEntriesOperationallyAllowed())
         CancelPassivePendingOrder(order_ticket,
                                   "new entries not authorized");
      return;
     }
   if(tracked_passive_pending_order > 0 &&
      !HandleMissingPassivePendingOrder())
      return;
   if(last_decision_bar[US100_PASSIVE_LIMIT] == current_bar)
      return;
   BeginEntryCheck(US100_PASSIVE_LIMIT, current_bar, "CHECKING_SIGNAL");
   if(current_bar < passive_next_entry_current_bar)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "COOLDOWN";
      last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
      return;
     }
   if(TimeCurrent() - current_bar >
      InpMaxEntryDelayMinutes * 60)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "ENTRY_DELAY_EXCEEDED";
      last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
      return;
     }
   const datetime decision_bar = iTime("US100", PERIOD_M15, 1);
   if(decision_bar == 0 ||
      current_bar - decision_bar != PASSIVE_BAR_SECONDS ||
      !PassiveDecisionSessionAllows(decision_bar))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "OUTSIDE_DECISION_SESSION";
      last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
      return;
     }
   if(passive_last_feature_attempt_bar == current_bar &&
      TimeCurrent() - passive_last_feature_attempt_server < 5)
      return;
   passive_last_feature_attempt_bar = current_bar;
   passive_last_feature_attempt_server = TimeCurrent();
   double state = 0.0;
   double range_scale = 0.0;
   double decision_close = 0.0;
   if(!CalculatePassiveState(state, range_scale, decision_close))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed =
      (MathAbs(state) >= PASSIVE_ENTRY_STRENGTH);
   const int signal_direction =
      (signal_passed ? (state > 0.0 ? -1 : 1) : 0);
   SetEntrySignalCheck(US100_PASSIVE_LIMIT,
                       state,
                       signal_passed,
                       signal_direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!signal_passed)
     {
      last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
      return;
     }
   last_decision_bar[US100_PASSIVE_LIMIT] = current_bar;
   if(!NewEntriesOperationallyAllowed())
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "ENTRY_BLOCKED";
      return;
     }
   const int direction = signal_direction;
   const double raw_limit =
      decision_close -
      direction * PASSIVE_LIMIT_OFFSET_RANGE_SCALE * range_scale;
   const double limit_price = PassiveLimitPrice(raw_limit, direction);
   if(limit_price <= 0.0)
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "LIMIT_PRICE_INVALID";
      return;
     }
   entry_check_order_price[US100_PASSIVE_LIMIT] = limit_price;
   entry_check_volume[US100_PASSIVE_LIMIT] = InpBaseVolume;
   const datetime expiration =
      current_bar + PASSIVE_ACTIVATION_BARS * PASSIVE_BAR_SECONDS;
   if(!PersistDecisionUntil(US100_PASSIVE_LIMIT,
                            current_bar,
                            expiration))
     {
      entry_check_result[US100_PASSIVE_LIMIT] = "PERSISTENCE_FAILED";
      return;
     }
   PlacePassiveLimit(direction, state, limit_price, expiration);
   if(!FinalizeDecisionJournal(US100_PASSIVE_LIMIT,
                               entry_check_result[US100_PASSIVE_LIMIT]))
      entry_check_result[US100_PASSIVE_LIMIT] = "PERSISTENCE_FAILED";
  }


bool IsEntryWindow(const int hour,
                   const int minute,
                   int &elapsed_minutes)
  {
   MqlDateTime server = {};
   TimeCurrent(server);
   if(server.hour != hour || server.min < minute)
      return(false);
   elapsed_minutes = server.min - minute;
   return(elapsed_minutes < 30);
  }


bool PrepareEntry(const int component,
                  const int hour,
                  const int minute,
                  datetime &current_bar)
  {
   current_bar = iTime(COMPONENT_SYMBOLS[component],
                       COMPONENT_TIMEFRAMES[component],
                       0);
   if(current_bar == 0 || last_decision_bar[component] == current_bar)
      return(false);
   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned = CountOwnedPositions(component, ticket, opened_at);
   if(owned > 1)
     {
      BeginEntryCheck(component, current_bar, "DUPLICATE_EXPOSURE");
      broker_mismatch = true;
      EngageSafetyStop("duplicate component position before entry");
      PersistDecision(component, current_bar);
      return(false);
     }
   if(owned == 1)
     {
      BeginEntryCheck(component, current_bar, "EXISTING_EXPOSURE");
      PersistDecision(component, current_bar);
      return(false);
     }
   if(component == RC4_BOTH && rc4_shadow_occupied)
     {
      BeginEntryCheck(component, current_bar, "SHADOW_ACCEPTED_OCCUPANCY");
      ++rc4_shadow_entry_blocks;
      PersistDecision(component, current_bar);
      return(false);
     }
   int elapsed = 0;
   if(!IsEntryWindow(hour, minute, elapsed))
      return(false);
   if(elapsed > InpMaxEntryDelayMinutes)
     {
      BeginEntryCheck(component, current_bar, "ENTRY_DELAY_EXCEEDED");
      RecordEvent(component,
                  "SKIP_DELAY",
                  (double)elapsed,
                  0.0,
                  TimeToString(current_bar));
      PersistDecision(component, current_bar);
      return(false);
     }
   BeginEntryCheck(component, current_bar, "CHECKING_SIGNAL");
   return(true);
  }



void ProcessRC16Long()
  {
   datetime bar = 0;
   if(!PrepareEntry(RC16_LONG, 13, 30, bar))
      return;
   double feature = 0.0;
   if(!CalculateRangeCompression("US30", 16, feature))
     {
      entry_check_result[RC16_LONG] = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (feature >= 1.5);
   SetEntrySignalCheck(RC16_LONG,
                       feature,
                       signal_passed,
                       (signal_passed ? 1 : 0),
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(RC16_LONG, bar))
     {
      entry_check_result[RC16_LONG] = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(RC16_LONG, 1, feature);
      if(!FinalizeDecisionJournal(RC16_LONG, entry_check_result[RC16_LONG]))
         entry_check_result[RC16_LONG] = "PERSISTENCE_FAILED";
     }
  }


void ProcessRC4Both()
  {
   datetime bar = 0;
   if(!PrepareEntry(RC4_BOTH, 13, 0, bar))
      return;
   double feature = 0.0;
   if(!CalculateRangeCompression("US30", 4, feature))
     {
      entry_check_result[RC4_BOTH] = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (MathAbs(feature) >= 1.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? 1 : -1) : 0);
   SetEntrySignalCheck(RC4_BOTH,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(RC4_BOTH, bar))
     {
      entry_check_result[RC4_BOTH] = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(RC4_BOTH, direction, feature);
      if(!FinalizeDecisionJournal(RC4_BOTH, entry_check_result[RC4_BOTH]))
         entry_check_result[RC4_BOTH] = "PERSISTENCE_FAILED";
     }
  }


void ProcessUS100Cross()
  {
   datetime bar = 0;
   if(!PrepareEntry(US100_CROSS, 17, 0, bar))
      return;
   if(IsUSEquityClosureDate())
     {
      entry_check_result[US100_CROSS] = "SESSION_EXCLUDED";
      RecordEvent(US100_CROSS,
                  "SKIP_SESSION",
                  0.0,
                  0.0,
                  TimeToString(ServerMidnight(), TIME_DATE));
      PersistDecision(US100_CROSS, bar);
      return;
     }
   double feature = 0.0;
   if(!CalculateUS100RelativeMomentum(feature))
     {
      entry_check_result[US100_CROSS] = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (MathAbs(feature) >= 0.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? 1 : -1) : 0);
   SetEntrySignalCheck(US100_CROSS,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(US100_CROSS, bar))
     {
      entry_check_result[US100_CROSS] = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(US100_CROSS, direction, feature);
      if(!FinalizeDecisionJournal(US100_CROSS,
                                  entry_check_result[US100_CROSS]))
         entry_check_result[US100_CROSS] = "PERSISTENCE_FAILED";
     }
  }


void ProcessUS30Pressure()
  {
   datetime bar = 0;
   if(!PrepareEntry(US30_PRESSURE, 15, 0, bar))
      return;
   double feature = 0.0;
   if(!CalculateIntradayRangePressure("US30", feature))
     {
      entry_check_result[US30_PRESSURE] = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (MathAbs(feature) >= 0.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? 1 : -1) : 0);
   SetEntrySignalCheck(US30_PRESSURE,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(US30_PRESSURE, bar))
     {
      entry_check_result[US30_PRESSURE] = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(US30_PRESSURE, direction, feature);
      if(!FinalizeDecisionJournal(US30_PRESSURE,
                                  entry_check_result[US30_PRESSURE]))
         entry_check_result[US30_PRESSURE] = "PERSISTENCE_FAILED";
     }
  }


void ProcessUS30ReturnReversalLong()
  {
   datetime bar = 0;
   if(!PrepareEntry(US30_RETURN_REV_LONG, 16, 0, bar))
      return;
   if(IsUSEquityClosureDate())
     {
      entry_check_result[US30_RETURN_REV_LONG] = "SESSION_EXCLUDED";
      RecordEvent(US30_RETURN_REV_LONG,
                  "SKIP_SESSION",
                  0.0,
                  0.0,
                  TimeToString(ServerMidnight(), TIME_DATE));
      PersistDecision(US30_RETURN_REV_LONG, bar);
      return;
     }
   double feature = 0.0;
   if(!CalculateUS30ReturnImpulse(feature))
     {
      entry_check_result[US30_RETURN_REV_LONG] = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (feature <= -0.5);
   SetEntrySignalCheck(US30_RETURN_REV_LONG,
                       feature,
                       signal_passed,
                       (signal_passed ? 1 : 0),
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(US30_RETURN_REV_LONG, bar))
     {
      entry_check_result[US30_RETURN_REV_LONG] =
         "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(US30_RETURN_REV_LONG, 1, feature);
      if(!FinalizeDecisionJournal(US30_RETURN_REV_LONG,
                                  entry_check_result[
                                     US30_RETURN_REV_LONG]))
         entry_check_result[US30_RETURN_REV_LONG] =
            "PERSISTENCE_FAILED";
     }
  }


bool InitializeConnectedRuntime()
  {
   if(runtime_ready)
      return(true);
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      return(false);
   if(!ConnectedEnvironmentCompatible())
     {
      if(!runtime_error_logged)
        {
         PrintFormat("%s incompatible connected broker/account/contract",
                     EXECUTION_VERSION);
         runtime_error_logged = true;
        }
      return(false);
     }

    const bool state_files_exist =
       (FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B));
   ResetRuntimeState();
   const bool recovered = (!tester_mode && LoadState());
   if(!recovered)
     {
      ResetRuntimeState();
      if(state_files_exist && !tester_mode)
        {
         broker_mismatch = true;
         safety_stopped = true;
         PrintFormat("%s state snapshots exist but neither is valid; "
                     "new entries remain blocked",
                     EXECUTION_VERSION);
        }
      else if(!tester_mode && HasOwnedDealHistory())
        {
         broker_mismatch = true;
         safety_stopped = true;
         PrintFormat("%s owned broker history exists without state; "
                     "new entries remain blocked",
                     EXECUTION_VERSION);
         }
      }

   if(tester_mode)
      bound_account_login = 0;
   else if(bound_account_login <= 0)
      bound_account_login =
         (long)AccountInfoInteger(ACCOUNT_LOGIN);

   runtime_ready = true;
   UpdateAccountRisk();
   const bool broker_reconciled = ReconcileBrokerState(true);
   if(recovered && broker_reconciled && !ReconcileArcPendingModify(true))
      EngageSafetyStop("restart RC4 stop journal could not be resolved");
   if(recovered && !ResolveRestartDecisionJournal())
      EngageSafetyStop("restart decision journal could not be resolved");
   UpdateSizingDay();
   RecordEvent(-1,
               (recovered ? "RESUME" : "START"),
               stressed_balance,
               (double)state_sequence,
               (NewEntriesOperationallyAllowed() ? "entries-enabled" :
                                                   "entries-disabled"));
   SaveState();
   PrintFormat("%s initialized portfolio=%s recovered=%s "
               "entries=%s safety=%s sequence=%I64d",
               EXECUTION_VERSION,
               PORTFOLIO_ID,
               (recovered ? "true" : "false"),
               (NewEntriesOperationallyAllowed() ? "enabled" : "disabled"),
               (safety_stopped ? "true" : "false"),
               state_sequence);
   return(true);
  }


int OnInit()
  {
   tester_mode = (bool)MQLInfoInteger(MQL_TESTER);
   if(_Symbol != "US30" || _Period != PERIOD_M30 ||
       MathAbs(InpReferenceCapitalUSD - 100.0) > 1.0e-9 ||
       !MathIsValidNumber(InpPriorProjectRealizedNetUSD) ||
       MathAbs(InpPriorProjectRealizedNetUSD) > 1.0e9 ||
       InpReferenceCapitalUSD + InpPriorProjectRealizedNetUSD <= 0.0 ||
       MathAbs(InpBaseVolume - 0.01) > 1.0e-9 ||
       MathAbs(InpAdditionStepUSD - 150.0) > 1.0e-9 ||
       MathAbs(InpMaximumMarginFraction - 0.45) > 1.0e-9 ||
       MathAbs(InpMaximumPositionRiskFraction - 0.04) > 1.0e-9 ||
       MathAbs(InpMaximumAggregateRiskFraction - 0.12) > 1.0e-9 ||
       MathAbs(InpUnmodelledRiskReserveFraction - 0.25) > 1.0e-9 ||
       MathAbs(InpStopPlacementHeadroomFraction - 0.25) > 1.0e-9 ||
       InpMaxEntryDelayMinutes != 2 || InpDeviationPoints != 100 ||
       InpExpectedLiveAccountLogin < 0 ||
       (!tester_mode && InpAllowNewEntries &&
        InpExpectedLiveAccountLogin <= 0) ||
       InpEventCapacity < 256 || InpEventCapacity > 8192 ||
      InpSnapshotSeconds < 10 || InpSnapshotSeconds > 600)
      return(INIT_PARAMETERS_INCORRECT);
   FolderCreate("ZetaTerminus");
   FolderCreate("ZetaTerminus\\live");
   if(tester_mode)
      ResetTesterArtifacts();
   if(!AcquireRuntimeOwnership())
      return(INIT_FAILED);
   ResetRuntimeState();
   if(!tester_mode && !EventSetTimer(2))
     {
      PrintFormat("%s timer initialization failed error=%d",
                  EXECUTION_VERSION, GetLastError());
      ReleaseRuntimeOwnership();
      return(INIT_FAILED);
     }
   if(!InitializeConnectedRuntime())
      PrintFormat("%s waiting for the saved FPMarkets connection",
                  EXECUTION_VERSION);
   return(INIT_SUCCEEDED);
  }


bool TesterDataRetryRequired(const datetime current_server,
                             const datetime us100_m15_bar)
  {
   MqlDateTime server = {};
   TimeToStruct(current_server, server);
   const bool fixed_data_retry =
      ((entry_check_result[RC4_BOTH] == "DATA_UNAVAILABLE" &&
        server.hour == 13 && server.min >= 0 && server.min <= 2) ||
       (entry_check_result[RC16_LONG] == "DATA_UNAVAILABLE" &&
        server.hour == 13 && server.min >= 30 && server.min <= 32) ||
       (entry_check_result[US30_PRESSURE] == "DATA_UNAVAILABLE" &&
        server.hour == 15 && server.min >= 0 && server.min <= 2) ||
       (entry_check_result[US30_RETURN_REV_LONG] == "DATA_UNAVAILABLE" &&
        server.hour == 16 && server.min >= 0 && server.min <= 2) ||
       (entry_check_result[US100_CROSS] == "DATA_UNAVAILABLE" &&
        server.hour == 17 && server.min >= 0 && server.min <= 2));
   const bool passive_data_retry =
      (tracked_passive_pending_order == 0 &&
       (entry_check_result[US100_PASSIVE_LIMIT] == "DATA_UNAVAILABLE" ||
        (tracked_position_identifier[US100_PASSIVE_LIMIT] > 0 &&
         us100_m15_bar > 0 &&
         last_decision_bar[US100_PASSIVE_LIMIT] != us100_m15_bar)));
   const datetime slot_start =
      (datetime)(((long)current_server / PASSIVE_BAR_SECONDS) *
                 PASSIVE_BAR_SECONDS);
   const long seconds_into_slot =
      (long)current_server - (long)slot_start;
   const bool bounded_native_sync_retry =
      (us100_m15_bar > 0 && us100_m15_bar < slot_start &&
       seconds_into_slot >= 0 &&
       seconds_into_slot <= InpMaxEntryDelayMinutes * 60);
   return(fixed_data_retry || passive_data_retry ||
          bounded_native_sync_retry);
  }


void OnTick()
  {
   if(!runtime_ready && !InitializeConnectedRuntime())
      return;

   datetime current_server = 0;
   datetime us100_m15_bar = 0;
   bool tester_clock_dispatch = false;
   bool tester_retry_dispatch = false;
   if(tester_mode)
     {
      // Shadow occupancy must observe every real tick so an intrabar touch of
      // the accepted original stop cannot be missed by the tester scheduler.
      if(rc4_shadow_occupied)
         ProcessRC4ShadowOccupancy();
      current_server = TimeCurrent();
      const long current_m15_slot =
         (long)current_server / PASSIVE_BAR_SECONDS;
      tester_clock_dispatch =
         (current_m15_slot != tester_last_m15_slot);
      const bool transaction_gate =
         (pending_reconcile || passive_cancel_pending ||
          arc_modify_retry_pending);
      tester_retry_dispatch = tester_data_retry_active;
      if(!tester_clock_dispatch && !transaction_gate &&
         !tester_retry_dispatch)
         return;
      if(tester_clock_dispatch)
         tester_last_m15_slot = current_m15_slot;
     }
   else if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      if(tracked_passive_pending_order > 0)
         DeferPassivePendingCancellation(
            tracked_passive_pending_order,
            "tick observed disconnected terminal");
      return;
     }
   if(!EnforceLiveAccountIdentity())
      return;
   UpdateAccountRisk();
   if(tester_mode)
     {
      us100_m15_bar = iTime("US100", PERIOD_M15, 0);
      const bool passive_order_disappeared =
         (tracked_passive_pending_order > 0 &&
          !OrderSelect(tracked_passive_pending_order));
      if(passive_order_disappeared)
         pending_reconcile = true;
      ++tester_dispatched_ticks;
      if(tester_clock_dispatch)
         ++tester_clock_dispatches;
      if(pending_reconcile || passive_cancel_pending ||
         passive_order_disappeared)
         ++tester_transaction_dispatches;
      if(tester_retry_dispatch)
         ++tester_retry_dispatches;
     }
   UpdateSizingDay();
   if(!AuditPositionOwnership())
     {
      MakeExistingRiskSafe("tick ownership/protection audit failed");
      return;
     }
   if(pending_reconcile || passive_cancel_pending ||
      (!tester_mode && TimeCurrent() - last_reconcile_server >= 60))
     {
      const bool deferred_cancel_requires_reconciliation =
         passive_cancel_pending;
      const bool reconciled = ReconcileBrokerState(false);
      if(deferred_cancel_requires_reconciliation && !reconciled)
         return;
     }
   ProcessClosures();
   ProcessPassiveLimit();
   if(!tester_mode)
      ProcessRC4ShadowOccupancy();
   if(NewEntriesOperationallyAllowed())
     {
      ProcessRC4Both();
      ProcessRC16Long();
      ProcessUS30Pressure();
      ProcessUS30ReturnReversalLong();
      ProcessUS100Cross();
     }
   ProcessRC4AdverseRiskCompression();
   if(tester_mode)
      tester_data_retry_active =
         TesterDataRetryRequired(current_server, us100_m15_bar);
  }


void OnTimer()
  {
   if(tester_mode)
      return;
   if(!runtime_ready && !InitializeConnectedRuntime())
      return;
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      if(tracked_passive_pending_order > 0)
         DeferPassivePendingCancellation(
            tracked_passive_pending_order,
            "timer observed disconnected terminal");
      return;
     }
   if(!EnforceLiveAccountIdentity())
      return;
   UpdateAccountRisk();
   if(!ReconcileBrokerState(false))
      return;
   if(tracked_passive_pending_order > 0 &&
      (passive_cancel_pending || !NewEntriesOperationallyAllowed()))
     {
      ulong order_ticket = 0;
      if(CountOwnedPassiveOrders(order_ticket) == 1)
         CancelPassivePendingOrder(order_ticket,
                                   "new entries disabled by runtime");
     }
   if((long)TimeGMT() - (long)last_snapshot_utc >= InpSnapshotSeconds)
      SaveState();
  }


void OnTradeTransaction(const MqlTradeTransaction &transaction,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(runtime_ready && !trade_operation_active)
      pending_reconcile = true;
  }


void OnDeinit(const int reason)
  {
   if(!tester_mode)
      EventKillTimer();
   if(runtime_ready)
     {
      UpdateAccountRisk();
      RecordEvent(-1,
                  "STOP",
                  stressed_balance,
                  (double)reason,
                  (safety_stopped ? "safety" : "normal"));
      SaveState();
     }
   PrintFormat("%s final portfolio=%s reason=%d stressed_balance_2x=%.4f "
                "stressed_net_2x=%.4f stressed_max_closed_dd=%.4f "
                "project_realized_net=%.4f project_stage_balance=%.4f "
                "safety_stopped=%s persistence_failed=%s "
                "broker_mismatch=%s foreign_exposure=%s "
                "protection_calc_failures=%I64d risk_admission_skips=%I64d "
                "protection_mismatches=%I64d stop_loss_exits=%I64d "
                "aggregate_planned_risk=%.4f max_aggregate_planned_risk=%.4f",
               EXECUTION_VERSION,
               PORTFOLIO_ID,
               reason,
                stressed_balance,
                stressed_balance - InpReferenceCapitalUSD,
                stressed_maximum_closed_drawdown,
                project_realized_net,
                ProjectStageBalance(),
               (safety_stopped ? "true" : "false"),
                (persistence_failed ? "true" : "false"),
                (broker_mismatch ? "true" : "false"),
                (foreign_exposure ? "true" : "false"),
                protection_calculation_failures,
                risk_admission_skips,
                protection_mismatches,
                stop_loss_exits,
                TrackedAggregatePlannedRisk(),
                maximum_aggregate_planned_risk_usd);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      PrintFormat("%s component=%s closed=%I64d stressed_net_2x=%.4f",
                  EXECUTION_VERSION,
                  COMPONENT_IDS[component],
                  closed_trades[component],
                  component_stressed_net[component]);
   PrintFormat("%s tester_scheduler dispatched_ticks=%I64d "
               "clock_dispatches=%I64d transaction_dispatches=%I64d "
               "retry_dispatches=%I64d",
               EXECUTION_VERSION,
               tester_dispatched_ticks,
               tester_clock_dispatches,
               tester_transaction_dispatches,
               tester_retry_dispatches);
   PrintFormat("%s arc_checkpoints=%I64d adverse_triggers=%I64d "
               "compressions_placed=%I64d compression_refusals=%I64d "
                "data_unavailable=%I64d modify_pending=%s "
                "pending_stop=%.5f retry_pending=%s retry_consumed=%s "
                "retry_after_msc=%I64d retry_initial_retcode=%u "
                "retry_intents=%I64d retry_attempts=%I64d "
                "retry_successes=%I64d "
                "retry_adoptions=%I64d retry_holds=%I64d "
                "shadow_occupied=%s "
               "shadow_activations=%I64d shadow_stop_releases=%I64d "
               "shadow_deadline_releases=%I64d shadow_entry_blocks=%I64d "
               "shadow_last_observed_msc=%I64d shadow_cursor_ordinal=%I64d "
               "catchup_required=%s "
               "catchup_scans=%I64d catchup_ticks=%I64d "
               "catchup_stop_releases=%I64d catchup_failures=%I64d "
               "cursor_checkpoint_observation_bucket=%I64d "
               "cursor_checkpoint_last_completed_bucket=%I64d "
               "cursor_checkpoint_last_persisted=%I64d/%I64d "
               "cursor_checkpoint_eligible=%I64d "
               "cursor_checkpoint_persisted=%I64d "
               "cursor_checkpoint_save_failures=%I64d "
               "cursor_checkpoint_readback_failures=%I64d "
               "cursor_checkpoint_event_failures=%I64d "
               "cursor_checkpoint_duplicate_bucket_failures=%I64d "
               "cursor_checkpoint_regressions=%I64d "
               "cursor_checkpoint_pending=%s",
               EXECUTION_VERSION,
               arc_checkpoints,
               arc_adverse_triggers,
               arc_compressions_placed,
               arc_compression_refusals,
                arc_data_unavailable,
                (arc_modify_pending ? "true" : "false"),
                arc_pending_stop_loss,
                (arc_modify_retry_pending ? "true" : "false"),
                (arc_modify_retry_consumed ? "true" : "false"),
                arc_modify_retry_after_msc,
                arc_modify_retry_initial_retcode,
                arc_modify_retry_intents,
                arc_modify_retry_attempts,
                arc_modify_retry_successes,
                arc_modify_retry_adoptions,
                arc_modify_retry_holds,
                (rc4_shadow_occupied ? "true" : "false"),
               rc4_shadow_activations,
               rc4_shadow_stop_releases,
               rc4_shadow_deadline_releases,
               rc4_shadow_entry_blocks,
               rc4_shadow_last_observed_msc,
               rc4_shadow_cursor_ordinal,
               (rc4_shadow_catchup_required ? "true" : "false"),
               rc4_shadow_catchup_scans,
               rc4_shadow_catchup_ticks,
               rc4_shadow_catchup_stop_releases,
               rc4_shadow_catchup_failures,
               rc4_shadow_cursor_checkpoint_observation_bucket,
               rc4_shadow_cursor_checkpoint_last_completed_bucket,
               rc4_shadow_cursor_checkpoint_last_persisted_msc,
               rc4_shadow_cursor_checkpoint_last_persisted_ordinal,
               rc4_shadow_cursor_checkpoint_eligible,
               rc4_shadow_cursor_checkpoint_persisted,
               rc4_shadow_cursor_checkpoint_save_failures,
               rc4_shadow_cursor_checkpoint_readback_failures,
               rc4_shadow_cursor_checkpoint_event_failures,
               rc4_shadow_cursor_checkpoint_duplicate_bucket_failures,
               rc4_shadow_cursor_checkpoint_regressions,
               (rc4_shadow_cursor_checkpoint_pending ? "true" : "false"));
   PrintFormat("%s activation_seal eligible=%I64d sealed=%I64d "
               "pending=%I64d save_attempts=%I64d save_failures=%I64d "
               "readbacks=%I64d readback_failures=%I64d failures=%I64d "
               "ambiguities=%I64d sealed_cursor=%I64d/%I64d "
               "pre_boundary_consumed=%I64d current_sealed=%s "
               "current_pending=%s current_boundary=%I64d/%I64d",
               EXECUTION_VERSION,
               rc4_shadow_activation_seal_eligible,
               rc4_shadow_activation_seal_sealed,
               rc4_shadow_activation_seal_pending_count,
               rc4_shadow_activation_seal_save_attempts,
               rc4_shadow_activation_seal_save_failures,
               rc4_shadow_activation_seal_readbacks,
               rc4_shadow_activation_seal_readback_failures,
               rc4_shadow_activation_seal_failures,
               rc4_shadow_activation_seal_ambiguities,
               rc4_shadow_activation_last_sealed_msc,
               rc4_shadow_activation_last_sealed_ordinal,
               rc4_shadow_activation_pre_boundary_consumed,
               (rc4_shadow_activation_sealed ? "true" : "false"),
               (rc4_shadow_activation_seal_pending ? "true" : "false"),
               rc4_shadow_activation_boundary_msc,
               rc4_shadow_activation_boundary_ordinal);
   ReleaseRuntimeOwnership();
  }
