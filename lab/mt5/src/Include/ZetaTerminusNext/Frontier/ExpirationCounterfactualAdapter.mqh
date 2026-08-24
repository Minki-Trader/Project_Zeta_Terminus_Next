#ifndef ZETA_NEXT_FRONTIER_EXPIRATION_COUNTERFACTUAL_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_EXPIRATION_COUNTERFACTUAL_ADAPTER_MQH

#define EXPIRATION_COUNTERFACTUAL_CAPACITY 64
const int EXPIRATION_COUNTERFACTUAL_PENDING_SECONDS = 4 * 60 * 60;
const int EXPIRATION_COUNTERFACTUAL_HOLD_SECONDS = 4 * 60 * 60;
const int EXPIRATION_COUNTERFACTUAL_TOTAL_SECONDS =
   EXPIRATION_COUNTERFACTUAL_PENDING_SECONDS +
   EXPIRATION_COUNTERFACTUAL_HOLD_SECONDS;

datetime counterfactual_expiration[EXPIRATION_COUNTERFACTUAL_CAPACITY];
int counterfactual_direction[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_feature[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_limit[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_stop[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_span[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_pre_closest[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_pre_endpoint[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_pre_efficiency[EXPIRATION_COUNTERFACTUAL_CAPACITY];
double counterfactual_pre_persistence[EXPIRATION_COUNTERFACTUAL_CAPACITY];
int counterfactual_count = 0;
long counterfactual_pre_ticks = 0;
long counterfactual_post_ticks = 0;
long counterfactual_pre_copy_failures = 0;
long counterfactual_post_copy_failures = 0;
long counterfactual_invalid_geometry = 0;
long counterfactual_labels_emitted = 0;


struct ExpirationShadowOutcome
  {
   bool touched;
   long touch_seconds;
   bool stopped;
   long stop_seconds;
   bool complete;
   double fill_price;
   double stop_price;
   double net_ratio;
   double mfe_ratio;
   double mae_ratio;
  };


bool ExpirationCounterfactualInitialize()
  {
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void ExpirationCounterfactualReset()
  {
   ArrayInitialize(counterfactual_expiration, 0);
   ArrayInitialize(counterfactual_direction, 0);
   ArrayInitialize(counterfactual_feature, 0.0);
   ArrayInitialize(counterfactual_limit, 0.0);
   ArrayInitialize(counterfactual_stop, 0.0);
   ArrayInitialize(counterfactual_span, 0.0);
   ArrayInitialize(counterfactual_pre_closest, 0.0);
   ArrayInitialize(counterfactual_pre_endpoint, 0.0);
   ArrayInitialize(counterfactual_pre_efficiency, 0.0);
   ArrayInitialize(counterfactual_pre_persistence, 0.0);
   counterfactual_count = 0;
   counterfactual_pre_ticks = 0;
   counterfactual_post_ticks = 0;
   counterfactual_pre_copy_failures = 0;
   counterfactual_post_copy_failures = 0;
   counterfactual_invalid_geometry = 0;
   counterfactual_labels_emitted = 0;
  }


double ExpirationCounterfactualGap(const MqlTick &tick,
                                   const int direction,
                                   const double price)
  {
   if(direction > 0)
      return(tick.ask - price);
   return(price - tick.bid);
  }


double ExpirationCounterfactualCloseRatio(const MqlTick &tick,
                                          const int direction,
                                          const double fill_price,
                                          const double span)
  {
   if(direction > 0)
      return((tick.bid - fill_price) / span);
   return((fill_price - tick.ask) / span);
  }


bool ExpirationCounterfactualTouched(const MqlTick &tick,
                                     const int direction,
                                     const double entry_price)
  {
   if(direction > 0)
      return(tick.ask <= entry_price);
   return(tick.bid >= entry_price);
  }


bool ExpirationCounterfactualStopped(const MqlTick &tick,
                                     const int direction,
                                     const double stop_price)
  {
   if(direction > 0)
      return(tick.bid <= stop_price);
   return(tick.ask >= stop_price);
  }


void ExpirationCounterfactualClearOutcome(ExpirationShadowOutcome &outcome)
  {
   outcome.touched = false;
   outcome.touch_seconds = -1;
   outcome.stopped = false;
   outcome.stop_seconds = -1;
   outcome.complete = false;
   outcome.fill_price = 0.0;
   outcome.stop_price = 0.0;
   outcome.net_ratio = 0.0;
   outcome.mfe_ratio = 0.0;
   outcome.mae_ratio = 0.0;
  }


void ExpirationCounterfactualSimulate(const MqlTick &ticks[],
                                      const int tick_count,
                                      const datetime expiration,
                                      const int direction,
                                      const double entry_price,
                                      const double stop_price,
                                      const double span,
                                      const int pending_seconds,
                                      const bool market_entry,
                                      ExpirationShadowOutcome &outcome)
  {
   ExpirationCounterfactualClearOutcome(outcome);
   if(tick_count <= 0 || direction == 0 || entry_price <= 0.0 ||
      stop_price <= 0.0 || span <= 0.0)
      return;

   int fill_index = -1;
   for(int index = 0; index < tick_count; ++index)
     {
      const MqlTick current = ticks[index];
      if(current.bid <= 0.0 || current.ask <= 0.0 ||
         current.ask < current.bid)
         continue;
      const long elapsed = (long)current.time - (long)expiration;
      if(elapsed < 0)
         continue;
      if(market_entry ||
         (elapsed <= pending_seconds &&
          ExpirationCounterfactualTouched(current,
                                          direction,
                                          entry_price)))
        {
         fill_index = index;
         outcome.touched = true;
         outcome.touch_seconds = elapsed;
         outcome.fill_price =
            (market_entry
             ? (direction > 0 ? current.ask : current.bid)
             : entry_price);
         outcome.stop_price =
            (market_entry
             ? outcome.fill_price - direction * span
             : stop_price);
         break;
        }
      if(elapsed > pending_seconds)
         break;
     }
   if(fill_index < 0)
      return;

   const long fill_server = (long)ticks[fill_index].time;
   const long hold_end = fill_server + EXPIRATION_COUNTERFACTUAL_HOLD_SECONDS;
   bool observed = false;
   double last_ratio = 0.0;
   for(int index = fill_index; index < tick_count; ++index)
     {
      const MqlTick current = ticks[index];
      if(current.bid <= 0.0 || current.ask <= 0.0 ||
         current.ask < current.bid)
         continue;
      if((long)current.time > hold_end)
        {
         outcome.complete = true;
         break;
        }
      const double ratio =
         ExpirationCounterfactualCloseRatio(current,
                                            direction,
                                            outcome.fill_price,
                                            span);
      if(!observed)
        {
         observed = true;
         outcome.mfe_ratio = ratio;
         outcome.mae_ratio = ratio;
        }
      else
        {
         outcome.mfe_ratio = MathMax(outcome.mfe_ratio, ratio);
         outcome.mae_ratio = MathMin(outcome.mae_ratio, ratio);
        }
      last_ratio = ratio;
      if(ExpirationCounterfactualStopped(current,
                                         direction,
                                         outcome.stop_price))
        {
         outcome.stopped = true;
         outcome.stop_seconds = (long)current.time - fill_server;
         outcome.net_ratio = -1.0;
         outcome.complete = true;
         return;
        }
     }
   outcome.net_ratio = last_ratio;
   if(!outcome.complete && tick_count > 0 &&
      (long)ticks[tick_count - 1].time >= hold_end)
      outcome.complete = true;
  }


void ExpirationCounterfactualObserveExpiration(const int direction,
                                               const datetime expiration)
  {
   const datetime observed_server = TimeCurrent();
   const datetime placed_server =
      expiration - PASSIVE_ACTIVATION_BARS * PASSIVE_BAR_SECONDS;
   const double limit_price = passive_pending_limit_price;
   const double stop_loss = passive_pending_stop_loss;
   const double feature = passive_pending_feature;
   const double protection_span = MathAbs(limit_price - stop_loss);
   if(counterfactual_count >= EXPIRATION_COUNTERFACTUAL_CAPACITY ||
      direction == 0 || expiration <= 0 || placed_server <= 0 ||
      observed_server < placed_server || limit_price <= 0.0 ||
      stop_loss <= 0.0 || protection_span <= 0.0)
     {
      ++counterfactual_invalid_geometry;
      return;
     }

   MqlTick ticks[];
   ResetLastError();
   const int copied =
      CopyTicksRange("US100",
                     ticks,
                     COPY_TICKS_ALL,
                     (ulong)((long)placed_server * 1000),
                     (ulong)((long)observed_server * 1000 + 999));
   const int history_error = GetLastError();
   if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
     {
      ++counterfactual_pre_copy_failures;
      PrintFormat("ZETA_FRONTIER_EXPIRATION_PRE_FAILURE|server=%I64d|expiration=%I64d|direction=%d|copied=%d|size=%d|error=%d",
                  (long)observed_server,
                  (long)expiration,
                  direction,
                  copied,
                  ArraySize(ticks),
                  history_error);
      return;
     }

   bool known = false;
   double first_gap = 0.0;
   double closest_gap = 0.0;
   double farthest_gap = 0.0;
   double endpoint_gap = 0.0;
   double prior_gap = 0.0;
   double path_travel = 0.0;
   int valid_ticks = 0;
   for(int index = 0; index < copied; ++index)
     {
      const MqlTick current = ticks[index];
      if(current.bid <= 0.0 || current.ask <= 0.0 ||
         current.ask < current.bid)
         continue;
      const double gap =
         ExpirationCounterfactualGap(current, direction, limit_price);
      if(!MathIsValidNumber(gap))
         continue;
      if(!known)
        {
         known = true;
         first_gap = gap;
         closest_gap = gap;
         farthest_gap = gap;
        }
      else
        {
         closest_gap = MathMin(closest_gap, gap);
         farthest_gap = MathMax(farthest_gap, gap);
         path_travel += MathAbs(gap - prior_gap);
        }
      prior_gap = gap;
      endpoint_gap = gap;
      ++valid_ticks;
     }
   if(!known || valid_ticks <= 0)
     {
      ++counterfactual_invalid_geometry;
      return;
     }

   const int slot = counterfactual_count;
   counterfactual_expiration[slot] = observed_server;
   counterfactual_direction[slot] = direction;
   counterfactual_feature[slot] = feature;
   counterfactual_limit[slot] = limit_price;
   counterfactual_stop[slot] = stop_loss;
   counterfactual_span[slot] = protection_span;
   counterfactual_pre_closest[slot] = closest_gap / protection_span;
   counterfactual_pre_endpoint[slot] = endpoint_gap / protection_span;
   counterfactual_pre_efficiency[slot] =
      (path_travel > 0.0
       ? (endpoint_gap - first_gap) / path_travel
       : 0.0);
   counterfactual_pre_persistence[slot] =
      (farthest_gap > 0.0 ? endpoint_gap / farthest_gap : 0.0);
   ++counterfactual_count;
   counterfactual_pre_ticks += valid_ticks;
  }


void ExpirationCounterfactualReportOutcome(const string prefix,
                                           const ExpirationShadowOutcome &outcome)
  {
   PrintFormat("%s_touched=%d|%s_touch_seconds=%I64d|%s_stopped=%d|%s_stop_seconds=%I64d|%s_complete=%d|%s_fill=%.5f|%s_stop=%.5f|%s_net_ratio=%.10f|%s_mfe_ratio=%.10f|%s_mae_ratio=%.10f",
               prefix,
               (int)outcome.touched,
               prefix,
               outcome.touch_seconds,
               prefix,
               (int)outcome.stopped,
               prefix,
               outcome.stop_seconds,
               prefix,
               (int)outcome.complete,
               prefix,
               outcome.fill_price,
               prefix,
               outcome.stop_price,
               prefix,
               outcome.net_ratio,
               prefix,
               outcome.mfe_ratio,
               prefix,
               outcome.mae_ratio);
  }


void ExpirationCounterfactualReport()
  {
   for(int slot = 0; slot < counterfactual_count; ++slot)
     {
      const datetime expiration = counterfactual_expiration[slot];
      MqlTick ticks[];
      ResetLastError();
      const int copied =
         CopyTicksRange(
            "US100",
            ticks,
            COPY_TICKS_ALL,
            (ulong)((long)expiration * 1000 + 1),
            (ulong)(((long)expiration +
                     EXPIRATION_COUNTERFACTUAL_TOTAL_SECONDS) * 1000));
      const int history_error = GetLastError();
      if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
        {
         ++counterfactual_post_copy_failures;
         PrintFormat("ZETA_FRONTIER_EXPIRATION_POST_FAILURE|expiration=%I64d|direction=%d|copied=%d|size=%d|error=%d",
                     (long)expiration,
                     counterfactual_direction[slot],
                     copied,
                     ArraySize(ticks),
                     history_error);
         continue;
        }

      const int direction = counterfactual_direction[slot];
      const double limit_price = counterfactual_limit[slot];
      const double protection_span = counterfactual_span[slot];
      const double expiration_executable =
         (direction > 0 ? ticks[0].ask : ticks[0].bid);
      const double reprice_50 =
         limit_price + 0.50 * (expiration_executable - limit_price);
      const double reprice_75 =
         limit_price + 0.75 * (expiration_executable - limit_price);
      const double reprice_50_stop =
         reprice_50 - direction * protection_span;
      const double reprice_75_stop =
         reprice_75 - direction * protection_span;

      ExpirationShadowOutcome original = {};
      ExpirationShadowOutcome reprice50 = {};
      ExpirationShadowOutcome reprice75 = {};
      ExpirationShadowOutcome market = {};
      ExpirationCounterfactualSimulate(
         ticks,
         copied,
         expiration,
         direction,
         limit_price,
         counterfactual_stop[slot],
         protection_span,
         EXPIRATION_COUNTERFACTUAL_PENDING_SECONDS,
         false,
         original);
      ExpirationCounterfactualSimulate(ticks,
                                       copied,
                                       expiration,
                                       direction,
                                       reprice_50,
                                       reprice_50_stop,
                                       protection_span,
                                       60 * 60,
                                       false,
                                       reprice50);
      ExpirationCounterfactualSimulate(ticks,
                                       copied,
                                       expiration,
                                       direction,
                                       reprice_75,
                                       reprice_75_stop,
                                       protection_span,
                                       60 * 60,
                                       false,
                                       reprice75);
      ExpirationCounterfactualSimulate(ticks,
                                       copied,
                                       expiration,
                                       direction,
                                       expiration_executable,
                                       expiration_executable -
                                          direction * protection_span,
                                       protection_span,
                                       0,
                                       true,
                                       market);

      ++counterfactual_labels_emitted;
      counterfactual_post_ticks += copied;
      PrintFormat("ZETA_FRONTIER_EXPIRATION_LABEL|expiration=%I64d|direction=%d|feature=%.10f|limit=%.5f|stop=%.5f|span=%.5f|post_ticks=%d|pre_closest=%.10f|pre_endpoint=%.10f|pre_efficiency=%.10f|pre_persistence=%.10f|expiration_executable=%.5f|reprice_50=%.5f|reprice_75=%.5f",
                  (long)expiration,
                  direction,
                  counterfactual_feature[slot],
                  limit_price,
                  counterfactual_stop[slot],
                  protection_span,
                  copied,
                  counterfactual_pre_closest[slot],
                  counterfactual_pre_endpoint[slot],
                  counterfactual_pre_efficiency[slot],
                  counterfactual_pre_persistence[slot],
                  expiration_executable,
                  reprice_50,
                  reprice_75);
      ExpirationCounterfactualReportOutcome("original", original);
      ExpirationCounterfactualReportOutcome("reprice50", reprice50);
      ExpirationCounterfactualReportOutcome("reprice75", reprice75);
      ExpirationCounterfactualReportOutcome("market", market);
     }
   PrintFormat("ZETA_FRONTIER_EXPIRATION_SUMMARY|captured=%d|labels=%I64d|pre_ticks=%I64d|post_ticks=%I64d|pre_copy_failures=%I64d|post_copy_failures=%I64d|invalid_geometry=%I64d|pending_hours=4|shadow_hold_hours=4",
               counterfactual_count,
               counterfactual_labels_emitted,
               counterfactual_pre_ticks,
               counterfactual_post_ticks,
               counterfactual_pre_copy_failures,
               counterfactual_post_copy_failures,
               counterfactual_invalid_geometry);
  }

#endif
