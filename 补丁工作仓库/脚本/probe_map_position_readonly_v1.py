"""Bounded external position sampling. ReadProcessMemory only; no hooks or input."""
import argparse,csv,ctypes,hashlib,json,sqlite3,struct,subprocess,time
from ctypes import wintypes as wt
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'补丁工作仓库'
OUT=WORK/'地图开发/逐图开发/01_罗刹山洞（首次梦中进入）/线路校准/只读定位记录.json'

def read_snapshot(read,base,known):
 def mem(va,n):return read(base+va-0x400000,n)
 def u32(va):return struct.unpack('<I',mem(va,4))[0]
 def header():return (u32(0x53d064),u32(0x53a5fc),u32(0x52cda0),u32(0x53ccd0),u32(0x53ccd4))
 h=header();scene,leader,total,width,height=h
 if scene not in known:return dict(valid=False,scene_id=scene,reason='scene not in exported index')
 if not(1<=total<=2048 and leader<total):return dict(valid=False,scene_id=scene,reason='leader/object list not ready')
 if [width,height]!=known[scene]:return dict(valid=False,scene_id=scene,reason='map dimensions changing or unsupported')
 actor=base+0x13e8c8+leader*0x48
 raw=read(actor,0x40);x,y=struct.unpack_from('<2H',raw,4);actor_id=struct.unpack_from('<H',raw,0x20)[0]
 if h!=header():return dict(valid=False,scene_id=scene,reason='scene or leader changed during snapshot')
 if not(0<=x<width*16 and 0<=y<height*16):return dict(valid=False,scene_id=scene,reason='position outside indexed map')
 return dict(valid=True,scene_id=scene,leader_slot=leader,actor_id=actor_id,object_count=total,
  world_xy=[x,y],grid_xy=[x/16,y/16],grid_size=[width,height],actor_address=hex(actor))

class Module(ctypes.Structure):
 _fields_=[('dwSize',wt.DWORD),('th32ModuleID',wt.DWORD),('th32ProcessID',wt.DWORD),
  ('GlblcntUsage',wt.DWORD),('ProccntUsage',wt.DWORD),('modBaseAddr',ctypes.c_void_p),
  ('modBaseSize',wt.DWORD),('hModule',wt.HMODULE),('szModule',wt.WCHAR*256),('szExePath',wt.WCHAR*260)]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=8);ap.add_argument('--hz',type=float,default=5)
 args=ap.parse_args()
 if not(0<args.seconds<=30 and 0<args.hz<=10):raise ValueError('Bounded samples: seconds<=30, hz<=10')
 task=subprocess.run(['tasklist','/FI','IMAGENAME eq NewPAL_Release.exe','/FO','CSV','/NH'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
 rows=list(csv.reader(task.stdout.decode(errors='replace').splitlines()));pids=[int(r[1]) for r in rows if r and r[0].lower()=='newpal_release.exe']
 if len(pids)!=1:raise RuntimeError('Expected one running game; open through Steam and enter a map first')
 pid=pids[0];k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateToolhelp32Snapshot.argtypes=[wt.DWORD,wt.DWORD];k.CreateToolhelp32Snapshot.restype=wt.HANDLE
 k.Module32FirstW.argtypes=[wt.HANDLE,ctypes.POINTER(Module)];k.Module32FirstW.restype=wt.BOOL
 k.Module32NextW.argtypes=[wt.HANDLE,ctypes.POINTER(Module)];k.Module32NextW.restype=wt.BOOL
 k.CloseHandle.argtypes=[wt.HANDLE];k.CloseHandle.restype=wt.BOOL
 k.OpenProcess.argtypes=[wt.DWORD,wt.BOOL,wt.DWORD];k.OpenProcess.restype=wt.HANDLE
 k.ReadProcessMemory.argtypes=[wt.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)];k.ReadProcessMemory.restype=wt.BOOL
 handle=k.CreateToolhelp32Snapshot(0x18,pid)
 if handle in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
 try:
  module=Module();module.dwSize=ctypes.sizeof(Module);ok=k.Module32FirstW(handle,ctypes.byref(module));base=None
  while ok:
   if module.szModule.lower()=='newpal_release.exe':base=module.modBaseAddr;break
   ok=k.Module32NextW(handle,ctypes.byref(module))
  if not base:raise RuntimeError('Game module not found')
 finally:k.CloseHandle(handle)
 # PROCESS_VM_READ + PROCESS_QUERY_LIMITED_INFORMATION; no write/injection access.
 process=k.OpenProcess(0x1010,False,pid)
 if not process:raise ctypes.WinError(ctypes.get_last_error())
 def read(addr,n):
  buf=ctypes.create_string_buffer(n);got=ctypes.c_size_t()
  if not k.ReadProcessMemory(process,addr,buf,n,ctypes.byref(got)) or got.value!=n:raise ctypes.WinError(ctypes.get_last_error())
  return buf.raw
 c=sqlite3.connect((WORK/'地图开发/地图索引/scene_export_index.sqlite').as_uri()+'?mode=ro',uri=True)
 known={id:[w,h] for id,w,h in c.execute('SELECT scene_id,grid_width,grid_height FROM scenes WHERE map_exists=1')};c.close()
 samples=[];start=time.monotonic()
 try:
  if read(base,2)!=b'MZ':raise RuntimeError('Unexpected module header')
  print('READY: bounded read-only sampling; keep the game foreground and move normally',flush=True)
  while time.monotonic()-start<args.seconds:
   try:sample=read_snapshot(read,base,known)
   except OSError as e:sample=dict(valid=False,reason='read failed or process ended: '+str(e))
   sample['elapsed_ms']=round((time.monotonic()-start)*1000);samples.append(sample)
   time.sleep(1/args.hz)
 finally:k.CloseHandle(process)
 record=dict(status='external read-only samples; no hooks or game changes',
  captured_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),pid=pid,module_base=hex(base),
  disk_exe_sha1=hashlib.sha1((ROOT/'NewPAL_Release.exe').read_bytes()).hexdigest(),
  seconds=args.seconds,hz=args.hz,samples=samples,valid_samples=sum(p['valid'] for p in samples),
  note='world_xy are raw leader object+4/+6 values; foot-anchor alignment is to be checked against gameplay. No movement deltas are required to be exactly16.')
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(output=str(OUT),samples=len(samples),valid=record['valid_samples'],scenes=sorted({p['scene_id'] for p in samples if p['valid']})),ensure_ascii=True),flush=True)

if __name__=='__main__':main()
