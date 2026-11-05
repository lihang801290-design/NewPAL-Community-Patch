"""Only the three changed ratio immediates and affected co-op outputs."""
import json,hashlib,math
import flash_v4 as pe
import four_features_v9 as fix
from native_damage_harness import Machine

data,previous,offset=fix.candidate()
assert len(data)==len(previous)
assert {i for i,(a,b) in enumerate(zip(data,previous)) if a!=b}=={offset+5}
cases=[]
for stats in ([(40,30,8),(35,55,8),(50,25,9)],[(120,80,20),(60,170,19),(150,60,21)],[(300,220,45),(170,400,44),(360,200,46)]):
 for n in (2,3):
  for roll in (0,5,9):
   m=Machine(data);roles,enemy=m.party(stats[:n]);m.attr(enemy,0x29,-10);m.attr(enemy,0x35,3)
   for role,id,cls in zip(roles,(2000,2002,2003),(0,4,5)):m.w(role,id);m.attr(role,0xfe,cls)
   m.stub(0x4dd8b0,lambda:m.attr(m.arg(0),0xfe));m.stub(0x4ddea0,lambda:m.arg(0))
   total=0
   for (a,s,l),cls in zip(stats[:n],(0,4,5)):
    core=math.ceil(a*25*110/(1800*3))
    total+=core*40//100+6 if cls==4 else core*36//100+6 if cls==5 else core+core//20+1
   growth=sum((a+s)//6+2*l for a,s,l in stats[:n])
   original=m.damage(roles[0],enemy,31,roll,False)
   expected=max(original,(29*total+19)//20+min(growth//8,(total+9)//10))
   result=m.damage(roles[0],enemy,31,roll)
   assert result==expected
   cases.append({'n':n,'level':stats[0][2],'roll':roll,'result':result})
# Regression of the user's original two-person incident, not a balance baseline.
m=Machine(data);stats=[(286,254,11),(235,194,10)];roles,enemy=m.party(stats)
m.w(roles[1],2002);m.attr(roles[0],0xfe,0);m.attr(roles[1],0xfe,4)
m.attr(enemy,0x29,-10);m.attr(enemy,0x35,3)
m.stub(0x4dd8b0,lambda:m.attr(m.arg(0),0xfe));m.stub(0x4ddea0,lambda:m.arg(0))
replay=m.damage(roles[0],enemy,31,5);assert 315<=replay<=330,replay
# Requested confirmation: execute the native HP/MP growth merge at cap9999.
from unicorn.x86_const import *
cap_cases=0
for id in (0x11,0x17):
 for maximum,current,delta in ((1006,990,20),(9999,9990,60),(12000,11000,1),(500,400,5)):
  m=Machine(data);src=0x850000;dst=0x851000
  m.attr(src,id,delta);m.attr(dst,id,current);m.attr(dst,id-1,maximum)
  m.stub(0x4ddd90,lambda:m.attrs.get((m.arg(0),m.arg(1)),0))
  sp=0x9ef000;m.w(sp,0x9ff000);m.w(sp+4,src);m.w(sp+8,dst);m.w(sp+12,id)
  m.u.reg_write(UC_X86_REG_ESP,sp);m.u.reg_write(UC_X86_REG_EBP,0x9ed000)
  m.u.emu_start(0x4d89f0,0x9ff000,count=2000)
  assert m.u.reg_read(UC_X86_REG_EIP)==0x9ff000
  assert m.r(m.attr(dst,id-1))==min(maximum,9999)
  assert m.r(m.attr(dst,id))==min(current+delta,maximum,9999)
  cap_cases+=1
for rva in (0xd8a8b,0xd8a96):assert data[pe.rva_offset(data,rva):pe.rva_offset(data,rva)+4]==pe.u32(9999)

folder=pe.ROOT/'补丁工作仓库/候选版本';(folder/'NewPAL_Release.four-features-v9.exe').write_bytes(data)
report={'status':'passed; gameplay acceptance pending','candidate_sha1':hashlib.sha1(data).hexdigest(),
 'changed_bytes':1,'native_hp_mp_cap_cases':cap_cases,'native_affected_cases':len(cases),'incident_replay':{'observed_normals':[149,50],'previous_replay':302,'new_replay':replay},
 'scope':'only co-op ratio1.35->1.45 changed; original move floor, bounded mixed-stat/level bonus and all other bytes retained'}
(folder/'four-features-v9-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
