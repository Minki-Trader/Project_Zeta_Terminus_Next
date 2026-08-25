#ifndef ZETA_ADMISSION_TOPOLOGY_MQH
#define ZETA_ADMISSION_TOPOLOGY_MQH

long admission_topology_checks = 0;
long admission_topology_overrides = 0;
long admission_topology_unit_blocks = 0;
long admission_topology_stop_risk_blocks = 0;
long admission_topology_read_failures = 0;
long admission_topology_post_placement_checks = 0;
long admission_topology_post_placement_confirmations = 0;
long admission_topology_post_placement_blocks = 0;
int admission_topology_maximum_units_after = 0;
double admission_topology_maximum_actual_stop_risk_after = 0.0;


bool AdmissionTopologyInitialize()
  {
   const double units =
      InpMaximumAggregateRiskFraction / InpMaximumPositionRiskFraction;
   return(MathAbs(units - 3.0) <= 1.0e-9);
  }


void AdmissionTopologyReset()
  {
   admission_topology_checks = 0;
   admission_topology_overrides = 0;
   admission_topology_unit_blocks = 0;
   admission_topology_stop_risk_blocks = 0;
   admission_topology_read_failures = 0;
   admission_topology_post_placement_checks = 0;
   admission_topology_post_placement_confirmations = 0;
   admission_topology_post_placement_blocks = 0;
   admission_topology_maximum_units_after = 0;
   admission_topology_maximum_actual_stop_risk_after = 0.0;
  }


bool AdmissionTopologyPositionStopRisk(const ulong ticket,
                                       double &actual_stop_risk)
  {
   actual_stop_risk = 0.0;
   if(ticket == 0 || !PositionSelectByTicket(ticket))
      return(false);
   const string symbol = PositionGetString(POSITION_SYMBOL);
   const double volume = PositionGetDouble(POSITION_VOLUME);
   const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   const double stop = PositionGetDouble(POSITION_SL);
   const ENUM_POSITION_TYPE type =
      (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   const int direction = (type == POSITION_TYPE_BUY ? 1 : -1);
   if(symbol == "" || volume <= 0.0 || entry <= 0.0 || stop <= 0.0)
      return(false);
   if((direction > 0 && stop >= entry) ||
      (direction < 0 && stop <= entry))
     {
      actual_stop_risk = 0.0;
      return(true);
     }
   return(BufferedPlannedRisk(symbol,
                              direction,
                              volume,
                              entry,
                              stop,
                              actual_stop_risk));
  }


bool AdmissionTopologyPendingStopRisk(double &actual_stop_risk)
  {
   actual_stop_risk = 0.0;
   if(execution_state.passive_pending_order == 0)
      return(true);
   if(passive_pending_direction == 0 ||
      passive_pending_limit_price <= 0.0 ||
      passive_pending_stop_loss <= 0.0)
      return(false);
   if((passive_pending_direction > 0 &&
       passive_pending_stop_loss >= passive_pending_limit_price) ||
      (passive_pending_direction < 0 &&
       passive_pending_stop_loss <= passive_pending_limit_price))
      return(true);
   return(BufferedPlannedRisk("US100",
                              passive_pending_direction,
                              InpBaseVolume,
                              passive_pending_limit_price,
                              passive_pending_stop_loss,
                              actual_stop_risk));
  }


bool AdmissionTopologyCurrentExposure(int &occupied_units,
                                      double &actual_stop_risk)
  {
   occupied_units = 0;
   actual_stop_risk = 0.0;
   for(int incumbent = 0; incumbent < COMPONENT_COUNT; ++incumbent)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int owned = CountOwnedPositions(incumbent, ticket, opened_at);
      if(owned < 0 || owned > 1)
         return(false);
      if(owned == 0)
         continue;
      double incumbent_stop_risk = 0.0;
      if(!AdmissionTopologyPositionStopRisk(ticket, incumbent_stop_risk))
         return(false);
      ++occupied_units;
      actual_stop_risk += incumbent_stop_risk;
     }

   if(execution_state.passive_pending_order != 0)
     {
      double pending_stop_risk = 0.0;
      if(!AdmissionTopologyPendingStopRisk(pending_stop_risk))
         return(false);
      ++occupied_units;
      actual_stop_risk += pending_stop_risk;
     }
   return(true);
  }


bool AdmissionTopologyAllow(const int component,
                            const string symbol,
                            const int direction,
                            const double volume,
                            const double entry_price,
                            const double stop_loss,
                            const double candidate_actual_stop_risk,
                            const double position_budget,
                            const double current_dollar_aggregate_after,
                            const double aggregate_budget)
  {
   ++admission_topology_checks;
   int occupied_units = 0;
   double actual_stop_risk_before = 0.0;
   if(!AdmissionTopologyCurrentExposure(occupied_units,
                                        actual_stop_risk_before))
     {
      ++admission_topology_read_failures;
      return(false);
     }

   const int units_after = occupied_units + 1;
   const double actual_stop_risk_after =
      actual_stop_risk_before + candidate_actual_stop_risk;
   admission_topology_maximum_units_after =
      MathMax(admission_topology_maximum_units_after, units_after);
   admission_topology_maximum_actual_stop_risk_after =
      MathMax(admission_topology_maximum_actual_stop_risk_after,
              actual_stop_risk_after);
   if(units_after > 3)
     {
      ++admission_topology_unit_blocks;
      return(false);
     }
   if(actual_stop_risk_after > aggregate_budget + 0.01)
     {
      ++admission_topology_stop_risk_blocks;
      return(false);
     }

   ++admission_topology_overrides;
   RecordEvent(component,
               "RISK_UNIT_ADMISSION_OVERRIDE",
               actual_stop_risk_after,
               (double)units_after,
               StringFormat("actual_before=%.4f actual_candidate=%.4f actual_cap=%.4f nominal_after=%.4f position_cap=%.4f symbol=%s direction=%d volume=%.2f entry=%.2f stop=%.2f",
                            actual_stop_risk_before,
                            candidate_actual_stop_risk,
                            aggregate_budget,
                            current_dollar_aggregate_after,
                            position_budget,
                            symbol,
                            direction,
                            volume,
                            entry_price,
                            stop_loss));
   return(true);
  }


bool AdmissionTopologyPostPlacementConfirmed(
   const double aggregate_before,
   const double pending_planned_risk,
   const double admitted_capital)
  {
   ++admission_topology_post_placement_checks;
   int occupied_units = 0;
   double actual_stop_risk = 0.0;
   if(admitted_capital <= 0.0 ||
      !AdmissionTopologyCurrentExposure(occupied_units, actual_stop_risk))
     {
      ++admission_topology_read_failures;
      ++admission_topology_post_placement_blocks;
      return(false);
     }

   const double actual_stop_risk_cap =
      admitted_capital * InpMaximumAggregateRiskFraction;
   admission_topology_maximum_units_after =
      MathMax(admission_topology_maximum_units_after, occupied_units);
   admission_topology_maximum_actual_stop_risk_after =
      MathMax(admission_topology_maximum_actual_stop_risk_after,
              actual_stop_risk);
   if(occupied_units > 3)
     {
      ++admission_topology_unit_blocks;
      ++admission_topology_post_placement_blocks;
      return(false);
     }
   if(actual_stop_risk > actual_stop_risk_cap + 0.01)
     {
      ++admission_topology_stop_risk_blocks;
      ++admission_topology_post_placement_blocks;
      return(false);
     }

   ++admission_topology_post_placement_confirmations;
   RecordEvent(US100_PASSIVE_LIMIT,
               "RISK_UNIT_POST_PLACEMENT_CONFIRM",
               actual_stop_risk,
               (double)occupied_units,
               StringFormat("actual_cap=%.4f nominal_before=%.4f nominal_pending=%.4f nominal_after=%.4f",
                            actual_stop_risk_cap,
                            aggregate_before,
                            pending_planned_risk,
                            aggregate_before + pending_planned_risk));
   return(true);
  }


void AdmissionTopologyReport()
  {
   PrintFormat("ZETA_FRONTIER_ADMISSION_TOPOLOGY_SUMMARY|checks=%I64d|overrides=%I64d|unit_blocks=%I64d|stop_risk_blocks=%I64d|read_failures=%I64d|post_placement_checks=%I64d|post_placement_confirmations=%I64d|post_placement_blocks=%I64d|max_units_after=%d|max_actual_stop_risk_after=%.10f",
               admission_topology_checks,
               admission_topology_overrides,
               admission_topology_unit_blocks,
               admission_topology_stop_risk_blocks,
               admission_topology_read_failures,
               admission_topology_post_placement_checks,
               admission_topology_post_placement_confirmations,
               admission_topology_post_placement_blocks,
               admission_topology_maximum_units_after,
               admission_topology_maximum_actual_stop_risk_after);
  }

#endif
