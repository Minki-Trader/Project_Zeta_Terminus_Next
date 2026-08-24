#ifndef ZETA_NEXT_FRONTIER_SLOT_SHADOW_TAPE_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_SLOT_SHADOW_TAPE_ADAPTER_MQH

long slot_shadow_candidate_count = 0;
long slot_shadow_incumbent_snapshots = 0;
long slot_shadow_pending_snapshots = 0;
long slot_shadow_position_read_failures = 0;


bool SlotShadowTapeInitialize()
  {
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void SlotShadowTapeReset()
  {
   slot_shadow_candidate_count = 0;
   slot_shadow_incumbent_snapshots = 0;
   slot_shadow_pending_snapshots = 0;
   slot_shadow_position_read_failures = 0;
  }


int SlotShadowTapeEffectiveHoldBars(const int component,
                                    const ulong identifier)
  {
   int hold_bars = component_definitions[component].hold_bars;
   if(component == US30_RETURN_REV_LONG &&
      ReceiverTimeFieldCurrentLifecycle(component))
      hold_bars = 3;
   else if(component == US100_CROSS &&
           ReceiverTimeFieldCurrentLifecycle(component) &&
           time_field_cross_gate_identifier == identifier &&
           time_field_cross_gate_decided &&
           time_field_cross_gate_extended)
      hold_bars = 6;
   return(hold_bars);
  }


void SlotShadowTapeObserveSignal(const int component,
                                 const double value,
                                 const bool passed,
                                 const int direction)
  {
   if(!passed || direction == 0 || component < 0 ||
      component >= COMPONENT_COUNT)
      return;

   const long candidate_id = ++slot_shadow_candidate_count;
   const datetime server = TimeCurrent();
   const double aggregate_risk = TrackedAggregatePlannedRisk();
   const double risk_capital = ConservativeRiskCapital();
   const bool receiver_qualified =
      ((component == US100_CROSS || component == US30_RETURN_REV_LONG) &&
       time_field_qualified[component]);
   int active_positions = 0;
   for(int incumbent = 0; incumbent < COMPONENT_COUNT; ++incumbent)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int owned = CountOwnedPositions(incumbent, ticket, opened_at);
      if(owned == 1)
         ++active_positions;
     }
   const bool pending_passive =
      (execution_state.passive_pending_order != 0);
   PrintFormat("ZETA_FRONTIER_SLOT_CANDIDATE|id=%I64d|server=%I64d|component=%d|direction=%d|signal=%.10f|receiver_qualified=%d|active_positions=%d|pending_passive=%d|aggregate_risk=%.10f|risk_capital=%.10f|equity=%.10f|margin=%.10f",
               candidate_id,
               (long)server,
               component,
               direction,
               value,
               (int)receiver_qualified,
               active_positions,
               (int)pending_passive,
               aggregate_risk,
               risk_capital,
               AccountInfoDouble(ACCOUNT_EQUITY),
               AccountInfoDouble(ACCOUNT_MARGIN));

   for(int incumbent = 0; incumbent < COMPONENT_COUNT; ++incumbent)
     {
      ulong ticket = 0;
      datetime opened_at = 0;
      const int owned = CountOwnedPositions(incumbent, ticket, opened_at);
      if(owned == 0)
         continue;
      if(owned != 1 || ticket == 0 || !PositionSelectByTicket(ticket))
        {
         ++slot_shadow_position_read_failures;
         PrintFormat("ZETA_FRONTIER_SLOT_READ_FAILURE|candidate_id=%I64d|server=%I64d|component=%d|owned=%d|ticket=%I64u",
                     candidate_id,
                     (long)server,
                     incumbent,
                     owned,
                     ticket);
         continue;
        }
      const ulong identifier =
         (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      const int held_bars =
         iBarShift(component_definitions[incumbent].symbol,
                   component_definitions[incumbent].timeframe,
                   opened_at,
                   false);
      const int effective_hold_bars =
         SlotShadowTapeEffectiveHoldBars(incumbent, identifier);
      const double planned_risk =
         component_states[incumbent].entry_planned_risk_usd;
      const double floating_profit =
         PositionGetDouble(POSITION_PROFIT) +
         PositionGetDouble(POSITION_SWAP);
      const double floating_r =
         (planned_risk > 0.0 ? floating_profit / planned_risk : 0.0);
      ++slot_shadow_incumbent_snapshots;
      PrintFormat("ZETA_FRONTIER_SLOT_INCUMBENT|candidate_id=%I64d|server=%I64d|candidate_component=%d|component=%d|state=POSITION|identifier=%I64u|ticket=%I64u|direction=%d|opened=%I64d|age_seconds=%I64d|held_bars=%d|effective_hold_bars=%d|entry=%.10f|mark=%.10f|stop=%.10f|volume=%.10f|planned_risk=%.10f|floating_profit=%.10f|floating_r=%.10f",
                  candidate_id,
                  (long)server,
                  component,
                  incumbent,
                  identifier,
                  ticket,
                  component_states[incumbent].entry_direction,
                  (long)opened_at,
                  (long)server - (long)opened_at,
                  held_bars,
                  effective_hold_bars,
                  PositionGetDouble(POSITION_PRICE_OPEN),
                  PositionGetDouble(POSITION_PRICE_CURRENT),
                  PositionGetDouble(POSITION_SL),
                  PositionGetDouble(POSITION_VOLUME),
                  planned_risk,
                  floating_profit,
                  floating_r);
     }

   if(pending_passive)
     {
      ++slot_shadow_pending_snapshots;
      PrintFormat("ZETA_FRONTIER_SLOT_INCUMBENT|candidate_id=%I64d|server=%I64d|candidate_component=%d|component=%d|state=PENDING|identifier=0|ticket=%I64u|direction=%d|opened=0|age_seconds=0|held_bars=0|effective_hold_bars=%d|entry=%.10f|mark=0.0000000000|stop=%.10f|volume=0.0000000000|planned_risk=%.10f|floating_profit=0.0000000000|floating_r=0.0000000000|expiration=%I64d|remaining_seconds=%I64d",
                  candidate_id,
                  (long)server,
                  component,
                  US100_PASSIVE_LIMIT,
                  execution_state.passive_pending_order,
                  passive_pending_direction,
                  PASSIVE_ACTIVATION_BARS,
                  passive_pending_limit_price,
                  passive_pending_stop_loss,
                  passive_pending_planned_risk_usd,
                  (long)passive_pending_expiration,
                  MathMax((long)0,
                          (long)passive_pending_expiration - (long)server));
     }
  }


void SlotShadowTapeReport()
  {
   PrintFormat("ZETA_FRONTIER_SLOT_TAPE_SUMMARY|candidates=%I64d|incumbent_snapshots=%I64d|pending_snapshots=%I64d|position_read_failures=%I64d",
               slot_shadow_candidate_count,
               slot_shadow_incumbent_snapshots,
               slot_shadow_pending_snapshots,
               slot_shadow_position_read_failures);
  }

#endif
