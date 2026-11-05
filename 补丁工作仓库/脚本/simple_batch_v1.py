"""First three requested changes; fourth co-op fix awaits actual diagnosis."""
import hashlib,json,struct
import flash_v4 as pe
import postbattle_recovery_v1 as recovery

GROWTH={0xd7904:(50,75),0xd7b54:(50,75),0xd7d9b:(60,90),0xd7fe2:(60,90),
        0xd8229:(50,75),0xd8470:(40,60),0xd865f:(50,75)}
CAPS=(0xd8a8b,0xd8a96)

def candidate(source):
 out,_=recovery.candidate(source);data=bytearray(out)
 for rva,(old,new) in GROWTH.items():
  off=pe.rva_offset(source,rva)
  if source[off-3:off+1]!=bytes([0x83,0x7d,0xf8,old]):raise ValueError('Growth compare differs')
  data[off]=new
 for rva in CAPS:
  off=pe.rva_offset(source,rva)
  if source[off:off+4]!=pe.u32(999):raise ValueError('HP/MP clamp differs')
  data[off:off+4]=pe.u32(9999)
 return bytes(data)

if __name__=='__main__':
 out=candidate((pe.ROOT/'NewPAL_Release.exe').read_bytes());path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.simple-batch-v1.exe';path.write_bytes(out)
 print(json.dumps({'status':'first three candidate; fourth not yet implemented','sha1':hashlib.sha1(out).hexdigest(),'growth':'earliest +1 eligible band chance multiplied by1.5; counters and later +2/+3 unchanged','cap':9999}))
