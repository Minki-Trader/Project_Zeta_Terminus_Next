bool DensityInitializeOwnedPaths()
  {
   if(!tester_mode || StringLen(InpRunTag)<1 || StringLen(InpRunTag)>48)
      return(false);
   for(int i=0;i<StringLen(InpRunTag);++i)
     {
      ushort c=StringGetCharacter(InpRunTag,i);
      if(!((c>=48 && c<=57)||(c>=65 && c<=90)||(c>=97 && c<=122)||c==45))
         return(false);
     }
   density_root=DENSITY_EA_NAME+"\\"+InpRunTag;
   STATE_PATH_A=density_root+"\\state\\state-a.csv";
   STATE_PATH_B=density_root+"\\state\\state-b.csv";
   EVENT_PATH_A=density_root+"\\state\\events-a.csv";
   EVENT_PATH_B=density_root+"\\state\\events-b.csv";
   CURRENT_SNAPSHOT_PATH_A=density_root+"\\state\\current-a.csv";
   CURRENT_SNAPSHOT_PATH_B=density_root+"\\state\\current-b.csv";
   OWNERSHIP_PATH=density_root+"\\state\\runtime.lock";
   RESEARCH_OBSERVATION_DIRECTORY=density_root+"\\research";
   RESEARCH_OBSERVATION_STATE_PATH_A=density_root+"\\research\\research-state-a.csv";
   RESEARCH_OBSERVATION_STATE_PATH_B=density_root+"\\research\\research-state-b.csv";
   RESEARCH_CANDIDATE_LEDGER_PATH=density_root+"\\research\\research-candidates.csv";
   RESEARCH_LIFECYCLE_LEDGER_PATH=density_root+"\\research\\research-lifecycles.csv";
   string previous;
   long finder=FileFindFirst(density_root+"\\*",previous);
   if(finder!=INVALID_HANDLE)
     {
      FileFindClose(finder);
      Print("DENSITY_FRESH_START_REFUSED existing owned namespace");
      return(false);
     }
   FolderCreate(DENSITY_EA_NAME);
   FolderCreate(density_root);
   FolderCreate(density_root+"\\state");
   FolderCreate(density_root+"\\research");
   FolderCreate(density_root+"\\learning");
   int marker=FileOpen(density_root+"\\started.bin",FILE_WRITE|FILE_BIN);
   if(marker==INVALID_HANDLE) return(false);
   uint written=FileWriteLong(marker,(long)TimeCurrent());
   FileFlush(marker);
   FileClose(marker);
   return(written==8);
  }
