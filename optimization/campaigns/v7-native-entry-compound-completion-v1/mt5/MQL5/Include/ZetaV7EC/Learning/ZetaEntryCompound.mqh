#ifndef ZETA_V7_ENTRY_COMPOUND_MQH
#define ZETA_V7_ENTRY_COMPOUND_MQH

// Family23: exact frozen Family1 policy, implemented against the original V7.
// No future tape, external source, refit, new signal, or borrowed learner state.
#resource "\\Files\\ZetaV7EC\\v7-risk-score.onnx" as uchar EC_MODEL_BYTES[]

struct ECEntry
  {
   long forecast_id;
   long forecast_server;
   long decision_bar;
   int direction;
   int prior_direction;
   double feature;
   double frozen_prediction;
   double bias_used;
   double score;
   double risk_fraction;
   double capital;
   double volume;
   double stop_loss;
   double original_risk;
   ulong position_id;
   ulong pending_order;
   long entry_server;
   double actual_net;
   double stressed_net;
   long last_exit_msc;
   ulong last_exit_deal;
  };

struct ECClosedLabel
  {
   long label_id;
   long forecast_id;
   int component;
   ulong position_id;
   long entry_server;
   long completion_msc;
   long observed_server;
   ulong final_deal;
   double frozen_prediction;
   double original_risk;
   double stressed_net;
   double label;
  };

struct ECCheckpoint
  {
   long schema;
   long role;
   long sequence;
   long forecasts;
   long labels;
   long updates;
   long last_decision_second;
   int pending_count;
   double closed_positive_swap;
   double bias[6];
   ECEntry entry[6];
   ECClosedLabel pending[64];
  };

ECCheckpoint ec_book;
long ec_onnx=INVALID_HANDLE;
bool ec_ready=false;
long ec_faults=0;
long ec_readbacks=0;
long ec_marks=0;
long ec_last_minute=-1;
long ec_last_mark_server=0;
int ec_forecast_file=INVALID_HANDLE;
int ec_entry_file=INVALID_HANDLE;
int ec_exit_file=INVALID_HANDLE;
int ec_update_file=INVALID_HANDLE;
int ec_equity_file=INVALID_HANDLE;
const string EC_MODEL_SHA="539C75E331A79ED96FAF7FCFE170D92672EECC8E05712E61AA95FC6D036CDBFE";
const string EC_PARAMETER_SHA="88D32985BB11D6270B8A096786A1FEF929CEF7030112C79D50615051D96DE0EC";
const string EC_NATIVE_CONTRACT="F23-fixed14-raw-onnx-standardize-clip-ridge-capital100-risk004-tanh025-eta003-limit05-strict-second-v1";

string ECNum(const double x) { return(DoubleToString(x,16)); }
double ECClip(const double x,const double low,const double high) { return(MathMax(low,MathMin(high,x))); }

void ECFault(const string reason)
  {
   ++ec_faults;
   if(ec_faults<=8) PrintFormat("V7EC_FAULT role=%d server=%I64d reason=%s error=%d",EC_ROLE,(long)TimeCurrent(),reason,GetLastError());
  }

bool ECEntryGate()
  {
   return(ec_ready && ec_faults==0);
  }

bool ECWrite(const int handle,const string row)
  {
   if(handle==INVALID_HANDLE || FileSize(handle)>167772160 || FileWriteString(handle,row+"\r\n")==0)
     { ECFault("bounded native ledger write"); return(false); }
   return(true);
  }

int ECOpenLedger(const string leaf,const string header)
  {
   const string path=EC_ROOT+"\\learning\\"+leaf;
   if(FileIsExist(path)) { ECFault("fresh tag already has a ledger: "+leaf); return(INVALID_HANDLE); }
   const int h=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h==INVALID_HANDLE || !ECWrite(h,header)) return(INVALID_HANDLE);
   FileFlush(h);
   return(h);
  }

string ECCheckpointIdentity()
  {
   return(EC_NATIVE_CONTRACT+"|"+EC_MODEL_SHA+"|"+EC_PARAMETER_SHA+"|"+PORTFOLIO_ID+"|"+InpECRunTag);
  }

bool ECReadCheckpoint(const string path,ECCheckpoint &result)
  {
   const int h=FileOpen(path,FILE_READ|FILE_BIN|FILE_ANSI|FILE_SHARE_READ);
   if(h==INVALID_HANDLE) return(false);
   const string identity=ECCheckpointIdentity();
   const int n=FileReadInteger(h,INT_VALUE);
   bool ok=(n==StringLen(identity) && FileSize(h)==(ulong)(4+n+sizeof(ECCheckpoint)));
   string stored="";
   if(ok) stored=FileReadString(h,n);
   if(ok) ok=(stored==identity && FileReadStruct(h,result)==sizeof(ECCheckpoint));
   FileClose(h);
   if(!ok || result.schema!=2301 || result.role!=EC_ROLE || result.sequence<1 || result.pending_count<0 || result.pending_count>64) return(false);
   for(int c=0;c<6;++c)
      if(!MathIsValidNumber(result.bias[c]) || MathAbs(result.bias[c])>0.500000000001) return(false);
   return(true);
  }

bool ECSave()
  {
   if(!ec_ready || ec_faults!=0) return(false);
   ++ec_book.sequence;
   const string path=EC_ROOT+"\\learning\\checkpoint-"+(ec_book.sequence%2==0?"a":"b")+".bin";
   const string identity=ECCheckpointIdentity();
   const int h=FileOpen(path,FILE_WRITE|FILE_BIN|FILE_ANSI|FILE_SHARE_READ);
   if(h==INVALID_HANDLE) { ECFault("checkpoint open"); return(false); }
   bool ok=(FileWriteInteger(h,StringLen(identity),INT_VALUE)==4);
   ok=(FileWriteString(h,identity,StringLen(identity))==(uint)StringLen(identity) && ok);
   ok=(FileWriteStruct(h,ec_book)==sizeof(ECCheckpoint) && ok);
   FileFlush(h); FileClose(h);
   ECCheckpoint recovered={};
   ok=(ECReadCheckpoint(path,recovered) && ok);
   uchar expected[],actual[];
   if(ok) ok=(StructToCharArray(ec_book,expected) && StructToCharArray(recovered,actual) && ArrayCompare(expected,actual)==0);
   if(!ok) { ECFault("identity-bound full checkpoint readback"); return(false); }
   ++ec_readbacks;
   FileFlush(ec_forecast_file); FileFlush(ec_entry_file); FileFlush(ec_exit_file); FileFlush(ec_update_file);
   return(true);
  }

void ECApplyMature(const long now)
  {
   // A later callback in the same second cannot change the state seen by peers.
   if(now==ec_book.last_decision_second) return;
   ec_book.last_decision_second=now;
   int consumed=0;
   while(consumed<ec_book.pending_count)
     {
      ECClosedLabel q=ec_book.pending[consumed];
      if(q.completion_msc/1000>=now || q.observed_server>now) break;
      const double before=ec_book.bias[q.component];
      double after=before;
      if(EC_ROLE==2)
        {
         after=ECClip(0.97*before+0.03*(q.label-q.frozen_prediction),-0.5,0.5);
         ec_book.bias[q.component]=after;
         ++ec_book.updates;
        }
      ECWrite(ec_update_file,StringFormat("%I64d,%I64d,%I64d,%d,%I64u,%I64d,%I64d,%I64d,%I64d,",ec_book.updates,q.label_id,q.forecast_id,q.component,q.position_id,q.completion_msc,q.observed_server,now,ec_book.sequence)+ECNum(q.label)+","+ECNum(q.frozen_prediction)+","+ECNum(before)+","+ECNum(after)+","+(EC_ROLE==2?"ONLINE":"STATIC_MATURE"));
      ++consumed;
     }
   if(consumed>0)
     {
      for(int i=consumed;i<ec_book.pending_count;++i) ec_book.pending[i-consumed]=ec_book.pending[i];
      ec_book.pending_count-=consumed;
      for(int i=ec_book.pending_count;i<ec_book.pending_count+consumed;++i) ZeroMemory(ec_book.pending[i]);
     }
  }

bool ECPrepare(const int component,const int direction,const double feature)
  {
   if(!ECEntryGate()) return(false);
   if(EC_ROLE==0) return(true);
   if(component<0 || component>=6 || MathAbs(direction)!=1 || !MathIsValidNumber(feature)) { ECFault("invalid native feature"); return(false); }
   if(ec_book.entry[component].position_id!=0 || ec_book.entry[component].pending_order!=0) { ECFault("unresolved own entry before decision"); return(false); }
   const long now=(long)TimeCurrent();
   ECApplyMature(now);
   matrixf features(1,14); features.Fill(0.0);
   features[0][component]=1.0f;
   features[0][component+6]=(float)((feature>0.0?1.0:(feature<0.0?-1.0:0.0))*MathLog(1.0+MathAbs(feature)));
   const int prior=research_signal_prior_direction[component];
   features[0][12]=(float)direction;
   features[0][13]=(float)(direction*prior);
   matrixf prediction(1,1);
   ResetLastError();
   if(!OnnxRun(ec_onnx,ONNX_NO_CONVERSION|ONNX_USE_CPU_ONLY,features,prediction) || !MathIsValidNumber((double)prediction[0][0])) { ECFault("native ONNX inference"); return(false); }
   ECEntry p={};
   p.forecast_id=++ec_book.forecasts; p.forecast_server=now;
   p.decision_bar=(long)component_states[component].entry_check_bar;
   p.direction=direction; p.prior_direction=prior; p.feature=feature;
   p.frozen_prediction=(double)prediction[0][0];
   p.bias_used=(EC_ROLE==2?ec_book.bias[component]:0.0);
   p.score=p.frozen_prediction+p.bias_used;
   p.risk_fraction=(component==US100_PASSIVE_LIMIT?0.04:0.04*ECClip(0.75+0.5*MathTanh(p.score/0.25),0.25,1.0));
   p.capital=ConservativeRiskCapital();
   ec_book.entry[component]=p;
   string row=StringFormat("%I64d,%I64d,%I64d,%d,%d,%d,%I64d,%I64d,",p.forecast_id,now,p.decision_bar,component,direction,prior,ec_book.updates,ec_book.sequence)+ECNum(feature)+","+ECNum(p.frozen_prediction)+","+ECNum(p.bias_used)+","+ECNum(p.score)+","+ECNum(p.risk_fraction)+","+ECNum(p.capital);
   for(int f=0;f<14;++f) row+=","+ECNum((double)features[0][f]);
   return(ECWrite(ec_forecast_file,row) && ECSave());
  }

double ECVolume(const string symbol)
  {
   if(EC_ROLE==0) return(NormalizedVolume(symbol));
   const double minimum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   const double maximum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0 || minimum<=0.0 || ConservativeRiskCapital()<=0.0) return(0.0);
   const double requested=0.01*ConservativeRiskCapital()/100.0;
   const double volume=MathMax(minimum,MathFloor(requested/step+1.0e-9)*step);
   if(volume>maximum+1.0e-9) return(0.0);
   return(NormalizeDouble(volume,8));
  }

double ECRiskFraction(const int component)
  {
   if(EC_ROLE==0 || component==US100_PASSIVE_LIMIT) return(InpMaximumPositionRiskFraction);
   if(!ECEntryGate() || component<0 || component>=6 || ec_book.entry[component].forecast_id<=0) return(0.0);
   return(ec_book.entry[component].risk_fraction);
  }

bool ECJournal(const int component,const double volume,const double stop,const double risk)
  {
   if(!ECEntryGate()) return(false);
   if(EC_ROLE>0 && ec_book.entry[component].forecast_id<=0) { ECFault("order lacks frozen forecast"); return(false); }
   ec_book.entry[component].volume=volume; ec_book.entry[component].stop_loss=stop; ec_book.entry[component].original_risk=risk;
   if(EC_ROLE==0) { ec_book.entry[component].capital=ConservativeRiskCapital(); ec_book.entry[component].risk_fraction=0.04; }
   return(ECSave());
  }

void ECPending(const ulong order)
  {
   if(!ec_ready) return;
   ec_book.entry[US100_PASSIVE_LIMIT].pending_order=order;
   ECSave();
  }

void ECClearPassive()
  {
   if(!ec_ready) return;
   ec_book.entry[US100_PASSIVE_LIMIT].pending_order=0;
   if(ec_book.entry[US100_PASSIVE_LIMIT].position_id==0) ZeroMemory(ec_book.entry[US100_PASSIVE_LIMIT]);
   ECSave();
  }

void ECBind(const int component)
  {
   if(!ec_ready || ec_faults) return;
   const ulong position=component_states[component].position_identifier;
   if(position==0) { ECFault("empty core lifecycle bind"); return; }
   if(ec_book.entry[component].position_id==position) return;
   if(ec_book.entry[component].position_id!=0 || (EC_ROLE>0 && ec_book.entry[component].forecast_id<=0)) { ECFault("unattributed own native lifecycle"); return; }
   ec_book.entry[component].position_id=position; ec_book.entry[component].pending_order=0;
   ec_book.entry[component].entry_server=(long)component_states[component].entry_time_server;
   ec_book.entry[component].original_risk=component_states[component].entry_planned_risk_usd;
   ec_book.entry[component].volume=component_states[component].entry_volume;
   ec_book.entry[component].stop_loss=component_states[component].entry_stop_loss;
   ECEntry p=ec_book.entry[component];
   ECWrite(ec_entry_file,StringFormat("%I64d,%d,%I64u,%I64d,%I64d,%I64d,",p.forecast_id,component,position,p.entry_server,(long)TimeCurrent(),ec_book.sequence)+ECNum(p.volume)+","+ECNum(p.original_risk)+","+ECNum(p.stop_loss)+","+ECNum(p.capital)+","+ECNum(p.risk_fraction)+","+ECNum(p.frozen_prediction)+","+ECNum(p.bias_used));
   ECSave();
  }

void ECExit(const ResearchExitSnapshot &s)
  {
   if(!ec_ready || ec_faults) return;
   const int c=s.component;
   ECEntry p=ec_book.entry[c];
   if(p.position_id!=s.position_identifier || p.original_risk<=0.0 || s.deal_time_msc<p.last_exit_msc || (s.deal_time_msc==p.last_exit_msc && s.deal_ticket<=p.last_exit_deal)) { ECFault("own close attribution/cursor"); return; }
   p.actual_net+=s.deal_net; p.stressed_net+=s.stressed_net;
   p.last_exit_msc=s.deal_time_msc; p.last_exit_deal=s.deal_ticket;
   const double swap=HistoryDealGetDouble(s.deal_ticket,DEAL_SWAP);
   ec_book.closed_positive_swap+=MathMax(0.0,swap);
   ECWrite(ec_exit_file,StringFormat("%I64d,%d,%I64u,%I64u,%I64d,%I64d,%I64d,%d,",p.forecast_id,c,p.position_id,s.deal_ticket,s.deal_time_msc,(long)TimeCurrent(),p.entry_server,(s.full_exit?1:0))+ECNum(s.deal_net)+","+ECNum(s.stressed_net)+","+ECNum(p.actual_net)+","+ECNum(p.stressed_net)+","+ECNum(p.original_risk)+","+ECNum(swap)+","+ECNum(ec_book.closed_positive_swap)+","+ECNum(s.remaining_volume)+","+ECNum(p.frozen_prediction));
   ec_book.entry[c]=p;
   if(s.full_exit)
     {
      ++ec_book.labels;
      if(EC_ROLE>0)
        {
         if(ec_book.pending_count>=64) { ECFault("bounded mature label queue full"); return; }
         ECClosedLabel q={}; q.label_id=ec_book.labels; q.forecast_id=p.forecast_id; q.component=c; q.position_id=p.position_id; q.entry_server=p.entry_server;
         q.completion_msc=s.deal_time_msc; q.observed_server=(long)TimeCurrent(); q.final_deal=s.deal_ticket;
         q.frozen_prediction=p.frozen_prediction; q.original_risk=p.original_risk; q.stressed_net=p.stressed_net; q.label=ECClip(p.stressed_net/p.original_risk,-2.0,2.0);
         int j=ec_book.pending_count;
         while(j>0 && (ec_book.pending[j-1].completion_msc>q.completion_msc || (ec_book.pending[j-1].completion_msc==q.completion_msc && ec_book.pending[j-1].final_deal>q.final_deal))) { ec_book.pending[j]=ec_book.pending[j-1]; --j; }
         ec_book.pending[j]=q; ++ec_book.pending_count;
        }
      ZeroMemory(ec_book.entry[c]);
     }
   ECSave();
  }

void ECMark(const bool force=false)
  {
   if(!ec_ready || ec_faults) return;
   const long now=(long)TimeCurrent(); const long minute=now/60;
   if(!force && minute==ec_last_minute) return;
   double floating=0.0,reserve=0.0,positive_open_swap=0.0;
   int owned=0;
   for(int c=0;c<6;++c)
     {
      ulong ticket=0;datetime opened=0;
      const int n=CountOwnedPositions(c,ticket,opened);
      if(n==0) { if(component_states[c].position_identifier!=0) { ECFault("unreconciled closed position at minute mark"); return; } continue; }
      if(n!=1 || !PositionSelectByTicket(ticket) || component_states[c].position_identifier!=(ulong)PositionGetInteger(POSITION_IDENTIFIER)) { ECFault("unreconciled owned minute mark"); return; }
      ++owned;
      const string symbol=component_definitions[c].symbol; MqlTick tick={};
      if(!SymbolInfoTick(symbol,tick) || tick.bid<=0.0 || tick.ask<tick.bid || !component_states[c].entry_cost_known) { ECFault("incomplete minute cost quote"); return; }
      const double swap=PositionGetDouble(POSITION_SWAP); const double volume=PositionGetDouble(POSITION_VOLUME);
      floating+=PositionGetDouble(POSITION_PROFIT)+swap+component_states[c].entry_transaction_cost;
      positive_open_swap+=MathMax(0.0,swap);
      reserve+=MathMax(component_states[c].entry_spread_price,tick.ask-tick.bid)*SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE)*volume+component_states[c].entry_adverse_slippage+MathMax(0.0,-component_states[c].entry_transaction_cost)+MathMax(0.0,-swap);
     }
   const double conservative_closed=portfolio_state.stressed_balance-ec_book.closed_positive_swap;
   const double conservative_equity=conservative_closed+floating-reserve-positive_open_swap;
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(!MathIsValidNumber(conservative_equity) || !MathIsValidNumber(equity)) { ECFault("nonfinite equity mark"); return; }
   ECWrite(ec_equity_file,StringFormat("%I64d,%I64d,",now,minute)+ECNum(AccountInfoDouble(ACCOUNT_BALANCE))+","+ECNum(equity)+","+ECNum(portfolio_state.project_realized_net)+","+ECNum(portfolio_state.stressed_balance)+","+ECNum(conservative_closed)+","+ECNum(conservative_equity)+","+ECNum(AccountInfoDouble(ACCOUNT_MARGIN))+","+ECNum(ConservativeRiskCapital())+","+ECNum(TrackedAggregatePlannedRisk())+StringFormat(",%d,%d,%d,",owned,(execution_state.passive_pending_order>0?1:0),portfolio_state.day_volume_multiplier)+ECNum(ec_book.closed_positive_swap)+","+ECNum(reserve)+StringFormat(",%I64d,%I64d,%I64d,%I64d",ec_book.forecasts,ec_book.labels,ec_book.updates,ec_faults));
   ++ec_marks; ec_last_minute=minute; ec_last_mark_server=now;
   if(ec_marks%60==0) FileFlush(ec_equity_file);
  }

bool ECInitialize()
  {
   if(!tester_mode) { ECFault("Optimization Tester-only package"); return(false); }
   ZeroMemory(ec_book); ec_book.schema=2301; ec_book.role=EC_ROLE;
   if(FileIsExist(EC_ROOT+"\\learning\\checkpoint-a.bin") || FileIsExist(EC_ROOT+"\\learning\\checkpoint-b.bin")) { ECFault("fresh role tag must not adopt old state"); return(false); }
   FolderCreate(EC_ROLE_ROOT);FolderCreate(EC_ROOT);FolderCreate(EC_ROOT+"\\state");FolderCreate(EC_ROOT+"\\research");FolderCreate(EC_ROOT+"\\learning");
   ec_forecast_file=ECOpenLedger("forecasts.csv","forecast_id,server,decision_bar,component,direction,prior_direction,updates_seen,checkpoint,feature,frozen_prediction,bias,score,risk_fraction,capital,f0,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13");
   ec_entry_file=ECOpenLedger("entries.csv","forecast_id,component,position_id,entry_server,observed_server,checkpoint,volume,planned_entry_risk,entry_stop,capital,risk_fraction,frozen_prediction,bias");
   ec_exit_file=ECOpenLedger("exits.csv","forecast_id,component,position_id,deal,completion_msc,observed_server,entry_server,full_exit,deal_actual,deal_stressed,lifecycle_actual,lifecycle_stressed,planned_entry_risk,swap,closed_positive_swap,remaining_volume,frozen_prediction");
   ec_update_file=ECOpenLedger("updates.csv","update_id,label_id,forecast_id,component,position_id,completion_msc,observed_server,applied_server,checkpoint,label,frozen_prediction,bias_before,bias_after,mode");
   ec_equity_file=ECOpenLedger("equity.csv","server,minute,balance,equity,project_actual,core_stressed_balance,conservative_closed,conservative_equity,margin,risk_capital,aggregate_risk,positions,pending_orders,original_daily_units,closed_positive_swap,open_cost_reserve,forecasts,closed_labels,updates,faults");
   if(ec_faults) return(false);
   if(EC_ROLE>0)
     {
      const ulong start=GetTickCount64();
      PrintFormat("V7EC_ONNX_CREATE_BEGIN role=%d bytes=%d CPU_ONLY=1",EC_ROLE,ArraySize(EC_MODEL_BYTES));
      ec_onnx=OnnxCreateFromBuffer(EC_MODEL_BYTES,ONNX_USE_CPU_ONLY);
      const long input_shape[]={1,14};const long output_shape[]={1,1};
      if(ec_onnx==INVALID_HANDLE || !OnnxSetInputShape(ec_onnx,0,input_shape) || !OnnxSetOutputShape(ec_onnx,0,output_shape)) { ECFault("ONNX session/shape initialization"); return(false); }
      PrintFormat("V7EC_ONNX_CREATED role=%d elapsed_ms=%I64u",EC_ROLE,GetTickCount64()-start);
     }
   ec_ready=true;
   return(ECSave());
  }

bool ECFinish()
  {
   if(!ec_ready) return(false);
   ECMark(true);
   if(PositionsTotal()!=0 || OrdersTotal()!=0 || TrackedAggregatePlannedRisk()>1.0e-8) ECFault("final native account not flat");
   for(int c=0;c<6;++c) if(ec_book.entry[c].position_id!=0 || ec_book.entry[c].pending_order!=0) ECFault("final unresolved own lifecycle");
   ECSave();
   FileFlush(ec_equity_file);
   const string path=EC_ROOT+"\\learning\\final.json";
   const int h=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   string biases="[";
   for(int c=0;c<6;++c) biases+=(c>0?",":"")+ECNum(ec_book.bias[c]);
   biases+="]";
   const string row=StringFormat("{\"role\":%d,\"faults\":%I64d,\"forecasts\":%I64d,\"labels\":%I64d,\"updates\":%I64d,\"pending_mature_labels\":%d,\"checkpoint_sequence\":%I64d,\"checkpoint_readbacks\":%I64d,\"minute_marks\":%I64d,\"final_server\":%I64d,\"closed_positive_swap\":",EC_ROLE,ec_faults,ec_book.forecasts,ec_book.labels,ec_book.updates,ec_book.pending_count,ec_book.sequence,ec_readbacks,ec_marks,(long)TimeCurrent())+ECNum(ec_book.closed_positive_swap)+",\"bias\":"+biases+",\"model_sha256\":\""+EC_MODEL_SHA+"\",\"state_contract\":\""+EC_NATIVE_CONTRACT+"\",\"process_restart_demonstrated\":false}";
   if(h==INVALID_HANDLE || FileWriteString(h,row)==0) ECFault("final learning evidence write");
   if(h!=INVALID_HANDLE) {FileFlush(h);FileClose(h);}
   PrintFormat("V7EC_FINAL role=%d faults=%I64d forecasts=%I64d labels=%I64d updates=%I64d pending=%d readbacks=%I64d marks=%I64d",EC_ROLE,ec_faults,ec_book.forecasts,ec_book.labels,ec_book.updates,ec_book.pending_count,ec_readbacks,ec_marks);
   return(ec_faults==0);
  }

void ECShutdown()
  {
   if(ec_onnx!=INVALID_HANDLE) {const ulong before=GetTickCount64();OnnxRelease(ec_onnx);ec_onnx=INVALID_HANDLE;PrintFormat("V7EC_ONNX_RELEASE elapsed_ms=%I64u",GetTickCount64()-before);}
   if(ec_forecast_file!=INVALID_HANDLE) FileClose(ec_forecast_file);
   if(ec_entry_file!=INVALID_HANDLE) FileClose(ec_entry_file);
   if(ec_exit_file!=INVALID_HANDLE) FileClose(ec_exit_file);
   if(ec_update_file!=INVALID_HANDLE) FileClose(ec_update_file);
   if(ec_equity_file!=INVALID_HANDLE) FileClose(ec_equity_file);
  }

#endif
