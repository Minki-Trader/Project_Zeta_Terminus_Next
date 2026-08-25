#property strict
#property version   "1.00"
#property description "Trade-free US500 ordinal acceleration response observer"

input int  InpRunCode = 1;
input long InpLastTriggerEpoch = 1767110400;

const string OBSERVER_ID = "ZETA-NEXT-US500-ORDINAL-ACCELERATION-RESPONSE-V1";
const double OBSERVATION_VOLUME = 0.01;
const int HORIZON_MARKET_BARS = 4;

int      g_opportunity_handle = INVALID_HANDLE;
string   g_output_root = "";
datetime g_last_seen_bar_open = 0;
datetime g_last_trigger_time = 0;
int      g_last_eligible_day_key = -1;

bool     g_pending = false;
int      g_pending_native_direction = 0;
datetime g_pending_trigger_time = 0;
datetime g_pending_last_bar_open = 0;
int      g_pending_advances = 0;
double   g_pending_r1 = 0.0;
double   g_pending_r2 = 0.0;
double   g_pending_r3 = 0.0;
double   g_pending_entry_bid = 0.0;
double   g_pending_entry_ask = 0.0;

long g_eligible_path_days = 0;
long g_eligible_path_evaluations = 0;
long g_finalized_bars = 0;
long g_valid_ticks = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_rate_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;
long g_row_faults = 0;

long   g_start_digits = 0;
double g_start_point = 0.0;
double g_start_tick_size = 0.0;
double g_start_tick_value = 0.0;
double g_start_contract_size = 0.0;
double g_start_volume_min = 0.0;
double g_start_volume_step = 0.0;
long   g_start_stops_level = 0;
long   g_start_freeze_level = 0;

string FormatTime(const datetime value)
{
   if(value <= 0)
      return "";
   return TimeToString(value, TIME_DATE | TIME_SECONDS);
}

int DayKey(const datetime value)
{
   MqlDateTime parts;
   if(!TimeToStruct(value, parts))
      return -1;
   return parts.year * 10000 + parts.mon * 100 + parts.day;
}

bool ValidExecutableTick(const MqlTick &tick)
{
   return (tick.time > 0 &&
           MathIsValidNumber(tick.bid) &&
           MathIsValidNumber(tick.ask) &&
           tick.bid > 0.0 &&
           tick.ask >= tick.bid);
}

void CaptureStartSpecification()
{
   g_start_digits        = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_start_point         = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_start_tick_size     = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_start_tick_value    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   g_start_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   g_start_volume_min    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   g_start_volume_step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   g_start_stops_level   = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   g_start_freeze_level  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
}

bool CalculateBookProfit(const int direction,
                         const double entry_price,
                         const double exit_price,
                         double &profit)
{
   if(direction == 0 ||
      !MathIsValidNumber(entry_price) ||
      !MathIsValidNumber(exit_price) ||
      entry_price <= 0.0 ||
      exit_price <= 0.0)
   {
      g_profit_calc_faults++;
      return false;
   }

   const ENUM_ORDER_TYPE order_type = (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   profit = 0.0;
   if(!OrderCalcProfit(order_type,
                       _Symbol,
                       OBSERVATION_VOLUME,
                       entry_price,
                       exit_price,
                       profit) ||
      !MathIsValidNumber(profit))
   {
      g_profit_calc_faults++;
      return false;
   }
   return true;
}

bool CalculateDirectionBooks(const int direction,
                             const double exit_bid,
                             const double exit_ask,
                             double &observed_profit,
                             double &double_spread_profit)
{
   const double entry_spread = g_pending_entry_ask - g_pending_entry_bid;
   const double exit_spread = exit_ask - exit_bid;
   if(!MathIsValidNumber(entry_spread) ||
      !MathIsValidNumber(exit_spread) ||
      entry_spread < 0.0 ||
      exit_spread < 0.0)
   {
      g_profit_calc_faults++;
      return false;
   }

   double observed_entry = 0.0;
   double observed_exit = 0.0;
   double stressed_entry = 0.0;
   double stressed_exit = 0.0;
   if(direction > 0)
   {
      observed_entry = g_pending_entry_ask;
      observed_exit = exit_bid;
      stressed_entry = g_pending_entry_ask + entry_spread;
      stressed_exit = exit_bid - exit_spread;
   }
   else
   {
      observed_entry = g_pending_entry_bid;
      observed_exit = exit_ask;
      stressed_entry = g_pending_entry_bid - entry_spread;
      stressed_exit = exit_ask + exit_spread;
   }

   if(!CalculateBookProfit(direction, observed_entry, observed_exit, observed_profit))
      return false;
   if(!CalculateBookProfit(direction, stressed_entry, stressed_exit, double_spread_profit))
      return false;
   return true;
}

void ResolvePendingObservation(const MqlTick &tick)
{
   if(!g_pending)
      return;

   double continuation_observed = 0.0;
   double continuation_double = 0.0;
   double reversion_observed = 0.0;
   double reversion_double = 0.0;
   const bool continuation_ok = CalculateDirectionBooks(g_pending_native_direction,
                                                         tick.bid,
                                                         tick.ask,
                                                         continuation_observed,
                                                         continuation_double);
   const bool reversion_ok = CalculateDirectionBooks(-g_pending_native_direction,
                                                      tick.bid,
                                                      tick.ask,
                                                      reversion_observed,
                                                      reversion_double);

   if(continuation_ok && reversion_ok)
   {
      const uint bytes_written = FileWrite(g_opportunity_handle,
                                           OBSERVER_ID,
                                           InpRunCode,
                                           FormatTime(g_pending_trigger_time),
                                           FormatTime(tick.time),
                                           (g_pending_native_direction > 0 ? "BUY" : "SELL"),
                                           DoubleToString(g_pending_r1, 12),
                                           DoubleToString(g_pending_r2, 12),
                                           DoubleToString(g_pending_r3, 12),
                                           DoubleToString(g_pending_entry_bid, 5),
                                           DoubleToString(g_pending_entry_ask, 5),
                                           DoubleToString(tick.bid, 5),
                                           DoubleToString(tick.ask, 5),
                                           DoubleToString(g_pending_entry_ask - g_pending_entry_bid, 5),
                                           DoubleToString(tick.ask - tick.bid, 5),
                                           DoubleToString(continuation_observed, 8),
                                           DoubleToString(continuation_double, 8),
                                           DoubleToString(reversion_observed, 8),
                                           DoubleToString(reversion_double, 8));
      if(bytes_written == 0)
         g_row_faults++;
      else
      {
         FileFlush(g_opportunity_handle);
         g_resolved++;
      }
   }
   else
      g_row_faults++;

   g_pending = false;
   g_pending_native_direction = 0;
   g_pending_trigger_time = 0;
   g_pending_last_bar_open = 0;
   g_pending_advances = 0;
}

void AdvancePendingObservation(const datetime current_bar_open,
                               const MqlTick &tick)
{
   if(!g_pending || current_bar_open <= g_pending_last_bar_open)
      return;

   g_pending_last_bar_open = current_bar_open;
   g_pending_advances++;
   if(g_pending_advances >= HORIZON_MARKET_BARS)
      ResolvePendingObservation(tick);
}

bool LoadContinuousCompletedBars(MqlRates &rates[])
{
   ArrayResize(rates, 5);
   ArraySetAsSeries(rates, true);
   const int copied = CopyRates(_Symbol, PERIOD_M15, 0, 5, rates);
   if(copied != 5)
   {
      g_rate_faults++;
      return false;
   }

   for(int index = 0; index < 4; index++)
   {
      if((long)rates[index].time - (long)rates[index + 1].time != 900)
         return false;
   }
   return true;
}

void EvaluateOrdinalAcceleration(const datetime current_bar_open,
                                 const MqlTick &tick)
{
   MqlRates rates[];
   if(!LoadContinuousCompletedBars(rates))
      return;

   if(current_bar_open > (datetime)InpLastTriggerEpoch)
      return;

   g_eligible_path_evaluations++;
   const int day_key = DayKey(current_bar_open);
   if(day_key < 0)
   {
      g_rate_faults++;
      return;
   }
   if(day_key != g_last_eligible_day_key)
   {
      g_last_eligible_day_key = day_key;
      g_eligible_path_days++;
   }

   if(g_pending)
      return;

   const double close_oldest = rates[4].close;
   const double close_third = rates[3].close;
   const double close_second = rates[2].close;
   const double close_latest = rates[1].close;
   if(close_oldest <= 0.0 || close_third <= 0.0 || close_second <= 0.0 || close_latest <= 0.0)
   {
      g_rate_faults++;
      return;
   }

   const double r1 = MathLog(close_third / close_oldest);
   const double r2 = MathLog(close_second / close_third);
   const double r3 = MathLog(close_latest / close_second);
   if(!MathIsValidNumber(r1) || !MathIsValidNumber(r2) || !MathIsValidNumber(r3) ||
      r1 == 0.0 || r2 == 0.0 || r3 == 0.0)
      return;

   const int sign1 = (r1 > 0.0 ? 1 : -1);
   const int sign2 = (r2 > 0.0 ? 1 : -1);
   const int sign3 = (r3 > 0.0 ? 1 : -1);
   if(sign1 != sign2 || sign2 != sign3)
      return;
   if(!(MathAbs(r1) < MathAbs(r2) && MathAbs(r2) < MathAbs(r3)))
      return;

   g_pending = true;
   g_pending_native_direction = sign3;
   g_pending_trigger_time = tick.time;
   g_pending_last_bar_open = current_bar_open;
   g_pending_advances = 0;
   g_pending_r1 = r1;
   g_pending_r2 = r2;
   g_pending_r3 = r3;
   g_pending_entry_bid = tick.bid;
   g_pending_entry_ask = tick.ask;
   g_last_trigger_time = tick.time;
   g_triggers++;
}

void ProcessNewBar(const datetime current_bar_open,
                   const MqlTick &tick)
{
   g_finalized_bars++;
   AdvancePendingObservation(current_bar_open, tick);
   EvaluateOrdinalAcceleration(current_bar_open, tick);
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || _Symbol != "US500" || Period() != PERIOD_M15)
      return INIT_FAILED;
   if(InpRunCode < 1 || InpRunCode > 3 || InpLastTriggerEpoch <= 0)
      return INIT_PARAMETERS_INCORRECT;

   CaptureStartSpecification();
   g_output_root = StringFormat("US500OA38V1\\run-%d", InpRunCode);
   FolderCreate("US500OA38V1");
   FolderCreate(g_output_root);
   g_opportunity_handle = FileOpen(g_output_root + "\\opportunities.csv",
                                   FILE_WRITE | FILE_CSV | FILE_ANSI,
                                   ',');
   if(g_opportunity_handle == INVALID_HANDLE)
      return INIT_FAILED;

   FileWrite(g_opportunity_handle,
             "observer_id",
             "run_code",
             "trigger_time",
             "resolve_time",
             "native_direction",
             "r1_oldest",
             "r2_middle",
             "r3_latest",
             "entry_bid",
             "entry_ask",
             "exit_bid",
             "exit_ask",
             "entry_spread",
             "exit_spread",
             "continuation_observed_net",
             "continuation_double_spread_net",
             "reversion_observed_net",
             "reversion_double_spread_net");
   FileFlush(g_opportunity_handle);

   PrintFormat("%s START run=%d symbol=%s returns=3 order=ABS_STRICT_ACCELERATION horizon=%d cutoff=%s",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               HORIZON_MARKET_BARS,
               FormatTime((datetime)InpLastTriggerEpoch));
   return INIT_SUCCEEDED;
}

void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick) || !ValidExecutableTick(tick))
   {
      g_tick_faults++;
      return;
   }
   g_valid_ticks++;

   const datetime current_bar_open = iTime(_Symbol, PERIOD_M15, 0);
   if(current_bar_open <= 0)
   {
      g_rate_faults++;
      return;
   }
   if(current_bar_open == g_last_seen_bar_open)
      return;
   if(g_last_seen_bar_open > 0 && current_bar_open < g_last_seen_bar_open)
   {
      g_rate_faults++;
      return;
   }

   g_last_seen_bar_open = current_bar_open;
   ProcessNewBar(current_bar_open, tick);
}

void OnDeinit(const int reason)
{
   if(g_opportunity_handle != INVALID_HANDLE)
   {
      FileFlush(g_opportunity_handle);
      FileClose(g_opportunity_handle);
      g_opportunity_handle = INVALID_HANDLE;
   }

   const long end_digits = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   const double end_point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double end_tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double end_tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   const double end_contract_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double end_volume_min = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double end_volume_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   const long end_stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const long end_freeze_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   const long unresolved = (g_pending ? 1 : 0);

   const int summary_handle = FileOpen(g_output_root + "\\summary.csv",
                                       FILE_WRITE | FILE_CSV | FILE_ANSI,
                                       ',');
   if(summary_handle == INVALID_HANDLE)
      g_row_faults++;
   else
   {
      FileWrite(summary_handle,
                "observer_id",
                "run_code",
                "last_trigger_time",
                "eligible_path_days",
                "eligible_path_evaluations",
                "finalized_bars",
                "valid_ticks",
                "triggers",
                "resolved",
                "unresolved",
                "rate_faults",
                "tick_faults",
                "profit_calc_faults",
                "row_faults",
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
      FileWrite(summary_handle,
                OBSERVER_ID,
                InpRunCode,
                FormatTime(g_last_trigger_time),
                g_eligible_path_days,
                g_eligible_path_evaluations,
                g_finalized_bars,
                g_valid_ticks,
                g_triggers,
                g_resolved,
                unresolved,
                g_rate_faults,
                g_tick_faults,
                g_profit_calc_faults,
                g_row_faults,
                g_start_digits,
                end_digits,
                DoubleToString(g_start_point, 12),
                DoubleToString(end_point, 12),
                DoubleToString(g_start_tick_size, 12),
                DoubleToString(end_tick_size, 12),
                DoubleToString(g_start_tick_value, 12),
                DoubleToString(end_tick_value, 12),
                DoubleToString(g_start_contract_size, 8),
                DoubleToString(end_contract_size, 8),
                DoubleToString(g_start_volume_min, 8),
                DoubleToString(end_volume_min, 8),
                DoubleToString(g_start_volume_step, 8),
                DoubleToString(end_volume_step, 8),
                g_start_stops_level,
                end_stops_level,
                g_start_freeze_level,
                end_freeze_level);
      FileFlush(summary_handle);
      FileClose(summary_handle);
   }

   PrintFormat("%s STOP run=%d reason=%d cutoff=%s eligible_days=%I64d eligible_evaluations=%I64d finalized_bars=%I64d valid_ticks=%I64d triggers=%I64d resolved=%I64d unresolved=%I64d rate_faults=%I64d tick_faults=%I64d calc_faults=%I64d row_faults=%I64d",
               OBSERVER_ID,
               InpRunCode,
               reason,
               FormatTime((datetime)InpLastTriggerEpoch),
               g_eligible_path_days,
               g_eligible_path_evaluations,
               g_finalized_bars,
               g_valid_ticks,
               g_triggers,
               g_resolved,
               unresolved,
               g_rate_faults,
               g_tick_faults,
               g_profit_calc_faults,
               g_row_faults);
}

double OnTester()
{
   return (double)g_resolved;
}
