#property strict
#property version   "1.00"
#property description "Trade-free US30 compression-break response observer for Zeta Next Lab Unit 029."

input int InpRunCode = 1;

const string OBSERVER_ID = "ZETA-NEXT-US30-COMPRESSION-BREAK-RESPONSE-V1";
const int RECENT_RETURNS = 12;
const int REFERENCE_RETURNS = 36;
const int REQUIRED_BARS = RECENT_RETURNS + REFERENCE_RETURNS + 1;
const int RANGE_BARS = 12;
const int HORIZON_BARS = 12;
const long M5_SECONDS = 300;
const double COMPRESSION_THRESHOLD = 0.65;
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
datetime g_last_bar_time = 0;
int g_last_eligible_day_key = -1;
bool g_active = false;
int g_market_bars_held = 0;
long g_evaluations = 0;
long g_eligible_continuous_days = 0;
long g_eligible_compression_evaluations = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_rate_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;
datetime g_trigger_time = 0;
datetime g_trigger_bar_time = 0;
double g_trigger_recent_volatility = 0.0;
double g_trigger_reference_volatility = 0.0;
double g_trigger_compression_ratio = 0.0;
double g_trigger_range_high = 0.0;
double g_trigger_range_low = 0.0;
double g_trigger_mid = 0.0;
int g_break_direction = 0;
double g_entry_bid = 0.0;
double g_entry_ask = 0.0;
double g_entry_spread = 0.0;
ContractSnapshot g_start_spec;
ContractSnapshot g_end_spec;
string g_output_directory = "";

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
             "trigger_bar_time",
             "trigger_tick_time",
             "resolve_time",
             "elapsed_seconds",
             "market_bars_held",
             "recent_volatility",
             "reference_volatility",
             "compression_ratio",
             "range_high",
             "range_low",
             "break_mid",
             "break_direction",
             "entry_bid",
             "entry_ask",
             "entry_spread",
             "exit_bid",
             "exit_ask",
             "exit_spread",
             "continuation_direction",
             "reversion_direction",
             "continuation_observed_usd",
             "continuation_double_spread_usd",
             "reversion_observed_usd",
             "reversion_double_spread_usd",
             "calc_ok");
}

bool OpenOpportunityFile()
{
   FolderCreate("US30CompressionBreakResponseV1");
   g_output_directory =
      StringFormat("US30CompressionBreakResponseV1\\run-%d", InpRunCode);
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

bool SampleStandardDeviation(const double &values[],
                             const int count,
                             double &standard_deviation)
{
   if(count < 2 || ArraySize(values) < count)
      return(false);

   double mean = 0.0;
   for(int index = 0; index < count; ++index)
   {
      if(!MathIsValidNumber(values[index]))
         return(false);
      mean += values[index];
   }
   mean /= (double)count;

   double squared_sum = 0.0;
   for(int index = 0; index < count; ++index)
   {
      double deviation = values[index] - mean;
      squared_sum += deviation * deviation;
   }
   standard_deviation = MathSqrt(squared_sum / (double)(count - 1));
   return(MathIsValidNumber(standard_deviation));
}

bool ReadCompressionState(const datetime current_bar_time,
                          const MqlTick &current_tick,
                          bool &continuous,
                          bool &volatility_valid,
                          double &recent_volatility,
                          double &reference_volatility,
                          double &compression_ratio,
                          double &range_high,
                          double &range_low,
                          double &current_mid,
                          int &break_direction)
{
   continuous = false;
   volatility_valid = false;
   recent_volatility = 0.0;
   reference_volatility = 0.0;
   compression_ratio = 0.0;
   range_high = 0.0;
   range_low = 0.0;
   current_mid = 0.0;
   break_direction = 0;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M5, 1, REQUIRED_BARS, rates);
   if(copied != REQUIRED_BARS)
      return(false);

   if((long)current_bar_time - (long)rates[0].time != M5_SECONDS)
      return(true);
   for(int index = 0; index < REQUIRED_BARS - 1; ++index)
   {
      if((long)rates[index].time - (long)rates[index + 1].time != M5_SECONDS)
         return(true);
   }
   continuous = true;

   double recent_values[];
   double reference_values[];
   ArrayResize(recent_values, RECENT_RETURNS);
   ArrayResize(reference_values, REFERENCE_RETURNS);

   for(int index = 0; index < REQUIRED_BARS; ++index)
   {
      if(rates[index].close <= 0.0 ||
         rates[index].high <= 0.0 ||
         rates[index].low <= 0.0 ||
         rates[index].high < rates[index].low)
         return(false);
   }

   for(int index = 0; index < RECENT_RETURNS; ++index)
      recent_values[index] = MathLog(rates[index].close / rates[index + 1].close);
   for(int index = 0; index < REFERENCE_RETURNS; ++index)
   {
      int offset = RECENT_RETURNS + index;
      reference_values[index] = MathLog(rates[offset].close / rates[offset + 1].close);
   }

   if(!SampleStandardDeviation(recent_values,
                               RECENT_RETURNS,
                               recent_volatility) ||
      !SampleStandardDeviation(reference_values,
                               REFERENCE_RETURNS,
                               reference_volatility))
      return(false);
   if(reference_volatility <= 0.0)
      return(true);

   compression_ratio = recent_volatility / reference_volatility;
   if(!MathIsValidNumber(compression_ratio))
      return(false);
   volatility_valid = true;

   range_high = rates[0].high;
   range_low = rates[0].low;
   for(int index = 1; index < RANGE_BARS; ++index)
   {
      if(rates[index].high > range_high)
         range_high = rates[index].high;
      if(rates[index].low < range_low)
         range_low = rates[index].low;
   }

   current_mid = 0.5 * (current_tick.bid + current_tick.ask);
   if(current_mid > range_high)
      break_direction = 1;
   else if(current_mid < range_low)
      break_direction = -1;
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
   int continuation_direction = g_break_direction;
   int reversion_direction = -g_break_direction;
   double continuation_observed = 0.0;
   double continuation_double = 0.0;
   double reversion_observed = 0.0;
   double reversion_double = 0.0;

   bool calc_ok =
      CalculateDirectionProfit(continuation_direction,
                               false,
                               exit_tick,
                               continuation_observed) &&
      CalculateDirectionProfit(continuation_direction,
                               true,
                               exit_tick,
                               continuation_double) &&
      CalculateDirectionProfit(reversion_direction,
                               false,
                               exit_tick,
                               reversion_observed) &&
      CalculateDirectionProfit(reversion_direction,
                               true,
                               exit_tick,
                               reversion_double);
   if(!calc_ok)
      ++g_profit_calc_faults;

   ++g_resolved;
   double exit_spread = exit_tick.ask - exit_tick.bid;
   long elapsed_seconds = (long)exit_tick.time - (long)g_trigger_time;
   FileWrite(g_opportunity_handle,
             OBSERVER_ID,
             InpRunCode,
             g_resolved,
             TimeToString(g_trigger_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_trigger_time, TIME_DATE | TIME_SECONDS),
             TimeToString(exit_tick.time, TIME_DATE | TIME_SECONDS),
             elapsed_seconds,
             g_market_bars_held,
             DoubleToString(g_trigger_recent_volatility, 12),
             DoubleToString(g_trigger_reference_volatility, 12),
             DoubleToString(g_trigger_compression_ratio, 12),
             DoubleToString(g_trigger_range_high, _Digits),
             DoubleToString(g_trigger_range_low, _Digits),
             DoubleToString(g_trigger_mid, _Digits),
             g_break_direction,
             DoubleToString(g_entry_bid, _Digits),
             DoubleToString(g_entry_ask, _Digits),
             DoubleToString(g_entry_spread, _Digits),
             DoubleToString(exit_tick.bid, _Digits),
             DoubleToString(exit_tick.ask, _Digits),
             DoubleToString(exit_spread, _Digits),
             continuation_direction,
             reversion_direction,
             DoubleToString(continuation_observed, 8),
             DoubleToString(continuation_double, 8),
             DoubleToString(reversion_observed, 8),
             DoubleToString(reversion_double, 8),
             calc_ok ? 1 : 0);
   FileFlush(g_opportunity_handle);

   g_active = false;
   g_market_bars_held = 0;
}

void StartObservation(const datetime current_bar_time,
                      const double recent_volatility,
                      const double reference_volatility,
                      const double compression_ratio,
                      const double range_high,
                      const double range_low,
                      const double current_mid,
                      const int break_direction,
                      const MqlTick &entry_tick)
{
   g_active = true;
   g_market_bars_held = 0;
   ++g_triggers;
   g_trigger_time = entry_tick.time;
   g_trigger_bar_time = current_bar_time;
   g_trigger_recent_volatility = recent_volatility;
   g_trigger_reference_volatility = reference_volatility;
   g_trigger_compression_ratio = compression_ratio;
   g_trigger_range_high = range_high;
   g_trigger_range_low = range_low;
   g_trigger_mid = current_mid;
   g_break_direction = break_direction;
   g_entry_bid = entry_tick.bid;
   g_entry_ask = entry_tick.ask;
   g_entry_spread = entry_tick.ask - entry_tick.bid;
}

void CountEligibleContinuousDay(const datetime bar_time)
{
   MqlDateTime parts;
   TimeToStruct(bar_time, parts);
   int day_key = parts.year * 1000 + parts.day_of_year;
   if(day_key != g_last_eligible_day_key)
   {
      g_last_eligible_day_key = day_key;
      ++g_eligible_continuous_days;
   }
}

void ProcessNewBar(const datetime current_bar_time)
{
   MqlTick current_tick;
   if(!ReadValidTick(current_tick))
   {
      ++g_tick_faults;
      return;
   }
   ++g_evaluations;

   if(g_active)
   {
      ++g_market_bars_held;
      if(g_market_bars_held >= HORIZON_BARS)
         ResolveObservation(current_tick);
      else
         return;
   }

   bool continuous = false;
   bool volatility_valid = false;
   double recent_volatility = 0.0;
   double reference_volatility = 0.0;
   double compression_ratio = 0.0;
   double range_high = 0.0;
   double range_low = 0.0;
   double current_mid = 0.0;
   int break_direction = 0;
   if(!ReadCompressionState(current_bar_time,
                            current_tick,
                            continuous,
                            volatility_valid,
                            recent_volatility,
                            reference_volatility,
                            compression_ratio,
                            range_high,
                            range_low,
                            current_mid,
                            break_direction))
   {
      ++g_rate_faults;
      return;
   }
   if(!continuous || !volatility_valid)
      return;

   CountEligibleContinuousDay(current_bar_time);
   if(compression_ratio > COMPRESSION_THRESHOLD)
      return;

   ++g_eligible_compression_evaluations;
   if(break_direction == 0)
      return;

   StartObservation(current_bar_time,
                    recent_volatility,
                    reference_volatility,
                    compression_ratio,
                    range_high,
                    range_low,
                    current_mid,
                    break_direction,
                    current_tick);
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
             "eligible_continuous_days",
             "eligible_compression_evaluations",
             "evaluations",
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
             g_eligible_continuous_days,
             g_eligible_compression_evaluations,
             g_evaluations,
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
   if(_Symbol != "US30" || _Period != PERIOD_M5)
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

   PrintFormat("%s START run=%d symbol=%s recent=%d reference=%d compression=%.2f range=%d horizon=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               RECENT_RETURNS,
               REFERENCE_RETURNS,
               COMPRESSION_THRESHOLD,
               RANGE_BARS,
               HORIZON_BARS);
   return(INIT_SUCCEEDED);
}

void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_M5, 0);
   if(current_bar_time <= 0 || current_bar_time == g_last_bar_time)
      return;
   g_last_bar_time = current_bar_time;
   ProcessNewBar(current_bar_time);
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

   PrintFormat("%s STOP run=%d reason=%d continuous_days=%I64d compression_evaluations=%I64d evaluations=%I64d triggers=%I64d resolved=%I64d unresolved=%d rate_faults=%I64d tick_faults=%I64d calc_faults=%I64d",
               OBSERVER_ID,
               InpRunCode,
               reason,
               g_eligible_continuous_days,
               g_eligible_compression_evaluations,
               g_evaluations,
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
