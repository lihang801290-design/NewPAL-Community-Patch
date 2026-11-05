"""Restore native growth RNG; halve all action-count band boundaries."""
import hashlib,json,os,shutil,sys
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import *
import flash_v4 as pe
import four_features_v6 as v6
from install_verified_candidate import running

PREVIOUS='9a37e6bab9d9438b42d7938c8569f868aa49f963'

def thresholds(original):
 cs=Cs(CS_ARCH_X86,CS_MODE_32);cs.detail=True
 start=0xd7830;off=pe.rva_offset(original,start)
 ins=list(cs.disasm(original[off:off+0x1000],pe.IMAGE_BASE+start));rows=[]
 for j,i in enumerate(ins[1:-1],1):
  prev=ins[j-1];ops=i.operands
  if i.mnemonic!='cmp' or len(ops)!=2 or ops[0].type!=X86_OP_MEM or ops[1].type!=X86_OP_IMM or not 0<ops[1].imm<32:continue
  if prev.mnemonic!='mov' or len(prev.operands)!=2 or prev.operands[1].type!=X86_OP_MEM:continue
  mem=prev.operands[1].mem
  if mem.base!=X86_REG_EBP or mem.disp!=-4 or prev.operands[0].reg!=ops[0].mem.base:continue
  branch=ins[j+1].mnemonic;old=ops[1].imm
  if branch=='jl':new=(old+1)//2
  elif branch=='jg':new=old//2
  else:raise ValueError('Unexpected counter comparison branch')
  if i.imm_size!=1:raise ValueError('Unexpected count encoding')
  rows.append({'rva':i.address-pe.IMAGE_BASE+i.imm_offset,'old':old,'new':new,'branch':branch})
 if len(rows)!=35:raise ValueError('Expected five band limits for each of seven attributes')
 return rows

def candidate():
 previous,plan,_,_=v6.candidate()
 if hashlib.sha1(previous).hexdigest()!=PREVIOUS:raise ValueError('Previous version differs')
 original=v6.v5.v4.v3.v2.baseline();data=bytearray(previous)
 for rva,(native,_) in v6.growth.GROWTH.items():
  off=pe.rva_offset(previous,rva)
  if previous[off]!=min(100,native*2):raise ValueError('Probability byte differs')
  data[off]=native
 rows=thresholds(original)
 for row in rows:
  off=pe.rva_offset(previous,row['rva'])
  if previous[off]!=row['old']:raise ValueError('Count boundary differs')
  data[off]=row['new']
 return bytes(data),previous,original,rows

def main():
 data,previous,original,rows=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';sha=hashlib.sha1(data).hexdigest()
 (folder/'NewPAL_Release.four-features-v7.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':sha}));return
 report=json.loads((folder/'four-features-v7-verification.json').read_text(encoding='utf-8'))
 if report['candidate_sha1']!=sha or report['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=previous:raise ValueError('Installed EXE differs')
 if running():print('Game still running; save and exit normally; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v7-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.four-features-v7-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 result={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':sha,'backup':str(backup),
  'growth':'all original probabilities restored; action-count band transitions ceil(original/2), inclusive upper bounds adjusted to prevent overlaps; first thresholds15->8,12->6,10->5; +2/+3 bands also reached at half counts with native probabilities',
  'retained':'v5 corrected co-op balance and all other batch/released patches; no save/current counter edits',
  'formal_log_and_collaboration_package':'deferred until batch acceptance'}
 (folder/'installation-four-features-v7.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
