#ifndef ZETA_DENSITY_LEARNING_MQH
#define ZETA_DENSITY_LEARNING_MQH

#include <ZetaV7Density\Learning\DensityPaths.mqh>

void DensityFault(const string message)
  {
   if(!density_failed)
      PrintFormat("DENSITY_FAULT status=CORRECTION_REQUIRED role=%d message=%s",
                  DENSITY_ROLE,message);
   density_failed=true;
  }

string DensityStateIdentity()
  {
   return("DENSITY_STATE_V2|"+DENSITY_EA_NAME+"|"+InpRunTag+"|"+
          DENSITY_FIT_SHA+"|"+DENSITY_GRAPH_SHA+"|"+InpNativeBinding);
  }

bool DensityEngineStage(const string stage,const int engine_error=0)
  {
   ResetLastError();
   int h=FileOpen(density_root+"\\learning\\engine.csv",
                  FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(h==INVALID_HANDLE)
     { DensityFault("cannot open own engine lifecycle ledger"); return(false); }
   bool ok=true;
   if(FileSize(h)==0)
      ok=(FileWrite(h,"stage","host_uptime_ms","server_time","role","engine_error",
                      "provider","run_binding")>0);
   if(!FileSeek(h,0,SEEK_END)) ok=false;
   if(FileWrite(h,stage,GetTickCount64(),(long)TimeCurrent(),DENSITY_ROLE,engine_error,
                  "CPU_ONLY",InpNativeBinding)==0) ok=false;
   FileFlush(h);
   if(GetLastError()!=0 || FileTell(h)!=FileSize(h)) ok=false;
   FileClose(h);
   if(!ok) DensityFault("own engine lifecycle ledger write incomplete");
   return(ok);
  }

bool DensitySaveCheckpoint()
  {
   if(density_failed) return(false);
   const long sequence=density_state_sequence+1;
   const long core_sequence=state_sequence;
   const string path=density_root+"\\learning\\state-"+
                     ((sequence%2)==0 ? "a.bin" : "b.bin");
   int h=FileOpen(path,FILE_WRITE|FILE_BIN|FILE_ANSI);
   if(h==INVALID_HANDLE)
     { DensityFault("cannot open own checkpoint"); return(false); }
   const string identity=DensityStateIdentity();
   FileWriteInteger(h,StringLen(identity),INT_VALUE);
   FileWriteString(h,identity);
   FileWriteLong(h,sequence);
   FileWriteLong(h,density_sequence);
   FileWriteLong(h,density_forecasts);
   FileWriteLong(h,density_abstentions);
   FileWriteLong(h,density_observations);
   FileWriteLong(h,density_updates);
   FileWriteLong(h,density_ledger_bytes);
   FileWriteLong(h,(long)density_last_applied_observation);
   FileWriteLong(h,core_sequence);
   FileWriteDouble(h,density_positive_swap);
   FileWriteDouble(h,density_conservative_peak);
   FileWriteDouble(h,density_conservative_closed_dd);
   for(int c=0;c<6;++c)
     {
      FileWriteLong(h,(long)density_last_bar[c]);
      FileWriteDouble(h,density_last_feature[c]);
      FileWriteInteger(h,density_last_passed[c],INT_VALUE);
      FileWriteInteger(h,density_last_direction[c],INT_VALUE);
      for(int k=0;k<2;++k)
        {
         FileWriteDouble(h,density_N[c][k]);
         FileWriteDouble(h,density_S[c][k]);
         FileWriteDouble(h,density_Q[c][k]);
         FileWriteDouble(h,density_weights[c][k]);
         FileWriteDouble(h,density_means[c][k]);
         FileWriteDouble(h,density_variances[c][k]);
        }
     }
   const int count=ArraySize(density_pending);
   FileWriteInteger(h,count,INT_VALUE);
   for(int i=0;i<count;++i)
     {
      FileWriteLong(h,(long)density_pending[i].observed);
      FileWriteLong(h,(long)density_pending[i].bar);
      FileWriteInteger(h,density_pending[i].component,INT_VALUE);
      FileWriteDouble(h,density_pending[i].z);
      FileWriteLong(h,density_pending[i].serial);
     }
   FileWriteLong(h,sequence);
   FileFlush(h);
   const ulong written=FileTell(h);
   const ulong expected=(ulong)(4+StringLen(identity)+96+6*120+4+count*36+8);
   FileClose(h);
   if(written!=expected)
     { DensityFault("checkpoint byte count incomplete"); return(false); }
   h=FileOpen(path,FILE_READ|FILE_BIN|FILE_ANSI|FILE_SHARE_READ);
   if(h==INVALID_HANDLE)
     { DensityFault("checkpoint readback open failed"); return(false); }
   bool ok=(FileSize(h)==expected);
   const int length=FileReadInteger(h,INT_VALUE);
   if(length!=StringLen(identity)) ok=false;
   if(length<0 || length>1024)
     { FileClose(h); DensityFault("checkpoint identity length invalid"); return(false); }
   if(FileReadString(h,length)!=identity) ok=false;
   if(FileReadLong(h)!=sequence) ok=false;
   if(FileReadLong(h)!=density_sequence) ok=false;
   if(FileReadLong(h)!=density_forecasts) ok=false;
   if(FileReadLong(h)!=density_abstentions) ok=false;
   if(FileReadLong(h)!=density_observations) ok=false;
   if(FileReadLong(h)!=density_updates) ok=false;
   if(FileReadLong(h)!=density_ledger_bytes) ok=false;
   if(FileReadLong(h)!=(long)density_last_applied_observation) ok=false;
   if(FileReadLong(h)!=core_sequence) ok=false;
   if(FileReadDouble(h)!=density_positive_swap) ok=false;
   if(FileReadDouble(h)!=density_conservative_peak) ok=false;
   if(FileReadDouble(h)!=density_conservative_closed_dd) ok=false;
   for(int c=0;c<6;++c)
     {
      if(FileReadLong(h)!=(long)density_last_bar[c]) ok=false;
      if(FileReadDouble(h)!=density_last_feature[c]) ok=false;
      if(FileReadInteger(h,INT_VALUE)!=density_last_passed[c]) ok=false;
      if(FileReadInteger(h,INT_VALUE)!=density_last_direction[c]) ok=false;
      for(int k=0;k<2;++k)
        {
         if(FileReadDouble(h)!=density_N[c][k]) ok=false;
         if(FileReadDouble(h)!=density_S[c][k]) ok=false;
         if(FileReadDouble(h)!=density_Q[c][k]) ok=false;
         if(FileReadDouble(h)!=density_weights[c][k]) ok=false;
         if(FileReadDouble(h)!=density_means[c][k]) ok=false;
         if(FileReadDouble(h)!=density_variances[c][k]) ok=false;
        }
     }
   if(FileReadInteger(h,INT_VALUE)!=count) ok=false;
   for(int i=0;i<count;++i)
     {
      if(FileReadLong(h)!=(long)density_pending[i].observed) ok=false;
      if(FileReadLong(h)!=(long)density_pending[i].bar) ok=false;
      if(FileReadInteger(h,INT_VALUE)!=density_pending[i].component) ok=false;
      if(FileReadDouble(h)!=density_pending[i].z) ok=false;
      if(FileReadLong(h)!=density_pending[i].serial) ok=false;
     }
   if(FileReadLong(h)!=sequence || FileTell(h)!=expected) ok=false;
   FileClose(h);
   if(!ok)
     { DensityFault("own checkpoint readback differs"); return(false); }
   density_state_sequence=sequence;
   ++density_readbacks;
   return(true);
  }

bool DensityRun(const int component,const double z,double &score,double &r0,double &r1)
  {
   if(component<0 || component>=6 || !MathIsValidNumber(z) || density_onnx==INVALID_HANDLE)
     { DensityFault("invalid ONNX input context"); return(false); }
   matrixf feature_input(1,1),parameters(1,6),output(1,1),responsibility(1,2);
   feature_input[0][0]=(float)z;
   for(int k=0;k<2;++k)
     {
      const double w=density_weights[component][k];
      const double m=density_means[component][k];
      const double v=density_variances[component][k];
      if(!MathIsValidNumber(w) || !MathIsValidNumber(m) || !MathIsValidNumber(v) || w<=0 || v<.01-1e-12)
        { DensityFault("invalid mixture state"); return(false); }
      parameters[0][k]=(float)w;
      parameters[0][2+k]=(float)m;
      parameters[0][4+k]=(float)v;
     }
   if(!OnnxRun(density_onnx,ONNX_NO_CONVERSION|ONNX_USE_CPU_ONLY,
               feature_input,parameters,output,responsibility))
     { DensityFault("ONNX inference failed "+IntegerToString(GetLastError())); return(false); }
   score=(double)output[0][0];
   r0=(double)responsibility[0][0];
   r1=(double)responsibility[0][1];
   if(!MathIsValidNumber(score) || !MathIsValidNumber(r0) || !MathIsValidNumber(r1) ||
      r0<0 || r1<0 || MathAbs(r0+r1-1.0)>1e-5)
     { DensityFault("invalid ONNX density/responsibilities"); return(false); }
   return(true);
  }

bool DensityAppend(const string event,const int c,const datetime bar,
                   const datetime available,const long observation,const double z,
                   const double score,const double r0,const double r1,const int allow)
  {
   if(density_failed) return(false);
   const string path=density_root+"\\learning\\learning.csv";
   int h=FileOpen(path,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(h==INVALID_HANDLE)
     { DensityFault("cannot append own learning ledger"); return(false); }
   if(FileSize(h)==0)
      FileWrite(h,"event","sequence","server_time","component","decision_bar",
                  "available_time","observation_id","z","score","r0","r1","allow",
                  "cutoff","w0","w1","mu0","mu1","var0","var1","updates",
                  "last_applied_observation","pending","fit_sha","run_binding");
   FileSeek(h,0,SEEK_END);
   const long sequence=density_sequence+1;
   const uint written=FileWrite(h,event,sequence,(long)TimeCurrent(),c,(long)bar,
       (long)available,observation,DoubleToString(z,17),DoubleToString(score,17),
       DoubleToString(r0,17),DoubleToString(r1,17),allow,
       DoubleToString(DENSITY_INITIAL[c][2],17),
       DoubleToString(density_weights[c][0],17),DoubleToString(density_weights[c][1],17),
       DoubleToString(density_means[c][0],17),DoubleToString(density_means[c][1],17),
       DoubleToString(density_variances[c][0],17),DoubleToString(density_variances[c][1],17),
       density_updates,(long)density_last_applied_observation,ArraySize(density_pending),
       DENSITY_FIT_SHA,InpNativeBinding);
   FileFlush(h);
   density_ledger_bytes=(long)FileTell(h);
   FileClose(h);
   if(written==0)
     { DensityFault("own learning ledger write failed"); return(false); }
   density_sequence=sequence;
   return(true);
  }

bool DensityApplyOlderObservations(const datetime now)
  {
   if(DENSITY_ROLE!=2) return(true);
   while(!density_failed)
     {
      int selected=-1;
      const int count=ArraySize(density_pending);
      for(int i=0;i<count;++i)
        {
         if(density_pending[i].observed>=now) continue;
         if(selected<0 || density_pending[i].observed<density_pending[selected].observed ||
            (density_pending[i].observed==density_pending[selected].observed &&
             (density_pending[i].component<density_pending[selected].component ||
              (density_pending[i].component==density_pending[selected].component &&
               density_pending[i].bar<density_pending[selected].bar)))) selected=i;
        }
      if(selected<0) return(true);
      DensityPendingObservation row=density_pending[selected];
      const int c=row.component;
      double score=0,r0=0,r1=0;
      if(!DensityRun(c,row.z,score,r0,r1)) return(false);
      ++density_update_inferences;
      const double eta=1.0/64.0;
      for(int k=0;k<2;++k)
        {
         const double r=(k==0 ? r0 : r1);
         density_N[c][k]=(1.0-eta)*density_N[c][k]+eta*r;
         density_S[c][k]=(1.0-eta)*density_S[c][k]+eta*r*row.z;
         density_Q[c][k]=(1.0-eta)*density_Q[c][k]+eta*r*row.z*row.z;
         if(density_N[c][k]<=0 || !MathIsValidNumber(density_Q[c][k]))
           { DensityFault("online sufficient statistic invalid"); return(false); }
         density_means[c][k]=density_S[c][k]/density_N[c][k];
         density_variances[c][k]=MathMax(.01,density_Q[c][k]/density_N[c][k]-
                                             density_means[c][k]*density_means[c][k]);
        }
      const double total=density_N[c][0]+density_N[c][1];
      for(int k=0;k<2;++k) density_weights[c][k]=MathMax(.05,density_N[c][k]/total);
      const double weight_sum=density_weights[c][0]+density_weights[c][1];
      for(int k=0;k<2;++k) density_weights[c][k]/=weight_sum;
      ++density_updates;
      density_last_applied_observation=row.observed;
      for(int i=selected+1;i<count;++i) density_pending[i-1]=density_pending[i];
      ArrayResize(density_pending,count-1);
      if(!DensityAppend("UPDATE",c,row.bar,row.observed,row.serial,row.z,score,r0,r1,-1) ||
         !DensitySaveCheckpoint()) return(false);
     }
   return(false);
  }

bool DensityAllow(const int component,const double feature)
  {
   if(density_failed || !density_initialized)
     {
      if(!density_initialized) DensityFault("density engine was not initialized");
      component_states[component].entry_check_result="DENSITY_CORRECTION_REQUIRED";
      return(false);
     }
   if(DENSITY_ROLE==0) return(true);
   if(!MathIsValidNumber(feature))
     { DensityFault("nonfinite original passed feature"); return(false); }
   if(!DensityApplyOlderObservations(TimeCurrent())) return(false);
   const double x=(feature==0.0 ? 0.0 : (feature>0 ? 1.0 : -1.0)*MathLog(1.0+MathAbs(feature)));
   const double z=(x-DENSITY_INITIAL[component][0])/DENSITY_INITIAL[component][1];
   double score=0,r0=0,r1=0;
   if(!DensityRun(component,z,score,r0,r1)) return(false);
   const bool allow=(score<=DENSITY_INITIAL[component][2]);
   ++density_forecasts;
   if(!allow) ++density_abstentions;
   const datetime bar=component_states[component].entry_check_bar;
   if(!DensityAppend("FORECAST",component,bar,TimeCurrent(),0,z,score,r0,r1,(allow ? 1 : 0)) ||
      !DensitySaveCheckpoint()) return(false);
   if(!allow)
     {
      component_states[component].entry_check_result="DENSITY_ABSTAIN";
      RecordEvent(component,"DENSITY_ABSTAIN",score,DENSITY_INITIAL[component][2],
                  StringFormat("bar=%I64d updates=%I64d",(long)bar,density_updates));
     }
   return(allow);
  }

bool DensityCaptureObservation(const int component,const string stage)
  {
   if(DENSITY_ROLE==0) return(true);
   if(stage!="SIGNAL" && stage!="OUTCOME") return(true);
   if(component_states[component].entry_check_signal_known!=1) return(true);
   if(density_failed || !density_initialized) return(false);
   const datetime bar=component_states[component].entry_check_bar;
   const double feature=component_states[component].entry_check_signal_value;
   const int passed=component_states[component].entry_check_signal_passed;
   const int direction=component_states[component].entry_check_direction;
   if(!MathIsValidNumber(feature) || bar<=0 || bar<density_last_bar[component])
     { DensityFault("known observation invalid or regressed"); return(false); }
   if(bar==density_last_bar[component])
     {
      if(feature!=density_last_feature[component] || passed!=density_last_passed[component] ||
         direction!=density_last_direction[component])
         DensityFault("conflicting duplicate original observation");
      return(!density_failed);
     }
   const double x=(feature==0.0 ? 0.0 : (feature>0 ? 1.0 : -1.0)*MathLog(1.0+MathAbs(feature)));
   const double z=(x-DENSITY_INITIAL[component][0])/DENSITY_INITIAL[component][1];
   if(!MathIsValidNumber(z))
     { DensityFault("invalid transformed known observation"); return(false); }
   ++density_observations;
   density_last_bar[component]=bar;
   density_last_feature[component]=feature;
   density_last_passed[component]=passed;
   density_last_direction[component]=direction;
   if(DENSITY_ROLE==2)
     {
      const int count=ArraySize(density_pending);
      if(count>=8192 || ArrayResize(density_pending,count+1)!=count+1)
        { DensityFault("pending observation capacity exceeded"); return(false); }
      density_pending[count].observed=TimeCurrent();
      density_pending[count].bar=bar;
      density_pending[count].component=component;
      density_pending[count].z=z;
      density_pending[count].serial=density_observations;
     }
   return(DensityAppend("OBSERVATION",component,bar,TimeCurrent(),density_observations,z,
                        0.0,0.0,0.0,-1) && DensitySaveCheckpoint());
  }

bool DensityInitialize()
  {
   if(!tester_mode || StringLen(InpNativeBinding)!=64)
     { DensityFault("fresh tester source/settings binding missing"); return(false); }
   for(int i=0;i<64;++i)
     {
      const ushort c=StringGetCharacter(InpNativeBinding,i);
      if(!((c>=48 && c<=57)||(c>=65 && c<=70)))
        { DensityFault("invalid native binding identity"); return(false); }
     }
   for(int c=0;c<6;++c)
      for(int k=0;k<2;++k)
        {
         density_weights[c][k]=DENSITY_INITIAL[c][3+k];
         density_means[c][k]=DENSITY_INITIAL[c][5+k];
         density_variances[c][k]=DENSITY_INITIAL[c][7+k];
         density_N[c][k]=DENSITY_INITIAL[c][9+k];
         density_S[c][k]=DENSITY_INITIAL[c][11+k];
         density_Q[c][k]=DENSITY_INITIAL[c][13+k];
        }
   if(DENSITY_ROLE!=0)
     {
      if(!DensityEngineStage("CREATE_BEGIN")) return(false);
      ResetLastError();
      density_onnx=OnnxCreateFromBuffer(DensityOnnxBytes,ONNX_USE_CPU_ONLY);
      if(density_onnx==INVALID_HANDLE)
        {
         const int error=GetLastError();
         DensityEngineStage("CREATE_FAILED",error);
         DensityFault("ONNX CPU session creation failed "+IntegerToString(error));
         return(false);
        }
      if(!DensityEngineStage("CREATE_READY")) return(false);
      const long z_shape[]={1,1},parameter_shape[]={1,6},score_shape[]={1,1},r_shape[]={1,2};
      if(!OnnxSetInputShape(density_onnx,0,z_shape))
        { DensityEngineStage("INPUT_0_FAILED",GetLastError()); DensityFault("ONNX input 0 shape failed"); return(false); }
      if(!DensityEngineStage("INPUT_0_READY")) return(false);
      if(!OnnxSetInputShape(density_onnx,1,parameter_shape))
        { DensityEngineStage("INPUT_1_FAILED",GetLastError()); DensityFault("ONNX input 1 shape failed"); return(false); }
      if(!DensityEngineStage("INPUT_1_READY")) return(false);
      if(!OnnxSetOutputShape(density_onnx,0,score_shape))
        { DensityEngineStage("OUTPUT_0_FAILED",GetLastError()); DensityFault("ONNX output 0 shape failed"); return(false); }
      if(!DensityEngineStage("OUTPUT_0_READY")) return(false);
      if(!OnnxSetOutputShape(density_onnx,1,r_shape))
        { DensityEngineStage("OUTPUT_1_FAILED",GetLastError()); DensityFault("ONNX output 1 shape failed"); return(false); }
      if(!DensityEngineStage("OUTPUT_1_READY")) return(false);
     }
   density_initialized=true;
   return(DensitySaveCheckpoint() && DensityEngineStage("INITIALIZED"));
  }

void DensityShutdown()
  {
   DensityFlushEquity(true);
   if(density_initialized && !density_failed) DensitySaveCheckpoint();
   if(density_onnx!=INVALID_HANDLE)
     {
      DensityEngineStage("RELEASE_BEGIN");
      ResetLastError();
      if(!OnnxRelease(density_onnx))
        {
         const int error=GetLastError();
         DensityEngineStage("RELEASE_FAILED",error);
         DensityFault("ONNX CPU session release failed "+IntegerToString(error));
        }
      else
        {
         density_onnx=INVALID_HANDLE;
         DensityEngineStage("RELEASED");
        }
     }
  }

#endif
