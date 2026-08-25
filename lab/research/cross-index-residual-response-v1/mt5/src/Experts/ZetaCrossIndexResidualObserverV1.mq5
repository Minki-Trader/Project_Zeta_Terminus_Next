#property strict
#property version   "1.00"
#property description "Trade-free observation of causal cross-index residual response states."

input int InpRunCode = 1;

const string RELEASE_ID = "NEXT-LAB-CIRR1-OBSERVER";
const double OBSERVATION_VOLUME = 0.01;
const int REQUIRED_SYMBOLS = 3;
const int SCALE_RETURNS = 48;
const int IMPULSE_BARS = 3;
const int OUTCOME_SECONDS = 1800;
const int MAX_QUOTE_LAG_SECONDS = 300;
const double TRIGGER_RESIDUAL = 1.5;
const double REARM_RESIDUAL = 0.75;

struct DayStat
{
   datetime day;
   int eligible_evaluations;
   int resolved_events;
};

struct PendingObservation
{
   string event_id;
   datetime decision_time;
   datetime decision_day;
   datetime due_time;
   string symbol;
   int selected_index;
   double residual;
   double z_us30;
   double z_us100;
   double z_us500;
   double sigma_log_5m;
   double entry_bid;
   double entry_ask;
   long entry_quote_msc;
};

string g_symbols[3];
string g_run_id = "";
string g_output_root = "";
int g_opportunity_file = INVALID_HANDLE;
int g_day_file = INVALID_HANDLE;
datetime g_last_current_bar = 0;
bool g_armed = true;
bool g_pending_active = false;
PendingObservation g_pending;
DayStat g_days[];
long g_next_event_id = 1;
long g_eligible_evaluations = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_faults = 0;
long g_rate_faults = 0;
long g_scale_faults = 0;
long g_entry_quote_faults = 0;
long g_outcome_quote_faults = 0;
long g_profit_conversion_faults = 0;
long g_nonfinite_faults = 0;
long g_unresolved = 0;

string SideName(const bool buy)
{
   return buy ? "BUY" : "SELL";
}

datetime DayStart(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   parts.hour = 0;
   parts.min = 0;
   parts.sec = 0;
   return StructToTime(parts);
}

int FindOrAddDay(const datetime day)
{
   const int count = ArraySize(g_days);
   for(int i = count - 1; i >= 0; --i)
   {
      if(g_days[i].day == day)
         return i;
      if(g_days[i].day < day)
         break;
   }

   const int next = ArraySize(g_days);
   if(ArrayResize(g_days, next + 1) != next + 1)
      return -1;
   g_days[next].day = day;
   g_days[next].eligible_evaluations = 0;
   g_days[next].resolved_events = 0;
   return next;
}

bool IsFinite(const double value)
{
   return MathIsValidNumber(value) && value != DBL_MAX && value != -DBL_MAX;
}

double Median3(const double first, const double second, const double third)
{
   const double minimum = MathMin(first, MathMin(second, third));
   const double maximum = MathMax(first, MathMax(second, third));
   return first + second + third - minimum - maximum;
}

bool ReadNormalizedImpulse(const string symbol,
                           datetime &completed_bar_time,
                           double &normalized_impulse,
                           double &sigma_log_5m)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   ResetLastError();
   const int required = SCALE_RETURNS + IMPULSE_BARS + 1;
   const int copied = CopyRates(symbol, PERIOD_M5, 1, required, rates);
   if(copied != required)
   {
      ++g_rate_faults;
      ++g_faults;
      return false;
   }

   completed_bar_time = rates[0].time;
   if(completed_bar_time <= 0 || rates[0].close <= 0.0 || rates[IMPULSE_BARS].close <= 0.0)
   {
      ++g_rate_faults;
      ++g_faults;
      return false;
   }

   double returns[48];
   double mean = 0.0;
   for(int i = 0; i < SCALE_RETURNS; ++i)
   {
      const int newer = IMPULSE_BARS + i;
      const int older = newer + 1;
      if(rates[newer].close <= 0.0 || rates[older].close <= 0.0)
      {
         ++g_rate_faults;
         ++g_faults;
         return false;
      }
      returns[i] = MathLog(rates[newer].close / rates[older].close);
      mean += returns[i];
   }
   mean /= (double)SCALE_RETURNS;

   double squared = 0.0;
   for(int i = 0; i < SCALE_RETURNS; ++i)
   {
      const double deviation = returns[i] - mean;
      squared += deviation * deviation;
   }
   sigma_log_5m = MathSqrt(squared / (double)(SCALE_RETURNS - 1));
   if(!IsFinite(sigma_log_5m) || sigma_log_5m <= 0.0)
   {
      ++g_scale_faults;
      ++g_faults;
      return false;
   }

   const double impulse = MathLog(rates[0].close / rates[IMPULSE_BARS].close);
   normalized_impulse = impulse / (sigma_log_5m * MathSqrt((double)IMPULSE_BARS));
   if(!IsFinite(normalized_impulse))
   {
      ++g_nonfinite_faults;
      ++g_faults;
      return false;
   }
   return true;
}

bool ReadDecisionQuote(const string symbol,
                       const datetime decision_time,
                       MqlTick &tick)
{
   ResetLastError();
   if(!SymbolInfoTick(symbol, tick))
      return false;
   if(tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid || tick.time <= 0)
      return false;
   const long lag = MathAbs((long)decision_time - (long)tick.time);
   return lag <= MAX_QUOTE_LAG_SECONDS;
}

bool CalculateSideResults(const string symbol,
                          const bool buy,
                          const double entry_bid,
                          const double entry_ask,
                          const double exit_bid,
                          const double exit_ask,
                          double &gross_usd,
                          double &observed_usd,
                          double &double_spread_usd)
{
   const double entry_mid = 0.5 * (entry_bid + entry_ask);
   const double exit_mid = 0.5 * (exit_bid + exit_ask);
   const ENUM_ORDER_TYPE order_type = buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   const double observed_open = buy ? entry_ask : entry_bid;
   const double observed_close = buy ? exit_bid : exit_ask;
   ResetLastError();
   if(!OrderCalcProfit(order_type,
                       symbol,
                       OBSERVATION_VOLUME,
                       entry_mid,
                       exit_mid,
                       gross_usd))
      return false;
   if(!OrderCalcProfit(order_type,
                       symbol,
                       OBSERVATION_VOLUME,
                       observed_open,
                       observed_close,
                       observed_usd))
      return false;
   double_spread_usd = 2.0 * observed_usd - gross_usd;
   return IsFinite(gross_usd) && IsFinite(observed_usd) && IsFinite(double_spread_usd);
}

void LogContract(const string phase, const string symbol)
{
   PrintFormat("%s CIRR_CONTRACT phase=%s symbol=%s digits=%d point=%.10f contract=%.10f tick_size=%.10f tick_value_profit=%.10f tick_value_loss=%.10f volume_min=%.10f volume_max=%.10f volume_step=%.10f calc_mode=%d swap_mode=%d swap_long=%.10f swap_short=%.10f rollover3day=%d currency_profit=%s currency_margin=%s",
               RELEASE_ID,
               phase,
               symbol,
               (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS),
               SymbolInfoDouble(symbol, SYMBOL_POINT),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP),
               (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_CALC_MODE),
               (int)SymbolInfoInteger(symbol, SYMBOL_SWAP_MODE),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_LONG),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SHORT),
               (int)SymbolInfoInteger(symbol, SYMBOL_SWAP_ROLLOVER3DAYS),
               SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT),
               SymbolInfoString(symbol, SYMBOL_CURRENCY_MARGIN));
}

bool OpenOutputs()
{
   FolderCreate("ZetaTerminusNext");
   FolderCreate("ZetaTerminusNext\\research");
   FolderCreate("ZetaTerminusNext\\research\\cross-index-residual-response-v1");
   g_output_root = "ZetaTerminusNext\\research\\cross-index-residual-response-v1\\" + g_run_id;
   g_opportunity_file = FileOpen(g_output_root + "-opportunities.csv",
                                 FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
                                 ',');
   if(g_opportunity_file == INVALID_HANDLE)
      return false;
   g_day_file = FileOpen(g_output_root + "-days.csv",
                         FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
                         ',');
   if(g_day_file == INVALID_HANDLE)
      return false;

   FileWrite(g_opportunity_file,
             "event_id",
             "run_id",
             "decision_server",
             "outcome_server",
             "elapsed_seconds",
             "symbol",
             "selected_residual",
             "abs_selected_residual",
             "z_us30",
             "z_us100",
             "z_us500",
             "sigma_log_5m",
             "entry_bid",
             "entry_ask",
             "entry_quote_msc",
             "outcome_bid",
             "outcome_ask",
             "outcome_quote_msc",
             "entry_spread_points",
             "outcome_spread_points",
             "continuation_side",
             "continuation_gross_usd",
             "continuation_observed_usd",
             "continuation_double_spread_usd",
             "reversion_side",
             "reversion_gross_usd",
             "reversion_observed_usd",
             "reversion_double_spread_usd");
   FileWrite(g_day_file,
             "run_id",
             "server_day",
             "eligible_evaluations",
             "resolved_events");
   return true;
}

bool WriteResolvedObservation(const MqlTick &outcome_tick)
{
   const bool continuation_buy = g_pending.residual > 0.0;
   const bool reversion_buy = !continuation_buy;
   double continuation_gross = 0.0;
   double continuation_observed = 0.0;
   double continuation_double = 0.0;
   double reversion_gross = 0.0;
   double reversion_observed = 0.0;
   double reversion_double = 0.0;
   if(!CalculateSideResults(g_pending.symbol,
                            continuation_buy,
                            g_pending.entry_bid,
                            g_pending.entry_ask,
                            outcome_tick.bid,
                            outcome_tick.ask,
                            continuation_gross,
                            continuation_observed,
                            continuation_double) ||
      !CalculateSideResults(g_pending.symbol,
                            reversion_buy,
                            g_pending.entry_bid,
                            g_pending.entry_ask,
                            outcome_tick.bid,
                            outcome_tick.ask,
                            reversion_gross,
                            reversion_observed,
                            reversion_double))
   {
      ++g_profit_conversion_faults;
      ++g_faults;
      return false;
   }

   const double point = SymbolInfoDouble(g_pending.symbol, SYMBOL_POINT);
   if(point <= 0.0)
   {
      ++g_nonfinite_faults;
      ++g_faults;
      return false;
   }
   const double entry_spread_points = (g_pending.entry_ask - g_pending.entry_bid) / point;
   const double outcome_spread_points = (outcome_tick.ask - outcome_tick.bid) / point;
   const long elapsed = (long)outcome_tick.time - (long)g_pending.decision_time;

   FileWrite(g_opportunity_file,
             g_pending.event_id,
             g_run_id,
             TimeToString(g_pending.decision_time, TIME_DATE | TIME_SECONDS),
             TimeToString(outcome_tick.time, TIME_DATE | TIME_SECONDS),
             IntegerToString(elapsed),
             g_pending.symbol,
             DoubleToString(g_pending.residual, 9),
             DoubleToString(MathAbs(g_pending.residual), 9),
             DoubleToString(g_pending.z_us30, 9),
             DoubleToString(g_pending.z_us100, 9),
             DoubleToString(g_pending.z_us500, 9),
             DoubleToString(g_pending.sigma_log_5m, 12),
             DoubleToString(g_pending.entry_bid, 8),
             DoubleToString(g_pending.entry_ask, 8),
             IntegerToString(g_pending.entry_quote_msc),
             DoubleToString(outcome_tick.bid, 8),
             DoubleToString(outcome_tick.ask, 8),
             IntegerToString(outcome_tick.time_msc),
             DoubleToString(entry_spread_points, 6),
             DoubleToString(outcome_spread_points, 6),
             SideName(continuation_buy),
             DoubleToString(continuation_gross, 9),
             DoubleToString(continuation_observed, 9),
             DoubleToString(continuation_double, 9),
             SideName(reversion_buy),
             DoubleToString(reversion_gross, 9),
             DoubleToString(reversion_observed, 9),
             DoubleToString(reversion_double, 9));
   FileFlush(g_opportunity_file);

   const int day_index = FindOrAddDay(g_pending.decision_day);
   if(day_index < 0)
   {
      ++g_faults;
      return false;
   }
   ++g_days[day_index].resolved_events;
   ++g_resolved;
   return true;
}

void TryResolvePending()
{
   if(!g_pending_active || TimeCurrent() < g_pending.due_time)
      return;
   MqlTick tick;
   ResetLastError();
   if(!SymbolInfoTick(g_pending.symbol, tick) ||
      tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid ||
      tick.time < g_pending.due_time)
      return;

   if(!WriteResolvedObservation(tick))
      ++g_outcome_quote_faults;
   g_pending_active = false;
   g_armed = false;
}

void EvaluateNewBar()
{
   datetime completed_times[3];
   double normalized[3];
   double sigmas[3];
   for(int i = 0; i < REQUIRED_SYMBOLS; ++i)
   {
      if(!ReadNormalizedImpulse(g_symbols[i],
                                completed_times[i],
                                normalized[i],
                                sigmas[i]))
         return;
   }
   if(completed_times[0] != completed_times[1] || completed_times[0] != completed_times[2])
   {
      ++g_rate_faults;
      ++g_faults;
      return;
   }

   const datetime decision_time = TimeCurrent();
   const datetime decision_day = DayStart(decision_time);
   const int day_index = FindOrAddDay(decision_day);
   if(day_index < 0)
   {
      ++g_faults;
      return;
   }
   ++g_days[day_index].eligible_evaluations;
   ++g_eligible_evaluations;

   const double center = Median3(normalized[0], normalized[1], normalized[2]);
   double residuals[3];
   int selected = 0;
   for(int i = 0; i < REQUIRED_SYMBOLS; ++i)
   {
      residuals[i] = normalized[i] - center;
      if(!IsFinite(residuals[i]))
      {
         ++g_nonfinite_faults;
         ++g_faults;
         return;
      }
      if(MathAbs(residuals[i]) > MathAbs(residuals[selected]))
         selected = i;
   }
   const double magnitude = MathAbs(residuals[selected]);

   if(g_pending_active)
      return;
   if(!g_armed)
   {
      if(magnitude <= REARM_RESIDUAL)
         g_armed = true;
      return;
   }
   if(magnitude < TRIGGER_RESIDUAL)
      return;

   MqlTick entry_tick;
   if(!ReadDecisionQuote(g_symbols[selected], decision_time, entry_tick))
   {
      ++g_entry_quote_faults;
      ++g_faults;
      return;
   }

   g_pending.event_id = g_run_id + "-" + IntegerToString(g_next_event_id++);
   g_pending.decision_time = decision_time;
   g_pending.decision_day = decision_day;
   g_pending.due_time = decision_time + OUTCOME_SECONDS;
   g_pending.symbol = g_symbols[selected];
   g_pending.selected_index = selected;
   g_pending.residual = residuals[selected];
   g_pending.z_us30 = normalized[0];
   g_pending.z_us100 = normalized[1];
   g_pending.z_us500 = normalized[2];
   g_pending.sigma_log_5m = sigmas[selected];
   g_pending.entry_bid = entry_tick.bid;
   g_pending.entry_ask = entry_tick.ask;
   g_pending.entry_quote_msc = entry_tick.time_msc;
   g_pending_active = true;
   g_armed = false;
   ++g_triggers;
}

void WriteDays()
{
   const int count = ArraySize(g_days);
   for(int i = 0; i < count; ++i)
   {
      FileWrite(g_day_file,
                g_run_id,
                TimeToString(g_days[i].day, TIME_DATE),
                IntegerToString(g_days[i].eligible_evaluations),
                IntegerToString(g_days[i].resolved_events));
   }
   FileFlush(g_day_file);
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER))
   {
      Print(RELEASE_ID + " TESTER_ONLY");
      return INIT_FAILED;
   }
   if(_Symbol != "US30" || _Period != PERIOD_M5)
   {
      PrintFormat("%s WRONG_CHART symbol=%s period=%d", RELEASE_ID, _Symbol, (int)_Period);
      return INIT_FAILED;
   }
   if(InpRunCode == 1)
      g_run_id = "long";
   else if(InpRunCode == 2)
      g_run_id = "latest";
   else
   {
      PrintFormat("%s INVALID_RUN_CODE value=%d", RELEASE_ID, InpRunCode);
      return INIT_PARAMETERS_INCORRECT;
   }

   g_symbols[0] = "US30";
   g_symbols[1] = "US100";
   g_symbols[2] = "US500";
   for(int i = 0; i < REQUIRED_SYMBOLS; ++i)
   {
      if(!SymbolSelect(g_symbols[i], true))
      {
         PrintFormat("%s SYMBOL_SELECT_FAILED symbol=%s error=%d", RELEASE_ID, g_symbols[i], GetLastError());
         return INIT_FAILED;
      }
   }
   if(!OpenOutputs())
   {
      PrintFormat("%s OUTPUT_OPEN_FAILED run=%s error=%d", RELEASE_ID, g_run_id, GetLastError());
      return INIT_FAILED;
   }
   for(int i = 0; i < REQUIRED_SYMBOLS; ++i)
      LogContract("start", g_symbols[i]);
   PrintFormat("%s START run=%s trigger=%.2f rearm=%.2f horizon_seconds=%d volume=%.2f",
               RELEASE_ID,
               g_run_id,
               TRIGGER_RESIDUAL,
               REARM_RESIDUAL,
               OUTCOME_SECONDS,
               OBSERVATION_VOLUME);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   TryResolvePending();
   const datetime current_bar = iTime("US30", PERIOD_M5, 0);
   if(current_bar <= 0 || current_bar == g_last_current_bar)
      return;
   g_last_current_bar = current_bar;
   EvaluateNewBar();
}

void OnDeinit(const int reason)
{
   if(g_pending_active)
   {
      ++g_unresolved;
      ++g_faults;
      g_pending_active = false;
   }
   for(int i = 0; i < REQUIRED_SYMBOLS; ++i)
      LogContract("end", g_symbols[i]);
   if(g_day_file != INVALID_HANDLE)
      WriteDays();
   if(g_opportunity_file != INVALID_HANDLE)
      FileClose(g_opportunity_file);
   if(g_day_file != INVALID_HANDLE)
      FileClose(g_day_file);
   PrintFormat("%s SUMMARY run=%s reason=%d eligible=%I64d triggers=%I64d resolved=%I64d faults=%I64d rate_faults=%I64d scale_faults=%I64d entry_quote_faults=%I64d outcome_quote_faults=%I64d profit_conversion_faults=%I64d nonfinite_faults=%I64d unresolved=%I64d",
               RELEASE_ID,
               g_run_id,
               reason,
               g_eligible_evaluations,
               g_triggers,
               g_resolved,
               g_faults,
               g_rate_faults,
               g_scale_faults,
               g_entry_quote_faults,
               g_outcome_quote_faults,
               g_profit_conversion_faults,
               g_nonfinite_faults,
               g_unresolved);
}
