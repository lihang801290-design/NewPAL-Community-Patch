"""Candidate: let fixed-level co-op formulas scale with participating attack.

Keep the original level as a floor and retain each move's constants/resistance
and random variation. Only cooperative player moves using the fixed-level
formula are changed; real level values are never written.
"""
import hashlib,json,struct
import flash_v4 as pe
import simple_batch_v1 as first_three

SITE=0xda339;EXPECTED=pe.branch(0xe8,pe.IMAGE_BASE+SITE,pe.IMAGE_BASE+0xddd60)
SIZE=4096
AOE_SITE=0xdf21d

def aoe_payload(base,origin):
 # Called only by the player-command target selection site. Parent EBP+8 is
 # the acting role. Native 1017 expands to all living opponents, relative to
 # the source side; native scripts and damage/death processing stay in use.
 a=pe.Asm(origin)
 a.raw('9c 60 8b 75 08 85 f6');a.jump('0f 84','done')
 a.raw('81 3e d0 07 00 00');a.jump('0f 8c','done');a.raw('81 3e b8 0b 00 00');a.jump('0f 8d','done')
 a.raw(b'\x68'+pe.u32(0x3f2));a.jump('e8',base+0xccee0);a.raw('83 c4 04 84 c0');a.jump('0f 84','done')
 a.raw('68 b4 00 00 00 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','done')
 a.raw('8b 00 3d a7 02 00 00');a.jump('0f 8c','done');a.raw('3d b8 02 00 00');a.jump('0f 8f','done')
 for excluded in (0x2b4,0x2b5):
  a.raw(b'\x3d'+pe.u32(excluded));a.jump('0f 84','done')
 a.raw('8b 44 24 28 3d 00 00 ff 7e');a.jump('0f 8c','concrete')
 for target in (0x7eff1003,0x7eff1005,0x7eff1007,0x7eff1015,0x7eff1017):
  a.raw(b'\x3d'+pe.u32(target));a.jump('0f 84','all')
 a.jump('e9','done')
 a.label('concrete');a.raw('50');a.jump('e8',base+0xd8f50);a.raw('83 c4 04 83 f8 01');a.jump('0f 85','done')
 a.label('all');a.raw('c7 44 24 28 17 10 ff 7e')
 a.label('done');a.raw('61 9d');a.jump('e9',base+0xee070)
 return a.finish()

def payload(base,origin,mixed=False):
 a=pe.Asm(origin);scratch=origin+0x3f0
 def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
 a.raw('55 8b ec 83 ec 18 53 56 57 ff 75 0c ff 75 08');a.jump('e8',base+0xddd60);a.raw('83 c4 08 89 45 fc 85 c0');a.jump('0f 84','original')
 a.raw('83 7d 0c 05');a.jump('0f 85','original');a.raw('8b 55 08 81 3a d0 07 00 00');a.jump('0f 8c','original');a.raw('81 3a b8 0b 00 00');a.jump('0f 8d','original')
 a.raw(b'\x68'+pe.u32(0x3f2));a.jump('e8',base+0xccee0);a.raw('83 c4 04 84 c0');a.jump('0f 84','original')
 op('8b 3d',base+0x199894);a.raw('85 ff');a.jump('0f 84','original');a.raw('8b cf');a.jump('e8',base+0xcd2d0)
 a.raw('83 f8 02');a.jump('0f 8c','original');a.raw('83 f8 03');a.jump('0f 8f','original')
 a.raw('89 45 f8 c7 45 f4 00 00 00 00 c7 45 ec 00 00 00 00 c7 45 e8 00 00 00 00 33 db')
 a.label('loop');a.raw('ff 75 f4 8b cf');a.jump('e8',base+0xcd170);a.raw('85 c0');a.jump('0f 84','next');a.raw('8b 70 04 85 f6');a.jump('0f 84','next')
 a.raw('f7 46 28 04 00 00 00');a.jump('0f 85','next');a.raw('f7 46 30 0c 00 00 00');a.jump('0f 85','next')
 a.raw('6a 11 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','next');a.raw('83 38 00');a.jump('0f 8e','next')
 a.raw('c7 45 f0 00 00 00 00 6a 1a 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','bonus');a.raw('8b 00 89 45 f0')
 a.label('bonus');a.raw('6a 1d 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','combined' if mixed else 'sum');a.raw('8b 00 01 45 f0')
 if mixed:
  a.label('combined')
  for attr in (0x20,0x23):
   a.raw(bytes([0x6a,attr,0x56]));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','spirit_'+str(attr));a.raw('8b 00 01 45 f0');a.label('spirit_'+str(attr))
  a.raw('d1 7d f0') # arithmetic /2: each participant's (attack+spirit)/2
 a.label('sum');a.raw('8b 45 f0 85 c0');a.jump('0f 8e','next');a.raw('3d 40 42 0f 00');a.jump('0f 8f','original')
 a.raw('03 d8 ff 45 e8 3b 75 08');a.jump('0f 85','next');a.raw('c7 45 ec 01 00 00 00')
 a.label('next');a.raw('ff 45 f4 8b 45 f4 3b 45 f8');a.jump('0f 8c','loop')
 a.raw('83 7d ec 01');a.jump('0f 85','original');a.raw('83 7d e8 02');a.jump('0f 8c','original')
 a.raw('d1 eb 8b 45 fc 3b 18');a.jump('0f 8e','original');op('89 1d',scratch);a.raw(b'\xb8'+pe.u32(scratch));a.jump('e9','return')
 a.label('original');a.raw('8b 45 fc');a.label('return');a.raw('5f 5e 5b 8b e5 5d c3')
 blob=a.finish();assert len(blob)<0x3f0
 return {'blob':blob+bytes(SIZE-len(blob)),'scratch':scratch,'patches':{SITE:pe.branch(0xe8,base+SITE,origin)}}

def candidate(source):
 out=first_three.candidate(source);header,opt,sections=pe.pe_info(out);last=sections[-1]
 if last[0]!=b'.palhov' or last[4]+last[3]!=len(out) or last[3]!=4096:raise ValueError('Expected final palhov section with no overlay')
 origin=pe.IMAGE_BASE+last[2]+last[3];plan=payload(pe.IMAGE_BASE,origin)
 blob=bytearray(plan['blob']);aoe=aoe_payload(pe.IMAGE_BASE,origin+0x400);assert len(aoe)<0x400
 blob[0x400:0x400+len(aoe)]=aoe;plan['aoe']=origin+0x400
 data=bytearray(out);data.extend(blob)
 section_header=opt+struct.unpack_from('<H',out,header+20)[0]+(len(sections)-1)*40
 struct.pack_into('<I',data,section_header+8,last[1]+SIZE);struct.pack_into('<I',data,section_header+16,last[3]+SIZE)
 struct.pack_into('<I',data,opt+56,last[2]+last[3]+SIZE);struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',out,opt+4)[0]+SIZE)
 off=pe.rva_offset(out,SITE)
 if out[off:off+5]!=EXPECTED:raise ValueError('Fixed-level damage getter differs')
 data[off:off+5]=plan['patches'][SITE]
 off=pe.rva_offset(out,AOE_SITE)
 if out[off:off+5]!=pe.branch(0xe8,pe.IMAGE_BASE+AOE_SITE,pe.IMAGE_BASE+0xee070):raise ValueError('Co-op target site differs')
 data[off:off+5]=pe.branch(0xe8,pe.IMAGE_BASE+AOE_SITE,plan['aoe'])
 return bytes(data),plan

if __name__=='__main__':
 out,plan=candidate((pe.ROOT/'NewPAL_Release.exe').read_bytes());path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.four-features-v1.exe';path.write_bytes(out)
 print(json.dumps({'status':'four-feature candidate; verification/user test pending','sha1':hashlib.sha1(out).hexdigest(),'coop':'effective fixed-formula basis=max(level, sum(eligible party attack)/2); other move logic unchanged'}))
