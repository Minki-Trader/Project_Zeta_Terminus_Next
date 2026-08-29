#ifndef ZETA_OPT_DD20_CESNM1_MODULE_01_MQH
#define ZETA_OPT_DD20_CESNM1_MODULE_01_MQH

// Behavior-preserving function extraction from B70 V6R6: Time\ZetaSessionClock.mqh

datetime ServerMidnight()
  {
   MqlDateTime parts = {};
   TimeCurrent(parts);
   parts.hour = 0;
   parts.min = 0;
   parts.sec = 0;
   return(StructToTime(parts));
  }


datetime CalendarDate(const int year, const int month, const int day)
  {
   MqlDateTime parts = {};
   parts.year = year;
   parts.mon = month;
   parts.day = day;
   return(StructToTime(parts));
  }


bool SameCalendarDate(const datetime left, const datetime right)
  {
   MqlDateTime left_parts = {};
   MqlDateTime right_parts = {};
   TimeToStruct(left, left_parts);
   TimeToStruct(right, right_parts);
   return(left_parts.year == right_parts.year &&
          left_parts.mon == right_parts.mon &&
          left_parts.day == right_parts.day);
  }


datetime NthWeekday(const int year,
                    const int month,
                    const int weekday,
                    const int occurrence)
  {
   const datetime first = CalendarDate(year, month, 1);
   MqlDateTime parts = {};
   TimeToStruct(first, parts);
   const int offset = (weekday - parts.day_of_week + 7) % 7;
   return(first + (offset + 7 * (occurrence - 1)) * 86400);
  }


datetime LastWeekday(const int year,
                     const int month,
                     const int weekday)
  {
   const int next_month = (month == 12 ? 1 : month + 1);
   const int next_year = (month == 12 ? year + 1 : year);
   datetime day = CalendarDate(next_year, next_month, 1) - 86400;
   MqlDateTime parts = {};
   TimeToStruct(day, parts);
   const int offset = (parts.day_of_week - weekday + 7) % 7;
   return(day - offset * 86400);
  }


datetime ObservedFixedHoliday(const int year,
                              const int month,
                              const int day)
  {
   datetime holiday = CalendarDate(year, month, day);
   MqlDateTime parts = {};
   TimeToStruct(holiday, parts);
   if(parts.day_of_week == 6)
      holiday -= 86400;
   else if(parts.day_of_week == 0)
      holiday += 86400;
   return(holiday);
  }


datetime EasterSunday(const int year)
  {
   const int a = year % 19;
   const int b = year / 100;
   const int c = year % 100;
   const int d = b / 4;
   const int e = b % 4;
   const int f = (b + 8) / 25;
   const int g = (b - f + 1) / 3;
   const int h = (19 * a + b - d - g + 15) % 30;
   const int i = c / 4;
   const int k = c % 4;
   const int l = (32 + 2 * e + 2 * i - h - k) % 7;
   const int m = (a + 11 * h + 22 * l) / 451;
   const int month = (h + l - 7 * m + 114) / 31;
   const int day = ((h + l - 7 * m + 114) % 31) + 1;
   return(CalendarDate(year, month, day));
  }


bool SessionContractYearVerified(const int year)
  {
   return(year >= SESSION_CONTRACT_FIRST_YEAR &&
          year <= SESSION_CONTRACT_LAST_YEAR);
  }


int ExpectedFPMarketsUTCOffsetSeconds(const datetime utc_now)
  {
   MqlDateTime parts = {};
   TimeToStruct(utc_now, parts);
   const datetime summer_start =
      LastWeekday(parts.year, 3, 0) + 3600;
   const datetime summer_end =
      LastWeekday(parts.year, 10, 0) + 3600;
   return(utc_now >= summer_start && utc_now < summer_end
          ? 3 * 3600
          : 2 * 3600);
  }


int ExpectedNewYorkUTCOffsetSeconds(const datetime utc_now)
  {
   MqlDateTime parts = {};
   TimeToStruct(utc_now, parts);
   const datetime summer_start =
      NthWeekday(parts.year, 3, 0, 2) + 7 * 3600;
   const datetime summer_end =
      NthWeekday(parts.year, 11, 0, 1) + 6 * 3600;
   return(utc_now >= summer_start && utc_now < summer_end
          ? -4 * 3600
          : -5 * 3600);
  }


bool FPMarketsServerClockCompatible()
  {
   // Entry hours are frozen FPMarkets server-wall economic variables.  This
   // contract blocks an offset-convention change; it does not remap them to
   // New York time during the US/Europe DST mismatch weeks.
   const datetime server_now = TimeTradeServer();
   MqlDateTime server_parts = {};
   TimeToStruct(server_now, server_parts);
   if(server_now <= 0 || !SessionContractYearVerified(server_parts.year))
     {
      if(!server_clock_mismatch_logged)
        {
         PrintFormat("%s session-clock contract unavailable server_year=%d "
                     "verified=%d-%d; new entries blocked",
                     EXECUTION_VERSION,
                     server_parts.year,
                     SESSION_CONTRACT_FIRST_YEAR,
                     SESSION_CONTRACT_LAST_YEAR);
         server_clock_mismatch_logged = true;
        }
      return(false);
     }

   if(tester_mode)
     {
      if(!server_clock_contract_logged)
        {
         PrintFormat("%s session-clock contract tester_mode=true "
                     "calendar=%s; TimeGMT offset is not observable in "
                     "Strategy Tester, fixed server-hour economics retained",
                     EXECUTION_VERSION,
                     US_EQUITY_CALENDAR_VERSION);
         server_clock_contract_logged = true;
        }
      return(true);
     }

   const datetime utc_now = TimeGMT();
   if(utc_now <= 0)
     {
      if(!server_clock_mismatch_logged)
        {
         PrintFormat("%s session-clock UTC unavailable; new entries blocked",
                     EXECUTION_VERSION);
         server_clock_mismatch_logged = true;
        }
      return(false);
     }
   const int expected_server_offset =
      ExpectedFPMarketsUTCOffsetSeconds(utc_now);
   const int expected_new_york_offset =
      ExpectedNewYorkUTCOffsetSeconds(utc_now);
   const long observed_server_offset =
      (long)server_now - (long)utc_now;
   const bool compatible =
      MathAbs((double)(observed_server_offset - expected_server_offset)) <=
      SERVER_UTC_OFFSET_TOLERANCE_SECONDS;
   if(!compatible)
     {
      if(!server_clock_mismatch_logged)
        {
         PrintFormat("%s session-clock mismatch observed_server_utc=%I64d "
                     "expected_server_utc=%d tolerance=%d; new entries blocked",
                     EXECUTION_VERSION,
                     observed_server_offset,
                     expected_server_offset,
                     SERVER_UTC_OFFSET_TOLERANCE_SECONDS);
         server_clock_mismatch_logged = true;
        }
      return(false);
     }

   if(server_clock_mismatch_logged)
      PrintFormat("%s session-clock contract restored", EXECUTION_VERSION);
   server_clock_mismatch_logged = false;
   if(!server_clock_contract_logged)
     {
      PrintFormat("%s session-clock contract observed_server_utc=%I64d "
                  "expected_server_utc=%d expected_new_york_utc=%d "
                  "server_new_york_gap_hours=%d calendar=%s",
                  EXECUTION_VERSION,
                  observed_server_offset,
                  expected_server_offset,
                  expected_new_york_offset,
                  (expected_server_offset - expected_new_york_offset) / 3600,
                  US_EQUITY_CALENDAR_VERSION);
      server_clock_contract_logged = true;
     }
   return(true);
  }


bool IsExtraordinaryUSEquityClosureDate(const datetime today)
  {
   // Published calendars are supplemented by known extraordinary closures as
   // of this calendar version's 2026-08-18 review date.
   MqlDateTime parts = {};
   TimeToStruct(today, parts);
   return(parts.year == 2025 && parts.mon == 1 && parts.day == 9);
  }


bool IsUSEquityClosureDate()
  {
   const datetime today = ServerMidnight();
   MqlDateTime parts = {};
   TimeToStruct(today, parts);
   const int year = parts.year;
   if(!SessionContractYearVerified(year))
     {
      if(unverified_calendar_logged_day != today)
        {
         PrintFormat("%s US-equity calendar unverified date=%s version=%s; "
                     "calendar-dependent entry blocked",
                     EXECUTION_VERSION,
                     TimeToString(today, TIME_DATE),
                     US_EQUITY_CALENDAR_VERSION);
         unverified_calendar_logged_day = today;
        }
      return(true);
     }
   if(IsExtraordinaryUSEquityClosureDate(today))
      return(true);
   datetime holidays[];
   ArrayResize(holidays, 10);
   holidays[0] = ObservedFixedHoliday(year, 1, 1);
   holidays[1] = NthWeekday(year, 1, 1, 3);
   holidays[2] = NthWeekday(year, 2, 1, 3);
   holidays[3] = EasterSunday(year) - 2 * 86400;
   holidays[4] = LastWeekday(year, 5, 1);
   holidays[5] = ObservedFixedHoliday(year, 6, 19);
   holidays[6] = ObservedFixedHoliday(year, 7, 4);
   holidays[7] = NthWeekday(year, 9, 1, 1);
   holidays[8] = NthWeekday(year, 11, 4, 4);
   holidays[9] = ObservedFixedHoliday(year, 12, 25);
   for(int index = 0; index < ArraySize(holidays); ++index)
      if(holidays[index] > 0 && SameCalendarDate(today, holidays[index]))
         return(true);

   const datetime thanksgiving = NthWeekday(year, 11, 4, 4);
   if(SameCalendarDate(today, thanksgiving + 86400))
      return(true);
   if(parts.mon == 7 && parts.day == 3 &&
      parts.day_of_week >= 1 && parts.day_of_week <= 5)
      return(true);
   if(parts.mon == 12 && parts.day == 24 &&
      parts.day_of_week >= 1 && parts.day_of_week <= 5)
      return(true);
   return(false);
  }


#endif
