#ifndef ZETA_VOLATILITY_RATCHET_MQH
#define ZETA_VOLATILITY_RATCHET_MQH

#resource "\\Experts\\ZetaV7VRStatic\\volatility-ratchet.onnx" as uchar vr_model_bytes[]
#include <ZetaV7VRStatic\Learning\ZetaVolatilityParameters.mqh>

long vr_model = INVALID_HANDLE;
int vr_trace = INVALID_HANDLE;
datetime vr_cache_bar[2];
bool vr_cache_ready[2];
double vr_cache_quantile[2][2];
double vr_cache_scale[2];
double vr_cache_quote[2][2];
datetime vr_cache_quote_minute[2];

void VRFault(const string detail)
  {
   ++vr_errors;
   EngageSafetyStop("volatility ratchet: " + detail);
  }

void VRTrace(const string kind, const int component, const datetime bar,
             const double value_a, const double value_b, const string detail)
  {
   if(vr_trace == INVALID_HANDLE) return;
   const ulong id = (component >= 0 ? component_states[component].position_identifier : 0);
   if(FileTell(vr_trace) > 64 * 1024 * 1024)
     { VRFault("bounded trace capacity exceeded"); return; }
   ResetLastError();
   const uint written = FileWrite(vr_trace, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
      (long)bar, kind, component, (long)id, value_a, value_b, detail, state_sequence);
   if(written == 0) VRFault("trace write failed");
  }

bool InitializeVRModel()
  {
   vr_model = OnnxCreateFromBuffer(vr_model_bytes, ONNX_DEFAULT);
   const long feature_shape[] = {1,11};
   const long weight_shape[] = {11,1};
   const long scalar_shape[] = {1,1};
   if(vr_model == INVALID_HANDLE ||
      !OnnxSetInputShape(vr_model, 0, feature_shape) ||
      !OnnxSetInputShape(vr_model, 1, weight_shape) ||
      !OnnxSetInputShape(vr_model, 2, scalar_shape) ||
      !OnnxSetOutputShape(vr_model, 0, scalar_shape))
      return(false);
   vr_trace = FileOpen(RESEARCH_OBSERVATION_DIRECTORY + "\\volatility-ratchet.csv",
      FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',');
   if(vr_trace == INVALID_HANDLE) return(false);
   FileWrite(vr_trace, "server_time", "bar", "kind", "component", "position_identifier",
      "value_a", "value_b", "detail", "state_sequence");
   ArrayInitialize(vr_cache_bar, 0);
   ArrayInitialize(vr_cache_ready, false);
   return(true);
  }

struct VRBar
  {
   datetime time;
   double high;
   double low;
   double close;
   double volume;
   double spread;
   datetime quote_minute;
  };

bool VRForecast(const int symbol_index, const datetime bar)
  {
   if(vr_cache_bar[symbol_index] == bar) return(vr_cache_ready[symbol_index]);
   vr_cache_bar[symbol_index] = bar;
   vr_cache_ready[symbol_index] = false;
   const string symbol = (symbol_index == 0 ? "US30" : "US100");
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   const int copied = CopyRates(symbol, PERIOD_M1, bar - 7*86400, bar - 1, rates);
   if(copied <= 0)
     {
      VRTrace("COPYRATES_UNAVAILABLE", -1, bar, symbol_index, copied, symbol);
      VRFault("native M1 acquisition unavailable: " + symbol);
      return(false);
     }
   VRBar bars[];
   ArrayResize(bars, 7*48 + 1);
   int count = 0;
   for(int i = 0; i < copied; ++i)
     {
      const datetime bucket = (datetime)(((long)rates[i].time / 1800) * 1800);
      if(rates[i].time >= bar || rates[i].time < bar - 7*86400 ||
         rates[i].close <= 0.0 || rates[i].high < rates[i].low || rates[i].spread < 0)
        { VRFault("invalid completed M1 input"); return(false); }
      if(count == 0 || bars[count-1].time != bucket)
        {
         if(count >= ArraySize(bars)) { VRFault("bar capacity"); return(false); }
         bars[count].time = bucket;
         bars[count].high = rates[i].high;
         bars[count].low = rates[i].low;
         bars[count].volume = 0.0;
         ++count;
        }
      const int k = count - 1;
      bars[k].high = MathMax(bars[k].high, rates[i].high);
      bars[k].low = MathMin(bars[k].low, rates[i].low);
      bars[k].close = rates[i].close;
      bars[k].volume += (double)rates[i].tick_volume;
      bars[k].spread = 0.01 * (double)rates[i].spread;
      bars[k].quote_minute = rates[i].time;
     }
   if(count < 48 || bars[count-1].time != bar - 1800)
     {
      ++vr_missing_prefixes;
      VRTrace("PREFIX_UNAVAILABLE", -1, bar, symbol_index, count, symbol);
      return(false);
     }
   double sorted_ranges[48];
   double range6 = 0.0, volume6 = 0.0, volume48 = 0.0;
   for(int j = 0; j < 48; ++j)
     {
      const int k = count - 48 + j;
      sorted_ranges[j] = bars[k].high - bars[k].low;
      volume48 += bars[k].volume;
      if(j >= 42) { range6 += sorted_ranges[j]; volume6 += bars[k].volume; }
     }
   ArraySort(sorted_ranges);
   const double scale = MathMax(0.01, 0.5 * (sorted_ranges[23] + sorted_ranges[24]));
   const double hour = (double)((long)bar % 86400) / 3600.0;
   vr_cache_scale[symbol_index] = scale;
   vr_cache_quote_minute[symbol_index] = bars[count-1].quote_minute;
   for(int side = 0; side < 2; ++side)
     {
      const int direction = (side == 0 ? -1 : 1);
      double raw[10];
      raw[0] = symbol_index;
      raw[1] = direction;
      raw[2] = MathLog(MathMax(0.01, range6 / 6.0) / scale);
      raw[3] = (bars[count-1].high - bars[count-1].low) / scale;
      raw[4] = direction * (bars[count-1].close - bars[count-2].close) / scale;
      raw[5] = direction * (bars[count-1].close - bars[count-7].close) / scale;
      raw[6] = MathLog((1.0 + volume6/6.0) / (1.0 + volume48/48.0));
      raw[7] = bars[count-1].spread / scale;
      raw[8] = MathSin(2.0 * M_PI * hour / 24.0);
      raw[9] = MathCos(2.0 * M_PI * hour / 24.0);
      matrixf features(1,11), weights(11,1), offset(1,1), output(1,1);
      features[0][0] = 1.0f;
      for(int j = 0; j < 10; ++j)
        {
         if(!MathIsValidNumber(raw[j])) { VRFault("feature arithmetic"); return(false); }
         features[0][j+1] = (float)MathMax(-6.0, MathMin(6.0,
            (raw[j] - vr_feature_mean[j]) / vr_feature_scale[j]));
        }
      for(int j = 0; j < 11; ++j) weights[j][0] = (float)vr_static_weights[j];
      offset[0][0] = (float)vr_static_calibration;
      if(!OnnxRun(vr_model, ONNX_NO_CONVERSION, features, weights, offset, output) ||
         !MathIsValidNumber((double)output[0][0]) || output[0][0] < 0.25f || output[0][0] > 8.0f)
        { VRFault("ONNX inference"); return(false); }
      vr_cache_quantile[symbol_index][side] = (double)output[0][0];
      vr_cache_quote[symbol_index][side] = bars[count-1].close + (direction < 0 ? bars[count-1].spread : 0.0);
      ++vr_forecasts;
      VRTrace("FORECAST", -1, bar, (double)output[0][0], scale,
         StringFormat("%s direction=%d quote=%.8f quote_minute=%I64d", symbol, direction,
            vr_cache_quote[symbol_index][side], (long)bars[count-1].quote_minute));
     }
   vr_cache_ready[symbol_index] = true;
   return(true);
  }

bool ResolveVRPending()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(vr_positions[component].pending_stop <= 0.0) continue;
      ulong ticket = 0;
      datetime opened = 0;
      const int count = CountOwnedPositions(component, ticket, opened);
      if(count == 0) { execution_state.pending_reconcile = true; continue; }
      if(count != 1 || !PositionSelectByTicket(ticket) ||
         (ulong)PositionGetInteger(POSITION_IDENTIFIER) != vr_positions[component].identifier)
        { VRFault("pending modify identity mismatch"); return(false); }
      const double broker_stop = PositionGetDouble(POSITION_SL);
      const double tick_size = SymbolInfoDouble(component_definitions[component].symbol, SYMBOL_TRADE_TICK_SIZE);
      const double tolerance = 0.5 * tick_size + 1.0e-9;
      if(MathAbs(broker_stop - vr_positions[component].pending_stop) <= tolerance)
        {
         component_states[component].entry_stop_loss = broker_stop;
         vr_positions[component].expected_stop = broker_stop;
         vr_positions[component].pending_stop = 0.0;
         ++vr_modify_adoptions;
         VRTrace("MODIFY_ADOPTED", component, vr_positions[component].last_bar,
            broker_stop, component_states[component].entry_planned_risk_usd, "original admission risk retained");
        }
      else if(MathAbs(broker_stop - vr_positions[component].expected_stop) <= tolerance)
        {
         vr_positions[component].pending_stop = 0.0;
         ++vr_modify_refusals;
         VRTrace("MODIFY_NOT_APPLIED", component, vr_positions[component].last_bar,
            broker_stop, 0.0, "old protected stop confirmed; no replay");
        }
      else { VRFault("broker stop differs from saved and pending"); return(false); }
      if(!SaveState()) { VRFault("modify adoption persistence"); return(false); }
      FileFlush(vr_trace);
     }
   return(true);
  }

void ProcessVolatilityRatchet()
  {
   if(portfolio_state.safety_stopped || persistence_failed || execution_state.broker_mismatch ||
      execution_state.trade_operation_active || execution_state.arc_modify_pending ||
      execution_state.arc_modify_retry_pending)
      return;
   if(!ResolveVRPending()) return;
   const datetime now = TimeCurrent();
   const datetime bar = (datetime)(((long)now / 1800) * 1800);
   // Forecasts are market-wide, including times without an accepted position.
   VRForecast(0, bar);
   VRForecast(1, bar);
   if(portfolio_state.safety_stopped || (long)now - (long)bar > 120) return;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      const ulong identifier = component_states[component].position_identifier;
      if(identifier == 0 || vr_positions[component].pending_stop > 0.0) continue;
      ulong ticket = 0;
      datetime opened = 0;
      if(CountOwnedPositions(component, ticket, opened) != 1 || !PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
        { VRFault("position identity changed"); return; }
      const int direction = component_states[component].entry_direction;
      if(vr_positions[component].identifier != identifier)
        {
         ClearVRPosition(component);
         vr_positions[component].identifier = identifier;
         vr_positions[component].entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
         vr_positions[component].initial_stop = (component == RC4_BOTH && arc_lifecycle_identifier == identifier
            ? arc_original_stop_loss : component_states[component].entry_stop_loss);
         vr_positions[component].directional_peak = direction * vr_positions[component].entry_price;
         vr_positions[component].expected_stop = component_states[component].entry_stop_loss;
         if(!SaveState()) { VRFault("position initialization persistence"); return; }
        }
      if(bar <= component_states[component].entry_time_server || vr_positions[component].last_bar == bar) continue;
      const int symbol_index = (component_definitions[component].symbol == "US100" ? 1 : 0);
      const int side = (direction < 0 ? 0 : 1);
      if(!vr_cache_ready[symbol_index]) continue;
      const string symbol = component_definitions[component].symbol;
      MqlTick tick = {};
      if(!ExecutableTick(symbol, tick) || !TradeSessionAllows(symbol, now, false)) continue;
      vr_positions[component].last_bar = bar;
      ++vr_decisions;
      if(vr_cache_quote_minute[symbol_index] >= component_states[component].entry_time_server)
         vr_positions[component].directional_peak = MathMax(vr_positions[component].directional_peak,
            direction * vr_cache_quote[symbol_index][side]);
      const double peak = vr_positions[component].directional_peak;
      const double raw_stop = direction * (peak - vr_cache_quantile[symbol_index][side] * vr_cache_scale[symbol_index]);
      const double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      if(tick_size <= 0.0) { VRFault("symbol price tick"); return; }
      const double target = NormalizeDouble((direction > 0 ? MathFloor(raw_stop/tick_size + 1.0e-8)
         : MathCeil(raw_stop/tick_size - 1.0e-8)) * tick_size, digits);
      const double entry = vr_positions[component].entry_price;
      const double saved_stop = component_states[component].entry_stop_loss;
      const double executable = (direction > 0 ? tick.bid : tick.ask);
      const double required = MinimumProtectionDistance(symbol);
      string reason = "INTENT";
      if(direction * (target - entry) <= component_states[component].entry_spread_price) reason = "NOT_PROFIT_PROTECTING";
      else if(direction * (target - saved_stop) < tick_size - 1.0e-8) reason = "NOT_TIGHTER";
      else if(direction * (executable - target) < required - 1.0e-8) reason = "NO_QUOTE_CLEARANCE";
      VRTrace(reason, component, bar, target, peak,
         StringFormat("old=%.8f q=%.8f scale=%.8f quote=%.8f required=%.8f", saved_stop,
            vr_cache_quantile[symbol_index][side], vr_cache_scale[symbol_index], executable, required));
      if(reason != "INTENT")
        {
         if(!SaveState()) { VRFault("closed-bar position state persistence"); return; }
         continue;
        }
      vr_positions[component].expected_stop = saved_stop;
      vr_positions[component].pending_stop = target;
      ++vr_modify_intents;
      if(!SaveState()) { VRFault("modify intent persistence"); return; }
      FileFlush(vr_trace);
      trade.SetExpertMagicNumber(component_definitions[component].magic);
      trade.SetDeviationInPoints(InpDeviationPoints);
      trade.SetTypeFillingBySymbol(symbol);
      trade.SetAsyncMode(false);
      const double take_profit = PositionGetDouble(POSITION_TP);
      execution_state.trade_operation_active = true;
      const bool requested = trade.PositionModify(ticket, target, take_profit);
      const uint retcode = trade.ResultRetcode();
      execution_state.trade_operation_active = false;
      VRTrace("MODIFY_RESULT", component, bar, (double)retcode, (requested ? 1.0 : 0.0), trade.ResultRetcodeDescription());
      if(!ResolveVRPending()) return;
     }
  }

void CloseVRModel()
  {
   if(vr_trace != INVALID_HANDLE) { FileFlush(vr_trace); FileClose(vr_trace); vr_trace = INVALID_HANDLE; }
   if(vr_model != INVALID_HANDLE) { OnnxRelease(vr_model); vr_model = INVALID_HANDLE; }
  }

#endif
