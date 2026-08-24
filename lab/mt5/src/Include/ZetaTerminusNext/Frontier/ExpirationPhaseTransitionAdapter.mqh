#ifndef ZETA_NEXT_FRONTIER_EXPIRATION_PHASE_TRANSITION_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_EXPIRATION_PHASE_TRANSITION_ADAPTER_MQH

const double PHASE_TRANSITION_EFFICIENCY_Q50_VALUE = 0.0125708051;
const double PHASE_TRANSITION_EFFICIENCY_Q75_VALUE = 0.0172137644;
const double PHASE_TRANSITION_ENDPOINT_Q50_VALUE = 0.1546587652;
const double PHASE_TRANSITION_PERSISTENCE_Q75_VALUE = 0.8771183848;

datetime phase_transition_last_expiration = 0;
bool phase_transition_last_qualified = false;
double phase_transition_last_efficiency = 0.0;
double phase_transition_last_endpoint = 0.0;
double phase_transition_last_persistence = 0.0;
long phase_transition_expirations = 0;
long phase_transition_qualified = 0;
long phase_transition_attempts = 0;
long phase_transition_entries = 0;
long phase_transition_not_opened = 0;
long phase_transition_journal_failures = 0;
long phase_transition_copy_failures = 0;
long phase_transition_invalid_geometry = 0;
long phase_transition_ticks_observed = 0;


string ExpirationPhaseTransitionModeName()
  {
   if(InpExpirationPhaseTransitionMode == PHASE_TRANSITION_EFFICIENCY_Q75)
      return("EFFICIENCY_Q75");
   if(InpExpirationPhaseTransitionMode == PHASE_TRANSITION_EFFICIENCY_Q50)
      return("EFFICIENCY_Q50");
   return("PERSISTENT_ESCAPE");
  }


bool ExpirationPhaseTransitionInitialize()
  {
   if(InpExpirationPhaseTransitionMode != PHASE_TRANSITION_EFFICIENCY_Q75 &&
      InpExpirationPhaseTransitionMode != PHASE_TRANSITION_EFFICIENCY_Q50 &&
      InpExpirationPhaseTransitionMode != PHASE_TRANSITION_PERSISTENT_ESCAPE)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void ExpirationPhaseTransitionReset()
  {
   phase_transition_last_expiration = 0;
   phase_transition_last_qualified = false;
   phase_transition_last_efficiency = 0.0;
   phase_transition_last_endpoint = 0.0;
   phase_transition_last_persistence = 0.0;
   phase_transition_expirations = 0;
   phase_transition_qualified = 0;
   phase_transition_attempts = 0;
   phase_transition_entries = 0;
   phase_transition_not_opened = 0;
   phase_transition_journal_failures = 0;
   phase_transition_copy_failures = 0;
   phase_transition_invalid_geometry = 0;
   phase_transition_ticks_observed = 0;
  }


double ExpirationPhaseTransitionGap(const MqlTick &tick,
                                    const int direction,
                                    const double limit_price)
  {
   if(direction > 0)
      return(tick.ask - limit_price);
   return(limit_price - tick.bid);
  }


bool ExpirationPhaseTransitionQualified(const double efficiency,
                                        const double endpoint,
                                        const double persistence)
  {
   if(InpExpirationPhaseTransitionMode == PHASE_TRANSITION_EFFICIENCY_Q75)
      return(efficiency >= PHASE_TRANSITION_EFFICIENCY_Q75_VALUE);
   if(InpExpirationPhaseTransitionMode == PHASE_TRANSITION_EFFICIENCY_Q50)
      return(efficiency >= PHASE_TRANSITION_EFFICIENCY_Q50_VALUE);
   return(endpoint >= PHASE_TRANSITION_ENDPOINT_Q50_VALUE &&
          persistence >= PHASE_TRANSITION_PERSISTENCE_Q75_VALUE);
  }


void ExpirationPhaseTransitionObserveExpiration(const int direction,
                                                const datetime expiration)
  {
   phase_transition_last_expiration = expiration;
   phase_transition_last_qualified = false;
   phase_transition_last_efficiency = 0.0;
   phase_transition_last_endpoint = 0.0;
   phase_transition_last_persistence = 0.0;
   ++phase_transition_expirations;

   const datetime observed_server = TimeCurrent();
   const datetime placed_server =
      expiration - PASSIVE_ACTIVATION_BARS * PASSIVE_BAR_SECONDS;
   const double limit_price = passive_pending_limit_price;
   const double stop_loss = passive_pending_stop_loss;
   const double protection_span = MathAbs(limit_price - stop_loss);
   if(direction == 0 || expiration <= 0 || placed_server <= 0 ||
      observed_server < placed_server || limit_price <= 0.0 ||
      stop_loss <= 0.0 || protection_span <= 0.0)
     {
      ++phase_transition_invalid_geometry;
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
      ++phase_transition_copy_failures;
      PrintFormat("ZETA_FRONTIER_PHASE_TRANSITION_FAILURE|expiration=%I64d|direction=%d|copied=%d|size=%d|error=%d",
                  (long)expiration,
                  direction,
                  copied,
                  ArraySize(ticks),
                  history_error);
      return;
     }

   bool known = false;
   double first_gap = 0.0;
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
         ExpirationPhaseTransitionGap(current, direction, limit_price);
      if(!MathIsValidNumber(gap))
         continue;
      if(!known)
        {
         known = true;
         first_gap = gap;
         farthest_gap = gap;
        }
      else
        {
         farthest_gap = MathMax(farthest_gap, gap);
         path_travel += MathAbs(gap - prior_gap);
        }
      prior_gap = gap;
      endpoint_gap = gap;
      ++valid_ticks;
     }
   if(!known || valid_ticks <= 0)
     {
      ++phase_transition_invalid_geometry;
      return;
     }

   phase_transition_last_efficiency =
      (path_travel > 0.0
       ? (endpoint_gap - first_gap) / path_travel
       : 0.0);
   phase_transition_last_endpoint = endpoint_gap / protection_span;
   phase_transition_last_persistence =
      (farthest_gap > 0.0 ? endpoint_gap / farthest_gap : 0.0);
   phase_transition_last_qualified =
      ExpirationPhaseTransitionQualified(
         phase_transition_last_efficiency,
         phase_transition_last_endpoint,
         phase_transition_last_persistence);
   if(phase_transition_last_qualified)
      ++phase_transition_qualified;
   phase_transition_ticks_observed += valid_ticks;
   PrintFormat("ZETA_FRONTIER_PHASE_TRANSITION_OBSERVE|expiration=%I64d|direction=%d|mode=%s|ticks=%d|efficiency=%.10f|endpoint=%.10f|persistence=%.10f|qualified=%d",
               (long)expiration,
               direction,
               ExpirationPhaseTransitionModeName(),
               valid_ticks,
               phase_transition_last_efficiency,
               phase_transition_last_endpoint,
               phase_transition_last_persistence,
               (int)phase_transition_last_qualified);
  }


void ExpirationPhaseTransitionAfterExpiration(const int direction,
                                              const datetime expiration,
                                              const double feature,
                                              const double limit_price,
                                              const double stop_loss,
                                              const double planned_risk)
  {
   if(!phase_transition_last_qualified ||
      phase_transition_last_expiration != expiration || direction == 0)
      return;
   ++phase_transition_attempts;
   const datetime decision_bar = iTime("US100", PERIOD_M15, 0);
   const datetime deadline =
      TimeCurrent() + InpMaxEntryDelayMinutes * 60;
   BeginEntryCheck(US100_PASSIVE_LIMIT,
                   decision_bar,
                   "CHECKING_PHASE_TRANSITION");
   SetEntrySignalCheck(US100_PASSIVE_LIMIT,
                       feature,
                       true,
                       direction,
                       "PHASE_TRANSITION_SIGNAL");
   if(!PersistDecisionUntil(US100_PASSIVE_LIMIT,
                            decision_bar,
                            deadline))
     {
      ++phase_transition_journal_failures;
      return;
     }

   const bool requested =
      OpenComponent(US100_PASSIVE_LIMIT, direction, feature);
   const bool opened =
      component_states[US100_PASSIVE_LIMIT].position_identifier > 0;
   const string outcome =
      component_states[US100_PASSIVE_LIMIT].entry_check_result;
   if(!FinalizeDecisionJournal(US100_PASSIVE_LIMIT, outcome))
      ++phase_transition_journal_failures;
   if(opened)
      ++phase_transition_entries;
   else
      ++phase_transition_not_opened;
   PrintFormat("ZETA_FRONTIER_PHASE_TRANSITION_ACTION|expiration=%I64d|direction=%d|mode=%s|feature=%.10f|expired_limit=%.5f|expired_stop=%.5f|expired_planned_risk=%.4f|efficiency=%.10f|endpoint=%.10f|persistence=%.10f|requested=%d|opened=%d|outcome=%s",
               (long)expiration,
               direction,
               ExpirationPhaseTransitionModeName(),
               feature,
               limit_price,
               stop_loss,
               planned_risk,
               phase_transition_last_efficiency,
               phase_transition_last_endpoint,
               phase_transition_last_persistence,
               (int)requested,
               (int)opened,
               outcome);
  }


void ExpirationPhaseTransitionReport()
  {
   PrintFormat("ZETA_FRONTIER_PHASE_TRANSITION_SUMMARY|mode=%s|expirations=%I64d|qualified=%I64d|attempts=%I64d|entries=%I64d|not_opened=%I64d|journal_failures=%I64d|copy_failures=%I64d|invalid_geometry=%I64d|ticks_observed=%I64d",
               ExpirationPhaseTransitionModeName(),
               phase_transition_expirations,
               phase_transition_qualified,
               phase_transition_attempts,
               phase_transition_entries,
               phase_transition_not_opened,
               phase_transition_journal_failures,
               phase_transition_copy_failures,
               phase_transition_invalid_geometry,
               phase_transition_ticks_observed);
  }

#endif
