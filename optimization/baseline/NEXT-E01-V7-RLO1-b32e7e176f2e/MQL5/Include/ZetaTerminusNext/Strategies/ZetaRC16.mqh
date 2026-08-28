#ifndef ZETA_NEXT_MODULE_03_MQH
#define ZETA_NEXT_MODULE_03_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaRC16.mqh

void ProcessRC16Long()
  {
   EntryGateResult gate = {};
   EvaluateEntryGate(RC16_LONG, 13, 30, gate);
   ApplyEntryGateResult(RC16_LONG, gate);
   CommitOpportunityConsumption(RC16_LONG, gate);
   if(!gate.enter_signal_path)
      return;
   const datetime bar = gate.current_bar;
   double feature = 0.0;
   if(!CalculateRangeCompression("US30", 16, feature))
     {
      component_states[RC16_LONG].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (feature >= 1.5);
   SetEntrySignalCheck(RC16_LONG,
                       feature,
                       signal_passed,
                       (signal_passed ? 1 : 0),
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(RC16_LONG, bar))
     {
      component_states[RC16_LONG].entry_check_result = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(RC16_LONG, 1, feature);
      if(!FinalizeDecisionJournal(RC16_LONG, component_states[RC16_LONG].entry_check_result))
         component_states[RC16_LONG].entry_check_result = "PERSISTENCE_FAILED";
     }
  }


#endif
