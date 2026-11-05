"""Relocatable, leased map-test bridge for exact original/v5 profiles; RAM only."""
import struct
from flash_v4 import Asm,u32,branch

SIZE=0x4000
FRAME_RVA=0xaf11c
SAVE_RVA=0xc7100
GATES=[(0x5d3dd,8,0x5d5a7),(0x5de5f,7,0x5de76),(0x73863,6,0x73875),(0x93736,7,0x9373d)]
SIGNATURE=b'NPT2RAM1'

def rebased(profile,base,rva,hexdata):
 data=bytearray.fromhex(hexdata);delta=base-0x400000
 for address in profile.get('relocations',[]):
  if rva<=address and address+4<=rva+len(data):
   offset=address-rva;struct.pack_into('<I',data,offset,(struct.unpack_from('<I',data,offset)[0]+delta)&0xffffffff)
 return bytes(data)

def payload(origin,base,profile,table):
 a=Asm(origin);sy={};st={k:origin+0x1000+i*4 for i,k in enumerate(['magic','version','enabled','heartbeat','request','ack','scene','x','y','result','busy','frames','warps','blocked_saves'])}
 def va(v):return base+v-0x400000
 def op(code,addr,end=b''):a.raw(bytes.fromhex(code)+u32(addr)+end)
 def store(addr,v):op('c7 05',addr,u32(v))
 def cmp(addr,v):op('81 3d',addr,u32(v))
 def start(n):sy[n]=a.pc;a.label(n)
 def call(n):a.jump('e8',n)
 def push(v):a.raw(b'\x68'+u32(v))
 start('active');cmp(st['enabled'],1);a.jump('0f 85','inactive');op('ff 15',base+profile['ticks_iat_rva']);op('2b 05',st['heartbeat']);a.raw(b'\x3d'+u32(3000));a.jump('0f 83','inactive');a.raw('b8 01 00 00 00 c3');a.label('inactive');a.raw('31 c0 c3')
 start('frame');a.raw('9c 60');op('ff 05',st['frames']);call('active');a.raw('85 c0');a.jump('0f 85','check_request')
 op('a1',st['request']);op('3b 05',st['ack']);a.jump('0f 84','frame_done');op('a3',st['ack']);store(st['result'],5);a.jump('e9','frame_done')
 a.label('check_request');cmp(st['busy'],0);a.jump('0f 85','frame_done');op('a1',st['request']);op('3b 05',st['ack']);a.jump('0f 84','frame_done');op('a3',st['ack']);store(st['result'],10);store(st['busy'],1)
 for addr in (0x531b80,0x531b7c,0x56ffc0,0x56ffc4):cmp(va(addr),0);a.jump('0f 85','bad_context')
 op('80 3d',va(0x53a605),b'\x00');a.jump('0f 85','bad_context');op('f7 05',va(0x53b628),u32(0x61));a.jump('0f 85','bad_context');op('66 83 3d',va(0x5628e8),b'\xff');a.jump('0f 85','bad_context')
 # A portable bridge never calls project-specific overlay helpers.
 cmp(va(0x53b8d8),0);a.jump('0f 85','bad_context');op('8b 1d',va(0x53a5fc));op('a1',va(0x52cda0));a.raw('85 c0');a.jump('0f 84','bad_context');a.raw('3d 00 08 00 00');a.jump('0f 87','bad_context');a.raw('3b d8');a.jump('0f 83','bad_context')
 a.raw(b'\x6b\xdb\x48\x81\xc3'+u32(va(0x53e8c8))+bytes.fromhex('83 7b 3c 00'));a.jump('0f 84','bad_context')
 op('a1',st['scene']);a.raw('3d 00 04 00 00');a.jump('0f 83','bad_scene');a.raw(b'\x0f\xb7\x0c\x85'+u32(origin+0x2000)+b'\x0f\xb7\x14\x85'+u32(origin+0x2002)+bytes.fromhex('85 c9'));a.jump('0f 84','bad_scene');a.raw('85 d2');a.jump('0f 84','bad_scene')
 op('a1',st['x']);a.raw('3b c1');a.jump('0f 83','bad_xy');op('a1',st['y']);a.raw('3b c2');a.jump('0f 83','bad_xy')
 push(1);push(0xffff);push(0xffff);push(0xffff);op('ff 35',st['y']);op('ff 35',st['x']);op('ff 35',st['scene']);call(va(0x49dc40));a.raw('83 c4 1c');op('a1',st['scene']);op('3b 05',va(0x53d064));a.jump('0f 85','load_failed');store(st['result'],1);op('ff 05',st['warps']);a.jump('e9','request_done')
 for label,result in [('bad_context',2),('bad_scene',3),('bad_xy',4),('load_failed',6)]:
  a.label(label);store(st['result'],result);a.jump('e9','request_done')
 a.label('request_done');store(st['busy'],0);a.label('frame_done');a.raw('61 9d');a.jump('e9',base+profile['frame_target_rva'])
 for i,(rva,n,skip) in enumerate(GATES):
  start('gate_'+str(i));a.raw('9c 60');call('active');a.raw('85 c0');a.jump('0f 85','protect_'+str(i));a.raw('61 9d')
  target=profile['gates'][i].get('normal_target_rva')
  if target is not None:a.jump('e9',base+target)
  elif i==0:a.raw('85 c0');a.jump('0f 84',base+skip);a.jump('e9',base+rva+n)
  else:
   a.raw(bytes.fromhex('66 a3' if i==2 else '66 89 15')+u32(va(0x5628e8)));a.jump('e9',base+rva+n)
  a.label('protect_'+str(i));a.raw('61 9d');a.jump('e9',base+skip)
 start('save_guard');a.raw('9c 60');call('active');a.raw('85 c0');a.jump('0f 84','save_normal');op('ff 05',st['blocked_saves']);a.raw('61 9d c3');a.label('save_normal');a.raw('61 9d 55 8b ec 6a ff');a.jump('e9',base+SAVE_RVA+5)
 code=a.finish();assert len(code)<0x1000
 blob=bytearray(SIZE);blob[:len(code)]=code;blob[0x1000:0x1008]=b'NMT1\x01\0\0\0';blob[0x2000:0x3000]=table;blob[0x3000:0x3008]=SIGNATURE
 patches={base+FRAME_RVA:branch(0xe8,base+FRAME_RVA,sy['frame']),base+SAVE_RVA:branch(0xe9,base+SAVE_RVA,sy['save_guard'])}
 patches.update({base+rva:branch(0xe9,base+rva,sy['gate_'+str(i)])+b'\x90'*(n-5) for i,(rva,n,_) in enumerate(GATES)})
 return dict(blob=bytes(blob),symbols=sy,state=st,patches=patches)

class ThreadEntry(__import__('ctypes').Structure):
 from ctypes import wintypes as wt
 _fields_=[('dwSize',wt.DWORD),('cntUsage',wt.DWORD),('th32ThreadID',wt.DWORD),('th32OwnerProcessID',wt.DWORD),('tpBasePri',wt.LONG),('tpDeltaPri',wt.LONG),('dwFlags',wt.DWORD)]

def attach(game,profile,table):
 """Install under a bounded all-thread pause, or reuse an identical dormant bridge.

 Allocations remain dormant until process exit. Never free code that a game thread
 might still be executing, and never unhook a live five-byte instruction on close.
 """
 import ctypes as c,time
 from ctypes import wintypes as wt
 k=game.k;handle=game.handle;base=game.base
 definitions={
  'VirtualAllocEx':([wt.HANDLE,c.c_void_p,c.c_size_t,wt.DWORD,wt.DWORD],c.c_void_p),
  'VirtualProtectEx':([wt.HANDLE,c.c_void_p,c.c_size_t,wt.DWORD,c.POINTER(wt.DWORD)],wt.BOOL),
  'FlushInstructionCache':([wt.HANDLE,c.c_void_p,c.c_size_t],wt.BOOL),
  'OpenThread':([wt.DWORD,wt.BOOL,wt.DWORD],wt.HANDLE),'SuspendThread':([wt.HANDLE],wt.DWORD),'ResumeThread':([wt.HANDLE],wt.DWORD),
  'Thread32First':([wt.HANDLE,c.POINTER(ThreadEntry)],wt.BOOL),'Thread32Next':([wt.HANDLE,c.POINTER(ThreadEntry)],wt.BOOL)}
 context_fn=k.Wow64GetThreadContext if c.sizeof(c.c_void_p)==8 else k.GetThreadContext
 context_fn.argtypes=[wt.HANDLE,c.c_void_p];context_fn.restype=wt.BOOL
 for name,(args,result) in definitions.items():getattr(k,name).argtypes=args;getattr(k,name).restype=result
 def read(addr,n):return game.read(addr-base+0x400000,n)
 def write(addr,data):
  buf=c.create_string_buffer(data);got=c.c_size_t()
  if not k.WriteProcessMemory(handle,addr,buf,len(data),c.byref(got)) or got.value!=len(data):raise c.WinError(c.get_last_error())
 def threads():
  snap=k.CreateToolhelp32Snapshot(4,0)
  if snap in (None,c.c_void_p(-1).value):raise c.WinError(c.get_last_error())
  try:
   e=ThreadEntry();e.dwSize=c.sizeof(e);ok=k.Thread32First(snap,c.byref(e));result=[]
   while ok:
    if e.th32OwnerProcessID==game.pid:result.append(e.th32ThreadID)
    ok=k.Thread32Next(snap,c.byref(e))
   if c.get_last_error()!=18:raise c.WinError(c.get_last_error())
   return result
  finally:k.CloseHandle(snap)
 original={base+FRAME_RVA:rebased(profile,base,FRAME_RVA,profile['frame_old']),base+SAVE_RVA:rebased(profile,base,SAVE_RVA,profile['save_old'])}
 original.update({base+rva:rebased(profile,base,rva,profile['gates'][i]['old']) for i,(rva,_,_) in enumerate(GATES)})
 current=read(base+FRAME_RVA,5)
 if current!=original[base+FRAME_RVA]:
  if current[0]!=0xe8:raise RuntimeError('游戏帧入口已被其他程序修改，拒绝连接')
  offset=payload(0x10000000,base,profile,table)['symbols']['frame']-0x10000000
  origin=base+FRAME_RVA+5+int.from_bytes(current[1:],'little',signed=True)-offset
  if not 0<origin<0x100000000-SIZE:raise RuntimeError('未知的游戏内存补丁')
  p=payload(origin,base,profile,table)
  if any(read(addr,len(data))!=data for addr,data in p['patches'].items()) or read(origin,0x1000)!=p['blob'][:0x1000] or read(origin+0x2000,0x1008)!=p['blob'][0x2000:0x3008]:raise RuntimeError('临时传送桥校验失败，拒绝连接')
  return origin,p['state']
 # Verify loader code as well as all hook sites; native loader is never patched.
 if read(base+0x9dc40,32)!=rebased(profile,base,0x9dc40,profile['loader_signature']):raise RuntimeError('原生地图加载入口与版本不符')
 if any(read(addr,len(data))!=data for addr,data in original.items()):raise RuntimeError('游戏内存入口与磁盘版本不符，拒绝修改')
 # Native mode/menu guards before any mutation.
 if game.u(0x531b80)!=0 or game.u(0x531b7c)!=0 or game.u(0x53b8d8)!=0:raise RuntimeError('请先读档进入能自由走动的地图，并关闭菜单/地图')
 origin=k.VirtualAllocEx(handle,None,SIZE,0x3000,0x40)
 if not origin or origin+SIZE>0x100000000:raise RuntimeError('无法分配32位临时传送桥')
 p=payload(origin,base,profile,table);write(origin,p['blob'])
 if read(origin,SIZE)!=p['blob']:raise RuntimeError('临时传送桥写入校验失败')
 if not k.FlushInstructionCache(handle,origin,SIZE):raise c.WinError(c.get_last_error())
 for attempt in range(5):
  held={};changed=[];protections=[];busy=False
  try:
   for _ in range(4):
    new=set(threads())-set(held)
    if not new:break
    for tid in sorted(new):
     th=k.OpenThread(0x5a,False,tid)
     if not th:raise c.WinError(c.get_last_error())
     if k.SuspendThread(th)==0xffffffff:k.CloseHandle(th);raise c.WinError(c.get_last_error())
     held[tid]=th
   else:raise RuntimeError('游戏线程仍在变化，请稍后重试')
   for th in held.values():
    ctx=c.create_string_buffer(716);struct.pack_into('<I',ctx,0,0x10001)
    if not context_fn(th,ctx):raise c.WinError(c.get_last_error())
    ip=struct.unpack_from('<I',ctx,184)[0]
    if any(addr<=ip<addr+len(data) for addr,data in original.items()):busy=True;break
   if not busy:
    if any(read(addr,len(data))!=data for addr,data in original.items()):raise RuntimeError('暂停后入口已改变，未安装')
    try:
     for addr,data in p['patches'].items():
      oldprotect=wt.DWORD()
      if not k.VirtualProtectEx(handle,addr,len(data),0x40,c.byref(oldprotect)):raise c.WinError(c.get_last_error())
      protections.append((addr,len(data),oldprotect.value));changed.append(addr);write(addr,data)
     if any(read(addr,len(data))!=data for addr,data in p['patches'].items()):raise RuntimeError('传送桥入口写入核对失败')
     if not k.FlushInstructionCache(handle,None,0):raise c.WinError(c.get_last_error())
    except Exception:
     for addr in reversed(changed):write(addr,original[addr])
     k.FlushInstructionCache(handle,None,0);raise
    finally:
     for addr,n,old in reversed(protections):
      ignored=wt.DWORD();k.VirtualProtectEx(handle,addr,n,old,c.byref(ignored))
    return origin,p['state']
  finally:
   for th in reversed(list(held.values())):k.ResumeThread(th);k.CloseHandle(th)
  time.sleep(.01)
 raise RuntimeError('入口正被执行，未安装临时桥；稍后重新连接即可')
