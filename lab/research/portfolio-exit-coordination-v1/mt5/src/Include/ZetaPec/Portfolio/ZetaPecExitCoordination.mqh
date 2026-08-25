#ifndef ZETA_PEC_EXIT_COORDINATION_MQH
#define ZETA_PEC_EXIT_COORDINATION_MQH

const int PEC_CONTROL = 0;
const int PEC_FIRST_NATURAL_EXIT_POSITIVE_COHORT = 1;
const int PEC_ALL_GREEN_ZERO_FLOOR = 2;
const int PEC_ALL_GREEN_QUARTER_R_HALF_PEAK = 3;
const double PEC_TRAIL_ACTIVATION_R = 0.25;
const double PEC_TRAIL_RETAINED_PEAK = 0.50;

struct PecPortfolioSnapshot
  {
   int mask;
   int count;
   double aggregate_profit;
   double planned_risk;
   bool all_positive;
   int components[COMPONENT_COUNT];
   ulong tickets[COMPONENT_COUNT];
  };

int pec_active_mask = 0;
bool pec_armed = false;
double pec_peak_profit = 0.0;
long pec_group_changes = 0;
long pec_arm_events = 0;
long pec_trigger_events = 0;
long pec_requested_closes = 0;
long pec_successful_closes = 0;
long pec_close_failures = 0;
long pec_continuous_dispatches = 0;


void PecResetGroupState(const int mask)
  {
   if(mask != pec_active_mask)
      ++pec_group_changes;
   pec_active_mask = mask;
   pec_armed = false;
   pec_peak_profit = 0.0;
  }


bool PecBuildPortfolioSnapshot(PecPortfolioSnapshot &snapshot)
  {
   snapshot.mask = 0;
   snapshot.count = 0;
   snapshot.aggregate_profit = 0.0;
   snapshot.planned_risk = 0.0;
   snapshot.all_positive = true;
   ArrayInitialize(snapshot.components, -1);
   ArrayInitialize(snapshot.tickets, 0);

   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int count = CountOwnedPositions(component, ticket, opened_at);
      if(count > 1)
         return(false);
      if(count != 1)
         continue;
      if(!PositionSelectByTicket(ticket))
         return(false);
      const double profit = PositionGetDouble(POSITION_PROFIT);
      snapshot.components[snapshot.count] = component;
      snapshot.tickets[snapshot.count] = ticket;
      ++snapshot.count;
      snapshot.mask |= (1 << component);
      snapshot.aggregate_profit += profit;
      snapshot.planned_risk +=
         MathMax(0.0, component_states[component].entry_planned_risk_usd);
      if(profit <= 0.0)
         snapshot.all_positive = false;
     }
   if(snapshot.count == 0)
      snapshot.all_positive = false;
   return(true);
  }


string PecSnapshotDetail(const PecPortfolioSnapshot &snapshot,
                         const double peak)
  {
   return(StringFormat("policy=%s|mask=%d|count=%d|risk=%.4f|peak=%.4f",
                       PEC_POLICY_LABEL,
                       snapshot.mask,
                       snapshot.count,
                       snapshot.planned_risk,
                       peak));
  }


void PecRecordArm(const PecPortfolioSnapshot &snapshot)
  {
   ++pec_arm_events;
   RecordEvent(-1,
               "PEC_ARM",
               snapshot.aggregate_profit,
               snapshot.planned_risk,
               PecSnapshotDetail(snapshot, pec_peak_profit));
  }


bool PecCloseSnapshot(const PecPortfolioSnapshot &snapshot,
                      const string trigger)
  {
   ++pec_trigger_events;
   pec_requested_closes += snapshot.count;
   RecordEvent(-1,
               trigger,
               snapshot.aggregate_profit,
               snapshot.planned_risk,
               PecSnapshotDetail(snapshot, pec_peak_profit));
   bool all_closed = true;
   for(int index = 0; index < snapshot.count; ++index)
     {
      const int component = snapshot.components[index];
      const ulong ticket = snapshot.tickets[index];
      if(component < 0 || ticket == 0 ||
         !CloseComponent(component, ticket))
        {
         ++pec_close_failures;
         all_closed = false;
        }
      else
         ++pec_successful_closes;
     }
   PecResetGroupState(0);
   if(!all_closed)
      EngageSafetyStop("PEC coordinated close failed");
   return(all_closed);
  }


bool PecNaturalClose(const int component, const ulong ticket)
  {
   if(PEC_POLICY_KIND != PEC_FIRST_NATURAL_EXIT_POSITIVE_COHORT)
      return(CloseComponent(component, ticket));

   PecPortfolioSnapshot snapshot = {};
   if(!PecBuildPortfolioSnapshot(snapshot))
     {
      EngageSafetyStop("PEC natural-exit snapshot failed");
      return(false);
     }
   if(snapshot.count >= 2 &&
      (snapshot.mask & (1 << component)) != 0 &&
      snapshot.aggregate_profit > 0.0)
      return(PecCloseSnapshot(snapshot, "PEC_FIRST_EXIT_TRIGGER"));
   return(CloseComponent(component, ticket));
  }


bool PecTesterContinuousDispatchRequired()
  {
   if(PEC_POLICY_KIND != PEC_ALL_GREEN_ZERO_FLOOR &&
      PEC_POLICY_KIND != PEC_ALL_GREEN_QUARTER_R_HALF_PEAK)
      return(false);
   int tracked = 0;
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_states[component].position_identifier > 0)
         ++tracked;
   return(tracked >= 2);
  }


bool PecProcessContinuousExit()
  {
   if(PEC_POLICY_KIND != PEC_ALL_GREEN_ZERO_FLOOR &&
      PEC_POLICY_KIND != PEC_ALL_GREEN_QUARTER_R_HALF_PEAK)
      return(false);
   ++pec_continuous_dispatches;
   PecPortfolioSnapshot snapshot = {};
   if(!PecBuildPortfolioSnapshot(snapshot))
     {
      EngageSafetyStop("PEC continuous snapshot failed");
      return(false);
     }
   if(snapshot.count < 2)
     {
      PecResetGroupState(0);
      return(false);
     }
   if(snapshot.mask != pec_active_mask)
      PecResetGroupState(snapshot.mask);

   if(!pec_armed)
     {
      if(PEC_POLICY_KIND == PEC_ALL_GREEN_ZERO_FLOOR &&
         snapshot.all_positive)
        {
         pec_armed = true;
         pec_peak_profit = snapshot.aggregate_profit;
         PecRecordArm(snapshot);
        }
      else if(PEC_POLICY_KIND == PEC_ALL_GREEN_QUARTER_R_HALF_PEAK &&
              snapshot.all_positive && snapshot.planned_risk > 0.0 &&
              snapshot.aggregate_profit >=
                 PEC_TRAIL_ACTIVATION_R * snapshot.planned_risk)
        {
         pec_armed = true;
         pec_peak_profit = snapshot.aggregate_profit;
         PecRecordArm(snapshot);
        }
      return(false);
     }

   pec_peak_profit = MathMax(pec_peak_profit, snapshot.aggregate_profit);
   if(PEC_POLICY_KIND == PEC_ALL_GREEN_ZERO_FLOOR &&
      snapshot.aggregate_profit <= 0.0)
      return(PecCloseSnapshot(snapshot, "PEC_ZERO_FLOOR_TRIGGER"));
   if(PEC_POLICY_KIND == PEC_ALL_GREEN_QUARTER_R_HALF_PEAK &&
      snapshot.aggregate_profit <=
         PEC_TRAIL_RETAINED_PEAK * pec_peak_profit)
      return(PecCloseSnapshot(snapshot, "PEC_HALF_PEAK_TRIGGER"));
   return(false);
  }


void PecPrintFinalTelemetry()
  {
   PrintFormat("%s PEC_FINAL policy=%s group_changes=%I64d arms=%I64d "
               "triggers=%I64d requested_closes=%I64d successful_closes=%I64d "
               "close_failures=%I64d continuous_dispatches=%I64d "
               "active_mask=%d armed=%s peak=%.4f",
               EXECUTION_VERSION,
               PEC_POLICY_LABEL,
               pec_group_changes,
               pec_arm_events,
               pec_trigger_events,
               pec_requested_closes,
               pec_successful_closes,
               pec_close_failures,
               pec_continuous_dispatches,
               pec_active_mask,
               (pec_armed ? "true" : "false"),
               pec_peak_profit);
  }

#endif
