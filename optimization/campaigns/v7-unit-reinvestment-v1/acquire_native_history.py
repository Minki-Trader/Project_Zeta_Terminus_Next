"""Capture this V7 family's full native bar inputs for ordinary economic runs."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, io, json, re, shutil, sys
import MetaTrader5 as mt5
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
FAMILY=Path(__file__).resolve().parent
RUNTIME=ROOT/'optimization/runtime/v7-unit-reinvestment-v1-portable'
RAW=ROOT/'optimization/artifacts/raw/v7-unit-reinvestment-v1'

def capture(tag):
    match=re.fullmatch(r'(selection|confirmation)-(before|after)-(control|reinvest)-v[1-9][0-9]*',tag)
    if not match: raise ValueError('Only the declared whole native matrix inputs are supported')
    phase,_,role=match.groups()
    if phase=='confirmation':
        finalist=json.loads((FAMILY/'evidence/FINALIST_FREEZE_V1.json').read_text())
        if finalist['status']!='ONE_UNCHANGED_NATIVE_UNIT_FINALIST': raise RuntimeError('No finalist authority')
    end=datetime(2026,1,1,tzinfo=timezone.utc) if phase=='selection' else datetime(2026,9,1,tzinfo=timezone.utc)
    begin=datetime(2024,1,1,tzinfo=timezone.utc)
    output=RAW/'history-observations'/f'{tag}.json'
    if output.exists(): raise RuntimeError('Preserve the existing native observation')
    if shutil.disk_usage(ROOT).free<30*1024**3+256*1024**2: raise RuntimeError('Native input reserve')
    if not mt5.initialize(str(RUNTIME/'terminal64.exe'),portable=True,timeout=60000): raise RuntimeError(str(mt5.last_error()))
    try:
        info=mt5.terminal_info()
        if info is None or Path(info.path).resolve()!=RUNTIME.resolve() or Path(info.data_path).resolve()!=RUNTIME.resolve(): raise RuntimeError('Wrong physical Portable')
        records=[]
        for symbol in ('US30','US100','US500'):
            data=mt5.copy_rates_range(symbol,mt5.TIMEFRAME_M1,begin,end)
            if data is None: raise RuntimeError(str(mt5.last_error()))
            data=data[(data['time']>=int(begin.timestamp()))&(data['time']<int(end.timestamp()))]
            if len(data)==0 or np.any(np.diff(data['time'])<=0): raise RuntimeError('Incomplete or unordered native input')
            stream=io.BytesIO();np.save(stream,data,allow_pickle=False);content=stream.getvalue();digest=hashlib.sha256(content).hexdigest().upper()
            path=RAW/'history'/f'{symbol}-{digest}.npy';path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest().upper()!=digest: raise RuntimeError('Existing input content differs')
            else:path.write_bytes(content)
            records.append(dict(symbol=symbol,path=path.relative_to(ROOT).as_posix(),sha256=digest,bytes=len(content),rows=len(data),first=int(data['time'][0]),last=int(data['time'][-1]),fields=list(data.dtype.names)))
        result=dict(utc=datetime.now(timezone.utc).isoformat(),status='FULL_NATIVE_M1_CAPTURE_COMPLETE',tag=tag,terminal_build=info.build,terminal_path=str(RUNTIME),begin=str(begin),end_exclusive=str(end),clock='Unshifted native server-epoch integers; timezone encoding does not convert exchange sessions.',records=records,account_position_order_deal_queries=False,live_changes=False)
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':result['status'],'tag':tag,'rows':{v['symbol']:v['rows'] for v in records},'build':info.build}))
    finally:mt5.shutdown()

if __name__=='__main__':capture(sys.argv[1])
