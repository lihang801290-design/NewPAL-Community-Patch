"""Execute the candidate with native death/rewards, template validation and FX APIs."""
import hashlib,json,struct
import flash_v4 as pe
import group_death_v1 as fix
from research_group_death_v1 import native_fixture,script_record
from unicorn.x86_const import *

source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();candidate,plan=fix.candidate(source);st=plan['state'];checks=[]
raw=(pe.ROOT/'gitem.dat').read_bytes();rows=fix.templates()

def fixture(hps,scripts=None,already=None,corrupt=None):
 m=native_fixture(candidate,hps,scripts,already);m.fx=[];m.sounds=[];m.cache={}
 def restore(addr,size):
  m.hooks.pop(addr,None);off=pe.rva_offset(candidate,addr-0x400000);m.u.mem_write(addr,candidate[off:off+size])
 restore(0x4de7f0,0xe0);m.w(0x59bf4c,0x830000)
 for i,obj in enumerate(m.enemies):
  m.w(obj+4,3);sprite=0x930000+i*0x100;m.w(obj+0x70,sprite);m.w(sprite,1)
 for i,(id,sound,commands) in enumerate(rows+[(1602,-1,[b'parent fixture'])]):
  base=0x8c0000+i*0x1000;lst=base+0x40;m.w(base+8,lst);m.w(lst,base+0x100);m.w(lst+4,len(commands))
  for j,command in enumerate(commands):
   node=base+0x100+j*0x20;buf=base+0x500+j*0x60
   m.w(node,len(command));m.w(node+4,buf);m.w(node+0x10,node+0x20 if j+1<len(commands) else 0);m.u.mem_write(buf,command)
  m.cache[id]=base
  if id==corrupt:m.u.mem_write(base+0x500+4,b'\x00')
 m.w(0x531b88,1602);m.w(0x531bc0,2000);m.w(0x59c510,0x960000);m.w(0x960004,0)
 m.stub(0x4cb7c0,lambda:m.cache.get(m.arg(0),0))
 # Use real EE540 and EEBD0; only sprite decoding, allocation and resource lookup
 # are replaced. Each fake F3540 instance models one native asynchronous effect.
 def targets():
  id=m.r(m.arg(0));obj=next((o for o in m.enemies if m.r(o)==id),0)
  if not obj:return 0
  idx=m.enemies.index(obj);lst=0x920000+idx*0x80;node=0x922000+idx*0x20
  m.w(lst,node);m.w(lst+4,1);m.w(lst+8,0);m.w(lst+12,node);m.w(node+4,obj);return lst
 m.stub(0x4eb250,targets);m.stub(0x4eadb0,lambda:0)
 # Synthetic target lists have no native allocator/vtable. Model their cleanup;
 # the deleting destructor is thiscall and pops its one explicit argument.
 m.stub(0x4cc740,lambda:0);m.stub(0x4b0240,lambda:0)
 m.u.mem_write(0x4b0240,b'\xc2\x04\x00')
 def decode():m.w(m.arg(1),2010);m.w(m.arg(2),0x24);return 0
 m.stub(0x4cec50,decode)
 def effect():
  id=m.arg(0);assert m.arg(5)==7
  address=0x940000+len(m.fx)*0x1000;m.fx.append(id);m.w(0x960004,len(m.fx));return address
 m.stub(0x4f3540,effect);m.stub(0x4f3280,lambda:m.sounds.append(m.arg(0)) or 0)
 def invoke(continuation=1600,side=0):
  sp=0x9ef000;m.w(sp,0x9ff000);m.w(sp+4,side);m.w(sp+8,continuation)
  regs={UC_X86_REG_EAX:91,UC_X86_REG_EBX:123,UC_X86_REG_ECX:92,UC_X86_REG_EDX:93,UC_X86_REG_ESI:234,UC_X86_REG_EDI:345,UC_X86_REG_EBP:0x9ed000}
  for r,v in regs.items():m.u.reg_write(r,v)
  m.u.reg_write(UC_X86_REG_ESP,sp);m.u.reg_write(UC_X86_REG_EFLAGS,0x246)
  try:m.u.emu_start(plan['symbols']['entry'],0x9ff000,count=100000)
  except Exception:
   print('failed EIP/ESP:',hex(m.u.reg_read(UC_X86_REG_EIP)),hex(m.u.reg_read(UC_X86_REG_ESP)))
   raise
  assert m.u.reg_read(UC_X86_REG_EIP)==0x9ff000 and m.u.reg_read(UC_X86_REG_ESP)==sp+4
  assert all(m.u.reg_read(r)==v for r,v in regs.items())
  assert m.u.reg_read(UC_X86_REG_EFLAGS)==0x246
 def finish():
  m.w(0x960004,0)
  for obj in m.enemies:m.w(obj+0x28,m.r(obj+0x28)&~(1<<27))
 m.invoke=invoke;m.finish=finish
 return m

def reward_state(m):return {'coins':m.coins,'drops':m.drops,'money':m.r(0x5998c4),'xp':[m.r(m.attr(h,0xb)) for h in m.heroes],'drop_queue_size':m.r(0x599918)}

for n in (2,3,6,16):
 for surviving in (False,True):
  for ids in ([1504]*n,[1504 if i%2 else 1509 for i in range(n)],[0xefff]*n):
   hps=[0]*n+([100] if surviving and n<16 else []);scripts=ids+([1504] if len(hps)>n else [])
   m=fixture(hps,scripts);m.invoke()
   assert m.fx==[100+i*10 for i in range(n)],m.fx
   assert m.r(st['mode'])==2 and m.r(st['objects'])==n and not m.launched
   assert m.r(0x531b88)==1602 and m.r(0x531bc0)==2000
   assert m.r(0x599814)==2 and not m.advanced and m.r(0x59937c)&1
   expected_sounds=[]
   for id in ids:
    sound=next((s for sid,s,_ in rows if sid==(8000 if id==0xefff else id)),None)
    if sound!=0xffffffff and sound not in expected_sounds:expected_sounds.append(sound)
   assert m.sounds==expected_sounds
   baseline=native_fixture(source,hps,scripts)
   for i in range(n):baseline.run()
   assert reward_state(m)==reward_state(baseline),(reward_state(m),reward_state(baseline))
   rewards=reward_state(m)
   for _ in range(4):m.invoke();assert reward_state(m)==rewards and len(m.fx)==n and not m.advanced
   m.finish();m.invoke()
   assert m.r(st['mode'])==0 and reward_state(m)==rewards and m.advanced==[1]
   assert m.r(0x599814)==(2 if surviving and n<16 else 4)
   checks.append({'new_deaths':n,'survivor':bool(surviving and n<16),'scripts':ids[:3],'same_frame_fx':n,'same_sound_deduplicated':True,'native_rewards_equal':True,'wait_no_repeat_or_early_victory':True})

# Every template validates loaded record count/size/payload and runs as a group.
for id,sound,commands in rows:
 m=fixture([0,0],[id,id]);m.invoke();assert m.fx==[100,110] and m.r(st['mode'])==2
 checks.append({'supported_template':id})

for label,hps,scripts,kwargs in [
 ('single',[0,100],[1504,1504],{}),('mixed_special',[0,0],[1504,1337],{}),
 ('extended_special',[0,0],[1504,1527],{}),('unknown',[0,0],[1504,9999],{}),
 ('modified_loaded_script',[0,0],[1504,1504],{'corrupt':1504}),
 ('already_processed',[0,0],[1504,1504],{'already':{0}}),
 ('oversized',[0]*17,[1504]*17,{})]:
 m=fixture(hps,scripts,**kwargs);m.invoke();assert not m.fx and m.r(st['mode'])==0
 assert len(m.launched)==1 and not m.advanced
 checks.append({'native_fallback':label})

m=fixture([0,0],[1504,1504]);m.invoke(continuation=9999);assert not m.fx and m.launched
checks.append({'native_fallback':'nonstandard_continuation'})
m=fixture([0,0],[1504,1504]);m.w(0x960004,1);m.invoke();assert not m.fx and m.launched
checks.append({'native_fallback':'existing_other_effect'})
m=fixture([0,0],[1504,1504]);m.w(m.enemies[1]+0x70,0);m.invoke();assert not m.fx and m.launched
checks.append({'native_fallback':'missing_sprite'})
m=fixture([0,0],[1504,1504]);m.invoke(side=1);assert not m.fx and not m.coins
checks.append({'party_side_unchanged':True})
m=fixture([0,0],[1504,1504]);m.invoke();rewards=reward_state(m);m.invoke(side=1)
assert m.r(st['mode'])==2 and reward_state(m)==rewards and len(m.fx)==2
checks.append({'party_side_during_enemy_batch_unchanged':True})

# Actual opcode wrapper still calls its native parser and cleans stack correctly.
m=fixture([0,0],[1504,1504]);m.stub(0x4f87d0,lambda:1600)
sp=0x9ef000;m.w(sp,0x9ff000);m.w(sp+4,0x850000);m.u.reg_write(UC_X86_REG_ESP,sp);m.u.reg_write(UC_X86_REG_EBP,0x9ed000)
m.u.emu_start(0x4e6d00,0x9ff000,count=100000);assert m.fx==[100,110] and m.u.reg_read(UC_X86_REG_ESP)==sp+4
checks.append({'original_enemy_opcode_wrapper':'passed'})

# New battle reset chains to the existing initialization hook, preserving registers.
m=fixture([0,0],[1504,1504]);m.w(st['mode'],2);sp=0x9ef000;m.w(sp,0x9ff000);m.u.reg_write(UC_X86_REG_ESP,sp)
m.u.reg_write(UC_X86_REG_EAX,123);m.u.reg_write(UC_X86_REG_EFLAGS,0x246)
m.u.emu_start(0x4d07a0,plan['reset_target'],count=100)
assert m.r(st['mode'])==0 and m.u.reg_read(UC_X86_REG_EAX)==123 and m.u.reg_read(UC_X86_REG_EFLAGS)==0x246
checks.append({'battle_reset_preserves_prior_hook':True})

# No old payload overwritten; only3 guarded CALL/JMP sites and PE size fields differ.
h,o,sections=pe.pe_info(source);last=sections[-1];assert candidate[last[4]:last[4]+last[3]]==source[last[4]:]
allowed=set()
for site,(old,new) in plan['patches'].items():
 off=pe.rva_offset(source,site);allowed.update(range(off,off+len(new)))
hdr=o+struct.unpack_from('<H',source,h+20)[0]+(len(sections)-1)*40
for off in (o+4,o+56,o+64,hdr+8,hdr+16):allowed.update(range(off,off+4))
assert all(x==y or i in allowed for i,(x,y) in enumerate(zip(source,candidate)))
assert candidate[pe.rva_offset(candidate,0xecb90):][:9]==source[pe.rva_offset(source,0xecb90):][:9]
assert (pe.ROOT/'NewPAL_Release.exe').read_bytes()==source
out=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.group-death-v1.exe';out.write_bytes(candidate)
report={'status':'passed; gameplay acceptance pending','baseline_sha1':fix.BASE,'candidate_sha1':hashlib.sha1(candidate).hexdigest(),'cases':len(checks),'details':checks,
 'native_scope':'Actual EC840/list/flags/XP/money-addition/drop queue and victory scan, actual EE540/EEBD0; sprite decode, resource cache, temporary-list cleanup, FX allocation/timing, removal, coin/drop APIs and sound device are bounded stubs. Runtime loaded script records are compared byte-for-byte. No live game attachment or file install.',
 'retained':'All accepted v4 payload bytes; old UAF9-byte skip; existing battle-init hook chain; actor/parent context; sound dedup only this batch'}
(pe.ROOT/'补丁工作仓库/候选版本/group-death-v1-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=True,indent=2))
