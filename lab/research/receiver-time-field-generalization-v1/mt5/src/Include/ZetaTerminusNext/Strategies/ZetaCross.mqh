#ifndef ZETA_NEXT_MODULE_05_MQH
#define ZETA_NEXT_MODULE_05_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaCross.mqh

bool CalculateUS100RelativeMomentum(double &zscore)
  {
   const int scale_window = 120;
   const int count = scale_window + 2;
   const datetime expected = iTime("US100", PERIOD_H1, 1);
   if(expected == 0)
      return(false);
   double own[];
   double peer_a[];
   double peer_b[];
   if(!CopySynchronizedCloses("US100", count, expected, own) ||
      !CopySynchronizedCloses("US30", count, expected, peer_a) ||
      !CopySynchronizedCloses("US500", count, expected, peer_b))
      return(false);
   double relative[];
   ArrayResize(relative, scale_window + 1);
   for(int sample = 0; sample <= scale_window; ++sample)
     {
      if(own[sample] <= 0.0 || own[sample + 1] <= 0.0 ||
         peer_a[sample] <= 0.0 || peer_a[sample + 1] <= 0.0 ||
         peer_b[sample] <= 0.0 || peer_b[sample + 1] <= 0.0)
         return(false);
      relative[sample] =
         MathLog(own[sample + 1] / own[sample]) -
         0.5 * (MathLog(peer_a[sample + 1] / peer_a[sample]) +
                MathLog(peer_b[sample + 1] / peer_b[sample]));
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
   if(standard_deviation <= 0.0)
      return(false);
   zscore = relative[scale_window] / standard_deviation;
   return(MathIsValidNumber(zscore));
  }


void ProcessUS100Cross()
  {
   EntryGateResult gate = {};
   EvaluateEntryGate(US100_CROSS, 17, 0, gate);
   ApplyEntryGateResult(US100_CROSS, gate);
   CommitOpportunityConsumption(US100_CROSS, gate);
   if(!gate.enter_signal_path)
      return;
   const datetime bar = gate.current_bar;
   if(IsUSEquityClosureDate())
     {
      component_states[US100_CROSS].entry_check_result = "SESSION_EXCLUDED";
      RecordEvent(US100_CROSS,
                  "SKIP_SESSION",
                  0.0,
                  0.0,
                  TimeToString(ServerMidnight(), TIME_DATE));
      PersistDecision(US100_CROSS, bar);
      return;
     }
   double feature = 0.0;
   if(!CalculateUS100RelativeMomentum(feature))
     {
      component_states[US100_CROSS].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (MathAbs(feature) >= 0.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? 1 : -1) : 0);
   int rtf_matching_emitters = 0;
   const bool rtf_qualified =
      (signal_passed &&
       RtfCrossQualifies(direction,
                         TimeCurrent(),
                         rtf_matching_emitters));
   if(signal_passed)
      RtfNoteCrossSignal(rtf_qualified,
                         rtf_matching_emitters);
   SetEntrySignalCheck(US100_CROSS,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(US100_CROSS, bar))
     {
      component_states[US100_CROSS].entry_check_result = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(US100_CROSS, direction, feature);
      RtfAdoptCrossLifecycle(rtf_qualified,
                             rtf_matching_emitters);
      if(!FinalizeDecisionJournal(US100_CROSS,
                                  component_states[US100_CROSS].entry_check_result))
         component_states[US100_CROSS].entry_check_result = "PERSISTENCE_FAILED";
     }
  }


#endif
