#ifndef ZETA_VS_ACCOUNT_PATH_MQH
#define ZETA_VS_ACCOUNT_PATH_MQH

// Read-only tester account path for the variance-standardization campaign.

int      vs_account_handle = INVALID_HANDLE;
string   vs_account_path = "";
bool     vs_account_initialized = false;
long     vs_account_rows = 0;
long     vs_account_write_faults = 0;
long     vs_account_evidence_faults = 0;
long     vs_account_mark_skips = 0;
long     vs_account_entry_state_skips = 0;
long     vs_account_quote_skips = 0;
long     vs_account_quote_age_unknown_rows = 0;
long     vs_account_last_server_minute = -1;
double   vs_account_positive_closed_swap = 0.0;
double   vs_account_maximum_observed_quote_age_seconds = 0.0;
bool     vs_account_last_mark_known = false;
int      vs_account_last_owned_position_count = 0;
int      vs_account_last_owned_pending_count = 0;
double   vs_account_last_owned_open_volume = 0.0;
double   vs_account_last_owned_pending_volume = 0.0;
string   vs_account_last_mark_status = "NOT_OBSERVED";

void VSAccountObserve(bool force=false);


struct VSAccountSnapshot
  {
   datetime server_time;
   long server_minute;
   double actual_balance;
   double actual_equity;
   double stressed_balance;
   double conservative_stressed_mark;
   bool conservative_mark_known;
   string conservative_mark_status;
   double conservative_risk_capital;
   int day_volume_multiplier;
   double owned_open_volume;
   double owned_pending_volume;
   double tracked_aggregate_planned_risk;
   double row_maximum_quote_age_seconds;
   bool quote_age_known;
   int owned_position_count;
   int owned_pending_count;
   bool entry_state_unknown;
   bool position_quote_unknown;
  };


void VSAccountRecordFileFault(const string stage,
                              const int error_code)
  {
   ++vs_account_write_faults;
   ++vs_account_evidence_faults;
   PrintFormat("VS_ACCOUNT_FILE_FAULT stage=%s error=%d path=%s faults=%I64d",
               stage,
               error_code,
               vs_account_path,
               vs_account_write_faults);
  }


void VSAccountMarkUnknown(VSAccountSnapshot &snapshot,
                          const string reason,
                          const bool entry_state_unknown,
                          const bool position_quote_unknown)
  {
   snapshot.conservative_mark_known = false;
   if(snapshot.conservative_mark_status == "KNOWN")
      snapshot.conservative_mark_status = reason;
   else if(StringFind(snapshot.conservative_mark_status, reason) < 0)
      snapshot.conservative_mark_status += "|" + reason;
   if(entry_state_unknown)
      snapshot.entry_state_unknown = true;
   if(position_quote_unknown)
      snapshot.position_quote_unknown = true;
  }


int VSSelectedPositionComponent()
  {
   const string symbol = PositionGetString(POSITION_SYMBOL);
   const ulong magic = (ulong)PositionGetInteger(POSITION_MAGIC);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_definitions[component].symbol == symbol &&
         component_definitions[component].magic == magic)
         return(component);
   return(-1);
  }


int VSSelectedOrderComponent()
  {
   const string symbol = OrderGetString(ORDER_SYMBOL);
   const ulong magic = (ulong)OrderGetInteger(ORDER_MAGIC);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_definitions[component].symbol == symbol &&
         component_definitions[component].magic == magic)
         return(component);
   return(-1);
  }


bool VSAccountReadCurrentQuote(const string symbol,
                               const datetime server_time,
                               MqlTick &tick,
                               double &age_seconds)
  {
   age_seconds = 0.0;
   if(server_time <= 0 || !SymbolInfoTick(symbol, tick) ||
      tick.time <= 0 || tick.ask <= tick.bid ||
      tick.bid <= 0.0 || tick.ask <= 0.0)
      return(false);
   const long age = (long)server_time - (long)tick.time;
   if(age < 0)
      return(false);
   age_seconds = (double)age;
   return(MathIsValidNumber(age_seconds));
  }


void VSAccountObserveQuoteAge(VSAccountSnapshot &snapshot,
                              const string symbol,
                              const bool required_for_mark,
                              MqlTick &tick,
                              bool &quote_known)
  {
   double age_seconds = 0.0;
   quote_known = VSAccountReadCurrentQuote(symbol,
                                           snapshot.server_time,
                                           tick,
                                           age_seconds);
   if(!quote_known)
     {
      snapshot.quote_age_known = false;
      if(required_for_mark)
         VSAccountMarkUnknown(snapshot,
                              "POSITION_QUOTE_UNKNOWN",
                              false,
                              true);
      return;
     }
   snapshot.row_maximum_quote_age_seconds =
      MathMax(snapshot.row_maximum_quote_age_seconds, age_seconds);
   vs_account_maximum_observed_quote_age_seconds =
      MathMax(vs_account_maximum_observed_quote_age_seconds, age_seconds);
  }


void VSAccountCollectSnapshot(VSAccountSnapshot &snapshot)
  {
   snapshot.server_time = TimeCurrent();
   snapshot.server_minute = (long)snapshot.server_time / 60;
   snapshot.actual_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   snapshot.actual_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   snapshot.stressed_balance = portfolio_state.stressed_balance;
   snapshot.conservative_stressed_mark =
      portfolio_state.stressed_balance - vs_account_positive_closed_swap;
   snapshot.conservative_mark_known = true;
   snapshot.conservative_mark_status = "KNOWN";
   snapshot.conservative_risk_capital = ConservativeRiskCapital();
   snapshot.day_volume_multiplier = portfolio_state.day_volume_multiplier;
   snapshot.owned_open_volume = 0.0;
   snapshot.owned_pending_volume = 0.0;
   snapshot.tracked_aggregate_planned_risk =
      TrackedAggregatePlannedRisk();
   snapshot.row_maximum_quote_age_seconds = 0.0;
   snapshot.quote_age_known = true;
   snapshot.owned_position_count = 0;
   snapshot.owned_pending_count = 0;
   snapshot.entry_state_unknown = false;
   snapshot.position_quote_unknown = false;

   if(snapshot.server_time <= 0 ||
      !MathIsValidNumber(snapshot.actual_balance) ||
      !MathIsValidNumber(snapshot.actual_equity) ||
      !MathIsValidNumber(snapshot.stressed_balance) ||
      !MathIsValidNumber(vs_account_positive_closed_swap) ||
      !MathIsValidNumber(snapshot.conservative_risk_capital) ||
      !MathIsValidNumber(snapshot.tracked_aggregate_planned_risk))
      VSAccountMarkUnknown(snapshot,
                           "BASE_STATE_UNKNOWN",
                           true,
                           false);

   int observed_components[COMPONENT_COUNT];
   ArrayInitialize(observed_components, 0);

   const int position_total = PositionsTotal();
   for(int index = position_total - 1; index >= 0; --index)
     {
      const ulong ticket = PositionGetTicket(index);
      if(ticket == 0)
         continue;
      const int component = VSSelectedPositionComponent();
      if(component < 0)
         continue;

      ++snapshot.owned_position_count;
      ++observed_components[component];
      const double remaining_volume = PositionGetDouble(POSITION_VOLUME);
      snapshot.owned_open_volume += remaining_volume;

      MqlTick tick = {};
      bool quote_known = false;
      VSAccountObserveQuoteAge(snapshot,
                               component_definitions[component].symbol,
                               true,
                               tick,
                               quote_known);

      const ulong identifier =
         (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      const double position_profit = PositionGetDouble(POSITION_PROFIT);
      const double position_swap = PositionGetDouble(POSITION_SWAP);
      const double contract_size =
         SymbolInfoDouble(component_definitions[component].symbol,
                          SYMBOL_TRADE_CONTRACT_SIZE);
      long broker_volume_steps = 0;
      long tracked_volume_steps = 0;
      const bool volume_reconciled =
         VolumeToSteps(component_definitions[component].symbol,
                       remaining_volume,
                       broker_volume_steps) &&
         VolumeToSteps(component_definitions[component].symbol,
                       component_states[component].entry_volume,
                       tracked_volume_steps) &&
         broker_volume_steps == tracked_volume_steps;
      const bool entry_state_known =
         observed_components[component] == 1 &&
         component_states[component].position_identifier == identifier &&
         identifier > 0 && volume_reconciled &&
         component_states[component].entry_cost_known &&
         component_states[component].entry_spread_price >= 0.0 &&
         component_states[component].entry_adverse_slippage >= 0.0 &&
         MathIsValidNumber(component_states[component].entry_spread_price) &&
         MathIsValidNumber(component_states[component].entry_transaction_cost) &&
         MathIsValidNumber(component_states[component].entry_adverse_slippage) &&
         MathIsValidNumber(position_profit) &&
         MathIsValidNumber(position_swap) &&
         MathIsValidNumber(contract_size) && contract_size > 0.0;
      if(!entry_state_known)
        {
         VSAccountMarkUnknown(snapshot,
                              "ENTRY_STATE_UNKNOWN",
                              true,
                              false);
         continue;
        }
      if(!quote_known)
         continue;

      // ApplyExitDeal has already reduced these three tracked fields after a
      // partial exit. They therefore represent the remaining position and are
      // not allocated by entry_volume again here.
      const double remaining_entry_transaction_cost =
         component_states[component].entry_transaction_cost;
      const double remaining_entry_adverse_slippage =
         component_states[component].entry_adverse_slippage;
      const double current_spread = tick.ask - tick.bid;
      const double stressed_spread =
         MathMax(component_states[component].entry_spread_price,
                 current_spread);
      snapshot.conservative_stressed_mark +=
         position_profit + MathMin(0.0, position_swap) +
         remaining_entry_transaction_cost -
         stressed_spread * contract_size * remaining_volume -
         remaining_entry_adverse_slippage -
         MathMax(0.0, -remaining_entry_transaction_cost) -
         MathMax(0.0, -position_swap);
     }

   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      const bool tracked_position =
         (component_states[component].position_identifier > 0);
      const bool residual_entry_state =
         (component_states[component].entry_volume != 0.0 ||
          component_states[component].entry_spread_price != 0.0 ||
          component_states[component].entry_transaction_cost != 0.0 ||
          component_states[component].entry_adverse_slippage != 0.0 ||
          component_states[component].entry_cost_known);
      if((tracked_position && observed_components[component] != 1) ||
         (!tracked_position &&
          (observed_components[component] != 0 || residual_entry_state)))
         VSAccountMarkUnknown(snapshot,
                              "ENTRY_RECONCILIATION_UNKNOWN",
                              true,
                              false);
     }

   const int order_total = OrdersTotal();
   for(int index = order_total - 1; index >= 0; --index)
     {
      const ulong ticket = OrderGetTicket(index);
      if(ticket == 0)
         continue;
      const int component = VSSelectedOrderComponent();
      if(component < 0)
         continue;
      ++snapshot.owned_pending_count;
      const double remaining_volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
      if(MathIsValidNumber(remaining_volume) && remaining_volume >= 0.0)
         snapshot.owned_pending_volume += remaining_volume;
      else
        {
         snapshot.quote_age_known = false;
         ++vs_account_evidence_faults;
        }
      MqlTick tick = {};
      bool quote_known = false;
      VSAccountObserveQuoteAge(snapshot,
                               component_definitions[component].symbol,
                               false,
                               tick,
                               quote_known);
     }

   if(!MathIsValidNumber(snapshot.conservative_stressed_mark))
      VSAccountMarkUnknown(snapshot,
                           "CONSERVATIVE_MARK_NONFINITE",
                           true,
                           false);
  }


bool VSAccountWriteHeader()
  {
   ResetLastError();
   const uint written =
      FileWrite(vs_account_handle,
                "server_time", "server_time_epoch", "server_minute_epoch",
                "forced", "actual_balance", "actual_equity",
                "original_stressed_balance", "conservative_stressed_mark",
                "conservative_mark_known", "conservative_mark_status",
                "positive_closed_swap", "conservative_risk_capital",
                "day_volume_multiplier", "owned_open_volume",
                "owned_pending_volume", "tracked_aggregate_planned_risk",
                "row_maximum_quote_age_seconds",
                "maximum_observed_quote_age_seconds", "quote_age_known",
                "owned_position_count", "owned_pending_count",
                "mark_skip_total", "entry_state_skip_total",
                "position_quote_skip_total", "quote_age_unknown_row_total",
                "write_fault_total", "evidence_fault_total");
   if(written == 0)
     {
      VSAccountRecordFileFault("HEADER_WRITE", GetLastError());
      return(false);
     }
   ResetLastError();
   FileFlush(vs_account_handle);
   const int flush_error = GetLastError();
   if(flush_error != 0)
     {
      VSAccountRecordFileFault("HEADER_FLUSH", flush_error);
      return(false);
     }
   return(true);
  }


bool VSAccountInit(const string root_path)
  {
   vs_account_handle = INVALID_HANDLE;
   vs_account_path = root_path + "\\equity.csv";
   vs_account_initialized = false;
   vs_account_rows = 0;
   vs_account_write_faults = 0;
   vs_account_evidence_faults = 0;
   vs_account_mark_skips = 0;
   vs_account_entry_state_skips = 0;
   vs_account_quote_skips = 0;
   vs_account_quote_age_unknown_rows = 0;
   vs_account_last_server_minute = -1;
   vs_account_positive_closed_swap = 0.0;
   vs_account_maximum_observed_quote_age_seconds = 0.0;
   vs_account_last_mark_known = false;
   vs_account_last_owned_position_count = 0;
   vs_account_last_owned_pending_count = 0;
   vs_account_last_owned_open_volume = 0.0;
   vs_account_last_owned_pending_volume = 0.0;
   vs_account_last_mark_status = "NOT_OBSERVED";

   if(!MQLInfoInteger(MQL_TESTER) || root_path == "")
     {
      VSAccountRecordFileFault("INIT_SCOPE", 0);
      return(false);
     }

   ResetLastError();
   if(FileIsExist(vs_account_path))
     {
      VSAccountRecordFileFault("PREEXISTING_OUTPUT", 0);
      return(false);
     }

   ResetLastError();
   vs_account_handle =
      FileOpen(vs_account_path,
               FILE_WRITE | FILE_CSV | FILE_ANSI,
               ',');
   if(vs_account_handle == INVALID_HANDLE)
     {
      VSAccountRecordFileFault("OPEN", GetLastError());
      return(false);
     }
   if(!VSAccountWriteHeader())
     {
      FileClose(vs_account_handle);
      vs_account_handle = INVALID_HANDLE;
      return(false);
     }

   vs_account_initialized = true;
   VSAccountObserve(true);
   if(vs_account_rows != 1 || vs_account_write_faults != 0)
     {
      ++vs_account_evidence_faults;
      PrintFormat("VS_ACCOUNT_INIT_FAULT rows=%I64d write_faults=%I64d path=%s",
                  vs_account_rows,
                  vs_account_write_faults,
                  vs_account_path);
      ResetLastError();
      FileClose(vs_account_handle);
      const int close_error = GetLastError();
      if(close_error != 0)
         VSAccountRecordFileFault("INIT_CLOSE", close_error);
      vs_account_handle = INVALID_HANDLE;
      vs_account_initialized = false;
      return(false);
     }
   PrintFormat("VS_ACCOUNT_INIT path=%s rows=%I64d",
               vs_account_path,
               vs_account_rows);
   return(true);
  }


void VSAccountObserve(bool force)
  {
   if(!vs_account_initialized || vs_account_handle == INVALID_HANDLE)
     {
      VSAccountRecordFileFault("OBSERVE_NOT_INITIALIZED", 0);
      return;
     }

   const datetime current_server = TimeCurrent();
   const long current_minute = (long)current_server / 60;
   if(!force && current_minute == vs_account_last_server_minute)
      return;

   VSAccountSnapshot snapshot = {};
   VSAccountCollectSnapshot(snapshot);
   if(!snapshot.conservative_mark_known)
     {
      ++vs_account_mark_skips;
      if(snapshot.entry_state_unknown)
         ++vs_account_entry_state_skips;
      if(snapshot.position_quote_unknown)
         ++vs_account_quote_skips;
     }
   if(!snapshot.quote_age_known)
      ++vs_account_quote_age_unknown_rows;

   vs_account_last_mark_known = snapshot.conservative_mark_known;
   vs_account_last_owned_position_count = snapshot.owned_position_count;
   vs_account_last_owned_pending_count = snapshot.owned_pending_count;
   vs_account_last_owned_open_volume = snapshot.owned_open_volume;
   vs_account_last_owned_pending_volume = snapshot.owned_pending_volume;
   vs_account_last_mark_status = snapshot.conservative_mark_status;

   const string mark_value =
      (snapshot.conservative_mark_known
       ? DoubleToString(snapshot.conservative_stressed_mark, 10) : "");
   const string row_quote_age =
      (snapshot.quote_age_known
       ? DoubleToString(snapshot.row_maximum_quote_age_seconds, 3) : "");

   ResetLastError();
   const uint written =
      FileWrite(vs_account_handle,
                TimeToString(snapshot.server_time, TIME_DATE | TIME_SECONDS),
                (long)snapshot.server_time,
                snapshot.server_minute,
                (force ? 1 : 0),
                DoubleToString(snapshot.actual_balance, 10),
                DoubleToString(snapshot.actual_equity, 10),
                DoubleToString(snapshot.stressed_balance, 10),
                mark_value,
                (snapshot.conservative_mark_known ? 1 : 0),
                snapshot.conservative_mark_status,
                DoubleToString(vs_account_positive_closed_swap, 10),
                DoubleToString(snapshot.conservative_risk_capital, 10),
                snapshot.day_volume_multiplier,
                DoubleToString(snapshot.owned_open_volume, 10),
                DoubleToString(snapshot.owned_pending_volume, 10),
                DoubleToString(snapshot.tracked_aggregate_planned_risk, 10),
                row_quote_age,
                DoubleToString(vs_account_maximum_observed_quote_age_seconds, 3),
                (snapshot.quote_age_known ? 1 : 0),
                snapshot.owned_position_count,
                snapshot.owned_pending_count,
                vs_account_mark_skips,
                vs_account_entry_state_skips,
                vs_account_quote_skips,
                vs_account_quote_age_unknown_rows,
                vs_account_write_faults,
                vs_account_evidence_faults);
   if(written == 0)
     {
      VSAccountRecordFileFault("ROW_WRITE", GetLastError());
      return;
     }
   ++vs_account_rows;
   vs_account_last_server_minute = snapshot.server_minute;

   ResetLastError();
   FileFlush(vs_account_handle);
   const int flush_error = GetLastError();
   if(flush_error != 0)
      VSAccountRecordFileFault("ROW_FLUSH", flush_error);
  }


void VSRecordPositiveClosedSwap(double swap)
  {
   if(!MathIsValidNumber(swap))
     {
      ++vs_account_evidence_faults;
      PrintFormat("VS_ACCOUNT_SWAP_FAULT nonfinite swap evidence_faults=%I64d",
                  vs_account_evidence_faults);
      return;
     }
   if(swap > 0.0)
      vs_account_positive_closed_swap += swap;
  }


bool VSAccountLocalTrackingFlat()
  {
   if(execution_state.passive_pending_order != 0 ||
      passive_pending_planned_risk_usd != 0.0 ||
      TrackedAggregatePlannedRisk() != 0.0)
      return(false);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_states[component].position_identifier != 0 ||
         component_states[component].entry_volume != 0.0 ||
         component_states[component].entry_spread_price != 0.0 ||
         component_states[component].entry_transaction_cost != 0.0 ||
         component_states[component].entry_adverse_slippage != 0.0 ||
         component_states[component].entry_cost_known)
         return(false);
   return(true);
  }


void VSAccountEnd()
  {
   if(!vs_account_initialized || vs_account_handle == INVALID_HANDLE)
     {
      VSAccountRecordFileFault("END_NOT_INITIALIZED", 0);
      PrintFormat("VS_ACCOUNT_END rows=%I64d write_faults=%I64d "
                  "evidence_faults=%I64d positive_closed_swap=%.10f "
                  "flat=false mark_known=false path=%s",
                  vs_account_rows,
                  vs_account_write_faults,
                  vs_account_evidence_faults,
                  vs_account_positive_closed_swap,
                  vs_account_path);
      return;
     }

   VSAccountObserve(true);
   const bool flat =
      (vs_account_last_owned_position_count == 0 &&
       vs_account_last_owned_pending_count == 0 &&
       vs_account_last_owned_open_volume == 0.0 &&
       vs_account_last_owned_pending_volume == 0.0 &&
       VSAccountLocalTrackingFlat());
   const bool final_known = vs_account_last_mark_known;
   if(!flat || !final_known)
     {
      ++vs_account_evidence_faults;
      PrintFormat("VS_ACCOUNT_END_FAULT flat=%s mark_known=%s status=%s "
                  "positions=%d pending=%d open_volume=%.10f "
                  "pending_volume=%.10f evidence_faults=%I64d",
                  (flat ? "true" : "false"),
                  (final_known ? "true" : "false"),
                  vs_account_last_mark_status,
                  vs_account_last_owned_position_count,
                  vs_account_last_owned_pending_count,
                  vs_account_last_owned_open_volume,
                  vs_account_last_owned_pending_volume,
                  vs_account_evidence_faults);
     }

   ResetLastError();
   FileFlush(vs_account_handle);
   const int flush_error = GetLastError();
   if(flush_error != 0)
      VSAccountRecordFileFault("END_FLUSH", flush_error);
   ResetLastError();
   FileClose(vs_account_handle);
   const int close_error = GetLastError();
   if(close_error != 0)
      VSAccountRecordFileFault("CLOSE", close_error);
   vs_account_handle = INVALID_HANDLE;
   vs_account_initialized = false;

   PrintFormat("VS_ACCOUNT_END rows=%I64d write_faults=%I64d "
               "evidence_faults=%I64d mark_skips=%I64d "
               "entry_state_skips=%I64d position_quote_skips=%I64d "
               "quote_age_unknown_rows=%I64d positive_closed_swap=%.10f "
               "maximum_quote_age_seconds=%.3f flat=%s mark_known=%s "
               "status=%s path=%s",
               vs_account_rows,
               vs_account_write_faults,
               vs_account_evidence_faults,
               vs_account_mark_skips,
               vs_account_entry_state_skips,
               vs_account_quote_skips,
               vs_account_quote_age_unknown_rows,
               vs_account_positive_closed_swap,
               vs_account_maximum_observed_quote_age_seconds,
               (flat ? "true" : "false"),
               (final_known ? "true" : "false"),
               vs_account_last_mark_status,
               vs_account_path);
  }

#endif
