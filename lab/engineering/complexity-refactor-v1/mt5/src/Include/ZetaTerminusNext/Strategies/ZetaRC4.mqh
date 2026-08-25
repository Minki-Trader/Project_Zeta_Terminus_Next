#ifndef ZETA_NEXT_MODULE_04_MQH
#define ZETA_NEXT_MODULE_04_MQH

// Behavior-preserving function extraction from B70 V6R6: Strategies\ZetaRC4.mqh

void ClearArcLifecycleState()
  {
   arc_lifecycle_identifier = 0;
   arc_last_attempt_bar = 0;
   arc_checkpoint_evaluated = false;
   arc_lifecycle_compressed = false;
   arc_original_stop_loss = 0.0;
   execution_state.arc_modify_pending = false;
   arc_pending_stop_loss = 0.0;
   execution_state.arc_modify_retry_pending = false;
   arc_modify_retry_consumed = false;
   execution_state.arc_modify_retry_after_msc = 0;
   arc_modify_retry_initial_retcode = 0;
  }


void ClearRC4ShadowState()
  {
   execution_state.rc4_shadow_occupied = false;
   rc4_shadow_source_identifier = 0;
   rc4_shadow_entry_time = 0;
   rc4_shadow_direction = 0;
   rc4_shadow_original_stop_loss = 0.0;
   rc4_shadow_last_observed_msc = 0;
   rc4_shadow_cursor_ordinal = 0;
   rc4_shadow_catchup_required = false;
   rc4_shadow_catchup_failure_logged = false;
   rc4_shadow_cursor_checkpoint_observation_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
   rc4_shadow_cursor_checkpoint_pending = false;
   execution_state.rc4_shadow_activation_sealed = false;
   execution_state.rc4_shadow_activation_seal_pending = false;
   rc4_shadow_activation_seal_failure_logged = false;
   rc4_shadow_activation_deal_ticket = 0;
   rc4_shadow_activation_deal_time_msc = 0;
   rc4_shadow_activation_deal_price = 0.0;
   rc4_shadow_activation_deal_reason = 0;
   rc4_shadow_activation_protected_stop = 0.0;
   rc4_shadow_activation_sampled_tick_known = false;
   rc4_shadow_activation_sampled_time = 0;
   rc4_shadow_activation_sampled_time_msc = 0;
   rc4_shadow_activation_sampled_bid = 0.0;
   rc4_shadow_activation_sampled_ask = 0.0;
   rc4_shadow_activation_sampled_last = 0.0;
   rc4_shadow_activation_sampled_volume = 0;
   rc4_shadow_activation_sampled_volume_real = 0.0;
   rc4_shadow_activation_sampled_flags = 0;
   rc4_shadow_activation_boundary_msc = 0;
   rc4_shadow_activation_boundary_ordinal = 0;
  }


bool ArcOriginalStopReached(const int direction,
                            const double original_stop,
                            const MqlTick &tick)
  {
   if(MathAbs(direction) != 1 || original_stop <= 0.0 ||
      tick.bid <= 0.0 || tick.ask <= 0.0 || tick.ask < tick.bid)
      return(false);
   return(direction > 0
          ? tick.bid <= original_stop
          : tick.ask >= original_stop);
  }


bool SameRC4ShadowTick(const MqlTick &left,
                       const MqlTick &right)
  {
   return(left.time == right.time &&
          left.time_msc == right.time_msc &&
          left.bid == right.bid && left.ask == right.ask &&
          left.last == right.last && left.volume == right.volume &&
          left.volume_real == right.volume_real &&
          left.flags == right.flags);
  }


bool CatchUpRC4ShadowToTick(const MqlTick &current_tick,
                            bool &stop_release,
                            long &stop_time_msc)
  {
   stop_release = false;
   stop_time_msc = 0;
   const bool recovery_pending_before = rc4_shadow_catchup_required;
   const long from_msc = rc4_shadow_last_observed_msc;
   const long from_ordinal = rc4_shadow_cursor_ordinal;
   if(!execution_state.rc4_shadow_occupied || !execution_state.rc4_shadow_activation_sealed ||
      execution_state.rc4_shadow_activation_seal_pending ||
      rc4_shadow_activation_boundary_msc <= 0 ||
      rc4_shadow_activation_boundary_ordinal <= 0 ||
      from_msc <= 0 || from_ordinal < 0 ||
      current_tick.time_msc <= 0 || current_tick.time_msc < from_msc)
     {
      rc4_shadow_catchup_required = true;
      ++rc4_shadow_catchup_failures;
      if(!rc4_shadow_catchup_failure_logged)
        {
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_CATCHUP_FAILED",
                     (double)from_msc,
                     (double)current_tick.time_msc,
                     "invalid causal shadow tick range or ordinal");
         rc4_shadow_catchup_failure_logged = true;
        }
      return(false);
     }

   MqlTick ticks[];
   ResetLastError();
   const int copied =
      CopyTicksRange("US30",
                     ticks,
                     COPY_TICKS_ALL,
                     (ulong)from_msc,
                     (ulong)current_tick.time_msc);
   const int history_error = GetLastError();
   if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
     {
      rc4_shadow_catchup_required = true;
      ++rc4_shadow_catchup_failures;
      if(!rc4_shadow_catchup_failure_logged)
        {
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_CATCHUP_FAILED",
                     (double)from_msc,
                     (double)current_tick.time_msc,
                     StringFormat("incomplete CopyTicksRange copied=%d size=%d error=%d",
                                  copied,
                                  ArraySize(ticks),
                                  history_error));
         rc4_shadow_catchup_failure_logged = true;
        }
      return(false);
     }

   long prior_time_msc = from_msc;
   long seen_at_cursor = 0;
   long same_millisecond_ordinal = 0;
   long ordinal_millisecond = -1;
   long selected_ordinal = 0;
   int selected_index = -1;
   long processed_ticks = 0;
   for(int index = 0; index < copied; ++index)
     {
      const MqlTick recovered = ticks[index];
      if(recovered.time_msc < from_msc ||
         recovered.time_msc < prior_time_msc ||
         recovered.time_msc > current_tick.time_msc ||
         recovered.bid <= 0.0 || recovered.ask <= 0.0 ||
         recovered.ask < recovered.bid)
        {
         rc4_shadow_catchup_required = true;
         ++rc4_shadow_catchup_failures;
         if(!rc4_shadow_catchup_failure_logged)
           {
            RecordEvent(RC4_BOTH,
                        "ARC_SHADOW_CATCHUP_FAILED",
                        (double)recovered.time_msc,
                        (double)current_tick.time_msc,
                        "invalid or noncausal recovered tick");
            rc4_shadow_catchup_failure_logged = true;
           }
         return(false);
        }
      prior_time_msc = recovered.time_msc;
      if(recovered.time_msc != ordinal_millisecond)
        {
         ordinal_millisecond = recovered.time_msc;
         same_millisecond_ordinal = 1;
        }
      else
         ++same_millisecond_ordinal;
      if(recovered.time_msc == from_msc)
         ++seen_at_cursor;
      else if(seen_at_cursor < from_ordinal)
        {
         rc4_shadow_catchup_required = true;
         ++rc4_shadow_catchup_failures;
         if(!rc4_shadow_catchup_failure_logged)
           {
            RecordEvent(RC4_BOTH,
                        "ARC_SHADOW_CATCHUP_FAILED",
                        (double)seen_at_cursor,
                        (double)from_ordinal,
                        "persisted cursor ordinal is not reproducible");
            rc4_shadow_catchup_failure_logged = true;
           }
         return(false);
        }

      const bool already_observed =
         (recovered.time_msc == from_msc &&
          seen_at_cursor <= from_ordinal);
      if(already_observed)
         continue;
      const bool at_or_before_activation_boundary =
         (recovered.time_msc < rc4_shadow_activation_boundary_msc ||
          (recovered.time_msc == rc4_shadow_activation_boundary_msc &&
           same_millisecond_ordinal <=
              rc4_shadow_activation_boundary_ordinal));
      if(at_or_before_activation_boundary)
        {
         ++rc4_shadow_activation_pre_boundary_consumed;
         rc4_shadow_catchup_required = true;
         ++rc4_shadow_catchup_failures;
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_ACTIVATION_PRE_BOUNDARY_CONSUMPTION",
                     (double)recovered.time_msc,
                     (double)same_millisecond_ordinal,
                     StringFormat("sealed=%I64d/%I64d consumed=%I64d",
                                  rc4_shadow_activation_boundary_msc,
                                  rc4_shadow_activation_boundary_ordinal,
                                  rc4_shadow_activation_pre_boundary_consumed));
         EngageSafetyStop("RC4 shadow scanner crossed its activation boundary");
         return(false);
        }
      const bool ignored_activation_same_millisecond_tail =
         (recovered.time_msc == rc4_shadow_activation_boundary_msc);
      if(ignored_activation_same_millisecond_tail)
        {
         if(SameRC4ShadowTick(recovered, current_tick))
           {
            selected_index = index;
            selected_ordinal = same_millisecond_ordinal;
            break;
           }
         continue;
        }
      ++processed_ticks;
      if(!stop_release &&
         ArcOriginalStopReached(rc4_shadow_direction,
                                rc4_shadow_original_stop_loss,
                                recovered))
        {
         stop_release = true;
         stop_time_msc = recovered.time_msc;
        }
      if(SameRC4ShadowTick(recovered, current_tick))
        {
         selected_index = index;
         selected_ordinal = same_millisecond_ordinal;
         break;
        }
     }

   if(selected_index < 0 || seen_at_cursor < from_ordinal ||
      selected_ordinal <= 0)
     {
      stop_release = false;
      stop_time_msc = 0;
      rc4_shadow_catchup_required = true;
      ++rc4_shadow_catchup_failures;
      if(!rc4_shadow_catchup_failure_logged)
        {
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_CATCHUP_FAILED",
                     (double)seen_at_cursor,
                     (double)from_ordinal,
                     "current tick boundary or cursor ordinal is incomplete");
         rc4_shadow_catchup_failure_logged = true;
        }
      return(false);
     }

   ++rc4_shadow_catchup_scans;
   rc4_shadow_catchup_ticks += processed_ticks;
   rc4_shadow_last_observed_msc = current_tick.time_msc;
   rc4_shadow_cursor_ordinal = selected_ordinal;
   rc4_shadow_catchup_required = false;
   rc4_shadow_catchup_failure_logged = false;
   if(recovery_pending_before || processed_ticks > 1 || stop_release)
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_GAP_COMPLETE",
                  (double)processed_ticks,
                  (double)stop_time_msc,
                  StringFormat("identifier=%I64u stop_release=%d from=%I64d/%I64d to=%I64d/%I64d",
                               rc4_shadow_source_identifier,
                               (stop_release ? 1 : 0),
                               from_msc,
                               from_ordinal,
                               current_tick.time_msc,
                               selected_ordinal));
   return(true);
  }


bool PersistRC4ShadowCursorCheckpointIfEligible(const long prior_msc,
                                                const long prior_ordinal)
  {
   if(!execution_state.rc4_shadow_occupied)
      return(true);
   const long observation_bucket =
      rc4_shadow_last_observed_msc / RC4_NATIVE_M30_BUCKET_MSC;
   if(observation_bucket == rc4_shadow_cursor_checkpoint_observation_bucket)
      return(true);
   if(observation_bucket < rc4_shadow_cursor_checkpoint_observation_bucket)
     {
      ++rc4_shadow_cursor_checkpoint_regressions;
      rc4_shadow_cursor_checkpoint_pending = true;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)observation_bucket,
                  (double)rc4_shadow_cursor_checkpoint_observation_bucket,
                  "native M30 observation bucket regressed");
      EngageSafetyStop("RC4 shadow cursor checkpoint bucket regressed");
      return(false);
     }

   const bool cursor_advanced =
      (rc4_shadow_last_observed_msc > prior_msc ||
       (rc4_shadow_last_observed_msc == prior_msc &&
        rc4_shadow_cursor_ordinal > prior_ordinal));
   if(!cursor_advanced)
     {
      ++rc4_shadow_cursor_checkpoint_regressions;
      rc4_shadow_cursor_checkpoint_pending = true;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)prior_msc,
                  (double)rc4_shadow_last_observed_msc,
                  "millisecond-and-ordinal cursor did not advance");
      EngageSafetyStop("RC4 shadow cursor checkpoint did not advance");
      return(false);
     }

   const long completed_bucket = observation_bucket - 1;
   if(rc4_shadow_cursor_checkpoint_last_completed_bucket > 0 &&
      completed_bucket <=
         rc4_shadow_cursor_checkpoint_last_completed_bucket)
     {
      ++rc4_shadow_cursor_checkpoint_duplicate_bucket_failures;
      rc4_shadow_cursor_checkpoint_pending = true;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)completed_bucket,
                  (double)rc4_shadow_cursor_checkpoint_last_completed_bucket,
                  "duplicate or nonmonotone completed M30 bucket");
      EngageSafetyStop("RC4 shadow cursor checkpoint duplicated a native bucket");
      return(false);
     }

   const long previous_observation_bucket =
      rc4_shadow_cursor_checkpoint_observation_bucket;
   const long previous_completed_bucket =
      rc4_shadow_cursor_checkpoint_last_completed_bucket;
   const long previous_persisted_msc =
      rc4_shadow_cursor_checkpoint_last_persisted_msc;
   const long previous_persisted_ordinal =
      rc4_shadow_cursor_checkpoint_last_persisted_ordinal;
   const long expected_msc = rc4_shadow_last_observed_msc;
   const long expected_ordinal = rc4_shadow_cursor_ordinal;
   const long expected_eligible =
      rc4_shadow_cursor_checkpoint_eligible + 1;
   const long expected_persisted =
      rc4_shadow_cursor_checkpoint_persisted + 1;

   rc4_shadow_cursor_checkpoint_observation_bucket = observation_bucket;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = completed_bucket;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = expected_msc;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = expected_ordinal;
   rc4_shadow_cursor_checkpoint_eligible = expected_eligible;
   rc4_shadow_cursor_checkpoint_persisted = expected_persisted;
   rc4_shadow_cursor_checkpoint_pending = false;

   if(!SaveState())
     {
      rc4_shadow_cursor_checkpoint_observation_bucket =
         previous_observation_bucket;
      rc4_shadow_cursor_checkpoint_last_completed_bucket =
         previous_completed_bucket;
      rc4_shadow_cursor_checkpoint_last_persisted_msc =
         previous_persisted_msc;
      rc4_shadow_cursor_checkpoint_last_persisted_ordinal =
         previous_persisted_ordinal;
      rc4_shadow_cursor_checkpoint_persisted = expected_persisted - 1;
      rc4_shadow_cursor_checkpoint_pending = true;
      ++rc4_shadow_cursor_checkpoint_save_failures;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)completed_bucket,
                  (double)expected_msc,
                  "synchronous state save failed");
      EngageSafetyStop("RC4 shadow cursor checkpoint save failed");
      return(false);
     }

   const bool readback_equal =
      (rc4_shadow_last_observed_msc == expected_msc &&
       rc4_shadow_cursor_ordinal == expected_ordinal &&
       rc4_shadow_cursor_checkpoint_observation_bucket ==
          observation_bucket &&
       rc4_shadow_cursor_checkpoint_last_completed_bucket ==
          completed_bucket &&
       rc4_shadow_cursor_checkpoint_last_persisted_msc == expected_msc &&
       rc4_shadow_cursor_checkpoint_last_persisted_ordinal ==
          expected_ordinal &&
       rc4_shadow_cursor_checkpoint_eligible == expected_eligible &&
       rc4_shadow_cursor_checkpoint_persisted == expected_persisted &&
       !rc4_shadow_cursor_checkpoint_pending);
   if(!readback_equal)
     {
      rc4_shadow_cursor_checkpoint_pending = true;
      ++rc4_shadow_cursor_checkpoint_readback_failures;
      RecordEvent(RC4_BOTH,
                  "ARC_SHADOW_CURSOR_CHECKPOINT_FAILED",
                  (double)completed_bucket,
                  (double)expected_msc,
                  "persisted cursor readback did not match");
      EngageSafetyStop("RC4 shadow cursor checkpoint readback mismatch");
      return(false);
     }

   if(!RecordEvent(RC4_BOTH,
                   "ARC_SHADOW_CURSOR_CHECKPOINT",
                   (double)completed_bucket,
                   (double)expected_msc,
                   StringFormat("identifier=%I64u observation_bucket=%I64d cursor=%I64d/%I64d eligible=%I64d persisted=%I64d",
                                rc4_shadow_source_identifier,
                                observation_bucket,
                                expected_msc,
                                expected_ordinal,
                                expected_eligible,
                                expected_persisted)))
     {
      ++rc4_shadow_cursor_checkpoint_event_failures;
      EngageSafetyStop("RC4 shadow cursor checkpoint event failed");
      return(false);
     }
   return(true);
  }


bool RC4ActivationTickCausalCompatible(const MqlTick &tick)
  {
   if(tick.time_msc != rc4_shadow_activation_deal_time_msc ||
      tick.time <= 0 || tick.bid <= 0.0 || tick.ask <= 0.0 ||
      tick.ask < tick.bid ||
      rc4_shadow_activation_deal_reason != (int)DEAL_REASON_SL ||
      rc4_shadow_activation_deal_price <= 0.0 ||
      rc4_shadow_activation_protected_stop <= 0.0 ||
      MathAbs(rc4_shadow_direction) != 1)
      return(false);
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   if(!MathIsValidNumber(tick_size) || tick_size <= 0.0)
      return(false);
   const double tolerance = MathMax(1.0e-8, 0.5 * tick_size);
   if(rc4_shadow_direction > 0)
      return(tick.bid <=
                rc4_shadow_activation_protected_stop + tolerance &&
             rc4_shadow_activation_deal_price <=
                rc4_shadow_activation_protected_stop + tolerance &&
             rc4_shadow_activation_deal_price <= tick.bid + tolerance);
   return(tick.ask >=
             rc4_shadow_activation_protected_stop - tolerance &&
          rc4_shadow_activation_deal_price >=
             rc4_shadow_activation_protected_stop - tolerance &&
          rc4_shadow_activation_deal_price >= tick.ask - tolerance);
  }


bool ResolveRC4ShadowActivationBoundary(MqlTick &boundary_tick,
                                        long &boundary_ordinal,
                                        bool &sampled_identity_used,
                                        bool &ambiguous,
                                        string &failure_detail)
  {
   ZeroMemory(boundary_tick);
   boundary_ordinal = 0;
   sampled_identity_used = false;
   ambiguous = false;
   failure_detail = "";
   if(!execution_state.rc4_shadow_occupied || !execution_state.rc4_shadow_activation_seal_pending ||
      rc4_shadow_activation_deal_ticket == 0 ||
      rc4_shadow_activation_deal_time_msc <= 0)
     {
      failure_detail = "activation seal state is incomplete";
      return(false);
     }
   if(!HistoryDealSelect(rc4_shadow_activation_deal_ticket))
     {
      failure_detail = "exit deal identity is not yet selectable";
      return(false);
     }
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   if(!MathIsValidNumber(tick_size) || tick_size <= 0.0)
     {
      failure_detail = "US30 tick size is unavailable for activation seal";
      return(false);
     }
   const double tolerance = MathMax(1.0e-8, 0.5 * tick_size);
   const long selected_deal_time_msc =
      HistoryDealGetInteger(rc4_shadow_activation_deal_ticket,
                            DEAL_TIME_MSC);
   const double selected_deal_price =
      HistoryDealGetDouble(rc4_shadow_activation_deal_ticket,
                           DEAL_PRICE);
   const ENUM_DEAL_REASON selected_deal_reason =
      (ENUM_DEAL_REASON)HistoryDealGetInteger(
         rc4_shadow_activation_deal_ticket,
         DEAL_REASON);
   const ENUM_DEAL_ENTRY selected_deal_entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(
         rc4_shadow_activation_deal_ticket,
         DEAL_ENTRY);
   const ENUM_DEAL_TYPE selected_deal_type =
      (ENUM_DEAL_TYPE)HistoryDealGetInteger(
         rc4_shadow_activation_deal_ticket,
         DEAL_TYPE);
   const bool selected_direction_matches =
      (rc4_shadow_direction > 0
       ? selected_deal_type == DEAL_TYPE_SELL
       : selected_deal_type == DEAL_TYPE_BUY);
   if(selected_deal_time_msc != rc4_shadow_activation_deal_time_msc ||
      MathAbs(selected_deal_price - rc4_shadow_activation_deal_price) >
         tolerance ||
      (int)selected_deal_reason != rc4_shadow_activation_deal_reason ||
      selected_deal_reason != DEAL_REASON_SL ||
      (selected_deal_entry != DEAL_ENTRY_OUT &&
       selected_deal_entry != DEAL_ENTRY_OUT_BY) ||
      !selected_direction_matches ||
      (ulong)HistoryDealGetInteger(rc4_shadow_activation_deal_ticket,
                                   DEAL_MAGIC) != MAGIC_RC4_BOTH ||
      HistoryDealGetString(rc4_shadow_activation_deal_ticket,
                           DEAL_SYMBOL) != "US30" ||
      (ulong)HistoryDealGetInteger(rc4_shadow_activation_deal_ticket,
                                   DEAL_POSITION_ID) !=
         rc4_shadow_source_identifier)
     {
      failure_detail = "exit deal identity changed or is incompatible";
      return(false);
     }

   MqlTick ticks[];
   ResetLastError();
   const int copied =
      CopyTicksRange("US30",
                     ticks,
                     COPY_TICKS_ALL,
                     (ulong)rc4_shadow_activation_deal_time_msc,
                     (ulong)rc4_shadow_activation_deal_time_msc);
   const int history_error = GetLastError();
   if(copied <= 0 || history_error != 0 || ArraySize(ticks) != copied)
     {
      failure_detail =
         StringFormat("incomplete exact-ms CopyTicksRange copied=%d size=%d error=%d",
                      copied,
                      ArraySize(ticks),
                      history_error);
      return(false);
     }
   for(int index = 0; index < copied; ++index)
     {
      if(ticks[index].time_msc !=
            rc4_shadow_activation_deal_time_msc ||
         ticks[index].time <= 0 || ticks[index].bid <= 0.0 ||
         ticks[index].ask <= 0.0 || ticks[index].ask < ticks[index].bid)
        {
         failure_detail = "invalid exact-ms activation tick sequence";
         return(false);
        }
     }

   MqlTick sampled_tick = {};
   sampled_tick.time = rc4_shadow_activation_sampled_time;
   sampled_tick.time_msc = rc4_shadow_activation_sampled_time_msc;
   sampled_tick.bid = rc4_shadow_activation_sampled_bid;
   sampled_tick.ask = rc4_shadow_activation_sampled_ask;
   sampled_tick.last = rc4_shadow_activation_sampled_last;
   sampled_tick.volume = rc4_shadow_activation_sampled_volume;
   sampled_tick.volume_real = rc4_shadow_activation_sampled_volume_real;
   sampled_tick.flags = rc4_shadow_activation_sampled_flags;
   const bool sampled_candidate =
      (rc4_shadow_activation_sampled_tick_known &&
       sampled_tick.time_msc == rc4_shadow_activation_deal_time_msc &&
       RC4ActivationTickCausalCompatible(sampled_tick));
   int selected_index = -1;
   if(sampled_candidate)
     {
      int sampled_matches = 0;
      for(int index = 0; index < copied; ++index)
         if(SameRC4ShadowTick(ticks[index], sampled_tick) &&
            RC4ActivationTickCausalCompatible(ticks[index]))
           {
            ++sampled_matches;
            selected_index = index;
           }
      if(sampled_matches > 1)
        {
         ambiguous = true;
         failure_detail =
            "sampled full tick identity maps to multiple exact-ms records";
         return(false);
        }
      if(sampled_matches == 0)
        {
         failure_detail =
            "sampled full tick identity is absent from exact-ms records";
         return(false);
        }
      sampled_identity_used = true;
     }
   if(selected_index < 0)
     {
      for(int index = 0; index < copied; ++index)
         if(RC4ActivationTickCausalCompatible(ticks[index]))
           {
            selected_index = index;
            break;
           }
     }
   if(selected_index < 0)
     {
      failure_detail =
         "no causal-compatible exit record exists in the exact deal millisecond";
      return(false);
     }
   boundary_tick = ticks[selected_index];
   boundary_ordinal = (long)selected_index + 1;
   return(boundary_ordinal > 0);
  }


bool ResolveAndPersistRC4ShadowActivationSeal()
  {
   if(!execution_state.rc4_shadow_occupied)
      return(false);
   if(execution_state.rc4_shadow_activation_sealed &&
      !execution_state.rc4_shadow_activation_seal_pending)
      return(true);

   MqlTick boundary_tick = {};
   long boundary_ordinal = 0;
   bool sampled_identity_used = false;
   bool ambiguous = false;
   string failure_detail = "";
   if(!ResolveRC4ShadowActivationBoundary(boundary_tick,
                                          boundary_ordinal,
                                          sampled_identity_used,
                                          ambiguous,
                                          failure_detail))
     {
      execution_state.rc4_shadow_activation_sealed = false;
      execution_state.rc4_shadow_activation_seal_pending = true;
      rc4_shadow_last_observed_msc =
         rc4_shadow_activation_deal_time_msc;
      rc4_shadow_cursor_ordinal = 0;
      rc4_shadow_catchup_required = true;
      if(!rc4_shadow_activation_seal_failure_logged)
        {
         ++rc4_shadow_activation_seal_pending_count;
         ++rc4_shadow_activation_seal_failures;
         if(ambiguous)
            ++rc4_shadow_activation_seal_ambiguities;
         rc4_shadow_activation_seal_failure_logged = true;
         RecordEvent(RC4_BOTH,
                     "ARC_SHADOW_ACTIVATION_SEAL_PENDING",
                     (double)rc4_shadow_activation_deal_time_msc,
                     (double)rc4_shadow_activation_deal_ticket,
                     failure_detail +
                     StringFormat(" deal=%I64u eligible=%I64d sealed=%I64d pending=%I64d save_attempts=%I64d readbacks=%I64d failures=%I64d ambiguities=%I64d pre_boundary_consumed=%I64d",
                                  rc4_shadow_activation_deal_ticket,
                                  rc4_shadow_activation_seal_eligible,
                                  rc4_shadow_activation_seal_sealed,
                                  rc4_shadow_activation_seal_pending_count,
                                  rc4_shadow_activation_seal_save_attempts,
                                  rc4_shadow_activation_seal_readbacks,
                                  rc4_shadow_activation_seal_failures,
                                  rc4_shadow_activation_seal_ambiguities,
                                  rc4_shadow_activation_pre_boundary_consumed));
        }
      ++rc4_shadow_activation_seal_save_attempts;
      ++rc4_shadow_activation_seal_readbacks;
      if(!SaveState())
        {
         --rc4_shadow_activation_seal_readbacks;
         ++rc4_shadow_activation_seal_save_failures;
         EngageSafetyStop("RC4 shadow activation pending state could not be persisted");
        }
      return(false);
     }

   const ulong identifier = rc4_shadow_source_identifier;
   const ulong activation_deal_ticket =
      rc4_shadow_activation_deal_ticket;
   const double original_stop = rc4_shadow_original_stop_loss;
   const int shadow_direction = rc4_shadow_direction;
   const long deal_time_msc = rc4_shadow_activation_deal_time_msc;
   execution_state.rc4_shadow_activation_sealed = true;
   execution_state.rc4_shadow_activation_seal_pending = false;
   rc4_shadow_activation_seal_failure_logged = false;
   rc4_shadow_activation_boundary_msc = deal_time_msc;
   rc4_shadow_activation_boundary_ordinal = boundary_ordinal;
   rc4_shadow_last_observed_msc = deal_time_msc;
   rc4_shadow_cursor_ordinal = boundary_ordinal;
   rc4_shadow_catchup_required = true;
   rc4_shadow_catchup_failure_logged = false;
   ++rc4_shadow_activation_seal_sealed;
   rc4_shadow_activation_last_sealed_msc = deal_time_msc;
   rc4_shadow_activation_last_sealed_ordinal = boundary_ordinal;

   const bool original_stop_reached =
      ArcOriginalStopReached(rc4_shadow_direction,
                             rc4_shadow_original_stop_loss,
                             boundary_tick);
   if(original_stop_reached)
      ClearRC4ShadowState();
   else
      ++rc4_shadow_activations;
   ClearArcLifecycleState();

   ++rc4_shadow_activation_seal_save_attempts;
   ++rc4_shadow_activation_seal_readbacks;
   if(!SaveState())
     {
      --rc4_shadow_activation_seal_readbacks;
      ++rc4_shadow_activation_seal_save_failures;
      ++rc4_shadow_activation_seal_failures;
      EngageSafetyStop("RC4 shadow activation seal could not be persisted");
      return(false);
     }
   const bool readback_equal =
      (rc4_shadow_activation_last_sealed_msc == deal_time_msc &&
       rc4_shadow_activation_last_sealed_ordinal == boundary_ordinal &&
       rc4_shadow_activation_pre_boundary_consumed == 0 &&
       (original_stop_reached ||
        (execution_state.rc4_shadow_occupied && execution_state.rc4_shadow_activation_sealed &&
         !execution_state.rc4_shadow_activation_seal_pending &&
         rc4_shadow_activation_boundary_msc == deal_time_msc &&
         rc4_shadow_activation_boundary_ordinal == boundary_ordinal &&
         rc4_shadow_last_observed_msc == deal_time_msc &&
         rc4_shadow_cursor_ordinal == boundary_ordinal)));
   if(!readback_equal)
     {
      ++rc4_shadow_activation_seal_readback_failures;
      ++rc4_shadow_activation_seal_failures;
      EngageSafetyStop("RC4 shadow activation seal readback mismatch");
      return(false);
     }

   RecordEvent(RC4_BOTH,
               (original_stop_reached
                ? "ARC_SHADOW_NOT_REQUIRED"
                : "ARC_SHADOW_ACTIVATION_SEALED"),
               (double)deal_time_msc,
               (double)boundary_ordinal,
               StringFormat("identifier=%I64u deal=%I64u source=%s original_stop=%.5f boundary_side=%.5f eligible=%I64d sealed=%I64d pending=%I64d save_attempts=%I64d save_failures=%I64d readbacks=%I64d readback_failures=%I64d failures=%I64d ambiguities=%I64d sealed_cursor=%I64d/%I64d pre_boundary_consumed=%I64d",
                            identifier,
                            activation_deal_ticket,
                            (sampled_identity_used
                             ? "sampled-full-identity"
                             : "deal-first-causal-compatible"),
                            original_stop,
                            (shadow_direction > 0
                             ? boundary_tick.bid : boundary_tick.ask),
                            rc4_shadow_activation_seal_eligible,
                            rc4_shadow_activation_seal_sealed,
                            rc4_shadow_activation_seal_pending_count,
                            rc4_shadow_activation_seal_save_attempts,
                            rc4_shadow_activation_seal_save_failures,
                            rc4_shadow_activation_seal_readbacks,
                            rc4_shadow_activation_seal_readback_failures,
                            rc4_shadow_activation_seal_failures,
                            rc4_shadow_activation_seal_ambiguities,
                            deal_time_msc,
                            boundary_ordinal,
                            rc4_shadow_activation_pre_boundary_consumed));
   return(!original_stop_reached);
  }


void ActivateRC4ShadowAfterCompressedExit(const ulong identifier,
                                          const datetime entered_at,
                                          const int direction,
                                          const double original_stop,
                                          const ulong deal_ticket,
                                          const long exit_time_msc,
                                          const double deal_price,
                                          const ENUM_DEAL_REASON deal_reason,
                                          const double protected_stop,
                                          const MqlTick &sampled_tick,
                                          const bool sampled_tick_known)
  {
   if(identifier == 0 || entered_at <= 0 || MathAbs(direction) != 1 ||
      original_stop <= 0.0 || deal_ticket == 0 || exit_time_msc <= 0 ||
      deal_price <= 0.0 || deal_reason != DEAL_REASON_SL ||
      protected_stop <= 0.0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("compressed RC4 exit lacks shadow identity");
      ClearArcLifecycleState();
      return;
     }
   if(execution_state.rc4_shadow_occupied)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("duplicate RC4 shadow occupancy activation");
      ClearArcLifecycleState();
      return;
     }
   execution_state.rc4_shadow_occupied = true;
   rc4_shadow_source_identifier = identifier;
   rc4_shadow_entry_time = entered_at;
   rc4_shadow_direction = direction;
   rc4_shadow_original_stop_loss = original_stop;
   rc4_shadow_last_observed_msc = exit_time_msc;
   rc4_shadow_cursor_ordinal = 0;
   rc4_shadow_catchup_required = true;
   rc4_shadow_catchup_failure_logged = false;
   rc4_shadow_cursor_checkpoint_observation_bucket =
      exit_time_msc / RC4_NATIVE_M30_BUCKET_MSC;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
   rc4_shadow_cursor_checkpoint_pending = false;
   execution_state.rc4_shadow_activation_sealed = false;
   execution_state.rc4_shadow_activation_seal_pending = true;
   rc4_shadow_activation_seal_failure_logged = false;
   rc4_shadow_activation_deal_ticket = deal_ticket;
   rc4_shadow_activation_deal_time_msc = exit_time_msc;
   rc4_shadow_activation_deal_price = deal_price;
   rc4_shadow_activation_deal_reason = (int)deal_reason;
   rc4_shadow_activation_protected_stop = protected_stop;
   rc4_shadow_activation_sampled_tick_known = sampled_tick_known;
   rc4_shadow_activation_sampled_time =
      (sampled_tick_known ? sampled_tick.time : 0);
   rc4_shadow_activation_sampled_time_msc =
      (sampled_tick_known ? sampled_tick.time_msc : 0);
   rc4_shadow_activation_sampled_bid =
      (sampled_tick_known ? sampled_tick.bid : 0.0);
   rc4_shadow_activation_sampled_ask =
      (sampled_tick_known ? sampled_tick.ask : 0.0);
   rc4_shadow_activation_sampled_last =
      (sampled_tick_known ? sampled_tick.last : 0.0);
   rc4_shadow_activation_sampled_volume =
      (sampled_tick_known ? sampled_tick.volume : 0);
   rc4_shadow_activation_sampled_volume_real =
      (sampled_tick_known ? sampled_tick.volume_real : 0.0);
   rc4_shadow_activation_sampled_flags =
      (sampled_tick_known ? sampled_tick.flags : 0);
   rc4_shadow_activation_boundary_msc = 0;
   rc4_shadow_activation_boundary_ordinal = 0;
   ++rc4_shadow_activation_seal_eligible;
   ClearArcLifecycleState();
   ResolveAndPersistRC4ShadowActivationSeal();
  }


void ProcessRC4ShadowOccupancy()
  {
   if(!execution_state.rc4_shadow_occupied)
      return;
   if(component_states[RC4_BOTH].position_identifier != 0 ||
      rc4_shadow_source_identifier == 0 ||
      rc4_shadow_entry_time <= 0 ||
      MathAbs(rc4_shadow_direction) != 1 ||
      rc4_shadow_original_stop_loss <= 0.0 ||
      rc4_shadow_last_observed_msc <= 0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 shadow occupancy state is inconsistent");
      return;
     }
   if(execution_state.rc4_shadow_activation_seal_pending)
     {
      if(!ResolveAndPersistRC4ShadowActivationSeal())
         return;
      if(!execution_state.rc4_shadow_occupied)
         return;
     }
   if(!execution_state.rc4_shadow_activation_sealed ||
      rc4_shadow_activation_boundary_msc <= 0 ||
      rc4_shadow_activation_boundary_ordinal <= 0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 shadow activation boundary is not sealed");
      return;
     }

   MqlTick tick = {};
   const bool tick_known = StructurallyValidTick("US30", tick);
   const int held_bars =
      iBarShift("US30", PERIOD_M30, rc4_shadow_entry_time, false);
   const bool deadline_release =
      (held_bars >= component_definitions[RC4_BOTH].hold_bars);
   const bool recovery_pending_before = rc4_shadow_catchup_required;
   const long cursor_before_msc = rc4_shadow_last_observed_msc;
   const long cursor_before_ordinal = rc4_shadow_cursor_ordinal;
   const bool gap_scan_required = tick_known;
   bool gap_complete = false;
   bool stop_release = false;
   bool catchup_stop_release = false;
   long stop_time_msc = 0;
   if(gap_scan_required)
     {
      gap_complete =
         CatchUpRC4ShadowToTick(tick,
                                catchup_stop_release,
                                stop_time_msc);
      if(!gap_complete)
        {
         if(tick.time_msc > rc4_shadow_activation_boundary_msc &&
            ArcOriginalStopReached(rc4_shadow_direction,
                                   rc4_shadow_original_stop_loss,
                                   tick))
           {
            stop_release = true;
            stop_time_msc = tick.time_msc;
           }
         else if(!deadline_release)
           {
            if(!SaveState())
               EngageSafetyStop("RC4 incomplete shadow gap state could not be persisted");
            return;
           }
        }
      else
        {
         stop_release = catchup_stop_release;
         if(!PersistRC4ShadowCursorCheckpointIfEligible(
               cursor_before_msc,
               cursor_before_ordinal))
            return;
        }
     }
   else if(recovery_pending_before && !deadline_release)
      return;
   if(!stop_release && !deadline_release)
     {
      if(recovery_pending_before && !SaveState())
         EngageSafetyStop("RC4 shadow catch-up state could not be persisted");
      return;
     }

   const ulong identifier = rc4_shadow_source_identifier;
   const double original_stop = rc4_shadow_original_stop_loss;
   const string reason = (stop_release ? "ORIGINAL_STOP" : "ORIGINAL_DEADLINE");
   if(stop_release)
     {
      ++rc4_shadow_stop_releases;
      if(catchup_stop_release)
         ++rc4_shadow_catchup_stop_releases;
     }
   else
      ++rc4_shadow_deadline_releases;
   ClearRC4ShadowState();
   RecordEvent(RC4_BOTH,
               "ARC_SHADOW_RELEASED",
               original_stop,
               (double)held_bars,
               StringFormat("identifier=%I64u reason=%s",
                            identifier,
                            reason) +
               StringFormat(" catchup=%d stop_time_msc=%I64d",
                            (catchup_stop_release ? 1 : 0),
                            stop_time_msc));
   if(!SaveState())
      EngageSafetyStop("RC4 shadow release state could not be persisted");
  }


double ArcBounded(const double value)
  {
   return(MathMax(-8.0, MathMin(8.0, value)));
  }


int ArcOrdinalVote(const double value,
                   const double lower,
                   const double upper)
  {
   if(value <= lower)
      return(-1);
   if(value >= upper)
      return(1);
   return(0);
  }


double ArcSampleStandardDeviation(const double &values[],
                                  const int start,
                                  const int count)
  {
   if(count < 2 || start < 0 || start + count > ArraySize(values))
      return(0.0);
   double mean = 0.0;
   for(int index = start; index < start + count; ++index)
      mean += values[index];
   mean /= (double)count;
   double squared = 0.0;
   for(int index = start; index < start + count; ++index)
     {
      const double deviation = values[index] - mean;
      squared += deviation * deviation;
     }
   return(MathSqrt(squared / (double)(count - 1)));
  }


bool ArcCalculateRangeCompressionAtOffset(const int completed_offset,
                                          double &signed_tightness)
  {
   signed_tightness = 0.0;
   const int compression_window = 4;
   const int normal_window = 96;
   const int direction_lookback = 2;
   const int bar_count = normal_window + compression_window;
   double highs[];
   double lows[];
   double closes[];
   const int start_shift = 1 + completed_offset;
   if(CopyHigh("US30", PERIOD_M30, start_shift, bar_count, highs) != bar_count ||
      CopyLow("US30", PERIOD_M30, start_shift, bar_count, lows) != bar_count ||
      CopyClose("US30", PERIOD_M30, start_shift, bar_count, closes) != bar_count)
      return(false);

   double prior_ranges[];
   ArrayResize(prior_ranges, normal_window);
   for(int sample = 0; sample < normal_window; ++sample)
     {
      prior_ranges[sample] =
         WindowLogRange(highs, lows, sample, compression_window);
      if(prior_ranges[sample] <= 0.0)
         return(false);
     }
   const double normal_range = Median(prior_ranges);
   const double current_range =
      WindowLogRange(highs, lows, normal_window, compression_window);
   const int latest = bar_count - 1;
   const int earlier = latest - direction_lookback;
   if(normal_range <= 0.0 || current_range <= 0.0 ||
      closes[latest] <= 0.0 || closes[earlier] <= 0.0)
      return(false);
   const double direction_return =
      MathLog(closes[latest] / closes[earlier]);
   if(direction_return == 0.0)
      return(true);
   signed_tightness =
      (direction_return > 0.0 ? 1.0 : -1.0) /
      (current_range / normal_range);
   return(MathIsValidNumber(signed_tightness));
  }


bool ArcCalculateUS30M30NativeState(double &ret1_z,
                                    double &efficiency4,
                                    double &close_location,
                                    double &vol_ratio,
                                    double &range_median96)
  {
   ret1_z = 0.0;
   efficiency4 = 0.0;
   close_location = 0.0;
   vol_ratio = 0.0;
   range_median96 = 0.0;
   const int count = 97;
   MqlRates rates[];
   if(CopyRates("US30", PERIOD_M30, 1, count, rates) != count)
      return(false);

   double returns[];
   ArrayResize(returns, count - 1);
   for(int index = 1; index < count; ++index)
     {
      if(rates[index].close <= 0.0 || rates[index - 1].close <= 0.0)
         return(false);
      returns[index - 1] =
         MathLog(rates[index].close / rates[index - 1].close);
     }
   const double prior_std = ArcSampleStandardDeviation(returns, 47, 48);
   const double fast_std = ArcSampleStandardDeviation(returns, 92, 4);
   const double slow_std = ArcSampleStandardDeviation(returns, 71, 24);
   if(prior_std <= 0.0 || slow_std < 0.0)
      return(false);

   const int latest = count - 1;
   ret1_z = returns[95] / prior_std;
   double absolute_path = 0.0;
   for(int index = 92; index <= 95; ++index)
      absolute_path += MathAbs(returns[index]);
   efficiency4 =
      MathAbs(MathLog(rates[latest].close / rates[latest - 4].close)) /
      (absolute_path + 1.0e-12);
   const double latest_range = rates[latest].high - rates[latest].low;
   if(latest_range <= 0.0)
      return(false);
   close_location =
      2.0 * ((rates[latest].close - rates[latest].low) /
             latest_range - 0.5);
   vol_ratio = fast_std / (slow_std + 1.0e-12);

   double prior_ranges[];
   ArrayResize(prior_ranges, 96);
   for(int index = 0; index < 96; ++index)
     {
      prior_ranges[index] = rates[index].high - rates[index].low;
      if(prior_ranges[index] <= 0.0)
         return(false);
     }
   range_median96 = Median(prior_ranges);
   return(MathIsValidNumber(ret1_z) &&
          MathIsValidNumber(efficiency4) &&
          MathIsValidNumber(close_location) &&
          MathIsValidNumber(vol_ratio) &&
          MathIsValidNumber(range_median96) &&
          range_median96 > 0.0);
  }


bool ArcCalculateRC4Heads(const int direction,
                          double &market,
                          double &decision,
                          double &confirmation)
  {
   market = 0.0;
   decision = 0.0;
   confirmation = 0.0;
   if(MathAbs(direction) != 1)
      return(false);

   double current_feature = 0.0;
   double previous_feature = 0.0;
   double two_back_feature = 0.0;
   if(!ArcCalculateRangeCompressionAtOffset(0, current_feature) ||
      !ArcCalculateRangeCompressionAtOffset(1, previous_feature) ||
      !ArcCalculateRangeCompressionAtOffset(2, two_back_feature))
      return(false);

   double ret1_z = 0.0;
   double efficiency4 = 0.0;
   double close_location = 0.0;
   double vol_ratio = 0.0;
   double native_range = 0.0;
   if(!ArcCalculateUS30M30NativeState(ret1_z,
                                      efficiency4,
                                      close_location,
                                      vol_ratio,
                                      native_range))
      return(false);
   double pressure = 0.0;
   if(!CalculateIntradayRangePressure("US30", pressure))
      return(false);
   MqlTick tick = {};
   if(!StructurallyValidTick("US30", tick))
      return(false);

   const double entry_support =
      (double)direction * component_states[RC4_BOTH].entry_feature;
   const double current_support = (double)direction * current_feature;
   const double previous_support = (double)direction * previous_feature;
   const double two_back_support = (double)direction * two_back_feature;
   const double scale = MathMax(MathMax(MathAbs(entry_support), 1.5), 0.25);
   const double velocity =
      (current_support - previous_support) / scale;
   const double prior_velocity =
      (previous_support - two_back_support) / scale;
   const double curvature = velocity - prior_velocity;
   const double spread = MathMax(tick.ask - tick.bid, 1.10);
   const double cost_scale =
      MathMax(0.0, MathMin(2.0, spread / native_range));

   market = ArcBounded(
      (double)direction * ret1_z * (0.40 + 0.60 * efficiency4) -
      0.25 * MathMax(0.0, vol_ratio - 1.0) -
      0.20 * cost_scale);
   decision = ArcBounded(
      current_support / scale +
      0.65 * velocity +
      0.35 * curvature -
      (current_support < 0.0 ? 1.25 : 0.0));
   confirmation = ArcBounded(
      0.70 * (double)direction * pressure +
      0.30 * (double)direction * close_location);
   return(MathIsValidNumber(market) &&
          MathIsValidNumber(decision) &&
          MathIsValidNumber(confirmation));
  }


bool ArcRoundedLossSideStop(const double entry,
                            const double original_stop,
                            const int direction,
                            double &new_stop)
  {
   new_stop = 0.0;
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const int digits = (int)SymbolInfoInteger("US30", SYMBOL_DIGITS);
   if(entry <= 0.0 || original_stop <= 0.0 || tick_size <= 0.0 ||
      MathAbs(direction) != 1)
      return(false);
   const double raw =
      entry + ARC_RC4_RETAINED_LOSS_FRACTION * (original_stop - entry);
   const double units = raw / tick_size;
   new_stop = NormalizeDouble(
      (direction > 0
       ? MathFloor(units + 1.0e-12) * tick_size
       : MathCeil(units - 1.0e-12) * tick_size),
      digits);
   return(new_stop > 0.0);
  }


void BeginArcLifecycle(const ulong identifier)
  {
   ClearArcLifecycleState();
   if(identifier == 0)
      return;
   arc_lifecycle_identifier = identifier;
   arc_original_stop_loss = component_states[RC4_BOTH].entry_stop_loss;
  }


bool IsArcTransientModifyRetcode(const uint retcode)
  {
   return(retcode == TRADE_RETCODE_REQUOTE ||
          retcode == TRADE_RETCODE_TIMEOUT ||
          retcode == TRADE_RETCODE_PRICE_CHANGED ||
          retcode == TRADE_RETCODE_PRICE_OFF ||
          retcode == TRADE_RETCODE_TOO_MANY_REQUESTS ||
          retcode == TRADE_RETCODE_LOCKED ||
          retcode == TRADE_RETCODE_CONNECTION);
  }


void ClearArcRetryIntent()
  {
   execution_state.arc_modify_retry_pending = false;
   execution_state.arc_modify_retry_after_msc = 0;
   arc_modify_retry_initial_retcode = 0;
  }


bool ReconcileArcPendingModify(const bool restart_recovery)
  {
   if(!execution_state.arc_modify_pending && !execution_state.arc_modify_retry_pending)
      return(true);
   const ulong identifier = component_states[RC4_BOTH].position_identifier;
   if(identifier == 0 || identifier != arc_lifecycle_identifier ||
      !arc_checkpoint_evaluated || arc_lifecycle_compressed ||
      arc_pending_stop_loss <= 0.0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 pending stop journal is inconsistent");
      return(false);
     }

   ulong ticket = 0;
   datetime opened_at = 0;
   if(CountOwnedPositions(RC4_BOTH, ticket, opened_at) != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 pending stop journal lacks its broker position");
      return(false);
     }
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   const double original_saved_stop = component_states[RC4_BOTH].entry_stop_loss;
   const double pending_stop = arc_pending_stop_loss;
   const double tolerance = MathMax(1.0e-9, 0.5 * tick_size);
   const bool broker_applied =
      (tick_size > 0.0 &&
       MathAbs(broker_stop - pending_stop) <= tolerance);
   const bool broker_not_applied =
      (tick_size > 0.0 && original_saved_stop > 0.0 &&
       MathAbs(broker_stop - original_saved_stop) <= tolerance);
   if(!broker_applied && !broker_not_applied)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 pending stop journal differs from broker stop");
      return(false);
     }
   if(execution_state.arc_modify_retry_pending && broker_not_applied)
      return(true);
   if(!restart_recovery && broker_not_applied)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 completed stop modify was not applied by broker");
      return(false);
     }

   execution_state.arc_modify_pending = false;
   ClearArcRetryIntent();
   if(broker_applied)
     {
      component_states[RC4_BOTH].entry_stop_loss = broker_stop;
      arc_lifecycle_compressed = true;
      ++arc_compressions_placed;
      arc_pending_stop_loss = 0.0;
      RecordEvent(RC4_BOTH,
                  (restart_recovery ? "ARC_MODIFY_RECOVERED" :
                                      "ARC_COMPRESSED"),
                  original_saved_stop,
                  broker_stop,
                  StringFormat("identifier=%I64u broker_applied=1 recovery=%d",
                               identifier,
                               (restart_recovery ? 1 : 0)));
     }
   else
     {
      arc_pending_stop_loss = 0.0;
      ++arc_modify_retry_holds;
      ++arc_compression_refusals;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_RESTART_HOLD",
                  original_saved_stop,
                  pending_stop,
                  StringFormat("identifier=%I64u ambiguous_request_not_applied=1",
                               identifier));
     }
   if(!SaveState())
     {
      EngageSafetyStop("RC4 pending stop recovery could not be persisted");
      return(false);
     }
   return(true);
  }


bool ResolveArcNonSuccessfulModify(const uint retcode,
                                   const string description,
                                   const long attempt_tick_msc,
                                   const bool retry_attempt)
  {
   const ulong identifier = component_states[RC4_BOTH].position_identifier;
   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned_positions =
      CountOwnedPositions(RC4_BOTH, ticket, opened_at);
   if(identifier != 0 && identifier == arc_lifecycle_identifier &&
      owned_positions == 0)
     {
      execution_state.pending_reconcile = true;
      if(ReconcileBrokerState(false))
         return(true);
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 non-successful modify close could not be reconciled");
      return(false);
     }
   if(identifier == 0 || identifier != arc_lifecycle_identifier ||
      owned_positions != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 non-successful modify lost owned position");
      return(false);
     }

   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   const double original_stop = component_states[RC4_BOTH].entry_stop_loss;
   const double target_stop = arc_pending_stop_loss;
   const double tolerance = MathMax(1.0e-9, 0.5 * tick_size);
   const bool broker_applied =
      (tick_size > 0.0 && target_stop > 0.0 &&
       MathAbs(broker_stop - target_stop) <= tolerance);
   const bool broker_original =
      (tick_size > 0.0 && original_stop > 0.0 &&
       MathAbs(broker_stop - original_stop) <= tolerance);
   if(!broker_applied && !broker_original)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 non-successful modify broker stop is inconsistent");
      return(false);
     }

   execution_state.arc_modify_pending = false;
   if(broker_applied)
     {
      ClearArcRetryIntent();
      arc_pending_stop_loss = 0.0;
      component_states[RC4_BOTH].entry_stop_loss = broker_stop;
      arc_lifecycle_compressed = true;
      ++arc_compressions_placed;
      ++arc_modify_retry_adoptions;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_ALREADY_APPLIED",
                  broker_stop,
                  (double)retcode,
                  StringFormat("identifier=%I64u retry=%d %s",
                               identifier,
                               (retry_attempt ? 1 : 0),
                               description));
      if(!SaveState())
        {
         EngageSafetyStop("RC4 applied modify adoption could not be persisted");
         return(false);
        }
      return(true);
     }

   if(!retry_attempt && IsArcTransientModifyRetcode(retcode) &&
      attempt_tick_msc > 0 && !arc_modify_retry_consumed)
     {
      execution_state.arc_modify_retry_pending = true;
      execution_state.arc_modify_retry_after_msc = attempt_tick_msc;
      arc_modify_retry_initial_retcode = retcode;
      ++arc_modify_retry_intents;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_RETRY_INTENT",
                  target_stop,
                  (double)retcode,
                  StringFormat("identifier=%I64u strictly_after_msc=%I64d %s",
                               identifier,
                               attempt_tick_msc,
                               description));
      if(!SaveState())
        {
         EngageSafetyStop("RC4 retry intent could not be persisted");
         return(false);
        }
      return(true);
     }

   ClearArcRetryIntent();
   arc_pending_stop_loss = 0.0;
   ++arc_modify_retry_holds;
   ++arc_compression_refusals;
   RecordEvent(RC4_BOTH,
               (retry_attempt ? "ARC_MODIFY_RETRY_HOLD" :
                                "ARC_MODIFY_NONRETRYABLE_HOLD"),
               original_stop,
               (double)retcode,
               StringFormat("identifier=%I64u %s", identifier, description));
   if(!SaveState())
     {
      EngageSafetyStop("RC4 modify HOLD could not be persisted");
      return(false);
     }
   return(true);
  }


void ProcessArcModifyRetry()
  {
   if(!execution_state.arc_modify_retry_pending || execution_state.arc_modify_pending ||
      arc_modify_retry_consumed || portfolio_state.safety_stopped || execution_state.broker_mismatch ||
      persistence_failed)
      return;

   MqlTick observed = {};
   if(!SymbolInfoTick("US30", observed) ||
      observed.time_msc <= execution_state.arc_modify_retry_after_msc)
      return;

   const ulong identifier = component_states[RC4_BOTH].position_identifier;
   ulong ticket = 0;
   datetime opened_at = 0;
   const int owned_positions =
      CountOwnedPositions(RC4_BOTH, ticket, opened_at);
   if(identifier != 0 && identifier == arc_lifecycle_identifier &&
      owned_positions == 0)
     {
      execution_state.pending_reconcile = true;
      if(!ReconcileBrokerState(false))
        {
         execution_state.broker_mismatch = true;
         EngageSafetyStop("RC4 retry checkpoint close could not be reconciled");
        }
      return;
     }
   if(identifier == 0 || identifier != arc_lifecycle_identifier ||
      owned_positions != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 retry checkpoint lost owned position");
      return;
     }

   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double broker_stop = PositionGetDouble(POSITION_SL);
   const double original_stop = component_states[RC4_BOTH].entry_stop_loss;
   const double target_stop = arc_pending_stop_loss;
   const double tolerance = MathMax(1.0e-9, 0.5 * tick_size);
   if(tick_size <= 0.0 || target_stop <= 0.0 || original_stop <= 0.0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 retry checkpoint has invalid stop state");
      return;
     }
   if(MathAbs(broker_stop - target_stop) <= tolerance)
     {
      execution_state.arc_modify_pending = true;
      ++arc_modify_retry_adoptions;
      if(!ReconcileArcPendingModify(false))
         return;
      return;
     }
   if(MathAbs(broker_stop - original_stop) > tolerance)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 retry checkpoint broker stop changed");
      return;
     }

   const int direction = component_states[RC4_BOTH].entry_direction;
   const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   const double take_profit = PositionGetDouble(POSITION_TP);
   const MqlTick tick = observed;
   const double tick_age_seconds =
      MathAbs((double)((long)TimeCurrent() - (long)tick.time));
   const bool executable_tick =
      (tick.ask > tick.bid && tick.time > 0 &&
       tick_age_seconds <= MAX_EXECUTABLE_TICK_AGE_SECONDS);
   const double required = MinimumProtectionDistance("US30");
   const double executable =
      (executable_tick ? (direction > 0 ? tick.bid : tick.ask) : 0.0);
   const double retained_loss = (double)direction * (entry - target_stop);
   const double tightening = (double)direction * (target_stop - original_stop);
   const double quote_clearance =
      (executable_tick ? (double)direction * (executable - target_stop) : 0.0);
   const double price_tolerance = MathMax(1.0e-10, tick_size * 1.0e-8);
   const bool legal =
      (MathAbs(direction) == 1 && entry > 0.0 && executable_tick &&
       TradeSessionAllows("US30", TimeCurrent(), false) &&
       retained_loss >= tick_size - price_tolerance &&
       tightening >= tick_size - price_tolerance &&
       quote_clearance >= required - price_tolerance);
   if(!legal)
     {
      ClearArcRetryIntent();
      arc_pending_stop_loss = 0.0;
      ++arc_modify_retry_holds;
      ++arc_compression_refusals;
      RecordEvent(RC4_BOTH,
                  "ARC_MODIFY_RETRY_ILLEGAL_HOLD",
                  target_stop,
                  executable,
                  StringFormat("identifier=%I64u retained=%.5f tighten=%.5f clearance=%.5f required=%.5f",
                               identifier,
                               retained_loss,
                               tightening,
                               quote_clearance,
                               required));
      if(!SaveState())
         EngageSafetyStop("RC4 illegal retry HOLD could not be persisted");
      return;
     }

   execution_state.arc_modify_retry_pending = false;
   arc_modify_retry_consumed = true;
   execution_state.arc_modify_retry_after_msc = 0;
   arc_modify_retry_initial_retcode = 0;
   execution_state.arc_modify_pending = true;
   ++arc_modify_retry_attempts;
   if(!SaveState())
     {
      EngageSafetyStop("RC4 consumed retry journal could not be persisted");
      return;
     }

   trade.SetExpertMagicNumber(MAGIC_RC4_BOTH);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol("US30");
   trade.SetAsyncMode(false);
   execution_state.trade_operation_active = true;
   const bool requested =
      trade.PositionModify(ticket, target_stop, take_profit);
   const uint retcode = trade.ResultRetcode();
   const string description = trade.ResultRetcodeDescription();
   execution_state.trade_operation_active = false;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      ResolveArcNonSuccessfulModify(retcode,
                                    description,
                                    tick.time_msc,
                                    true);
      return;
     }
   ++arc_modify_retry_successes;
   if(!PositionSelectByTicket(ticket))
     {
      execution_state.pending_reconcile = true;
      if(!ReconcileBrokerState(false))
         EngageSafetyStop("RC4 retried position disappeared before confirmation");
      return;
     }
   ReconcileArcPendingModify(false);
  }


void ProcessRC4AdverseRiskCompression()
  {
   const ulong identifier = component_states[RC4_BOTH].position_identifier;
   if(identifier == 0)
     {
      if(arc_lifecycle_identifier != 0)
        {
         ClearArcLifecycleState();
         if(!SaveState())
            EngageSafetyStop("stale RC4 management state could not be cleared");
        }
      return;
     }
   if(execution_state.rc4_shadow_occupied)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("RC4 position overlaps shadow occupancy");
      return;
     }
   if(execution_state.arc_modify_retry_pending)
     {
      ProcessArcModifyRetry();
      return;
     }
   if(identifier != arc_lifecycle_identifier)
     {
      BeginArcLifecycle(identifier);
      if(arc_original_stop_loss <= 0.0 || !SaveState())
        {
         EngageSafetyStop("RC4 management lifecycle could not be initialized");
         return;
        }
     }
   if(arc_checkpoint_evaluated || portfolio_state.safety_stopped || execution_state.broker_mismatch ||
      persistence_failed)
      return;

   ulong ticket = 0;
   datetime opened_at = 0;
   if(CountOwnedPositions(RC4_BOTH, ticket, opened_at) != 1 ||
      !PositionSelectByTicket(ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER) != identifier)
      return;
   const int held_bars =
      iBarShift("US30", PERIOD_M30, opened_at, false);
   if(held_bars < ARC_RC4_CHECKPOINT_BARS)
      return;
   const datetime current_bar = iTime("US30", PERIOD_M30, 0);
   if(current_bar <= 0 || current_bar == arc_last_attempt_bar)
      return;
   arc_last_attempt_bar = current_bar;

   double market = 0.0;
   double decision = 0.0;
   double confirmation = 0.0;
   if(!ArcCalculateRC4Heads(component_states[RC4_BOTH].entry_direction,
                            market,
                            decision,
                            confirmation))
     {
      ++arc_data_unavailable;
      if(!SaveState())
         EngageSafetyStop("RC4 unavailable-checkpoint state could not be persisted");
      return;
     }

   arc_checkpoint_evaluated = true;
   ++arc_checkpoints;
   const int market_vote =
      ArcOrdinalVote(market, ARC_MARKET_LOWER, ARC_MARKET_UPPER);
   const int decision_vote =
      ArcOrdinalVote(decision, ARC_DECISION_LOWER, ARC_DECISION_UPPER);
   const int confirmation_vote =
      ArcOrdinalVote(confirmation, ARC_CONFIRM_LOWER, ARC_CONFIRM_UPPER);
   const int vote_sum = market_vote + decision_vote + confirmation_vote;
   RecordEvent(RC4_BOTH,
               "ARC_CHECKPOINT",
               (double)vote_sum,
               market,
               StringFormat("held=%d votes=%d/%d/%d heads=%.8f/%.8f/%.8f",
                            held_bars,
                            market_vote,
                            decision_vote,
                            confirmation_vote,
                            market,
                            decision,
                            confirmation));
   if(vote_sum > ARC_ADVERSE_VOTE_THRESHOLD)
     {
      if(!SaveState())
         EngageSafetyStop("RC4 checkpoint state could not be persisted");
      return;
     }
   ++arc_adverse_triggers;

   if(!PositionSelectByTicket(ticket))
     {
      ++arc_compression_refusals;
      SaveState();
      return;
     }
   const int direction = component_states[RC4_BOTH].entry_direction;
   const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   const double original_stop = arc_original_stop_loss;
   const double take_profit = PositionGetDouble(POSITION_TP);
   double new_stop = 0.0;
   MqlTick tick = {};
   if(!ArcRoundedLossSideStop(entry, original_stop, direction, new_stop) ||
      !ExecutableTick("US30", tick) ||
      !TradeSessionAllows("US30", TimeCurrent(), false))
     {
      ++arc_compression_refusals;
      SaveState();
      return;
     }
   const double tick_size =
      SymbolInfoDouble("US30", SYMBOL_TRADE_TICK_SIZE);
   const double required = MinimumProtectionDistance("US30");
   const double executable = (direction > 0 ? tick.bid : tick.ask);
   const double retained_loss = (double)direction * (entry - new_stop);
   const double tightening = (double)direction * (new_stop - original_stop);
   const double quote_clearance = (double)direction * (executable - new_stop);
   const double tolerance = MathMax(1.0e-10, tick_size * 1.0e-8);
   if(retained_loss < tick_size - tolerance ||
      tightening < tick_size - tolerance ||
      quote_clearance < required - tolerance)
     {
      ++arc_compression_refusals;
      RecordEvent(RC4_BOTH,
                  "ARC_REFUSED",
                  new_stop,
                  executable,
                  StringFormat("retained=%.5f tighten=%.5f clearance=%.5f required=%.5f",
                               retained_loss,
                               tightening,
                               quote_clearance,
                               required));
      SaveState();
      return;
     }

   execution_state.arc_modify_pending = true;
   arc_pending_stop_loss = new_stop;
   if(!SaveState())
     {
      execution_state.arc_modify_pending = false;
      arc_pending_stop_loss = 0.0;
      EngageSafetyStop("RC4 stop-modify journal could not be persisted");
      return;
     }
   trade.SetExpertMagicNumber(MAGIC_RC4_BOTH);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol("US30");
   trade.SetAsyncMode(false);
   execution_state.trade_operation_active = true;
   const bool requested = trade.PositionModify(ticket, new_stop, take_profit);
   const uint retcode = trade.ResultRetcode();
   const string result_description = trade.ResultRetcodeDescription();
   execution_state.trade_operation_active = false;
   if(!requested || !IsCompletedTradeRetcode(retcode))
     {
      ResolveArcNonSuccessfulModify(retcode,
                                    result_description,
                                    tick.time_msc,
                                    false);
      return;
     }
   if(!PositionSelectByTicket(ticket))
     {
      execution_state.pending_reconcile = true;
      if(!ReconcileBrokerState(false))
         EngageSafetyStop("RC4 modified position disappeared before confirmation");
      return;
     }
   if(!ReconcileArcPendingModify(false))
      return;
  }


void ProcessRC4Both()
  {
   EntryGateResult gate = {};
   EvaluateEntryGate(RC4_BOTH, 13, 0, gate);
   ApplyEntryGateResult(RC4_BOTH, gate);
   CommitOpportunityConsumption(RC4_BOTH, gate);
   if(!gate.enter_signal_path)
      return;
   const datetime bar = gate.current_bar;
   double feature = 0.0;
   if(!CalculateRangeCompression("US30", 4, feature))
     {
      component_states[RC4_BOTH].entry_check_result = "DATA_UNAVAILABLE";
      return;
     }
   const bool signal_passed = (MathAbs(feature) >= 1.5);
   const int direction =
      (signal_passed ? (feature > 0.0 ? 1 : -1) : 0);
   SetEntrySignalCheck(RC4_BOTH,
                       feature,
                       signal_passed,
                       direction,
                       (signal_passed
                        ? "SIGNAL_MET_ORDER_CHECK"
                        : "SIGNAL_NOT_MET"));
   if(!PersistDecision(RC4_BOTH, bar))
     {
      component_states[RC4_BOTH].entry_check_result = "PERSISTENCE_FAILED";
      return;
     }
   if(signal_passed)
     {
      OpenComponent(RC4_BOTH, direction, feature);
      if(!FinalizeDecisionJournal(RC4_BOTH, component_states[RC4_BOTH].entry_check_result))
         component_states[RC4_BOTH].entry_check_result = "PERSISTENCE_FAILED";
     }
  }


#endif
