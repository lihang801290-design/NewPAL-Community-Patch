"""Run the actual installed hook against native x86, without touching a game."""
import hashlib,itertools,json,struct,sys
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
import story_motion_v2 as fix
import monster_motion_v1 as motion

BASE=0x400000;SCRATCH=0x8000000
ACTOR=SCRATCH;PATH=SCRATCH+0x1000;SPRITE=SCRATCH+0x2000;EBP=SCRATCH+0xd000
REGS=[UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EFLAGS]
VALUES=[0x12345678,0x23456789,0x3456789a,0x456789ab,SCRATCH+0xf000,EBP,0x56789abc,0x6789abcd,0x246]

class Machine:
 def __init__(self,data):
  self.uc=Uc(UC_ARCH_X86,UC_MODE_32)
  sections=fix.pe.pe_info(data)[2];end=max(s[2]+max(s[1],s[3]) for s in sections)
  self.uc.mem_map(BASE,(end+0xfff)&~0xfff);self.uc.mem_map(SCRATCH,0x10000)
  for _,vs,va,rs,rp in sections:self.uc.mem_write(BASE+va,data[rp:rp+rs])
  self.put(EBP-0x14,ACTOR);self.put(EBP-0x1c,PATH);self.put(EBP-8,1);self.put(EBP-4,ACTOR)
  self.put(ACTOR+0x3c,SPRITE);self.put(PATH+4,0x02000400)
 def put(self,p,v):self.uc.mem_write(p,struct.pack('<I',v))
 def words(self,p,*v):self.uc.mem_write(p,struct.pack('<'+'h'*len(v),*v))
 def actor(self,actor_id,ai=0,flags=0,animation=0,native_double=1):
  self.uc.mem_write(ACTOR+0x20,struct.pack('<H',actor_id));self.uc.mem_write(ACTOR+0x1c,struct.pack('<H',ai))
  self.put(ACTOR+0xc,flags);self.put(SPRITE+8,animation);self.put(SPRITE+0xa0,native_double)
 def step(self,x,y,index=0):
  self.words(PATH+0x16,x,y);self.uc.mem_write(PATH+2,struct.pack('<H',index))
  for r,v in zip(REGS,VALUES):self.uc.reg_write(r,v)
  self.uc.emu_start(BASE+motion.SITE,BASE+fix.TAIL_END,count=2000)
  assert self.uc.reg_read(UC_X86_REG_EIP)==BASE+fix.TAIL_END
  return (struct.unpack('<i',self.uc.mem_read(EBP-0x24,4))[0],struct.unpack('<i',self.uc.mem_read(EBP-0x2c,4))[0]),[self.uc.reg_read(r) for r in REGS]

def main():
 source=(fix.pe.ROOT/'NewPAL_Release.exe').read_bytes()
 if hashlib.sha1(source).hexdigest()!=fix.BASE:
  source=(fix.pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-story-motion-v2-20261104').read_bytes()
 out,plan=fix.candidate(source);assert (fix.OUT/'NewPAL_Release.exe').read_bytes()==out
 native=(fix.pe.ROOT/'NewPAL_Release.exe.orig-ufa').read_bytes()
 new=Machine(out);orig=Machine(native);old=Machine(source)
 vectors=list(itertools.product([-16,-4,-2,-1,0,1,2,4,16],repeat=2))
 actors=[(1,0),(3,0),(5,0),(116,0),(117,0),(118,0),(3501,0),(3514,0),(3542,0),(7001,0),(9019,0),(5043,0),(5043,65535),(5043,2173)]
 checks=0
 for actor_id,ai in actors:
  # The final case verifies native follower exclusion even with an AI script.
  follower=0x80 if ai==2173 else 0
  for doubled,run in itertools.product([0,1],[0,0x4000000]):
   for m in (new,orig):m.actor(actor_id,ai,follower|run,native_double=doubled)
   for x,y in vectors:
    a=new.step(x,y);b=orig.step(x,y);assert a==b,(actor_id,ai,doubled,run,x,y,a,b)
    checks+=1
 old.actor(1);orig.actor(1);new.actor(1)
 example=dict(raw=[4,2],old=old.step(4,2)[0],native=orig.step(4,2)[0],fixed=new.step(4,2)[0])
 assert example['old']!=example['native'] and example['fixed']==example['native']
 # Global scripted scenes bypass ordinary AI slowdown as well.
 story_checks=0
 for offset,value in [(0x13b628,1),(0x13b628,0x20),(0x13b628,0x40),(0x131b80,1),(0x131b7c,1),(0x16ffc0,1),(0x16ffc4,1)]:
  for m in (new,orig):m.actor(5043,2173);m.put(BASE+offset,value)
  for x,y in vectors:
   assert new.step(x,y)==orig.step(x,y);story_checks+=1
  for m in (new,orig):m.put(BASE+offset,0)
 # Keep fractional patrol/chase speed and the small-vector direction intact.
 slow_checks=0
 for animation,factor in [(0,1),(16,2)]:
  new.actor(5043,2173,animation=animation)
  for i,(x,y) in enumerate(vectors):
   chunks=[new.step(x,y,index=i+1)[0] for _ in range(3)]
   assert tuple(map(sum,zip(*chunks)))==(x*factor,y*factor),(x,y,chunks)
   slow_checks+=3
 # Recovery from old fractional positions remains bounded to the next grid.
 recovery=[((1641,649),(4,4),(1648,656)),((638,1065),(-4,4),(624,1072)),((640,219),(4,2),(640,224)),((640,219),(-4,2),(640,224))]
 new.actor(5043,2173)
 for i,(start,raw,target) in enumerate(recovery):
  position=list(start);new.uc.mem_write(ACTOR+4,struct.pack('<HH',*position))
  for tick in range(100):
   dx,dy=new.step(*raw,index=500+i)[0];position[0]+=dx;position[1]+=dy
   new.uc.mem_write(ACTOR+4,struct.pack('<HH',*position))
   if tuple(position)==target:break
  assert tuple(position)==target,(start,position,target)
 radius_checks=0
 for actor_id,ai,flags,story,target,expected in [(5043,2173,0,0,0xfff1,120),(5043,2173,0,0,0xfffe,120),(5043,2173,0,0,100,240),(5043,0,0,0,0xfff1,240),(9019,0,0,0,0xfff1,240),(5043,2173,0x80,0,0xfff1,240),(5043,2173,0,1,0xfff1,240),(116,0,0,0,0xfff1,240)]:
  new.actor(actor_id,ai,flags);new.put(BASE+0x13b628,story)
  new.uc.mem_write(PATH+2,struct.pack('<HH',target,15))
  for r,v in zip(REGS,VALUES):new.uc.reg_write(r,v)
  new.uc.reg_write(UC_X86_REG_ECX,PATH)
  new.uc.emu_start(BASE+motion.RADIUS_SITE,BASE+motion.RADIUS_SITE+7,count=500)
  assert new.uc.reg_read(UC_X86_REG_EDX)==expected
  assert new.uc.reg_read(UC_X86_REG_EAX)==VALUES[0] and new.uc.reg_read(UC_X86_REG_ESP)==VALUES[4]
  radius_checks+=1
 allowed=[(c['offset'],c['offset']+c['size']) for c in plan['changes']]
 changes=[i for i,(a,b) in enumerate(zip(source,out)) if a!=b]
 assert len(source)==len(out) and all(any(lo<=i<hi for lo,hi in allowed) for i in changes)
 assert source[fix.pe.rva_offset(source,0x739a0):fix.pe.rva_offset(source,0x739a0)+128]==out[fix.pe.rva_offset(out,0x739a0):fix.pe.rva_offset(out,0x739a0)+128]
 report=dict(status='passed; gameplay acceptance pending',baseline_sha1=fix.BASE,candidate_sha1=hashlib.sha1(out).hexdigest(),native_actor_register_comparisons=checks,scripted_context_comparisons=story_checks,slow_fractional_steps=slow_checks,recovery_cases=len(recovery),radius_cases=radius_checks,example=example,map_test_bridge_unchanged=True,resources_unchanged=True,changed_bytes=len(changes),limits='Offline x86 instruction checks; lotus camera recovery and native scripted gameplay need a clean-save retest.')
 (fix.OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':main()
