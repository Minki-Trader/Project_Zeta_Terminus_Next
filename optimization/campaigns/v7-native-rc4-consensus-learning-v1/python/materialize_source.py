"""Author the owned original-V7 source-recording control from its frozen parent."""
from pathlib import Path
import hashlib
import json
import re
import shutil

FAMILY = Path(__file__).resolve().parents[1]
ROOT = FAMILY.parents[2]
BASE = ROOT / 'optimization/baseline/NEXT-E03-V7R-RLO1-0bba2ca045fe'
NAME = 'ZetaV7RC4ConsensusControl'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8', newline='\r\n')


def main():
    parent = FAMILY / 'parent'
    if not parent.exists():
        shutil.copytree(BASE, parent)
    elif not (FAMILY/'evidence/ONE_TIME_ORIGINAL_SOURCE_COPY_V1.json').is_file():
        raise RuntimeError('Existing parent has no one-time copy receipt')
    records = []
    for path in sorted(parent.rglob('*')):
        if path.is_file():
            origin = BASE / path.relative_to(parent)
            if digest(path) != digest(origin):
                raise RuntimeError('Original parent copy differs')
            records.append({'source': origin.relative_to(ROOT).as_posix(),
                            'path': path.relative_to(ROOT).as_posix(),
                            'bytes': path.stat().st_size, 'sha256': digest(path)})
    replacements = {
        'ZetaTerminusNext': NAME,
        'zt-next-v7-rlo1-return-portfolio-v1': 'zt-opt-v7-rc4-consensus-control-v1',
        'ZT-PORT-NEXT-V7R-RLO1-20260907': 'ZT-OPT-V7-RC4-CONSENSUS-CONTROL-20260908',
        'NEXT-E03-V7R-RLO1-0bba2ca045fe': 'OPT-V7-RC4-CONSENSUS-CONTROL-V1',
        '"7R1"': '"RC4C1CONTROL"',
        'ZT_NEXT_7R1_STATE_V1': 'ZT_RC4C1_CONTROL_STATE_V1',
        'ZT_NEXT_7R1_OBSERVATION_STATE_V1': 'ZT_RC4C1_CONTROL_OBSERVATION_STATE_V1',
    }
    replacements.update({str(260907701+i): str(2609081101+i) for i in range(6)})
    paths = {
        'STATE_PATH_A': 'state/state-a.csv', 'STATE_PATH_B': 'state/state-b.csv',
        'EVENT_PATH_A': 'state/events-a.csv', 'EVENT_PATH_B': 'state/events-b.csv',
        'CURRENT_SNAPSHOT_PATH_A': 'state/current-a.csv',
        'CURRENT_SNAPSHOT_PATH_B': 'state/current-b.csv',
        'OWNERSHIP_PATH': 'state/runtime.lock',
        'RESEARCH_OBSERVATION_DIRECTORY': 'research',
        'RESEARCH_OBSERVATION_STATE_PATH_A': 'research/research-state-a.csv',
        'RESEARCH_OBSERVATION_STATE_PATH_B': 'research/research-state-b.csv',
        'RESEARCH_CANDIDATE_LEDGER_PATH': 'research/research-candidates.csv',
        'RESEARCH_LIFECYCLE_LEDGER_PATH': 'research/research-lifecycles.csv',
    }
    source = parent / 'MQL5/Include/ZetaTerminusNext'
    destination = FAMILY / 'mt5/MQL5/Include' / NAME
    for path in source.rglob('*.mqh'):
        text = path.read_text(encoding='utf-8-sig')
        for old, new in replacements.items():
            text = text.replace(old, new)
        if path.name == 'ZetaDomain.mqh':
            text = text.replace('input double InpReferenceCapitalUSD',
                                'input string InpRunTag = "source-2024-v1";\n\ninput double InpReferenceCapitalUSD', 1)
            for name in paths:
                text, count = re.subn(r'const string '+name+r'\s*=\s*"[^"\n]*";',
                                     'string '+name+' = "";', text)
                if count != 1:
                    raise RuntimeError('Own path declaration not found: '+name)
        write(destination / path.relative_to(source), text)
    ea = (parent/'MQL5/Experts/ZetaTerminusNext/ZetaNextV7ReturnPortfolio.mq5').read_text(encoding='utf-8-sig')
    for old, new in replacements.items():
        ea = ea.replace(old, new)
    assignments = '\n'.join('   '+name+' = run_root+"\\\\'+suffix.replace('/', '\\\\')+'";'
                            for name, suffix in paths.items())
    initializer = '''bool InitializeOwnedSourcePaths()
  {
   if(!MQLInfoInteger(MQL_TESTER) || StringLen(InpRunTag)<1 || StringLen(InpRunTag)>48)
      return(false);
   for(int i=0;i<StringLen(InpRunTag);++i)
     {
      const ushort c=StringGetCharacter(InpRunTag,i);
      if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='-'))
         return(false);
     }
   const string run_root="ZetaV7RC4ConsensusControl\\\\"+InpRunTag;
ASSIGNMENTS
   const string marker=run_root+"\\\\source-started.bin";
   if(FileIsExist(marker) || FileIsExist(STATE_PATH_A) || FileIsExist(STATE_PATH_B) ||
      FileIsExist(EVENT_PATH_A) || FileIsExist(EVENT_PATH_B) ||
      FileIsExist(CURRENT_SNAPSHOT_PATH_A) || FileIsExist(CURRENT_SNAPSHOT_PATH_B) ||
      FileIsExist(OWNERSHIP_PATH) || FileIsExist(RESEARCH_OBSERVATION_STATE_PATH_A) ||
      FileIsExist(RESEARCH_OBSERVATION_STATE_PATH_B) ||
      FileIsExist(RESEARCH_CANDIDATE_LEDGER_PATH) || FileIsExist(RESEARCH_LIFECYCLE_LEDGER_PATH))
      return(false);
   FolderCreate("ZetaV7RC4ConsensusControl");
   FolderCreate(run_root);FolderCreate(run_root+"\\\\state");FolderCreate(run_root+"\\\\research");
   const int handle=FileOpen(marker,FILE_WRITE|FILE_BIN);
   if(handle==INVALID_HANDLE) return(false);
   FileWriteInteger(handle,1,INT_VALUE);FileFlush(handle);FileClose(handle);
   return(true);
  }


'''.replace('ASSIGNMENTS', assignments)
    ea = ea.replace('int OnInit()\n  {', initializer+'int OnInit()\n  {', 1)
    start = ea.index('   FolderCreate("'+NAME+'")', ea.index('int OnInit()'))
    end = ea.index('   if(!AcquireRuntimeOwnership())', start)
    ea = ea[:start] + '   if(!InitializeOwnedSourcePaths()) return(INIT_FAILED);\n' + ea[end:]
    write(FAMILY/'mt5/MQL5/Experts'/f'{NAME}.mq5', ea)
    preset = (parent/'MQL5/Presets/ZetaTerminusNext/next-v7-return.set').read_text(encoding='utf-8-sig')
    preset = '; Original V7 source recording; tester only, fresh own identity.\n'+preset.split('\n',1)[1]
    preset = re.sub(r'^InpEventCapacity=.*$', 'InpEventCapacity=8192||8192||1||8192||N', preset, flags=re.M)
    preset += '\nInpRunTag=source-2024-v1\n'
    write(FAMILY/'settings/source-2024-v1.set', preset)
    write(FAMILY/'settings/source-2024-v1.ini', '''[Common]
KeepPrivate=1
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[Tester]
Expert=ZetaV7RC4ConsensusControl.ex5
ExpertParameters=source-2024-v1.set
Symbol=US30
Period=M30
Optimization=0
Model=4
FromDate=2024.01.01
ToDate=2025.01.01
ForwardMode=0
Deposit=100
Currency=USD
Leverage=100
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
Report=reports\\source-2024-v1
ReplaceReport=0
ShutdownTerminal=1
''')
    write(FAMILY/'settings/history.ini', '[Experts]\nEnabled=0\nAllowLiveTrading=0\nAllowDllImport=0\n')
    if not (FAMILY/'evidence/ONE_TIME_ORIGINAL_SOURCE_COPY_V1.json').exists():
     write(FAMILY/'evidence/ONE_TIME_ORIGINAL_SOURCE_COPY_V1.json', json.dumps({
        'status': 'ORIGINAL_PARENT_COPIED_ONCE_AND_OWN_TESTER_CONTROL_AUTHORED',
        'files': records, 'closed_candidate_source_or_model_imported': False,
        'own_change': 'Identity, private run paths, tester-only fresh marker and original permitted8192event setting. Original trading equations and sequencing unchanged.'}, indent=2)+'\n')
    print('OWN_ORIGINAL_SOURCE_AUTHORED', len(records), flush=True)


if __name__ == '__main__':
    main()
