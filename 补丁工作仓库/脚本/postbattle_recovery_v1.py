"""Recover floor(max*6/100) HP/MP for living actual party at normal exit."""
import hashlib,json
import flash_v4 as pe

BASELINE='9165872a2eb8f24f709475df2c04a7b4e9897f99'
SITE=0xc97f3;SIZE=0x500
EXPECTED=pe.branch(0xe8,pe.IMAGE_BASE+SITE,pe.IMAGE_BASE+0xd1c90)

def payload(base,origin):
 a=pe.Asm(origin)
 def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
 a.raw('9c 60 55 8b ec 83 ec 10')
 op('83 3d',base+0x131b80,b'\x01');a.jump('0f 85','done')
 op('83 3d',base+0x199814,b'\x00');a.jump('0f 84','done')
 op('8b 3d',base+0x199894);a.raw('85 ff');a.jump('0f 84','done')
 a.raw('8b cf');a.jump('e8',base+0xcd2d0);a.raw('85 c0');a.jump('0f 8e','done');a.raw('83 f8 03');a.jump('0f 8f','done')
 a.raw('89 45 fc 33 db')
 a.label('role');a.raw('53 8b cf');a.jump('e8',base+0xcd170);a.raw('85 c0');a.jump('0f 84','next')
 a.raw('8b 70 04 85 f6');a.jump('0f 84','next')
 a.raw('6a 11 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','next')
 a.raw('83 38 00');a.jump('0f 8e','next')
 a.raw('f7 46 28 04 00 00 00');a.jump('0f 85','next')
 for name,max_id,current_id in [('hp',0x10,0x11),('mp',0x16,0x17)]:
  skip=name+'_done';a.raw(bytes([0x6a,max_id,0x56]));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84',skip)
  a.raw('8b 10 85 d2');a.jump('0f 8e',skip);a.raw('81 fa 0f 27 00 00');a.jump('0f 8f',skip);a.raw('89 55 f4')
  a.raw(bytes([0x6a,current_id,0x56]));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84',skip)
  a.raw('89 45 f8 8b 08 85 c9');a.jump('0f 88',skip);a.raw('3b 4d f4');a.jump('0f 8d',skip)
  a.raw('8b 45 f4 b9 06 00 00 00 f7 e1 b9 64 00 00 00 f7 f1 8b 55 f8 03 02 3b 45 f4');a.jump('0f 8e',name+'_store')
  a.raw('8b 45 f4');a.label(name+'_store');a.raw('89 02');a.label(skip)
 a.label('next');a.raw('43 3b 5d fc');a.jump('0f 8c','role')
 a.label('done');a.raw('8b e5 5d 61 9d');a.jump('e9',base+0xd1c90)
 blob=a.finish();assert len(blob)<=SIZE
 return {'blob':blob+bytes(SIZE-len(blob)),'patches':{SITE:pe.branch(0xe8,base+SITE,origin)}}

def candidate(source):
 if hashlib.sha1(source).hexdigest()!=BASELINE:raise ValueError('Expected integrated9165872a')
 section=next(s for s in pe.pe_info(source)[2] if s[0]==b'.palhov');offset=section[4]+0xa00
 if any(source[offset:offset+SIZE]):raise ValueError('Recovery area occupied')
 plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+section[2]+0xa00);data=bytearray(source);data[offset:offset+SIZE]=plan['blob']
 off=pe.rva_offset(source,SITE)
 if source[off:off+5]!=EXPECTED:raise ValueError('Exit call differs')
 data[off:off+5]=plan['patches'][SITE];return bytes(data),plan

if __name__=='__main__':
 out,plan=candidate((pe.ROOT/'NewPAL_Release.exe').read_bytes());p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.postbattle-recovery-v1.exe';p.write_bytes(out)
 print(json.dumps({'status':'candidate; verification pending','sha1':hashlib.sha1(out).hexdigest()}))
