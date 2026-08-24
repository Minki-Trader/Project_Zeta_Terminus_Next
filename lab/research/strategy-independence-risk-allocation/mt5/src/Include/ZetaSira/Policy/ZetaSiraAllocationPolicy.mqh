#ifndef ZETA_SIRA_ALLOCATION_POLICY_MQH
#define ZETA_SIRA_ALLOCATION_POLICY_MQH

// Constants are frozen from STRATEGY_INDEPENDENCE_RISK_ALLOCATION_FIT_V1.
const int SIRA_POLICY_FIRST_COME = 0;
const int SIRA_POLICY_WIN_PROBABILITY = 1;
const int SIRA_POLICY_CONSERVATIVE_R = 2;
const int SIRA_POLICY_OVERLAP_AWARE = 3;

const double SIRA_FIT_WIN_PROBABILITY[COMPONENT_COUNT] =
  {
   0.6075949367088608,
   0.5454545454545454,
   0.5389610389610390,
   0.4594594594594595,
   0.5555555555555556,
   0.6325581395348837
  };

const double SIRA_FIT_CONSERVATIVE_R[COMPONENT_COUNT] =
  {
    0.04719169202466941,
    0.01471541825381822,
   -0.00092947266286211,
   -0.05365755557196825,
    0.01717133979739545,
   -0.00675524228591550
  };

const double SIRA_FIT_OVERLAP_ADJUSTMENT[COMPONENT_COUNT][COMPONENT_COUNT] =
  {
   { 0.0, -0.00252080075895698,  0.0,  0.0,  0.0, -0.02410169071402679 },
   { 0.0,  0.0,  0.0,  0.0,  0.0,  0.04835859598570523 },
   {-0.00529892641564204, -0.02034011241908741,  0.0, -0.02458125828454629,  0.02480187952505701,  0.00970895292996045 },
   { 0.04799139792738248,  0.03911438386669482,  0.0,  0.0,  0.0,  0.00845141784976615 },
   {-0.03970016888784907, -0.00938289004027436,  0.0, -0.01889547652620349,  0.0,  0.00240169051995083 },
   {-0.03219876195192593,  0.00829228759374356,  0.0,  0.02339448340683201, -0.01110726251058709,  0.0 }
  };


string SiraPolicyName()
  {
   if(SIRA_POLICY_MODE == SIRA_POLICY_WIN_PROBABILITY)
      return("WIN_PROB_RESERVE_ONE");
   if(SIRA_POLICY_MODE == SIRA_POLICY_CONSERVATIVE_R)
      return("CONSERVATIVE_R_RESERVE_ONE");
   if(SIRA_POLICY_MODE == SIRA_POLICY_OVERLAP_AWARE)
      return("OVERLAP_AWARE_RESERVE_ONE");
   return("FIRST_COME");
  }


int SiraPolicyActiveMask()
  {
   int mask = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_states[component].position_identifier > 0)
         mask |= (1 << component);
   if(execution_state.passive_pending_order > 0)
      mask |= (1 << US100_PASSIVE_LIMIT);
   return(mask);
  }


double SiraPolicyScore(const int component, const int active_mask)
  {
   if(SIRA_POLICY_MODE == SIRA_POLICY_WIN_PROBABILITY)
      return(SIRA_FIT_WIN_PROBABILITY[component]);
   double score = SIRA_FIT_CONSERVATIVE_R[component];
   if(SIRA_POLICY_MODE != SIRA_POLICY_OVERLAP_AWARE)
      return(score);
   bool adjustment_known = false;
   double minimum_adjustment = 0.0;
   for(int incumbent = 0; incumbent < COMPONENT_COUNT; ++incumbent)
     {
      if(incumbent == component ||
         (active_mask & (1 << incumbent)) == 0)
         continue;
      const double adjustment =
         SIRA_FIT_OVERLAP_ADJUSTMENT[component][incumbent];
      if(!adjustment_known || adjustment < minimum_adjustment)
        {
         minimum_adjustment = adjustment;
         adjustment_known = true;
        }
     }
   return(score + (adjustment_known ? minimum_adjustment : 0.0));
  }


int SiraPolicyEvaluationMinute(const int component)
  {
   if(component == RC4_BOTH)
      return(13 * 60);
   if(component == RC16_LONG)
      return(13 * 60 + 30);
   if(component == US30_PRESSURE)
      return(15 * 60);
   if(component == US30_RETURN_REV_LONG)
      return(16 * 60);
   if(component == US100_CROSS)
      return(17 * 60);
   return(-1);
  }


bool SiraPolicyHigherScoredLaterStrategy(const int component,
                                         const int active_mask,
                                         int &later_component,
                                         double &component_score,
                                         double &later_score)
  {
   later_component = -1;
   component_score = SiraPolicyScore(component, active_mask);
   later_score = component_score;
   MqlDateTime now = {};
   TimeToStruct(TimeCurrent(), now);
   const int current_minute = now.hour * 60 + now.min;
   for(int candidate = 0; candidate < COMPONENT_COUNT; ++candidate)
     {
      const int candidate_minute = SiraPolicyEvaluationMinute(candidate);
      if(candidate_minute <= current_minute ||
         (active_mask & (1 << candidate)) != 0)
         continue;
      const double candidate_score =
         SiraPolicyScore(candidate, active_mask);
      if(candidate_score > later_score + 1.0e-12)
        {
         later_component = candidate;
         later_score = candidate_score;
        }
     }
   return(later_component >= 0);
  }


bool SiraPolicyReservationAllows(const int component,
                                 const double capital,
                                 const double aggregate_after,
                                 const double aggregate_budget)
  {
   if(SIRA_POLICY_MODE == SIRA_POLICY_FIRST_COME)
      return(true);
   const double tolerance = 0.01;
   const double one_slot =
      capital * InpMaximumPositionRiskFraction;
   const double reservation_cap = aggregate_budget - one_slot;
   if(aggregate_after <= reservation_cap + tolerance ||
      aggregate_after > aggregate_budget + tolerance)
      return(true);
   const int active_mask = SiraPolicyActiveMask();
   int later_component = -1;
   double component_score = 0.0;
   double later_score = 0.0;
   if(!SiraPolicyHigherScoredLaterStrategy(component,
                                           active_mask,
                                           later_component,
                                           component_score,
                                           later_score))
      return(true);
   ++sira_policy_reservation_skips;
   ++risk_admission_skips;
   RecordEvent(component,
               "SIRA_POLICY_RESERVE_SKIP",
               aggregate_after,
               reservation_cap,
               StringFormat("policy=%s current_score=%.10f later_component=%s later_score=%.10f active_mask=%d hard_cap=%.4f",
                            SiraPolicyName(),
                            component_score,
                            component_definitions[later_component].id,
                            later_score,
                            active_mask,
                            aggregate_budget));
   return(false);
  }


#endif
