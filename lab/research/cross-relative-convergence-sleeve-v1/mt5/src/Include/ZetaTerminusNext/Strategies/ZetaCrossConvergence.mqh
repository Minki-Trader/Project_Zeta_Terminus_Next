#ifndef ZETA_NEXT_UNIT093_CROSS_CONVERGENCE_MQH
#define ZETA_NEXT_UNIT093_CROSS_CONVERGENCE_MQH

// Frozen Unit 093 mechanism: one-H1 target residual versus equal-weight peers,
// scaled by the preceding 120 residual observations and traded for convergence.

bool CalculateCrossRelativeConvergence(const string target,
                                       const string peer_a,
                                       const string peer_b,
                                       double &zscore)
  {
   const int scale_window = 120;
   const int count = scale_window + 2;
   const datetime expected = iTime(target, PERIOD_H1, 1);
   if(expected == 0)
      return(false);

   double own[];
   double peers_a[];
   double peers_b[];
   if(!CopySynchronizedCloses(target, count, expected, own) ||
      !CopySynchronizedCloses(peer_a, count, expected, peers_a) ||
      !CopySynchronizedCloses(peer_b, count, expected, peers_b))
      return(false);

   double relative[];
   ArrayResize(relative, scale_window + 1);
   for(int sample = 0; sample <= scale_window; ++sample)
     {
      if(own[sample] <= 0.0 || own[sample + 1] <= 0.0 ||
         peers_a[sample] <= 0.0 || peers_a[sample + 1] <= 0.0 ||
         peers_b[sample] <= 0.0 || peers_b[sample + 1] <= 0.0)
         return(false);
      relative[sample] =
         MathLog(own[sample + 1] / own[sample]) -
         0.5 * (MathLog(peers_a[sample + 1] / peers_a[sample]) +
                MathLog(peers_b[sample + 1] / peers_b[sample]));
     }

   double mean = 0.0;
   for(int sample = 0; sample < scale_window; ++sample)
      mean += relative[sample];
   mean /= scale_window;

   double squared = 0.0;
   for(int sample = 0; sample < scale_window; ++sample)
     {
      const double deviation = relative[sample] - mean;
      squared += deviation * deviation;
     }
   const double standard_deviation =
      MathSqrt(squared / (scale_window - 1));
   if(standard_deviation <= 0.0 ||
      !MathIsValidNumber(standard_deviation))
      return(false);

   // Preserve the anchored contract: do not subtract the historical mean from
   // the current residual before division by the historical standard deviation.
   zscore = relative[scale_window] / standard_deviation;
   return(MathIsValidNumber(zscore));
  }


void ProcessCrossRelativeConvergence(const int component,
                                     const string peer_a,
                                     const string peer_b)
  {
   EntryGateResult gate = {};
   EvaluateEntryGate(component, 17, 0, gate);
   ApplyEntryGateResult(component, gate);
   CommitOpportunityConsumption(component, gate);
   if(!gate.enter_signal_path)
      return;

   const datetime bar = gate.current_bar;
   if(IsUSEquityClosureDate())
     {
      component_states[component].entry_check_result = "SESSION_EXCLUDED";
      RecordEvent(component,
                  "SKIP_SESSION",
                  0.0,
                  0.0,
                  TimeToString(ServerMidnight(), TIME_DATE));
      PersistDecision(component, bar);
      return;
     }

   double feature = 0.0;
   if(!CalculateCrossRelativeConvergence(
         component_definitions[component].symbol,
         peer_a,
         peer_b,
         feature))
     {
      component_states[component].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }

   const bool signal_passed = (MathAbs(feature) >= 0.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? -1 : 1) : 0);
   SetEntrySignalCheck(component,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(component, bar))
     {
      component_states[component].entry_check_result = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(component, direction, feature);
      if(!FinalizeDecisionJournal(
            component,
            component_states[component].entry_check_result))
         component_states[component].entry_check_result =
            "PERSISTENCE_FAILED";
     }
  }


void ProcessUS30Convergence()
  {
   ProcessCrossRelativeConvergence(US30_CONVERGENCE, "US100", "US500");
  }


void ProcessUS500Convergence()
  {
   ProcessCrossRelativeConvergence(US500_CONVERGENCE, "US30", "US100");
  }


#endif
