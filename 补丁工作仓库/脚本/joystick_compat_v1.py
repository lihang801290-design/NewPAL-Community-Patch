"""Generic JOY A-release compatibility and controller-family state continuity.

Keep the legacy standard-controller A fix and B trampoline byte-identical.
No controller configuration, LED, reconnect or firmware-mode APIs are called.
"""
import hashlib,json
import flash_v4 as pe
import hover_hand_v1 as previous

UP=0xae4bd;SOURCE=0xadf60;SIZE=512
EXPECTED={UP:bytes.fromhex('e8 0e a9 ff ff'),SOURCE:bytes.fromhex('55 8b ec 51 89 4d fc')}

def payload(base,origin):
 a=pe.Asm(origin);symbols={}
 symbols['up']=a.pc
 a.raw('55 8b ec 53 56 57 8b f1 0f b6 9e 00 03 00 00 8b be 08 03 00 00')
 a.raw('ff 75 14 ff 75 10 ff 75 0c ff 75 08 8b ce');a.jump('e8',base+0xa8dd0)
 a.raw('83 7d 10 00');a.jump('0f 85','up_done');a.raw('83 7d 14 00');a.jump('0f 85','up_done')
 a.raw('83 fb 01');a.jump('0f 85','rapid_release');a.raw('80 be 00 03 00 00 02');a.jump('0f 85','up_done')
 # Native A release changed state1->2. Restore the pre-release pending flag:
 # preserve an unread press, but do not regenerate an already consumed press.
 a.raw('89 be 08 03 00 00');a.jump('e9','up_done')
 # A rapid second press uses native state3. An unread press must remain
 # readable even when its release changes state3->0 before menu consumption.
 a.label('rapid_release');a.raw('83 fb 03');a.jump('0f 85','up_done')
 a.raw('80 be 00 03 00 00 00');a.jump('0f 85','up_done');a.raw('f7 c7 01 00 00 00');a.jump('0f 84','up_done')
 a.raw('c6 86 00 03 00 00 02 89 be 08 03 00 00')
 a.label('up_done');a.raw('5f 5e 5b 8b e5 5d c2 10 00')
 symbols['source']=a.pc;a.raw(EXPECTED[SOURCE]);a.raw('9c 60 81 f9');a.raw(pe.u32(base+0x180b38));a.jump('0f 85','native')
 a.raw('83 b9 50 01 00 00 01');a.jump('0f 85','native');a.raw('8b 45 08')
 for value in (1,3):a.raw(bytes([0x83,0xf8,value]));a.jump('0f 84','new_family')
 a.raw('83 f8 04');a.jump('0f 85','native')
 a.label('new_family');a.raw('c7 45 08 01 00 00 00 8b 81 ac 06 00 00')
 for value in (1,3):a.raw(bytes([0x83,0xf8,value]));a.jump('0f 84','same_family')
 a.raw('83 f8 04');a.jump('0f 85','native')
 # Canonical kind1 also preserves legacy controller UP->kind0 clearing;
 # leaving kind3 here would bypass that old A fix when axis events interleave.
 a.label('same_family');a.raw('c7 81 ac 06 00 00 01 00 00 00')
 a.label('native');a.raw('61 9d');a.jump('e9',base+SOURCE+7)
 blob=a.finish();assert len(blob)<=SIZE
 return {'blob':blob+bytes(SIZE-len(blob)),'symbols':symbols,'patches':{
  UP:pe.branch(0xe8,base+UP,symbols['up']),SOURCE:pe.branch(0xe9,base+SOURCE,symbols['source'])+b'\x90\x90'}}

def candidate(source):
 if hashlib.sha1(source).hexdigest()=='3853c3ed892fe37e632cd777d5553f20681eda6f':out=source
 else:out,_=previous.candidate(source)
 section=next(s for s in pe.pe_info(out)[2] if s[0]==b'.palhov');off=section[4]+0x800
 if any(out[off:off+SIZE]):raise ValueError('Helper area occupied')
 plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+section[2]+0x800);data=bytearray(out);data[off:off+SIZE]=plan['blob']
 for site,value in plan['patches'].items():
  off=pe.rva_offset(out,site)
  if out[off:off+len(EXPECTED[site])]!=EXPECTED[site]:raise ValueError('Generic joystick site differs')
  data[off:off+len(value)]=value
 return bytes(data),plan

if __name__=='__main__':
 out,plan=candidate((pe.ROOT/'NewPAL_Release.exe').read_bytes());p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.joystick-compat-v1.exe';p.write_bytes(out)
 report={'status':'candidate; native/gameplay pending','target_sha1':hashlib.sha1(out).hexdigest(),
  'scope':'generic JOY A release only plus state continuity between controller button/axis/hat; legacy standard A/B unchanged; no physical mode commands'}
 p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
