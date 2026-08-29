#ifndef ZETA_OPT_DD20_MSR1_ROUTER_MQH
#define ZETA_OPT_DD20_MSR1_ROUTER_MQH

// Exact fixed router policy retained by Lab Unit 099. This is a fresh,
// self-contained implementation inside the Optimization campaign; it does
// not include or link the legacy repository, Live, Lab or another campaign.

#define ROUTER_COMPONENT_COUNT 5
#define ROUTER_FEATURE_COUNT 10

const double ROUTER_RIDGE_ALPHA = 10.0;
const double ROUTER_LABEL_LOWER_QUANTILE = 0.02;
const double ROUTER_LABEL_UPPER_QUANTILE = 0.98;
const int ROUTER_MINIMUM_TOTAL_SAMPLES = 80;
const int ROUTER_MINIMUM_COMPONENT_SAMPLES = 8;
const double ROUTER_LABEL_VOLUME = 0.01;

struct MarketStateRouterSample
  {
   int component;
   datetime closed_at;
   double label;
   double features[ROUTER_FEATURE_COUNT];
  };

MarketStateRouterSample router_samples[];
bool router_virtual_active[ROUTER_COMPONENT_COUNT];
datetime router_virtual_opened_at[ROUTER_COMPONENT_COUNT];
datetime router_virtual_last_close_attempt[ROUTER_COMPONENT_COUNT];
int router_virtual_direction[ROUTER_COMPONENT_COUNT];
double router_virtual_entry_price[ROUTER_COMPONENT_COUNT];
double router_virtual_entry_spread[ROUTER_COMPONENT_COUNT];
double router_virtual_features[ROUTER_COMPONENT_COUNT][ROUTER_FEATURE_COUNT];
datetime router_last_decision_bar[ROUTER_COMPONENT_COUNT];

bool router_decision_valid[ROUTER_COMPONENT_COUNT];
datetime router_decision_bar[ROUTER_COMPONENT_COUNT];
int router_decision_direction[ROUTER_COMPONENT_COUNT];
double router_decision_feature[ROUTER_COMPONENT_COUNT];
double router_decision_rank[ROUTER_COMPONENT_COUNT];
bool router_decision_allowed[ROUTER_COMPONENT_COUNT];

double router_feature_means[ROUTER_FEATURE_COUNT];
double router_feature_scales[ROUTER_FEATURE_COUNT];
double router_coefficients[ROUTER_FEATURE_COUNT];
double router_intercept = 0.0;
double router_system[ROUTER_FEATURE_COUNT][ROUTER_FEATURE_COUNT + 1];
double router_training_predictions[];
int router_training_components[];
bool router_model_ready = false;
int router_quarter_key = -1;
long router_model_fit_attempts = 0;
long router_model_fit_count = 0;
long router_model_fit_failures = 0;

bool router_economic_started = false;
long router_virtual_starts_total[ROUTER_COMPONENT_COUNT];
long router_virtual_closes_total[ROUTER_COMPONENT_COUNT];
long router_virtual_starts_economic[ROUTER_COMPONENT_COUNT];
long router_virtual_closes_economic[ROUTER_COMPONENT_COUNT];
double router_virtual_net_total[ROUTER_COMPONENT_COUNT];
double router_virtual_net_economic[ROUTER_COMPONENT_COUNT];
long router_allowed_signals = 0;
long router_blocked_signals = 0;
long router_core_consults = 0;
long router_core_allowed = 0;
long router_core_blocked = 0;
long router_core_virtual_occupied_blocks = 0;
long router_core_missing_decision_blocks = 0;
long router_signal_mismatch_faults = 0;
long router_virtual_start_failures = 0;
long router_virtual_close_data_waits = 0;
long router_output_failures = 0;
int router_decision_handle = INVALID_HANDLE;


string RouterComponentId(const int component)
  {
   if(component < 0 || component >= ROUTER_COMPONENT_COUNT)
      return("UNKNOWN");
   return(component_definitions[component].id);
  }


void ResetMarketStateRouterArtifacts()
  {
   FileDelete(ROUTER_DECISION_LEDGER_PATH);
   FileDelete(ROUTER_SUMMARY_PATH);
  }


void RouterResetDecisionCache(const int component)
  {
   router_decision_valid[component] = false;
   router_decision_bar[component] = 0;
   router_decision_direction[component] = 0;
   router_decision_feature[component] = 0.0;
   router_decision_rank[component] = 0.0;
   router_decision_allowed[component] = false;
  }


void InitializeMarketStateRouter()
  {
   ArrayResize(router_samples, 0);
   ArrayResize(router_training_predictions, 0);
   ArrayResize(router_training_components, 0);
   ArrayInitialize(router_virtual_active, false);
   ArrayInitialize(router_virtual_opened_at, 0);
   ArrayInitialize(router_virtual_last_close_attempt, 0);
   ArrayInitialize(router_virtual_direction, 0);
   ArrayInitialize(router_virtual_entry_price, 0.0);
   ArrayInitialize(router_virtual_entry_spread, 0.0);
   ArrayInitialize(router_last_decision_bar, 0);
   ArrayInitialize(router_feature_means, 0.0);
   ArrayInitialize(router_feature_scales, 0.0);
   ArrayInitialize(router_coefficients, 0.0);
   ArrayInitialize(router_virtual_starts_total, 0);
   ArrayInitialize(router_virtual_closes_total, 0);
   ArrayInitialize(router_virtual_starts_economic, 0);
   ArrayInitialize(router_virtual_closes_economic, 0);
   ArrayInitialize(router_virtual_net_total, 0.0);
   ArrayInitialize(router_virtual_net_economic, 0.0);
   for(int component = 0; component < ROUTER_COMPONENT_COUNT; ++component)
      RouterResetDecisionCache(component);
   router_intercept = 0.0;
   router_model_ready = false;
   router_quarter_key = -1;
   router_model_fit_attempts = 0;
   router_model_fit_count = 0;
   router_model_fit_failures = 0;
   router_allowed_signals = 0;
   router_blocked_signals = 0;
   router_core_consults = 0;
   router_core_allowed = 0;
   router_core_blocked = 0;
   router_core_virtual_occupied_blocks = 0;
   router_core_missing_decision_blocks = 0;
   router_signal_mismatch_faults = 0;
   router_virtual_start_failures = 0;
   router_virtual_close_data_waits = 0;
   router_output_failures = 0;
   router_economic_started =
      (TimeCurrent() >= InpRouterActualTradingStart);

   router_decision_handle =
      FileOpen(ROUTER_DECISION_LEDGER_PATH,
               FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(router_decision_handle == INVALID_HANDLE)
     {
      ++router_output_failures;
     }
   else
     {
      FileWrite(router_decision_handle,
                "schema",
                "server_time",
                "economic_window",
                "component_id",
                "decision_bar",
                "direction",
                "feature",
                "rank",
                "allowed",
                "model_ready",
                "sample_count",
                "quarter_key");
      FileFlush(router_decision_handle);
     }
  }


bool MarketStateRouterEconomicStarted()
  {
   return(router_economic_started);
  }


void RouterUpdateEconomicStart()
  {
   if(router_economic_started || TimeCurrent() < InpRouterActualTradingStart)
      return;
   router_economic_started = true;
   router_allowed_signals = 0;
   router_blocked_signals = 0;
   router_core_consults = 0;
   router_core_allowed = 0;
   router_core_blocked = 0;
   router_core_virtual_occupied_blocks = 0;
   router_core_missing_decision_blocks = 0;
   router_signal_mismatch_faults = 0;
   ArrayInitialize(router_virtual_starts_economic, 0);
   ArrayInitialize(router_virtual_closes_economic, 0);
   ArrayInitialize(router_virtual_net_economic, 0.0);
   PrintFormat("%s router economic window started at %s samples=%d model=%s",
               EXECUTION_VERSION,
               TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
               ArraySize(router_samples),
               (router_model_ready ? "ready" : "warmup"));
  }


void RouterBuildFeatures(const int component,
                         const int direction,
                         const double raw_feature,
                         double &features[])
  {
   ArrayResize(features, ROUTER_FEATURE_COUNT);
   const double clipped = MathMax(-20.0, MathMin(20.0, raw_feature));
   features[0] = clipped;
   features[1] = MathAbs(clipped);
   features[2] = (double)direction;
   MqlDateTime parts = {};
   TimeCurrent(parts);
   const int monday_weekday = (parts.day_of_week + 6) % 7;
   const double angle = 2.0 * M_PI * (double)monday_weekday / 5.0;
   features[3] = MathSin(angle);
   features[4] = MathCos(angle);
   for(int index = 0; index < ROUTER_COMPONENT_COUNT; ++index)
      features[5 + index] = (index == component ? 1.0 : 0.0);
  }


double RouterQuantile(double &sorted_values[], const double probability)
  {
   const int count = ArraySize(sorted_values);
   if(count <= 0)
      return(0.0);
   if(count == 1)
      return(sorted_values[0]);
   const double position = (count - 1) * probability;
   const int lower = (int)MathFloor(position);
   const int upper = (int)MathCeil(position);
   if(lower == upper)
      return(sorted_values[lower]);
   const double weight = position - lower;
   return(sorted_values[lower] * (1.0 - weight) +
          sorted_values[upper] * weight);
  }


double RouterPredictFeatures(const double &features[])
  {
   double prediction = router_intercept;
   for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
     {
      const double standardized =
         (features[feature] - router_feature_means[feature]) /
         router_feature_scales[feature];
      prediction += router_coefficients[feature] * standardized;
     }
   return(prediction);
  }


bool RouterSolveSystem()
  {
   for(int column = 0; column < ROUTER_FEATURE_COUNT; ++column)
     {
      int pivot = column;
      double magnitude = MathAbs(router_system[column][column]);
      for(int row = column + 1; row < ROUTER_FEATURE_COUNT; ++row)
        {
         const double candidate = MathAbs(router_system[row][column]);
         if(candidate > magnitude)
           {
            magnitude = candidate;
            pivot = row;
           }
        }
      if(magnitude <= 1.0e-12)
         return(false);
      if(pivot != column)
         for(int item = column; item <= ROUTER_FEATURE_COUNT; ++item)
           {
            const double temporary = router_system[column][item];
            router_system[column][item] = router_system[pivot][item];
            router_system[pivot][item] = temporary;
           }
      const double divisor = router_system[column][column];
      for(int item = column; item <= ROUTER_FEATURE_COUNT; ++item)
         router_system[column][item] /= divisor;
      for(int row = 0; row < ROUTER_FEATURE_COUNT; ++row)
        {
         if(row == column)
            continue;
         const double factor = router_system[row][column];
         if(MathAbs(factor) <= 1.0e-18)
            continue;
         for(int item = column; item <= ROUTER_FEATURE_COUNT; ++item)
            router_system[row][item] -=
               factor * router_system[column][item];
        }
     }
   for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
      router_coefficients[feature] =
         router_system[feature][ROUTER_FEATURE_COUNT];
   return(true);
  }


bool RouterFitModel()
  {
   ++router_model_fit_attempts;
   const int count = ArraySize(router_samples);
   int component_counts[ROUTER_COMPONENT_COUNT] = {0, 0, 0, 0, 0};
   for(int sample = 0; sample < count; ++sample)
      ++component_counts[router_samples[sample].component];
   if(count < ROUTER_MINIMUM_TOTAL_SAMPLES)
     {
      router_model_ready = false;
      return(false);
     }
   for(int component = 0; component < ROUTER_COMPONENT_COUNT; ++component)
      if(component_counts[component] < ROUTER_MINIMUM_COMPONENT_SAMPLES)
        {
         router_model_ready = false;
         return(false);
        }

   ArrayInitialize(router_feature_means, 0.0);
   ArrayInitialize(router_feature_scales, 0.0);
   ArrayInitialize(router_coefficients, 0.0);
   for(int sample = 0; sample < count; ++sample)
      for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
         router_feature_means[feature] +=
            router_samples[sample].features[feature];
   for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
      router_feature_means[feature] /= count;
   for(int sample = 0; sample < count; ++sample)
      for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
        {
         const double difference =
            router_samples[sample].features[feature] -
            router_feature_means[feature];
         router_feature_scales[feature] += difference * difference;
        }
   for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
     {
      router_feature_scales[feature] =
         MathSqrt(router_feature_scales[feature] / count);
      if(router_feature_scales[feature] <= 1.0e-12)
         router_feature_scales[feature] = 1.0;
     }

   double sorted_labels[];
   ArrayResize(sorted_labels, count);
   for(int sample = 0; sample < count; ++sample)
      sorted_labels[sample] = router_samples[sample].label;
   ArraySort(sorted_labels);
   const double lower =
      RouterQuantile(sorted_labels, ROUTER_LABEL_LOWER_QUANTILE);
   const double upper =
      RouterQuantile(sorted_labels, ROUTER_LABEL_UPPER_QUANTILE);
   double clipped_labels[];
   ArrayResize(clipped_labels, count);
   double label_mean = 0.0;
   for(int sample = 0; sample < count; ++sample)
     {
      clipped_labels[sample] =
         MathMax(lower, MathMin(upper, router_samples[sample].label));
      label_mean += clipped_labels[sample];
     }
   label_mean /= count;

   for(int row = 0; row < ROUTER_FEATURE_COUNT; ++row)
      for(int column = 0; column <= ROUTER_FEATURE_COUNT; ++column)
         router_system[row][column] = 0.0;
   for(int sample = 0; sample < count; ++sample)
     {
      double standardized[ROUTER_FEATURE_COUNT];
      for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
         standardized[feature] =
            (router_samples[sample].features[feature] -
             router_feature_means[feature]) /
            router_feature_scales[feature];
      const double centered_label = clipped_labels[sample] - label_mean;
      for(int row = 0; row < ROUTER_FEATURE_COUNT; ++row)
        {
         router_system[row][ROUTER_FEATURE_COUNT] +=
            standardized[row] * centered_label;
         for(int column = 0; column < ROUTER_FEATURE_COUNT; ++column)
            router_system[row][column] +=
               standardized[row] * standardized[column];
        }
     }
   for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
      router_system[feature][feature] += ROUTER_RIDGE_ALPHA;
   router_intercept = label_mean;
   if(!RouterSolveSystem())
     {
      router_model_ready = false;
      ++router_model_fit_failures;
      return(false);
     }
   ArrayResize(router_training_predictions, count);
   ArrayResize(router_training_components, count);
   for(int sample = 0; sample < count; ++sample)
     {
      router_training_predictions[sample] =
         RouterPredictFeatures(router_samples[sample].features);
      router_training_components[sample] = router_samples[sample].component;
     }
   router_model_ready = true;
   ++router_model_fit_count;
   PrintFormat("%s router fit samples=%d fits=%I64d clip=[%.6f,%.6f]",
               EXECUTION_VERSION,
               count,
               router_model_fit_count,
               lower,
               upper);
   return(true);
  }


void RouterUpdateQuarter()
  {
   MqlDateTime parts = {};
   TimeCurrent(parts);
   const int key = parts.year * 4 + (parts.mon - 1) / 3;
   if(key == router_quarter_key)
      return;
   router_quarter_key = key;
   RouterFitModel();
  }


double RouterRank(const int component, const double &features[])
  {
   if(!router_model_ready)
      return(1.0);
   const double score = RouterPredictFeatures(features);
   int component_count = 0;
   int less_or_equal = 0;
   for(int sample = 0; sample < ArraySize(router_training_predictions); ++sample)
     {
      if(router_training_components[sample] != component)
         continue;
      ++component_count;
      if(router_training_predictions[sample] <= score)
         ++less_or_equal;
     }
   if(component_count <= 0)
      return(1.0);
   return((double)less_or_equal / component_count);
  }


void RouterWriteDecision(const int component,
                         const datetime bar,
                         const int direction,
                         const double feature,
                         const double rank,
                         const bool allowed)
  {
   if(router_decision_handle == INVALID_HANDLE)
      return;
   const uint written =
      FileWrite(router_decision_handle,
                "zeta-opt-dd20-market-state-router-decision-v1",
                TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
                (router_economic_started ? 1 : 0),
                RouterComponentId(component),
                TimeToString(bar, TIME_DATE | TIME_MINUTES),
                direction,
                feature,
                rank,
                (allowed ? 1 : 0),
                (router_model_ready ? 1 : 0),
                ArraySize(router_samples),
                router_quarter_key);
   FileFlush(router_decision_handle);
   if(written == 0)
      ++router_output_failures;
  }


void RouterAddSample(const int component,
                     const double label,
                     const datetime closed_at)
  {
   const int next = ArraySize(router_samples);
   ArrayResize(router_samples, next + 1);
   router_samples[next].component = component;
   router_samples[next].closed_at = closed_at;
   router_samples[next].label = label;
   for(int feature = 0; feature < ROUTER_FEATURE_COUNT; ++feature)
      router_samples[next].features[feature] =
         router_virtual_features[component][feature];
  }


bool RouterStartVirtualLifecycle(const int component,
                                 const datetime bar,
                                 const int direction,
                                 const double feature)
  {
   if(router_virtual_active[component] || direction == 0)
      return(false);
   const string symbol = component_definitions[component].symbol;
   MqlTick tick = {};
   if(!ExecutableTick(symbol, tick) ||
      !TradeSessionAllows(symbol, TimeCurrent(), true))
     {
      if(router_economic_started)
         ++router_virtual_start_failures;
      return(false);
     }
   double features[];
   RouterBuildFeatures(component, direction, feature, features);
   router_virtual_active[component] = true;
   router_virtual_opened_at[component] = TimeCurrent();
   router_virtual_last_close_attempt[component] = 0;
   router_virtual_direction[component] = direction;
   router_virtual_entry_price[component] =
      (direction > 0 ? tick.ask : tick.bid);
   router_virtual_entry_spread[component] = tick.ask - tick.bid;
   for(int index = 0; index < ROUTER_FEATURE_COUNT; ++index)
      router_virtual_features[component][index] = features[index];

   const double rank = RouterRank(component, features);
   const bool allowed =
      (rank + 1.0e-12 >= InpRouterMinimumPercentile);
   router_decision_valid[component] = true;
   router_decision_bar[component] = bar;
   router_decision_direction[component] = direction;
   router_decision_feature[component] = feature;
   router_decision_rank[component] = rank;
   router_decision_allowed[component] = allowed;
   ++router_virtual_starts_total[component];
   if(router_economic_started)
     {
      ++router_virtual_starts_economic[component];
      if(allowed)
         ++router_allowed_signals;
      else
         ++router_blocked_signals;
     }
   RouterWriteDecision(component, bar, direction, feature, rank, allowed);
   return(true);
  }


void RouterFinalizeVirtualLifecycle(const int component,
                                    const MqlTick &exit_tick)
  {
   const string symbol = component_definitions[component].symbol;
   const int direction = router_virtual_direction[component];
   const double exit_price = (direction > 0 ? exit_tick.bid : exit_tick.ask);
   const double contract =
      SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   const double raw_net =
      direction * (exit_price - router_virtual_entry_price[component]) *
      contract * ROUTER_LABEL_VOLUME;
   const double extra_spread =
      MathMax(router_virtual_entry_spread[component],
              exit_tick.ask - exit_tick.bid) *
      contract * ROUTER_LABEL_VOLUME;
   const double label = raw_net - extra_spread;
   RouterAddSample(component, label, TimeCurrent());
   ++router_virtual_closes_total[component];
   router_virtual_net_total[component] += label;
   if(router_economic_started)
     {
      ++router_virtual_closes_economic[component];
      router_virtual_net_economic[component] += label;
     }
   router_virtual_active[component] = false;
   router_virtual_opened_at[component] = 0;
   router_virtual_last_close_attempt[component] = 0;
   router_virtual_direction[component] = 0;
   router_virtual_entry_price[component] = 0.0;
   router_virtual_entry_spread[component] = 0.0;
  }


void RouterProcessVirtualClosures()
  {
   for(int component = 0; component < ROUTER_COMPONENT_COUNT; ++component)
     {
      if(!router_virtual_active[component])
         continue;
      const int held_bars =
         iBarShift(component_definitions[component].symbol,
                   component_definitions[component].timeframe,
                   router_virtual_opened_at[component],
                   false);
      if(held_bars < component_definitions[component].hold_bars)
         continue;
      const datetime now = TimeCurrent();
      if(router_virtual_last_close_attempt[component] > 0 &&
         now - router_virtual_last_close_attempt[component] < 60)
         continue;
      const string symbol = component_definitions[component].symbol;
      if(!TradeSessionAllows(symbol, now, false))
        {
         router_virtual_last_close_attempt[component] = now;
         continue;
        }
      MqlTick tick = {};
      if(!ExecutableTick(symbol, tick))
        {
         if(router_economic_started)
            ++router_virtual_close_data_waits;
         continue;
        }
      RouterFinalizeVirtualLifecycle(component, tick);
     }
  }


bool RouterPrepareSignal(const int component,
                         const int hour,
                         const int minute,
                         datetime &current_bar)
  {
   current_bar =
      iTime(component_definitions[component].symbol,
            component_definitions[component].timeframe,
            0);
   if(current_bar == 0 ||
      router_last_decision_bar[component] == current_bar ||
      router_virtual_active[component])
      return(false);
   int elapsed = 0;
   if(!IsEntryWindow(hour, minute, elapsed))
      return(false);
   if(elapsed > InpMaxEntryDelayMinutes)
     {
      router_last_decision_bar[component] = current_bar;
      RouterResetDecisionCache(component);
      return(false);
     }
   return(true);
  }


void RouterConsumeSignal(const int component,
                         const datetime bar,
                         const bool passed,
                         const int direction,
                         const double feature)
  {
   router_last_decision_bar[component] = bar;
   RouterResetDecisionCache(component);
   if(passed)
      RouterStartVirtualLifecycle(component, bar, direction, feature);
  }


void RouterProcessRC4()
  {
   datetime bar = 0;
   if(!RouterPrepareSignal(RC4_BOTH, 13, 0, bar))
      return;
   double feature = 0.0;
   if(!CalculateRangeCompression("US30", 4, feature))
      return;
   const bool passed = (MathAbs(feature) >= 1.5);
   RouterConsumeSignal(RC4_BOTH,
                       bar,
                       passed,
                       (passed ? (feature > 0.0 ? 1 : -1) : 0),
                       feature);
  }


void RouterProcessRC16()
  {
   datetime bar = 0;
   if(!RouterPrepareSignal(RC16_LONG, 13, 30, bar))
      return;
   double feature = 0.0;
   if(!CalculateRangeCompression("US30", 16, feature))
      return;
   const bool passed = (feature >= 1.5);
   RouterConsumeSignal(RC16_LONG, bar, passed, (passed ? 1 : 0), feature);
  }


void RouterProcessPressure()
  {
   datetime bar = 0;
   if(!RouterPrepareSignal(US30_PRESSURE, 15, 0, bar))
      return;
   double feature = 0.0;
   if(!CalculateIntradayRangePressure("US30", feature))
      return;
   const bool passed = (MathAbs(feature) >= 0.5);
   RouterConsumeSignal(US30_PRESSURE,
                       bar,
                       passed,
                       (passed ? (feature > 0.0 ? 1 : -1) : 0),
                       feature);
  }


void RouterProcessReturn()
  {
   datetime bar = 0;
   if(!RouterPrepareSignal(US30_RETURN_REV_LONG, 16, 0, bar))
      return;
   if(IsUSEquityClosureDate())
     {
      router_last_decision_bar[US30_RETURN_REV_LONG] = bar;
      RouterResetDecisionCache(US30_RETURN_REV_LONG);
      return;
     }
   double feature = 0.0;
   if(!CalculateUS30ReturnImpulse(feature))
      return;
   const bool passed = (feature <= -0.5);
   RouterConsumeSignal(US30_RETURN_REV_LONG,
                       bar,
                       passed,
                       (passed ? 1 : 0),
                       feature);
  }


void RouterProcessCross()
  {
   datetime bar = 0;
   if(!RouterPrepareSignal(US100_CROSS, 17, 0, bar))
      return;
   if(IsUSEquityClosureDate())
     {
      router_last_decision_bar[US100_CROSS] = bar;
      RouterResetDecisionCache(US100_CROSS);
      return;
     }
   double feature = 0.0;
   if(!CalculateUS100RelativeMomentum(feature))
      return;
   const bool passed = (MathAbs(feature) >= 0.5);
   RouterConsumeSignal(US100_CROSS,
                       bar,
                       passed,
                       (passed ? (feature > 0.0 ? 1 : -1) : 0),
                       feature);
  }


void ProcessMarketStateRouter()
  {
   RouterUpdateQuarter();
   RouterUpdateEconomicStart();
   RouterProcessVirtualClosures();
   RouterProcessRC4();
   RouterProcessRC16();
   RouterProcessPressure();
   RouterProcessReturn();
   RouterProcessCross();
  }


bool MarketStateRouterPermitCoreEntry(const int component,
                                      const datetime bar,
                                      const int direction,
                                      const double feature)
  {
   ++router_core_consults;
   bool allowed = false;
   string reason = "NO_CURRENT_ROUTER_DECISION";
   double rank = -1.0;
   if(component < 0 || component >= ROUTER_COMPONENT_COUNT)
     {
      ++router_signal_mismatch_faults;
      EngageSafetyStop("invalid market-state router component");
      return(false);
     }
   else if(router_decision_valid[component] &&
           router_decision_bar[component] == bar)
     {
      rank = router_decision_rank[component];
      const double tolerance =
         1.0e-9 * MathMax(1.0, MathAbs(feature));
      if(router_decision_direction[component] != direction ||
         MathAbs(router_decision_feature[component] - feature) > tolerance)
        {
         reason = "ROUTER_CORE_SIGNAL_MISMATCH";
         ++router_signal_mismatch_faults;
         EngageSafetyStop("market-state router/core signal mismatch");
        }
      else if(router_decision_allowed[component])
        {
         allowed = true;
         reason = "ROUTER_ALLOWED";
        }
      else
         reason = "ROUTER_RANK_BLOCKED";
     }
   else if(component >= 0 && component < ROUTER_COMPONENT_COUNT &&
           router_virtual_active[component])
     {
      reason = "ROUTER_VIRTUAL_OCCUPIED";
      ++router_core_virtual_occupied_blocks;
     }
   else
      ++router_core_missing_decision_blocks;

   if(allowed)
     {
      ++router_core_allowed;
      return(true);
     }

   ++router_core_blocked;
   component_states[component].entry_check_result = "ROUTER_BLOCKED";
   const string detail =
      StringFormat("reason=%s rank=%.12f model=%s samples=%d quarter=%d",
                   reason,
                   rank,
                   (router_model_ready ? "ready" : "warmup"),
                   ArraySize(router_samples),
                   router_quarter_key);
   RecordEvent(component, "ROUTER_BLOCK", rank, feature, detail);
   ResearchRecordCandidateOutcome(component,
                                  "OUTCOME",
                                  "ROUTER_BLOCKED",
                                  detail);
   if(!FinalizeDecisionJournal(component, "ROUTER_BLOCKED"))
      component_states[component].entry_check_result = "PERSISTENCE_FAILED";
   return(false);
  }


void WriteMarketStateRouterSummary(const int reason)
  {
   if(router_decision_handle != INVALID_HANDLE)
     {
      FileFlush(router_decision_handle);
      FileClose(router_decision_handle);
      router_decision_handle = INVALID_HANDLE;
     }
   const int handle =
      FileOpen(ROUTER_SUMMARY_PATH, FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(handle == INVALID_HANDLE)
     {
      ++router_output_failures;
      return;
     }
   FileWrite(handle, "execution_version", EXECUTION_VERSION);
   FileWrite(handle, "reason", reason);
   FileWrite(handle,
             "actual_trading_start",
             TimeToString(InpRouterActualTradingStart,
                          TIME_DATE | TIME_SECONDS));
   FileWrite(handle, "sample_count", ArraySize(router_samples));
   FileWrite(handle, "model_ready", (router_model_ready ? 1 : 0));
   FileWrite(handle, "model_fit_attempts", router_model_fit_attempts);
   FileWrite(handle, "model_fit_count", router_model_fit_count);
   FileWrite(handle, "model_fit_failures", router_model_fit_failures);
   FileWrite(handle, "allowed_signals", router_allowed_signals);
   FileWrite(handle, "blocked_signals", router_blocked_signals);
   FileWrite(handle, "core_consults", router_core_consults);
   FileWrite(handle, "core_allowed", router_core_allowed);
   FileWrite(handle, "core_blocked", router_core_blocked);
   FileWrite(handle,
             "core_virtual_occupied_blocks",
             router_core_virtual_occupied_blocks);
   FileWrite(handle,
             "core_missing_decision_blocks",
             router_core_missing_decision_blocks);
   FileWrite(handle, "signal_mismatch_faults", router_signal_mismatch_faults);
   FileWrite(handle, "virtual_start_failures", router_virtual_start_failures);
   FileWrite(handle,
             "virtual_close_data_waits",
             router_virtual_close_data_waits);
   FileWrite(handle, "output_failures", router_output_failures);
   for(int component = 0; component < ROUTER_COMPONENT_COUNT; ++component)
     {
      const string prefix =
         "component_" + IntegerToString(component + 1) + "_";
      FileWrite(handle, prefix + "id", RouterComponentId(component));
      FileWrite(handle,
                prefix + "virtual_starts_total",
                router_virtual_starts_total[component]);
      FileWrite(handle,
                prefix + "virtual_closes_total",
                router_virtual_closes_total[component]);
      FileWrite(handle,
                prefix + "virtual_starts_economic",
                router_virtual_starts_economic[component]);
      FileWrite(handle,
                prefix + "virtual_closes_economic",
                router_virtual_closes_economic[component]);
      FileWrite(handle,
                prefix + "virtual_net_total",
                router_virtual_net_total[component]);
      FileWrite(handle,
                prefix + "virtual_net_economic",
                router_virtual_net_economic[component]);
      FileWrite(handle,
                prefix + "active_at_end",
                (router_virtual_active[component] ? 1 : 0));
     }
   FileFlush(handle);
   FileClose(handle);
   PrintFormat("%s router final samples=%d fits=%I64d allowed=%I64d "
               "blocked=%I64d core=%I64d/%I64d/%I64d mismatch=%I64d "
               "output_failures=%I64d",
               EXECUTION_VERSION,
               ArraySize(router_samples),
               router_model_fit_count,
               router_allowed_signals,
               router_blocked_signals,
               router_core_consults,
               router_core_allowed,
               router_core_blocked,
               router_signal_mismatch_faults,
               router_output_failures);
  }


#endif
