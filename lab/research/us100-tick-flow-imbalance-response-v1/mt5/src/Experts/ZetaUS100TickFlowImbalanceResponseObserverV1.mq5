#property strict
#property version   "1.00"
#property description "Trade-free US100 completed-M15 tick-flow imbalance observer for Zeta Next Lab Unit 030."

input int InpRunCode = 1;

const string OBSERVER_ID = "ZETA-NEXT-US100-TICK-FLOW-IMBALANCE-RESPONSE-V1";
const long M15_SECONDS = 900;
const long MIN_DIRECTIONAL_TICKS = 200;
const int HORIZON_BARS = 4;
const double IMBALANCE_THRESHOLD = 0.25;
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

datetime g_flow_bar_time = 0;
double g_last_mid = 0.0;
long g_bar_tick_samples = 0;
long g_bar_upticks = 0;
long g_bar_downticks = 0;
long g_bar_equal_ticks = 0;

int g_last_eligible_day_key = -1;
long g_eligible_tick_flow_days = 0;
long g_eligible_tick_flow_evaluations = 0;
long g_finalized_bars = 0;
long g_valid_ticks = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;

bool g_active = false;
int g_market_bars_held = 0;
datetime g_trigger_completed_bar_time = 0;
datetime g_trigger_entry_bar_time = 0;
datetime g_trigger_time = 0;
long g_trigger_tick_samples = 0;
long g_trigger_upticks = 0;
long g_trigger_downticks = 0;
long g_trigger_equal_ticks = 0;
double g_trigger_imbalance = 0.0;
int g_flow_direction = 0;
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
             "completed_bar_time",
             "entry_bar_time",
             "trigger_tick_time",
             "resolve_time",
             "elapsed_seconds",
             "market_bars_held",
             "tick_samples",
             "upticks",
             "downticks",
             "equal_ticks",
             "directional_ticks",
             "imbalance",
             "flow_direction",
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
   FolderCreate("US100TickFlowImbalanceResponseV1");
   g_output_directory =
      StringFormat("US100TickFlowImbalanceResponseV1\\run-%d", InpRunCode);
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

void BeginFlowBar(const datetime bar_time, const double mid)
{
   g_flow_bar_time = bar_time;
   g_last_mid = mid;
   g_bar_tick_samples = 1;
   g_bar_upticks = 0;
   g_bar_downticks = 0;
   g_bar_equal_ticks = 0;
}

void AccumulateFlowTick(const double mid)
{
   ++g_bar_tick_samples;
   if(mid > g_last_mid)
      ++g_bar_upticks;
   else if(mid < g_last_mid)
      ++g_bar_downticks;
   else
      ++g_bar_equal_ticks;
   g_last_mid = mid;
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
   int continuation_direction = g_flow_direction;
   int reversion_direction = -g_flow_direction;
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
   long directional_ticks = g_trigger_upticks + g_trigger_downticks;
   double exit_spread = exit_tick.ask - exit_tick.bid;
   long elapsed_seconds = (long)exit_tick.time - (long)g_trigger_time;
   FileWrite(g_opportunity_handle,
             OBSERVER_ID,
             InpRunCode,
             g_resolved,
             TimeToString(g_trigger_completed_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_trigger_entry_bar_time, TIME_DATE | TIME_SECONDS),
             TimeToString(g_trigger_time, TIME_DATE | TIME_SECONDS),
             TimeToString(exit_tick.time, TIME_DATE | TIME_SECONDS),
             elapsed_seconds,
             g_market_bars_held,
             g_trigger_tick_samples,
             g_trigger_upticks,
             g_trigger_downticks,
             g_trigger_equal_ticks,
             directional_ticks,
             DoubleToString(g_trigger_imbalance, 12),
             g_flow_direction,
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

void StartObservation(const datetime completed_bar_time,
                      const datetime entry_bar_time,
                      const double imbalance,
                      const int flow_direction,
                      const MqlTick &entry_tick)
{
   g_active = true;
   g_market_bars_held = 0;
   ++g_triggers;
   g_trigger_completed_bar_time = completed_bar_time;
   g_trigger_entry_bar_time = entry_bar_time;
   g_trigger_time = entry_tick.time;
   g_trigger_tick_samples = g_bar_tick_samples;
   g_trigger_upticks = g_bar_upticks;
   g_trigger_downticks = g_bar_downticks;
   g_trigger_equal_ticks = g_bar_equal_ticks;
   g_trigger_imbalance = imbalance;
   g_flow_direction = flow_direction;
   g_entry_bid = entry_tick.bid;
   g_entry_ask = entry_tick.ask;
   g_entry_spread = entry_tick.ask - entry_tick.bid;
}

void CountEligibleTickFlowDay(const datetime bar_time)
{
   MqlDateTime parts;
   TimeToStruct(bar_time, parts);
   int day_key = parts.year * 1000 + parts.day_of_year;
   if(day_key != g_last_eligible_day_key)
   {
      g_last_eligible_day_key = day_key;
      ++g_eligible_tick_flow_days;
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
   if((long)new_bar_time - (long)g_flow_bar_time != M15_SECONDS)
      return;

   long directional_ticks = g_bar_upticks + g_bar_downticks;
   if(directional_ticks < MIN_DIRECTIONAL_TICKS)
      return;

   ++g_eligible_tick_flow_evaluations;
   CountEligibleTickFlowDay(new_bar_time);
   double imbalance =
      (double)(g_bar_upticks - g_bar_downticks) / (double)directional_ticks;
   if(!MathIsValidNumber(imbalance) || MathAbs(imbalance) < IMBALANCE_THRESHOLD)
      return;

   int flow_direction = imbalance > 0.0 ? 1 : -1;
   StartObservation(g_flow_bar_time,
                    new_bar_time,
                    imbalance,
                    flow_direction,
                    entry_tick);
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
             "eligible_tick_flow_days",
             "eligible_tick_flow_evaluations",
             "finalized_bars",
             "valid_ticks",
             "triggers",
             "resolved",
             "unresolved",
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
             g_eligible_tick_flow_days,
             g_eligible_tick_flow_evaluations,
             g_finalized_bars,
             g_valid_ticks,
             g_triggers,
             g_resolved,
             g_active ? 1 : 0,
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

   PrintFormat("%s START run=%d symbol=%s minimum_directional_ticks=%I64d threshold=%.2f horizon=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               MIN_DIRECTIONAL_TICKS,
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
   double mid = 0.5 * (tick.bid + tick.ask);

   if(g_flow_bar_time == 0)
   {
      BeginFlowBar(bar_time, mid);
      return;
   }
   if(bar_time == g_flow_bar_time)
   {
      AccumulateFlowTick(mid);
      return;
   }
   if(bar_time < g_flow_bar_time)
   {
      ++g_tick_faults;
      return;
   }

   ProcessBarBoundary(bar_time, tick);
   BeginFlowBar(bar_time, mid);
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

   PrintFormat("%s STOP run=%d reason=%d eligible_days=%I64d eligible_evaluations=%I64d finalized_bars=%I64d valid_ticks=%I64d triggers=%I64d resolved=%I64d unresolved=%d tick_faults=%I64d calc_faults=%I64d",
               OBSERVER_ID,
               InpRunCode,
               reason,
               g_eligible_tick_flow_days,
               g_eligible_tick_flow_evaluations,
               g_finalized_bars,
               g_valid_ticks,
               g_triggers,
               g_resolved,
               g_active ? 1 : 0,
               g_tick_faults,
               g_profit_calc_faults);
}

double OnTester()
{
   return((double)g_resolved);
}
