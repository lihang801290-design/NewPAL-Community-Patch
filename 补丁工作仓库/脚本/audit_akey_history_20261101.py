"""Audit historical A backups and replay the complete legacy event path."""
import sys,json,hashlib
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
import flash_v4 as pe

root=pe.ROOT
before_names=['NewPAL_Release.exe.preAkey_bak_20261006_125129.exe','NewPAL_Release.exe.preAkey_bak_20261006_125312.exe','NewPAL_Release.exe.preAkey_bak_20261006_190503.exe']
before=[(root/'修改exe备份'/n).read_bytes() for n in before_names]
assert before[0]==before[1]==before[2]
after=(root/'修改exe备份/NewPAL_Release.exe.preSpeed_bak_20261006_205628.exe').read_bytes()
changed=[i for i,(x,y) in enumerate(zip(before[0],after)) if x!=y]
assert len(before[0])==len(after) and changed==[pe.rva_offset(after,0xae3cb)]
assert before[0][changed[0]]==1 and after[changed[0]]==0

def replay(data,route,button,early,repeat_press=False):
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x300000);u.mem_map(0x800000,0x10000)
 for _,vs,rva,rs,rp in pe.pe_info(data)[2]:u.mem_write(0x400000+rva,data[rp:rp+rs])
 def w(a,v):u.mem_write(a,pe.u32(v))
 def g(a):return int.from_bytes(u.mem_read(a,4),'little')
 w(0x581280,0x804000);w(0x804120,1);w(0x580c88,1);w(0x5811e4,1);w(0x53a584,1000)
 for slot,key in [(21,0),(22,1)]:u.mem_write(0x580af8+slot*2,bytes([key,key]))
 u.mem_write(0x50aece,bytes.fromhex('55 8b ec 57 51 8b 7d 08 8b 45 0c 8b 4d 10 fc f3 aa 8b 45 08 59 5f 5d c3'))
 resets=[]
 def hook(u,pc,size,_):
  if pc==0x509dc1:
   sp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,int(route=='controller'));u.reg_write(UC_X86_REG_ESP,sp+4);u.reg_write(UC_X86_REG_EIP,g(sp))
  elif pc==0x4a8210:resets.append(g(0x5811e4))
 u.hook_add(UC_HOOK_CODE,hook)
 def event(down):
  ebp=0x80e100;u.reg_write(UC_X86_REG_ESP,0x80e000);u.reg_write(UC_X86_REG_EBP,ebp);w(ebp-0x4c,0);w(ebp-0x48,button);w(0x53a584,g(0x53a584)+50)
  if route=='controller':start,end=(0x4ae36a if down else 0x4ae3b0),0x4ae405
  else:start,end=(0x4ae448 if down else 0x4ae49b),0x4ae565
  u.emu_start(start,end,count=15000);assert u.reg_read(UC_X86_REG_EIP)==end
 def consume():
  w(0x80e000,0x80f000);u.reg_write(UC_X86_REG_ESP,0x80e000);u.reg_write(UC_X86_REG_EBP,0x80d000)
  u.emu_start(0x4e0a90 if button==0 else 0x4e0e00,0x80f000,count=15000)
  return u.reg_read(UC_X86_REG_EAX)
 event(1);first=consume() if early else 0;event(0);second=consume()
 result={'route':route,'button':'A' if button==0 else 'B','read_before_release':early,
  'press_result':first,'after_release_result':second,'total':first+second,'reset_count':len(resets)}
 if repeat_press:
  event(1);next_first=consume() if early else 0;event(0);next_release=consume()
  result['second_press_total']=next_first+next_release
 return result

versions=[('preAkey-dad5a163',before[0]),('postA-period-10457d09',after),('installed-abeab444',(root/'NewPAL_Release.exe').read_bytes())]
report={'user_history':'User states A was repaired first, then B using A logic. Treat as confirmed user history; filenames alone do not establish the full chronology.',
 'binary_evidence':'Three preAkey copies are identical; next preSpeed copy differs in exactly one byte at RVA AE3CB: push1 -> push0 in controller release source setter.',
 'versions':[]}
for label,data in versions:
 rows=[replay(data,route,button,early) for route in ('controller','joystick') for button in (0,1) for early in (False,True)]
 report['versions'].append({'label':label,'sha1':hashlib.sha1(data).hexdigest(),'replays':rows})
 a=next(r for r in rows if r['route']=='controller' and r['button']=='A' and r['read_before_release'])
 assert a['total']==(2 if label.startswith('preAkey') else 1)
 generic=next(r for r in rows if r['route']=='joystick' and r['button']=='A' and r['read_before_release']);assert generic['total']==2
report['conclusion']='A behavioral fix exists at the upper controller-release path and is retained in installed EXE. It prevents the second A confirmation by clearing input on release, but does not cover generic joystick route and may discard an unread fast tap. Button-only replay had omitted this legacy fix.'
path=root/'补丁工作仓库/候选版本/akey-history-full-audit-20261101.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'conclusion':report['conclusion'],'versions':[{'label':v['label'],'sha1':v['sha1'],'controller_A_early':next(r for r in v['replays'] if r['route']=='controller' and r['button']=='A' and r['read_before_release'])} for v in report['versions']]},indent=2))
