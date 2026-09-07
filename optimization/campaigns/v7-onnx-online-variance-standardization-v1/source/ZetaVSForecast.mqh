#ifndef ZETA_VS_FORECAST_MQH
#define ZETA_VS_FORECAST_MQH

#include "ZetaVSModel.mqh"

struct VSForecastRecord
  {
   bool active;
   bool consumed;
   bool label_valid;
   int progress;
   datetime origin_closed_bar;
   datetime origin;
   datetime target_closed_bar;
   datetime available;
   double v0;
   double ratio;
   double sum_return;
   double label;
   double x[8];
  };

VSForecastRecord vs_records[3][64];
datetime vs_unavailable[3][64];
datetime vs_last_closed[3];
int vs_cursor[3];
int vs_unavailable_cursor[3];
double vs_weights[3][8];
long vs_forecasts[3];
long vs_updates[3];
long vs_missing_source[3];
long vs_entry_applied[3];
long vs_entry_fallback[3];
long vs_inference_faults=0;
long vs_learning_write_faults=0;
long vs_strict_maturity_faults=0;
long vs_onnx_handle=INVALID_HANDLE;
int vs_forecast_file=INVALID_HANDLE;
int vs_update_file=INVALID_HANDLE;
int vs_entry_file=INVALID_HANDLE;
datetime vs_last_refresh_second=0;
long vs_last_refresh_slot=-1;
const datetime VS_LEARNING_START=D'2025.01.01 00:00';

string VSSymbol(const int kind) { return(kind==1 ? "US30" : "US100"); }
ENUM_TIMEFRAMES VSPeriod(const int kind) { return(kind==2 ? PERIOD_M15 : PERIOD_H1); }
int VSHorizon(const int kind) { return(kind==0 ? 1 : (kind==1 ? 4 : 12)); }
int VSWindow(const int kind) { return(kind==2 ? 96 : 120); }

void VSLearningFault(const string reason)
  {
   ++vs_inference_faults;
   PrintFormat("VS_LEARNING_FAULT %s error=%d",reason,GetLastError());
   EngageSafetyStop("variance learning evidence: "+reason);
  }

bool VSForecastInit(const string root_path)
  {
   const string forecast_path=root_path+"\\forecasts.csv";
   const string updates_path=root_path+"\\updates.csv";
   const string entries_path=root_path+"\\entry-features.csv";
   if(FileIsExist(forecast_path) || FileIsExist(updates_path) || FileIsExist(entries_path))
      return(false);
   vs_forecast_file=FileOpen(forecast_path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   vs_update_file=FileOpen(updates_path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   vs_entry_file=FileOpen(entries_path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(vs_forecast_file==INVALID_HANDLE || vs_update_file==INVALID_HANDLE || vs_entry_file==INVALID_HANDLE)
      return(false);
   FileWrite(vs_forecast_file,"kind","origin","closed_bar","observed_server","v0","ratio","updates_before","x0","x1","x2","x3","x4","x5","x6","x7");
   FileWrite(vs_update_file,"kind","label_origin","available","before_origin","label","complete","update_count","w0","w1","w2","w3","w4","w5","w6","w7");
   FileWrite(vs_entry_file,"kind","server","decision_closed_bar","forecast_origin_bar","original_feature","candidate_feature","status");
   for(int k=0;k<3;++k)
     {
      vs_last_closed[k]=VS_LEARNING_START-PeriodSeconds(VSPeriod(k))-1;
      for(int j=0;j<8;++j) vs_weights[k][j]=VS_INITIAL_WEIGHTS[k][j];
     }
   vs_onnx_handle=OnnxCreateFromBuffer(VS_MODEL_BYTES,0);
   if(vs_onnx_handle==INVALID_HANDLE) return(false);
   const ulong shape_x[2]={1,8};
   const ulong shape_w[2]={8,1};
   const ulong shape_y[2]={1,1};
   return(OnnxSetInputShape(vs_onnx_handle,0,shape_x) &&
          OnnxSetInputShape(vs_onnx_handle,1,shape_w) &&
          OnnxSetOutputShape(vs_onnx_handle,0,shape_y));
  }

// Read exactly the declared past window. A transient short copy is retried;
// a fully observed but nonaligned Cross window is a declared unavailable origin.
bool VSOriginData(const int kind,const datetime closed_bar,double &returns[],
                  double &v0,double &x[],bool &ready,bool &last_return_valid)
  {
   ready=false; last_return_valid=false;
   const int count=VSWindow(kind)+1;
   const ENUM_TIMEFRAMES period=VSPeriod(kind);
   const int shift=iBarShift(VSSymbol(kind),period,closed_bar,true);
   if(shift<1) return(false);
   MqlRates own[];
   if(CopyRates(VSSymbol(kind),period,shift,count,own)!=count || own[count-1].time!=closed_bar)
      return(false);
   double levels[]; ArrayResize(levels,count);
   bool aligned[]; ArrayResize(aligned,count); ArrayInitialize(aligned,true);
   for(int n=0;n<count;++n)
     {
      if(own[n].close<=0.0) return(false);
      levels[n]=MathLog(own[n].close);
     }
   if(kind==0)
     {
      const string peers[2]={"US30","US500"};
      for(int p=0;p<2;++p)
        {
         const int peer_shift=iBarShift(peers[p],period,closed_bar,true);
         if(peer_shift<1)
           {
            ArrayResize(returns,count-1); ArrayInitialize(returns,0.0);
            return(true);
           }
         MqlRates peer[];
         if(CopyRates(peers[p],period,peer_shift,count,peer)!=count)
            return(false);
         for(int n=0;n<count;++n)
           {
            if(peer[n].close<=0.0) return(false);
            aligned[n]=(aligned[n] && own[n].time==peer[n].time);
            levels[n]-=0.5*MathLog(peer[n].close);
           }
        }
     }
   ArrayResize(returns,count-1);
   bool all_aligned=true;
   for(int n=0;n<count;++n) all_aligned=(all_aligned && aligned[n]);
   for(int n=1;n<count;++n) returns[n-1]=levels[n]-levels[n-1];
   last_return_valid=(aligned[count-1] && aligned[count-2]);
   if(!all_aligned) return(true);
   const int width=count-1;
   double mean=0.0; for(int n=0;n<width;++n) mean+=returns[n]; mean/=width;
   v0=0.0; for(int n=0;n<width;++n) v0+=MathPow(returns[n]-mean,2.0); v0/=(width-1);
   if(v0<=0.0 || !MathIsValidNumber(v0)) return(true);
   double mean4=0.0,mean24=0.0;
   for(int n=width-24;n<width;++n)
     { const double squared=returns[n]*returns[n]; mean24+=squared; if(n>=width-4) mean4+=squared; }
   mean4/=4.0; mean24/=24.0;
   const datetime origin=closed_bar+PeriodSeconds(period);
   const double phase=(double)((long)origin%86400)*6.2831853071795864769/86400.0;
   double raw[7];
   raw[0]=MathLog(1.0+returns[width-1]*returns[width-1]/v0);
   raw[1]=MathLog(1.0+mean4/v0); raw[2]=MathLog(1.0+mean24/v0);
   raw[3]=MathSin(phase); raw[4]=MathCos(phase);
   raw[5]=MathSin(2.0*phase); raw[6]=MathCos(2.0*phase);
   ArrayResize(x,8); x[0]=1.0;
   for(int n=0;n<7;++n)
      x[n+1]=(double)(float)MathMax(-6.0,MathMin(6.0,(raw[n]-VS_MEAN[kind][n])/VS_SD[kind][n]));
   ready=true; return(true);
  }

void VSCompleteAndConsume(const int kind,const datetime closed_bar,
                          const double last_return,const bool last_valid)
  {
   const datetime origin=closed_bar+PeriodSeconds(VSPeriod(kind));
   for(int n=0;n<64;++n)
     {
      if(!vs_records[kind][n].active) continue;
      if(vs_records[kind][n].available==0 && vs_records[kind][n].origin<origin)
        {
         ++vs_records[kind][n].progress;
         vs_records[kind][n].sum_return+=last_return;
         vs_records[kind][n].label_valid=(vs_records[kind][n].label_valid && last_valid);
         if(vs_records[kind][n].progress==VSHorizon(kind))
           {
            vs_records[kind][n].target_closed_bar=closed_bar;
            vs_records[kind][n].available=origin;
            vs_records[kind][n].label=MathPow(vs_records[kind][n].sum_return,2.0)/(VSHorizon(kind)*vs_records[kind][n].v0);
           }
        }
     }
   // Consume by knowledge time, not circular-buffer physical slot order.
   for(int step=0;step<64;++step)
     {
      int selected=-1;
      for(int n=0;n<64;++n)
         if(vs_records[kind][n].active && !vs_records[kind][n].consumed &&
            vs_records[kind][n].available>0 && vs_records[kind][n].available<origin &&
            (selected<0 || vs_records[kind][n].available<vs_records[kind][selected].available)) selected=n;
      if(selected<0) break;
      if(vs_records[kind][selected].available>=origin)
        { ++vs_strict_maturity_faults; VSLearningFault("noncausal label maturity"); return; }
      if(VS_MODE==2 && vs_records[kind][selected].label_valid)
        {
         double z=0.0; for(int j=0;j<8;++j) z+=vs_records[kind][selected].x[j]*vs_weights[kind][j];
         const double tangent=MathTanh(z/3.0);
         const double predicted=MathExp(3.0*tangent);
         const double multiplier=(1.0-vs_records[kind][selected].label/predicted)*(1.0-tangent*tangent);
         double gradient[8]; double norm=0.0;
         for(int j=0;j<8;++j) { gradient[j]=multiplier*vs_records[kind][selected].x[j]; norm+=gradient[j]*gradient[j]; }
         norm=MathSqrt(norm);
         for(int j=0;j<8;++j) vs_weights[kind][j]-=0.001*gradient[j]*(norm>10.0 ? 10.0/norm : 1.0);
         ++vs_updates[kind];
        }
      vs_records[kind][selected].consumed=true;
      if(FileWrite(vs_update_file,kind,(long)vs_records[kind][selected].origin,
         (long)vs_records[kind][selected].available,(long)origin,vs_records[kind][selected].label,
         (int)vs_records[kind][selected].label_valid,vs_updates[kind],
         vs_weights[kind][0],vs_weights[kind][1],vs_weights[kind][2],vs_weights[kind][3],
         vs_weights[kind][4],vs_weights[kind][5],vs_weights[kind][6],vs_weights[kind][7])==0) ++vs_learning_write_faults;
     }
  }

bool VSProcessKind(const int kind)
  {
   const ENUM_TIMEFRAMES period=VSPeriod(kind);
   const string symbol=VSSymbol(kind);
   const datetime last=iTime(symbol,period,1);
   if(last<=vs_last_closed[kind]) return(true);
   datetime times[];
   const int count=CopyTime(symbol,period,vs_last_closed[kind]+1,last,times);
   if(count<=0) return(false);
   for(int i=0;i<count;++i)
     {
      const datetime closed_bar=times[i];
      const datetime origin=closed_bar+PeriodSeconds(period);
      if(origin<VS_LEARNING_START || origin>TimeCurrent()) continue;
      double returns[],x[],v0=0.0; bool ready=false,last_valid=false;
      if(!VSOriginData(kind,closed_bar,returns,v0,x,ready,last_valid)) return(false);
      VSCompleteAndConsume(kind,closed_bar,returns[ArraySize(returns)-1],last_valid);
      if(!ready)
        {
         ++vs_missing_source[kind];
         vs_unavailable[kind][vs_unavailable_cursor[kind]%64]=closed_bar;
         ++vs_unavailable_cursor[kind]; vs_last_closed[kind]=closed_bar; continue;
        }
      matrixf features(1,8),weights(8,1),output(1,1);
      for(int j=0;j<8;++j) { features[0][j]=(float)x[j]; weights[j][0]=(float)vs_weights[kind][j]; }
      if(!OnnxRun(vs_onnx_handle,ONNX_NO_CONVERSION,features,weights,output) ||
         output[0][0]<=0.0 || !MathIsValidNumber((double)output[0][0]))
        { VSLearningFault("ONNX inference"); return(false); }
      const int slot=vs_cursor[kind]%64;
      if(vs_records[kind][slot].active && !vs_records[kind][slot].consumed)
        { VSLearningFault("pending-label buffer exhausted"); return(false); }
      ZeroMemory(vs_records[kind][slot]);
      vs_records[kind][slot].active=true; vs_records[kind][slot].label_valid=true;
      vs_records[kind][slot].origin_closed_bar=closed_bar;
      vs_records[kind][slot].origin=origin; vs_records[kind][slot].v0=v0;
      vs_records[kind][slot].ratio=(double)output[0][0];
      for(int j=0;j<8;++j) vs_records[kind][slot].x[j]=x[j];
      ++vs_cursor[kind]; ++vs_forecasts[kind];
      if(FileWrite(vs_forecast_file,kind,(long)origin,(long)closed_bar,(long)TimeCurrent(),v0,
         vs_records[kind][slot].ratio,vs_updates[kind],x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7])==0)
         ++vs_learning_write_faults;
      vs_last_closed[kind]=closed_bar;
     }
   FileFlush(vs_forecast_file); FileFlush(vs_update_file); return(true);
  }

void VSRefresh()
  {
   if(!execution_state.runtime_ready || vs_onnx_handle==INVALID_HANDLE) return;
   const datetime now=TimeCurrent(); const long slot=(long)now/900;
   if(now==vs_last_refresh_second) return;
   if(slot==vs_last_refresh_slot && (long)now%900>120) return;
   vs_last_refresh_second=now; vs_last_refresh_slot=slot;
   for(int k=0;k<3;++k) VSProcessKind(k);
  }

bool VSEntryFeature(const int kind,double &feature)
  {
   if(VS_MODE==0) return(true);
   if(!VSProcessKind(kind)) return(false);
   const ENUM_TIMEFRAMES period=VSPeriod(kind); const string symbol=VSSymbol(kind);
   const datetime decision_closed=iTime(symbol,period,1);
   const datetime origin_closed=iTime(symbol,period,VSHorizon(kind)+1);
   string status=""; int found=-1;
   if(origin_closed+PeriodSeconds(period)<VS_LEARNING_START) status="INITIAL_WARMUP";
   else
     {
      for(int n=0;n<64;++n)
         if(vs_records[kind][n].active && vs_records[kind][n].origin_closed_bar==origin_closed &&
            vs_records[kind][n].target_closed_bar==decision_closed) { found=n; break; }
      if(found<0)
        {
         bool declared_unavailable=false;
         for(int n=0;n<64;++n) if(vs_unavailable[kind][n]==origin_closed) declared_unavailable=true;
         if(!declared_unavailable) { VSLearningFault("missing causal entry forecast"); return(false); }
         status="PAST_SOURCE_UNAVAILABLE";
        }
     }
   const double original=feature;
   if(found>=0)
     {
      double close[]; const int needed=VSHorizon(kind)+1;
      if(CopyClose(symbol,period,1,needed,close)!=needed) return(false);
      double numerator=MathLog(close[needed-1]/close[0]);
      if(kind==0)
        {
         const string peers[2]={"US30","US500"};
         for(int p=0;p<2;++p)
           {
            double peer[];
            if(iTime(peers[p],period,1)!=decision_closed || CopyClose(peers[p],period,1,2,peer)!=2) return(false);
            numerator-=0.5*MathLog(peer[1]/peer[0]);
           }
        }
      const double denominator=MathSqrt(VSHorizon(kind)*vs_records[kind][found].v0*vs_records[kind][found].ratio);
      if(denominator<=0.0 || !MathIsValidNumber(denominator)) { VSLearningFault("entry denominator"); return(false); }
      feature=numerator/denominator; ++vs_entry_applied[kind]; status="APPLIED";
     }
   else ++vs_entry_fallback[kind];
   if(FileWrite(vs_entry_file,kind,(long)TimeCurrent(),(long)decision_closed,(long)origin_closed,original,feature,status)==0)
      ++vs_learning_write_faults;
   FileFlush(vs_entry_file); return(true);
  }

void VSForecastEnd()
  {
   for(int k=0;k<3;++k)
      PrintFormat("VS_LEARNING kind=%d forecasts=%I64d updates=%I64d unavailable=%I64d applied=%I64d fallback=%I64d",
                  k,vs_forecasts[k],vs_updates[k],vs_missing_source[k],vs_entry_applied[k],vs_entry_fallback[k]);
   PrintFormat("VS_LEARNING_FAULTS inference=%I64d write=%I64d maturity=%I64d",
               vs_inference_faults,vs_learning_write_faults,vs_strict_maturity_faults);
   if(vs_forecast_file!=INVALID_HANDLE) { FileFlush(vs_forecast_file); FileClose(vs_forecast_file); vs_forecast_file=INVALID_HANDLE; }
   if(vs_update_file!=INVALID_HANDLE) { FileFlush(vs_update_file); FileClose(vs_update_file); vs_update_file=INVALID_HANDLE; }
   if(vs_entry_file!=INVALID_HANDLE) { FileFlush(vs_entry_file); FileClose(vs_entry_file); vs_entry_file=INVALID_HANDLE; }
   if(vs_onnx_handle!=INVALID_HANDLE) { OnnxRelease(vs_onnx_handle); vs_onnx_handle=INVALID_HANDLE; }
  }
#endif
