#property strict
#property version   "1.00"
#property description "Trade-free US100 directional path-efficiency response observer"

input int InpRunCode = 1;

const string OBSERVER_ID = "ZETA-NEXT-US100-DIRECTIONAL-PATH-EFFICIENCY-RESPONSE-V1";
const string OUTPUT_ROOT = "US100DPEV1";
const int RETURN_SEGMENTS = 8;
const int REQUIRED_RATES = 10;
const int MINIMUM_NONZERO_RETURNS = 6;
const int CONTINUOUS_SECONDS = 900;
const double PATH_EFFICIENCY_THRESHOLD = 0.70;
const int HORIZON_MARKET_BARS = 4;
const double PROFIT_VOLUME = 0.01;

struct VisibleSpec
  {
   int               digits;
   double            point;
   double            tick_size;
   double            tick_value;
   double            contract_size;
   double            volume_min;
   double            volume_step;
   int               stops_level;
   int               freeze_level;
  };

struct PathObservation
  {
   bool              active;
   long              opportunity_id;
   datetime          window_end_time;
   datetime          entry_time;
   int               nonzero_returns;
   double            signed_displacement;
   double            travel_length;
   double            path_efficiency;
   ENUM_ORDER_TYPE   continuation_direction;
   double            entry_bid;
   double            entry_ask;
   double            entry_spread;
   int               market_bars_held;
  };

VisibleSpec g_start_spec;
PathObservation g_observation;
datetime g_last_bar_time = 0;
int g_last_eligible_day_key = 0;
int g_opportunity_handle = INVALID_HANDLE;
string g_run_directory = "";
bool g_initialized = false;

long g_eligible_days = 0;
long g_eligible_evaluations = 0;
long g_finalized_bars = 0;
long g_valid_ticks = 0;
long g_triggers = 0;
long g_resolved = 0;
long g_rate_faults = 0;
long g_tick_faults = 0;
long g_profit_calc_faults = 0;

bool ReadVisibleSpec(VisibleSpec &spec)
  {
   spec.digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   spec.point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   spec.tick_size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   spec.tick_value=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   spec.contract_size=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   spec.volume_min=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   spec.volume_step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   spec.stops_level=(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   spec.freeze_level=(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL);

   return(spec.digits>0 &&
          spec.point>0.0 &&
          spec.tick_size>0.0 &&
          spec.tick_value>0.0 &&
          spec.contract_size>0.0 &&
          spec.volume_min>0.0 &&
          spec.volume_step>0.0 &&
          spec.stops_level>=0 &&
          spec.freeze_level>=0);
  }

int DayKey(const datetime value)
  {
   MqlDateTime parts;
   if(!TimeToStruct(value,parts))
      return(0);
   return(parts.year*10000+parts.mon*100+parts.day);
  }

string DirectionText(const ENUM_ORDER_TYPE direction)
  {
   if(direction==ORDER_TYPE_BUY)
      return("BUY");
   return("SELL");
  }

ENUM_ORDER_TYPE OppositeDirection(const ENUM_ORDER_TYPE direction)
  {
   if(direction==ORDER_TYPE_BUY)
      return(ORDER_TYPE_SELL);
   return(ORDER_TYPE_BUY);
  }

bool ValidExecutableTick(MqlTick &tick)
  {
   if(!SymbolInfoTick(_Symbol,tick))
     {
      g_tick_faults++;
      return(false);
     }

   if(tick.bid<=0.0 || tick.ask<=0.0 || tick.ask<tick.bid)
     {
      g_tick_faults++;
      return(false);
     }

   return(true);
  }

bool CalculateProfit(const ENUM_ORDER_TYPE direction,
                     const double entry_bid,
                     const double entry_ask,
                     const double entry_spread,
                     const double exit_bid,
                     const double exit_ask,
                     const double exit_spread,
                     const bool double_spread,
                     double &profit)
  {
   double open_price=(direction==ORDER_TYPE_BUY ? entry_ask : entry_bid);
   double close_price=(direction==ORDER_TYPE_BUY ? exit_bid : exit_ask);

   if(double_spread)
     {
      if(direction==ORDER_TYPE_BUY)
        {
         open_price+=entry_spread;
         close_price-=exit_spread;
        }
      else
        {
         open_price-=entry_spread;
         close_price+=exit_spread;
        }
     }

   if(open_price<=0.0 || close_price<=0.0)
     {
      g_profit_calc_faults++;
      profit=0.0;
      return(false);
     }

   ResetLastError();
   if(!OrderCalcProfit(direction,_Symbol,PROFIT_VOLUME,open_price,close_price,profit))
     {
      g_profit_calc_faults++;
      profit=0.0;
      return(false);
     }

   return(true);
  }

void WriteOpportunity(const MqlTick &tick)
  {
   const ENUM_ORDER_TYPE continuation=g_observation.continuation_direction;
   const ENUM_ORDER_TYPE reversion=OppositeDirection(continuation);
   const double exit_spread=tick.ask-tick.bid;

   double continuation_observed=0.0;
   double continuation_double_spread=0.0;
   double reversion_observed=0.0;
   double reversion_double_spread=0.0;

   CalculateProfit(continuation,
                   g_observation.entry_bid,
                   g_observation.entry_ask,
                   g_observation.entry_spread,
                   tick.bid,
                   tick.ask,
                   exit_spread,
                   false,
                   continuation_observed);
   CalculateProfit(continuation,
                   g_observation.entry_bid,
                   g_observation.entry_ask,
                   g_observation.entry_spread,
                   tick.bid,
                   tick.ask,
                   exit_spread,
                   true,
                   continuation_double_spread);
   CalculateProfit(reversion,
                   g_observation.entry_bid,
                   g_observation.entry_ask,
                   g_observation.entry_spread,
                   tick.bid,
                   tick.ask,
                   exit_spread,
                   false,
                   reversion_observed);
   CalculateProfit(reversion,
                   g_observation.entry_bid,
                   g_observation.entry_ask,
                   g_observation.entry_spread,
                   tick.bid,
                   tick.ask,
                   exit_spread,
                   true,
                   reversion_double_spread);

   FileWrite(g_opportunity_handle,
             OBSERVER_ID,
             InpRunCode,
             g_observation.opportunity_id,
             TimeToString(g_observation.window_end_time,TIME_DATE|TIME_SECONDS),
             TimeToString(g_observation.entry_time,TIME_DATE|TIME_SECONDS),
             TimeToString((datetime)tick.time,TIME_DATE|TIME_SECONDS),
             g_observation.nonzero_returns,
             DoubleToString(g_observation.signed_displacement,12),
             DoubleToString(g_observation.travel_length,12),
             DoubleToString(g_observation.path_efficiency,9),
             DirectionText(continuation),
             DirectionText(reversion),
             DoubleToString(g_observation.entry_bid,_Digits),
             DoubleToString(g_observation.entry_ask,_Digits),
             DoubleToString(g_observation.entry_spread,_Digits),
             DoubleToString(tick.bid,_Digits),
             DoubleToString(tick.ask,_Digits),
             DoubleToString(exit_spread,_Digits),
             g_observation.market_bars_held,
             DoubleToString(continuation_observed,8),
             DoubleToString(continuation_double_spread,8),
             DoubleToString(reversion_observed,8),
             DoubleToString(reversion_double_spread,8));
   FileFlush(g_opportunity_handle);
   g_resolved++;
  }

bool LoadContinuousReturns(MqlRates &rates[],
                           int &nonzero_returns,
                           double &signed_displacement,
                           double &travel_length,
                           double &path_efficiency)
  {
   ArraySetAsSeries(rates,true);
   ResetLastError();
   const int copied=CopyRates(_Symbol,PERIOD_M15,0,REQUIRED_RATES,rates);
   if(copied!=REQUIRED_RATES)
     {
      g_rate_faults++;
      return(false);
     }

   for(int index=0; index<REQUIRED_RATES-1; index++)
     {
      if((long)(rates[index].time-rates[index+1].time)!=CONTINUOUS_SECONDS)
         return(false);
     }

   nonzero_returns=0;
   signed_displacement=0.0;
   travel_length=0.0;

   for(int index=1; index<=RETURN_SEGMENTS; index++)
     {
      if(rates[index].close<=0.0 || rates[index+1].close<=0.0)
        {
         g_rate_faults++;
         return(false);
        }

      const double path_return=MathLog(rates[index].close/rates[index+1].close);
      if(path_return!=0.0)
         nonzero_returns++;
      signed_displacement+=path_return;
      travel_length+=MathAbs(path_return);
     }

   if(nonzero_returns<MINIMUM_NONZERO_RETURNS ||
      travel_length<=0.0 ||
      signed_displacement==0.0)
      return(false);

   path_efficiency=MathAbs(signed_displacement)/travel_length;
   return(MathIsValidNumber(path_efficiency));
  }

void EvaluateCandidate(const MqlTick &tick)
  {
   MqlRates rates[];
   int nonzero_returns=0;
   double signed_displacement=0.0;
   double travel_length=0.0;
   double path_efficiency=0.0;

   if(!LoadContinuousReturns(rates,
                             nonzero_returns,
                             signed_displacement,
                             travel_length,
                             path_efficiency))
      return;

   g_eligible_evaluations++;
   const int day_key=DayKey(rates[0].time);
   if(day_key>0 && day_key!=g_last_eligible_day_key)
     {
      g_eligible_days++;
      g_last_eligible_day_key=day_key;
     }

   if(path_efficiency<PATH_EFFICIENCY_THRESHOLD)
      return;

   g_triggers++;
   g_observation.active=true;
   g_observation.opportunity_id=g_triggers;
   g_observation.window_end_time=rates[1].time;
   g_observation.entry_time=(datetime)tick.time;
   g_observation.nonzero_returns=nonzero_returns;
   g_observation.signed_displacement=signed_displacement;
   g_observation.travel_length=travel_length;
   g_observation.path_efficiency=path_efficiency;
   g_observation.continuation_direction=(signed_displacement>0.0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   g_observation.entry_bid=tick.bid;
   g_observation.entry_ask=tick.ask;
   g_observation.entry_spread=tick.ask-tick.bid;
   g_observation.market_bars_held=0;
  }

void ProcessNewBar(const MqlTick &tick)
  {
   if(g_observation.active)
     {
      g_observation.market_bars_held++;
      if(g_observation.market_bars_held>=HORIZON_MARKET_BARS)
        {
         WriteOpportunity(tick);
         g_observation.active=false;
        }
     }

   if(!g_observation.active)
      EvaluateCandidate(tick);
  }

void WriteSummary(const int reason)
  {
   VisibleSpec end_spec;
   if(!ReadVisibleSpec(end_spec))
     {
      ZeroMemory(end_spec);
      g_rate_faults++;
     }

   const string summary_path=g_run_directory+"\\summary.csv";
   const int summary_handle=FileOpen(summary_path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(summary_handle==INVALID_HANDLE)
     {
      PrintFormat("%s SUMMARY_OPEN_FAILED run=%d error=%d",OBSERVER_ID,InpRunCode,GetLastError());
      return;
     }

   FileWrite(summary_handle,
             "observer_id",
             "run_code",
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
             g_eligible_days,
             g_eligible_evaluations,
             g_finalized_bars,
             g_valid_ticks,
             g_triggers,
             g_resolved,
             (g_observation.active ? 1 : 0),
             g_rate_faults,
             g_tick_faults,
             g_profit_calc_faults,
             g_start_spec.digits,
             end_spec.digits,
             DoubleToString(g_start_spec.point,12),
             DoubleToString(end_spec.point,12),
             DoubleToString(g_start_spec.tick_size,12),
             DoubleToString(end_spec.tick_size,12),
             DoubleToString(g_start_spec.tick_value,12),
             DoubleToString(end_spec.tick_value,12),
             DoubleToString(g_start_spec.contract_size,8),
             DoubleToString(end_spec.contract_size,8),
             DoubleToString(g_start_spec.volume_min,8),
             DoubleToString(end_spec.volume_min,8),
             DoubleToString(g_start_spec.volume_step,8),
             DoubleToString(end_spec.volume_step,8),
             g_start_spec.stops_level,
             end_spec.stops_level,
             g_start_spec.freeze_level,
             end_spec.freeze_level);
   FileClose(summary_handle);

   PrintFormat("%s STOP run=%d reason=%d eligible_days=%I64d eligible_evaluations=%I64d finalized_bars=%I64d valid_ticks=%I64d triggers=%I64d resolved=%I64d unresolved=%d rate_faults=%I64d tick_faults=%I64d calc_faults=%I64d",
               OBSERVER_ID,
               InpRunCode,
               reason,
               g_eligible_days,
               g_eligible_evaluations,
               g_finalized_bars,
               g_valid_ticks,
               g_triggers,
               g_resolved,
               (g_observation.active ? 1 : 0),
               g_rate_faults,
               g_tick_faults,
               g_profit_calc_faults);
  }

int OnInit()
  {
   ZeroMemory(g_observation);

   if(!MQLInfoInteger(MQL_TESTER) ||
      _Symbol!="US100" ||
      _Period!=PERIOD_M15 ||
      InpRunCode<1 ||
      InpRunCode>3)
     {
      PrintFormat("%s INIT_CONTRACT_FAILED tester=%d symbol=%s period=%d run=%d",
                  OBSERVER_ID,
                  (int)MQLInfoInteger(MQL_TESTER),
                  _Symbol,
                  (int)_Period,
                  InpRunCode);
      return(INIT_FAILED);
     }

   if(!ReadVisibleSpec(g_start_spec))
     {
      PrintFormat("%s START_SPEC_FAILED run=%d",OBSERVER_ID,InpRunCode);
      return(INIT_FAILED);
     }

   FolderCreate(OUTPUT_ROOT);
   g_run_directory=StringFormat("%s\\run-%d",OUTPUT_ROOT,InpRunCode);
   FolderCreate(g_run_directory);

   const string opportunity_path=g_run_directory+"\\opportunities.csv";
   g_opportunity_handle=FileOpen(opportunity_path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(g_opportunity_handle==INVALID_HANDLE)
     {
      PrintFormat("%s OPPORTUNITY_OPEN_FAILED run=%d error=%d",OBSERVER_ID,InpRunCode,GetLastError());
      return(INIT_FAILED);
     }

   FileWrite(g_opportunity_handle,
             "observer_id",
             "run_code",
             "opportunity_id",
             "window_end_time",
             "entry_time",
             "exit_time",
             "nonzero_returns",
             "signed_displacement",
             "travel_length",
             "path_efficiency",
             "continuation_direction",
             "reversion_direction",
             "entry_bid",
             "entry_ask",
             "entry_spread",
             "exit_bid",
             "exit_ask",
             "exit_spread",
             "market_bars_held",
             "continuation_observed_usd",
             "continuation_double_spread_usd",
             "reversion_observed_usd",
             "reversion_double_spread_usd");
   FileFlush(g_opportunity_handle);

   g_initialized=true;
   PrintFormat("%s START run=%d symbol=%s segments=%d minimum_nonzero=%d threshold=%.2f horizon=%d",
               OBSERVER_ID,
               InpRunCode,
               _Symbol,
               RETURN_SEGMENTS,
               MINIMUM_NONZERO_RETURNS,
               PATH_EFFICIENCY_THRESHOLD,
               HORIZON_MARKET_BARS);
   return(INIT_SUCCEEDED);
  }

void OnTick()
  {
   if(!g_initialized)
      return;

   MqlTick tick;
   if(!ValidExecutableTick(tick))
      return;
   g_valid_ticks++;

   const datetime current_bar_time=iTime(_Symbol,PERIOD_M15,0);
   if(current_bar_time<=0)
     {
      g_rate_faults++;
      return;
     }

   if(current_bar_time==g_last_bar_time)
      return;

   if(g_last_bar_time>0)
      g_finalized_bars++;
   g_last_bar_time=current_bar_time;
   ProcessNewBar(tick);
  }

double OnTester()
  {
   return((double)g_resolved);
  }

void OnDeinit(const int reason)
  {
   if(!g_initialized)
      return;

   if(g_opportunity_handle!=INVALID_HANDLE)
     {
      FileFlush(g_opportunity_handle);
      FileClose(g_opportunity_handle);
      g_opportunity_handle=INVALID_HANDLE;
     }

   WriteSummary(reason);
   g_initialized=false;
  }
