#property strict
#property version   "1.00"
#property description "Trade-free Tester-only reconstruction of actual Live position T15."

const string OUTPUT_FILE = "ZetaTerminusNext\\research\\actual-live-position-economics-v1\\t15-path.csv";
const string POSITION_ID = "T15";
const string STRATEGY = "Pressure";
const string SYMBOL_NAME = "US30";
const datetime ENTRY_TIME = D'2026.08.25 15:00:00';
const datetime EXIT_TIME = D'2026.08.25 16:32:02';
const double ENTRY_PRICE = 53739.1;
const double VOLUME = 0.01;
const double ACTUAL_NET_USD = -2.04;

string FormatServerTime(const long time_msc)
{
   if(time_msc <= 0)
      return "";
   const datetime seconds = (datetime)(time_msc / 1000);
   return TimeToString(seconds, TIME_DATE | TIME_SECONDS);
}

bool CalculateBuyMark(const double bid, double &mark)
{
   if(bid <= 0.0)
      return false;
   return OrderCalcProfit(ORDER_TYPE_BUY,
                          SYMBOL_NAME,
                          VOLUME,
                          ENTRY_PRICE,
                          bid,
                          mark);
}

bool WriteT15Path()
{
   MqlTick ticks[];
   const ulong from_msc = ((ulong)ENTRY_TIME) * 1000;
   const ulong to_msc = ((ulong)EXIT_TIME) * 1000 + 999;
   ResetLastError();
   const int copied = CopyTicksRange(SYMBOL_NAME,
                                     ticks,
                                     COPY_TICKS_ALL,
                                     from_msc,
                                     to_msc);
   if(copied <= 0)
   {
      PrintFormat("T15_PATH_COPY_FAILED copied=%d error=%d", copied, GetLastError());
      return false;
   }

   double mfe = -DBL_MAX;
   double mae = DBL_MAX;
   double closest_actual_mark = 0.0;
   double closest_actual_abs_diff = DBL_MAX;
   long mfe_msc = 0;
   long mae_msc = 0;
   long first_positive_msc = 0;
   long first_half_dollar_msc = 0;
   int usable_ticks = 0;

   for(int i = 0; i < copied; ++i)
   {
      if(ticks[i].time_msc < (long)from_msc || ticks[i].time_msc > (long)to_msc)
         continue;
      double mark = 0.0;
      if(!CalculateBuyMark(ticks[i].bid, mark))
         continue;
      ++usable_ticks;
      if(mark > mfe)
      {
         mfe = mark;
         mfe_msc = ticks[i].time_msc;
      }
      if(mark < mae)
      {
         mae = mark;
         mae_msc = ticks[i].time_msc;
      }
      if(first_positive_msc == 0 && mark > 0.0)
         first_positive_msc = ticks[i].time_msc;
      if(first_half_dollar_msc == 0 && mark >= 0.50)
         first_half_dollar_msc = ticks[i].time_msc;
      const double actual_diff = MathAbs(mark - ACTUAL_NET_USD);
      if(actual_diff < closest_actual_abs_diff)
      {
         closest_actual_abs_diff = actual_diff;
         closest_actual_mark = mark;
      }
   }

   if(usable_ticks <= 0 || mfe_msc <= 0 || mae_msc <= 0)
   {
      PrintFormat("T15_PATH_NO_USABLE_TICKS copied=%d usable=%d error=%d",
                  copied,
                  usable_ticks,
                  GetLastError());
      return false;
   }

   const double lifetime_seconds = (double)(EXIT_TIME - ENTRY_TIME);
   const double peak_elapsed_seconds = (double)(mfe_msc - (long)from_msc) / 1000.0;
   const double peak_fraction = (lifetime_seconds > 0.0)
                                ? peak_elapsed_seconds / lifetime_seconds
                                : 0.0;
   const double giveback = mfe - ACTUAL_NET_USD;

   const int handle = FileOpen(OUTPUT_FILE,
                               FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ,
                               ',');
   if(handle == INVALID_HANDLE)
   {
      PrintFormat("T15_PATH_FILE_OPEN_FAILED path=%s error=%d", OUTPUT_FILE, GetLastError());
      return false;
   }

   FileWrite(handle,
             "id",
             "strategy",
             "symbol",
             "side",
             "entry_server",
             "exit_server",
             "entry_price",
             "volume",
             "actual_net_usd",
             "digits",
             "point",
             "contract_size",
             "tick_size",
             "tick_value",
             "tick_value_profit",
             "tick_value_loss",
             "swap_long",
             "swap_short",
             "swap_mode",
             "copied_ticks",
             "usable_ticks",
             "mfe_mark_usd",
             "mfe_server",
             "mae_mark_usd",
             "mae_server",
             "first_positive_server",
             "first_half_dollar_server",
             "closest_actual_mark_usd",
             "closest_actual_abs_diff_usd",
             "mfe_to_final_giveback_usd",
             "peak_fraction");
   FileWrite(handle,
             POSITION_ID,
             STRATEGY,
             SYMBOL_NAME,
             "BUY",
             TimeToString(ENTRY_TIME, TIME_DATE | TIME_SECONDS),
             TimeToString(EXIT_TIME, TIME_DATE | TIME_SECONDS),
             DoubleToString(ENTRY_PRICE, 1),
             DoubleToString(VOLUME, 2),
             DoubleToString(ACTUAL_NET_USD, 6),
             IntegerToString((int)SymbolInfoInteger(SYMBOL_NAME, SYMBOL_DIGITS)),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_POINT), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_TRADE_CONTRACT_SIZE), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_TRADE_TICK_SIZE), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_TRADE_TICK_VALUE), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_TRADE_TICK_VALUE_PROFIT), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_TRADE_TICK_VALUE_LOSS), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_SWAP_LONG), 9),
             DoubleToString(SymbolInfoDouble(SYMBOL_NAME, SYMBOL_SWAP_SHORT), 9),
             IntegerToString((int)SymbolInfoInteger(SYMBOL_NAME, SYMBOL_SWAP_MODE)),
             IntegerToString(copied),
             IntegerToString(usable_ticks),
             DoubleToString(mfe, 9),
             FormatServerTime(mfe_msc),
             DoubleToString(mae, 9),
             FormatServerTime(mae_msc),
             FormatServerTime(first_positive_msc),
             FormatServerTime(first_half_dollar_msc),
             DoubleToString(closest_actual_mark, 9),
             DoubleToString(closest_actual_abs_diff, 9),
             DoubleToString(giveback, 9),
             DoubleToString(peak_fraction, 9));
   FileFlush(handle);
   FileClose(handle);

   PrintFormat("T15_PATH_WRITTEN copied=%d usable=%d mfe=%.6f mae=%.6f closest_diff=%.6f peak_fraction=%.6f",
               copied,
               usable_ticks,
               mfe,
               mae,
               closest_actual_abs_diff,
               peak_fraction);
   return true;
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER))
   {
      Print("T15_PATH_TESTER_ONLY");
      return INIT_FAILED;
   }
   if(_Symbol != SYMBOL_NAME)
   {
      PrintFormat("T15_PATH_WRONG_SYMBOL actual=%s required=%s", _Symbol, SYMBOL_NAME);
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnTick()
{
}

void OnDeinit(const int reason)
{
   WriteT15Path();
}
