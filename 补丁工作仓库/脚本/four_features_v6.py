"""Merge corrected co-op v5 and requested double earliest +1 growth chance."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import coop_balance_v5 as v5
import simple_batch_v1 as growth
from install_verified_candidate import running

def candidate():
 previous,plan,installed=v5.candidate();data=bytearray(previous)
 for rva,(original,old) in growth.GROWTH.items():
  off=pe.rva_offset(previous,rva)
  if previous[off]!=old:raise ValueError('Growth byte differs')
  data[off]=min(100,original*2)
 return bytes(data),plan,previous,installed

def main():
 data,plan,previous,installed=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';sha=hashlib.sha1(data).hexdigest()
 (folder/'NewPAL_Release.four-features-v6.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':sha}));return
 report=json.loads((folder/'four-features-v6-verification.json').read_text(encoding='utf-8'))
 if report['candidate_sha1']!=sha or report['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source not in (installed,previous):raise ValueError('Installed baseline differs')
 if running():print('Game still running; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v6-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.four-features-v6-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 result={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':sha,
  'backup':str(backup),'changes':'v5 corrected player-normal co-op baseline and bounded growth bonus; seven earliest eligible +1 growth chances x2 capped100%; all other batch/released features retained',
  'formal_log_and_collaboration_package':'wait for batch acceptance'}
 (folder/'installation-four-features-v6.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
