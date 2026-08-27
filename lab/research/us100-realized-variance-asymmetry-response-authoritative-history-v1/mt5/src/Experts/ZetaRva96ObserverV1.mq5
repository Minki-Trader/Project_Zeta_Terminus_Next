#property strict
#property version   "1.00"
#property description "Trade-free US100 completed-M15 realized-variance asymmetry observer for Zeta Next Lab Unit 096."

input int InpRunCode = 1;

const string OBSERVER_ID = "ZETA-NEXT-RVA96-AUTHORITATIVE-HISTORY-V1";
const long M15_SECONDS = 900;
const int RETURN_WINDOW = 16;
const int MINIMUM_SIGN_COUNT = 4;
const int HORIZON_BARS = 4;
const double IMBALANCE_THRESHOLD = 0.35;
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
long g_eligible_variance_days = 0;
long g_eligible_variance_evaluations = 0;
long g_finalized_bars = 0;
long g_valid_ticks = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_rate_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;

bool g_active = false;
int g_market_bars_held = 0;
datetime g_window_end_bar_time = 0;
datetime g_entry_bar_time = 0;
datetime g_trigger_time = 0;
int g_positive_returns = 0;
int g_negative_returns = 0;
int g_zero_returns = 0;
double g_positive_energy = 0.0;
double g_negative_energy = 0.0;
double g_total_energy = 0.0;
double g_variance_imbalance = 0.0;
int g_dominant_direction = 0;
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
             "window_end_bar_time",
             "entry_bar_time",
             "trigger_tick_time",
             "resolve_time",
             "elapsed_seconds",
             "market_bars_held",
             "positive_returns",
             "negative_returns",
             "zero_returns",
             "positive_energy",
             "negative_energy",
             "total_energy",
             "variance_imbalance",
             "entry_bid",
             "entry_ask",
             "entry_spread",
             "exit_bid",
             "exit_ask",
             "exit_spread",
             "dominant_variance_direction",
             "counter_variance_direction",
             "dominant_observed_usd",
             "dominant_double_spread_usd",
             "counter_observed_usd",
             "counter_double_spread_usd",
             "calc_ok");
}

bool OpenOpportunityFile()
{
   FolderCreate("ZetaRva96");
   g_output_directory = StringFormat("ZetaRva96\\run-%d", InpRunCode);
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
   int counter_direction = -g_dominant_direction;
   double dominant_observed = 0.0;
   double dominant_double = 0.0;
   double counter_observed = 0.0;
   double counter_double = 0.0;

   bool calc_ok =
      CalculateDirectionProfit(g_dominant_direction,
                               false,
                               exit_tick,
                               dominant_observed) &&
      CalculateDirectionProfit(g_dominant_direction,
                               true,
                               exit_tick,
                               dominant_double) &&
      CalculateDirectionProfit(counter_direction,
                               false,
                               exit_tick,
                               counter_observed) &&
      CalculateDirectionProfit(counter_direction,
                               true,
                               exit_tick,
                               counter_double);
   if(!calc_ok)
      ++g_profit_calc_faults;

   ++g_resolved;
   double exit_spread = exit_tick.ask - exit_tick.bid;
   long elapsed_seconds = (long)exit_tick.time - (long)g_trigger_time;
   FileWrite(g_opportunity_handle,
             OBSERVER_ID,
             InpRunCode,
             g_resolved,
             TimeToString(g_window_end_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_entry_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_trigger_time, TIME_DATE | TIME_SECONDS),
             TimeToString(exit_tick.time, TIME_DATE | TIME_SECONDS),
             elapsed_seconds,
             g_market_bars_held,
             g_positive_returns,
             g_negative_returns,
             g_zero_returns,
             DoubleToString(g_positive_energy, 16),
             DoubleToString(g_negative_energy, 16),
             DoubleToString(g_total_energy, 16),
             DoubleToString(g_variance_imbalance, 12),
             DoubleToString(g_entry_bid, _Digits),
             DoubleToString(g_entry_ask, _Digits),
             DoubleToString(g_entry_spread, _Digits),
             DoubleToString(exit_tick.bid, _Digits),
             DoubleToString(exit_tick.ask, _Digits),
             DoubleToString(exit_spread, _Digits),
             g_dominant_direction,
             counter_direction,
             DoubleToString(dominant_observed, 8),
             DoubleToString(dominant_double, 8),
             DoubleToString(counter_observed, 8),
             DoubleToString(counter_double, 8),
             calc_ok ? 1 : 0);
   FileFlush(g_opportunity_handle);

   g_active = false;
   g_market_bars_held = 0;
}

void StartObservation(const datetime window_end_bar_time,
                      const datetime entry_bar_time,
                      const int positive_returns,
                      const int negative_returns,
                      const int zero_returns,
                      const double positive_energy,
                      const double negative_energy,
                      const double total_energy,
                      const double variance_imbalance,
                      const MqlTick &entry_tick)
{
   g_active = true;
   g_market_bars_held = 0;
   ++g_triggers;
   g_window_end_bar_time = window_end_bar_time;
   g_entry_bar_time = entry_bar_time;
   g_trigger_time = entry_tick.time;
   g_positive_returns = positive_returns;
   g_negative_returns = negative_returns;
   g_zero_returns = zero_returns;
   g_positive_energy = positive_energy;
   g_negative_energy = negative_energy;
   g_total_energy = total_energy;
   g_variance_imbalance = variance_imbalance;
   g_dominant_direction = variance_imbalance > 0.0 ? 1 : -1;
   g_entry_bid = entry_tick.bid;
   g_entry_ask = entry_tick.ask;
   g_entry_spread = entry_tick.ask - entry_tick.bid;
}

void CountEligibleVarianceDay(const datetime bar_time)
{
   MqlDateTime parts;
   TimeToStruct(bar_time, parts);
   int day_key = parts.year * 1000 + parts.day_of_year;
   if(day_key != g_last_eligible_day_key)
   {
      g_last_eligible_day_key = day_key;
      ++g_eligible_variance_days;
   }
}

void EvaluateCompletedWindow(const datetime new_bar_time,
                             const MqlTick &entry_tick)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int required = RETURN_WINDOW + 2;
   ResetLastError();
   int copied = CopyRates(_Symbol, PERIOD_M15, 0, required, rates);
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
      if((long)rates[index].time - (long)rates[index + 1].time != M15_SECONDS)
         return;
   }

   int positive_returns = 0;
   int negative_returns = 0;
   int zero_returns = 0;
   double positive_energy = 0.0;
   double negative_energy = 0.0;
   for(int index = 1; index <= RETURN_WINDOW; ++index)
   {
      double ratio = rates[index].close / rates[index + 1].close;
      if(ratio <= 0.0 || !MathIsValidNumber(ratio))
      {
         ++g_rate_faults;
         return;
      }
      double bar_return = MathLog(ratio);
      if(!MathIsValidNumber(bar_return))
      {
         ++g_rate_faults;
         return;
      }
      double energy = bar_return * bar_return;
      if(bar_return > 0.0)
      {
         ++positive_returns;
         positive_energy += energy;
      }
      else if(bar_return < 0.0)
      {
         ++negative_returns;
         negative_energy += energy;
      }
      else
         ++zero_returns;
   }

   if(positive_returns < MINIMUM_SIGN_COUNT ||
      negative_returns < MINIMUM_SIGN_COUNT)
      return;
   double total_energy = positive_energy + negative_energy;
   if(total_energy <= 0.0 || !MathIsValidNumber(total_energy))
   {
      ++g_rate_faults;
      return;
   }
   double variance_imbalance =
      (positive_energy - negative_energy) / total_energy;
   if(!MathIsValidNumber(variance_imbalance))
   {
      ++g_rate_faults;
      return;
   }

   ++g_eligible_variance_evaluations;
   CountEligibleVarianceDay(new_bar_time);
   if(MathAbs(variance_imbalance) < IMBALANCE_THRESHOLD)
      return;

   StartObservation(rates[1].time,
                    new_bar_time,
                    positive_returns,
                    negative_returns,
                    zero_returns,
                    positive_energy,
                    negative_energy,
                    total_energy,
                    variance_imbalance,
                    entry_tick);
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
   EvaluateCompletedWindow(new_bar_time, entry_tick);
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
             "eligible_variance_days",
             "eligible_variance_evaluations",
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
             g_eligible_variance_days,
             g_eligible_variance_evaluations,
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
   if(_Symbol != "US100" || _Period != PERIOD_M15)
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

   PrintFormat("%s START run=%d symbol=%s return_window=%d minimum_sign_count=%d threshold=%.2f horizon=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               RETURN_WINDOW,
               MINIMUM_SIGN_COUNT,
               IMBALANCE_THRESHOLD,
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

   datetime bar_time = iTime(_Symbol, PERIOD_M15, 0);
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
               g_eligible_variance_days,
               g_eligible_variance_evaluations,
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
