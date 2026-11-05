"""Withdraw co-op AoE; keep scaling and fit four-digit HP/MP status rows."""
import hashlib,json
import flash_v4 as pe
import coop_scaling_v1 as previous

BASELINE='9165872a2eb8f24f709475df2c04a7b4e9897f99'
PREVIOUS='c46c79b65317f6490054bcfb6b12d3fca8364b29'
LAYOUT={0xbf912:(0x24,0x2d),0xbf968:(0x90,0x87),
        0xbfa57:(0x24,0x2d),0xbfaad:(0x90,0x87)}

def baseline():
 p=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v1-20261101'
 data=p.read_bytes()
 if hashlib.sha1(data).hexdigest()!=BASELINE:raise ValueError('Backup baseline differs')
 return data

def candidate(source):
 out,plan=previous.candidate(source);data=bytearray(out)
 # Restore the exact native command target call and remove unused AoE code.
 off=pe.rva_offset(source,previous.AOE_SITE)
 data[off:off+5]=source[off:off+5]
 start=pe.rva_offset(out,plan['aoe']-pe.IMAGE_BASE)
 data[start:start+0x400]=bytes(0x400)
 for rva,(old,new) in LAYOUT.items():
  off=pe.rva_offset(source,rva)
  if source[off]!=old:raise ValueError('Status layout differs')
  data[off]=new
 return bytes(data),plan

if __name__=='__main__':
 out,_=candidate(baseline());p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.four-features-v2.exe';p.write_bytes(out)
 print(json.dumps({'candidate_sha1':hashlib.sha1(out).hexdigest(),'status':'AoE withdrawn; native selection/animations restored; status four-digit spacing corrected; acceptance pending'}))
