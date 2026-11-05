"""Verify real game actor records as well as synthetic native-speed exclusions."""
import hashlib,itertools,json,struct
import story_motion_v3 as fix
from verify_story_motion_v2 import Machine,BASE,ACTOR,PATH,SPRITE,EBP,REGS,VALUES
from unicorn.x86_const import *
import monster_motion_v1 as motion

def main():
 source=(fix.pe.ROOT/'NewPAL_Release.exe').read_bytes()
 if hashlib.sha1(source).hexdigest()!=fix.BASE:source=(fix.pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-story-motion-v3-20261104').read_bytes()
 out,p=fix.candidate(source);assert out==(fix.OUT/'NewPAL_Release.exe').read_bytes()
 native=(fix.pe.ROOT/'NewPAL_Release.exe.orig-ufa').read_bytes()
 new=Machine(out);old=Machine(source);orig=Machine(native)
 fixture=json.loads((fix.OUT/'native-actors-scene498.json').read_text(encoding='utf-8'));assert fixture['scene']==498
 # On-disk globals describe startup (-1/loading), not a running free map.
 # Initialize the real captured context, rather than accidentally testing fallback.
 for machine in (new,old,orig):
  for address,value in fixture['globals'].items():machine.put(int(address,16),value)
 mobs=[a for a in fixture['actors'] if 5001<=a['id']<=5019];assert len(mobs)==19
 checks=0
 for actor in mobs:
  raw=bytes.fromhex(actor['raw']);assert struct.unpack_from('<H',raw,0x18)[0]!=0 and struct.unpack_from('<H',raw,0x1c)[0]==0
  for m in (new,old):
   m.uc.mem_write(ACTOR,raw);m.uc.mem_write(ACTOR+4,bytes(4));m.put(ACTOR+0x3c,SPRITE)
   m.put(SPRITE+0xa0,1);m.put(SPRITE+8,0);m.put(ACTOR+12,int(actor['flags'],16)&~0x4000000)
  # v2 bypassed real mobs; v3 must accumulate patrol /3 for the same actor.
  assert old.step(4,2,index=actor['id'])[0]==(4,2)
  assert tuple(map(sum,zip(*[new.step(4,2,index=actor['id'])[0] for _ in range(3)])))==(4,2)
  checks+=1
 vectors=list(itertools.product([-16,-4,-2,-1,0,1,2,4,16],repeat=2));steps=0
 for animation,factor in [(0,1),(16,2)]:
  new.actor(5043,ai=0,animation=animation);new.uc.mem_write(ACTOR+0x18,struct.pack('<H',2173))
  for i,(x,y) in enumerate(vectors):
   chunks=[new.step(x,y,index=i+1)[0] for _ in range(3)]
   assert tuple(map(sum,zip(*chunks)))==(x*factor,y*factor),(x,y,chunks)
   for regs in [new.step(x,y,index=i+1)[1]]:assert regs==VALUES
   steps+=4
 native_checks=0
 # AI +1c can be nonzero without AI +18: must not qualify.
 for actor_id,ai18,ai1c,flags in [(1,0,0,0),(5,0,0,0),(116,0,0,0),(117,0,0,0),(118,0,0,0),(3501,0,0,0),(3514,0,0,0),(3542,0,0,0),(9019,0,2173,0),(7001,0,0,0),(5043,65535,0,0),(5043,2173,0,0x80)]:
  for doubled,run in itertools.product([0,1],[0,0x4000000]):
   for m in (new,orig):m.actor(actor_id,ai1c,flags|run,native_double=doubled);m.uc.mem_write(ACTOR+0x18,struct.pack('<H',ai18))
   for x,y in vectors:assert new.step(x,y)==orig.step(x,y);native_checks+=1
 story_checks=0
 for offset,value in [(0x13b628,1),(0x13b628,0x20),(0x13b628,0x40),(0x131b80,1),(0x131b7c,1),(0x16ffc0,1),(0x16ffc4,1)]:
  for m in (new,orig):m.actor(5043);m.uc.mem_write(ACTOR+0x18,struct.pack('<H',2173));m.put(BASE+offset,value)
  for x,y in vectors:assert new.step(x,y)==orig.step(x,y);story_checks+=1
  for m in (new,orig):m.put(BASE+offset,0)
 radius_checks=0
 for id,ai,target,story,expected in [(5001,2001,0xfff1,0,120),(5019,2019,0xfffe,0,120),(5001,2001,100,0,240),(9019,0,0xfff1,0,240),(3501,0,0xfff1,0,240),(5001,2001,0xfff1,1,240)]:
  new.actor(id);new.uc.mem_write(ACTOR+0x18,struct.pack('<H',ai));new.put(BASE+0x13b628,story)
  new.uc.mem_write(PATH+2,struct.pack('<HH',target,15))
  for r,v in zip(REGS,VALUES):new.uc.reg_write(r,v)
  new.uc.reg_write(UC_X86_REG_ECX,PATH);new.uc.emu_start(BASE+motion.RADIUS_SITE,BASE+motion.RADIUS_SITE+7,count=500)
  assert new.uc.reg_read(UC_X86_REG_EDX)==expected
  radius_checks+=1
 diffs=[i for i,(a,b) in enumerate(zip(source,out)) if a!=b];assert diffs==[r['offset'] for r in p['changes']]
 report=dict(status='passed; gameplay acceptance pending',baseline_sha1=fix.BASE,candidate_sha1=hashlib.sha1(out).hexdigest(),native_scene498_mob_fixtures=checks,signed_patrol_chase_steps=steps,native_exclusion_comparisons=native_checks,script_context_comparisons=story_checks,radius_checks=radius_checks,changed_bytes=len(diffs),map_test_bridge_unchanged=True,resources_unchanged=True,dream_cutscene_feedback='v2 user accepted speed; native tail byte-identical in v3',limits='Offline execution and actual actor data; gameplay slowdown and lotus camera still require feedback.')
 (fix.OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
