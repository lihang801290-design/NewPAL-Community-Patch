"""Full legacy event replay plus exhaustive input-family transition checks."""
import sys,json,hashlib
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
import flash_v4 as pe
import joystick_compat_v1 as fix
import audit_akey_history_20261101 as history

source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=fix.candidate(source)
event_cases=[]
for route in ('controller','joystick'):
 for button in (0,1):
  for early in (False,True):
   old=history.replay(source,route,button,early);new=history.replay(out,route,button,early)
   if route=='joystick':assert new['total']==1,(route,button,early,new)
   else:assert old==new,('legacy controller path changed',old,new)
   event_cases.append({'before':old,'after':new})
   old_repeat=history.replay(source,route,button,early,repeat_press=True)
   new_repeat=history.replay(out,route,button,early,repeat_press=True)
   if route=='joystick':assert new_repeat['second_press_total']==1,(route,button,early,new_repeat)
   else:assert old_repeat==new_repeat
   event_cases.append({'before':old_repeat,'after':new_repeat})

def transition(data,mode,old,new,obj=0x580b38):
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x300000);u.mem_map(0x800000,0x10000)
 for _,vs,rva,rs,rp in pe.pe_info(data)[2]:u.mem_write(0x400000+rva,data[rp:rp+rs])
 def w(a,v):u.mem_write(a,pe.u32(v))
 w(0x581280,0x804000);w(0x804120,1);w(obj+0x150,mode);w(obj+0x6ac,old)
 u.mem_write(obj+0x15c,bytes([1])*0x500)
 u.mem_write(0x50aece,bytes.fromhex('55 8b ec 57 51 8b 7d 08 8b 45 0c 8b 4d 10 fc f3 aa 8b 45 08 59 5f 5d c3'))
 resets=[]
 u.hook_add(UC_HOOK_CODE,lambda uc,pc,size,_:resets.append(pc) if pc==0x4a8210 else None)
 sp=0x80e000;w(sp,0x80f000);w(sp+4,new)
 regs={UC_X86_REG_ESP:sp,UC_X86_REG_EBP:0x80d000,UC_X86_REG_ECX:obj,
  UC_X86_REG_EBX:0x12345678,UC_X86_REG_ESI:0x87654321,UC_X86_REG_EDI:0xabcdef12}
 for r,v in regs.items():u.reg_write(r,v)
 u.emu_start(0x4adf60,0x80f000,count=10000)
 for r in (UC_X86_REG_EBP,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI):assert u.reg_read(r)==regs[r]
 assert u.reg_read(UC_X86_REG_ESP)==sp+8
 target=1 if data is out and obj==0x580b38 and mode==1 and new in (1,3,4) else new
 assert int.from_bytes(u.mem_read(obj+0x6ac,4),'little')==target
 return bytes(u.mem_read(obj+0x15c,0x500)),len(resets)

transitions=0;preserved=0
for obj in (0x580b38,0x805000):
 for mode in (0,1,2):
  for old in range(5):
   for new in range(5):
    before=transition(source,mode,old,new,obj);after=transition(out,mode,old,new,obj)
    guarded=obj==0x580b38 and mode==1 and old in (1,3,4) and new in (1,3,4)
    if guarded:
     assert after==(bytes([1])*0x500,0);preserved+=1
    else:assert after==before,(obj,mode,old,new)
    transitions+=1
# Legacy A override, B entry/trampoline and joystick first-deflection patches
# are all retained; the rejected global A-release replacement is absent.
for rva,size in [(0xae3ca,2),(0xa9566,6),(0xbfd58,28),(0xa89ac,2),(0xa8a57,2),(0xa8bea,2),(0xa8c95,2)]:
 off=pe.rva_offset(source,rva);assert out[off:off+size]==source[off:off+size]
report={'status':'passed','full_event_cases':event_cases,'source_transition_cases':transitions,
 'same_family_preserve_cases':preserved,'target_sha1':hashlib.sha1(out).hexdigest(),
 'scope':'generic A/B early/late; legacy controller behavior unchanged; source family1/3/4 continuity; keyboard/mouse/other input objects unchanged; no firmware or LED calls',
 'limits':'Existing standard-controller legacy release-clearing behavior, including its unread-fast-tap limitation, deliberately unchanged. Physical firmware modes not simulated.'}
(pe.ROOT/'补丁工作仓库/候选版本/joystick-compat-v1-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='full_event_cases'},indent=2))
