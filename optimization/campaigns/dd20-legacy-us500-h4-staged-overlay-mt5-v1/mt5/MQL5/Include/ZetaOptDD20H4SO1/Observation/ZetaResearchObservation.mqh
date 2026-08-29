#ifndef ZETA_OPT_DD20_H4SO1_RESEARCH_OBSERVATION_MQH
#define ZETA_OPT_DD20_H4SO1_RESEARCH_OBSERVATION_MQH

// Optional Codex research telemetry. Nothing in this module authorizes,
// blocks, sizes, modifies or closes an order. All writes occur after the core
// trading decision/state transition, and every failure remains non-fatal.

struct ResearchLifecycleObservation
  {
   ulong position_identifier;
   datetime entry_time_server;
   datetime segment_started_server;
   int direction;
   double volume;
   double entry_price;
   double entry_feature;
   double entry_stop_loss;
   double planned_risk_usd;
   double entry_spread_price;
   double entry_transaction_cost;
   double entry_adverse_slippage;
   bool entry_cost_known;
   double last_mark_profit_usd;
   double peak_mark_profit_usd;
   double trough_mark_profit_usd;
   double peak_mark_r;
   double trough_mark_r;
   double maximum_giveback_usd;
   double maximum_giveback_r;
   datetime peak_time_server;
   datetime trough_time_server;
   long mark_samples;
   double realized_net_usd;
   double stressed_net_usd;
   bool partial_observation;
   bool birth_logged;
   int first_peer_component;
   datetime first_peer_exit_server;
   int entry_active_mask;
   int entry_reserved_mask;
   int entry_active_slots;
   int entry_reserved_slots;
   double entry_aggregate_risk_usd;
   double entry_us30_risk_usd;
   double entry_us100_risk_usd;
   double entry_aggregate_headroom_usd;
   int prior_signal_direction;
   string signal_relation;
   bool rc4_sell_warning;
  };

ResearchLifecycleObservation research_lifecycles[COMPONENT_COUNT];
long research_state_sequence = 0;
datetime research_last_state_utc = 0;
long research_dropped_records = 0;
bool research_observation_initialized = false;
bool research_warning_logged = false;
bool research_startup_sync_pending = false;

int research_prior_us30_direction = 0;
int research_prior_us30_component = -1;
datetime research_prior_us30_bar = 0;
int research_prior_us100_direction = 0;
int research_prior_us100_component = -1;
datetime research_prior_us100_bar = 0;

int research_signal_prior_direction[COMPONENT_COUNT];
int research_signal_prior_component[COMPONENT_COUNT];
datetime research_signal_prior_bar[COMPONENT_COUNT];
string research_signal_relation[COMPONENT_COUNT];
string research_admission_reason[COMPONENT_COUNT];
double research_attempted_planned_risk[COMPONENT_COUNT];
double research_attempted_aggregate_after[COMPONENT_COUNT];
double research_attempted_position_cap[COMPONENT_COUNT];
double research_attempted_aggregate_cap[COMPONENT_COUNT];
double research_context_risk_capital[COMPONENT_COUNT];
int research_context_active_mask[COMPONENT_COUNT];
int research_context_reserved_mask[COMPONENT_COUNT];
double research_context_us30_risk[COMPONENT_COUNT];
double research_context_us100_risk[COMPONENT_COUNT];
int research_context_us30_direction[COMPONENT_COUNT];
int research_context_us100_direction[COMPONENT_COUNT];


string ResearchComponentId(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return("");
   return(component_definitions[component].id);
  }


string ResearchUtcMinute()
  {
   const datetime minute = (datetime)(((long)TimeGMT() / 60) * 60);
   return(TimeToString(minute, TIME_DATE | TIME_MINUTES));
  }


void ResearchWarnAndDrop(const string detail)
  {
   ++research_dropped_records;
   if(research_warning_logged)
      return;
   research_warning_logged = true;
   PrintFormat("%s optional research logging degraded: %s error=%d; trading state unchanged",
               EXECUTION_VERSION,
               detail,
               GetLastError());
  }


void ResearchClearLifecycle(const int component)
  {
   research_lifecycles[component].position_identifier = 0;
   research_lifecycles[component].entry_time_server = 0;
   research_lifecycles[component].segment_started_server = 0;
   research_lifecycles[component].direction = 0;
   research_lifecycles[component].volume = 0.0;
   research_lifecycles[component].entry_price = 0.0;
   research_lifecycles[component].entry_feature = 0.0;
   research_lifecycles[component].entry_stop_loss = 0.0;
   research_lifecycles[component].planned_risk_usd = 0.0;
   research_lifecycles[component].entry_spread_price = 0.0;
   research_lifecycles[component].entry_transaction_cost = 0.0;
   research_lifecycles[component].entry_adverse_slippage = 0.0;
   research_lifecycles[component].entry_cost_known = false;
   research_lifecycles[component].last_mark_profit_usd = 0.0;
   research_lifecycles[component].peak_mark_profit_usd = 0.0;
   research_lifecycles[component].trough_mark_profit_usd = 0.0;
   research_lifecycles[component].peak_mark_r = 0.0;
   research_lifecycles[component].trough_mark_r = 0.0;
   research_lifecycles[component].maximum_giveback_usd = 0.0;
   research_lifecycles[component].maximum_giveback_r = 0.0;
   research_lifecycles[component].peak_time_server = 0;
   research_lifecycles[component].trough_time_server = 0;
   research_lifecycles[component].mark_samples = 0;
   research_lifecycles[component].realized_net_usd = 0.0;
   research_lifecycles[component].stressed_net_usd = 0.0;
   research_lifecycles[component].partial_observation = false;
   research_lifecycles[component].birth_logged = false;
   research_lifecycles[component].first_peer_component = -1;
   research_lifecycles[component].first_peer_exit_server = 0;
   research_lifecycles[component].entry_active_mask = 0;
   research_lifecycles[component].entry_reserved_mask = 0;
   research_lifecycles[component].entry_active_slots = 0;
   research_lifecycles[component].entry_reserved_slots = 0;
   research_lifecycles[component].entry_aggregate_risk_usd = 0.0;
   research_lifecycles[component].entry_us30_risk_usd = 0.0;
   research_lifecycles[component].entry_us100_risk_usd = 0.0;
   research_lifecycles[component].entry_aggregate_headroom_usd = 0.0;
   research_lifecycles[component].prior_signal_direction = 0;
   research_lifecycles[component].signal_relation = "UNKNOWN";
   research_lifecycles[component].rc4_sell_warning = false;
  }


void ResetResearchObservationMemory()
  {
   research_state_sequence = 0;
   research_last_state_utc = 0;
   research_dropped_records = 0;
   research_warning_logged = false;
   research_prior_us30_direction = 0;
   research_prior_us30_component = -1;
   research_prior_us30_bar = 0;
   research_prior_us100_direction = 0;
   research_prior_us100_component = -1;
   research_prior_us100_bar = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ResearchClearLifecycle(component);
      research_signal_prior_direction[component] = 0;
      research_signal_prior_component[component] = -1;
      research_signal_prior_bar[component] = 0;
      research_signal_relation[component] = "UNKNOWN";
      research_admission_reason[component] = "";
      research_attempted_planned_risk[component] = 0.0;
      research_attempted_aggregate_after[component] = 0.0;
      research_attempted_position_cap[component] = 0.0;
      research_attempted_aggregate_cap[component] = 0.0;
      research_context_risk_capital[component] = 0.0;
      research_context_active_mask[component] = 0;
      research_context_reserved_mask[component] = 0;
      research_context_us30_risk[component] = 0.0;
      research_context_us100_risk[component] = 0.0;
      research_context_us30_direction[component] = 0;
      research_context_us100_direction[component] = 0;
     }
  }


int ResearchPositionMask()
  {
   int mask = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_states[component].position_identifier > 0)
         mask |= (1 << component);
   return(mask);
  }


int ResearchReservedMask()
  {
   int mask = ResearchPositionMask();
   if(execution_state.passive_pending_order > 0)
      mask |= (1 << US100_PASSIVE_LIMIT);
   return(mask);
  }


int ResearchMaskCount(const int mask)
  {
   int count = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if((mask & (1 << component)) != 0)
         ++count;
   return(count);
  }


double ResearchBookRisk(const string symbol)
  {
   double risk = 0.0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_definitions[component].symbol == symbol &&
         component_states[component].position_identifier > 0)
         risk += MathMax(0.0,
                         component_states[component].entry_planned_risk_usd);
   if(symbol == "US100" && execution_state.passive_pending_order > 0 &&
      component_states[US100_PASSIVE_LIMIT].position_identifier == 0)
      risk += MathMax(0.0, passive_pending_planned_risk_usd);
   return(risk);
  }


double ResearchAggregateRisk()
  {
   return(ResearchBookRisk("US30") + ResearchBookRisk("US100"));
  }


int ResearchBookDirection(const string symbol)
  {
   int direction = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_definitions[component].symbol == symbol &&
         component_states[component].position_identifier > 0)
         direction += component_states[component].entry_direction;
   if(symbol == "US100" && execution_state.passive_pending_order > 0 &&
      component_states[US100_PASSIVE_LIMIT].position_identifier == 0)
      direction += passive_pending_direction;
   return(direction);
  }


void ResearchResetAdmissionContext(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return;
   research_admission_reason[component] = "";
   research_attempted_planned_risk[component] = 0.0;
   research_attempted_aggregate_after[component] = 0.0;
   research_attempted_position_cap[component] = 0.0;
   research_attempted_aggregate_cap[component] = 0.0;
  }


void ResearchCapturePreDecisionBook(const int component)
  {
   research_context_risk_capital[component] = ConservativeRiskCapital();
   research_context_active_mask[component] = ResearchPositionMask();
   research_context_reserved_mask[component] = ResearchReservedMask();
   research_context_us30_risk[component] = ResearchBookRisk("US30");
   research_context_us100_risk[component] = ResearchBookRisk("US100");
   research_context_us30_direction[component] =
      ResearchBookDirection("US30");
   research_context_us100_direction[component] =
      ResearchBookDirection("US100");
  }


void ResearchCaptureSignalContext(const int component,
                                  const datetime bar,
                                  const double feature,
                                  const bool passed,
                                  const int direction)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return;
   ResearchResetAdmissionContext(component);
   ResearchCapturePreDecisionBook(component);
   const string symbol = component_definitions[component].symbol;
   const bool us30 = (symbol == "US30");
   research_signal_prior_direction[component] =
      (us30 ? research_prior_us30_direction :
       (symbol == "US100" ? research_prior_us100_direction : 0));
   research_signal_prior_component[component] =
      (us30 ? research_prior_us30_component :
       (symbol == "US100" ? research_prior_us100_component : -1));
   research_signal_prior_bar[component] =
      (us30 ? research_prior_us30_bar :
       (symbol == "US100" ? research_prior_us100_bar : 0));
   if(!passed || MathAbs(direction) != 1)
     {
      research_signal_relation[component] = "NO_SIGNAL";
      return;
     }
   if(research_signal_prior_direction[component] == 0)
      research_signal_relation[component] = "FIRST";
   else if(research_signal_prior_direction[component] == direction)
      research_signal_relation[component] = "PERSIST";
   else
      research_signal_relation[component] = "REVERSE";
   if(us30)
     {
      research_prior_us30_direction = direction;
      research_prior_us30_component = component;
      research_prior_us30_bar = bar;
     }
   else if(symbol == "US100")
     {
      research_prior_us100_direction = direction;
      research_prior_us100_component = component;
      research_prior_us100_bar = bar;
     }
  }


void ResearchCaptureAdmissionContext(const int component,
                                     const string reason,
                                     const double attempted_planned_risk,
                                     const double attempted_aggregate_after,
                                     const double position_cap,
                                     const double aggregate_cap)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return;
   research_admission_reason[component] = reason;
   research_attempted_planned_risk[component] = attempted_planned_risk;
   research_attempted_aggregate_after[component] =
      attempted_aggregate_after;
   research_attempted_position_cap[component] = position_cap;
   research_attempted_aggregate_cap[component] = aggregate_cap;
  }


bool ResearchAppendCandidateRow(const int component,
                                const string stage,
                                const string result,
                                const string detail)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return(false);
   ResetLastError();
   const int handle =
      FileOpen(RESEARCH_CANDIDATE_LEDGER_PATH,
               FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
               FILE_SHARE_READ,
               ',');
   if(handle == INVALID_HANDLE)
     {
      ResearchWarnAndDrop("cannot open candidate ledger");
      return(false);
     }
   if(FileSize(handle) == 0)
      FileWrite(handle,
                "schema", "record_id", "utc", "server_time",
                "macro_join_utc_minute", "release_id",
                "execution_version", "portfolio_id", "stage", "result",
                "component_id", "symbol", "decision_bar", "signal_known",
                "signal_passed", "feature", "direction",
                "prior_signal_direction", "prior_signal_component",
                "prior_signal_bar", "signal_relation", "rc4_sell_warning",
                "order_price", "volume", "stop_loss", "planned_risk_usd",
                "admission_reason", "attempted_planned_risk_usd",
                "attempted_aggregate_after_usd", "risk_capital_usd",
                "position_cap_usd", "aggregate_risk_before_usd",
                "aggregate_cap_usd", "aggregate_headroom_usd",
                "active_mask", "reserved_mask", "active_slots",
                "reserved_slots", "us30_risk_usd", "us100_risk_usd",
                "us30_direction_net", "us100_direction_net",
                "account_balance", "account_equity", "account_margin",
                "core_state_sequence", "research_dropped_records", "detail");
   FileSeek(handle, 0, SEEK_END);
   const int active_mask = research_context_active_mask[component];
   const int reserved_mask = research_context_reserved_mask[component];
   const double aggregate_before =
      research_context_us30_risk[component] +
      research_context_us100_risk[component];
   const double risk_capital = research_context_risk_capital[component];
   const double aggregate_cap =
      (research_attempted_aggregate_cap[component] > 0.0
       ? research_attempted_aggregate_cap[component]
       : risk_capital * InpMaximumAggregateRiskFraction);
   const string prior_component =
      ResearchComponentId(research_signal_prior_component[component]);
   const datetime bar = component_states[component].entry_check_bar;
   const string record_id =
      StringFormat("%s-%I64d-%s-%s",
                   component_definitions[component].id,
                   (long)bar,
                   stage,
                   result);
   const uint written =
      FileWrite(handle,
                RESEARCH_OBSERVATION_SCHEMA,
                record_id,
                TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS),
                TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
                ResearchUtcMinute(),
                RELEASE_ID,
                EXECUTION_VERSION,
                PORTFOLIO_ID,
                stage,
                result,
                component_definitions[component].id,
                component_definitions[component].symbol,
                TimeToString(bar, TIME_DATE | TIME_MINUTES),
                component_states[component].entry_check_signal_known,
                component_states[component].entry_check_signal_passed,
                component_states[component].entry_check_signal_value,
                component_states[component].entry_check_direction,
                research_signal_prior_direction[component],
                prior_component,
                TimeToString(research_signal_prior_bar[component],
                             TIME_DATE | TIME_MINUTES),
                research_signal_relation[component],
                (component == RC4_BOTH &&
                 component_states[component].entry_check_signal_passed == 1 &&
                 component_states[component].entry_check_direction < 0 ? 1 : 0),
                component_states[component].entry_check_order_price,
                component_states[component].entry_check_volume,
                component_states[component].entry_check_stop_loss,
                component_states[component].entry_check_planned_risk_usd,
                research_admission_reason[component],
                research_attempted_planned_risk[component],
                research_attempted_aggregate_after[component],
                risk_capital,
                (research_attempted_position_cap[component] > 0.0
                 ? research_attempted_position_cap[component]
                 : risk_capital * InpMaximumPositionRiskFraction *
                   MathMax(0.0, ComponentEffectiveWeight(component))),
                aggregate_before,
                aggregate_cap,
                MathMax(0.0, aggregate_cap - aggregate_before),
                active_mask,
                reserved_mask,
                ResearchMaskCount(active_mask),
                ResearchMaskCount(reserved_mask),
                research_context_us30_risk[component],
                research_context_us100_risk[component],
                research_context_us30_direction[component],
                research_context_us100_direction[component],
                AccountInfoDouble(ACCOUNT_BALANCE),
                AccountInfoDouble(ACCOUNT_EQUITY),
                AccountInfoDouble(ACCOUNT_MARGIN),
                state_sequence,
                research_dropped_records,
                detail);
   FileFlush(handle);
   FileClose(handle);
   if(written == 0)
     {
      ResearchWarnAndDrop("candidate ledger write returned zero");
      return(false);
     }
   return(true);
  }


void ResearchRecordCandidateOutcome(const int component,
                                    const string stage,
                                    const string result,
                                    const string detail)
  {
   if(!research_observation_initialized)
      return;
   ResearchAppendCandidateRow(component, stage, result, detail);
   SaveResearchObservationState();
  }


void ResearchRecordGateObservation(const int component,
                                   const datetime bar,
                                   const string result)
  {
   if(!research_observation_initialized || component < 0 ||
      component >= COMPONENT_COUNT)
      return;
   ResearchResetAdmissionContext(component);
   ResearchCapturePreDecisionBook(component);
   const string symbol = component_definitions[component].symbol;
   research_signal_prior_direction[component] =
      (symbol == "US30" ? research_prior_us30_direction :
       (symbol == "US100" ? research_prior_us100_direction : 0));
   research_signal_prior_component[component] =
      (symbol == "US30" ? research_prior_us30_component :
       (symbol == "US100" ? research_prior_us100_component : -1));
   research_signal_prior_bar[component] =
      (symbol == "US30" ? research_prior_us30_bar :
       (symbol == "US100" ? research_prior_us100_bar : 0));
   research_signal_relation[component] = "NOT_EVALUATED";
   ResearchAppendCandidateRow(component,
                              "GATE",
                              result,
                              StringFormat("consumed_bar=%s",
                                           TimeToString(bar,
                                                        TIME_DATE |
                                                        TIME_MINUTES)));
   SaveResearchObservationState();
  }


bool ResearchAppendLifecycleRow(const int component,
                                const string event_name,
                                const ulong related_deal,
                                const string exit_reason,
                                const string exit_class,
                                const double exit_price,
                                const string detail)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return(false);
   ResetLastError();
   const int handle =
      FileOpen(RESEARCH_LIFECYCLE_LEDGER_PATH,
               FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI |
               FILE_SHARE_READ,
               ',');
   if(handle == INVALID_HANDLE)
     {
      ResearchWarnAndDrop("cannot open lifecycle ledger");
      return(false);
     }
   if(FileSize(handle) == 0)
      FileWrite(handle,
                "schema", "record_id", "utc", "server_time",
                "macro_join_utc_minute", "release_id",
                "execution_version", "portfolio_id", "event",
                "component_id", "symbol", "position_identifier",
                "entry_time_server", "segment_started_server", "direction",
                "volume", "entry_price", "entry_feature", "stop_loss",
                "planned_risk_usd", "entry_spread_price",
                "entry_transaction_cost", "entry_adverse_slippage",
                "entry_cost_known", "last_mark_profit_usd", "last_mark_r",
                "peak_mark_profit_usd", "peak_mark_r", "peak_time_server",
                "trough_mark_profit_usd", "trough_mark_r",
                "trough_time_server", "maximum_giveback_usd",
                "maximum_giveback_r", "mark_samples", "entry_active_mask",
                "entry_reserved_mask", "entry_active_slots",
                "entry_aggregate_risk_usd", "entry_us30_risk_usd",
                "entry_us100_risk_usd", "entry_aggregate_headroom_usd",
                "prior_signal_direction", "signal_relation",
                "rc4_sell_warning", "first_peer_component",
                "first_peer_exit_server", "exit_reason", "exit_class",
                "exit_price", "actual_net_usd", "stressed_net_usd",
                "current_active_mask", "current_reserved_mask",
                "current_us30_risk_usd", "current_us100_risk_usd",
                "partial_observation", "research_state_sequence",
                "research_dropped_records", "detail");
   FileSeek(handle, 0, SEEK_END);
   const double planned_risk =
      research_lifecycles[component].planned_risk_usd;
   const double last_r =
      (planned_risk > 0.0
       ? research_lifecycles[component].last_mark_profit_usd / planned_risk
       : 0.0);
   const string peer_component =
      ResearchComponentId(research_lifecycles[component].first_peer_component);
   const string record_id =
      StringFormat("%I64u-%s-%I64u",
                   research_lifecycles[component].position_identifier,
                   event_name,
                   related_deal);
   const uint written =
      FileWrite(handle,
                RESEARCH_OBSERVATION_SCHEMA,
                record_id,
                TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS),
                TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
                ResearchUtcMinute(),
                RELEASE_ID,
                EXECUTION_VERSION,
                PORTFOLIO_ID,
                event_name,
                component_definitions[component].id,
                component_definitions[component].symbol,
                (long)research_lifecycles[component].position_identifier,
                TimeToString(
                   research_lifecycles[component].entry_time_server,
                   TIME_DATE | TIME_SECONDS),
                TimeToString(
                   research_lifecycles[component].segment_started_server,
                   TIME_DATE | TIME_SECONDS),
                research_lifecycles[component].direction,
                research_lifecycles[component].volume,
                research_lifecycles[component].entry_price,
                research_lifecycles[component].entry_feature,
                research_lifecycles[component].entry_stop_loss,
                planned_risk,
                research_lifecycles[component].entry_spread_price,
                research_lifecycles[component].entry_transaction_cost,
                research_lifecycles[component].entry_adverse_slippage,
                (research_lifecycles[component].entry_cost_known ? 1 : 0),
                research_lifecycles[component].last_mark_profit_usd,
                last_r,
                research_lifecycles[component].peak_mark_profit_usd,
                research_lifecycles[component].peak_mark_r,
                TimeToString(research_lifecycles[component].peak_time_server,
                             TIME_DATE | TIME_SECONDS),
                research_lifecycles[component].trough_mark_profit_usd,
                research_lifecycles[component].trough_mark_r,
                TimeToString(research_lifecycles[component].trough_time_server,
                             TIME_DATE | TIME_SECONDS),
                research_lifecycles[component].maximum_giveback_usd,
                research_lifecycles[component].maximum_giveback_r,
                research_lifecycles[component].mark_samples,
                research_lifecycles[component].entry_active_mask,
                research_lifecycles[component].entry_reserved_mask,
                research_lifecycles[component].entry_active_slots,
                research_lifecycles[component].entry_aggregate_risk_usd,
                research_lifecycles[component].entry_us30_risk_usd,
                research_lifecycles[component].entry_us100_risk_usd,
                research_lifecycles[component].entry_aggregate_headroom_usd,
                research_lifecycles[component].prior_signal_direction,
                research_lifecycles[component].signal_relation,
                (research_lifecycles[component].rc4_sell_warning ? 1 : 0),
                peer_component,
                TimeToString(
                   research_lifecycles[component].first_peer_exit_server,
                   TIME_DATE | TIME_SECONDS),
                exit_reason,
                exit_class,
                exit_price,
                research_lifecycles[component].realized_net_usd,
                research_lifecycles[component].stressed_net_usd,
                ResearchPositionMask(),
                ResearchReservedMask(),
                ResearchBookRisk("US30"),
                ResearchBookRisk("US100"),
                (research_lifecycles[component].partial_observation ? 1 : 0),
                research_state_sequence,
                research_dropped_records,
                detail);
   FileFlush(handle);
   FileClose(handle);
   if(written == 0)
     {
      ResearchWarnAndDrop("lifecycle ledger write returned zero");
      return(false);
     }
   return(true);
  }


void ResearchUpdateMark(const int component, const double mark_profit)
  {
   const datetime now = TimeCurrent();
   const double planned_risk =
      research_lifecycles[component].planned_risk_usd;
   const double mark_r = (planned_risk > 0.0 ? mark_profit / planned_risk : 0.0);
   if(research_lifecycles[component].mark_samples == 0)
     {
      research_lifecycles[component].peak_mark_profit_usd = mark_profit;
      research_lifecycles[component].trough_mark_profit_usd = mark_profit;
      research_lifecycles[component].peak_mark_r = mark_r;
      research_lifecycles[component].trough_mark_r = mark_r;
      research_lifecycles[component].peak_time_server = now;
      research_lifecycles[component].trough_time_server = now;
     }
   else
     {
      if(mark_profit >
         research_lifecycles[component].peak_mark_profit_usd)
        {
         research_lifecycles[component].peak_mark_profit_usd = mark_profit;
         research_lifecycles[component].peak_mark_r = mark_r;
         research_lifecycles[component].peak_time_server = now;
        }
      if(mark_profit <
         research_lifecycles[component].trough_mark_profit_usd)
        {
         research_lifecycles[component].trough_mark_profit_usd = mark_profit;
         research_lifecycles[component].trough_mark_r = mark_r;
         research_lifecycles[component].trough_time_server = now;
        }
     }
   research_lifecycles[component].last_mark_profit_usd = mark_profit;
   research_lifecycles[component].maximum_giveback_usd =
      MathMax(research_lifecycles[component].maximum_giveback_usd,
              research_lifecycles[component].peak_mark_profit_usd -
              mark_profit);
   research_lifecycles[component].maximum_giveback_r =
      MathMax(research_lifecycles[component].maximum_giveback_r,
              research_lifecycles[component].peak_mark_r - mark_r);
   ++research_lifecycles[component].mark_samples;
  }


void ResearchBeginLifecycle(const int component,
                            const ulong ticket,
                            const bool partial)
  {
   if(!PositionSelectByTicket(ticket))
      return;
   const ulong identifier =
      (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   if(identifier == 0 ||
      identifier != component_states[component].position_identifier)
      return;
   ResearchClearLifecycle(component);
   research_lifecycles[component].position_identifier = identifier;
   research_lifecycles[component].entry_time_server =
      component_states[component].entry_time_server;
   research_lifecycles[component].segment_started_server = TimeCurrent();
   research_lifecycles[component].direction =
      component_states[component].entry_direction;
   research_lifecycles[component].volume =
      PositionGetDouble(POSITION_VOLUME);
   research_lifecycles[component].entry_price =
      PositionGetDouble(POSITION_PRICE_OPEN);
   research_lifecycles[component].entry_feature =
      component_states[component].entry_feature;
   research_lifecycles[component].entry_stop_loss =
      component_states[component].entry_stop_loss;
   research_lifecycles[component].planned_risk_usd =
      component_states[component].entry_planned_risk_usd;
   research_lifecycles[component].entry_spread_price =
      component_states[component].entry_spread_price;
   research_lifecycles[component].entry_transaction_cost =
      component_states[component].entry_transaction_cost;
   research_lifecycles[component].entry_adverse_slippage =
      component_states[component].entry_adverse_slippage;
   research_lifecycles[component].entry_cost_known =
      component_states[component].entry_cost_known;
   research_lifecycles[component].partial_observation = partial;
   research_lifecycles[component].birth_logged = true;
   research_lifecycles[component].first_peer_component = -1;
   research_lifecycles[component].entry_active_mask = ResearchPositionMask();
   research_lifecycles[component].entry_reserved_mask = ResearchReservedMask();
   research_lifecycles[component].entry_active_slots =
      ResearchMaskCount(research_lifecycles[component].entry_active_mask);
   research_lifecycles[component].entry_reserved_slots =
      ResearchMaskCount(research_lifecycles[component].entry_reserved_mask);
   research_lifecycles[component].entry_aggregate_risk_usd =
      ResearchAggregateRisk();
   research_lifecycles[component].entry_us30_risk_usd =
      ResearchBookRisk("US30");
   research_lifecycles[component].entry_us100_risk_usd =
      ResearchBookRisk("US100");
   const double risk_capital = ConservativeRiskCapital();
   research_lifecycles[component].entry_aggregate_headroom_usd =
      MathMax(0.0,
              risk_capital * InpMaximumAggregateRiskFraction -
              research_lifecycles[component].entry_aggregate_risk_usd);
   research_lifecycles[component].prior_signal_direction =
      research_signal_prior_direction[component];
   research_lifecycles[component].signal_relation =
      (partial ? "RESTART_UNKNOWN" :
                 research_signal_relation[component]);
   research_lifecycles[component].rc4_sell_warning =
      (component == RC4_BOTH &&
       research_lifecycles[component].direction < 0);
   const double mark_profit =
      PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   ResearchUpdateMark(component, mark_profit);
   ResearchAppendLifecycleRow(component,
                              (partial ? "RESUME_PARTIAL" : "BIRTH"),
                              0,
                              "",
                              "",
                              0.0,
                              (partial
                               ? "observer began after lifecycle birth"
                               : "observer began after durable entry"));
   SaveResearchObservationState();
  }


void ResearchSampleOpenPositions()
  {
   if(!research_observation_initialized)
      return;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(component_states[component].position_identifier == 0)
         continue;
      ulong ticket = 0;
      datetime opened_at = 0;
      if(CountOwnedPositions(component, ticket, opened_at) != 1 ||
         !PositionSelectByTicket(ticket) ||
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) !=
         component_states[component].position_identifier)
         continue;
      const ulong identifier =
         (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(research_lifecycles[component].position_identifier != identifier)
        {
         const bool partial =
            (research_startup_sync_pending ||
             research_lifecycles[component].position_identifier != 0);
         ResearchBeginLifecycle(component, ticket, partial);
         continue;
        }
      research_lifecycles[component].volume =
         PositionGetDouble(POSITION_VOLUME);
      const double mark_profit =
         PositionGetDouble(POSITION_PROFIT) +
         PositionGetDouble(POSITION_SWAP);
      ResearchUpdateMark(component, mark_profit);
     }
   research_startup_sync_pending = false;
  }


void ResearchSeedExitFallback(const ResearchExitSnapshot &snapshot)
  {
   const int component = snapshot.component;
   ResearchClearLifecycle(component);
   research_lifecycles[component].position_identifier =
      snapshot.position_identifier;
   research_lifecycles[component].entry_time_server =
      snapshot.entry_time_server;
   research_lifecycles[component].segment_started_server = TimeCurrent();
   research_lifecycles[component].direction = snapshot.direction;
   research_lifecycles[component].volume = snapshot.entry_volume;
   research_lifecycles[component].entry_feature = snapshot.entry_feature;
   research_lifecycles[component].entry_stop_loss =
      snapshot.entry_stop_loss;
   research_lifecycles[component].planned_risk_usd =
      snapshot.entry_planned_risk_usd;
   research_lifecycles[component].entry_spread_price =
      snapshot.entry_spread_price;
   research_lifecycles[component].entry_transaction_cost =
      snapshot.entry_transaction_cost;
   research_lifecycles[component].entry_adverse_slippage =
      snapshot.entry_adverse_slippage;
   research_lifecycles[component].entry_cost_known =
      snapshot.entry_cost_known;
   research_lifecycles[component].partial_observation = true;
   research_lifecycles[component].first_peer_component = -1;
   research_lifecycles[component].signal_relation = "RESTART_UNKNOWN";
   research_lifecycles[component].rc4_sell_warning =
      (component == RC4_BOTH && snapshot.direction < 0);
  }


string ResearchExitClass(const ENUM_DEAL_REASON reason)
  {
   if(reason == DEAL_REASON_SL)
      return("STOP");
   if(reason == DEAL_REASON_EXPERT)
      return("NATIVE");
   return("EXTERNAL_OR_BROKER");
  }


void ResearchHandleExitDeal(const ResearchExitSnapshot &snapshot)
  {
   if(!research_observation_initialized || snapshot.component < 0 ||
      snapshot.component >= COMPONENT_COUNT)
      return;
   ResearchSampleOpenPositions();
   const int component = snapshot.component;
   if(research_lifecycles[component].position_identifier !=
      snapshot.position_identifier)
      ResearchSeedExitFallback(snapshot);
   research_lifecycles[component].realized_net_usd += snapshot.deal_net;
   research_lifecycles[component].stressed_net_usd += snapshot.stressed_net;
   research_lifecycles[component].volume = snapshot.remaining_volume;
   const string exit_reason = EnumToString(snapshot.exit_reason);
   const string exit_class = ResearchExitClass(snapshot.exit_reason);
   if(!snapshot.full_exit)
     {
      ResearchAppendLifecycleRow(
         component,
         "PARTIAL_EXIT",
         snapshot.deal_ticket,
         exit_reason,
         exit_class,
         snapshot.execution_price,
         StringFormat("core_event=%s remaining=%.2f",
                      snapshot.core_event_name,
                      snapshot.remaining_volume));
      SaveResearchObservationState();
      return;
     }
   ResearchAppendLifecycleRow(
      component,
      "CLOSE",
      snapshot.deal_ticket,
      exit_reason,
      exit_class,
      snapshot.execution_price,
      StringFormat("core_event=%s same_millisecond_peer_rows_require_offline_exclusion",
                   snapshot.core_event_name));
   if(snapshot.exit_reason == DEAL_REASON_EXPERT)
     {
      const datetime peer_exit_server =
         (datetime)(snapshot.deal_time_msc / 1000);
      for(int peer = 0; peer < COMPONENT_COUNT; ++peer)
        {
         if(peer == component ||
            research_lifecycles[peer].position_identifier == 0 ||
            research_lifecycles[peer].first_peer_component >= 0)
            continue;
         research_lifecycles[peer].first_peer_component = component;
         research_lifecycles[peer].first_peer_exit_server =
            peer_exit_server;
         ResearchAppendLifecycleRow(
            peer,
            "FIRST_PEER_NATURAL_EXIT",
            snapshot.deal_ticket,
            exit_reason,
            "PEER_NATIVE",
            snapshot.execution_price,
            StringFormat("peer_component=%s peer_position=%I64u same_millisecond_target_close_requires_offline_exclusion",
                         component_definitions[component].id,
                         snapshot.position_identifier));
        }
     }
   ResearchClearLifecycle(component);
   SaveResearchObservationState();
  }


bool ReadResearchObservationState(const string path,
                                  long &loaded_sequence)
  {
   loaded_sequence = -1;
   if(!FileIsExist(path))
      return(false);
   const int handle =
      FileOpen(path, FILE_READ | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(handle == INVALID_HANDLE)
      return(false);
   const string marker = FileReadString(handle);
   const string schema = FileReadString(handle);
   const string portfolio = FileReadString(handle);
   research_state_sequence = (long)FileReadNumber(handle);
   research_last_state_utc = (datetime)((long)FileReadNumber(handle));
   research_dropped_records = (long)FileReadNumber(handle);
   research_prior_us30_direction = (int)FileReadNumber(handle);
   research_prior_us30_component = (int)FileReadNumber(handle);
   research_prior_us30_bar = (datetime)((long)FileReadNumber(handle));
   research_prior_us100_direction = (int)FileReadNumber(handle);
   research_prior_us100_component = (int)FileReadNumber(handle);
   research_prior_us100_bar = (datetime)((long)FileReadNumber(handle));
   bool valid =
      (marker == RESEARCH_OBSERVATION_MARKER &&
       schema == RESEARCH_OBSERVATION_SCHEMA && portfolio == PORTFOLIO_ID &&
       research_state_sequence >= 0 && research_last_state_utc >= 0 &&
       research_dropped_records >= 0);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      const string component_id = FileReadString(handle);
      research_lifecycles[component].position_identifier =
         (ulong)((long)FileReadNumber(handle));
      research_lifecycles[component].entry_time_server =
         (datetime)((long)FileReadNumber(handle));
      research_lifecycles[component].segment_started_server =
         (datetime)((long)FileReadNumber(handle));
      research_lifecycles[component].direction =
         (int)FileReadNumber(handle);
      research_lifecycles[component].volume = FileReadNumber(handle);
      research_lifecycles[component].entry_price = FileReadNumber(handle);
      research_lifecycles[component].entry_feature = FileReadNumber(handle);
      research_lifecycles[component].entry_stop_loss = FileReadNumber(handle);
      research_lifecycles[component].planned_risk_usd = FileReadNumber(handle);
      research_lifecycles[component].entry_spread_price =
         FileReadNumber(handle);
      research_lifecycles[component].entry_transaction_cost =
         FileReadNumber(handle);
      research_lifecycles[component].entry_adverse_slippage =
         FileReadNumber(handle);
      research_lifecycles[component].entry_cost_known =
         ((int)FileReadNumber(handle) == 1);
      research_lifecycles[component].last_mark_profit_usd =
         FileReadNumber(handle);
      research_lifecycles[component].peak_mark_profit_usd =
         FileReadNumber(handle);
      research_lifecycles[component].trough_mark_profit_usd =
         FileReadNumber(handle);
      research_lifecycles[component].peak_mark_r = FileReadNumber(handle);
      research_lifecycles[component].trough_mark_r = FileReadNumber(handle);
      research_lifecycles[component].maximum_giveback_usd =
         FileReadNumber(handle);
      research_lifecycles[component].maximum_giveback_r =
         FileReadNumber(handle);
      research_lifecycles[component].peak_time_server =
         (datetime)((long)FileReadNumber(handle));
      research_lifecycles[component].trough_time_server =
         (datetime)((long)FileReadNumber(handle));
      research_lifecycles[component].mark_samples =
         (long)FileReadNumber(handle);
      research_lifecycles[component].realized_net_usd =
         FileReadNumber(handle);
      research_lifecycles[component].stressed_net_usd =
         FileReadNumber(handle);
      research_lifecycles[component].partial_observation =
         ((int)FileReadNumber(handle) == 1);
      research_lifecycles[component].birth_logged =
         ((int)FileReadNumber(handle) == 1);
      research_lifecycles[component].first_peer_component =
         (int)FileReadNumber(handle);
      research_lifecycles[component].first_peer_exit_server =
         (datetime)((long)FileReadNumber(handle));
      research_lifecycles[component].entry_active_mask =
         (int)FileReadNumber(handle);
      research_lifecycles[component].entry_reserved_mask =
         (int)FileReadNumber(handle);
      research_lifecycles[component].entry_active_slots =
         (int)FileReadNumber(handle);
      research_lifecycles[component].entry_reserved_slots =
         (int)FileReadNumber(handle);
      research_lifecycles[component].entry_aggregate_risk_usd =
         FileReadNumber(handle);
      research_lifecycles[component].entry_us30_risk_usd =
         FileReadNumber(handle);
      research_lifecycles[component].entry_us100_risk_usd =
         FileReadNumber(handle);
      research_lifecycles[component].entry_aggregate_headroom_usd =
         FileReadNumber(handle);
      research_lifecycles[component].prior_signal_direction =
         (int)FileReadNumber(handle);
      research_lifecycles[component].signal_relation =
         FileReadString(handle);
      research_lifecycles[component].rc4_sell_warning =
         ((int)FileReadNumber(handle) == 1);
      if(component_id != component_definitions[component].id ||
         research_lifecycles[component].mark_samples < 0 ||
         !MathIsValidNumber(
            research_lifecycles[component].last_mark_profit_usd) ||
         !MathIsValidNumber(
            research_lifecycles[component].peak_mark_profit_usd) ||
         !MathIsValidNumber(
            research_lifecycles[component].trough_mark_profit_usd))
         valid = false;
     }
   const string end_marker = FileReadString(handle);
   FileClose(handle);
   if(end_marker != RESEARCH_OBSERVATION_MARKER)
      valid = false;
   if(!valid)
      return(false);
   loaded_sequence = research_state_sequence;
   return(true);
  }


bool LoadResearchObservationState()
  {
   long sequence_a = -1;
   long sequence_b = -1;
   const bool valid_a =
      ReadResearchObservationState(RESEARCH_OBSERVATION_STATE_PATH_A,
                                   sequence_a);
   ResetResearchObservationMemory();
   const bool valid_b =
      ReadResearchObservationState(RESEARCH_OBSERVATION_STATE_PATH_B,
                                   sequence_b);
   ResetResearchObservationMemory();
   const string selected =
      (valid_a && (!valid_b || sequence_a >= sequence_b)
       ? RESEARCH_OBSERVATION_STATE_PATH_A :
       (valid_b ? RESEARCH_OBSERVATION_STATE_PATH_B : ""));
   if(selected == "")
      return(false);
   long selected_sequence = -1;
   return(ReadResearchObservationState(selected, selected_sequence));
  }


void SaveResearchObservationState()
  {
   if(!research_observation_initialized)
      return;
   const long previous_sequence = research_state_sequence;
   const datetime previous_utc = research_last_state_utc;
   ++research_state_sequence;
   research_last_state_utc = TimeGMT();
   const string path =
      ((research_state_sequence % 2) == 0
       ? RESEARCH_OBSERVATION_STATE_PATH_A
       : RESEARCH_OBSERVATION_STATE_PATH_B);
   ResetLastError();
   const int handle = FileOpen(path, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
     {
      research_state_sequence = previous_sequence;
      research_last_state_utc = previous_utc;
      ResearchWarnAndDrop("cannot open research state snapshot");
      return;
     }
   FileWrite(handle,
             RESEARCH_OBSERVATION_MARKER,
             RESEARCH_OBSERVATION_SCHEMA,
             PORTFOLIO_ID,
             research_state_sequence,
             (long)research_last_state_utc,
             research_dropped_records,
             research_prior_us30_direction,
             research_prior_us30_component,
             (long)research_prior_us30_bar,
             research_prior_us100_direction,
             research_prior_us100_component,
             (long)research_prior_us100_bar);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      FileWrite(handle,
                component_definitions[component].id,
                (long)research_lifecycles[component].position_identifier,
                (long)research_lifecycles[component].entry_time_server,
                (long)research_lifecycles[component].segment_started_server,
                research_lifecycles[component].direction,
                research_lifecycles[component].volume,
                research_lifecycles[component].entry_price,
                research_lifecycles[component].entry_feature,
                research_lifecycles[component].entry_stop_loss,
                research_lifecycles[component].planned_risk_usd,
                research_lifecycles[component].entry_spread_price,
                research_lifecycles[component].entry_transaction_cost,
                research_lifecycles[component].entry_adverse_slippage,
                (research_lifecycles[component].entry_cost_known ? 1 : 0),
                research_lifecycles[component].last_mark_profit_usd,
                research_lifecycles[component].peak_mark_profit_usd,
                research_lifecycles[component].trough_mark_profit_usd,
                research_lifecycles[component].peak_mark_r,
                research_lifecycles[component].trough_mark_r,
                research_lifecycles[component].maximum_giveback_usd,
                research_lifecycles[component].maximum_giveback_r,
                (long)research_lifecycles[component].peak_time_server,
                (long)research_lifecycles[component].trough_time_server,
                research_lifecycles[component].mark_samples,
                research_lifecycles[component].realized_net_usd,
                research_lifecycles[component].stressed_net_usd,
                (research_lifecycles[component].partial_observation ? 1 : 0),
                (research_lifecycles[component].birth_logged ? 1 : 0),
                research_lifecycles[component].first_peer_component,
                (long)research_lifecycles[component].first_peer_exit_server,
                research_lifecycles[component].entry_active_mask,
                research_lifecycles[component].entry_reserved_mask,
                research_lifecycles[component].entry_active_slots,
                research_lifecycles[component].entry_reserved_slots,
                research_lifecycles[component].entry_aggregate_risk_usd,
                research_lifecycles[component].entry_us30_risk_usd,
                research_lifecycles[component].entry_us100_risk_usd,
                research_lifecycles[component].entry_aggregate_headroom_usd,
                research_lifecycles[component].prior_signal_direction,
                research_lifecycles[component].signal_relation,
                (research_lifecycles[component].rc4_sell_warning ? 1 : 0));
   FileWrite(handle, RESEARCH_OBSERVATION_MARKER);
   FileFlush(handle);
   FileClose(handle);
  }


void InitializeResearchObservation()
  {
   if(research_observation_initialized)
      return;
   ResetResearchObservationMemory();
   const bool recovered = (!tester_mode && LoadResearchObservationState());
   research_observation_initialized = true;
   research_startup_sync_pending = true;
   PrintFormat("%s optional research observation initialized recovered=%s sequence=%I64d",
               EXECUTION_VERSION,
               (recovered ? "true" : "false"),
               research_state_sequence);
  }


void ResetResearchObservationArtifacts()
  {
   FileDelete(RESEARCH_OBSERVATION_STATE_PATH_A);
   FileDelete(RESEARCH_OBSERVATION_STATE_PATH_B);
   FileDelete(RESEARCH_CANDIDATE_LEDGER_PATH);
   FileDelete(RESEARCH_LIFECYCLE_LEDGER_PATH);
  }


#endif
