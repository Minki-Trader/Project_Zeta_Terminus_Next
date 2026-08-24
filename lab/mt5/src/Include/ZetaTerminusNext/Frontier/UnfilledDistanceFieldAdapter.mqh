#ifndef ZETA_NEXT_FRONTIER_UNFILLED_DISTANCE_FIELD_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_UNFILLED_DISTANCE_FIELD_ADAPTER_MQH

long unfilled_distance_emitted = 0;
long unfilled_distance_copy_failures = 0;
long unfilled_distance_invalid_geometry = 0;
long unfilled_distance_ticks_observed = 0;


bool UnfilledDistanceFieldInitialize()
  {
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void UnfilledDistanceFieldReset()
  {
   unfilled_distance_emitted = 0;
   unfilled_distance_copy_failures = 0;
   unfilled_distance_invalid_geometry = 0;
   unfilled_distance_ticks_observed = 0;
  }


double UnfilledExecutableGap(const MqlTick &tick,
                             const int direction,
                             const double limit_price)
  {
   if(direction > 0)
      return(tick.ask - limit_price);
   return(limit_price - tick.bid);
  }


void UnfilledDistanceFieldObserveExpiration(const int direction,
                                            const datetime expiration)
  {
   const datetime observed_server = TimeCurrent();
   const datetime placed_server =
      expiration - PASSIVE_ACTIVATION_BARS * PASSIVE_BAR_SECONDS;
   const double limit_price = passive_pending_limit_price;
   const double stop_loss = passive_pending_stop_loss;
   const double feature = passive_pending_feature;
   const double protection_span = MathAbs(limit_price - stop_loss);
   if(direction == 0 || expiration <= 0 || placed_server <= 0 ||
      observed_server < placed_server || limit_price <= 0.0 ||
      stop_loss <= 0.0 || protection_span <= 0.0)
     {
      ++unfilled_distance_invalid_geometry;
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
      ++unfilled_distance_copy_failures;
      PrintFormat("ZETA_FRONTIER_UNFILLED_DISTANCE_FAILURE|server=%I64d|expiration=%I64d|direction=%d|copied=%d|size=%d|error=%d",
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
         UnfilledExecutableGap(current, direction, limit_price);
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
      ++unfilled_distance_invalid_geometry;
      return;
     }

   const double first_ratio = first_gap / protection_span;
   const double closest_ratio = closest_gap / protection_span;
   const double farthest_ratio = farthest_gap / protection_span;
   const double endpoint_ratio = endpoint_gap / protection_span;
   const double escape_ratio =
      (endpoint_gap - closest_gap) / protection_span;
   const double travel_ratio = path_travel / protection_span;
   const double path_efficiency =
      (path_travel > 0.0
       ? (endpoint_gap - first_gap) / path_travel
       : 0.0);
   const double elapsed_minutes =
      ((double)((long)observed_server - (long)placed_server)) / 60.0;
   const double endpoint_speed =
      (elapsed_minutes > 0.0 ? endpoint_ratio / elapsed_minutes : 0.0);

   ++unfilled_distance_emitted;
   unfilled_distance_ticks_observed += valid_ticks;
   PrintFormat("ZETA_FRONTIER_UNFILLED_GEOMETRY|server=%I64d|placed=%I64d|expiration=%I64d|direction=%d|feature=%.10f|limit=%.5f|stop=%.5f|span=%.5f|ticks=%d|first_ratio=%.10f|closest_ratio=%.10f|farthest_ratio=%.10f|endpoint_ratio=%.10f|escape_ratio=%.10f|travel_ratio=%.10f|path_efficiency=%.10f|endpoint_speed=%.10f",
               (long)observed_server,
               (long)placed_server,
               (long)expiration,
               direction,
               feature,
               limit_price,
               stop_loss,
               protection_span,
               valid_ticks,
               first_ratio,
               closest_ratio,
               farthest_ratio,
               endpoint_ratio,
               escape_ratio,
               travel_ratio,
               path_efficiency,
               endpoint_speed);
  }


void UnfilledDistanceFieldReport()
  {
   PrintFormat("ZETA_FRONTIER_UNFILLED_DISTANCE_SUMMARY|emitted=%I64d|copy_failures=%I64d|invalid_geometry=%I64d|ticks_observed=%I64d",
               unfilled_distance_emitted,
               unfilled_distance_copy_failures,
               unfilled_distance_invalid_geometry,
               unfilled_distance_ticks_observed);
  }

#endif
