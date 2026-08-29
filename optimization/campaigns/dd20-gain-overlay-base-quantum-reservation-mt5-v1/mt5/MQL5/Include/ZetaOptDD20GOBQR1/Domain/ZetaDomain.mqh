#ifndef ZETA_OPT_DD20_GOBQR1_DOMAIN_MQH
#define ZETA_OPT_DD20_GOBQR1_DOMAIN_MQH

// Isolated tester-only optimization copy of the frozen RLO1 source.
// The candidate preserves the component-local stressed-R state and reserves
// one base position-risk quantum from incremental gain-overlay volume only.

input double InpReferenceCapitalUSD  = 100.0;
input double InpPriorProjectRealizedNetUSD = 0.0;
input double InpBaseVolume           = 0.01;
input double InpAdditionStepUSD      = 150.0;
input double InpMaximumMarginFraction = 0.45;
input double InpMaximumPositionRiskFraction = 0.04;
input double InpMaximumAggregateRiskFraction = 0.18;
input double InpRC16BaseWeight = 1.6;
input double InpRC4BaseWeight = 0.8;
input double InpUS100CrossBaseWeight = 0.4;
input double InpUS30PressureBaseWeight = 3.2;
input double InpUS30ReturnBaseWeight = 1.2;
input double InpUS100PassiveBaseWeight = 0.0;
input int    InpComponentStateLookback = 40;
input double InpComponentStateMeanBandR = 0.10;
input double InpComponentStateLossOverlay = 0.0;
input double InpComponentStateGainOverlay = 1.125;
input double InpGainOverlayBaseQuantumReserveFraction = 0.04;
input double InpUnmodelledRiskReserveFraction = 0.25;
input double InpStopPlacementHeadroomFraction = 0.25;
input int    InpMaxEntryDelayMinutes = 2;
input int    InpDeviationPoints      = 100;
input bool   InpAllowNewEntries       = false;
input long   InpExpectedLiveAccountLogin = 0;
input int    InpEventCapacity         = 4096;
input int    InpSnapshotSeconds       = 60;

const string EXECUTION_VERSION =
   "zt-opt-live-v7-dd20-gain-overlay-base-quantum-reservation-mt5-v1";
const string ECONOMIC_VERSION =
   "zt-next-pre500-finite-risk-portfolio-v7-modular-parent-b70-v6r6";
const string PROJECT_ID = "project-zeta-terminus-next";
const string SCHEMA_VERSION = "opt-dd20-gobqr-mt5-1";
const string RELEASE_ID = "OPT-LIVE-V7-DD20GOBQR1-20260829";
const string PORTFOLIO_ID = "ZT-OPT-LIVE-V7-DD20GOBQR1-20260829";
const string ECONOMIC_FINGERPRINT =
   "parent-rlo1-b32e7e176f2e-ref100-base0.01-step150-posrisk0.04-aggrisk0.18-baseweights-1.6-0.8-0.4-3.2-1.2-0-component-stressed-r-lookback40-band0.10-loss0-gain1.125-gain-increment-reserve0.04";
const string EXECUTION_FINGERPRINT =
   "isolated-tester-only-dd20-gain-overlay-base-quantum-reservation-one-candidate-real-tick-v1";
const string STATE_MARKER =
   "ZT_OPT_LIVE_V7_DD20_GAIN_OVERLAY_BASE_QUANTUM_RESERVATION_STATE_V1";
const string STATE_PATH_A =
   "ZetaOptimization\\dd20-gobqr1\\state\\state-a.csv";
const string STATE_PATH_B =
   "ZetaOptimization\\dd20-gobqr1\\state\\state-b.csv";
const string EVENT_PATH_A =
   "ZetaOptimization\\dd20-gobqr1\\state\\events-a.csv";
const string EVENT_PATH_B =
   "ZetaOptimization\\dd20-gobqr1\\state\\events-b.csv";
const string CURRENT_SNAPSHOT_PATH_A =
   "ZetaOptimization\\dd20-gobqr1\\state\\current-a.csv";
const string CURRENT_SNAPSHOT_PATH_B =
   "ZetaOptimization\\dd20-gobqr1\\state\\current-b.csv";
const string OWNERSHIP_PATH =
   "ZetaOptimization\\dd20-gobqr1\\state\\runtime.lock";
const string RESEARCH_OBSERVATION_DIRECTORY =
   "ZetaOptimization\\dd20-gobqr1\\research";
const string RESEARCH_OBSERVATION_SCHEMA =
   "zeta-optimization-dd20-gain-overlay-base-quantum-reservation-observation-v1";
const string RESEARCH_OBSERVATION_MARKER =
   "ZT_OPT_DD20_GAIN_OVERLAY_BASE_QUANTUM_RESERVATION_OBSERVATION_STATE_V1";
const string RESEARCH_OBSERVATION_STATE_PATH_A =
   "ZetaOptimization\\dd20-gobqr1\\research\\research-state-a.csv";
const string RESEARCH_OBSERVATION_STATE_PATH_B =
   "ZetaOptimization\\dd20-gobqr1\\research\\research-state-b.csv";
const string RESEARCH_CANDIDATE_LEDGER_PATH =
   "ZetaOptimization\\dd20-gobqr1\\research\\research-candidates.csv";
const string RESEARCH_LIFECYCLE_LEDGER_PATH =
   "ZetaOptimization\\dd20-gobqr1\\research\\research-lifecycles.csv";
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
const ulong MAGIC_RC16_LONG = 260829871;
const ulong MAGIC_RC4_BOTH = 260829872;
const ulong MAGIC_US100_CROSS = 260829873;
const ulong MAGIC_US30_PRESSURE = 260829874;
const ulong MAGIC_US30_RETURN = 260829875;
const ulong MAGIC_US100_PASSIVE_LIMIT = 260829876;
#define COMPONENT_EQUITY_STATE_MAX_LOOKBACK 40

struct ComponentDefinition
  {
   string id;
   string symbol;
   ENUM_TIMEFRAMES timeframe;
   int hold_bars;
   ulong magic;
  };

struct ComponentState
  {
   datetime last_decision_bar;
   datetime entry_check_bar;
   int entry_check_signal_known;
   int entry_check_signal_passed;
   double entry_check_signal_value;
   int entry_check_direction;
   double entry_check_order_price;
   double entry_check_volume;
   double entry_check_stop_loss;
   double entry_check_planned_risk_usd;
   string entry_check_result;
   datetime last_close_attempt_server;
   double entry_spread_price;
   double entry_transaction_cost;
   double entry_adverse_slippage;
   long closed_trades;
   double stressed_net;
   ulong position_identifier;
   ulong last_processed_exit_deal;
   long last_processed_exit_time_msc;
   bool lifecycle_stop_loss_seen;
   datetime entry_time_server;
   int entry_direction;
   double entry_volume;
   double entry_feature;
   double entry_stop_loss;
   double entry_planned_risk_usd;
   bool entry_cost_known;
  };

struct PortfolioState
  {
   datetime sizing_server_day;
   int day_volume_multiplier;
   bool safety_stopped;
   double stressed_balance;
   double stressed_peak;
   double stressed_maximum_closed_drawdown;
   double project_realized_net;
   double account_peak_equity;
   double account_maximum_drawdown;
   double maximum_aggregate_planned_risk_usd;
   long bound_account_login;
  };

struct ExecutionState
  {
   bool runtime_ready;
   bool trade_operation_active;
   bool pending_reconcile;
   bool broker_mismatch;
   bool foreign_exposure;
   ulong passive_pending_order;
   bool passive_cancel_pending;
   bool rc4_shadow_occupied;
   bool rc4_shadow_activation_sealed;
   bool rc4_shadow_activation_seal_pending;
   bool arc_modify_pending;
   bool arc_modify_retry_pending;
   long arc_modify_retry_after_msc;
  };

// Transient copy of a completed broker exit. It is intentionally outside the
// durable trading-state schema and is consumed only after core SaveState().
struct ResearchExitSnapshot
  {
   int component;
   ulong deal_ticket;
   ulong position_identifier;
   datetime entry_time_server;
   int direction;
   double entry_volume;
   double entry_feature;
   double entry_stop_loss;
   double entry_planned_risk_usd;
   double entry_spread_price;
   double entry_transaction_cost;
   double entry_adverse_slippage;
   bool entry_cost_known;
   double deal_net;
   double stressed_net;
   bool full_exit;
   double remaining_volume;
   double execution_price;
   long deal_time_msc;
   ENUM_DEAL_REASON exit_reason;
   string core_event_name;
  };

struct DecisionIntent
  {
   int component;
   datetime decision_bar;
   int direction;
   double signal_value;
   ENUM_ORDER_TYPE order_type;
   bool order_type_known;
   double intended_price;
   datetime expiration;
   datetime deadline;
   datetime attempted_server;
   ulong adopted_ticket;
   double volume;
   double stop_loss;
   double planned_risk_usd;
   int journal_stage;
  };

ComponentDefinition component_definitions[COMPONENT_COUNT];
ComponentState component_states[COMPONENT_COUNT];
PortfolioState portfolio_state;
ExecutionState execution_state;
DecisionIntent decision_intent;

void InitializeComponentDefinitions()
  {
   component_definitions[RC16_LONG].id = "ZT-M30-US30-RANGE-COMP-61f61deaba";
   component_definitions[RC16_LONG].symbol = "US30";
   component_definitions[RC16_LONG].timeframe = PERIOD_M30;
   component_definitions[RC16_LONG].hold_bars = 8;
   component_definitions[RC16_LONG].magic = MAGIC_RC16_LONG;

   component_definitions[RC4_BOTH].id = "ZT-M30-US30-RANGE-COMP-64efb16616";
   component_definitions[RC4_BOTH].symbol = "US30";
   component_definitions[RC4_BOTH].timeframe = PERIOD_M30;
   component_definitions[RC4_BOTH].hold_bars = 12;
   component_definitions[RC4_BOTH].magic = MAGIC_RC4_BOTH;

   component_definitions[US100_CROSS].id = "ZT-H1-US100-CROSS-IN-14b72317b7";
   component_definitions[US100_CROSS].symbol = "US100";
   component_definitions[US100_CROSS].timeframe = PERIOD_H1;
   component_definitions[US100_CROSS].hold_bars = 4;
   component_definitions[US100_CROSS].magic = MAGIC_US100_CROSS;

   component_definitions[US30_PRESSURE].id = "ZT-M30-US30-INTRADAY-R-2eb111fc46";
   component_definitions[US30_PRESSURE].symbol = "US30";
   component_definitions[US30_PRESSURE].timeframe = PERIOD_M30;
   component_definitions[US30_PRESSURE].hold_bars = 8;
   component_definitions[US30_PRESSURE].magic = MAGIC_US30_PRESSURE;

   component_definitions[US30_RETURN_REV_LONG].id = "ZT-H1-US30-RETURN-I-c870a788ec";
   component_definitions[US30_RETURN_REV_LONG].symbol = "US30";
   component_definitions[US30_RETURN_REV_LONG].timeframe = PERIOD_H1;
   component_definitions[US30_RETURN_REV_LONG].hold_bars = 6;
   component_definitions[US30_RETURN_REV_LONG].magic = MAGIC_US30_RETURN;

   component_definitions[US100_PASSIVE_LIMIT].id = "ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8";
   component_definitions[US100_PASSIVE_LIMIT].symbol = "US100";
   component_definitions[US100_PASSIVE_LIMIT].timeframe = PERIOD_M15;
   component_definitions[US100_PASSIVE_LIMIT].hold_bars = 16;
   component_definitions[US100_PASSIVE_LIMIT].magic = MAGIC_US100_PASSIVE_LIMIT;
  }

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
long state_sequence = 0;
long event_records = 0;
long event_segment_records = 0;
int event_segment = 0;
datetime started_utc = 0;
datetime last_snapshot_utc = 0;
datetime last_reconcile_server = 0;
bool persistence_failed = false;
bool persistence_error_logged = false;
bool foreign_exposure_logged = false;
bool runtime_error_logged = false;
bool tester_mode = false;
bool server_clock_contract_logged = false;
bool server_clock_mismatch_logged = false;
datetime unverified_calendar_logged_day = 0;
int ownership_handle = INVALID_HANDLE;
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
long journal_signal_decisions = 0;
long journal_order_attempts = 0;
long journal_broker_adoptions = 0;
long journal_restart_resolutions = 0;
ulong arc_lifecycle_identifier = 0;
datetime arc_last_attempt_bar = 0;
bool arc_checkpoint_evaluated = false;
bool arc_lifecycle_compressed = false;
double arc_original_stop_loss = 0.0;
double arc_pending_stop_loss = 0.0;
bool arc_modify_retry_consumed = false;
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
double component_equity_state_r[COMPONENT_COUNT][COMPONENT_EQUITY_STATE_MAX_LOOKBACK];
int component_equity_state_count[COMPONENT_COUNT];
int component_equity_state_next[COMPONENT_COUNT];
long component_equity_state_full_closes[COMPONENT_COUNT];
long component_equity_state_partial_exits[COMPONENT_COUNT];
long component_equity_state_volume_evaluations[COMPONENT_COUNT];
long component_equity_state_loss_evaluations[COMPONENT_COUNT];
long component_equity_state_neutral_evaluations[COMPONENT_COUNT];
long component_equity_state_gain_evaluations[COMPONENT_COUNT];
ulong component_equity_lifecycle_identifier[COMPONENT_COUNT];
double component_equity_lifecycle_original_planned_risk[COMPONENT_COUNT];
double component_equity_lifecycle_stressed_net[COMPONENT_COUNT];
long component_equity_state_faults = 0;
long gain_overlay_reserve_evaluations = 0;
long gain_overlay_reserve_bindings = 0;
long gain_overlay_reserve_steps_removed = 0;
long gain_overlay_reserve_neutral_floor_preserved = 0;

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
void InitializeResearchObservation();
void ResearchSampleOpenPositions();
void SaveResearchObservationState();
void ResearchCaptureSignalContext(const int component,
                                  const datetime bar,
                                  const double feature,
                                  const bool passed,
                                  const int direction);
void ResearchCaptureAdmissionContext(const int component,
                                     const string reason,
                                     const double attempted_planned_risk,
                                     const double attempted_aggregate_after,
                                     const double position_cap,
                                     const double aggregate_cap);
void ResearchRecordCandidateOutcome(const int component,
                                    const string stage,
                                    const string result,
                                    const string detail);
void ResearchRecordGateObservation(const int component,
                                   const datetime bar,
                                   const string result);
void ResearchHandleExitDeal(const ResearchExitSnapshot &snapshot);


#endif
