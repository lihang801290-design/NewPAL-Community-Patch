"""Correct player normal-hit baseline and bound the optional growth bonus."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import coop_balance_v4 as v4
from install_verified_candidate import running

PREVIOUS='1da77244d10f540263a435839fe51699ea4287dc'
def candidate():
 old,oldplan,_=v4.candidate()
 if hashlib.sha1(old).hexdigest()!=PREVIOUS:raise ValueError('Previous build differs')
 plan=v4.payload(pe.IMAGE_BASE,oldplan['origin'],balanced=True)
 data=bytearray(old);off=pe.rva_offset(old,plan['origin']-pe.IMAGE_BASE)
 data[off:off+v4.SIZE]=plan['blob'];return bytes(data),plan,old

def main():
 data,plan,old=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';sha=hashlib.sha1(data).hexdigest()
 (folder/'NewPAL_Release.four-features-v5.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'sha1':sha,'helper_bytes':plan['length']}));return
 check=json.loads((folder/'coop-balance-v5-verification.json').read_text(encoding='utf-8'))
 if check['candidate_sha1']!=sha or check['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=old:raise ValueError('Installed EXE differs')
 if running():print('Game still running; nothing installed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v5-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.four-features-v5-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; nothing installed')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 report={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':sha,'backup':str(backup),
  'correction':'v4 used enemy physical type33 as player normal baseline; actual player types1/2/4 differ. v5 uses player formula, target luck/defense percentages and native whip/staff variants.',
  'formula':'max(native damage, ceil(1.10*ordinary_upper_sum)+min(growth//8,ceil(ordinary_upper_sum/10)))',
  'retained':'actual eligible participants only; native targets and HP cost; no MP drain; all other accepted/pending batch changes byte-identical',
  'formal_log_and_collaboration_package':'wait for user acceptance'}
 (folder/'installation-four-features-v5.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
