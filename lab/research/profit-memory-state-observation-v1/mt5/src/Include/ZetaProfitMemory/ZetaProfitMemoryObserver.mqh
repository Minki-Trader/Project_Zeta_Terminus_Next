#ifndef ZETA_PROFIT_MEMORY_OBSERVER_MQH
#define ZETA_PROFIT_MEMORY_OBSERVER_MQH

#define PROFIT_MEMORY_CROSSING_COUNT 5
const double PROFIT_MEMORY_CROSSINGS_R[PROFIT_MEMORY_CROSSING_COUNT] =
  {0.0, 0.125, 0.25, 0.5, 1.0};

struct ProfitMemoryTracker
  {
   bool active;
   ulong position_identifier;
   int component;
   long entry_time_msc;
   int direction;
   double volume;
   double entry_price;
   double planned_risk_usd;
   double starting_stressed_net;
   long starting_closed_trades;
   long samples;
   long last_sample_msc;
   double mfe_usd;
   double mae_usd;
   long mfe_time_msc;
   long mae_time_msc;
   long crossing_time_msc[PROFIT_MEMORY_CROSSING_COUNT];
  };

ProfitMemoryTracker profit_memory_trackers[COMPONENT_COUNT];
int profit_memory_handle = INVALID_HANDLE;
long profit_memory_rows = 0;
long profit_memory_faults = 0;
long profit_memory_unresolved = 0;

string ProfitMemoryStrategyName(const int component)
  {
   if(component == RC16_LONG)
      return("RC16");
   if(component == RC4_BOTH)
      return("RC4");
   if(component == US100_CROSS)
      return("Cross");
   if(component == US30_PRESSURE)
      return("Pressure");
   if(component == US30_RETURN_REV_LONG)
      return("Return");
   if(component == US100_PASSIVE_LIMIT)
      return("Passive");
   return("UNKNOWN");
  }

string ProfitMemoryTimeText(const long time_msc)
  {
   if(time_msc <= 0)
      return("");
   return(TimeToString((datetime)(time_msc / 1000),
                       TIME_DATE | TIME_SECONDS));
  }

void ClearProfitMemoryTracker(const int component)
  {
   ZeroMemory(profit_memory_trackers[component]);
   profit_memory_trackers[component].component = component;
   profit_memory_trackers[component].mfe_usd = -DBL_MAX;
   profit_memory_trackers[component].mae_usd = DBL_MAX;
  }

bool SelectProfitMemoryPosition(const int component,
                                const ulong identifier,
                                ulong &ticket)
  {
   ticket = 0;
   for(int index = PositionsTotal() - 1; index >= 0; --index)
     {
      const ulong candidate = PositionGetTicket(index);
      if(candidate == 0)
         continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier ||
         (ulong)PositionGetInteger(POSITION_MAGIC) !=
            component_definitions[component].magic ||
         PositionGetString(POSITION_SYMBOL) !=
            component_definitions[component].symbol)
         continue;
      ticket = candidate;
      return(true);
     }
   return(false);
  }

void ObserveProfitMemoryMark(const int component)
  {
   ProfitMemoryTracker tracker = profit_memory_trackers[component];
   if(!tracker.active || tracker.planned_risk_usd <= 0.0)
      return;
   ulong ticket = 0;
   if(!SelectProfitMemoryPosition(component,
                                  tracker.position_identifier,
                                  ticket))
      return;
   MqlTick quote = {};
   if(!SymbolInfoTick(component_definitions[component].symbol, quote) ||
      quote.time_msc <= 0 || quote.time_msc < tracker.entry_time_msc ||
      quote.time_msc <= tracker.last_sample_msc)
      return;
   const double mark_usd = PositionGetDouble(POSITION_PROFIT);
   if(!MathIsValidNumber(mark_usd))
     {
      ++profit_memory_faults;
      return;
     }
   tracker.last_sample_msc = quote.time_msc;
   ++tracker.samples;
   if(mark_usd > tracker.mfe_usd)
     {
      tracker.mfe_usd = mark_usd;
      tracker.mfe_time_msc = quote.time_msc;
     }
   if(mark_usd < tracker.mae_usd)
     {
      tracker.mae_usd = mark_usd;
      tracker.mae_time_msc = quote.time_msc;
     }
   const double mark_r = mark_usd / tracker.planned_risk_usd;
   for(int crossing = 0; crossing < PROFIT_MEMORY_CROSSING_COUNT; ++crossing)
     {
      if(tracker.crossing_time_msc[crossing] > 0)
         continue;
      const bool reached =
         (crossing == 0 ? mark_r > 0.0
                        : mark_r >= PROFIT_MEMORY_CROSSINGS_R[crossing]);
      if(reached)
         tracker.crossing_time_msc[crossing] = quote.time_msc;
     }
   profit_memory_trackers[component] = tracker;
  }

bool StartProfitMemoryTracker(const int component)
  {
   const ulong identifier =
      component_states[component].position_identifier;
   if(identifier == 0 ||
      component_states[component].entry_planned_risk_usd <= 0.0)
      return(false);
   ulong ticket = 0;
   if(!SelectProfitMemoryPosition(component, identifier, ticket))
      return(false);
   ClearProfitMemoryTracker(component);
   ProfitMemoryTracker tracker = profit_memory_trackers[component];
   tracker.active = true;
   tracker.position_identifier = identifier;
   tracker.entry_time_msc =
      (long)PositionGetInteger(POSITION_TIME_MSC);
   tracker.direction = component_states[component].entry_direction;
   tracker.volume = component_states[component].entry_volume;
   tracker.entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
   tracker.planned_risk_usd =
      component_states[component].entry_planned_risk_usd;
   tracker.starting_stressed_net =
      component_states[component].stressed_net;
   tracker.starting_closed_trades =
      component_states[component].closed_trades;
   if(tracker.entry_time_msc <= 0 || tracker.entry_price <= 0.0 ||
      tracker.volume <= 0.0)
     {
      ++profit_memory_faults;
      ClearProfitMemoryTracker(component);
      return(false);
     }
   profit_memory_trackers[component] = tracker;
   ObserveProfitMemoryMark(component);
   return(true);
  }

void CloseProfitMemoryTracker(const int component)
  {
   ProfitMemoryTracker tracker = profit_memory_trackers[component];
   if(!tracker.active)
      return;
   const long close_time_msc =
      component_states[component].last_processed_exit_time_msc;
   const ulong close_deal =
      component_states[component].last_processed_exit_deal;
   const long closed_delta =
      component_states[component].closed_trades -
      tracker.starting_closed_trades;
   const double stressed_net_usd =
      component_states[component].stressed_net -
      tracker.starting_stressed_net;
   int close_reason = -1;
   if(close_deal > 0 && HistoryDealSelect(close_deal))
      close_reason = (int)HistoryDealGetInteger(close_deal, DEAL_REASON);
   if(profit_memory_handle == INVALID_HANDLE ||
      tracker.planned_risk_usd <= 0.0 || tracker.samples <= 0 ||
      tracker.mfe_usd < tracker.mae_usd || close_time_msc <= tracker.entry_time_msc ||
      closed_delta != 1 || !MathIsValidNumber(stressed_net_usd) ||
      close_reason < 0)
      ++profit_memory_faults;
   const double lifetime_seconds =
      (double)(close_time_msc - tracker.entry_time_msc) / 1000.0;
   const double peak_elapsed_seconds =
      (double)(tracker.mfe_time_msc - tracker.entry_time_msc) / 1000.0;
   const double peak_fraction =
      (lifetime_seconds > 0.0 ? peak_elapsed_seconds / lifetime_seconds : 0.0);
   const double mfe_r = tracker.mfe_usd / tracker.planned_risk_usd;
   const double mae_r = tracker.mae_usd / tracker.planned_risk_usd;
   const double stressed_r = stressed_net_usd / tracker.planned_risk_usd;
   const double giveback_r = mfe_r - stressed_r;
   if(profit_memory_handle != INVALID_HANDLE)
     {
      FileWrite(profit_memory_handle,
                (long)tracker.position_identifier,
                component,
                ProfitMemoryStrategyName(component),
                component_definitions[component].symbol,
                tracker.direction,
                tracker.volume,
                tracker.entry_price,
                tracker.planned_risk_usd,
                tracker.entry_time_msc,
                ProfitMemoryTimeText(tracker.entry_time_msc),
                close_time_msc,
                ProfitMemoryTimeText(close_time_msc),
                tracker.samples,
                tracker.mfe_usd,
                mfe_r,
                tracker.mfe_time_msc,
                ProfitMemoryTimeText(tracker.mfe_time_msc),
                tracker.mae_usd,
                mae_r,
                tracker.mae_time_msc,
                ProfitMemoryTimeText(tracker.mae_time_msc),
                stressed_net_usd,
                stressed_r,
                giveback_r,
                peak_fraction,
                tracker.crossing_time_msc[0],
                tracker.crossing_time_msc[1],
                tracker.crossing_time_msc[2],
                tracker.crossing_time_msc[3],
                tracker.crossing_time_msc[4],
                (long)close_deal,
                close_reason,
                EnumToString((ENUM_DEAL_REASON)close_reason));
      ++profit_memory_rows;
     }
   ClearProfitMemoryTracker(component);
  }

void ProfitMemoryObserverSyncAndMark()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      const ulong current_identifier =
         component_states[component].position_identifier;
      if(profit_memory_trackers[component].active &&
         current_identifier !=
            profit_memory_trackers[component].position_identifier)
         CloseProfitMemoryTracker(component);
      if(!profit_memory_trackers[component].active &&
         current_identifier > 0)
         StartProfitMemoryTracker(component);
      ObserveProfitMemoryMark(component);
     }
  }

bool ResetProfitMemoryObserver()
  {
   profit_memory_rows = 0;
   profit_memory_faults = 0;
   profit_memory_unresolved = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      ClearProfitMemoryTracker(component);
   profit_memory_handle =
      FileOpen(PROFIT_MEMORY_OBSERVATION_PATH,
               FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
               ',');
   if(profit_memory_handle == INVALID_HANDLE)
     {
      PrintFormat("%s profit-memory file open failed error=%d",
                  EXECUTION_VERSION,
                  GetLastError());
      return(false);
     }
   FileWrite(profit_memory_handle,
             "position_identifier", "component", "strategy", "symbol",
             "direction", "volume", "entry_price", "planned_risk_usd",
             "entry_time_msc", "entry_server", "close_time_msc", "close_server",
             "samples", "mfe_usd", "mfe_r", "mfe_time_msc", "mfe_server",
             "mae_usd", "mae_r", "mae_time_msc", "mae_server",
             "native_stressed_net_usd", "native_stressed_r", "giveback_r",
             "peak_fraction", "cross_positive_msc", "cross_0_125r_msc",
             "cross_0_25r_msc", "cross_0_5r_msc", "cross_1r_msc",
             "close_deal", "close_reason", "close_reason_text");
   FileFlush(profit_memory_handle);
   return(true);
  }

void FinalizeProfitMemoryObserver()
  {
   ProfitMemoryObserverSyncAndMark();
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(!profit_memory_trackers[component].active)
         continue;
      if(component_states[component].position_identifier == 0)
         CloseProfitMemoryTracker(component);
      else
         ++profit_memory_unresolved;
     }
   if(profit_memory_handle != INVALID_HANDLE)
     {
      FileFlush(profit_memory_handle);
      FileClose(profit_memory_handle);
      profit_memory_handle = INVALID_HANDLE;
     }
   PrintFormat("%s profit_memory_observer rows=%I64d faults=%I64d unresolved=%I64d",
               EXECUTION_VERSION,
               profit_memory_rows,
               profit_memory_faults,
               profit_memory_unresolved);
  }

#endif
