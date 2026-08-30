#ifndef ZETA_NEXT_MODULE_13_MQH
#define ZETA_NEXT_MODULE_13_MQH

// Behavior-preserving function extraction from B70 V6R6: Persistence\ZetaStateAndEvents.mqh

void ClearEntryTracking(const int component)
  {
   component_states[component].position_identifier = 0;
   component_states[component].entry_time_server = 0;
   component_states[component].entry_direction = 0;
   component_states[component].entry_volume = 0.0;
   component_states[component].entry_feature = 0.0;
   component_states[component].entry_stop_loss = 0.0;
   component_states[component].entry_planned_risk_usd = 0.0;
   component_states[component].entry_spread_price = 0.0;
   component_states[component].entry_transaction_cost = 0.0;
   component_states[component].entry_adverse_slippage = 0.0;
   component_states[component].entry_cost_known = false;
   component_states[component].lifecycle_stop_loss_seen = false;
  }


void ClearPassivePendingTracking()
  {
   execution_state.passive_pending_order = 0;
   execution_state.passive_cancel_pending = false;
   passive_pending_expiration = 0;
   passive_pending_direction = 0;
   passive_pending_feature = 0.0;
   passive_pending_limit_price = 0.0;
   passive_pending_stop_loss = 0.0;
   passive_pending_planned_risk_usd = 0.0;
  }


void ClearDecisionJournalState()
  {
   decision_intent.journal_stage = JOURNAL_NONE;
   decision_intent.component = -1;
   decision_intent.decision_bar = 0;
   decision_intent.direction = 0;
   decision_intent.signal_value = 0.0;
   decision_intent.order_type = ORDER_TYPE_BUY;
   decision_intent.order_type_known = false;
   decision_intent.intended_price = 0.0;
   decision_intent.expiration = 0;
   decision_intent.deadline = 0;
   decision_intent.attempted_server = 0;
   decision_intent.adopted_ticket = 0;
   decision_intent.volume = 0.0;
   decision_intent.stop_loss = 0.0;
   decision_intent.planned_risk_usd = 0.0;
  }


void BeginEntryCheck(const int component,
                     const datetime bar,
                     const string result)
  {
   component_states[component].entry_check_bar = bar;
   component_states[component].entry_check_signal_known = 0;
   component_states[component].entry_check_signal_passed = -1;
   component_states[component].entry_check_signal_value = 0.0;
   component_states[component].entry_check_direction = 0;
   component_states[component].entry_check_order_price = 0.0;
   component_states[component].entry_check_volume = 0.0;
   component_states[component].entry_check_stop_loss = 0.0;
   component_states[component].entry_check_planned_risk_usd = 0.0;
   component_states[component].entry_check_result = result;
  }


void SetEntrySignalCheck(const int component,
                         const double value,
                         const bool passed,
                         const int direction,
                         const string result)
  {
   component_states[component].entry_check_signal_known = 1;
   component_states[component].entry_check_signal_passed = (passed ? 1 : 0);
   component_states[component].entry_check_signal_value = value;
   component_states[component].entry_check_direction = direction;
   component_states[component].entry_check_result = result;
   ResearchCaptureSignalContext(component,
                                component_states[component].entry_check_bar,
                                value,
                                passed,
                                direction);
  }


void ResetRuntimeState()
  {
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      component_states[component].last_decision_bar = 0;
      component_states[component].last_close_attempt_server = 0;
      component_states[component].last_processed_exit_deal = 0;
      component_states[component].last_processed_exit_time_msc = 0;
      component_states[component].lifecycle_stop_loss_seen = false;
      component_states[component].closed_trades = 0;
      component_states[component].stressed_net = 0.0;
      ClearEntryTracking(component);
      BeginEntryCheck(component, 0, "NOT_EVALUATED_SINCE_START");
     }
   state_sequence = 0;
   event_records = 0;
   event_segment_records = 0;
   event_segment = 0;
   started_utc = TimeGMT();
   last_snapshot_utc = 0;
   last_reconcile_server = 0;
   portfolio_state.sizing_server_day = 0;
   portfolio_state.day_volume_multiplier = 1;
   portfolio_state.safety_stopped = false;
   portfolio_state.stressed_balance = InpReferenceCapitalUSD;
   portfolio_state.stressed_peak = InpReferenceCapitalUSD;
   portfolio_state.stressed_maximum_closed_drawdown = 0.0;
   portfolio_state.project_realized_net = InpPriorProjectRealizedNetUSD;
   portfolio_state.account_peak_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   portfolio_state.account_maximum_drawdown = 0.0;
   persistence_failed = false;
   persistence_error_logged = false;
   execution_state.broker_mismatch = false;
    execution_state.foreign_exposure = false;
    execution_state.pending_reconcile = false;
    portfolio_state.bound_account_login = 0;
    ClearPassivePendingTracking();
   ClearDecisionJournalState();
   passive_next_entry_current_bar = 0;
   passive_last_feature_attempt_bar = 0;
   passive_last_feature_attempt_server = 0;
   passive_pending_placements = 0;
   passive_cancel_connection_deferrals = 0;
   passive_pending_expirations = 0;
   passive_completed_entries = 0;
   passive_placement_failures = 0;
   passive_stale_price_rejections = 0;
   passive_unexpected_order_outcomes = 0;
   passive_margin_calculation_failures = 0;
   passive_margin_skips = 0;
   passive_price_constraint_skips = 0;
   protection_calculation_failures = 0;
   risk_admission_skips = 0;
   protection_mismatches = 0;
   stop_loss_exits = 0;
   portfolio_state.maximum_aggregate_planned_risk_usd = 0.0;
   journal_signal_decisions = 0;
   journal_order_attempts = 0;
   journal_broker_adoptions = 0;
   journal_restart_resolutions = 0;
   ClearArcLifecycleState();
   ClearRC4ShadowState();
   arc_checkpoints = 0;
   arc_adverse_triggers = 0;
   arc_compressions_placed = 0;
   arc_compression_refusals = 0;
   arc_data_unavailable = 0;
   arc_unavailability_rows = 0;
   arc_unavailability_complete_zero_range = 0;
   arc_unavailability_complete_zero_variance = 0;
   arc_unavailability_session_boundary = 0;
   arc_unavailability_invalid_direction = 0;
   arc_unavailability_short_copy = 0;
   arc_unavailability_invalid_price = 0;
   arc_unavailability_invalid_tick = 0;
   arc_unavailability_nonfinite = 0;
   arc_unavailability_unclassified = 0;
   arc_unavailability_reason_class = "UNCLASSIFIED";
   arc_unavailability_reason_detail = "not-classified";
   arc_unavailability_requested_count = 0;
   arc_unavailability_copied_count = 0;
   arc_unavailability_first_invalid_index = -1;
   arc_unavailability_observed_value = 0.0;
   arc_unavailability_value_finite = true;
   arc_unavailability_history_complete = false;
   arc_modify_retry_intents = 0;
   arc_modify_retry_attempts = 0;
   arc_modify_retry_successes = 0;
   arc_modify_retry_adoptions = 0;
   arc_modify_retry_holds = 0;
   rc4_shadow_activations = 0;
   rc4_shadow_stop_releases = 0;
   rc4_shadow_deadline_releases = 0;
   rc4_shadow_entry_blocks = 0;
   rc4_shadow_catchup_scans = 0;
   rc4_shadow_catchup_ticks = 0;
   rc4_shadow_catchup_stop_releases = 0;
   rc4_shadow_catchup_failures = 0;
   rc4_shadow_catchup_required = false;
   rc4_shadow_catchup_failure_logged = false;
   rc4_shadow_cursor_checkpoint_observation_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_completed_bucket = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_msc = 0;
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal = 0;
   rc4_shadow_cursor_checkpoint_eligible = 0;
   rc4_shadow_cursor_checkpoint_persisted = 0;
   rc4_shadow_cursor_checkpoint_save_failures = 0;
   rc4_shadow_cursor_checkpoint_readback_failures = 0;
   rc4_shadow_cursor_checkpoint_event_failures = 0;
   rc4_shadow_cursor_checkpoint_duplicate_bucket_failures = 0;
   rc4_shadow_cursor_checkpoint_regressions = 0;
   rc4_shadow_cursor_checkpoint_pending = false;
   rc4_shadow_activation_seal_eligible = 0;
   rc4_shadow_activation_seal_sealed = 0;
   rc4_shadow_activation_seal_pending_count = 0;
   rc4_shadow_activation_seal_save_attempts = 0;
   rc4_shadow_activation_seal_save_failures = 0;
   rc4_shadow_activation_seal_readbacks = 0;
   rc4_shadow_activation_seal_readback_failures = 0;
   rc4_shadow_activation_seal_failures = 0;
   rc4_shadow_activation_seal_ambiguities = 0;
   rc4_shadow_activation_last_sealed_msc = 0;
   rc4_shadow_activation_last_sealed_ordinal = 0;
   rc4_shadow_activation_pre_boundary_consumed = 0;
   tester_dispatched_ticks = 0;
   tester_transaction_dispatches = 0;
   tester_clock_dispatches = 0;
   tester_retry_dispatches = 0;
   tester_last_m15_slot = -1;
   tester_data_retry_active = false;
  }


void MarkPersistenceFailure(const string detail)
  {
   persistence_failed = true;
   if(persistence_error_logged)
      return;
   persistence_error_logged = true;
   PrintFormat("%s persistence failure; new entries blocked: %s error=%d",
               EXECUTION_VERSION, detail, GetLastError());
  }


void WriteComponentState(const int handle, const int component)
  {
   FileWrite(handle,
             component_definitions[component].id,
             (long)component_states[component].last_decision_bar,
             (long)component_states[component].last_processed_exit_deal,
             component_states[component].last_processed_exit_time_msc,
             (component_states[component].lifecycle_stop_loss_seen ? 1 : 0),
             (long)component_states[component].position_identifier,
             (long)component_states[component].entry_time_server,
             component_states[component].entry_direction,
              component_states[component].entry_volume,
              component_states[component].entry_feature,
              component_states[component].entry_stop_loss,
              component_states[component].entry_planned_risk_usd,
              component_states[component].entry_spread_price,
             component_states[component].entry_transaction_cost,
             component_states[component].entry_adverse_slippage,
             (component_states[component].entry_cost_known ? 1 : 0),
             component_states[component].closed_trades,
             component_states[component].stressed_net);
  }


void ReadComponentState(const int handle,
                        const int component,
                        string &component_id)
  {
   component_id = FileReadString(handle);
   component_states[component].last_decision_bar =
      (datetime)((long)FileReadNumber(handle));
   component_states[component].last_processed_exit_deal =
      (ulong)((long)FileReadNumber(handle));
   component_states[component].last_processed_exit_time_msc =
      (long)FileReadNumber(handle);
   component_states[component].lifecycle_stop_loss_seen =
      ((int)FileReadNumber(handle) == 1);
   component_states[component].position_identifier =
      (ulong)((long)FileReadNumber(handle));
   component_states[component].entry_time_server =
      (datetime)((long)FileReadNumber(handle));
   component_states[component].entry_direction = (int)FileReadNumber(handle);
   component_states[component].entry_volume = FileReadNumber(handle);
   component_states[component].entry_feature = FileReadNumber(handle);
   component_states[component].entry_stop_loss = FileReadNumber(handle);
   component_states[component].entry_planned_risk_usd = FileReadNumber(handle);
   component_states[component].entry_spread_price = FileReadNumber(handle);
   component_states[component].entry_transaction_cost = FileReadNumber(handle);
   component_states[component].entry_adverse_slippage = FileReadNumber(handle);
   component_states[component].entry_cost_known = ((int)FileReadNumber(handle) == 1);
   component_states[component].closed_trades = (long)FileReadNumber(handle);
   component_states[component].stressed_net = FileReadNumber(handle);
  }


bool ValidateLoadedState()
  {
   if(state_sequence < 0 || event_records < 0 ||
      event_segment_records < 0 ||
      event_segment_records > InpEventCapacity ||
      (event_segment != 0 && event_segment != 1) ||
      started_utc <= 0 || portfolio_state.day_volume_multiplier < 1 ||
       !MathIsValidNumber(portfolio_state.stressed_balance) ||
       !MathIsValidNumber(portfolio_state.stressed_peak) ||
       !MathIsValidNumber(portfolio_state.stressed_maximum_closed_drawdown) ||
       !MathIsValidNumber(portfolio_state.project_realized_net) ||
       MathAbs(portfolio_state.project_realized_net) > 1.0e9 ||
      !MathIsValidNumber(portfolio_state.account_peak_equity) ||
      !MathIsValidNumber(portfolio_state.account_maximum_drawdown) ||
      portfolio_state.stressed_peak <= 0.0 || portfolio_state.stressed_maximum_closed_drawdown < 0.0 ||
      portfolio_state.account_peak_equity < 0.0 || portfolio_state.account_maximum_drawdown < 0.0 ||
       passive_pending_expiration < 0 ||
       passive_next_entry_current_bar < 0 ||
       !MathIsValidNumber(passive_pending_feature) ||
       !MathIsValidNumber(passive_pending_limit_price) ||
       !MathIsValidNumber(passive_pending_stop_loss) ||
       !MathIsValidNumber(passive_pending_planned_risk_usd) ||
       passive_pending_stop_loss < 0.0 ||
       passive_pending_planned_risk_usd < 0.0 ||
       passive_pending_placements < 0 ||
       passive_cancel_connection_deferrals < 0 ||
       passive_pending_expirations < 0 ||
      passive_completed_entries < 0 || passive_placement_failures < 0 ||
      passive_stale_price_rejections < 0 ||
      passive_unexpected_order_outcomes < 0 ||
      passive_margin_calculation_failures < 0 || passive_margin_skips < 0 ||
       passive_price_constraint_skips < 0 ||
       protection_calculation_failures < 0 || risk_admission_skips < 0 ||
       protection_mismatches < 0 || stop_loss_exits < 0 ||
       !MathIsValidNumber(portfolio_state.maximum_aggregate_planned_risk_usd) ||
       portfolio_state.maximum_aggregate_planned_risk_usd < 0.0 ||
       !MathIsValidNumber(decision_intent.signal_value) ||
       decision_intent.journal_stage < JOURNAL_NONE ||
       decision_intent.journal_stage > JOURNAL_BROKER_STATE_ADOPTED ||
       journal_signal_decisions < 0 || journal_order_attempts < 0 ||
       journal_broker_adoptions < 0 || journal_restart_resolutions < 0 ||
       arc_last_attempt_bar < 0 ||
       !MathIsValidNumber(arc_original_stop_loss) ||
       arc_original_stop_loss < 0.0 ||
       !MathIsValidNumber(arc_pending_stop_loss) ||
       arc_pending_stop_loss < 0.0 ||
       execution_state.arc_modify_retry_after_msc < 0 ||
       arc_modify_retry_intents < 0 || arc_modify_retry_attempts < 0 ||
       arc_modify_retry_successes < 0 ||
       arc_modify_retry_adoptions < 0 || arc_modify_retry_holds < 0 ||
       arc_modify_retry_attempts > arc_modify_retry_intents ||
       arc_modify_retry_successes > arc_modify_retry_attempts ||
       arc_checkpoints < 0 || arc_adverse_triggers < 0 ||
       arc_compressions_placed < 0 || arc_compression_refusals < 0 ||
       arc_data_unavailable < 0 ||
       rc4_shadow_entry_time < 0 ||
       !MathIsValidNumber(rc4_shadow_original_stop_loss) ||
       rc4_shadow_original_stop_loss < 0.0 ||
       rc4_shadow_last_observed_msc < 0 ||
       rc4_shadow_cursor_ordinal < 0 ||
       rc4_shadow_activations < 0 || rc4_shadow_stop_releases < 0 ||
       rc4_shadow_deadline_releases < 0 || rc4_shadow_entry_blocks < 0 ||
       rc4_shadow_catchup_scans < 0 || rc4_shadow_catchup_ticks < 0 ||
       rc4_shadow_catchup_stop_releases < 0 ||
       rc4_shadow_catchup_failures < 0 ||
       rc4_shadow_cursor_checkpoint_observation_bucket < 0 ||
       rc4_shadow_cursor_checkpoint_last_completed_bucket < 0 ||
       rc4_shadow_cursor_checkpoint_last_persisted_msc < 0 ||
       rc4_shadow_cursor_checkpoint_last_persisted_ordinal < 0 ||
       rc4_shadow_cursor_checkpoint_eligible < 0 ||
       rc4_shadow_cursor_checkpoint_persisted < 0 ||
       rc4_shadow_cursor_checkpoint_persisted >
          rc4_shadow_cursor_checkpoint_eligible ||
       rc4_shadow_cursor_checkpoint_save_failures < 0 ||
       rc4_shadow_cursor_checkpoint_readback_failures < 0 ||
       rc4_shadow_cursor_checkpoint_event_failures < 0 ||
       rc4_shadow_cursor_checkpoint_duplicate_bucket_failures < 0 ||
       rc4_shadow_cursor_checkpoint_regressions < 0 ||
       rc4_shadow_activation_deal_time_msc < 0 ||
       !MathIsValidNumber(rc4_shadow_activation_deal_price) ||
       rc4_shadow_activation_deal_price < 0.0 ||
       !MathIsValidNumber(rc4_shadow_activation_protected_stop) ||
       rc4_shadow_activation_protected_stop < 0.0 ||
       rc4_shadow_activation_sampled_time < 0 ||
       rc4_shadow_activation_sampled_time_msc < 0 ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_bid) ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_ask) ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_last) ||
       !MathIsValidNumber(rc4_shadow_activation_sampled_volume_real) ||
       rc4_shadow_activation_sampled_bid < 0.0 ||
       rc4_shadow_activation_sampled_ask < 0.0 ||
       rc4_shadow_activation_sampled_last < 0.0 ||
       rc4_shadow_activation_sampled_volume_real < 0.0 ||
       rc4_shadow_activation_boundary_msc < 0 ||
       rc4_shadow_activation_boundary_ordinal < 0 ||
       rc4_shadow_activation_seal_eligible < 0 ||
       rc4_shadow_activation_seal_sealed < 0 ||
       rc4_shadow_activation_seal_sealed >
          rc4_shadow_activation_seal_eligible ||
       rc4_shadow_activation_seal_pending_count < 0 ||
       rc4_shadow_activation_seal_pending_count >
          rc4_shadow_activation_seal_eligible ||
       rc4_shadow_activation_seal_save_attempts < 0 ||
       rc4_shadow_activation_seal_save_failures < 0 ||
       rc4_shadow_activation_seal_save_failures >
          rc4_shadow_activation_seal_save_attempts ||
       rc4_shadow_activation_seal_readbacks < 0 ||
       rc4_shadow_activation_seal_readbacks >
          rc4_shadow_activation_seal_save_attempts ||
       rc4_shadow_activation_seal_readback_failures < 0 ||
       rc4_shadow_activation_seal_readback_failures >
          rc4_shadow_activation_seal_readbacks ||
       rc4_shadow_activation_seal_failures < 0 ||
       rc4_shadow_activation_seal_ambiguities < 0 ||
       rc4_shadow_activation_last_sealed_msc < 0 ||
       rc4_shadow_activation_last_sealed_ordinal < 0 ||
       ((rc4_shadow_activation_last_sealed_msc == 0) !=
        (rc4_shadow_activation_last_sealed_ordinal == 0)) ||
       rc4_shadow_activation_pre_boundary_consumed != 0 ||
       (tester_mode && portfolio_state.bound_account_login != 0) ||
       (!tester_mode && portfolio_state.bound_account_login <= 0))
      return(false);
   if(arc_lifecycle_identifier == 0)
     {
      if(arc_last_attempt_bar != 0 || arc_checkpoint_evaluated ||
         arc_lifecycle_compressed || arc_original_stop_loss != 0.0 ||
         execution_state.arc_modify_pending || arc_pending_stop_loss != 0.0 ||
         execution_state.arc_modify_retry_pending || arc_modify_retry_consumed ||
         execution_state.arc_modify_retry_after_msc != 0 ||
         arc_modify_retry_initial_retcode != 0)
         return(false);
     }
   else
     {
      if(component_states[RC4_BOTH].position_identifier !=
         arc_lifecycle_identifier || arc_original_stop_loss <= 0.0 ||
         (arc_lifecycle_compressed && !arc_checkpoint_evaluated))
         return(false);
      if(execution_state.arc_modify_pending)
        {
         if(!arc_checkpoint_evaluated || arc_lifecycle_compressed ||
            arc_pending_stop_loss <= 0.0)
            return(false);
        }
      if(execution_state.arc_modify_retry_pending)
        {
         if(execution_state.arc_modify_pending || arc_modify_retry_consumed ||
            !arc_checkpoint_evaluated || arc_lifecycle_compressed ||
            arc_pending_stop_loss <= 0.0 ||
            execution_state.arc_modify_retry_after_msc <= 0 ||
            !IsArcTransientModifyRetcode(arc_modify_retry_initial_retcode))
            return(false);
        }
      else if(!execution_state.arc_modify_pending && arc_pending_stop_loss != 0.0)
         return(false);
      if(!execution_state.arc_modify_retry_pending &&
         (execution_state.arc_modify_retry_after_msc != 0 ||
          arc_modify_retry_initial_retcode != 0))
         return(false);
      if(arc_modify_retry_consumed && execution_state.arc_modify_retry_pending)
         return(false);
     }
   if(execution_state.rc4_shadow_occupied)
     {
      if(rc4_shadow_source_identifier == 0 ||
         rc4_shadow_entry_time <= 0 ||
         MathAbs(rc4_shadow_direction) != 1 ||
         rc4_shadow_original_stop_loss <= 0.0 ||
         rc4_shadow_last_observed_msc <= 0 ||
         rc4_shadow_cursor_ordinal < 0 ||
         rc4_shadow_activation_deal_ticket == 0 ||
         rc4_shadow_activation_deal_time_msc <= 0 ||
         rc4_shadow_activation_deal_price <= 0.0 ||
         rc4_shadow_activation_deal_reason != (int)DEAL_REASON_SL ||
         rc4_shadow_activation_protected_stop <= 0.0 ||
         (execution_state.rc4_shadow_activation_sealed ==
          execution_state.rc4_shadow_activation_seal_pending) ||
         (execution_state.rc4_shadow_activation_seal_pending &&
          (rc4_shadow_activation_boundary_msc != 0 ||
           rc4_shadow_activation_boundary_ordinal != 0 ||
           rc4_shadow_last_observed_msc !=
              rc4_shadow_activation_deal_time_msc ||
           rc4_shadow_cursor_ordinal != 0)) ||
         (execution_state.rc4_shadow_activation_sealed &&
          (rc4_shadow_activation_boundary_msc !=
              rc4_shadow_activation_deal_time_msc ||
           rc4_shadow_activation_boundary_ordinal <= 0 ||
           rc4_shadow_last_observed_msc <
              rc4_shadow_activation_boundary_msc ||
           (rc4_shadow_last_observed_msc ==
               rc4_shadow_activation_boundary_msc &&
            rc4_shadow_cursor_ordinal <
               rc4_shadow_activation_boundary_ordinal))) ||
         (rc4_shadow_activation_sampled_tick_known &&
          (rc4_shadow_activation_sampled_time <= 0 ||
           rc4_shadow_activation_sampled_time_msc <= 0 ||
           rc4_shadow_activation_sampled_bid <= 0.0 ||
           rc4_shadow_activation_sampled_ask <
              rc4_shadow_activation_sampled_bid)) ||
         rc4_shadow_cursor_checkpoint_observation_bucket <= 0 ||
         (rc4_shadow_cursor_checkpoint_last_completed_bucket > 0 &&
          rc4_shadow_cursor_checkpoint_last_completed_bucket >=
             rc4_shadow_cursor_checkpoint_observation_bucket) ||
         ((rc4_shadow_cursor_checkpoint_last_persisted_msc == 0) !=
          (rc4_shadow_cursor_checkpoint_last_persisted_ordinal == 0)) ||
         rc4_shadow_cursor_checkpoint_last_persisted_msc >
            rc4_shadow_last_observed_msc ||
         (rc4_shadow_cursor_checkpoint_last_persisted_msc ==
             rc4_shadow_last_observed_msc &&
          rc4_shadow_cursor_checkpoint_last_persisted_ordinal >
             rc4_shadow_cursor_ordinal) ||
         component_states[RC4_BOTH].position_identifier != 0 ||
         arc_lifecycle_identifier != 0)
         return(false);
     }
   else if(rc4_shadow_source_identifier != 0 ||
           rc4_shadow_entry_time != 0 || rc4_shadow_direction != 0 ||
           rc4_shadow_original_stop_loss != 0.0 ||
           rc4_shadow_last_observed_msc != 0 ||
           rc4_shadow_cursor_ordinal != 0 ||
           rc4_shadow_cursor_checkpoint_observation_bucket != 0 ||
           rc4_shadow_cursor_checkpoint_last_completed_bucket != 0 ||
           rc4_shadow_cursor_checkpoint_last_persisted_msc != 0 ||
           rc4_shadow_cursor_checkpoint_last_persisted_ordinal != 0 ||
           rc4_shadow_cursor_checkpoint_pending ||
           execution_state.rc4_shadow_activation_sealed ||
           execution_state.rc4_shadow_activation_seal_pending ||
           rc4_shadow_activation_seal_failure_logged ||
           rc4_shadow_activation_deal_ticket != 0 ||
           rc4_shadow_activation_deal_time_msc != 0 ||
           rc4_shadow_activation_deal_price != 0.0 ||
           rc4_shadow_activation_deal_reason != 0 ||
           rc4_shadow_activation_protected_stop != 0.0 ||
           rc4_shadow_activation_sampled_tick_known ||
           rc4_shadow_activation_sampled_time != 0 ||
           rc4_shadow_activation_sampled_time_msc != 0 ||
           rc4_shadow_activation_sampled_bid != 0.0 ||
           rc4_shadow_activation_sampled_ask != 0.0 ||
           rc4_shadow_activation_sampled_last != 0.0 ||
           rc4_shadow_activation_sampled_volume != 0 ||
           rc4_shadow_activation_sampled_volume_real != 0.0 ||
           rc4_shadow_activation_sampled_flags != 0 ||
           rc4_shadow_activation_boundary_msc != 0 ||
           rc4_shadow_activation_boundary_ordinal != 0)
      return(false);
   if(decision_intent.journal_stage == JOURNAL_NONE)
     {
      if(decision_intent.component != -1 || decision_intent.decision_bar != 0 ||
         decision_intent.direction != 0 ||
         decision_intent.signal_value != 0.0 ||
         decision_intent.deadline != 0 ||
         decision_intent.attempted_server != 0 ||
         decision_intent.adopted_ticket != 0)
         return(false);
     }
   else
     {
      if(decision_intent.component < 0 ||
         decision_intent.component >= COMPONENT_COUNT ||
         decision_intent.decision_bar <= 0 ||
         MathAbs(decision_intent.direction) != 1 ||
         decision_intent.deadline < decision_intent.decision_bar ||
         component_states[decision_intent.component].last_decision_bar <
         decision_intent.decision_bar)
         return(false);
      if(decision_intent.journal_stage == JOURNAL_SIGNAL_DECIDED &&
         (decision_intent.attempted_server != 0 ||
          decision_intent.adopted_ticket != 0))
         return(false);
      if(decision_intent.journal_stage == JOURNAL_ORDER_ATTEMPTED &&
         (decision_intent.attempted_server <= 0 ||
          decision_intent.adopted_ticket != 0))
         return(false);
      if(decision_intent.journal_stage == JOURNAL_BROKER_STATE_ADOPTED &&
         (decision_intent.attempted_server <= 0 ||
          decision_intent.adopted_ticket == 0))
         return(false);
     }
   if(execution_state.passive_pending_order > 0)
     {
      if(passive_pending_expiration <= 0 ||
          MathAbs(passive_pending_direction) != 1 ||
          passive_pending_limit_price <= 0.0 ||
          passive_pending_stop_loss <= 0.0 ||
          passive_pending_planned_risk_usd <= 0.0 ||
          (execution_state.passive_cancel_pending &&
           passive_cancel_connection_deferrals <= 0) ||
          component_states[US100_PASSIVE_LIMIT].position_identifier > 0)
         return(false);
     }
   else if(execution_state.passive_cancel_pending ||
            passive_pending_expiration != 0 ||
            passive_pending_direction != 0 ||
            passive_pending_feature != 0.0 ||
            passive_pending_limit_price != 0.0 ||
            passive_pending_stop_loss != 0.0 ||
            passive_pending_planned_risk_usd != 0.0)
      return(false);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
     {
      if(component_states[component].last_decision_bar < 0 ||
         component_states[component].last_processed_exit_time_msc < 0 ||
         component_states[component].entry_time_server < 0 ||
         component_states[component].closed_trades < 0 ||
          !MathIsValidNumber(component_states[component].entry_volume) ||
          !MathIsValidNumber(component_states[component].entry_feature) ||
          !MathIsValidNumber(component_states[component].entry_stop_loss) ||
          !MathIsValidNumber(component_states[component].entry_planned_risk_usd) ||
          !MathIsValidNumber(component_states[component].entry_spread_price) ||
         !MathIsValidNumber(component_states[component].entry_transaction_cost) ||
         !MathIsValidNumber(component_states[component].entry_adverse_slippage) ||
         !MathIsValidNumber(component_states[component].stressed_net) ||
          component_states[component].entry_volume < 0.0 ||
          component_states[component].entry_stop_loss < 0.0 ||
          component_states[component].entry_planned_risk_usd < 0.0 ||
          component_states[component].entry_spread_price < 0.0 ||
         component_states[component].entry_adverse_slippage < 0.0)
         return(false);
      if(component_states[component].position_identifier > 0 &&
         (component_states[component].entry_time_server <= 0 ||
           MathAbs(component_states[component].entry_direction) != 1 ||
           component_states[component].entry_volume <= 0.0 ||
           component_states[component].entry_stop_loss <= 0.0 ||
           component_states[component].entry_planned_risk_usd <= 0.0))
          return(false);
      if(component_states[component].position_identifier > 0)
        {
         long loaded_steps = 0;
         if(!VolumeToSteps(component_definitions[component].symbol,
                           component_states[component].entry_volume,
                           loaded_steps))
            return(false);
        }
       if(component_states[component].position_identifier == 0 &&
          (component_states[component].entry_stop_loss != 0.0 ||
           component_states[component].entry_planned_risk_usd != 0.0 ||
           component_states[component].lifecycle_stop_loss_seen))
          return(false);
     }
   return(true);
  }


int OpenFileWithRetry(const string path,
                      const int flags,
                      const short delimiter)
  {
   for(int attempt = 0; attempt < FILE_OPEN_ATTEMPTS; ++attempt)
     {
      ResetLastError();
      const int handle = FileOpen(path, flags, delimiter);
      if(handle != INVALID_HANDLE)
         return(handle);
      if(attempt + 1 < FILE_OPEN_ATTEMPTS)
         Sleep(FILE_RETRY_DELAY_MS);
     }
   return(INVALID_HANDLE);
  }


bool ReadState(const string path, long &loaded_sequence)
  {
   const int handle = OpenFileWithRetry(path,
                                        FILE_READ | FILE_CSV | FILE_ANSI,
                                        ',');
   if(handle == INVALID_HANDLE)
      return(false);
   const string marker = FileReadString(handle);
   const string execution_version = FileReadString(handle);
    const string economic_version = FileReadString(handle);
    const string portfolio_id = FileReadString(handle);
    const string fingerprint = FileReadString(handle);
    const string execution_fingerprint = FileReadString(handle);
    portfolio_state.bound_account_login = (long)FileReadNumber(handle);
   state_sequence = (long)FileReadNumber(handle);
   event_records = (long)FileReadNumber(handle);
   event_segment_records = (long)FileReadNumber(handle);
   event_segment = (int)FileReadNumber(handle);
   portfolio_state.stressed_balance = FileReadNumber(handle);
   portfolio_state.stressed_peak = FileReadNumber(handle);
   portfolio_state.stressed_maximum_closed_drawdown = FileReadNumber(handle);
   const double prior_project_realized_net = FileReadNumber(handle);
   portfolio_state.project_realized_net = FileReadNumber(handle);
   portfolio_state.sizing_server_day = (datetime)((long)FileReadNumber(handle));
   portfolio_state.day_volume_multiplier = (int)FileReadNumber(handle);
   portfolio_state.safety_stopped = ((int)FileReadNumber(handle) == 1);
   started_utc = (datetime)((long)FileReadNumber(handle));
   last_snapshot_utc = (datetime)((long)FileReadNumber(handle));
   portfolio_state.account_peak_equity = FileReadNumber(handle);
   portfolio_state.account_maximum_drawdown = FileReadNumber(handle);
   execution_state.passive_pending_order =
      (ulong)((long)FileReadNumber(handle));
   execution_state.passive_cancel_pending = ((int)FileReadNumber(handle) == 1);
   passive_pending_expiration =
      (datetime)((long)FileReadNumber(handle));
   passive_pending_direction = (int)FileReadNumber(handle);
   passive_pending_feature = FileReadNumber(handle);
   passive_pending_limit_price = FileReadNumber(handle);
   passive_pending_stop_loss = FileReadNumber(handle);
   passive_pending_planned_risk_usd = FileReadNumber(handle);
   passive_next_entry_current_bar =
      (datetime)((long)FileReadNumber(handle));
   passive_pending_placements = (long)FileReadNumber(handle);
   passive_cancel_connection_deferrals = (long)FileReadNumber(handle);
   passive_pending_expirations = (long)FileReadNumber(handle);
   passive_completed_entries = (long)FileReadNumber(handle);
   passive_placement_failures = (long)FileReadNumber(handle);
   passive_stale_price_rejections = (long)FileReadNumber(handle);
   passive_unexpected_order_outcomes = (long)FileReadNumber(handle);
   passive_margin_calculation_failures = (long)FileReadNumber(handle);
   passive_margin_skips = (long)FileReadNumber(handle);
   passive_price_constraint_skips = (long)FileReadNumber(handle);
   protection_calculation_failures = (long)FileReadNumber(handle);
   risk_admission_skips = (long)FileReadNumber(handle);
   protection_mismatches = (long)FileReadNumber(handle);
   stop_loss_exits = (long)FileReadNumber(handle);
   portfolio_state.maximum_aggregate_planned_risk_usd = FileReadNumber(handle);
   decision_intent.journal_stage = (int)FileReadNumber(handle);
   decision_intent.component = (int)FileReadNumber(handle);
   decision_intent.decision_bar =
      (datetime)((long)FileReadNumber(handle));
   decision_intent.direction = (int)FileReadNumber(handle);
   decision_intent.signal_value = FileReadNumber(handle);
   decision_intent.deadline =
      (datetime)((long)FileReadNumber(handle));
   decision_intent.attempted_server =
      (datetime)((long)FileReadNumber(handle));
   decision_intent.adopted_ticket =
      (ulong)((long)FileReadNumber(handle));
   journal_signal_decisions = (long)FileReadNumber(handle);
   journal_order_attempts = (long)FileReadNumber(handle);
   journal_broker_adoptions = (long)FileReadNumber(handle);
   journal_restart_resolutions = (long)FileReadNumber(handle);
   arc_lifecycle_identifier =
      (ulong)((long)FileReadNumber(handle));
   arc_last_attempt_bar =
      (datetime)((long)FileReadNumber(handle));
   arc_checkpoint_evaluated = ((int)FileReadNumber(handle) == 1);
   arc_lifecycle_compressed = ((int)FileReadNumber(handle) == 1);
   arc_original_stop_loss = FileReadNumber(handle);
   arc_checkpoints = (long)FileReadNumber(handle);
   arc_adverse_triggers = (long)FileReadNumber(handle);
   arc_compressions_placed = (long)FileReadNumber(handle);
   arc_compression_refusals = (long)FileReadNumber(handle);
   arc_data_unavailable = (long)FileReadNumber(handle);
   execution_state.rc4_shadow_occupied = ((int)FileReadNumber(handle) == 1);
   rc4_shadow_source_identifier =
      (ulong)((long)FileReadNumber(handle));
   rc4_shadow_entry_time =
      (datetime)((long)FileReadNumber(handle));
   rc4_shadow_direction = (int)FileReadNumber(handle);
   rc4_shadow_original_stop_loss = FileReadNumber(handle);
   rc4_shadow_last_observed_msc = (long)FileReadNumber(handle);
   rc4_shadow_cursor_ordinal = (long)FileReadNumber(handle);
   rc4_shadow_activations = (long)FileReadNumber(handle);
   rc4_shadow_stop_releases = (long)FileReadNumber(handle);
   rc4_shadow_deadline_releases = (long)FileReadNumber(handle);
   rc4_shadow_entry_blocks = (long)FileReadNumber(handle);
   rc4_shadow_catchup_scans = (long)FileReadNumber(handle);
   rc4_shadow_catchup_ticks = (long)FileReadNumber(handle);
   rc4_shadow_catchup_stop_releases = (long)FileReadNumber(handle);
   rc4_shadow_catchup_failures = (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_observation_bucket =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_last_completed_bucket =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_last_persisted_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_last_persisted_ordinal =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_eligible = (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_persisted = (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_save_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_readback_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_event_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_duplicate_bucket_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_regressions =
      (long)FileReadNumber(handle);
   rc4_shadow_cursor_checkpoint_pending =
      ((int)FileReadNumber(handle) == 1);
   execution_state.arc_modify_pending = ((int)FileReadNumber(handle) == 1);
   arc_pending_stop_loss = FileReadNumber(handle);
   execution_state.arc_modify_retry_pending = ((int)FileReadNumber(handle) == 1);
   arc_modify_retry_consumed = ((int)FileReadNumber(handle) == 1);
   execution_state.arc_modify_retry_after_msc = (long)FileReadNumber(handle);
   arc_modify_retry_initial_retcode = (uint)FileReadNumber(handle);
   arc_modify_retry_intents = (long)FileReadNumber(handle);
   arc_modify_retry_attempts = (long)FileReadNumber(handle);
   arc_modify_retry_successes = (long)FileReadNumber(handle);
   arc_modify_retry_adoptions = (long)FileReadNumber(handle);
   arc_modify_retry_holds = (long)FileReadNumber(handle);
   execution_state.rc4_shadow_activation_sealed =
      ((int)FileReadNumber(handle) == 1);
   execution_state.rc4_shadow_activation_seal_pending =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_seal_failure_logged =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_deal_ticket =
      (ulong)((long)FileReadNumber(handle));
   rc4_shadow_activation_deal_time_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_deal_price = FileReadNumber(handle);
   rc4_shadow_activation_deal_reason =
      (int)FileReadNumber(handle);
   rc4_shadow_activation_protected_stop = FileReadNumber(handle);
   rc4_shadow_activation_sampled_tick_known =
      ((int)FileReadNumber(handle) == 1);
   rc4_shadow_activation_sampled_time =
      (datetime)((long)FileReadNumber(handle));
   rc4_shadow_activation_sampled_time_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_sampled_bid = FileReadNumber(handle);
   rc4_shadow_activation_sampled_ask = FileReadNumber(handle);
   rc4_shadow_activation_sampled_last = FileReadNumber(handle);
   rc4_shadow_activation_sampled_volume =
      (ulong)((long)FileReadNumber(handle));
   rc4_shadow_activation_sampled_volume_real =
      FileReadNumber(handle);
   rc4_shadow_activation_sampled_flags =
      (uint)FileReadNumber(handle);
   rc4_shadow_activation_boundary_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_boundary_ordinal =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_eligible =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_sealed =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_pending_count =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_save_attempts =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_save_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_readbacks =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_readback_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_failures =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_seal_ambiguities =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_last_sealed_msc =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_last_sealed_ordinal =
      (long)FileReadNumber(handle);
   rc4_shadow_activation_pre_boundary_consumed =
      (long)FileReadNumber(handle);
   string component_ids[COMPONENT_COUNT];
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      ReadComponentState(handle, component, component_ids[component]);
   const string end_marker = FileReadString(handle);
   FileClose(handle);
   if(marker != STATE_MARKER || end_marker != STATE_MARKER ||
       execution_version != EXECUTION_VERSION ||
       economic_version != ECONOMIC_VERSION || portfolio_id != PORTFOLIO_ID ||
        fingerprint != ECONOMIC_FINGERPRINT ||
        execution_fingerprint != EXECUTION_FINGERPRINT ||
        (!tester_mode &&
         portfolio_state.bound_account_login !=
         (long)AccountInfoInteger(ACCOUNT_LOGIN)) ||
        MathAbs(prior_project_realized_net -
               InpPriorProjectRealizedNetUSD) > 1.0e-8)
      return(false);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      if(component_ids[component] != component_definitions[component].id)
         return(false);
   if(!ValidateLoadedState())
      return(false);
   loaded_sequence = state_sequence;
   return(true);
  }


bool LoadState()
  {
   long sequence_a = -1;
   long sequence_b = -1;
   const bool valid_a = ReadState(STATE_PATH_A, sequence_a);
   ResetRuntimeState();
   const bool valid_b = ReadState(STATE_PATH_B, sequence_b);
   ResetRuntimeState();
   const string selected =
      (valid_a && (!valid_b || sequence_a >= sequence_b)
       ? STATE_PATH_A : (valid_b ? STATE_PATH_B : ""));
   if(selected == "")
      return(false);
   long selected_sequence = -1;
   if(!ReadState(selected, selected_sequence))
      return(false);
   rc4_shadow_catchup_required = execution_state.rc4_shadow_occupied;
   rc4_shadow_catchup_failure_logged = false;
   return(true);
  }


bool WriteCurrentSnapshotFile(const string path)
  {
   const int handle = OpenFileWithRetry(path,
                                        FILE_WRITE | FILE_CSV | FILE_ANSI |
                                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                                        ',');
   if(handle == INVALID_HANDLE)
      return(false);
   FileWriteString(handle, "schema_version,release_id,project_id,");
   FileWrite(handle,
              "utc", "server_time", "execution_version", "economic_version",
               "portfolio_id", "state_sequence", "new_entries_input",
              "new_entries_effective", "safety_stopped",
              "persistence_failed", "broker_mismatch", "foreign_exposure",
              "terminal_connected", "account_binding_configured",
              "account_identity_match",
              "stressed_balance", "stressed_max_closed_drawdown",
             "project_realized_net", "project_stage_balance",
             "account_balance", "account_equity", "account_margin",
              "account_max_drawdown", "passive_pending_order",
              "passive_cancel_pending",
             "passive_pending_expiration", "passive_pending_direction",
              "passive_pending_limit", "passive_pending_stop",
              "passive_pending_planned_risk", "passive_placements",
              "passive_cancel_connection_deferrals",
              "passive_expirations", "passive_entries",
              "passive_stale_rejections", "protection_calc_failures",
              "risk_admission_skips", "protection_mismatches",
              "stop_loss_exits", "aggregate_planned_risk",
              "maximum_aggregate_planned_risk",
              "decision_journal_stage", "decision_journal_component",
              "decision_journal_bar", "decision_journal_direction",
              "decision_journal_feature", "decision_journal_deadline",
              "decision_journal_attempted", "decision_journal_ticket",
              "journal_signal_decisions", "journal_order_attempts",
              "journal_broker_adoptions", "journal_restart_resolutions",
               "arc_lifecycle_identifier", "arc_modify_pending",
               "arc_pending_stop", "arc_lifecycle_compressed",
               "arc_original_stop",
              "rc4_shadow_occupied", "rc4_shadow_source_identifier",
              "rc4_shadow_entry_time", "rc4_shadow_direction",
              "rc4_shadow_original_stop");
   const bool entries_effective = NewEntriesOperationallyAllowed();
   FileWriteString(handle,
                   SCHEMA_VERSION + "," + RELEASE_ID + "," +
                   PROJECT_ID + ",");
   FileWrite(handle,
             TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS),
             TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
              EXECUTION_VERSION,
              ECONOMIC_VERSION,
              PORTFOLIO_ID,
             state_sequence,
             (InpAllowNewEntries ? 1 : 0),
             (entries_effective ? 1 : 0),
             (portfolio_state.safety_stopped ? 1 : 0),
              (persistence_failed ? 1 : 0),
              (execution_state.broker_mismatch ? 1 : 0),
              (execution_state.foreign_exposure ? 1 : 0),
              (TerminalInfoInteger(TERMINAL_CONNECTED) ? 1 : 0),
              (InpExpectedLiveAccountLogin > 0 ? 1 : 0),
              (LiveAccountIdentityCompatible() ? 1 : 0),
              portfolio_state.stressed_balance,
             portfolio_state.stressed_maximum_closed_drawdown,
             portfolio_state.project_realized_net,
             InpReferenceCapitalUSD + portfolio_state.project_realized_net,
             AccountInfoDouble(ACCOUNT_BALANCE),
             AccountInfoDouble(ACCOUNT_EQUITY),
             AccountInfoDouble(ACCOUNT_MARGIN),
             portfolio_state.account_maximum_drawdown,
              (long)execution_state.passive_pending_order,
              (execution_state.passive_cancel_pending ? 1 : 0),
             (long)passive_pending_expiration,
              passive_pending_direction,
              passive_pending_limit_price,
              passive_pending_stop_loss,
              passive_pending_planned_risk_usd,
              passive_pending_placements,
              passive_cancel_connection_deferrals,
              passive_pending_expirations,
              passive_completed_entries,
              passive_stale_price_rejections,
              protection_calculation_failures,
              risk_admission_skips,
              protection_mismatches,
              stop_loss_exits,
              TrackedAggregatePlannedRisk(),
              portfolio_state.maximum_aggregate_planned_risk_usd,
              decision_intent.journal_stage,
              decision_intent.component,
              (long)decision_intent.decision_bar,
              decision_intent.direction,
              decision_intent.signal_value,
              (long)decision_intent.deadline,
              (long)decision_intent.attempted_server,
              (long)decision_intent.adopted_ticket,
              journal_signal_decisions,
              journal_order_attempts,
              journal_broker_adoptions,
              journal_restart_resolutions,
              (long)arc_lifecycle_identifier,
              (execution_state.arc_modify_pending ? 1 : 0),
              arc_pending_stop_loss,
              (arc_lifecycle_compressed ? 1 : 0),
               arc_original_stop_loss,
              (execution_state.rc4_shadow_occupied ? 1 : 0),
              (long)rc4_shadow_source_identifier,
              (long)rc4_shadow_entry_time,
              rc4_shadow_direction,
               rc4_shadow_original_stop_loss);
   FileWrite(handle,
             "rc4_modify_retry", "pending", "consumed", "after_msc",
             "initial_retcode", "intents", "attempts", "successes",
             "adoptions", "holds");
   FileWrite(handle,
             "rc4_modify_retry",
             (execution_state.arc_modify_retry_pending ? 1 : 0),
             (arc_modify_retry_consumed ? 1 : 0),
             execution_state.arc_modify_retry_after_msc,
             (long)arc_modify_retry_initial_retcode,
             arc_modify_retry_intents,
             arc_modify_retry_attempts,
             arc_modify_retry_successes,
             arc_modify_retry_adoptions,
             arc_modify_retry_holds);
   FileWrite(handle,
             "component_id", "magic", "last_decision_bar",
              "entry_check_bar", "entry_check_signal_known",
              "entry_check_signal_passed", "entry_check_signal_value",
              "entry_check_direction", "entry_check_order_price",
              "entry_check_volume", "entry_check_stop_loss",
              "entry_check_planned_risk", "entry_check_result",
              "position_identifier", "last_exit_deal",
              "last_exit_time_msc", "stop_loss_seen", "entry_time",
              "entry_direction", "entry_volume", "entry_stop_loss",
              "entry_planned_risk", "entry_cost_known", "closed",
              "stressed_net");
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      FileWrite(handle,
                component_definitions[component].id,
                (long)component_definitions[component].magic,
                (long)component_states[component].last_decision_bar,
                (long)component_states[component].entry_check_bar,
                component_states[component].entry_check_signal_known,
                component_states[component].entry_check_signal_passed,
                component_states[component].entry_check_signal_value,
                component_states[component].entry_check_direction,
                component_states[component].entry_check_order_price,
                component_states[component].entry_check_volume,
                component_states[component].entry_check_stop_loss,
                component_states[component].entry_check_planned_risk_usd,
                component_states[component].entry_check_result,
                (long)component_states[component].position_identifier,
                (long)component_states[component].last_processed_exit_deal,
                component_states[component].last_processed_exit_time_msc,
                (component_states[component].lifecycle_stop_loss_seen ? 1 : 0),
                (long)component_states[component].entry_time_server,
                 component_states[component].entry_direction,
                 component_states[component].entry_volume,
                 component_states[component].entry_stop_loss,
                 component_states[component].entry_planned_risk_usd,
                 (component_states[component].entry_cost_known ? 1 : 0),
                component_states[component].closed_trades,
                component_states[component].stressed_net);
   FileWrite(handle,
             "rc4_shadow_recovery", "last_observed_msc", "cursor_ordinal",
             "catchup_required", "catchup_scans", "catchup_ticks",
             "catchup_stop_releases", "catchup_failures",
             "checkpoint_observation_bucket",
             "checkpoint_last_completed_bucket",
             "checkpoint_last_persisted_msc",
             "checkpoint_last_persisted_ordinal",
             "checkpoint_eligible", "checkpoint_persisted",
             "checkpoint_save_failures", "checkpoint_readback_failures",
             "checkpoint_event_failures",
             "checkpoint_duplicate_bucket_failures",
             "checkpoint_cursor_regressions", "checkpoint_pending");
   FileWrite(handle,
             "rc4_shadow_recovery",
             rc4_shadow_last_observed_msc,
             rc4_shadow_cursor_ordinal,
             (rc4_shadow_catchup_required ? 1 : 0),
             rc4_shadow_catchup_scans,
             rc4_shadow_catchup_ticks,
             rc4_shadow_catchup_stop_releases,
             rc4_shadow_catchup_failures,
             rc4_shadow_cursor_checkpoint_observation_bucket,
             rc4_shadow_cursor_checkpoint_last_completed_bucket,
             rc4_shadow_cursor_checkpoint_last_persisted_msc,
             rc4_shadow_cursor_checkpoint_last_persisted_ordinal,
             rc4_shadow_cursor_checkpoint_eligible,
             rc4_shadow_cursor_checkpoint_persisted,
             rc4_shadow_cursor_checkpoint_save_failures,
             rc4_shadow_cursor_checkpoint_readback_failures,
             rc4_shadow_cursor_checkpoint_event_failures,
             rc4_shadow_cursor_checkpoint_duplicate_bucket_failures,
             rc4_shadow_cursor_checkpoint_regressions,
             (rc4_shadow_cursor_checkpoint_pending ? 1 : 0));
   FileWrite(handle,
             "rc4_shadow_activation_seal",
             "eligible", "sealed", "pending", "save_attempts",
             "save_failures", "readbacks", "readback_failures",
             "failures", "ambiguities", "sealed_msc",
             "sealed_ordinal", "pre_boundary_consumed");
   FileWrite(handle,
             "rc4_shadow_activation_seal",
             rc4_shadow_activation_seal_eligible,
             rc4_shadow_activation_seal_sealed,
             rc4_shadow_activation_seal_pending_count,
             rc4_shadow_activation_seal_save_attempts,
             rc4_shadow_activation_seal_save_failures,
             rc4_shadow_activation_seal_readbacks,
             rc4_shadow_activation_seal_readback_failures,
             rc4_shadow_activation_seal_failures,
             rc4_shadow_activation_seal_ambiguities,
             rc4_shadow_activation_last_sealed_msc,
             rc4_shadow_activation_last_sealed_ordinal,
             rc4_shadow_activation_pre_boundary_consumed);
   FileFlush(handle);
   FileClose(handle);
   return(true);
  }


bool WriteCurrentSnapshot()
  {
   const string preferred =
      ((state_sequence % 2) == 0
       ? CURRENT_SNAPSHOT_PATH_A : CURRENT_SNAPSHOT_PATH_B);
   const string fallback =
      ((state_sequence % 2) == 0
       ? CURRENT_SNAPSHOT_PATH_B : CURRENT_SNAPSHOT_PATH_A);
   if(WriteCurrentSnapshotFile(preferred))
      return(true);
   return(WriteCurrentSnapshotFile(fallback));
  }


bool SaveState()
  {
   const long previous_sequence = state_sequence;
   const datetime previous_snapshot = last_snapshot_utc;
   ++state_sequence;
   last_snapshot_utc = TimeGMT();
   const string path =
      ((state_sequence % 2) == 0 ? STATE_PATH_A : STATE_PATH_B);
   const int handle = OpenFileWithRetry(path,
                                        FILE_WRITE | FILE_CSV | FILE_ANSI,
                                        ',');
   if(handle == INVALID_HANDLE)
     {
      state_sequence = previous_sequence;
      last_snapshot_utc = previous_snapshot;
      MarkPersistenceFailure("cannot open state snapshot");
      return(false);
     }
   FileWrite(handle,
             STATE_MARKER,
             EXECUTION_VERSION,
             ECONOMIC_VERSION,
              PORTFOLIO_ID,
              ECONOMIC_FINGERPRINT,
              EXECUTION_FINGERPRINT,
              portfolio_state.bound_account_login,
              state_sequence,
             event_records,
             event_segment_records,
             event_segment,
             portfolio_state.stressed_balance,
             portfolio_state.stressed_peak,
             portfolio_state.stressed_maximum_closed_drawdown,
             InpPriorProjectRealizedNetUSD,
             portfolio_state.project_realized_net,
             (long)portfolio_state.sizing_server_day,
             portfolio_state.day_volume_multiplier,
             (portfolio_state.safety_stopped ? 1 : 0),
             (long)started_utc,
             (long)last_snapshot_utc,
             portfolio_state.account_peak_equity,
             portfolio_state.account_maximum_drawdown,
              (long)execution_state.passive_pending_order,
              (execution_state.passive_cancel_pending ? 1 : 0),
             (long)passive_pending_expiration,
              passive_pending_direction,
              passive_pending_feature,
              passive_pending_limit_price,
              passive_pending_stop_loss,
              passive_pending_planned_risk_usd,
              (long)passive_next_entry_current_bar,
              passive_pending_placements,
              passive_cancel_connection_deferrals,
             passive_pending_expirations,
             passive_completed_entries,
             passive_placement_failures,
             passive_stale_price_rejections,
             passive_unexpected_order_outcomes,
              passive_margin_calculation_failures,
              passive_margin_skips,
              passive_price_constraint_skips,
              protection_calculation_failures,
              risk_admission_skips,
              protection_mismatches,
              stop_loss_exits,
              portfolio_state.maximum_aggregate_planned_risk_usd,
              decision_intent.journal_stage,
              decision_intent.component,
              (long)decision_intent.decision_bar,
              decision_intent.direction,
              decision_intent.signal_value,
              (long)decision_intent.deadline,
              (long)decision_intent.attempted_server,
              (long)decision_intent.adopted_ticket,
              journal_signal_decisions,
              journal_order_attempts,
              journal_broker_adoptions,
              journal_restart_resolutions);
   FileWrite(handle,
              (long)arc_lifecycle_identifier,
              (long)arc_last_attempt_bar,
              (arc_checkpoint_evaluated ? 1 : 0),
              (arc_lifecycle_compressed ? 1 : 0),
              arc_original_stop_loss,
              arc_checkpoints,
              arc_adverse_triggers,
              arc_compressions_placed,
              arc_compression_refusals,
              arc_data_unavailable,
              (execution_state.rc4_shadow_occupied ? 1 : 0),
              (long)rc4_shadow_source_identifier,
              (long)rc4_shadow_entry_time,
              rc4_shadow_direction,
              rc4_shadow_original_stop_loss,
              rc4_shadow_last_observed_msc,
              rc4_shadow_cursor_ordinal,
              rc4_shadow_activations,
              rc4_shadow_stop_releases,
              rc4_shadow_deadline_releases,
              rc4_shadow_entry_blocks,
              rc4_shadow_catchup_scans,
              rc4_shadow_catchup_ticks,
              rc4_shadow_catchup_stop_releases,
              rc4_shadow_catchup_failures,
              rc4_shadow_cursor_checkpoint_observation_bucket,
              rc4_shadow_cursor_checkpoint_last_completed_bucket,
              rc4_shadow_cursor_checkpoint_last_persisted_msc,
              rc4_shadow_cursor_checkpoint_last_persisted_ordinal,
              rc4_shadow_cursor_checkpoint_eligible,
              rc4_shadow_cursor_checkpoint_persisted,
              rc4_shadow_cursor_checkpoint_save_failures,
              rc4_shadow_cursor_checkpoint_readback_failures,
              rc4_shadow_cursor_checkpoint_event_failures,
              rc4_shadow_cursor_checkpoint_duplicate_bucket_failures,
              rc4_shadow_cursor_checkpoint_regressions,
              (rc4_shadow_cursor_checkpoint_pending ? 1 : 0),
              (execution_state.arc_modify_pending ? 1 : 0),
              arc_pending_stop_loss,
              (execution_state.arc_modify_retry_pending ? 1 : 0),
              (arc_modify_retry_consumed ? 1 : 0),
              execution_state.arc_modify_retry_after_msc,
              (long)arc_modify_retry_initial_retcode,
              arc_modify_retry_intents,
              arc_modify_retry_attempts,
              arc_modify_retry_successes,
              arc_modify_retry_adoptions,
              arc_modify_retry_holds);
   FileWrite(handle,
             (execution_state.rc4_shadow_activation_sealed ? 1 : 0),
             (execution_state.rc4_shadow_activation_seal_pending ? 1 : 0),
             (rc4_shadow_activation_seal_failure_logged ? 1 : 0),
             (long)rc4_shadow_activation_deal_ticket,
             rc4_shadow_activation_deal_time_msc,
             rc4_shadow_activation_deal_price,
             rc4_shadow_activation_deal_reason,
             rc4_shadow_activation_protected_stop,
             (rc4_shadow_activation_sampled_tick_known ? 1 : 0),
             (long)rc4_shadow_activation_sampled_time,
             rc4_shadow_activation_sampled_time_msc,
             rc4_shadow_activation_sampled_bid,
             rc4_shadow_activation_sampled_ask,
             rc4_shadow_activation_sampled_last,
             (long)rc4_shadow_activation_sampled_volume,
             rc4_shadow_activation_sampled_volume_real,
             (long)rc4_shadow_activation_sampled_flags,
             rc4_shadow_activation_boundary_msc,
             rc4_shadow_activation_boundary_ordinal,
             rc4_shadow_activation_seal_eligible,
             rc4_shadow_activation_seal_sealed,
             rc4_shadow_activation_seal_pending_count,
             rc4_shadow_activation_seal_save_attempts,
             rc4_shadow_activation_seal_save_failures,
             rc4_shadow_activation_seal_readbacks,
             rc4_shadow_activation_seal_readback_failures,
             rc4_shadow_activation_seal_failures,
             rc4_shadow_activation_seal_ambiguities,
             rc4_shadow_activation_last_sealed_msc,
             rc4_shadow_activation_last_sealed_ordinal,
             rc4_shadow_activation_pre_boundary_consumed);
   for(int component = 0; component < COMPONENT_COUNT; ++component)
      WriteComponentState(handle, component);
   FileWrite(handle, STATE_MARKER);
   FileFlush(handle);
   FileClose(handle);
   long verified_sequence = -1;
   if(!ReadState(path, verified_sequence) ||
      verified_sequence != state_sequence)
     {
      MarkPersistenceFailure("state verification failed");
      return(false);
     }
   if(!WriteCurrentSnapshot())
     {
      MarkPersistenceFailure("current snapshot failed");
      return(false);
     }
   return(true);
  }


bool RecordEvent(const int component,
                 const string event_name,
                 const double value_a,
                 const double value_b,
                 const string detail)
  {
   const bool rotate = (event_segment_records >= InpEventCapacity);
   const int target_segment = (rotate ? 1 - event_segment : event_segment);
   const long target_records = (rotate ? 0 : event_segment_records);
   const bool replace_segment = (rotate || target_records == 0);
   const string path = (target_segment == 0 ? EVENT_PATH_A : EVENT_PATH_B);
   const int flags =
      (replace_segment
       ? FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ
       : FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ);
   const int handle = OpenFileWithRetry(path, flags, ',');
   if(handle == INVALID_HANDLE)
     {
      MarkPersistenceFailure("cannot open event segment");
      return(false);
     }
   if(!replace_segment)
      FileSeek(handle, 0, SEEK_END);
   if(FileSize(handle) == 0)
      FileWrite(handle,
                 "utc", "server_time", "event", "execution_version",
                 "schema_version", "release_id", "project_id",
                 "portfolio_id", "component_id", "value_a", "value_b",
                 "detail", "stressed_balance", "project_stage_balance",
                 "account_equity",
                "account_margin", "state_sequence");
   const string component_id =
      (component >= 0 && component < COMPONENT_COUNT
       ? component_definitions[component].id : "PORTFOLIO");
   FileWrite(handle,
             TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS),
             TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
              event_name,
              EXECUTION_VERSION,
              SCHEMA_VERSION,
              RELEASE_ID,
              PROJECT_ID,
              PORTFOLIO_ID,
             component_id,
             value_a,
             value_b,
             detail,
             portfolio_state.stressed_balance,
             InpReferenceCapitalUSD + portfolio_state.project_realized_net,
             AccountInfoDouble(ACCOUNT_EQUITY),
             AccountInfoDouble(ACCOUNT_MARGIN),
             state_sequence);
   FileFlush(handle);
   FileClose(handle);
   const int verify = OpenFileWithRetry(path,
                                        FILE_READ | FILE_BIN |
                                        FILE_SHARE_READ,
                                        ',');
   if(verify == INVALID_HANDLE || FileSize(verify) <= 0)
     {
      if(verify != INVALID_HANDLE)
         FileClose(verify);
      MarkPersistenceFailure("event verification failed");
      return(false);
     }
   FileClose(verify);
   event_segment = target_segment;
   event_segment_records = target_records + 1;
   ++event_records;
   return(true);
  }


bool AcquireRuntimeOwnership()
  {
   ResetLastError();
   int ownership_flags = FILE_WRITE | FILE_TXT | FILE_ANSI;
   if(!tester_mode)
      ownership_flags |= FILE_COMMON;
   ownership_handle = FileOpen(OWNERSHIP_PATH,
                               ownership_flags);
   if(ownership_handle == INVALID_HANDLE)
     {
      PrintFormat("%s runtime ownership unavailable; duplicate instance "
                  "or storage failure error=%d",
                  EXECUTION_VERSION, GetLastError());
      return(false);
     }
   FileWriteString(ownership_handle,
                   EXECUTION_VERSION + "," + (string)ChartID() + "," +
                   TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS));
   FileFlush(ownership_handle);
   return(true);
  }


void ReleaseRuntimeOwnership()
  {
   if(ownership_handle == INVALID_HANDLE)
      return;
   FileClose(ownership_handle);
   ownership_handle = INVALID_HANDLE;
  }


void ResetTesterArtifacts()
  {
   FileDelete(STATE_PATH_A);
   FileDelete(STATE_PATH_B);
   FileDelete(EVENT_PATH_A);
   FileDelete(EVENT_PATH_B);
   FileDelete(CURRENT_SNAPSHOT_PATH_A);
   FileDelete(CURRENT_SNAPSHOT_PATH_B);
   FileDelete(OWNERSHIP_PATH);
  }


string DecisionJournalStageName(const int stage)
  {
   if(stage == JOURNAL_SIGNAL_DECIDED)
      return("SIGNAL_DECIDED");
   if(stage == JOURNAL_ORDER_ATTEMPTED)
      return("ORDER_ATTEMPTED");
   if(stage == JOURNAL_BROKER_STATE_ADOPTED)
      return("BROKER_STATE_ADOPTED");
   return("NONE");
  }


bool PersistDecisionUntil(const int component,
                          const datetime bar,
                          const datetime deadline)
  {
   component_states[component].last_decision_bar = bar;
   if(component_states[component].entry_check_signal_passed != 1)
     {
      const bool saved = SaveState();
      if(saved && component_states[component].entry_check_signal_known == 1)
         ResearchRecordCandidateOutcome(component,
                                        "SIGNAL",
                                        component_states[component].entry_check_result,
                                        "signal evaluation completed without an order path");
      return(saved);
     }
   if(component < 0 || component >= COMPONENT_COUNT || bar <= 0 ||
      deadline < bar || MathAbs(component_states[component].entry_check_direction) != 1 ||
      !MathIsValidNumber(component_states[component].entry_check_signal_value) ||
      decision_intent.journal_stage != JOURNAL_NONE)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("decision journal cannot begin unambiguously");
      return(false);
     }
   decision_intent.journal_stage = JOURNAL_SIGNAL_DECIDED;
   decision_intent.component = component;
   decision_intent.decision_bar = bar;
   decision_intent.direction = component_states[component].entry_check_direction;
   decision_intent.signal_value = component_states[component].entry_check_signal_value;
   decision_intent.order_type =
      (decision_intent.direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   decision_intent.order_type_known = true;
   decision_intent.intended_price = 0.0;
   decision_intent.expiration = deadline;
   decision_intent.deadline = deadline;
   decision_intent.attempted_server = 0;
   decision_intent.adopted_ticket = 0;
   decision_intent.volume = 0.0;
   decision_intent.stop_loss = 0.0;
   decision_intent.planned_risk_usd = 0.0;
   ++journal_signal_decisions;
   // The state write is intentionally first. Once it succeeds, a restart
   // cannot replay this opportunity even if the audit event write is lost.
   if(!SaveState())
      return(false);
   const bool event_saved =
      RecordEvent(component,
                  "SIGNAL_DECIDED",
                  decision_intent.signal_value,
                  (double)decision_intent.direction,
                  StringFormat("bar=%s deadline=%s replay=0",
                               TimeToString(bar,
                                            TIME_DATE | TIME_MINUTES),
                               TimeToString(deadline,
                                            TIME_DATE | TIME_MINUTES)));
   const bool counters_saved = SaveState();
   return(event_saved && counters_saved);
  }


bool PersistDecision(const int component, const datetime bar)
  {
   return(PersistDecisionUntil(component,
                               bar,
                               bar + InpMaxEntryDelayMinutes * 60));
  }


bool MarkDecisionOrderAttempted(const int component,
                                const int direction,
                                const double feature,
                                const string operation)
  {
   if(decision_intent.journal_stage != JOURNAL_SIGNAL_DECIDED ||
      decision_intent.component != component ||
      decision_intent.decision_bar <= 0 ||
      MathAbs(decision_intent.direction) != 1 ||
      direction != decision_intent.direction ||
      !MathIsValidNumber(feature) ||
      MathAbs(feature - decision_intent.signal_value) > 1.0e-10 ||
      TimeCurrent() > decision_intent.deadline)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("order attempt lacks an active decision journal");
      return(false);
     }
   decision_intent.journal_stage = JOURNAL_ORDER_ATTEMPTED;
   decision_intent.attempted_server = TimeCurrent();
   ++journal_order_attempts;
   // ORDER_ATTEMPTED is the durable intent immediately before the
   // synchronous broker call. It does not claim that the broker received it.
   if(!SaveState())
      return(false);
   const bool event_saved =
      RecordEvent(component,
                  "ORDER_ATTEMPTED",
                  (double)decision_intent.direction,
                  (double)decision_intent.decision_bar,
                  StringFormat("operation=%s attempted=%s replay=0",
                               operation,
                               TimeToString(decision_intent.attempted_server,
                                            TIME_DATE | TIME_SECONDS)));
   const bool counters_saved = SaveState();
   return(event_saved && counters_saved);
  }


bool MarkDecisionBrokerStateAdopted(const int component,
                                    const ulong broker_ticket,
                                    const string adoption)
  {
   if(decision_intent.journal_stage != JOURNAL_ORDER_ATTEMPTED ||
      decision_intent.component != component || broker_ticket == 0)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("broker adoption lacks an attempted decision journal");
      return(false);
     }
   decision_intent.journal_stage = JOURNAL_BROKER_STATE_ADOPTED;
   decision_intent.adopted_ticket = broker_ticket;
   ++journal_broker_adoptions;
   if(!SaveState())
      return(false);
   const bool event_saved =
      RecordEvent(component,
                  "BROKER_STATE_ADOPTED",
                  (double)broker_ticket,
                  (double)decision_intent.decision_bar,
                  adoption);
   const bool counters_saved = SaveState();
   return(event_saved && counters_saved);
  }


bool FinalizeDecisionJournal(const int component,
                             const string outcome)
  {
   if(decision_intent.journal_stage == JOURNAL_NONE)
      return(true);
   if(decision_intent.component != component)
     {
      execution_state.broker_mismatch = true;
      EngageSafetyStop("decision journal component mismatch at finalization");
      return(false);
     }
   const string stage_name =
      DecisionJournalStageName(decision_intent.journal_stage);
   if(!RecordEvent(component,
                   "DECISION_JOURNAL_FINAL",
                   (double)decision_intent.journal_stage,
                   (double)decision_intent.adopted_ticket,
                   StringFormat("stage=%s outcome=%s replay=0",
                                stage_name,
                                outcome)))
     {
      SaveState();
      return(false);
     }
   ClearDecisionJournalState();
   const bool saved = SaveState();
   if(saved)
      ResearchRecordCandidateOutcome(component,
                                     "OUTCOME",
                                     outcome,
                                     "order and admission path completed");
   return(saved);
  }


bool ResolveRestartDecisionJournal()
  {
   if(decision_intent.journal_stage == JOURNAL_NONE)
      return(true);
   const int component = decision_intent.component;
   ulong position_ticket = 0;
   datetime opened_at = 0;
   const int positions =
      CountOwnedPositions(component, position_ticket, opened_at);
   ulong order_ticket = 0;
   const int orders =
      (component == US100_PASSIVE_LIMIT
       ? CountOwnedPassiveOrders(order_ticket) : 0);
   const string stage_name =
      DecisionJournalStageName(decision_intent.journal_stage);
   ++journal_restart_resolutions;
   if(!RecordEvent(component,
                   "RESTART_JOURNAL_NO_REPLAY",
                   (double)decision_intent.journal_stage,
                   (double)decision_intent.adopted_ticket,
                   StringFormat("stage=%s positions=%d orders=%d deadline=%s expired=%d automatic_replay=0",
                                stage_name,
                                positions,
                                orders,
                                TimeToString(decision_intent.deadline,
                                             TIME_DATE | TIME_SECONDS),
                                (int)(TimeCurrent() >
                                      decision_intent.deadline))))
     {
      SaveState();
      return(false);
     }
   ClearDecisionJournalState();
   return(SaveState());
  }


#endif
