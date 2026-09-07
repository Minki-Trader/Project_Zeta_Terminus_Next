#ifndef ZETA_ECONOMIC_PATH_MQH
#define ZETA_ECONOMIC_PATH_MQH
// Read-only aggregation at every delivered EA tick. Native TesterStatistics
// remains authority for full tester equity DD, including other-symbol events.
int economic_path_handle = INVALID_HANDLE;
long economic_path_minute = -1;
long economic_path_first_ms = 0, economic_path_last_ms = 0;
long economic_path_high_ms = 0, economic_path_low_ms = 0;
long economic_path_ticks = 0, economic_path_rows = 0;
bool economic_path_failed = false;
double economic_path_open = 0.0, economic_path_high = 0.0;
double economic_path_low = 0.0, economic_path_close = 0.0;
double economic_path_balance_open = 0.0, economic_path_balance_close = 0.0;
double economic_path_stress_open = 0.0, economic_path_stress_close = 0.0;
int economic_path_multiplier = 1;

bool InitializeEconomicPath()
  {
   economic_path_handle = FileOpen(RESEARCH_OBSERVATION_DIRECTORY + "\\economic-path.csv",
      FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',');
   if(economic_path_handle == INVALID_HANDLE) return(false);
   FileWrite(economic_path_handle, "minute_server_epoch", "first_tick_ms", "last_tick_ms", "ticks",
      "equity_open", "equity_high", "high_ms", "equity_low", "low_ms", "equity_close",
      "balance_open", "balance_close", "core_stressed_open", "core_stressed_close", "day_lot_multiplier");
   return(true);
  }

void FlushEconomicMinute()
  {
   if(economic_path_handle == INVALID_HANDLE || economic_path_ticks == 0) return;
   if(FileTell(economic_path_handle) > 256*1024*1024)
     { economic_path_failed = true; return; }
   if(FileWrite(economic_path_handle, economic_path_minute*60, economic_path_first_ms,
      economic_path_last_ms, economic_path_ticks, economic_path_open, economic_path_high,
      economic_path_high_ms, economic_path_low, economic_path_low_ms, economic_path_close,
      economic_path_balance_open, economic_path_balance_close, economic_path_stress_open,
      economic_path_stress_close, economic_path_multiplier) == 0)
      economic_path_failed = true;
   ++economic_path_rows;
   economic_path_ticks = 0;
  }

void SampleEconomicPath()
  {
   if(economic_path_handle == INVALID_HANDLE) return;
   MqlTick tick = {};
   if(!SymbolInfoTick(_Symbol, tick) || tick.time_msc <= 0)
     { economic_path_failed = true; return; }
   const long minute = (long)tick.time / 60;
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(!MathIsValidNumber(equity) || !MathIsValidNumber(balance))
     { economic_path_failed = true; return; }
   if(minute != economic_path_minute)
     {
      FlushEconomicMinute();
      economic_path_minute = minute;
      economic_path_first_ms = tick.time_msc;
      economic_path_open = equity;
      economic_path_high = equity;
      economic_path_low = equity;
      economic_path_high_ms = tick.time_msc;
      economic_path_low_ms = tick.time_msc;
      economic_path_balance_open = balance;
      economic_path_stress_open = portfolio_state.stressed_balance;
     }
   if(equity > economic_path_high) { economic_path_high = equity; economic_path_high_ms = tick.time_msc; }
   if(equity < economic_path_low) { economic_path_low = equity; economic_path_low_ms = tick.time_msc; }
   economic_path_last_ms = tick.time_msc;
   economic_path_close = equity;
   economic_path_balance_close = balance;
   economic_path_stress_close = portfolio_state.stressed_balance;
   economic_path_multiplier = portfolio_state.day_volume_multiplier;
   ++economic_path_ticks;
  }

void CompleteEconomicPath()
  {
   FlushEconomicMinute();
   if(economic_path_handle != INVALID_HANDLE) FileFlush(economic_path_handle);
   PrintFormat("V7VR_PATH rows=%I64d failed=%d scope=every-delivered-EA-tick-minute-extrema", economic_path_rows, (economic_path_failed ? 1 : 0));
  }

void CloseEconomicPath()
  {
   if(economic_path_handle != INVALID_HANDLE)
     { FileFlush(economic_path_handle); FileClose(economic_path_handle); economic_path_handle = INVALID_HANDLE; }
  }
#endif
