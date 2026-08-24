#ifndef ZETA_NEXT_FRONTIER_OPPORTUNITY_ECOLOGY_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_OPPORTUNITY_ECOLOGY_ADAPTER_MQH

const int OPPORTUNITY_ECOLOGY_RELAY_SECONDS = 120 * 60;
const double OPPORTUNITY_ECOLOGY_VOLUME_MULTIPLIER = 2.0;

datetime ecology_last_signal_server[2][2];
datetime ecology_last_decision_bar[COMPONENT_COUNT];
bool ecology_entry_qualified[COMPONENT_COUNT];
long ecology_signal_count[COMPONENT_COUNT];
long ecology_qualified_count[COMPONENT_COUNT];


int OpportunityEcologySymbolIndex(const int component)
  {
   return(component == US100_CROSS || component == US100_PASSIVE_LIMIT ? 1 : 0);
  }


int OpportunityEcologyDirectionIndex(const int direction)
  {
   return(direction > 0 ? 1 : 0);
  }


int OpportunityEcologyActiveCount()
  {
   int count = (execution_state.passive_pending_order > 0 ? 1 : 0);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_states[component].position_identifier > 0)
         ++count;
   return(count);
  }


string OpportunityEcologyModeName()
  {
   if(InpOpportunityEcologyMode == ECOLOGY_CROSS_SYMBOL_RELAY_120)
      return("CROSS_SYMBOL_RELAY_120");
   if(InpOpportunityEcologyMode == ECOLOGY_RETURN_RECEIVER_RELAY_120)
      return("RETURN_RECEIVER_RELAY_120");
   return("SINGLE_ACTIVE_POSITION");
  }


bool OpportunityEcologyInitialize()
  {
   if(InpOpportunityEcologyMode != ECOLOGY_CROSS_SYMBOL_RELAY_120 &&
      InpOpportunityEcologyMode != ECOLOGY_SINGLE_ACTIVE_POSITION &&
      InpOpportunityEcologyMode != ECOLOGY_RETURN_RECEIVER_RELAY_120)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void OpportunityEcologyReset()
  {
   ArrayInitialize(ecology_last_signal_server, 0);
   ArrayInitialize(ecology_last_decision_bar, 0);
   ArrayInitialize(ecology_entry_qualified, false);
   ArrayInitialize(ecology_signal_count, 0);
   ArrayInitialize(ecology_qualified_count, 0);
  }


void OpportunityEcologyObserveSignal(const int component,
                                      const double value,
                                      const bool passed,
                                      const int direction)
  {
   if(component < 0 || component >= COMPONENT_COUNT)
      return;
   const datetime decision_bar = component_states[component].entry_check_bar;
   if(decision_bar > 0 &&
      ecology_last_decision_bar[component] == decision_bar)
      return;
   ecology_last_decision_bar[component] = decision_bar;
   ecology_entry_qualified[component] = false;
   if(!passed || direction == 0)
      return;

   const datetime now = TimeCurrent();
   const int symbol_index = OpportunityEcologySymbolIndex(component);
   const int direction_index = OpportunityEcologyDirectionIndex(direction);
   const int active_count = OpportunityEcologyActiveCount();
   const datetime relay_server =
      ecology_last_signal_server[1 - symbol_index][direction_index];
   const bool relay_qualified =
      (relay_server > 0 && now >= relay_server &&
       now - relay_server <= OPPORTUNITY_ECOLOGY_RELAY_SECONDS);
   const bool occupancy_qualified = (active_count == 1);
   bool qualified = false;
   if(InpOpportunityEcologyMode == ECOLOGY_CROSS_SYMBOL_RELAY_120)
      qualified = relay_qualified;
   else if(InpOpportunityEcologyMode == ECOLOGY_SINGLE_ACTIVE_POSITION)
      qualified = occupancy_qualified;
   else
      qualified =
         (component == US30_RETURN_REV_LONG && relay_qualified);

   ecology_entry_qualified[component] = qualified;
   ++ecology_signal_count[component];
   if(qualified)
      ++ecology_qualified_count[component];
   PrintFormat("ZETA_FRONTIER_ECOLOGY|server=%I64d|component=%d|mode=%s|direction=%d|signal=%.10f|active=%d|relay_age=%I64d|qualified=%d",
               (long)now,
               component,
               OpportunityEcologyModeName(),
               direction,
               value,
               active_count,
               (relay_server > 0 ? (long)(now - relay_server) : -1),
               (int)qualified);
   ecology_last_signal_server[symbol_index][direction_index] = now;
  }


double OpportunityEcologyEntryVolume(const int component,
                                     const string symbol)
  {
   // Pending-limit recovery has a fixed-volume lifecycle contract. It remains
   // part of the ecology state but is not resized by this adapter.
   if(component == US100_PASSIVE_LIMIT)
      return(InpBaseVolume);
   double base_volume = NormalizedVolume(symbol);
   if(base_volume <= 0.0 || component < 0 || component >= COMPONENT_COUNT ||
      !ecology_entry_qualified[component])
      return(base_volume);

   const double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double maximum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      return(0.0);
   const double requested =
      base_volume * OPPORTUNITY_ECOLOGY_VOLUME_MULTIPLIER;
   const double normalized = MathRound(requested / step) * step;
   if(normalized < minimum || normalized > maximum)
      return(0.0);
   return(normalized);
  }


void OpportunityEcologyReport()
  {
   long signals = 0;
   long qualified = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      signals += ecology_signal_count[component];
      qualified += ecology_qualified_count[component];
      PrintFormat("ZETA_FRONTIER_ECOLOGY_COMPONENT|component=%d|signals=%I64d|qualified=%I64d",
                  component,
                  ecology_signal_count[component],
                  ecology_qualified_count[component]);
     }
   PrintFormat("ZETA_FRONTIER_ECOLOGY_SUMMARY|mode=%s|signals=%I64d|qualified=%I64d|multiplier=%.2f",
               OpportunityEcologyModeName(),
               signals,
               qualified,
               OPPORTUNITY_ECOLOGY_VOLUME_MULTIPLIER);
  }

#endif
