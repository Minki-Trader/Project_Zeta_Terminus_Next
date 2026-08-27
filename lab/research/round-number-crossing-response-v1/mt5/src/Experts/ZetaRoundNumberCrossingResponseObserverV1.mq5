#property strict
#property version   "1.00"
#property description "Trade-free round-number crossing response observer"

input int  InpRunCode = 1;
input long InpLastTriggerEpoch = 1735664400;

const string OBSERVER_ID = "ZETA-NEXT-ROUND-NUMBER-CROSSING-RESPONSE-V1";
const double OBSERVATION_VOLUME = 0.01;
const long RESPONSE_HORIZON_MILLISECONDS = 1800000;
const int WINDOW_START_SECONDS = 12 * 60 * 60;
const int WINDOW_END_SECONDS = 17 * 60 * 60;

enum LatticeKind
{
   LATTICE_ROUND = 0,
   LATTICE_PLACEBO = 1
};

struct SeenCrossing
{
   int  lattice;
   long level_index;
   int  direction;
};

struct PendingObservation
{
   int      lattice;
   long     level_index;
   double   level;
   int      direction;
   int      day_key;
   datetime trigger_time;
   long     trigger_time_msc;
   double   entry_bid;
   double   entry_ask;
};

int    g_opportunity_handle = INVALID_HANDLE;
string g_output_root = "";
bool   g_initialized = false;
int    g_price_digits = 0;
double g_grid = 0.0;
double g_placebo_offset = 0.0;
string g_start_specification = "";

bool    g_have_previous_tick = false;
MqlTick g_previous_tick;
int     g_previous_day_key = -1;
int     g_active_day_key = -1;
bool    g_active_day_counted = false;
SeenCrossing g_seen[];
PendingObservation g_pending[];

long g_eligible_days = 0;
long g_valid_ticks = 0;
long g_crossing_candidates = 0;
long g_duplicate_crossings = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_round_triggers = 0;
long g_round_resolved = 0;
long g_placebo_triggers = 0;
long g_placebo_resolved = 0;
long g_up_triggers = 0;
long g_down_triggers = 0;
long g_same_tick_dual_lattice = 0;
long g_max_pending = 0;
long g_time_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;
long g_row_faults = 0;
datetime g_last_trigger_time = 0;
long g_last_trigger_time_msc = 0;

string FormatTime(const datetime value)
{
   if(value <= 0)
      return "";
   return TimeToString(value, TIME_DATE | TIME_SECONDS);
}

string LongText(const long value)
{
   return StringFormat("%I64d", value);
}

string DoubleText(const double value)
{
   return DoubleToString(value, 16);
}

string PriceText(const double value)
{
   return DoubleToString(value, g_price_digits);
}

int DayKey(const datetime value)
{
   MqlDateTime parts;
   if(!TimeToStruct(value, parts))
      return -1;
   return parts.year * 10000 + parts.mon * 100 + parts.day;
}

bool IsEligibleWindow(const datetime value)
{
   MqlDateTime parts;
   if(!TimeToStruct(value, parts))
      return false;
   const int seconds = parts.hour * 3600 + parts.min * 60 + parts.sec;
   return (seconds >= WINDOW_START_SECONDS && seconds < WINDOW_END_SECONDS);
}

bool ValidExecutableTick(const MqlTick &tick)
{
   return (tick.time > 0 &&
           tick.time_msc > 0 &&
           MathIsValidNumber(tick.bid) &&
           MathIsValidNumber(tick.ask) &&
           tick.bid > 0.0 &&
           tick.ask >= tick.bid);
}

string ExpectedSymbolForRun(const int run_code)
{
   const int symbol_slot = (run_code - 1) % 3;
   if(symbol_slot == 0)
      return "US30";
   if(symbol_slot == 1)
      return "US100";
   return "US500";
}

long ExpectedCutoffForRun(const int run_code)
{
   if(run_code <= 3)
      return 1735664400;
   if(run_code <= 6)
      return 1767200400;
   if(run_code <= 9)
      return 1780246800;
   return 1785517200;
}

bool GridForSymbol(const string symbol,
                   double &grid,
                   double &placebo_offset)
{
   if(symbol == "US30" || symbol == "US100")
   {
      grid = 100.0;
      placebo_offset = 50.0;
      return true;
   }
   if(symbol == "US500")
   {
      grid = 10.0;
      placebo_offset = 5.0;
      return true;
   }
   return false;
}

bool ObservationVolumeIsValid()
{
   const double minimum = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(minimum <= 0.0 || maximum < minimum || step <= 0.0)
      return false;
   if(OBSERVATION_VOLUME < minimum - 1e-12 || OBSERVATION_VOLUME > maximum + 1e-12)
      return false;
   const double step_count = (OBSERVATION_VOLUME - minimum) / step;
   return (MathAbs(step_count - MathRound(step_count)) <= 1e-8);
}

string CaptureSymbolSpecification()
{
   string value = "";
   value += "digits=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
   value += "|point=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_POINT));
   value += "|tick_size=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE));
   value += "|tick_value=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE));
   value += "|tick_value_profit=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT));
   value += "|tick_value_loss=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS));
   value += "|contract_size=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE));
   value += "|volume_min=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
   value += "|volume_max=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
   value += "|volume_step=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP));
   value += "|volume_limit=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_LIMIT));
   value += "|stops_level=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL));
   value += "|freeze_level=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
   value += "|trade_mode=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE));
   value += "|calc_mode=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_CALC_MODE));
   value += "|swap_mode=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_SWAP_MODE));
   value += "|swap_long=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_SWAP_LONG));
   value += "|swap_short=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_SWAP_SHORT));
   value += "|swap_rollover3=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_SWAP_ROLLOVER3DAYS));
   value += "|filling_mode=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE));
   value += "|order_mode=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_ORDER_MODE));
   value += "|expiration_mode=" + LongText(SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE));
   value += "|margin_initial=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_MARGIN_INITIAL));
   value += "|margin_maintenance=" + DoubleText(SymbolInfoDouble(_Symbol, SYMBOL_MARGIN_MAINTENANCE));
   value += "|currency_base=" + SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   value += "|currency_profit=" + SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);
   value += "|currency_margin=" + SymbolInfoString(_Symbol, SYMBOL_CURRENCY_MARGIN);
   value += "|path=" + SymbolInfoString(_Symbol, SYMBOL_PATH);
   return value;
}

string LatticeName(const int lattice)
{
   return (lattice == LATTICE_ROUND ? "ROUND" : "PLACEBO");
}

string DirectionName(const int direction)
{
   return (direction > 0 ? "UP" : "DOWN");
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

bool CalculateDirectionBooks(const PendingObservation &observation,
                             const int book_direction,
                             const MqlTick &tick,
                             double &observed_profit,
                             double &double_spread_profit)
{
   const double entry_spread = observation.entry_ask - observation.entry_bid;
   const double exit_spread = tick.ask - tick.bid;
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
   if(book_direction > 0)
   {
      observed_entry = observation.entry_ask;
      observed_exit = tick.bid;
      stressed_entry = observation.entry_ask + entry_spread;
      stressed_exit = tick.bid - exit_spread;
   }
   else
   {
      observed_entry = observation.entry_bid;
      observed_exit = tick.ask;
      stressed_entry = observation.entry_bid - entry_spread;
      stressed_exit = tick.ask + exit_spread;
   }

   if(!CalculateBookProfit(book_direction, observed_entry, observed_exit, observed_profit))
      return false;
   if(!CalculateBookProfit(book_direction, stressed_entry, stressed_exit, double_spread_profit))
      return false;
   return true;
}

void RemovePendingAt(const int index)
{
   const int count = ArraySize(g_pending);
   for(int cursor = index; cursor < count - 1; cursor++)
      g_pending[cursor] = g_pending[cursor + 1];
   ArrayResize(g_pending, count - 1);
}

void ResolvePendingAt(const int index,
                      const MqlTick &tick)
{
   const PendingObservation observation = g_pending[index];
   double continuation_observed = 0.0;
   double continuation_double = 0.0;
   double reversion_observed = 0.0;
   double reversion_double = 0.0;
   const bool continuation_ok = CalculateDirectionBooks(observation,
                                                         observation.direction,
                                                         tick,
                                                         continuation_observed,
                                                         continuation_double);
   const bool reversion_ok = CalculateDirectionBooks(observation,
                                                      -observation.direction,
                                                      tick,
                                                      reversion_observed,
                                                      reversion_double);

   if(continuation_ok && reversion_ok)
   {
      const uint bytes_written = FileWrite(g_opportunity_handle,
                                           OBSERVER_ID,
                                           InpRunCode,
                                           _Symbol,
                                           observation.day_key,
                                           LatticeName(observation.lattice),
                                           DoubleToString(g_grid, 8),
                                           DoubleToString(observation.lattice == LATTICE_ROUND ? 0.0 : g_placebo_offset, 8),
                                           observation.level_index,
                                           PriceText(observation.level),
                                           DirectionName(observation.direction),
                                           FormatTime(observation.trigger_time),
                                           observation.trigger_time_msc,
                                           FormatTime(tick.time),
                                           tick.time_msc,
                                           tick.time_msc - observation.trigger_time_msc,
                                           PriceText(observation.entry_bid),
                                           PriceText(observation.entry_ask),
                                           PriceText(tick.bid),
                                           PriceText(tick.ask),
                                           PriceText(observation.entry_ask - observation.entry_bid),
                                           PriceText(tick.ask - tick.bid),
                                           DoubleToString(continuation_observed, 8),
                                           DoubleToString(continuation_double, 8),
                                           DoubleToString(continuation_observed - continuation_double, 8),
                                           DoubleToString(reversion_observed, 8),
                                           DoubleToString(reversion_double, 8),
                                           DoubleToString(reversion_observed - reversion_double, 8));
      if(bytes_written == 0)
         g_row_faults++;
      else
      {
         FileFlush(g_opportunity_handle);
         g_resolved++;
         if(observation.lattice == LATTICE_ROUND)
            g_round_resolved++;
         else
            g_placebo_resolved++;
      }
   }
   else
      g_row_faults++;

   RemovePendingAt(index);
}

void ResolveDueObservations(const MqlTick &tick)
{
   int index = 0;
   while(index < ArraySize(g_pending))
   {
      if(tick.time_msc - g_pending[index].trigger_time_msc >= RESPONSE_HORIZON_MILLISECONDS)
         ResolvePendingAt(index, tick);
      else
         index++;
   }
}

bool CrossingAlreadySeen(const int lattice,
                         const long level_index,
                         const int direction)
{
   for(int index = 0; index < ArraySize(g_seen); index++)
   {
      if(g_seen[index].lattice == lattice &&
         g_seen[index].level_index == level_index &&
         g_seen[index].direction == direction)
         return true;
   }
   return false;
}

bool AddSeenCrossing(const int lattice,
                     const long level_index,
                     const int direction)
{
   const int index = ArraySize(g_seen);
   if(ArrayResize(g_seen, index + 1) != index + 1)
      return false;
   g_seen[index].lattice = lattice;
   g_seen[index].level_index = level_index;
   g_seen[index].direction = direction;
   return true;
}

bool AddPendingObservation(const int lattice,
                           const long level_index,
                           const double level,
                           const int direction,
                           const int day_key,
                           const MqlTick &tick)
{
   const int index = ArraySize(g_pending);
   if(ArrayResize(g_pending, index + 1) != index + 1)
      return false;

   g_pending[index].lattice = lattice;
   g_pending[index].level_index = level_index;
   g_pending[index].level = level;
   g_pending[index].direction = direction;
   g_pending[index].day_key = day_key;
   g_pending[index].trigger_time = tick.time;
   g_pending[index].trigger_time_msc = tick.time_msc;
   g_pending[index].entry_bid = tick.bid;
   g_pending[index].entry_ask = tick.ask;
   if(index + 1 > g_max_pending)
      g_max_pending = index + 1;
   return true;
}

int DetectCrossingForLattice(const int lattice,
                             const double previous_mid,
                             const double current_mid,
                             const int day_key,
                             const MqlTick &tick)
{
   const double offset = (lattice == LATTICE_ROUND ? 0.0 : g_placebo_offset);
   int direction = 0;
   long level_index = 0;
   double level = 0.0;

   if(current_mid > previous_mid)
   {
      direction = 1;
      level_index = (long)MathFloor((previous_mid - offset) / g_grid) + 1;
      level = (double)level_index * g_grid + offset;
      if(!(previous_mid < level && current_mid >= level))
         return 0;
   }
   else if(current_mid < previous_mid)
   {
      direction = -1;
      level_index = (long)MathCeil((previous_mid - offset) / g_grid) - 1;
      level = (double)level_index * g_grid + offset;
      if(!(previous_mid > level && current_mid <= level))
         return 0;
   }
   else
      return 0;

   g_crossing_candidates++;
   if(CrossingAlreadySeen(lattice, level_index, direction))
   {
      g_duplicate_crossings++;
      return 0;
   }
   if(!AddSeenCrossing(lattice, level_index, direction) ||
      !AddPendingObservation(lattice, level_index, level, direction, day_key, tick))
   {
      g_row_faults++;
      return 0;
   }

   g_triggers++;
   if(lattice == LATTICE_ROUND)
      g_round_triggers++;
   else
      g_placebo_triggers++;
   if(direction > 0)
      g_up_triggers++;
   else
      g_down_triggers++;
   g_last_trigger_time = tick.time;
   g_last_trigger_time_msc = tick.time_msc;
   return 1;
}

void PrepareServerDay(const int day_key,
                      const bool eligible_window)
{
   if(day_key != g_active_day_key)
   {
      g_active_day_key = day_key;
      g_active_day_counted = false;
      ArrayResize(g_seen, 0);
   }
   if(eligible_window && !g_active_day_counted)
   {
      g_active_day_counted = true;
      g_eligible_days++;
   }
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || Period() != PERIOD_M1)
      return INIT_FAILED;
   if(InpRunCode < 1 || InpRunCode > 12)
      return INIT_PARAMETERS_INCORRECT;
   if(_Symbol != ExpectedSymbolForRun(InpRunCode) ||
      InpLastTriggerEpoch != ExpectedCutoffForRun(InpRunCode))
      return INIT_PARAMETERS_INCORRECT;
   if(!GridForSymbol(_Symbol, g_grid, g_placebo_offset) ||
      !ObservationVolumeIsValid())
      return INIT_FAILED;

   g_price_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_start_specification = CaptureSymbolSpecification();
   g_output_root = StringFormat("RNCR94V1\\run-%02d", InpRunCode);
   FolderCreate("RNCR94V1");
   FolderCreate(g_output_root);
   g_opportunity_handle = FileOpen(g_output_root + "\\opportunities.csv",
                                   FILE_WRITE | FILE_CSV | FILE_ANSI,
                                   ',');
   if(g_opportunity_handle == INVALID_HANDLE)
      return INIT_FAILED;

   const uint header_bytes = FileWrite(g_opportunity_handle,
                                       "observer_id",
                                       "run_code",
                                       "symbol",
                                       "server_day",
                                       "lattice",
                                       "grid",
                                       "offset",
                                       "level_index",
                                       "level",
                                       "crossing_direction",
                                       "trigger_time",
                                       "trigger_time_msc",
                                       "resolve_time",
                                       "resolve_time_msc",
                                       "elapsed_milliseconds",
                                       "entry_bid",
                                       "entry_ask",
                                       "exit_bid",
                                       "exit_ask",
                                       "entry_spread",
                                       "exit_spread",
                                       "continuation_observed_net",
                                       "continuation_double_spread_net",
                                       "continuation_extra_spread_cost",
                                       "reversion_observed_net",
                                       "reversion_double_spread_net",
                                       "reversion_extra_spread_cost");
   if(header_bytes == 0)
   {
      FileClose(g_opportunity_handle);
      g_opportunity_handle = INVALID_HANDLE;
      return INIT_FAILED;
   }
   FileFlush(g_opportunity_handle);

   g_initialized = true;
   PrintFormat("%s START run=%d symbol=%s grid=%.8f placebo_offset=%.8f window=[12:00,17:00) horizon_ms=%I64d cutoff=%s",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               g_grid,
               g_placebo_offset,
               RESPONSE_HORIZON_MILLISECONDS,
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

   const int day_key = DayKey(tick.time);
   if(day_key < 0)
   {
      g_time_faults++;
      return;
   }
   if(g_have_previous_tick && tick.time_msc < g_previous_tick.time_msc)
   {
      g_time_faults++;
      return;
   }

   ResolveDueObservations(tick);
   const bool eligible_window = IsEligibleWindow(tick.time);
   PrepareServerDay(day_key, eligible_window);

   if(eligible_window &&
      tick.time <= (datetime)InpLastTriggerEpoch &&
      g_have_previous_tick &&
      g_previous_day_key == day_key)
   {
      const double previous_mid = (g_previous_tick.bid + g_previous_tick.ask) / 2.0;
      const double current_mid = (tick.bid + tick.ask) / 2.0;
      if(MathIsValidNumber(previous_mid) && MathIsValidNumber(current_mid))
      {
         const int round_added = DetectCrossingForLattice(LATTICE_ROUND,
                                                           previous_mid,
                                                           current_mid,
                                                           day_key,
                                                           tick);
         const int placebo_added = DetectCrossingForLattice(LATTICE_PLACEBO,
                                                             previous_mid,
                                                             current_mid,
                                                             day_key,
                                                             tick);
         if(round_added == 1 && placebo_added == 1)
            g_same_tick_dual_lattice++;
      }
      else
         g_tick_faults++;
   }

   g_previous_tick = tick;
   g_previous_day_key = day_key;
   g_have_previous_tick = true;
}

void OnDeinit(const int reason)
{
   if(g_opportunity_handle != INVALID_HANDLE)
   {
      FileFlush(g_opportunity_handle);
      FileClose(g_opportunity_handle);
      g_opportunity_handle = INVALID_HANDLE;
   }

   if(!g_initialized || g_output_root == "")
      return;

   const long unresolved = ArraySize(g_pending);
   const string end_specification = CaptureSymbolSpecification();
   const int specification_changed = (g_start_specification == end_specification ? 0 : 1);
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
                "symbol",
                "deinit_reason",
                "last_trigger_time",
                "last_trigger_time_msc",
                "eligible_days",
                "valid_ticks",
                "crossing_candidates",
                "duplicate_crossings",
                "triggers",
                "resolved",
                "unresolved",
                "round_triggers",
                "round_resolved",
                "placebo_triggers",
                "placebo_resolved",
                "up_triggers",
                "down_triggers",
                "same_tick_dual_lattice",
                "max_pending",
                "time_faults",
                "tick_faults",
                "profit_calc_faults",
                "row_faults",
                "start_specification",
                "end_specification",
                "specification_changed");
      FileWrite(summary_handle,
                OBSERVER_ID,
                InpRunCode,
                _Symbol,
                reason,
                FormatTime(g_last_trigger_time),
                g_last_trigger_time_msc,
                g_eligible_days,
                g_valid_ticks,
                g_crossing_candidates,
                g_duplicate_crossings,
                g_triggers,
                g_resolved,
                unresolved,
                g_round_triggers,
                g_round_resolved,
                g_placebo_triggers,
                g_placebo_resolved,
                g_up_triggers,
                g_down_triggers,
                g_same_tick_dual_lattice,
                g_max_pending,
                g_time_faults,
                g_tick_faults,
                g_profit_calc_faults,
                g_row_faults,
                g_start_specification,
                end_specification,
                specification_changed);
      FileFlush(summary_handle);
      FileClose(summary_handle);
   }

   PrintFormat("%s STOP run=%d symbol=%s reason=%d cutoff=%s eligible_days=%I64d valid_ticks=%I64d triggers=%I64d resolved=%I64d unresolved=%I64d round=%I64d/%I64d placebo=%I64d/%I64d time_faults=%I64d tick_faults=%I64d calc_faults=%I64d row_faults=%I64d spec_changed=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               reason,
               FormatTime((datetime)InpLastTriggerEpoch),
               g_eligible_days,
               g_valid_ticks,
               g_triggers,
               g_resolved,
               unresolved,
               g_round_triggers,
               g_round_resolved,
               g_placebo_triggers,
               g_placebo_resolved,
               g_time_faults,
               g_tick_faults,
               g_profit_calc_faults,
               g_row_faults,
               specification_changed);
}

double OnTester()
{
   return (double)g_resolved;
}
