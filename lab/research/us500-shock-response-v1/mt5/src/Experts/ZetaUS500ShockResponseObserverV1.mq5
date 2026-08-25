#property strict
#property version   "1.00"
#property description "Trade-free US500 completed-M15 shock response observer for Zeta Next Lab Unit 027."

input int InpRunCode = 1;

const string OBSERVER_ID = "ZETA-NEXT-US500-SHOCK-RESPONSE-V1";
const int IMPULSE_BARS = 4;
const int BASELINE_RETURNS = 32;
const int HORIZON_BARS = 4;
const double TRIGGER_Z = 2.0;
const double REARM_Z = 1.0;
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
int g_last_day_key = -1;
bool g_armed = true;
bool g_active = false;
int g_market_bars_held = 0;
long g_evaluations = 0;
long g_normal_days = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_rate_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;
datetime g_trigger_time = 0;
double g_trigger_score = 0.0;
double g_trigger_impulse = 0.0;
int g_impulse_sign = 0;
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
             "trigger_time",
             "resolve_time",
             "elapsed_seconds",
             "market_bars_held",
             "shock_score",
             "signed_impulse",
             "impulse_sign",
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
   FolderCreate("US500ShockResponseV1");
   g_output_directory = StringFormat("US500ShockResponseV1\\run-%d", InpRunCode);
   FolderCreate(g_output_directory);
   string path = g_output_directory + "\\opportunities.csv";
   g_opportunity_handle = FileOpen(path,
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

bool ReadShockState(double &signed_impulse, double &shock_score)
{
   const int required_bars = IMPULSE_BARS + BASELINE_RETURNS + 1;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, PERIOD_M15, 1, required_bars, rates);
   if(copied != required_bars)
      return(false);

   double newest_close = rates[0].close;
   double impulse_origin_close = rates[IMPULSE_BARS].close;
   if(newest_close <= 0.0 || impulse_origin_close <= 0.0)
      return(false);

   signed_impulse = MathLog(newest_close / impulse_origin_close);

   double returns[];
   ArrayResize(returns, BASELINE_RETURNS);
   double mean = 0.0;
   for(int i = 0; i < BASELINE_RETURNS; ++i)
   {
      int newer_index = IMPULSE_BARS + i;
      int older_index = newer_index + 1;
      if(rates[newer_index].close <= 0.0 || rates[older_index].close <= 0.0)
         return(false);
      returns[i] = MathLog(rates[newer_index].close / rates[older_index].close);
      mean += returns[i];
   }
   mean /= (double)BASELINE_RETURNS;

   double squared_sum = 0.0;
   for(int i = 0; i < BASELINE_RETURNS; ++i)
   {
      double deviation = returns[i] - mean;
      squared_sum += deviation * deviation;
   }
   double variance = squared_sum / (double)(BASELINE_RETURNS - 1);
   if(variance <= 0.0)
      return(false);

   double four_bar_volatility = MathSqrt(variance) * MathSqrt((double)IMPULSE_BARS);
   if(four_bar_volatility <= 0.0)
      return(false);

   shock_score = MathAbs(signed_impulse) / four_bar_volatility;
   return(MathIsValidNumber(shock_score));
}

bool ReadValidTick(MqlTick &tick)
{
   if(!SymbolInfoTick(_Symbol, tick))
      return(false);
   if(tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid)
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
   int continuation_direction = g_impulse_sign;
   int reversion_direction = -g_impulse_sign;
   double continuation_observed = 0.0;
   double continuation_double = 0.0;
   double reversion_observed = 0.0;
   double reversion_double = 0.0;

   bool calc_ok =
      CalculateDirectionProfit(continuation_direction, false, exit_tick, continuation_observed) &&
      CalculateDirectionProfit(continuation_direction, true, exit_tick, continuation_double) &&
      CalculateDirectionProfit(reversion_direction, false, exit_tick, reversion_observed) &&
      CalculateDirectionProfit(reversion_direction, true, exit_tick, reversion_double);

   if(!calc_ok)
      ++g_profit_calc_faults;

   ++g_resolved;
   double exit_spread = exit_tick.ask - exit_tick.bid;
   long elapsed_seconds = (long)exit_tick.time - (long)g_trigger_time;
   FileWrite(g_opportunity_handle,
             OBSERVER_ID,
             InpRunCode,
             g_resolved,
             TimeToString(g_trigger_time, TIME_DATE | TIME_SECONDS),
             TimeToString(exit_tick.time, TIME_DATE | TIME_SECONDS),
             elapsed_seconds,
             g_market_bars_held,
             DoubleToString(g_trigger_score, 12),
             DoubleToString(g_trigger_impulse, 12),
             g_impulse_sign,
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

void StartObservation(const double signed_impulse,
                      const double shock_score,
                      const MqlTick &entry_tick)
{
   g_active = true;
   g_armed = false;
   g_market_bars_held = 0;
   ++g_triggers;
   g_trigger_time = entry_tick.time;
   g_trigger_score = shock_score;
   g_trigger_impulse = signed_impulse;
   g_impulse_sign = signed_impulse > 0.0 ? 1 : -1;
   g_entry_bid = entry_tick.bid;
   g_entry_ask = entry_tick.ask;
   g_entry_spread = entry_tick.ask - entry_tick.bid;
}

void CountNormalDay(const datetime bar_time)
{
   MqlDateTime parts;
   TimeToStruct(bar_time, parts);
   int day_key = parts.year * 1000 + parts.day_of_year;
   if(day_key != g_last_day_key)
   {
      g_last_day_key = day_key;
      ++g_normal_days;
   }
}

void ProcessNewBar(const datetime bar_time)
{
   MqlTick current_tick;
   if(!ReadValidTick(current_tick))
   {
      ++g_tick_faults;
      return;
   }

   bool resolved_this_bar = false;
   if(g_active)
   {
      ++g_market_bars_held;
      if(g_market_bars_held >= HORIZON_BARS)
      {
         ResolveObservation(current_tick);
         resolved_this_bar = true;
      }
   }

   double signed_impulse = 0.0;
   double shock_score = 0.0;
   if(!ReadShockState(signed_impulse, shock_score))
   {
      ++g_rate_faults;
      return;
   }

   ++g_evaluations;
   CountNormalDay(bar_time);

   if(!g_armed && shock_score <= REARM_Z)
      g_armed = true;

   if(!g_active &&
      !resolved_this_bar &&
      g_armed &&
      shock_score >= TRIGGER_Z &&
      signed_impulse != 0.0)
   {
      StartObservation(signed_impulse, shock_score, current_tick);
   }
}

void WriteSummaryFile()
{
   string path = g_output_directory + "\\summary.csv";
   int handle = FileOpen(path,
                         FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
                         ',');
   if(handle == INVALID_HANDLE)
      return;

   FileWrite(handle,
             "observer_id",
             "run_code",
             "normal_days",
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
             g_normal_days,
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
   if(_Symbol != "US500" || _Period != PERIOD_M15)
   {
      PrintFormat("%s INVALID_CHART symbol=%s period=%d", OBSERVER_ID, _Symbol, _Period);
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpRunCode < 1 || InpRunCode > 4)
      return(INIT_PARAMETERS_INCORRECT);
   if(!CaptureContractSnapshot(g_start_spec))
      return(INIT_FAILED);
   if(!OpenOpportunityFile())
      return(INIT_FAILED);

   PrintFormat("%s START run=%d symbol=%s trigger=%.2f rearm=%.2f horizon=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               TRIGGER_Z,
               REARM_Z,
               HORIZON_BARS);
   return(INIT_SUCCEEDED);
}

void OnTick()
{
   datetime current_bar_time = iTime(_Symbol, PERIOD_M15, 0);
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

   PrintFormat("%s STOP run=%d reason=%d days=%I64d evaluations=%I64d triggers=%I64d resolved=%I64d unresolved=%d rate_faults=%I64d tick_faults=%I64d calc_faults=%I64d",
               OBSERVER_ID,
               InpRunCode,
               reason,
               g_normal_days,
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
