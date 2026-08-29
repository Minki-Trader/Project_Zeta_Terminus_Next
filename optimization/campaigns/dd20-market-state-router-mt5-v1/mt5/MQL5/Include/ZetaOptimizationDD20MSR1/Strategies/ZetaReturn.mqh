#ifndef ZETA_NEXT_MODULE_07_MQH
#define ZETA_NEXT_MODULE_07_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaReturn.mqh

bool CalculateUS30ReturnImpulse(double &feature)
  {
   const int lookback = 4;
   const int scale_window = 120;
   double recent[];
   if(CopyClose("US30", PERIOD_H1, 1, lookback + 1, recent) !=
      lookback + 1)
      return(false);
   double prior[];
   if(CopyClose("US30", PERIOD_H1, 2, scale_window + 1, prior) !=
      scale_window + 1)
      return(false);
   double mean = 0.0;
   double returns[];
   ArrayResize(returns, scale_window);
   for(int index = 0; index < scale_window; ++index)
     {
      if(prior[index] <= 0.0 || prior[index + 1] <= 0.0)
         return(false);
      returns[index] = MathLog(prior[index + 1] / prior[index]);
      mean += returns[index];
     }
   mean /= scale_window;
   double squared = 0.0;
   for(int index = 0; index < scale_window; ++index)
     {
      const double deviation = returns[index] - mean;
      squared += deviation * deviation;
     }
   const double standard_deviation =
      MathSqrt(squared / (scale_window - 1));
   if(standard_deviation <= 0.0 ||
      recent[0] <= 0.0 || recent[lookback] <= 0.0)
      return(false);
   feature = MathLog(recent[lookback] / recent[0]) /
             (standard_deviation * MathSqrt((double)lookback));
   return(MathIsValidNumber(feature));
  }


void ProcessUS30ReturnReversalLong()
  {
   EntryGateResult gate = {};
   EvaluateEntryGate(US30_RETURN_REV_LONG, 16, 0, gate);
   ApplyEntryGateResult(US30_RETURN_REV_LONG, gate);
   CommitOpportunityConsumption(US30_RETURN_REV_LONG, gate);
   if(!gate.enter_signal_path)
      return;
   const datetime bar = gate.current_bar;
   if(IsUSEquityClosureDate())
     {
      component_states[US30_RETURN_REV_LONG].entry_check_result = "SESSION_EXCLUDED";
      RecordEvent(US30_RETURN_REV_LONG,
                  "SKIP_SESSION",
                  0.0,
                  0.0,
                  TimeToString(ServerMidnight(), TIME_DATE));
      PersistDecision(US30_RETURN_REV_LONG, bar);
      return;
     }
   double feature = 0.0;
   if(!CalculateUS30ReturnImpulse(feature))
     {
      component_states[US30_RETURN_REV_LONG].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (feature <= -0.5);
   SetEntrySignalCheck(US30_RETURN_REV_LONG,
                       feature,
                       signal_passed,
                       (signal_passed ? 1 : 0),
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(US30_RETURN_REV_LONG, bar))
     {
      component_states[US30_RETURN_REV_LONG].entry_check_result =
         "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      if(!MarketStateRouterPermitCoreEntry(US30_RETURN_REV_LONG,
                                           bar,
                                           1,
                                           feature))
         return;
      OpenComponent(US30_RETURN_REV_LONG, 1, feature);
      if(!FinalizeDecisionJournal(
             US30_RETURN_REV_LONG,
             component_states[US30_RETURN_REV_LONG].entry_check_result))
         component_states[US30_RETURN_REV_LONG].entry_check_result =
            "PERSISTENCE_FAILED";
     }
  }


#endif
