#ifndef WC_NATIVE_MODULE
#define WC_NATIVE_MODULE
#include <ZetaV7WCControl\WinnerChild\InitialFit.mqh>
#resource "\\Files\\ZetaV7WCControl\\winner-child-kernel.onnx" as uchar wc_graph[]

// The original portfolio remains the owner of parent signals and management.
// This module owns only child positions, causal shadow outcomes and observation.
struct WCParent
  {
   ulong parent;
   int component;
   int direction;
   int alive;
   long entry_msc;
   double entry;
   double original_stop;
   double parent_budget;
   double volume;
   datetime checked_D;
   datetime D;
   long parent_exit_msc;
   int choice;
   int attempted;
   double prediction;
   double features[8];
   double phi[17];
   int shadow; // 0 waiting, 1 active, 2 completed, 3 no legal fill
   double shadow_entry;
   double shadow_stop;
   double shadow_risk;
   double shadow_spread;
   long shadow_cursor_msc;
   int shadow_cursor_ordinal;
   double label;
   datetime available;
   int updated;
   ulong child;
   ulong ticket;
   ulong last_deal;
   double child_entry;
   double child_stop;
   double child_risk;
   double remaining_volume;
   double entry_spread;
   double entry_cost;
   double entry_slip;
   int close_requested;
  };
WCParent wc_parents[];
int wc_active[];
double wc_weights[17];
double wc_P[289];
long wc_handle=INVALID_HANDLE;
int wc_events=INVALID_HANDLE,wc_forecasts=INVALID_HANDLE,wc_equity=INVALID_HANDLE;
long wc_faults=0,wc_inferences=0,wc_updates=0,wc_children=0,wc_closed_children=0;
long wc_labels=0,wc_sequence=0,wc_deferred=0;
double wc_positive_swap=0,wc_child_actual=0,wc_child_stress=0;
double wc_mse_sum=0,wc_zero_mse_sum=0;
datetime wc_mark_minute=0,wc_deferred_minute=0;
string wc_root="";
bool wc_dirty=false,wc_finished=false;
CTrade wc_trade;

void WCFail(const string reason)
  {
   ++wc_faults;
   PrintFormat("WC_FAULT time=%s reason=%s",TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),reason);
   portfolio_state.safety_stopped=true;
   wc_dirty=true;
  }

void WCLog(const string event,const int n,const double a=0,const double b=0,
           const double c=0,const string detail="")
  {
   if(wc_events==INVALID_HANDLE) return;
   ulong parent=0; int component=-1; datetime D=0;
   if(n>=0 && n<ArraySize(wc_parents))
     {parent=wc_parents[n].parent;component=wc_parents[n].component;D=wc_parents[n].D;}
   if(FileWrite(wc_events,(long)TimeCurrent(),event,n,parent,component,(long)D,
                DoubleToString(a,12),DoubleToString(b,12),DoubleToString(c,12),detail)==0)
      WCFail("event write failed");
   FileFlush(wc_events);
  }

bool WCIsMagic(const ulong magic)
  {return(WC_ROLE!=0 && magic>=WC_MAGIC_FIRST && magic<WC_MAGIC_FIRST+5);}

double WCReservedRisk()
  {
   double total=0;
   for(int k=0;k<ArraySize(wc_active);++k)
     {int n=wc_active[k]; if(wc_parents[n].child>0 || wc_parents[n].attempted==1) total+=wc_parents[n].child_risk;}
   return(total);
  }

bool WCAuditSelectedChild()
  {
   ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
   for(int k=0;k<ArraySize(wc_active);++k)
     {
      int n=wc_active[k];
      if(wc_parents[n].child!=id) continue;
      WCParent p=wc_parents[n];
      double step=SymbolInfoDouble(component_definitions[p.component].symbol,SYMBOL_VOLUME_STEP);
      double tick=SymbolInfoDouble(component_definitions[p.component].symbol,SYMBOL_TRADE_TICK_SIZE);
      bool valid=PositionGetString(POSITION_SYMBOL)==component_definitions[p.component].symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC)==WC_MAGIC_FIRST+p.component &&
         (int)PositionGetInteger(POSITION_TYPE)==(p.direction>0?POSITION_TYPE_BUY:POSITION_TYPE_SELL) &&
         MathAbs(PositionGetDouble(POSITION_VOLUME)-p.remaining_volume)<step*.5 &&
         MathAbs(PositionGetDouble(POSITION_SL)-p.child_stop)<tick*.25 &&
         PositionGetDouble(POSITION_TP)==0;
      if(!valid) WCFail("child protection/ownership mismatch");
      return(valid);
     }
   WCFail("unknown child identifier"); return(false);
  }

bool WCAuditSelectedOrder()
  {
   ulong magic=(ulong)OrderGetInteger(ORDER_MAGIC);
   ulong id=(ulong)OrderGetInteger(ORDER_POSITION_ID);
   for(int k=0;k<ArraySize(wc_active);++k)
     {
      WCParent p=wc_parents[wc_active[k]];
      if(magic!=WC_MAGIC_FIRST+p.component || p.child==0) continue;
      bool valid=OrderGetString(ORDER_SYMBOL)==component_definitions[p.component].symbol &&
         OrderGetInteger(ORDER_REASON)==ORDER_REASON_SL && (id==0 || id==p.child) &&
         OrderGetInteger(ORDER_TYPE)==(p.direction>0?ORDER_TYPE_SELL:ORDER_TYPE_BUY) &&
         MathAbs(OrderGetDouble(ORDER_VOLUME_INITIAL)-p.remaining_volume)<1e-9;
      if(valid) return(true);
     }
   WCFail("unknown child pending order"); return(false);
  }

// Write and reread the complete binary checkpoint, including every causal label.
// Struct bytes contain no strings, objects, pointers or dynamically sized arrays.
bool WCSave()
  {
   if(!wc_dirty) return(true);
   ++wc_sequence;
   string path=wc_root+"\\state\\child-"+(wc_sequence%2==0?"a":"b")+".bin";
   int h=FileOpen(path,FILE_WRITE|FILE_BIN);
   if(h==INVALID_HANDLE) {WCFail("snapshot open failed");return(false);}
   FileWriteLong(h,wc_sequence); FileWriteInteger(h,ArraySize(wc_parents));
   FileWriteLong(h,wc_updates); FileWriteLong(h,wc_inferences); FileWriteLong(h,wc_children);
   FileWriteLong(h,wc_closed_children);FileWriteDouble(h,wc_positive_swap);
   FileWriteDouble(h,wc_child_actual);FileWriteDouble(h,wc_child_stress);
   FileWriteArray(h,wc_weights);FileWriteArray(h,wc_P);
   for(int n=0;n<ArraySize(wc_parents);++n) FileWriteStruct(h,wc_parents[n]);
   FileFlush(h); ulong expected=FileTell(h);FileClose(h);
   h=FileOpen(path,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE) {WCFail("snapshot readback open failed");return(false);}
   bool valid=FileSize(h)==expected && FileReadLong(h)==wc_sequence && FileReadInteger(h)==ArraySize(wc_parents);
   valid=(FileReadLong(h)==wc_updates && valid);valid=(FileReadLong(h)==wc_inferences && valid);
   valid=(FileReadLong(h)==wc_children && valid);valid=(FileReadLong(h)==wc_closed_children && valid);
   valid=(FileReadDouble(h)==wc_positive_swap && valid);valid=(FileReadDouble(h)==wc_child_actual && valid);
   valid=(FileReadDouble(h)==wc_child_stress && valid);
   double weights[17],P[289];FileReadArray(h,weights);FileReadArray(h,P);
   for(int j=0;j<17;++j) if(weights[j]!=wc_weights[j]) valid=false;
   for(int j=0;j<289;++j) if(P[j]!=wc_P[j]) valid=false;
   for(int n=0;n<ArraySize(wc_parents);++n)
     {
      WCParent restored={};
      if(FileReadStruct(h,restored)!=sizeof(WCParent)) valid=false;
      uchar original_bytes[],restored_bytes[];
      if(!StructToCharArray(wc_parents[n],original_bytes) || !StructToCharArray(restored,restored_bytes)) valid=false;
      if(ArrayCompare(original_bytes,restored_bytes)!=0) valid=false;
     }
   if(FileTell(h)!=expected) valid=false;FileClose(h);
   if(!valid) {WCFail("complete snapshot readback failed");return(false);}
   wc_dirty=false;return(true);
  }

bool WCInitialize()
  {
   if(InpRunTag=="unset" || StringLen(InpRunTag)>80 || StringFind(InpRunTag,"..")>=0 ||
      StringFind(InpRunTag,"\\")>=0 || StringFind(InpRunTag,"/")>=0) return(false);
   wc_root="ZetaV7WCControl\\"+InpRunTag;
   FolderCreate("ZetaV7WCControl"); FolderCreate(wc_root);FolderCreate(wc_root+"\\state");FolderCreate(wc_root+"\\research");
   STATE_PATH_A=wc_root+"\\state\\state-a.csv";STATE_PATH_B=wc_root+"\\state\\state-b.csv";
   EVENT_PATH_A=wc_root+"\\state\\events-a.csv";EVENT_PATH_B=wc_root+"\\state\\events-b.csv";
   CURRENT_SNAPSHOT_PATH_A=wc_root+"\\state\\current-a.csv";CURRENT_SNAPSHOT_PATH_B=wc_root+"\\state\\current-b.csv";
   OWNERSHIP_PATH=wc_root+"\\state\\runtime.lock";
   RESEARCH_OBSERVATION_DIRECTORY=wc_root+"\\research";
   RESEARCH_OBSERVATION_STATE_PATH_A=wc_root+"\\research\\research-state-a.csv";
   RESEARCH_OBSERVATION_STATE_PATH_B=wc_root+"\\research\\research-state-b.csv";
   RESEARCH_CANDIDATE_LEDGER_PATH=wc_root+"\\research\\research-candidates.csv";
   RESEARCH_LIFECYCLE_LEDGER_PATH=wc_root+"\\research\\research-lifecycles.csv";
   if(FileIsExist(wc_root+"\\fresh.txt") || FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B)) return(false);
   int h=FileOpen(wc_root+"\\fresh.txt",FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return(false);FileWriteString(h,PORTFOLIO_ID+" "+InpRunTag);FileFlush(h);FileClose(h);
   wc_events=FileOpen(wc_root+"\\child-events.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   wc_forecasts=FileOpen(wc_root+"\\forecasts.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
   wc_equity=FileOpen(wc_root+"\\equity.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(wc_events==INVALID_HANDLE || wc_forecasts==INVALID_HANDLE || wc_equity==INVALID_HANDLE) return(false);
   FileWrite(wc_events,"server","event","index","parent","component","D","a","b","c","detail");
   string head="server,index,parent,D,prediction";
   for(int j=0;j<8;++j) head+=",f"+IntegerToString(j);
   for(int j=0;j<17;++j) head+=",phi"+IntegerToString(j);
   for(int j=0;j<17;++j) head+=",w"+IntegerToString(j);
   FileWriteString(wc_forecasts,head+"\r\n");
   FileWrite(wc_equity,"server","balance","equity","project_realized","stress_balance","positive_swap","conservative_equity","capital","multiplier","planned_risk","margin","positions","children");
   ArrayCopy(wc_weights,wc_initial_weights);ArrayCopy(wc_P,wc_initial_P);
   if(WC_ROLE>0)
     {
      wc_handle=OnnxCreateFromBuffer(wc_graph,ONNX_DEFAULT);
      if(wc_handle==INVALID_HANDLE) return(false);
      ulong fs[2]={1,8},ws[2]={17,1},ys[2]={1,1},ps[2]={1,17};
      if(!OnnxSetInputShape(wc_handle,0,fs) || !OnnxSetInputShape(wc_handle,1,ws) ||
         !OnnxSetOutputShape(wc_handle,0,ys) || !OnnxSetOutputShape(wc_handle,1,ps)) return(false);
     }
   wc_trade.SetAsyncMode(false);wc_trade.SetDeviationInPoints(InpDeviationPoints);
   wc_dirty=true;WCLog("INITIAL",-1,WC_ROLE,66,0,"fresh2024fit;empty2025pending");
   return(WCSave());
  }

void WCParentExit(const ResearchExitSnapshot &snapshot)
  {
   if(HistoryDealSelect(snapshot.deal_ticket))
      wc_positive_swap+=MathMax(0,HistoryDealGetDouble(snapshot.deal_ticket,DEAL_SWAP));
   else WCFail("parent swap observation unavailable");
   wc_dirty=true;
   if(!snapshot.full_exit) return;
   for(int k=0;k<ArraySize(wc_active);++k)
     {
      int n=wc_active[k];
      if(wc_parents[n].parent!=snapshot.position_identifier) continue;
      wc_parents[n].alive=0;wc_parents[n].parent_exit_msc=snapshot.deal_time_msc;
      WCLog(wc_parents[n].D==0?"PARENT_NO_TRIGGER":"PARENT_END",n,snapshot.deal_net,snapshot.stressed_net,
            snapshot.execution_price,IntegerToString(snapshot.deal_time_msc));return;
     }
  }

void WCCaptureParents()
  {
   if(WC_ROLE==0) return;
   for(int component=0;component<5;++component)
     {
      ulong id=component_states[component].position_identifier;if(id==0) continue;
      bool seen=false;for(int k=0;k<ArraySize(wc_active);++k) if(wc_parents[wc_active[k]].parent==id) seen=true;
      if(seen) continue;
      ulong ticket=0;datetime opened=0;
      if(CountOwnedPositions(component,ticket,opened)!=1 || !PositionSelectByTicket(ticket)) continue;
      int n=ArraySize(wc_parents);if(ArrayResize(wc_parents,n+1)!=n+1) {WCFail("parent allocation");return;}
      ZeroMemory(wc_parents[n]);wc_parents[n].parent=id;wc_parents[n].component=component;wc_parents[n].alive=1;
      wc_parents[n].entry_msc=PositionGetInteger(POSITION_TIME_MSC);
      wc_parents[n].entry=PositionGetDouble(POSITION_PRICE_OPEN);
      wc_parents[n].direction=component_states[component].entry_direction;
      wc_parents[n].original_stop=component_states[component].entry_stop_loss;
      wc_parents[n].parent_budget=component_states[component].entry_planned_risk_usd;
      wc_parents[n].volume=component_states[component].entry_volume;
      wc_parents[n].checked_D=(datetime)(wc_parents[n].entry_msc/60000*60);
      int count=ArraySize(wc_active);if(ArrayResize(wc_active,count+1)!=count+1) {WCFail("active allocation");return;}
      wc_active[count]=n;wc_dirty=true;
      WCLog("PARENT_BIRTH",n,wc_parents[n].entry,wc_parents[n].original_stop,wc_parents[n].volume,
            StringFormat("entry_msc=%I64d;budget=%.12f",wc_parents[n].entry_msc,wc_parents[n].parent_budget));
     }
  }

void WCUpdateBefore(const datetime D)
  {
   if(WC_ROLE!=3) return;
   while(true)
     {
      int best=-1;
      for(int n=0;n<ArraySize(wc_parents);++n)
        {
         WCParent p=wc_parents[n];
         if(p.shadow!=2 || p.updated || p.available>=D) continue;
         if(best<0 || p.available<wc_parents[best].available ||
            (p.available==wc_parents[best].available && (p.D<wc_parents[best].D ||
             (p.D==wc_parents[best].D && p.parent<wc_parents[best].parent)))) best=n;
        }
      if(best<0) return;
      double pv[17],next[289];ArrayInitialize(pv,0);
      double denominator=.995,estimate=0;
      for(int i=0;i<17;++i)
        {
         estimate+=wc_parents[best].phi[i]*wc_weights[i];
         for(int j=0;j<17;++j) pv[i]+=wc_P[i*17+j]*wc_parents[best].phi[j];
         denominator+=wc_parents[best].phi[i]*pv[i];
        }
      if(!MathIsValidNumber(denominator) || denominator<=0) {WCFail("RLS denominator");return;}
      for(int i=0;i<17;++i)
        {
         wc_weights[i]+=pv[i]/denominator*(wc_parents[best].label-estimate);
         if(!MathIsValidNumber(wc_weights[i])) {WCFail("RLS weight");return;}
         for(int j=0;j<17;++j) next[i*17+j]=(wc_P[i*17+j]-pv[i]*pv[j]/denominator)/.995;
        }
      for(int i=0;i<17;++i) for(int j=0;j<17;++j) wc_P[i*17+j]=.5*(next[i*17+j]+next[j*17+i]);
      for(int i=0;i<17;++i) if(!MathIsValidNumber(wc_P[i*17+i]) || wc_P[i*17+i]<=0) {WCFail("RLS covariance");return;}
      wc_parents[best].updated=1;++wc_updates;wc_dirty=true;
      WCLog("UPDATE",best,wc_parents[best].label,(double)wc_parents[best].available,(double)D,
            StringFormat("ordinal=%I64d;denominator=%.17g;estimate=%.17g",wc_updates,denominator,estimate));
     }
  }

bool WCForecast(const int n)
  {
   float features[8],weights[17],output[1],basis[17];
   for(int i=0;i<8;++i) features[i]=(float)((wc_parents[n].features[i]-wc_mean[i])/wc_sd[i]);
   for(int i=0;i<17;++i) weights[i]=(float)wc_weights[i];
   if(!OnnxRun(wc_handle,ONNX_NO_CONVERSION,features,weights,output,basis)) {WCFail("ONNX run");return(false);}
   if(!MathIsValidNumber(output[0])) {WCFail("nonfinite forecast");return(false);}
   wc_parents[n].prediction=(double)output[0];
   string row=StringFormat("%I64d,%d,%I64u,%I64d,%.17g",(long)TimeCurrent(),n,wc_parents[n].parent,(long)wc_parents[n].D,(double)output[0]);
   for(int i=0;i<8;++i) row+=StringFormat(",%.17g",wc_parents[n].features[i]);
   for(int i=0;i<17;++i)
     {if(!MathIsValidNumber(basis[i])) {WCFail("nonfinite phi");return(false);}wc_parents[n].phi[i]=(double)basis[i];row+=StringFormat(",%.17g",(double)basis[i]);}
   for(int i=0;i<17;++i) row+=StringFormat(",%.17g",(double)weights[i]);
   if(FileWriteString(wc_forecasts,row+"\r\n")==0) {WCFail("forecast write");return(false);}FileFlush(wc_forecasts);
   ++wc_inferences;wc_dirty=true;return(true);
  }

double WCBarExit(const MqlRates &bar,const int direction,const double point)
  {return(bar.close+(direction<0?(double)bar.spread*point:0));}

void WCTrigger(const int n,const datetime D)
  {
   if(wc_parents[n].D>0 || !wc_parents[n].alive || D<=wc_parents[n].checked_D) return;
   WCParent p=wc_parents[n];string symbol=component_definitions[p.component].symbol;
   MqlRates current[];int got=CopyRates(symbol,PERIOD_M1,D-60,D-1,current);
   if(got!=1 || current[0].time!=D-60) return; // Retry the same completed minute after native synchronization.
   wc_parents[n].checked_D=D;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT),R=p.direction*(p.entry-p.original_stop);
   if(R<=0) {WCFail("invalid original parent R");return;}
   double close=WCBarExit(current[0],p.direction,point);
   if(p.direction*(close-p.entry)<R) return;
   wc_parents[n].D=D;wc_dirty=true;WCLog("FIRST_TRIGGER",n,close,R,p.parent_budget);
   MqlRates bars[];got=CopyRates(symbol,PERIOD_M1,D-31*60,D-1,bars);
   bool complete=got==31;
   for(int j=0;j<got;++j) if(bars[j].time!=D-31*60+j*60) complete=false;
   if(!complete) {wc_parents[n].shadow=3;wc_parents[n].attempted=2;WCLog("MISSING_PREFIX",n,got);return;}
   double hi=-DBL_MAX,lo=DBL_MAX;
   for(int j=1;j<31;++j)
     {double shift=(p.direction<0?bars[j].spread*point:0);hi=MathMax(hi,bars[j].high+shift);lo=MathMin(lo,bars[j].low+shift);}
   double adverse=0,favorable=MathMax(0,p.direction*(close-p.entry));
   datetime path_start=(datetime)((p.entry_msc/60000+1)*60);
   if(path_start<D)
     {
      MqlRates path[];int count=CopyRates(symbol,PERIOD_M1,path_start,D-1,path);
      if(count!=(int)((D-path_start)/60)) {wc_parents[n].shadow=3;wc_parents[n].attempted=2;WCLog("MISSING_PARENT_PATH",n,count);return;}
      for(int j=0;j<count;++j)
        {
         if(path[j].time!=path_start+j*60) {WCFail("parent path chronology");return;}
         double shift=(p.direction<0?path[j].spread*point:0);
         double high=path[j].high+shift,low=path[j].low+shift;
         favorable=MathMax(favorable,p.direction>0?high-p.entry:p.entry-low);
         adverse=MathMax(adverse,p.direction>0?p.entry-low:high-p.entry);
        }
     }
   int hold=(p.component==1 || p.component==4?21600:14400);
   wc_parents[n].features[0]=p.direction*(close-p.entry)/R;
   wc_parents[n].features[1]=((double)D-(double)(p.entry_msc/1000))/hold;
   wc_parents[n].features[2]=p.direction*(close-WCBarExit(bars[25],p.direction,point))/R;
   wc_parents[n].features[3]=p.direction*(close-WCBarExit(bars[0],p.direction,point))/R;
   wc_parents[n].features[4]=(hi-lo)/R;wc_parents[n].features[5]=MathMax(0,adverse)/R;
   wc_parents[n].features[6]=MathMax(0,favorable)/R;wc_parents[n].features[7]=bars[30].spread*point/R;
   WCUpdateBefore(D);if(wc_faults>0 || !WCForecast(n)) return;
   wc_parents[n].choice=(WC_ROLE==1 || wc_parents[n].prediction>0?1:0);
   WCLog(wc_parents[n].choice?"MODEL_OPEN":"MODEL_DECLINE",n,wc_parents[n].prediction);
  }

void WCCompletedMinutes(const datetime now_D)
  {
   while(wc_faults==0)
     {
      int best=-1;datetime first=0;
      for(int k=0;k<ArraySize(wc_active);++k)
        {
         int n=wc_active[k];
         if(!wc_parents[n].alive || wc_parents[n].D>0 || wc_parents[n].checked_D>=now_D) continue;
         string symbol=component_definitions[wc_parents[n].component].symbol;
         MqlRates completed[];
         int count=CopyRates(symbol,PERIOD_M1,wc_parents[n].checked_D,now_D-1,completed);
         if(count<1) continue;
         datetime origin=completed[0].time+60;
         if(origin>now_D || origin<=wc_parents[n].checked_D) continue;
         if(best<0 || origin<first || (origin==first && wc_parents[n].parent<wc_parents[best].parent))
           {best=n;first=origin;}
        }
      if(best<0) return;
      datetime before=wc_parents[best].checked_D;
      WCTrigger(best,first);
      if(wc_parents[best].checked_D==before) return;
     }
  }

bool WCGeometry(const int n,const MqlTick &tick,double &entry,double &stop,double &risk)
  {
   WCParent p=wc_parents[n];string symbol=component_definitions[p.component].symbol;
   entry=(p.direction>0?tick.ask:tick.bid);double size=SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE);
   if(size<=0) return(false);
   double middle=(entry+p.entry)*.5;
   stop=(p.direction>0?MathCeil(middle/size-1e-10):MathFloor(middle/size+1e-10))*size;
   stop=NormalizeDouble(stop,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS));
   double distance=p.direction*(entry-stop),exit_distance=p.direction*((p.direction>0?tick.bid:tick.ask)-stop);
   return(distance>0 && exit_distance+size*.25>=MinimumProtectionDistance(symbol) &&
          GrossStopRisk(symbol,p.direction,p.volume,entry,stop,risk) && risk<=p.parent_budget*.5+1e-9);
  }

void WCShadowClose(const int n,const double exit_price,const double exit_spread,const long msc,const bool stopped)
  {
   WCParent p=wc_parents[n];double unit=p.volume*SymbolInfoDouble(component_definitions[p.component].symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   double actual=p.direction*(exit_price-p.shadow_entry)*unit;
   double gap=(stopped?MathMax(0,p.direction*(p.shadow_stop-exit_price)):0);
   double stress=actual-(MathMax(p.shadow_spread,exit_spread)+gap)*unit;
   wc_parents[n].label=stress/p.shadow_risk;wc_parents[n].available=(datetime)((msc/60000+1)*60);
   wc_parents[n].shadow=2;++wc_labels;wc_dirty=true;
   wc_mse_sum+=MathPow(wc_parents[n].label-p.prediction,2);wc_zero_mse_sum+=MathPow(wc_parents[n].label,2);
   WCLog("SHADOW_CLOSE",n,actual,stress,wc_parents[n].label,
         StringFormat("exit_msc=%I64d;available=%I64d;exit=%.12f;spread=%.12f;stop=%d",msc,(long)wc_parents[n].available,exit_price,exit_spread,stopped));
  }

void WCShadowTicks(const int n)
  {
   if(wc_parents[n].shadow!=1) return;
   WCParent p=wc_parents[n];string symbol=component_definitions[p.component].symbol;MqlTick now={};
   if(!SymbolInfoTick(symbol,now) || now.time_msc<p.shadow_cursor_msc) return;
   long until=now.time_msc;
   if(!p.alive && p.parent_exit_msc>0) until=MathMin(until,p.parent_exit_msc);
   if(until>=p.shadow_cursor_msc)
     {
      MqlTick ticks[];int count=CopyTicksRange(symbol,ticks,COPY_TICKS_ALL,(ulong)p.shadow_cursor_msc,(ulong)until);
      if(count<0) {WCFail("shadow tick range unavailable");return;}
      int ordinal=0;
      for(int j=0;j<count;++j)
        {
         if(j==0 || ticks[j].time_msc!=ticks[j-1].time_msc) ordinal=0;
         ++ordinal;
         if(ticks[j].time_msc==p.shadow_cursor_msc && ordinal<=p.shadow_cursor_ordinal) continue;
         if(ticks[j].ask<=ticks[j].bid || ticks[j].bid<=0) {WCFail("invalid shadow tick");return;}
         wc_parents[n].shadow_cursor_msc=ticks[j].time_msc;wc_parents[n].shadow_cursor_ordinal=ordinal;
         double exit_price=(p.direction>0?ticks[j].bid:ticks[j].ask);
         if(p.direction*(exit_price-p.shadow_stop)<=0)
           {WCShadowClose(n,exit_price,ticks[j].ask-ticks[j].bid,ticks[j].time_msc,true);return;}
        }
     }
   if(!p.alive && ExecutableTick(symbol,now) && now.time_msc>=p.parent_exit_msc && TradeSessionAllows(symbol,TimeCurrent(),false))
      WCShadowClose(n,p.direction>0?now.bid:now.ask,now.ask-now.bid,now.time_msc,false);
  }

void WCEntry(const int n)
  {
   WCParent p=wc_parents[n];if(p.D==0 || p.shadow!=0 || p.attempted!=0) return;
   if(!p.alive || TimeCurrent()>=p.D+120)
     {wc_parents[n].shadow=3;wc_parents[n].attempted=2;WCLog("NO_LEGAL_ENTRY",n);wc_dirty=true;return;}
   string symbol=component_definitions[p.component].symbol;MqlTick tick={};
   if(!ExecutableTick(symbol,tick) || tick.time<p.D || !TradeSessionAllows(symbol,TimeCurrent(),true)) return;
   ulong parent_ticket=0;datetime parent_opened=0;
   if(CountOwnedPositions(p.component,parent_ticket,parent_opened)!=1 || !PositionSelectByTicket(parent_ticket) ||
      (ulong)PositionGetInteger(POSITION_IDENTIFIER)!=p.parent) return;
   double entry=0,stop=0,risk=0;
   if(!WCGeometry(n,tick,entry,stop,risk))
     {wc_parents[n].shadow=3;wc_parents[n].attempted=2;WCLog("GEOMETRY_REFUSED",n,entry,stop,risk);wc_dirty=true;return;}
   wc_parents[n].shadow=1;wc_parents[n].shadow_entry=entry;wc_parents[n].shadow_stop=stop;
   wc_parents[n].shadow_risk=risk;wc_parents[n].shadow_spread=tick.ask-tick.bid;
   wc_parents[n].shadow_cursor_msc=tick.time_msc;
   MqlTick same[];int same_count=CopyTicksRange(symbol,same,COPY_TICKS_ALL,(ulong)tick.time_msc,(ulong)tick.time_msc);
   if(same_count<1) {WCFail("shadow entry tick boundary");return;}
   wc_parents[n].shadow_cursor_ordinal=same_count;
   WCLog("SHADOW_OPEN",n,entry,stop,risk,StringFormat("msc=%I64d;ordinal=%d;volume=%.8f",tick.time_msc,same_count,p.volume));
   wc_parents[n].attempted=2;wc_dirty=true;
   if(!p.choice) {WCSave();return;}
   double capital=ConservativeRiskCapital(),budget=.04*capital,buffered=0;
   long steps=0;
   bool admission=NewEntriesOperationallyAllowed() && capital>0 && VolumeToSteps(symbol,p.volume,steps) &&
      p.volume>=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN) && p.volume<=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX) &&
      BufferedPlannedRisk(symbol,p.direction,p.volume,entry,stop,buffered) && buffered<=budget+.01 &&
      TrackedAggregatePlannedRisk()+budget<=.12*capital+.01 && MarginAllows(symbol,p.direction,p.volume);
   if(!admission) {WCLog("NATIVE_ADMISSION_REFUSED",n,capital,budget,TrackedAggregatePlannedRisk());WCSave();return;}
   wc_parents[n].child_entry=entry;wc_parents[n].child_stop=stop;wc_parents[n].child_risk=budget;
   wc_parents[n].entry_spread=tick.ask-tick.bid;wc_parents[n].remaining_volume=p.volume;
   wc_parents[n].attempted=1;
   WCLog("CHILD_INTENT",n,entry,stop,budget,StringFormat("parent=%I64u;volume=%.8f;capital=%.12f;aggregate=%.12f;margin=%.12f",p.parent,p.volume,capital,TrackedAggregatePlannedRisk(),AccountInfoDouble(ACCOUNT_MARGIN)));
   if(!WCSave()) return;
   wc_trade.SetExpertMagicNumber(WC_MAGIC_FIRST+p.component);wc_trade.SetTypeFillingBySymbol(symbol);
   execution_state.trade_operation_active=true;
   bool sent=(p.direction>0?wc_trade.Buy(p.volume,symbol,0,stop,0,"WC:"+(string)p.parent):wc_trade.Sell(p.volume,symbol,0,stop,0,"WC:"+(string)p.parent));
   execution_state.trade_operation_active=false;
   uint ret=wc_trade.ResultRetcode();ulong deal=wc_trade.ResultDeal();
   if(!sent || !IsCompletedMarketTradeRetcode(ret))
     {wc_parents[n].attempted=2;wc_parents[n].child_risk=0;WCLog("CHILD_REJECTED",n,ret);wc_dirty=true;WCSave();return;}
   if(deal==0 || !HistoryDealSelect(deal)) {WCFail("child entry deal unavailable");return;}
   ulong id=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);ulong ticket=0;int count=0;
   for(int j=PositionsTotal()-1;j>=0;--j)
     {ulong t=PositionGetTicket(j);if((ulong)PositionGetInteger(POSITION_IDENTIFIER)==id){ticket=t;++count;}}
   if(count!=1 || !PositionSelectByTicket(ticket)) {WCFail("child fill association");return;}
   wc_parents[n].child=id;wc_parents[n].ticket=ticket;wc_parents[n].child_entry=PositionGetDouble(POSITION_PRICE_OPEN);
   wc_parents[n].entry_cost=HistoryDealGetDouble(deal,DEAL_COMMISSION)+HistoryDealGetDouble(deal,DEAL_SWAP)+HistoryDealGetDouble(deal,DEAL_FEE);
   wc_positive_swap+=MathMax(0,HistoryDealGetDouble(deal,DEAL_SWAP));
   wc_parents[n].entry_slip=MathMax(0,p.direction*(wc_parents[n].child_entry-entry))*p.volume*SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE);
   wc_parents[n].attempted=2;
   double filled_risk=0;
   if(!WCAuditSelectedChild() || !GrossStopRisk(symbol,p.direction,p.volume,wc_parents[n].child_entry,stop,filled_risk) || filled_risk>p.parent_budget*.5+1e-9)
      WCFail("filled child risk/geometry mismatch");
   ++wc_children;wc_dirty=true;
   portfolio_state.maximum_aggregate_planned_risk_usd=MathMax(portfolio_state.maximum_aggregate_planned_risk_usd,TrackedAggregatePlannedRisk());
   WCLog("CHILD_OPEN",n,wc_parents[n].child_entry,stop,budget,StringFormat("child=%I64u;ticket=%I64u;deal=%I64u;volume=%.8f;entry_cost=%.12f;entry_slip=%.12f",id,ticket,deal,p.volume,wc_parents[n].entry_cost,wc_parents[n].entry_slip));
   WCSave();SaveState();
  }

void WCReconcileChildren()
  {
   for(int k=0;k<ArraySize(wc_active);++k)
     {
      int n=wc_active[k];WCParent p=wc_parents[n];if(p.child==0) continue;
      if(PositionSelectByTicket(p.ticket) && MathAbs(PositionGetDouble(POSITION_VOLUME)-p.remaining_volume)<1e-9) continue;
      if(!HistorySelectByPosition(p.child)) {WCFail("child history selection");continue;}
      ulong deals[];int total=HistoryDealsTotal();ArrayResize(deals,total);
      for(int j=0;j<total;++j) deals[j]=HistoryDealGetTicket(j);
      for(int j=0;j<total;++j)
        {
         ulong deal=deals[j];if(deal<=wc_parents[n].last_deal || !HistoryDealSelect(deal)) continue;
         long kind=HistoryDealGetInteger(deal,DEAL_ENTRY);if(kind!=DEAL_ENTRY_OUT && kind!=DEAL_ENTRY_OUT_BY) continue;
         if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=WC_MAGIC_FIRST+p.component || HistoryDealGetString(deal,DEAL_SYMBOL)!=component_definitions[p.component].symbol)
           {WCFail("child exit identity");continue;}
         double v=HistoryDealGetDouble(deal,DEAL_VOLUME);double remaining=wc_parents[n].remaining_volume;
         if(v<=0 || v>remaining+1e-9) {WCFail("child exit quantity");continue;}
         double fraction=v/remaining,entry_cost=wc_parents[n].entry_cost*fraction,entry_slip=wc_parents[n].entry_slip*fraction;
         long msc=HistoryDealGetInteger(deal,DEAL_TIME_MSC);MqlTick q={};
         if(!QuoteAtMilliseconds(component_definitions[p.component].symbol,msc,q)) {WCFail("child exit quote");continue;}
         double price=HistoryDealGetDouble(deal,DEAL_PRICE),swap=HistoryDealGetDouble(deal,DEAL_SWAP);
         double costs=HistoryDealGetDouble(deal,DEAL_COMMISSION)+swap+HistoryDealGetDouble(deal,DEAL_FEE);
         double actual=HistoryDealGetDouble(deal,DEAL_PROFIT)+costs+entry_cost;
         double unit=v*SymbolInfoDouble(component_definitions[p.component].symbol,SYMBOL_TRADE_CONTRACT_SIZE);
         double slip=MathMax(0,p.direction*((p.direction>0?q.bid:q.ask)-price))*unit;
         double stress=actual-MathMax(p.entry_spread,q.ask-q.bid)*unit-entry_slip-slip-MathMax(0,-entry_cost)-MathMax(0,-costs);
         wc_parents[n].last_deal=deal;wc_parents[n].remaining_volume-=v;
         wc_parents[n].entry_cost-=entry_cost;wc_parents[n].entry_slip-=entry_slip;
         wc_parents[n].child_risk*=MathMax(0,1-fraction);
         wc_positive_swap+=MathMax(0,swap);wc_child_actual+=actual;wc_child_stress+=stress;
         portfolio_state.project_realized_net+=actual;portfolio_state.stressed_balance+=stress;
         portfolio_state.stressed_peak=MathMax(portfolio_state.stressed_peak,portfolio_state.stressed_balance);
         portfolio_state.stressed_maximum_closed_drawdown=MathMax(portfolio_state.stressed_maximum_closed_drawdown,portfolio_state.stressed_peak-portfolio_state.stressed_balance);
         WCLog("CHILD_CLOSE",n,actual,stress,MathMax(0,swap),StringFormat("deal=%I64u;child=%I64u;msc=%I64d;price=%.12f;volume=%.8f;remaining=%.8f;reason=%I64d",deal,p.child,msc,price,v,wc_parents[n].remaining_volume,HistoryDealGetInteger(deal,DEAL_REASON)));
         if(wc_parents[n].remaining_volume<1e-9) {wc_parents[n].child=0;wc_parents[n].ticket=0;wc_parents[n].child_risk=0;++wc_closed_children;}
         wc_dirty=true;WCSave();SaveState();
        }
     }
  }

void WCParentCloseDuty(const int n)
  {
   if(wc_parents[n].alive || wc_parents[n].child==0) return;
   WCParent p=wc_parents[n];MqlTick tick={};string symbol=component_definitions[p.component].symbol;
   if(!PositionSelectByTicket(p.ticket)) return;
   if(!ExecutableTick(symbol,tick) || !TradeSessionAllows(symbol,TimeCurrent(),false)) return;
   wc_parents[n].close_requested=1;wc_dirty=true;WCLog("CHILD_PARENT_CLOSE_INTENT",n,p.ticket);if(!WCSave()) return;
   wc_trade.SetExpertMagicNumber(WC_MAGIC_FIRST+p.component);wc_trade.SetTypeFillingBySymbol(symbol);
   execution_state.trade_operation_active=true;bool done=wc_trade.PositionClose(p.ticket);execution_state.trade_operation_active=false;
   WCLog("CHILD_PARENT_CLOSE_RECEIPT",n,wc_trade.ResultRetcode(),done);
  }

void WCObserve(const bool force=false)
  {
   datetime minute=(datetime)((long)TimeCurrent()/60*60);
   if(!force && minute==wc_mark_minute) return;
   double conservative=portfolio_state.stressed_balance-wc_positive_swap;bool known=true;int children=0;
   for(int j=PositionsTotal()-1;j>=0;--j)
     {
      ulong ticket=PositionGetTicket(j);if(ticket==0) {known=false;continue;}
      ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER),magic=(ulong)PositionGetInteger(POSITION_MAGIC);
      string symbol=PositionGetString(POSITION_SYMBOL);double v=PositionGetDouble(POSITION_VOLUME),profit=PositionGetDouble(POSITION_PROFIT),swap=PositionGetDouble(POSITION_SWAP);
      double entry_spread=0,cost=0,slip=0;bool found=false;
      for(int c=0;c<6;++c) if(magic==component_definitions[c].magic && component_states[c].position_identifier==id && component_states[c].entry_cost_known)
        {entry_spread=component_states[c].entry_spread_price;cost=component_states[c].entry_transaction_cost;slip=component_states[c].entry_adverse_slippage;found=true;break;}
      if(WCIsMagic(magic)) for(int k=0;k<ArraySize(wc_active);++k)
        {WCParent p=wc_parents[wc_active[k]];if(p.child==id){entry_spread=p.entry_spread;cost=p.entry_cost;slip=p.entry_slip;found=true;++children;break;}}
      MqlTick q={};if(!found || !StructurallyValidTick(symbol,q)) {known=false;continue;}
      conservative+=profit+cost+swap-MathMax(entry_spread,q.ask-q.bid)*v*SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE)-slip-MathMax(0,-cost)-MathMax(0,-swap)-MathMax(0,swap);
     }
   // A just-executed SL can be visible before the original reconciliation callback.
   for(int c=0;c<6;++c) if(component_states[c].position_identifier>0)
     {ulong ticket=0;datetime opened=0;if(CountOwnedPositions(c,ticket,opened)!=1) known=false;}
   for(int k=0;k<ArraySize(wc_active);++k)
     {WCParent p=wc_parents[wc_active[k]];if(p.child>0 && !PositionSelectByTicket(p.ticket)) known=false;}
   if(!known)
     {
      if(wc_deferred_minute==0) {wc_deferred_minute=minute;++wc_deferred;WCLog("MARK_DEFERRED",-1,(double)minute);}
      else if(minute>wc_deferred_minute) WCFail("unresolved minute mark");
      if(force) WCFail("unknown final mark");return;
     }
   if(wc_deferred_minute>0)
     {if(minute!=wc_deferred_minute) WCFail("mark crossed minute");WCLog("MARK_RESOLVED",-1,(double)wc_deferred_minute);wc_deferred_minute=0;}
   if(FileWrite(wc_equity,(long)TimeCurrent(),DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),10),DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),10),
      DoubleToString(portfolio_state.project_realized_net,10),DoubleToString(portfolio_state.stressed_balance,10),DoubleToString(wc_positive_swap,10),
      DoubleToString(conservative,10),DoubleToString(ConservativeRiskCapital(),10),portfolio_state.day_volume_multiplier,
      DoubleToString(TrackedAggregatePlannedRisk(),10),DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN),10),PositionsTotal(),children)==0) WCFail("equity write");
   wc_mark_minute=minute;
   if(force || (long)minute%3600==0) FileFlush(wc_equity);
  }

void WCBeforeTick()
  {if(WC_ROLE>0) WCReconcileChildren();}

void WCAfterTick()
  {
   if(WC_ROLE>0)
     {
      WCCaptureParents();datetime D=(datetime)((long)TimeCurrent()/60*60);
      // All shadow completions are observed before same-origin online forecasts.
      for(int k=0;k<ArraySize(wc_active);++k) WCShadowTicks(wc_active[k]);
      for(int k=0;k<ArraySize(wc_active);++k) WCParentCloseDuty(wc_active[k]);
      WCReconcileChildren();
      WCCompletedMinutes(D);
      for(int k=0;k<ArraySize(wc_active);++k)
        {int n=wc_active[k];if(wc_faults==0) WCEntry(n);}
      for(int k=ArraySize(wc_active)-1;k>=0;--k)
        {int n=wc_active[k];if(!wc_parents[n].alive && wc_parents[n].child==0 && wc_parents[n].shadow!=1)
          {for(int j=k;j<ArraySize(wc_active)-1;++j) wc_active[j]=wc_active[j+1];ArrayResize(wc_active,ArraySize(wc_active)-1);}}
     }
   WCObserve();if(wc_dirty) WCSave();
  }

void WCFinish()
  {
   if(wc_finished) return;wc_finished=true;WCReconcileChildren();WCObserve(true);
   int pending=0,shadow_open=0;
   for(int n=0;n<ArraySize(wc_parents);++n)
     {if(wc_parents[n].shadow==2 && !wc_parents[n].updated) ++pending;if(wc_parents[n].shadow==1) ++shadow_open;}
   if(PositionsTotal()!=0 || OrdersTotal()!=0 || shadow_open!=0 || wc_children!=wc_closed_children) WCFail("nonflat or incomplete final child path");
   wc_dirty=true;WCSave();
   PrintFormat("WC_RESULT role=%d faults=%I64d parents=%d inferences=%I64d updates=%I64d labels=%I64d children=%I64d closed_children=%I64d pending=%d shadow_open=%d child_actual=%.12f child_stress=%.12f positive_swap=%.12f mse_sum=%.12f zero_mse_sum=%.12f deferred=%I64d unresolved=%I64d sequence=%I64d",
      WC_ROLE,wc_faults,ArraySize(wc_parents),wc_inferences,wc_updates,wc_labels,wc_children,wc_closed_children,pending,shadow_open,wc_child_actual,wc_child_stress,wc_positive_swap,wc_mse_sum,wc_zero_mse_sum,wc_deferred,(long)wc_deferred_minute,wc_sequence);
  }

void WCShutdown()
  {
   if(wc_events!=INVALID_HANDLE) FileClose(wc_events);wc_events=INVALID_HANDLE;
   if(wc_forecasts!=INVALID_HANDLE) FileClose(wc_forecasts);wc_forecasts=INVALID_HANDLE;
   if(wc_equity!=INVALID_HANDLE) FileClose(wc_equity);wc_equity=INVALID_HANDLE;
   if(wc_handle!=INVALID_HANDLE) OnnxRelease(wc_handle);wc_handle=INVALID_HANDLE;
  }
#endif
