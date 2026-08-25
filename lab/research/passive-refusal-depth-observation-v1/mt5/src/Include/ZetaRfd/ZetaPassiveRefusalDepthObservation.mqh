#ifndef ZETA_PASSIVE_REFUSAL_DEPTH_OBSERVATION_MQH
#define ZETA_PASSIVE_REFUSAL_DEPTH_OBSERVATION_MQH

// Tester-only, economically inert observation of expired Passive limit geometry.

#define RFD_EMITTER_CAPACITY 64
#define RFD_RECEIVER_COUNT 2
const int RFD_LOOKBACK_MINUTES = 2880;

struct RfdPendingObservation
  {
   bool active;
   ulong ticket;
   int direction;
   datetime placed_server;
   datetime expiration;
   double feature;
   double limit_price;
   double initial_gap;
   double minimum_gap;
   double final_gap;
   long nearest_time_msc;
   long last_sample_time_msc;
   long unique_samples;
  };

struct RfdExpiredEmitter
  {
   long identifier;
   datetime observed_server;
   int direction;
   double approach_fraction;
   double rebound_fraction;
   double nearest_time_fraction;
  };

struct RfdReceiverObservation
  {
   bool active;
   int component;
   ulong identifier;
   int direction;
   datetime entry_server;
   bool matched;
   long emitter_identifier;
   datetime emitter_observed_server;
   double emitter_approach_fraction;
   double emitter_rebound_fraction;
   double emitter_nearest_time_fraction;
   double actual_net;
   double stressed_net;
   long exit_deals;
  };

RfdPendingObservation rfd_pending;
RfdExpiredEmitter rfd_emitters[RFD_EMITTER_CAPACITY];
int rfd_emitter_count = 0;
long rfd_next_emitter_identifier = 1;
RfdReceiverObservation rfd_receivers[RFD_RECEIVER_COUNT];

long rfd_pending_started = 0;
long rfd_pending_dropped_nonexpired = 0;
long rfd_expired_finalized = 0;
long rfd_measurement_faults = 0;
long rfd_receiver_adopted[RFD_RECEIVER_COUNT];
long rfd_receiver_matched[RFD_RECEIVER_COUNT];
long rfd_receiver_closed[RFD_RECEIVER_COUNT];


int RfdReceiverIndex(const int component)
  {
   if(component == US30_RETURN_REV_LONG)
      return(0);
   if(component == US100_CROSS)
      return(1);
   return(-1);
  }


string RfdReceiverLabel(const int component)
  {
   if(component == US30_RETURN_REV_LONG)
      return("RETURN");
   if(component == US100_CROSS)
      return("CROSS");
   return("OTHER");
  }


void RfdClearPendingMemory()
  {
   rfd_pending.active = false;
   rfd_pending.ticket = 0;
   rfd_pending.direction = 0;
   rfd_pending.placed_server = 0;
   rfd_pending.expiration = 0;
   rfd_pending.feature = 0.0;
   rfd_pending.limit_price = 0.0;
   rfd_pending.initial_gap = 0.0;
   rfd_pending.minimum_gap = 0.0;
   rfd_pending.final_gap = 0.0;
   rfd_pending.nearest_time_msc = 0;
   rfd_pending.last_sample_time_msc = 0;
   rfd_pending.unique_samples = 0;
  }


void RfdClearReceiverMemory(const int index)
  {
   if(index < 0 || index >= RFD_RECEIVER_COUNT)
      return;
   rfd_receivers[index].active = false;
   rfd_receivers[index].component = -1;
   rfd_receivers[index].identifier = 0;
   rfd_receivers[index].direction = 0;
   rfd_receivers[index].entry_server = 0;
   rfd_receivers[index].matched = false;
   rfd_receivers[index].emitter_identifier = 0;
   rfd_receivers[index].emitter_observed_server = 0;
   rfd_receivers[index].emitter_approach_fraction = 0.0;
   rfd_receivers[index].emitter_rebound_fraction = 0.0;
   rfd_receivers[index].emitter_nearest_time_fraction = 0.0;
   rfd_receivers[index].actual_net = 0.0;
   rfd_receivers[index].stressed_net = 0.0;
   rfd_receivers[index].exit_deals = 0;
  }


void RfdResetAll()
  {
   RfdClearPendingMemory();
   for(int index = 0; index < RFD_EMITTER_CAPACITY; ++index)
     {
      rfd_emitters[index].identifier = 0;
      rfd_emitters[index].observed_server = 0;
      rfd_emitters[index].direction = 0;
      rfd_emitters[index].approach_fraction = 0.0;
      rfd_emitters[index].rebound_fraction = 0.0;
      rfd_emitters[index].nearest_time_fraction = 0.0;
     }
   rfd_emitter_count = 0;
   rfd_next_emitter_identifier = 1;
   for(int index = 0; index < RFD_RECEIVER_COUNT; ++index)
     {
      RfdClearReceiverMemory(index);
      rfd_receiver_adopted[index] = 0;
      rfd_receiver_matched[index] = 0;
      rfd_receiver_closed[index] = 0;
     }
   rfd_pending_started = 0;
   rfd_pending_dropped_nonexpired = 0;
   rfd_expired_finalized = 0;
   rfd_measurement_faults = 0;
  }


bool RfdValidTick(const MqlTick &tick)
  {
   return(tick.time > 0 && tick.time_msc > 0 &&
          tick.bid > 0.0 && tick.ask > 0.0 &&
          tick.ask >= tick.bid &&
          MathIsValidNumber(tick.bid) && MathIsValidNumber(tick.ask));
  }


double RfdExecutableGap(const int direction,
                        const double limit_price,
                        const MqlTick &tick)
  {
   if(direction > 0)
      return(tick.ask - limit_price);
   if(direction < 0)
      return(limit_price - tick.bid);
   return(-1.0);
  }


bool RfdSamplePendingTick(const MqlTick &tick)
  {
   if(!rfd_pending.active)
      return(true);
   if(!RfdValidTick(tick) || tick.time_msc <= rfd_pending.last_sample_time_msc)
      return(true);
   const double gap =
      RfdExecutableGap(rfd_pending.direction,
                       rfd_pending.limit_price,
                       tick);
   if(!MathIsValidNumber(gap))
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=invalid_sample ticket=%I64u gap=%.8f tick_msc=%I64d",
                  EXECUTION_VERSION,
                  rfd_pending.ticket,
                  gap,
                  tick.time_msc);
      return(false);
     }
   const double observed_gap = MathMax(0.0, gap);
   rfd_pending.final_gap = observed_gap;
   rfd_pending.last_sample_time_msc = tick.time_msc;
   ++rfd_pending.unique_samples;
   if(rfd_pending.unique_samples == 1 ||
      observed_gap < rfd_pending.minimum_gap)
     {
      rfd_pending.minimum_gap = observed_gap;
      rfd_pending.nearest_time_msc = tick.time_msc;
     }
   return(true);
  }


void RfdBeginPending(const ulong ticket,
                     const int direction,
                     const datetime placed_server,
                     const datetime expiration,
                     const double feature,
                     const double limit_price,
                     const MqlTick &tick)
  {
   if(rfd_pending.active || ticket == 0 || MathAbs(direction) != 1 ||
      placed_server <= 0 || expiration <= placed_server ||
      limit_price <= 0.0 || !RfdValidTick(tick))
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=invalid_begin ticket=%I64u direction=%d placed=%I64d expiration=%I64d",
                  EXECUTION_VERSION,
                  ticket,
                  direction,
                  (long)placed_server,
                  (long)expiration);
      RfdClearPendingMemory();
      return;
     }
   const double initial_gap = RfdExecutableGap(direction, limit_price, tick);
   if(!MathIsValidNumber(initial_gap) || initial_gap <= 0.0)
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=invalid_initial_gap ticket=%I64u gap=%.8f",
                  EXECUTION_VERSION,
                  ticket,
                  initial_gap);
      RfdClearPendingMemory();
      return;
     }
   RfdClearPendingMemory();
   rfd_pending.active = true;
   rfd_pending.ticket = ticket;
   rfd_pending.direction = direction;
   rfd_pending.placed_server = placed_server;
   rfd_pending.expiration = expiration;
   rfd_pending.feature = feature;
   rfd_pending.limit_price = limit_price;
   rfd_pending.initial_gap = initial_gap;
   rfd_pending.minimum_gap = initial_gap;
   rfd_pending.final_gap = initial_gap;
   ++rfd_pending_started;
   RfdSamplePendingTick(tick);
  }


void RfdObservePendingTick()
  {
   if(!rfd_pending.active)
      return;
   MqlTick tick = {};
   if(SymbolInfoTick("US100", tick))
      RfdSamplePendingTick(tick);
  }


void RfdDropPending()
  {
   if(rfd_pending.active)
      ++rfd_pending_dropped_nonexpired;
   RfdClearPendingMemory();
  }


void RfdPruneEmitters(const datetime now)
  {
   int write_index = 0;
   const long maximum_age_seconds = (long)RFD_LOOKBACK_MINUTES * 60;
   for(int read_index = 0; read_index < rfd_emitter_count; ++read_index)
     {
      const datetime observed = rfd_emitters[read_index].observed_server;
      const long age_seconds = (long)now - (long)observed;
      if(observed <= 0 || age_seconds < 0 || age_seconds > maximum_age_seconds)
         continue;
      if(write_index != read_index)
         rfd_emitters[write_index] = rfd_emitters[read_index];
      ++write_index;
     }
   for(int index = write_index; index < rfd_emitter_count; ++index)
     {
      rfd_emitters[index].identifier = 0;
      rfd_emitters[index].observed_server = 0;
      rfd_emitters[index].direction = 0;
      rfd_emitters[index].approach_fraction = 0.0;
      rfd_emitters[index].rebound_fraction = 0.0;
      rfd_emitters[index].nearest_time_fraction = 0.0;
     }
   rfd_emitter_count = write_index;
  }


void RfdFinalizeExpired(const ulong ticket,
                        const int direction,
                        const datetime expiration,
                        const datetime observed_server)
  {
   RfdObservePendingTick();
   if(!rfd_pending.active || rfd_pending.ticket != ticket ||
      rfd_pending.direction != direction ||
      rfd_pending.expiration != expiration ||
      observed_server <= 0 || rfd_pending.initial_gap <= 0.0 ||
      rfd_pending.unique_samples <= 0)
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=invalid_expiry ticket=%I64u direction=%d expiration=%I64d active=%d tracked=%I64u samples=%I64d",
                  EXECUTION_VERSION,
                  ticket,
                  direction,
                  (long)expiration,
                  (int)rfd_pending.active,
                  rfd_pending.ticket,
                  rfd_pending.unique_samples);
      RfdClearPendingMemory();
      return;
     }
   const double approach_fraction =
      MathMax(0.0,
              MathMin(1.0,
                      1.0 - rfd_pending.minimum_gap /
                            rfd_pending.initial_gap));
   const double rebound_fraction =
      MathMax(0.0,
              (rfd_pending.final_gap - rfd_pending.minimum_gap) /
              rfd_pending.initial_gap);
   const long life_msc =
      ((long)rfd_pending.expiration -
       (long)rfd_pending.placed_server) * 1000;
   const long nearest_elapsed_msc =
      rfd_pending.nearest_time_msc -
      (long)rfd_pending.placed_server * 1000;
   const double nearest_time_fraction =
      (life_msc > 0
       ? MathMax(0.0,
                 MathMin(1.0,
                         (double)nearest_elapsed_msc / (double)life_msc))
       : 0.0);
   RfdPruneEmitters(observed_server);
   if(rfd_emitter_count >= RFD_EMITTER_CAPACITY)
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=emitter_capacity count=%d capacity=%d",
                  EXECUTION_VERSION,
                  rfd_emitter_count,
                  RFD_EMITTER_CAPACITY);
      RfdClearPendingMemory();
      return;
     }
   const long emitter_identifier = rfd_next_emitter_identifier++;
   rfd_emitters[rfd_emitter_count].identifier = emitter_identifier;
   rfd_emitters[rfd_emitter_count].observed_server = observed_server;
   rfd_emitters[rfd_emitter_count].direction = direction;
   rfd_emitters[rfd_emitter_count].approach_fraction = approach_fraction;
   rfd_emitters[rfd_emitter_count].rebound_fraction = rebound_fraction;
   rfd_emitters[rfd_emitter_count].nearest_time_fraction = nearest_time_fraction;
   ++rfd_emitter_count;
   ++rfd_expired_finalized;
   PrintFormat("%s RFD_EXPIRE emitter=%I64d ticket=%I64u direction=%d placed=%I64d expiration=%I64d observed=%I64d feature=%.8f limit=%.5f initial_gap=%.8f minimum_gap=%.8f final_gap=%.8f approach=%.8f rebound=%.8f nearest_fraction=%.8f samples=%I64d",
               EXECUTION_VERSION,
               emitter_identifier,
               ticket,
               direction,
               (long)rfd_pending.placed_server,
               (long)expiration,
               (long)observed_server,
               rfd_pending.feature,
               rfd_pending.limit_price,
               rfd_pending.initial_gap,
               rfd_pending.minimum_gap,
               rfd_pending.final_gap,
               approach_fraction,
               rebound_fraction,
               nearest_time_fraction,
               rfd_pending.unique_samples);
   RfdClearPendingMemory();
  }


bool RfdMostRecentEmitter(const int direction,
                          const datetime decision_server,
                          RfdExpiredEmitter &selected)
  {
   selected.identifier = 0;
   selected.observed_server = 0;
   selected.direction = 0;
   selected.approach_fraction = 0.0;
   selected.rebound_fraction = 0.0;
   selected.nearest_time_fraction = 0.0;
   if(MathAbs(direction) != 1 || decision_server <= 0)
      return(false);
   RfdPruneEmitters(decision_server);
   for(int index = 0; index < rfd_emitter_count; ++index)
     {
      if(rfd_emitters[index].direction != direction ||
         rfd_emitters[index].observed_server <= 0 ||
         rfd_emitters[index].observed_server >= decision_server)
         continue;
      if(selected.identifier == 0 ||
         rfd_emitters[index].observed_server > selected.observed_server)
         selected = rfd_emitters[index];
     }
   return(selected.identifier > 0);
  }


void RfdAdoptReceiver(const int component,
                      const ulong identifier,
                      const int direction,
                      const datetime entry_server)
  {
   const int index = RfdReceiverIndex(component);
   if(index < 0)
      return;
   if(identifier == 0 || MathAbs(direction) != 1 || entry_server <= 0 ||
      rfd_receivers[index].active)
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=invalid_receiver_adopt component=%s identifier=%I64u active=%d",
                  EXECUTION_VERSION,
                  RfdReceiverLabel(component),
                  identifier,
                  (int)rfd_receivers[index].active);
      return;
     }
   RfdClearReceiverMemory(index);
   rfd_receivers[index].active = true;
   rfd_receivers[index].component = component;
   rfd_receivers[index].identifier = identifier;
   rfd_receivers[index].direction = direction;
   rfd_receivers[index].entry_server = entry_server;
   ++rfd_receiver_adopted[index];
   RfdExpiredEmitter emitter = {};
   if(RfdMostRecentEmitter(direction, entry_server, emitter))
     {
      rfd_receivers[index].matched = true;
      rfd_receivers[index].emitter_identifier = emitter.identifier;
      rfd_receivers[index].emitter_observed_server = emitter.observed_server;
      rfd_receivers[index].emitter_approach_fraction = emitter.approach_fraction;
      rfd_receivers[index].emitter_rebound_fraction = emitter.rebound_fraction;
      rfd_receivers[index].emitter_nearest_time_fraction = emitter.nearest_time_fraction;
      ++rfd_receiver_matched[index];
     }
  }


void RfdRecordReceiverExit(const int component,
                           const ulong identifier,
                           const double deal_net,
                           const double stressed_net,
                           const long remaining_after_steps,
                           const long deal_time_msc,
                           const ENUM_DEAL_REASON exit_reason,
                           const bool stop_loss_seen)
  {
   const int index = RfdReceiverIndex(component);
   if(index < 0)
      return;
   if(!rfd_receivers[index].active ||
      rfd_receivers[index].identifier != identifier)
     {
      ++rfd_measurement_faults;
      PrintFormat("%s RFD_FAULT kind=receiver_exit_mismatch component=%s identifier=%I64u tracked=%I64u active=%d",
                  EXECUTION_VERSION,
                  RfdReceiverLabel(component),
                  identifier,
                  rfd_receivers[index].identifier,
                  (int)rfd_receivers[index].active);
      return;
     }
   rfd_receivers[index].actual_net += deal_net;
   rfd_receivers[index].stressed_net += stressed_net;
   ++rfd_receivers[index].exit_deals;
   if(remaining_after_steps != 0)
      return;
   const double emitter_age_minutes =
      (rfd_receivers[index].matched
       ? (double)((long)rfd_receivers[index].entry_server -
                  (long)rfd_receivers[index].emitter_observed_server) / 60.0
       : -1.0);
   PrintFormat("%s RFD_RECEIVER component=%s identifier=%I64u direction=%d entry=%I64d exit_msc=%I64d matched=%d emitter=%I64d emitter_observed=%I64d emitter_age_minutes=%.4f approach=%.8f rebound=%.8f nearest_fraction=%.8f actual_net=%.8f stressed_net=%.8f stop=%d reason=%s exit_deals=%I64d",
               EXECUTION_VERSION,
               RfdReceiverLabel(component),
               identifier,
               rfd_receivers[index].direction,
               (long)rfd_receivers[index].entry_server,
               deal_time_msc,
               (int)rfd_receivers[index].matched,
               rfd_receivers[index].emitter_identifier,
               (long)rfd_receivers[index].emitter_observed_server,
               emitter_age_minutes,
               rfd_receivers[index].emitter_approach_fraction,
               rfd_receivers[index].emitter_rebound_fraction,
               rfd_receivers[index].emitter_nearest_time_fraction,
               rfd_receivers[index].actual_net,
               rfd_receivers[index].stressed_net,
               (int)stop_loss_seen,
               EnumToString(exit_reason),
               rfd_receivers[index].exit_deals);
   ++rfd_receiver_closed[index];
   RfdClearReceiverMemory(index);
  }


void RfdPrintFinalTelemetry()
  {
   PrintFormat("%s refusal_depth pending_active=%d pending_started=%I64d dropped_nonexpired=%I64d expired_finalized=%I64d live_emitters=%d measurement_faults=%I64d return_adopted=%I64d return_matched=%I64d return_closed=%I64d cross_adopted=%I64d cross_matched=%I64d cross_closed=%I64d",
               EXECUTION_VERSION,
               (int)rfd_pending.active,
               rfd_pending_started,
               rfd_pending_dropped_nonexpired,
               rfd_expired_finalized,
               rfd_emitter_count,
               rfd_measurement_faults,
               rfd_receiver_adopted[0],
               rfd_receiver_matched[0],
               rfd_receiver_closed[0],
               rfd_receiver_adopted[1],
               rfd_receiver_matched[1],
               rfd_receiver_closed[1]);
  }


void RfdPrintSymbolContract(const string stage,
                            const string symbol)
  {
   PrintFormat("%s RFD_CONTRACT stage=%s symbol=%s contract=%.8f tick_size=%.8f tick_value=%.8f tick_value_profit=%.8f tick_value_loss=%.8f volume_min=%.8f volume_step=%.8f stops=%I64d freeze=%I64d swap_mode=%I64d swap_long=%.8f swap_short=%.8f rollover3=%I64d sun=%.8f mon=%.8f tue=%.8f wed=%.8f thu=%.8f fri=%.8f sat=%.8f",
               EXECUTION_VERSION,
               stage,
               symbol,
               SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT),
               SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP),
               SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL),
               SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               SymbolInfoInteger(symbol, SYMBOL_SWAP_MODE),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_LONG),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SHORT),
               SymbolInfoInteger(symbol, SYMBOL_SWAP_ROLLOVER3DAYS),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SUNDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_MONDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_TUESDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_WEDNESDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_THURSDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_FRIDAY),
               SymbolInfoDouble(symbol, SYMBOL_SWAP_SATURDAY));
  }


void RfdPrintRequiredContracts(const string stage)
  {
   RfdPrintSymbolContract(stage, "US30");
   RfdPrintSymbolContract(stage, "US100");
   RfdPrintSymbolContract(stage, "US500");
  }

#endif
