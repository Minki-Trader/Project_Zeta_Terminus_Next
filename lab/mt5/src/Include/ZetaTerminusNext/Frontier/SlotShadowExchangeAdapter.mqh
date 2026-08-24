#ifndef ZETA_NEXT_FRONTIER_SLOT_SHADOW_EXCHANGE_ADAPTER_MQH
#define ZETA_NEXT_FRONTIER_SLOT_SHADOW_EXCHANGE_ADAPTER_MQH

#define SLOT_SHADOW_QUALITY_WINDOW 32

double slot_shadow_quality[COMPONENT_COUNT][SLOT_SHADOW_QUALITY_WINDOW];
int slot_shadow_quality_count[COMPONENT_COUNT];
int slot_shadow_quality_cursor[COMPONENT_COUNT];
ulong slot_shadow_exit_identifier[COMPONENT_COUNT];
double slot_shadow_exit_stressed[COMPONENT_COUNT];
double slot_shadow_exit_initial_risk[COMPONENT_COUNT];
long slot_shadow_signals = 0;
long slot_shadow_completed_lifecycles = 0;
long slot_shadow_risk_blocks = 0;
long slot_shadow_qualified_exchanges = 0;
long slot_shadow_release_successes = 0;
long slot_shadow_release_failures = 0;
long slot_shadow_retry_blocks = 0;
long slot_shadow_headroom_blocks = 0;
long slot_shadow_pending_candidate_blocks = 0;
datetime slot_shadow_last_release_server = 0;
int slot_shadow_last_release_component = -1;


string SlotShadowExchangeModeName()
  {
   if(InpSlotShadowExchangeMode == SLOT_SHADOW_RECEIVER_WOUNDED)
      return("receiver-wounded");
   if(InpSlotShadowExchangeMode == SLOT_SHADOW_MATURE_WOUNDED)
      return("mature-wounded");
   return("loser-residual");
  }


void SlotShadowExchangePushQuality(const int component,
                                   const double stressed_r)
  {
   if(component < 0 || component >= COMPONENT_COUNT ||
      !MathIsValidNumber(stressed_r))
      return;
   const double bounded = MathMax(-3.0, MathMin(3.0, stressed_r));
   if(slot_shadow_quality_count[component] < SLOT_SHADOW_QUALITY_WINDOW)
     {
      slot_shadow_quality[component][slot_shadow_quality_count[component]] =
         bounded;
      ++slot_shadow_quality_count[component];
      if(slot_shadow_quality_count[component] == SLOT_SHADOW_QUALITY_WINDOW)
         slot_shadow_quality_cursor[component] = 0;
      return;
     }
   slot_shadow_quality[component][slot_shadow_quality_cursor[component]] =
      bounded;
   slot_shadow_quality_cursor[component] =
      (slot_shadow_quality_cursor[component] + 1) %
      SLOT_SHADOW_QUALITY_WINDOW;
  }


void SlotShadowExchangeSeedComponent(const int component,
                                     const double &values[])
  {
   for(int index = 0; index < ArraySize(values); ++index)
      SlotShadowExchangePushQuality(component, values[index]);
  }


void SlotShadowExchangeSeedQuality()
  {
   double rc16[] =
     {
      -0.503371,-0.506886,0.564711,0.257010,0.515761,0.366075,
      0.001717,-0.360310,-0.200184,0.293297,-0.268262,0.624210,
      -0.142909,0.036643,0.197072,0.339646,-0.320338,-0.086143,
      0.259055,0.161677,0.714485,0.361057,-0.092426,-0.188584,
      -0.100051,0.312100,0.059390,-0.003798,0.058862,-0.000651,
      0.075764,-0.503017
     };
   double rc4[] =
     {
      -0.140115,0.130129,0.414304,-0.504885,0.125336,-0.522176,
      -0.129618,0.156958,0.605488,0.429936,0.128665,-0.503283,
      -0.061877,-0.093033,-0.127115,0.735405,-0.276051,-0.332195,
      0.794044,-0.190531,-0.408343,-0.131741,-0.085869,0.410080,
      0.152228,-0.194544,0.214073,-0.128122,0.004213,-0.207475,
      -0.126775,0.693611
     };
   double cross[] =
     {
      0.240325,-0.024586,0.028157,0.320775,0.103849,-0.017765,
      -0.097726,-0.208101,0.449999,0.385840,0.037207,-0.309666,
      0.007781,0.145517,-0.024184,0.074141,0.084778,0.042088,
      -0.100739,0.021742,0.075871,-0.152138,-0.153068,0.149266,
      -0.175045,0.234737,-0.032681,-0.502527,0.182705,-0.102397,
      0.054219,0.342127
     };
   double pressure[] =
     {
      -0.503044,-0.508139,-0.505085,0.328212,-0.162071,-0.523380,
      0.514418,0.355570,-0.482716,0.840287,-0.180004,-0.100363,
      -0.502867,0.485075,-0.149289,0.438824,0.025620,0.390425,
      0.034832,0.012356,-0.160815,0.047590,0.086157
     };
   double return_reversal[] =
     {
      -0.506371,-0.399601,0.453941,-0.503684,0.440169,1.063404,
      0.341992,-0.152797,0.759628,-0.504016,0.259899,0.318139,
      0.671957,-0.505068,0.148963,0.527007,0.192693,-0.503688,
      -0.502880,-0.502348,0.212267,-0.507308,-0.504140,0.192154,
      0.184884,0.567867,0.339851,-0.207020,0.150522,-0.191395,
      -0.273173,0.167396
     };
   double passive[] =
     {
      0.231075,0.056737,-0.043418,0.026991,0.102894,-0.121669,
      -0.175151,0.063026,0.105528,-0.047421,0.259540,0.027200,
      0.046362,0.011482,0.189273,0.025161,0.054403,0.078335,
      0.276741,0.152520,-0.021009,0.015192,0.004138,-0.412787,
      0.023481,-0.085246,0.072130,0.034832,0.035118,-0.000652,
      -0.072868,-0.020301
     };
   SlotShadowExchangeSeedComponent(RC16_LONG, rc16);
   SlotShadowExchangeSeedComponent(RC4_BOTH, rc4);
   SlotShadowExchangeSeedComponent(US100_CROSS, cross);
   SlotShadowExchangeSeedComponent(US30_PRESSURE, pressure);
   SlotShadowExchangeSeedComponent(US30_RETURN_REV_LONG, return_reversal);
   SlotShadowExchangeSeedComponent(US100_PASSIVE_LIMIT, passive);
  }


double SlotShadowExchangeQuality(const int component)
  {
   if(component < 0 || component >= COMPONENT_COUNT ||
      slot_shadow_quality_count[component] <= 0)
      return(0.0);
   double sum = 0.0;
   for(int index = 0; index < slot_shadow_quality_count[component]; ++index)
      sum += slot_shadow_quality[component][index];
   return(sum / (double)slot_shadow_quality_count[component]);
  }


bool SlotShadowExchangeInitialize()
  {
   if(InpSlotShadowExchangeMode < SLOT_SHADOW_RECEIVER_WOUNDED ||
      InpSlotShadowExchangeMode > SLOT_SHADOW_LOSER_RESIDUAL)
      return(false);
   FolderCreate("ZetaTerminusNext\\frontier");
   return(true);
  }


void SlotShadowExchangeReset()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      slot_shadow_quality_count[component] = 0;
      slot_shadow_quality_cursor[component] = 0;
      slot_shadow_exit_identifier[component] = 0;
      slot_shadow_exit_stressed[component] = 0.0;
      slot_shadow_exit_initial_risk[component] = 0.0;
      for(int index = 0; index < SLOT_SHADOW_QUALITY_WINDOW; ++index)
         slot_shadow_quality[component][index] = 0.0;
     }
   slot_shadow_signals = 0;
   slot_shadow_completed_lifecycles = 0;
   slot_shadow_risk_blocks = 0;
   slot_shadow_qualified_exchanges = 0;
   slot_shadow_release_successes = 0;
   slot_shadow_release_failures = 0;
   slot_shadow_retry_blocks = 0;
   slot_shadow_headroom_blocks = 0;
   slot_shadow_pending_candidate_blocks = 0;
   slot_shadow_last_release_server = 0;
   slot_shadow_last_release_component = -1;
   SlotShadowExchangeSeedQuality();
  }


void SlotShadowExchangeObserveSignal(const int component,
                                     const double value,
                                     const bool passed,
                                     const int direction)
  {
   if(passed && direction != 0)
      ++slot_shadow_signals;
  }


void SlotShadowExchangeObserveExit(const int component,
                                   const ulong identifier,
                                   const double stressed_net,
                                   const double admitted_planned_risk,
                                   const bool completed)
  {
   if(component < 0 || component >= COMPONENT_COUNT || identifier == 0)
      return;
   if(slot_shadow_exit_identifier[component] != identifier)
     {
      slot_shadow_exit_identifier[component] = identifier;
      slot_shadow_exit_stressed[component] = 0.0;
      slot_shadow_exit_initial_risk[component] = admitted_planned_risk;
     }
   slot_shadow_exit_stressed[component] += stressed_net;
   if(slot_shadow_exit_initial_risk[component] <= 0.0)
      slot_shadow_exit_initial_risk[component] = admitted_planned_risk;
   if(!completed)
      return;
   const double initial_risk = slot_shadow_exit_initial_risk[component];
   const double stressed_r =
      (initial_risk > 0.0
       ? slot_shadow_exit_stressed[component] / initial_risk
       : 0.0);
   SlotShadowExchangePushQuality(component, stressed_r);
   ++slot_shadow_completed_lifecycles;
   PrintFormat("ZETA_FRONTIER_SLOT_QUALITY|server=%I64d|component=%d|identifier=%I64u|stressed_r=%.10f|rolling_mean=%.10f|count=%d",
               (long)TimeCurrent(),
               component,
               identifier,
               stressed_r,
               SlotShadowExchangeQuality(component),
               slot_shadow_quality_count[component]);
   slot_shadow_exit_identifier[component] = 0;
   slot_shadow_exit_stressed[component] = 0.0;
   slot_shadow_exit_initial_risk[component] = 0.0;
  }


int SlotShadowExchangeEffectiveHoldBars(const int component,
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


double SlotShadowExchangeCandidateScore(const int component)
  {
   double score = SlotShadowExchangeQuality(component);
   if(InpSlotShadowExchangeMode == SLOT_SHADOW_RECEIVER_WOUNDED &&
      (component == US100_CROSS ||
       component == US30_RETURN_REV_LONG) &&
      time_field_qualified[component])
      score += 0.5;
   return(score);
  }


double SlotShadowExchangePrice(const int component,
                               const double floating_r,
                               const double remaining_fraction)
  {
   const double mean_r = SlotShadowExchangeQuality(component);
   if(InpSlotShadowExchangeMode == SLOT_SHADOW_LOSER_RESIDUAL)
      return(mean_r * remaining_fraction);
   return(floating_r +
          MathMax(0.0, mean_r) * remaining_fraction -
          MathMax(0.0, -floating_r) * (1.0 - remaining_fraction));
  }


bool SlotShadowExchangeTryRelease(const int component,
                                  const string symbol,
                                  const int direction,
                                  const double volume,
                                  const double entry_price,
                                  const double position_budget,
                                  const double aggregate_after,
                                  const double aggregate_budget)
  {
   ++slot_shadow_risk_blocks;
   const datetime server = TimeCurrent();
   if(slot_shadow_last_release_server == server &&
      slot_shadow_last_release_component == component)
     {
      ++slot_shadow_retry_blocks;
      return(false);
     }
   if(component < 0 || component >= COMPONENT_COUNT ||
      component_states[component].entry_check_signal_passed != 1 ||
      direction == 0 || volume <= 0.0 || entry_price <= 0.0)
      return(false);
   if(component == US100_PASSIVE_LIMIT)
     {
      ++slot_shadow_pending_candidate_blocks;
      return(false);
     }
   if(component != US100_PASSIVE_LIMIT &&
      (!TradeSessionAllows(symbol, server, true) ||
       !MarginAllows(symbol, direction, volume)))
      return(false);

   const double candidate_score = SlotShadowExchangeCandidateScore(component);
   const double candidate_floor = -0.25;
   double margin = 0.5;
   double age_floor = 0.0;
   double floating_ceiling = 999.0;
   if(InpSlotShadowExchangeMode == SLOT_SHADOW_MATURE_WOUNDED)
     {
      margin = 0.25;
      age_floor = 0.5;
     }
   else if(InpSlotShadowExchangeMode == SLOT_SHADOW_LOSER_RESIDUAL)
     {
      margin = -0.25;
      age_floor = 0.25;
      floating_ceiling = 0.0;
     }
   if(candidate_score < candidate_floor)
      return(false);

   const double required_release =
      MathMax(0.0, aggregate_after - aggregate_budget);
   const double required_release_with_headroom =
      required_release + MathMax(0.05, position_budget * 0.05);
   int selected_component = -1;
   ulong selected_ticket = 0;
   double selected_price = DBL_MAX;
   double selected_planned_risk = 0.0;
   double selected_floating_r = 0.0;
   double selected_remaining = 0.0;
   int selected_held_bars = 0;
   for(int incumbent = 0; incumbent < COMPONENT_COUNT; ++incumbent)
     {
      if(incumbent == component)
         continue;
      ulong ticket = 0;
      datetime opened_at = 0;
      if(CountOwnedPositions(incumbent, ticket, opened_at) != 1 ||
         ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      const double planned_risk =
         component_states[incumbent].entry_planned_risk_usd;
      if(planned_risk + 0.01 < required_release_with_headroom)
        {
         if(planned_risk + 0.01 >= required_release)
            ++slot_shadow_headroom_blocks;
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
         SlotShadowExchangeEffectiveHoldBars(incumbent, identifier);
      if(held_bars < 0 || effective_hold_bars <= 0)
         continue;
      const double remaining =
         MathMax(0.0,
                 MathMin(1.0,
                         1.0 -
                         (double)held_bars / (double)effective_hold_bars));
      const double age = 1.0 - remaining;
      const double floating_profit =
         PositionGetDouble(POSITION_PROFIT) +
         PositionGetDouble(POSITION_SWAP);
      const double floating_r =
         (planned_risk > 0.0 ? floating_profit / planned_risk : 0.0);
      if(floating_r > floating_ceiling || age < age_floor)
         continue;
      const double price =
         SlotShadowExchangePrice(incumbent, floating_r, remaining);
      if(selected_component < 0 || price < selected_price)
        {
         selected_component = incumbent;
         selected_ticket = ticket;
         selected_price = price;
         selected_planned_risk = planned_risk;
         selected_floating_r = floating_r;
         selected_remaining = remaining;
         selected_held_bars = held_bars;
        }
     }
   if(selected_component < 0 || candidate_score - selected_price < margin)
      return(false);

   ++slot_shadow_qualified_exchanges;
   RecordEvent(component,
               "SLOT_EXCHANGE_INTENT",
               candidate_score,
               selected_price,
               StringFormat("mode=%s incumbent=%d ticket=%I64u required=%.4f release=%.4f floating_r=%.6f remaining=%.6f held_bars=%d",
                            SlotShadowExchangeModeName(),
                            selected_component,
                            selected_ticket,
                            required_release,
                            selected_planned_risk,
                            selected_floating_r,
                            selected_remaining,
                            selected_held_bars));
   const bool released =
      CloseComponent(selected_component, selected_ticket);
   if(!released)
     {
      ++slot_shadow_release_failures;
      RecordEvent(component,
                  "SLOT_EXCHANGE_FAIL",
                  candidate_score,
                  selected_price,
                  IntegerToString(selected_component));
      return(false);
     }
   ++slot_shadow_release_successes;
   slot_shadow_last_release_server = server;
   slot_shadow_last_release_component = component;
   RecordEvent(component,
               "SLOT_EXCHANGE_RELEASE",
               candidate_score,
               selected_price,
               StringFormat("mode=%s incumbent=%d required=%.4f released=%.4f position_budget=%.4f",
                            SlotShadowExchangeModeName(),
                            selected_component,
                            required_release,
                            selected_planned_risk,
                            position_budget));
   PrintFormat("ZETA_FRONTIER_SLOT_EXCHANGE|server=%I64d|mode=%s|candidate=%d|candidate_score=%.10f|incumbent=%d|slot_price=%.10f|required=%.10f|released=%.10f|floating_r=%.10f|remaining=%.10f|held_bars=%d",
               (long)server,
               SlotShadowExchangeModeName(),
               component,
               candidate_score,
               selected_component,
               selected_price,
               required_release,
               selected_planned_risk,
               selected_floating_r,
               selected_remaining,
               selected_held_bars);
   return(true);
  }


void SlotShadowExchangeReport()
  {
   PrintFormat("ZETA_FRONTIER_SLOT_EXCHANGE_SUMMARY|mode=%s|signals=%I64d|completed_lifecycles=%I64d|risk_blocks=%I64d|qualified=%I64d|release_successes=%I64d|release_failures=%I64d|retry_blocks=%I64d|headroom_blocks=%I64d|pending_candidate_blocks=%I64d",
               SlotShadowExchangeModeName(),
               slot_shadow_signals,
               slot_shadow_completed_lifecycles,
               slot_shadow_risk_blocks,
               slot_shadow_qualified_exchanges,
               slot_shadow_release_successes,
               slot_shadow_release_failures,
               slot_shadow_retry_blocks,
               slot_shadow_headroom_blocks,
               slot_shadow_pending_candidate_blocks);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      PrintFormat("ZETA_FRONTIER_SLOT_EXCHANGE_COMPONENT|mode=%s|component=%d|quality_count=%d|quality_mean=%.10f",
                  SlotShadowExchangeModeName(),
                  component,
                  slot_shadow_quality_count[component],
                  SlotShadowExchangeQuality(component));
  }

#endif
