#property strict
#property version   "1.00"
#property description "Trade-free US100 completed-M5 failed-extreme auction observer for Zeta Next Lab Unit 031."

input int InpRunCode = 1;

const string OBSERVER_ID = "ZETA-NEXT-US100-FAILED-EXTREME-AUCTION-RESPONSE-V1";
const long M5_SECONDS = 300;
const int REFERENCE_BARS = 24;
const int HORIZON_BARS = 6;
const double PENETRATION_FRACTION = 0.10;
const double RECOVERY_FRACTION = 0.10;
const double OBSERVATION_VOLUME = 0.01;

struct ContractSnapshot
{
   long digits;
   double point;
   double tick_size;
   double tick_value;
   double contract_size;
   double volume_min;
   double volume_step;
   long stops_level;
   long freeze_level;
};

int g_opportunity_handle = INVALID_HANDLE;
string g_output_directory = "";
ContractSnapshot g_start_spec;
ContractSnapshot g_end_spec;

datetime g_current_bar_time = 0;
int g_last_eligible_day_key = -1;
long g_eligible_failed_extreme_days = 0;
long g_eligible_failed_extreme_evaluations = 0;
long g_finalized_bars = 0;
long g_valid_ticks = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_rate_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;

bool g_active = false;
int g_market_bars_held = 0;
datetime g_signal_bar_time = 0;
datetime g_entry_bar_time = 0;
datetime g_trigger_time = 0;
double g_reference_high = 0.0;
double g_reference_low = 0.0;
double g_reference_mean_range = 0.0;
double g_signal_open = 0.0;
double g_signal_high = 0.0;
double g_signal_low = 0.0;
double g_signal_close = 0.0;
int g_failed_side = 0;
double g_penetration = 0.0;
double g_recovery = 0.0;
int g_rejection_direction = 0;
double g_entry_bid = 0.0;
double g_entry_ask = 0.0;
double g_entry_spread = 0.0;

bool CaptureContractSnapshot(ContractSnapshot &snapshot)
{
   snapshot.digits = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   snapshot.point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   snapshot.tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   snapshot.tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   snapshot.contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   snapshot.volume_min = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   snapshot.volume_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   snapshot.stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   snapshot.freeze_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);

   return(snapshot.digits >= 0 &&
          snapshot.point > 0.0 &&
          snapshot.tick_size > 0.0 &&
          snapshot.tick_value > 0.0 &&
          snapshot.contract_size > 0.0 &&
          snapshot.volume_min > 0.0 &&
          snapshot.volume_step > 0.0);
}

void WriteOpportunityHeader()
{
   FileWrite(g_opportunity_handle,
             "observer_id",
             "run_code",
             "opportunity_id",
             "signal_bar_time",
             "entry_bar_time",
             "trigger_tick_time",
             "resolve_time",
             "elapsed_seconds",
             "market_bars_held",
             "reference_high",
             "reference_low",
             "reference_mean_range",
             "signal_open",
             "signal_high",
             "signal_low",
             "signal_close",
             "failed_side",
             "penetration",
             "recovery",
             "entry_bid",
             "entry_ask",
             "entry_spread",
             "exit_bid",
             "exit_ask",
             "exit_spread",
             "rejection_direction",
             "breakout_direction",
             "rejection_observed_usd",
             "rejection_double_spread_usd",
             "breakout_observed_usd",
             "breakout_double_spread_usd",
             "calc_ok");
}

bool OpenOpportunityFile()
{
   FolderCreate("US100FailedExtremeAuctionResponseV1");
   g_output_directory =
      StringFormat("US100FailedExtremeAuctionResponseV1\\run-%d", InpRunCode);
   FolderCreate(g_output_directory);
   string path = g_output_directory + "\\opportunities.csv";
   g_opportunity_handle =
      FileOpen(path,
               FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
               ',');
   if(g_opportunity_handle == INVALID_HANDLE)
   {
      PrintFormat("%s FILE_OPEN_FAILED run=%d error=%d path=%s",
                  OBSERVER_ID,
                  InpRunCode,
                  GetLastError(),
                  path);
      return(false);
   }
   WriteOpportunityHeader();
   FileFlush(g_opportunity_handle);
   return(true);
}

bool ReadValidTick(MqlTick &tick)
{
   if(!SymbolInfoTick(_Symbol, tick))
      return(false);
   return(tick.bid > 0.0 && tick.ask > 0.0 && tick.ask >= tick.bid);
}

bool IsValidRate(const MqlRates &rate)
{
   if(rate.time <= 0 ||
      rate.open <= 0.0 ||
      rate.high <= 0.0 ||
      rate.low <= 0.0 ||
      rate.close <= 0.0)
      return(false);
   if(rate.high < rate.low ||
      rate.high < rate.open ||
      rate.high < rate.close ||
      rate.low > rate.open ||
      rate.low > rate.close)
      return(false);
   return(true);
}

bool CalculateDirectionProfit(const int direction,
                              const bool double_spread,
                              const MqlTick &exit_tick,
                              double &profit)
{
   double exit_spread = exit_tick.ask - exit_tick.bid;
   double open_price = 0.0;
   double close_price = 0.0;
   ENUM_ORDER_TYPE order_type = ORDER_TYPE_BUY;

   if(direction > 0)
   {
      order_type = ORDER_TYPE_BUY;
      open_price = g_entry_ask;
      close_price = exit_tick.bid;
      if(double_spread)
      {
         open_price += g_entry_spread;
         close_price -= exit_spread;
      }
   }
   else
   {
      order_type = ORDER_TYPE_SELL;
      open_price = g_entry_bid;
      close_price = exit_tick.ask;
      if(double_spread)
      {
         open_price -= g_entry_spread;
         close_price += exit_spread;
      }
   }

   if(open_price <= 0.0 || close_price <= 0.0)
      return(false);
   return(OrderCalcProfit(order_type,
                          _Symbol,
                          OBSERVATION_VOLUME,
                          open_price,
                          close_price,
                          profit));
}

void ResolveObservation(const MqlTick &exit_tick)
{
   int breakout_direction = -g_rejection_direction;
   double rejection_observed = 0.0;
   double rejection_double = 0.0;
   double breakout_observed = 0.0;
   double breakout_double = 0.0;

   bool calc_ok =
      CalculateDirectionProfit(g_rejection_direction,
                               false,
                               exit_tick,
                               rejection_observed) &&
      CalculateDirectionProfit(g_rejection_direction,
                               true,
                               exit_tick,
                               rejection_double) &&
      CalculateDirectionProfit(breakout_direction,
                               false,
                               exit_tick,
                               breakout_observed) &&
      CalculateDirectionProfit(breakout_direction,
                               true,
                               exit_tick,
                               breakout_double);
   if(!calc_ok)
      ++g_profit_calc_faults;

   ++g_resolved;
   double exit_spread = exit_tick.ask - exit_tick.bid;
   long elapsed_seconds = (long)exit_tick.time - (long)g_trigger_time;
   FileWrite(g_opportunity_handle,
             OBSERVER_ID,
             InpRunCode,
             g_resolved,
             TimeToString(g_signal_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_entry_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_trigger_time, TIME_DATE | TIME_SECONDS),
             TimeToString(exit_tick.time, TIME_DATE | TIME_SECONDS),
             elapsed_seconds,
             g_market_bars_held,
             DoubleToString(g_reference_high, _Digits),
             DoubleToString(g_reference_low, _Digits),
             DoubleToString(g_reference_mean_range, 8),
             DoubleToString(g_signal_open, _Digits),
             DoubleToString(g_signal_high, _Digits),
             DoubleToString(g_signal_low, _Digits),
             DoubleToString(g_signal_close, _Digits),
             g_failed_side,
             DoubleToString(g_penetration, 8),
             DoubleToString(g_recovery, 8),
             DoubleToString(g_entry_bid, _Digits),
             DoubleToString(g_entry_ask, _Digits),
             DoubleToString(g_entry_spread, _Digits),
             DoubleToString(exit_tick.bid, _Digits),
             DoubleToString(exit_tick.ask, _Digits),
             DoubleToString(exit_spread, _Digits),
             g_rejection_direction,
             breakout_direction,
             DoubleToString(rejection_observed, 8),
             DoubleToString(rejection_double, 8),
             DoubleToString(breakout_observed, 8),
             DoubleToString(breakout_double, 8),
             calc_ok ? 1 : 0);
   FileFlush(g_opportunity_handle);

   g_active = false;
   g_market_bars_held = 0;
}

void StartObservation(const MqlRates &signal,
                      const datetime entry_bar_time,
                      const double reference_high,
                      const double reference_low,
                      const double reference_mean_range,
                      const int failed_side,
                      const double penetration,
                      const double recovery,
                      const MqlTick &entry_tick)
{
   g_active = true;
   g_market_bars_held = 0;
   ++g_triggers;
   g_signal_bar_time = signal.time;
   g_entry_bar_time = entry_bar_time;
   g_trigger_time = entry_tick.time;
   g_reference_high = reference_high;
   g_reference_low = reference_low;
   g_reference_mean_range = reference_mean_range;
   g_signal_open = signal.open;
   g_signal_high = signal.high;
   g_signal_low = signal.low;
   g_signal_close = signal.close;
   g_failed_side = failed_side;
   g_penetration = penetration;
   g_recovery = recovery;
   g_rejection_direction = -failed_side;
   g_entry_bid = entry_tick.bid;
   g_entry_ask = entry_tick.ask;
   g_entry_spread = entry_tick.ask - entry_tick.bid;
}

void CountEligibleFailedExtremeDay(const datetime bar_time)
{
   MqlDateTime parts;
   TimeToStruct(bar_time, parts);
   int day_key = parts.year * 1000 + parts.day_of_year;
   if(day_key != g_last_eligible_day_key)
   {
      g_last_eligible_day_key = day_key;
      ++g_eligible_failed_extreme_days;
   }
}

void EvaluateCompletedBar(const datetime new_bar_time,
                          const MqlTick &entry_tick)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int required = REFERENCE_BARS + 2;
   ResetLastError();
   int copied = CopyRates(_Symbol, PERIOD_M5, 0, required, rates);
   if(copied != required)
   {
      ++g_rate_faults;
      return;
   }
   if(rates[0].time != new_bar_time)
   {
      ++g_rate_faults;
      return;
   }
   for(int index = 0; index < required; ++index)
   {
      if(!IsValidRate(rates[index]))
      {
         ++g_rate_faults;
         return;
      }
   }
   for(int index = 0; index < required - 1; ++index)
   {
      if((long)rates[index].time - (long)rates[index + 1].time != M5_SECONDS)
         return;
   }

   double reference_high = rates[2].high;
   double reference_low = rates[2].low;
   double range_sum = 0.0;
   for(int index = 2; index < required; ++index)
   {
      if(rates[index].high > reference_high)
         reference_high = rates[index].high;
      if(rates[index].low < reference_low)
         reference_low = rates[index].low;
      range_sum += rates[index].high - rates[index].low;
   }
   double reference_mean_range = range_sum / (double)REFERENCE_BARS;
   if(reference_mean_range <= 0.0 ||
      !MathIsValidNumber(reference_mean_range))
   {
      ++g_rate_faults;
      return;
   }

   ++g_eligible_failed_extreme_evaluations;
   CountEligibleFailedExtremeDay(new_bar_time);

   MqlRates signal = rates[1];
   double upper_penetration = signal.high - reference_high;
   double upper_recovery = reference_high - signal.close;
   double lower_penetration = reference_low - signal.low;
   double lower_recovery = signal.close - reference_low;
   double penetration_minimum = PENETRATION_FRACTION * reference_mean_range;
   double recovery_minimum = RECOVERY_FRACTION * reference_mean_range;
   bool upper_failed =
      upper_penetration >= penetration_minimum &&
      upper_recovery >= recovery_minimum;
   bool lower_failed =
      lower_penetration >= penetration_minimum &&
      lower_recovery >= recovery_minimum;

   if(upper_failed == lower_failed)
      return;
   if(upper_failed)
   {
      StartObservation(signal,
                       new_bar_time,
                       reference_high,
                       reference_low,
                       reference_mean_range,
                       1,
                       upper_penetration,
                       upper_recovery,
                       entry_tick);
   }
   else
   {
      StartObservation(signal,
                       new_bar_time,
                       reference_high,
                       reference_low,
                       reference_mean_range,
                       -1,
                       lower_penetration,
                       lower_recovery,
                       entry_tick);
   }
}

void ProcessBarBoundary(const datetime new_bar_time,
                        const MqlTick &entry_tick)
{
   ++g_finalized_bars;

   if(g_active)
   {
      ++g_market_bars_held;
      if(g_market_bars_held >= HORIZON_BARS)
         ResolveObservation(entry_tick);
   }

   if(g_active)
      return;
   EvaluateCompletedBar(new_bar_time, entry_tick);
}

void WriteSummaryFile()
{
   string path = g_output_directory + "\\summary.csv";
   int handle =
      FileOpen(path,
               FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
               ',');
   if(handle == INVALID_HANDLE)
      return;

   FileWrite(handle,
             "observer_id",
             "run_code",
             "eligible_failed_extreme_days",
             "eligible_failed_extreme_evaluations",
             "finalized_bars",
             "valid_ticks",
             "triggers",
             "resolved",
             "unresolved",
             "rate_faults",
             "tick_faults",
             "profit_calc_faults",
             "start_digits",
             "end_digits",
             "start_point",
             "end_point",
             "start_tick_size",
             "end_tick_size",
             "start_tick_value",
             "end_tick_value",
             "start_contract_size",
             "end_contract_size",
             "start_volume_min",
             "end_volume_min",
             "start_volume_step",
             "end_volume_step",
             "start_stops_level",
             "end_stops_level",
             "start_freeze_level",
             "end_freeze_level");

   FileWrite(handle,
             OBSERVER_ID,
             InpRunCode,
             g_eligible_failed_extreme_days,
             g_eligible_failed_extreme_evaluations,
             g_finalized_bars,
             g_valid_ticks,
             g_triggers,
             g_resolved,
             g_active ? 1 : 0,
             g_rate_faults,
             g_tick_faults,
             g_profit_calc_faults,
             g_start_spec.digits,
             g_end_spec.digits,
             DoubleToString(g_start_spec.point, 12),
             DoubleToString(g_end_spec.point, 12),
             DoubleToString(g_start_spec.tick_size, 12),
             DoubleToString(g_end_spec.tick_size, 12),
             DoubleToString(g_start_spec.tick_value, 12),
             DoubleToString(g_end_spec.tick_value, 12),
             DoubleToString(g_start_spec.contract_size, 8),
             DoubleToString(g_end_spec.contract_size, 8),
             DoubleToString(g_start_spec.volume_min, 8),
             DoubleToString(g_end_spec.volume_min, 8),
             DoubleToString(g_start_spec.volume_step, 8),
             DoubleToString(g_end_spec.volume_step, 8),
             g_start_spec.stops_level,
             g_end_spec.stops_level,
             g_start_spec.freeze_level,
             g_end_spec.freeze_level);
   FileClose(handle);
}

int OnInit()
{
   if(_Symbol != "US100" || _Period != PERIOD_M5)
   {
      PrintFormat("%s INVALID_CHART symbol=%s period=%d",
                  OBSERVER_ID,
                  _Symbol,
                  _Period);
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpRunCode < 1 || InpRunCode > 4)
      return(INIT_PARAMETERS_INCORRECT);
   if(!CaptureContractSnapshot(g_start_spec))
      return(INIT_FAILED);
   if(!OpenOpportunityFile())
      return(INIT_FAILED);

   PrintFormat("%s START run=%d symbol=%s reference_bars=%d penetration=%.2f recovery=%.2f horizon=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               REFERENCE_BARS,
               PENETRATION_FRACTION,
               RECOVERY_FRACTION,
               HORIZON_BARS);
   return(INIT_SUCCEEDED);
}

void OnTick()
{
   MqlTick tick;
   if(!ReadValidTick(tick))
   {
      ++g_tick_faults;
      return;
   }
   ++g_valid_ticks;

   datetime bar_time = iTime(_Symbol, PERIOD_M5, 0);
   if(bar_time <= 0)
   {
      ++g_tick_faults;
      return;
   }
   if(g_current_bar_time == 0)
   {
      g_current_bar_time = bar_time;
      return;
   }
   if(bar_time == g_current_bar_time)
      return;
   if(bar_time < g_current_bar_time)
   {
      ++g_tick_faults;
      return;
   }

   ProcessBarBoundary(bar_time, tick);
   g_current_bar_time = bar_time;
}

void OnDeinit(const int reason)
{
   CaptureContractSnapshot(g_end_spec);
   if(g_opportunity_handle != INVALID_HANDLE)
   {
      FileFlush(g_opportunity_handle);
      FileClose(g_opportunity_handle);
      g_opportunity_handle = INVALID_HANDLE;
   }
   WriteSummaryFile();

   PrintFormat("%s STOP run=%d reason=%d eligible_days=%I64d eligible_evaluations=%I64d finalized_bars=%I64d valid_ticks=%I64d triggers=%I64d resolved=%I64d unresolved=%d rate_faults=%I64d tick_faults=%I64d calc_faults=%I64d",
               OBSERVER_ID,
               InpRunCode,
               reason,
               g_eligible_failed_extreme_days,
               g_eligible_failed_extreme_evaluations,
               g_finalized_bars,
               g_valid_ticks,
               g_triggers,
               g_resolved,
               g_active ? 1 : 0,
               g_rate_faults,
               g_tick_faults,
               g_profit_calc_faults);
}

double OnTester()
{
   return((double)g_resolved);
}
