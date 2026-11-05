"""Opt-in development mailbox on the native game thread; inactive without a leased test session."""
import hashlib,json,sqlite3,struct
import flash_v4 as pe
from settings_toggle_v1 import imports

BASE='a95e308bc2c28413c7617c37e67c0c723a71f7f0'
OUT=pe.ROOT/'补丁工作仓库/候选版本/map-test-v1'
ASSETS=[]
SIZE=0x4000
MAGIC=int.from_bytes(b'NMT1','little')
LEASE_MS=3000

def dimensions():
 c=sqlite3.connect((pe.ROOT/'补丁工作仓库/地图开发/地图索引/scene_export_index.sqlite').as_uri()+'?mode=ro',uri=True)
 rows=c.execute('SELECT scene_id,grid_width,grid_height FROM scenes WHERE map_exists=1').fetchall();c.close()
 table=bytearray(1024*4)
 for id,w,h in rows:
  if not(0<id<1024 and 0<w<=4095 and 0<h<=4095):raise ValueError('Unexpected map dimensions')
  struct.pack_into('<HH',table,id*4,w,h)
 return bytes(table),rows

def payload(origin,source,frame_target):
 a=pe.Asm(origin);sy={};fields=['magic','version','enabled','heartbeat','request','ack','scene','x','y','result','busy','frames','warps','blocked_saves']
 st={k:origin+0x1000+i*4 for i,k in enumerate(fields)};dims=origin+0x2000;iat=imports(source)
 def op(s,addr,end=b''):a.raw(bytes.fromhex(s)+pe.u32(addr)+end)
 def store(addr,v):op('c7 05',addr,pe.u32(v))
 def cmp(addr,v):op('81 3d',addr,pe.u32(v))
 def start(n):sy[n]=a.pc;a.label(n)
 def call(n):a.jump('e8',n)
 def push(v):a.raw(b'\x68'+pe.u32(v))
 def ticks():op('ff 15',iat['SDL_GetTicks'])
 start('active');cmp(st['enabled'],1);a.jump('0f 85','inactive');ticks();op('2b 05',st['heartbeat']);a.raw(b'\x3d'+pe.u32(LEASE_MS));a.jump('0f 83','inactive');a.raw('b8 01 00 00 00 c3');a.label('inactive');a.raw('31 c0 c3')

 start('frame');a.raw('9c 60');op('ff 05',st['frames']);call('active');a.raw('85 c0');a.jump('0f 85','check_request')
 op('a1',st['request']);op('3b 05',st['ack']);a.jump('0f 84','frame_done');op('a3',st['ack']);store(st['result'],5);a.jump('e9','frame_done')
 a.label('check_request');cmp(st['busy'],0);a.jump('0f 85','frame_done');op('a1',st['request']);op('3b 05',st['ack']);a.jump('0f 84','frame_done')
 # Consume before invoking the loader, so event pumping cannot repeat a warp.
 op('a3',st['ack']);store(st['result'],10);store(st['busy'],1)
 for addr in (0x531b80,0x531b7c,0x56ffc0,0x56ffc4):cmp(addr,0);a.jump('0f 85','bad_context')
 op('80 3d',0x53a605,b'\x00');a.jump('0f 85','bad_context')
 op('f7 05',0x53b628,pe.u32(0x61));a.jump('0f 85','bad_context');op('66 83 3d',0x5628e8,b'\xff');a.jump('0f 85','bad_context')
 # The owned map overlay can be closed; never dismiss the native menu/story UI.
 cmp(0x53b8d8,0x40000000);a.jump('0f 85','menu_checked');call(0x5ed0af)
 a.label('menu_checked');cmp(0x53b8d8,0);a.jump('0f 85','bad_context')
 op('8b 1d',0x53a5fc);op('a1',0x52cda0);a.raw('85 c0');a.jump('0f 84','bad_context');a.raw('3d 00 08 00 00');a.jump('0f 87','bad_context');a.raw('3b d8');a.jump('0f 83','bad_context')
 a.raw('6b db 48 81 c3'+pe.u32(0x53e8c8).hex()+' 83 7b 3c 00');a.jump('0f 84','bad_context')
 op('a1',st['scene']);a.raw('3d 00 04 00 00');a.jump('0f 83','bad_scene');a.raw('0f b7 0c 85'+pe.u32(dims).hex()+' 0f b7 14 85'+pe.u32(dims+2).hex()+' 85 c9');a.jump('0f 84','bad_scene');a.raw('85 d2');a.jump('0f 84','bad_scene')
 op('a1',st['x']);a.raw('3b c1');a.jump('0f 83','bad_xy');op('a1',st['y']);a.raw('3b c2');a.jump('0f 83','bad_xy')
 push(1);push(0xffff);push(0xffff);push(0xffff);op('ff 35',st['y']);op('ff 35',st['x']);op('ff 35',st['scene']);call(0x49dc40);a.raw('83 c4 1c')
 op('a1',st['scene']);op('3b 05',0x53d064);a.jump('0f 85','load_failed');store(st['result'],1);op('ff 05',st['warps']);a.jump('e9','request_done')
 a.label('bad_context');store(st['result'],2);a.jump('e9','request_done')
 a.label('bad_scene');store(st['result'],3);a.jump('e9','request_done')
 a.label('bad_xy');store(st['result'],4);a.jump('e9','request_done')
 a.label('load_failed');store(st['result'],6)
 a.label('request_done');store(st['busy'],0)
 a.label('frame_done');a.raw('61 9d');a.jump('e9',frame_target)

 # Four verified ordinary encounter gates. The original chain remains exact
 # when inactive/expired; active testing overrides settings and incense.
 gates={}
 for i,site in enumerate(pe.TIMER_SITES):
  off=pe.rva_offset(source,site);old=source[off:off+5]
  if old[0]!=0xe9:raise ValueError('Expected current settings encounter gate')
  target=pe.IMAGE_BASE+site+5+int.from_bytes(old[1:],'little',signed=True)
  start('gate_'+str(i));a.raw('9c 60');call('active');a.raw('85 c0');a.jump('0f 85','protect_'+str(i));a.raw('61 9d');a.jump('e9',target)
  a.label('protect_'+str(i));a.raw('61 9d 50 31 c0 83 f8 01 58');a.jump('e9',pe.IMAGE_BASE+site+5)
  gates[site]=(old,pe.branch(0xe9,pe.IMAGE_BASE+site,sy['gate_'+str(i)]))

 start('save_guard');a.raw('9c 60');call('active');a.raw('85 c0');a.jump('0f 84','save_normal');op('ff 05',st['blocked_saves']);a.raw('61 9d c3')
 a.label('save_normal');a.raw('61 9d 55 8b ec 6a ff');a.jump('e9',0x4c7105)
 blob=bytearray(a.finish());assert len(blob)<0x1000;blob.extend(bytes(SIZE-len(blob)))
 struct.pack_into('<II',blob,0x1000,MAGIC,1);table,rows=dimensions();blob[0x2000:0x3000]=table
 return dict(blob=bytes(blob),symbols=sy,state=st,origin=origin,gates=gates,scene_count=len(rows),code_size=len(a.buf))

def candidate(source=None):
 source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
 if hashlib.sha1(source).hexdigest()!=BASE:raise ValueError('Expected accepted radius60 baseline')
 h,o,secs=pe.pe_info(source);last=secs[-1]
 if last[4]+last[3]!=len(source):raise ValueError('Unexpected file overlay')
 frame=0x4af11c;off=pe.rva_offset(source,frame-pe.IMAGE_BASE);old=source[off:off+5]
 if old[0]!=0xe8:raise ValueError('Outer frame call differs')
 target=frame+5+int.from_bytes(old[1:],'little',signed=True);origin=pe.IMAGE_BASE+last[2]+last[3];p=payload(origin,source,target)
 out=bytearray(source);out.extend(p['blob']);patches=dict(p['gates']);patches[frame-pe.IMAGE_BASE]=(old,pe.branch(0xe8,frame,p['symbols']['frame']))
 patches[0xc7100]=(bytes.fromhex('55 8b ec 6a ff'),pe.branch(0xe9,0x4c7100,p['symbols']['save_guard']))
 # Verify the cached original map close entry, never use a guessed address.
 close=pe.rva_offset(source,0x5ed0af-pe.IMAGE_BASE)
 if source[close:close+10]!=bytes.fromhex('c7 05 00 f0 5e 00 00 00 00 00'):raise ValueError('Map close helper differs')
 for rva,(a,b) in patches.items():
  at=pe.rva_offset(source,rva)
  if source[at:at+len(a)]!=a:raise ValueError('Patch source differs')
  out[at:at+len(b)]=b
 sh=o+struct.unpack_from('<H',source,h+20)[0]+(len(secs)-1)*40;size=last[3]+SIZE
 for off in (sh+8,sh+16):struct.pack_into('<I',out,off,size)
 struct.pack_into('<I',out,o+56,last[2]+size);struct.pack_into('<I',out,o+4,struct.unpack_from('<I',source,o+4)[0]+SIZE);struct.pack_into('<I',out,o+64,0)
 p.update(patches=patches,frame_target=target)
 return bytes(out),p

def main():
 OUT.mkdir(exist_ok=True);data,p=candidate();(OUT/'NewPAL_Release.exe').write_bytes(data)
 report={k:v for k,v in p.items() if k not in ('blob','patches','gates')};report.update(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest(),status='development bridge; internal checks pending',lease_ms=LEASE_MS,normal_default='disabled; expires when the controller heartbeat is absent')
 (OUT/'candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'assets.json').write_text('[]\n',encoding='utf-8');print(json.dumps(dict(sha1=report['candidate_sha1'],scene_count=p['scene_count'],code_size=p['code_size']),indent=2))

if __name__=='__main__':main()
