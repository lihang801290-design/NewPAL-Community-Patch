"""Read-only group-death research: static audit + unmodified native-code replay."""
import hashlib,json,re,struct,sys
from collections import Counter
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM
from unicorn.x86_const import *
import flash_v4 as pe
from native_damage_harness import Machine

BASE='a1f1d3f777684bfd84872412b57389ee5ab4d01a'
ROOT=pe.ROOT

def script_record(raw,id):
 start=raw.find(struct.pack('<II',0x7f102000,id))
 if start<0:return None
 rows=[];pos=start
 for _ in range(256):
  if pos+4>len(raw):raise ValueError('Truncated script')
  word=struct.unpack_from('<I',raw,pos)[0];count=(word>>20)&15
  if word>>24!=0x7f:raise ValueError('Unexpected script record at '+hex(pos))
  if count==15:
   return {'offset':start,'commands':rows,'extended_opcode':hex(word&0xff0fffff),'parse_note':'Extended-length record not decoded; do not classify as a simple parallel template'}
  args=list(struct.unpack_from('<'+'I'*count,raw,pos+4));rows.append({'offset':pos,'word':hex(word),'opcode':hex(word&0xff0fffff),'args':args})
  pos+=4+count*4
  if word==0x7f00ffff:return {'offset':start,'length':pos-start,'commands':rows}
 raise ValueError('Script record limit')

def native_fixture(binary,hps,scripts=None,already=None):
 m=Machine(binary);m.launched=[];m.coins=[];m.drops=[];m.removed=[];m.advanced=[];m.nodes=0
 enemies=[0x810000+i*0x100 for i in range(len(hps))];heroes=[0x814000,0x814100]
 def listing(address,roles,nodebase):
  m.w(address,nodebase if roles else 0);m.w(address+4,len(roles));m.w(address+8,0);m.w(address+12,nodebase if roles else 0)
  for i,role in enumerate(roles):
   n=nodebase+i*0x20;m.w(n+4,role);m.w(n+12,n-0x20 if i else 0);m.w(n+16,n+0x20 if i+1<len(roles) else 0)
 listing(0x830000,enemies,0x820000);listing(0x830100,heroes,0x824000);m.w(0x599898,0x830000);m.w(0x599894,0x830100)
 for i,(obj,hp) in enumerate(zip(enemies,hps)):
  m.w(obj,100+i*10);m.attr(obj,0x11,hp);m.attr(obj,0xb6,(scripts or [0x619]*len(hps))[i]);m.attr(obj,0xbe,10+i)
  if already and i in already:m.w(obj+0x28,(1<<2)|(1<<27))
 for i,obj in enumerate(heroes):
  m.w(obj,2000+i);m.attr(obj,0x11,100);m.attr(obj,0xb,20);m.attr(obj,9,0)
 m.w(0x531b88,0x2a7);m.w(0x531bc8,0x7777);m.w(0x599814,2);m.w(0x5998c4,0)
 def launch():
  actor=m.r(0x531bc0);m.launched.append({'actor':actor,'script':m.arg(0)})
  # External presentation stub models the native death FX's bit1B lifetime lock.
  obj=next(o for o in enemies+heroes if m.r(o)==actor);m.w(obj+0x28,m.r(obj+0x28)|(1<<27));return 1
 def coins():m.coins.append(m.r(m.arg(0)));return 5
 def drops():m.drops.append(m.r(m.arg(0)));return 42
 def allocate():
  p=0x8b0000+m.nodes*0x100;m.nodes+=1;m.w(p,4);m.w(p+4,p+0x40);return p
 m.stub(0x4cb710,launch);m.stub(0x4e0940,coins);m.stub(0x4e0530,drops)
 m.stub(0x4cdac0,allocate)
 # The actual list/flag/attribute operations and reward additions execute natively.
 m.stub(0x4eb050,lambda:m.removed.append(m.arg(0)) or 0)
 m.stub(0x4cba50,lambda:m.advanced.append(m.arg(0)) or 0)
 m.stub(0x4de7f0,lambda:0);m.stub(0x4de3c0,lambda:0)
 m.stub(0x4dfc70,lambda:0);m.stub(0x4ee740,lambda:0)
 def run(side=0):
  sp=0x9ef000;m.w(sp,0x9ff000);m.w(sp+4,side);m.w(sp+8,0x7777)
  preserved={UC_X86_REG_EBX:123,UC_X86_REG_ESI:234,UC_X86_REG_EDI:345,UC_X86_REG_EBP:0x9ed000}
  for r,v in preserved.items():m.u.reg_write(r,v)
  m.u.reg_write(UC_X86_REG_ESP,sp);m.u.emu_start(0x4ec840,0x9ff000,count=30000)
  assert m.u.reg_read(UC_X86_REG_EIP)==0x9ff000 and m.u.reg_read(UC_X86_REG_ESP)==sp+4
  assert all(m.u.reg_read(r)==v for r,v in preserved.items())
 m.run=run;m.enemies=enemies;m.heroes=heroes
 return m

def main():
 data=(ROOT/'NewPAL_Release.exe').read_bytes();assert hashlib.sha1(data).hexdigest()==BASE
 path=Path('USER_HOME/Doubao/chats/2026-10-18/new-chat/ghidra_decompile.c')
 if not path.exists():path=ROOT/'反编译参考/ghidra_decompile_历史版.c'
 text=path.read_text(encoding='utf-8');entries=[(int(m[1],16),m.start()) for m in re.finditer(r'/\* ===== FUN_([0-9a-f]+)',text)]
 official=(ROOT/'NewPAL_Release.exe.orig-ufa').read_bytes();ranges={}
 for address in (0x4ec840,0x4e6d00,0x4cb3d0,0x4e92e0,0x4f3280,0x4a7db0,0x4ee540,0x4e45d0,0x4f4d10):
  end=next(a for a,_ in entries if a>address);size=end-address
  current=data[pe.rva_offset(data,address-0x400000):][:size];old=official[pe.rva_offset(official,address-0x400000):][:size]
  ranges[hex(address)]={'length':size,'matches_official':current==old,'sha256':hashlib.sha256(current).hexdigest()}
 # EC840 contains the accepted historical UAF fix. Never restore the vanilla
 # decrement/dereference path after eb050 removes a battle object.
 at=pe.rva_offset(data,0xecb90);oa=pe.rva_offset(official,0xecb90)
 assert data[at:at+9]==bytes.fromhex('e9 e5 fc ff ff 90 90 90 90')
 assert official[oa:oa+9]==bytes.fromhex('8b 45 f4 83 e8 01 89 45 f4')
 check=bytearray(data[pe.rva_offset(data,0xec840):][:0x600]);check[0x350:0x359]=official[oa:oa+9]
 assert bytes(check)==official[pe.rva_offset(official,0xec840):][:0x600]
 ranges['0x4ec840']['known_difference']='9-byte UAF skip at4ECB90 ->4EC87A; all other function bytes equal official'
 cs=Cs(CS_ARCH_X86,CS_MODE_32);cs.detail=True;off=pe.rva_offset(data,0xe5f00);ins=list(cs.disasm(data[off:off+0x800],0x4e5f00));handlers={}
 for i,x in enumerate(ins):
  if i and x.mnemonic=='push' and x.operands[0].type==X86_OP_IMM and 0x7f002000<=x.operands[0].imm<0x7f002060:
   prev=ins[i-1]
   if prev.mnemonic=='push' and prev.operands[0].type==X86_OP_IMM:handlers[hex(x.operands[0].imm)]=hex(prev.operands[0].imm)
 assert handlers['0x7f00200d']=='0x4e6d00' and handlers['0x7f002038']=='0x4e92e0'
 assert handlers['0x7f002049']=='0x4e7ff0' and handlers['0x7f00204a']=='0x4e9490'
 # Explicit B6 death-script assignments in native monster data.
 mon=(ROOT/'gmon.dat').read_bytes();needle=struct.pack('<II',0x7f201001,0xb6);at=0;assignments=[]
 while True:
  at=mon.find(needle,at)
  if at<0:break
  assignments.append({'offset':at,'script':struct.unpack_from('<I',mon,at+8)[0]});at+=12
 counts=Counter(a['script'] for a in assignments)
 assert assignments,'Monster B6 assignments not found'
 wanted=set(counts)|{8000};scripts={};files={p.name:p.read_bytes() for p in ROOT.glob('*.dat') if p.name!='geindex.dat'}
 for id in sorted(wanted):
  if id==0xefff:continue
  found=[]
  for name,raw in files.items():
   try:r=script_record(raw,id)
   except (ValueError,struct.error) as e:r={'parse_note':str(e)}
   if r:
    for row in r.get('commands',[]):row['native_handler']=handlers.get(row['opcode'])
    found.append({'file':name,**r})
  scripts[str(id)]=found
 cases=[]
 for count in (1,2,3,6):
  m=native_fixture(data,[0]*count+[100]);m.run()
  assert len(m.launched)==1 and m.launched[0]['actor']==100
  assert m.coins==[100] and m.drops==[100] and m.r(0x5998c4)==5
  assert all(m.r(m.attr(h,0xb))==40 for h in m.heroes)
  assert sum(bool(m.r(o+0x28)&4) for o in m.enemies)==1 and not m.advanced
  for _ in range(count-1):m.run()
  assert len(m.launched)==count and len(m.coins)==count and len(m.drops)==count
  assert m.r(0x5998c4)==5*count
  assert all(m.r(m.attr(h,0xb))==20+sum(2*(10+i) for i in range(count)) for h in m.heroes)
  m.run();assert len(m.launched)==count and m.advanced==[1]
  cases.append({'newly_dead':count,'first_call_launches':1,'calls_to_launch_all':count,'coins_and_drops_once_per_enemy':True,'parent_advances_only_on_final_scan':True})
 m=native_fixture(data,[100,0,100,0]);m.run();assert m.launched==[{'actor':110,'script':0x619}]
 cases.append({'mixed_alive_dead':'first newly dead only, alive skipped'})
 m=native_fixture(data,[0,0],already={0});m.run();assert m.launched==[{'actor':110,'script':0x619}] and m.coins==[110]
 cases.append({'already_processed_with_FX_lock':'no duplicate reward; next new death only'})
 m=native_fixture(data,[0],[0xefff]);m.run();assert m.launched[0]['script']==8000
 cases.append({'default_script':'EFFf converted to8000'})
 m=native_fixture(data,[0]);m.run(1);assert not m.launched and not m.coins
 cases.append({'party_side':'separate list; enemy not processed by party-side scan'})
 supported=[];excluded=[]
 for id,rows in scripts.items():
  if len(rows)!=1:excluded.append(int(id));continue
  row=rows[0];cmd=row.get('commands',[]);seq=[x['opcode'] for x in cmd]
  body=cmd[1:-1]
  if body and body[0]['opcode']=='0x7f002038' and len(body[0]['args'])==1:body=body[1:]
  ok=(not row.get('parse_note') and seq[-1:] == ['0x7f00ffff'] and
      [x['opcode'] for x in body]==['0x7f002049','0x7f002011','0x7f00204a'] and
      body[0]['args']==[3,0x7eff1000,0,0,0,7,0] and body[1]['args']==[0x7eff1000,0,1] and body[2]['args']==[])
  (supported if ok else excluded).append(int(id))
 assert len(supported)==60 and set(excluded)=={1337,1527}
 covered=sum(n for id,n in counts.items() if id in supported or id==0xefff)
 result={'status':'research only; no patch or live game attachment','exe_sha1':BASE,'native_function_comparison':ranges,
  'opcode_handlers':{k:handlers[k] for k in ('0x7f00200c','0x7f00200d','0x7f002011','0x7f002038','0x7f002049','0x7f00204a')},
  'monster_B6_assignments':assignments,'death_script_counts':dict(counts),'death_scripts':scripts,'native_replay_cases':cases,
  'parallel_template_research':{'compatible_script_ids':supported,'excluded_script_ids':excluded,'matching_B6_assignments_including_native_default':covered,'total_B6_assignments':len(assignments),'meaning':'pattern coverage of static data, not implemented or gameplay coverage'},
  'post_action_driver_examples':{str(id):script_record(files['gitem.dat'],id) for id in (1600,1601,1602,1640)},
  'presentation_contract':{'spawn':'EE540 side3 resolves explicit actor, queues F3540 effect7, sets object+28 bit1B','hide':'EEBD0 actor, flag0,1; native flag2 remains death state','wait':'opcode204A/E9490 waits for0059C510 effects list to empty','release':'E45D0 asksF4D10(owner) and clears1B when no owner effect remains','audio':'F3280 ->C5490 ->A7DB0 halts/frees matching sound ID before8E3B0 plays; same-ID batch replay would restart, distinct IDs can be started same frame'},
  'resource_sha256':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items() if name in {'gmon.dat','gitem.dat'} or any(item.get('file')==name for rows in scripts.values() for item in rows)},
  'confirmed':'EC840 marks/rewards one new death, calls its B6 script and returns; next death waits for script resumption. E92E0 is shared sound opcode2038, CB3D0 is general script dispatcher, not a death-only queue.',
  'limitations':'Synthetic lists/HP; actual list traversal, bit operations and EC840 arithmetic execute in Unicorn. Script startup, coin/drop APIs and presentation lifetime are bounded stubs. No claim of actual battle timing or sound playback. No parallel implementation yet.'}
 assert (ROOT/'NewPAL_Release.exe').read_bytes()==data
 out=ROOT/'补丁工作仓库/候选版本/group-death-research-v1.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':result['status'],'native_cases':len(cases),'template_scripts':len(supported),'excluded_scripts':excluded,
  'matching_assignments':covered,'total_assignments':len(assignments),'kept_historical_UAF_fix':True,'output':str(out)},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
