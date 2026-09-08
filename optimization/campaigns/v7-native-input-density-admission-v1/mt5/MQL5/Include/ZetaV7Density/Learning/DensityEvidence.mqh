#ifndef ZETA_DENSITY_EVIDENCE_MQH
#define ZETA_DENSITY_EVIDENCE_MQH

void DensityFlushEquity(const bool close)
  {
   if(density_equity_handle==INVALID_HANDLE) return;
   ResetLastError();
   FileFlush(density_equity_handle);
   const int error=GetLastError();
   const bool complete=(FileSize(density_equity_handle)==density_equity_bytes);
   if(close)
     {
      FileClose(density_equity_handle);
      density_equity_handle=INVALID_HANDLE;
     }
   if(error!=0 || !complete)
      DensityFault("native equity batch flush incomplete");
  }

void DensityRecordExit(const int component,const ulong deal,const long deal_msc,
                       const double actual,const double stressed)
  {
   if(!density_initialized || density_failed) return;
   const double swap=HistoryDealGetDouble(deal,DEAL_SWAP);
   if(!MathIsValidNumber(swap) || !MathIsValidNumber(actual) || !MathIsValidNumber(stressed))
     { DensityFault("invalid completed native exit valuation"); return; }
   density_positive_swap+=MathMax(0.0,swap);
   const double conservative=portfolio_state.stressed_balance-density_positive_swap;
   density_conservative_peak=MathMax(density_conservative_peak,conservative);
   density_conservative_closed_dd=MathMax(density_conservative_closed_dd,
                                          density_conservative_peak-conservative);
   int h=FileOpen(density_root+"\\learning\\exits.csv",
                  FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(h==INVALID_HANDLE)
     { DensityFault("cannot append native exit evidence"); return; }
   if(FileSize(h)==0)
      FileWrite(h,"deal_msc","recorded_server","component","deal","actual_net",
                  "original_stressed_net","swap","positive_swap_total",
                  "conservative_closed_balance","native_balance","day_multiplier","core_sequence");
   FileSeek(h,0,SEEK_END);
   const uint written=FileWrite(h,deal_msc,(long)TimeCurrent(),component,deal,
       DoubleToString(actual,12),DoubleToString(stressed,12),DoubleToString(swap,12),
       DoubleToString(density_positive_swap,12),DoubleToString(conservative,12),
       DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),12),portfolio_state.day_volume_multiplier,state_sequence);
   FileFlush(h);
   FileClose(h);
   if(written==0)
     { DensityFault("native exit evidence write failed"); return; }
   ++density_exit_rows;
   DensityFlushEquity(false);
   DensitySaveCheckpoint();
  }

void DensityRecordEquity(const bool force)
  {
   if(!density_initialized || density_failed || !execution_state.runtime_ready) return;
   const datetime now=TimeCurrent();
   const long minute=(long)now/60;
   if(!force && minute==density_last_minute) return;
   double conservative=portfolio_state.stressed_balance-density_positive_swap;
   int positions=0;
   double lots=0.0;
   long maximum_quote_age_msc=0;
   for(int i=0;i<PositionsTotal();++i)
     {
      const ulong ticket=PositionGetTicket(i);
      if(ticket==0)
        { DensityFault("native mark position selection failed"); return; }
      const ulong magic=(ulong)PositionGetInteger(POSITION_MAGIC);
      int component=-1;
      for(int c=0;c<6;++c)
         if(component_definitions[c].magic==magic) component=c;
      if(component<0)
        { DensityFault("foreign position in owned native mark"); return; }
      const string symbol=PositionGetString(POSITION_SYMBOL);
      const double profit=PositionGetDouble(POSITION_PROFIT);
      const double swap=PositionGetDouble(POSITION_SWAP);
      const double volume=PositionGetDouble(POSITION_VOLUME);
      const double contract=SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE);
      MqlTick tick={};
      if(!SymbolInfoTick(symbol,tick) || !MathIsValidNumber(tick.bid) ||
         !MathIsValidNumber(tick.ask) || tick.bid<=0 || tick.ask<tick.bid ||
         !MathIsValidNumber(profit) || !MathIsValidNumber(swap) || volume<=0 || contract<=0 ||
         !component_states[component].entry_cost_known ||
         component_states[component].entry_volume<=0)
        { DensityFault("complete owned quote/entry-cost mark unavailable"); return; }
      const double fraction=volume/component_states[component].entry_volume;
      const double entry_cost=component_states[component].entry_transaction_cost*fraction;
      const double entry_slippage=component_states[component].entry_adverse_slippage*fraction;
      const double additional_spread=MathMax(tick.ask-tick.bid,
                         component_states[component].entry_spread_price)*contract*volume;
      conservative+=profit+MathMin(0.0,swap)+entry_cost-additional_spread-entry_slippage-
                    MathMax(0.0,-entry_cost)-MathMax(0.0,-swap);
      maximum_quote_age_msc=MathMax(maximum_quote_age_msc,
                                   MathMax(0,(long)now*1000-tick.time_msc));
      ++positions;
      lots+=volume;
     }
   const double actual=AccountInfoDouble(ACCOUNT_EQUITY);
   if(!MathIsValidNumber(actual) || !MathIsValidNumber(conservative))
     { DensityFault("nonfinite native account mark"); return; }
   if(density_equity_handle==INVALID_HANDLE)
      density_equity_handle=FileOpen(density_root+"\\learning\\equity.csv",
                         FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   const int h=density_equity_handle;
   if(h==INVALID_HANDLE)
     { DensityFault("cannot append native equity evidence"); return; }
   if(FileSize(h)==0)
      FileWrite(h,"server_time","actual_equity","native_balance","original_stressed_balance",
                  "conservative_closed_balance","conservative_mark","positive_swap_total",
                  "positions","lots","day_multiplier","max_owned_quote_age_msc",
                  "forecast_count","abstentions","observations","updates","pending");
   FileSeek(h,0,SEEK_END);
   const uint written=FileWrite(h,(long)now,DoubleToString(actual,12),
       DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),12),
       DoubleToString(portfolio_state.stressed_balance,12),
       DoubleToString(portfolio_state.stressed_balance-density_positive_swap,12),
       DoubleToString(conservative,12),DoubleToString(density_positive_swap,12),
       positions,DoubleToString(lots,8),portfolio_state.day_volume_multiplier,
       maximum_quote_age_msc,density_forecasts,density_abstentions,density_observations,
       density_updates,ArraySize(density_pending));
   density_equity_bytes=FileTell(h);
   if(written==0)
     { DensityFault("native equity evidence write failed"); return; }
   density_last_minute=minute;
   ++density_mark_rows;
   // Observation rows do not control trading or learning state. Keep every row;
   // commit batches and all normal exits/finalization without per-minute fsync.
   if(force || density_mark_rows%512==0) DensityFlushEquity(false);
  }

void DensityFinishEvidence()
  {
   if(density_finished) return;
   DensityRecordEquity(true);
   DensityFlushEquity(true);
   if(density_initialized && !density_failed) DensitySaveCheckpoint();
   const double conservative_net=portfolio_state.stressed_balance-density_positive_swap-InpReferenceCapitalUSD;
   const double actual_dd=TesterStatistics(STAT_EQUITY_DD);
   const double recovery=MathMin(portfolio_state.project_realized_net,conservative_net)/
                         MathMax(.01,MathMax(actual_dd,density_conservative_closed_dd));
   PrintFormat("DENSITY_RESULT status=%s role=%d forecasts=%I64d abstentions=%I64d "
               "observations=%I64d updates=%I64d update_inferences=%I64d pending=%d "
               "sequence=%I64d checkpoints=%I64d readbacks=%I64d marks=%I64d exits=%I64d "
               "positive_swap=%.12f conservative_net=%.12f conservative_closed_dd=%.12f "
               "native_equity_dd=%.12f native_equity_dd_percent=%.12f robust_recovery=%.12f "
               "open_positions=%d open_orders=%d final_server=%I64d",
               (density_failed || !density_initialized ? "CORRECTION_REQUIRED" : "COMPLETE"),
               DENSITY_ROLE,density_forecasts,density_abstentions,density_observations,
               density_updates,density_update_inferences,ArraySize(density_pending),
               density_sequence,density_state_sequence,density_readbacks,density_mark_rows,
               density_exit_rows,density_positive_swap,conservative_net,density_conservative_closed_dd,
               actual_dd,TesterStatistics(STAT_EQUITY_DDREL_PERCENT),recovery,
               PositionsTotal(),OrdersTotal(),(long)TimeCurrent());
   density_finished=true;
  }

#endif
