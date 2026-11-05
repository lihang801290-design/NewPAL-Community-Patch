"""Small co-op uplift: base1.45*normal upper plus existing bounded growth."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import four_features_v8 as v8
from install_verified_candidate import running

PREVIOUS='b8d0736a37face199972f9d1a3a8714ce3ca69c8'
BEFORE=bytes.fromhex('8b45e06bc01b83c01333d2b914000000f7f10345d0')
AFTER=bytes.fromhex('8b45e06bc01d83c01333d2b914000000f7f10345d0')

def candidate():
 previous,_,_=v8.candidate()
 if hashlib.sha1(previous).hexdigest()!=PREVIOUS:raise ValueError('Previous version differs')
 if previous.count(BEFORE)!=1:raise ValueError('Expected one guarded final co-op ratio')
 offset=previous.index(BEFORE);data=previous[:offset]+AFTER+previous[offset+len(BEFORE):]
 return data,previous,offset

def main():
 data,previous,offset=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';sha=hashlib.sha1(data).hexdigest()
 (folder/'NewPAL_Release.four-features-v9.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':sha}));return
 report=json.loads((folder/'four-features-v9-verification.json').read_text(encoding='utf-8'))
 if report['candidate_sha1']!=sha or report['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=previous:raise ValueError('Installed EXE differs')
 if running():print('Game still running; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v9-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.four-features-v9-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 result={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':sha,'backup':str(backup),
  'change':'co-op floor ratio1.35->1.45; bounded stat/level bonus at most0.10*ordinary upper retained, total1.45..1.55*upper; native stronger moves retained',
  'unchanged':'growth RNG native + halved count bands; HP/MP cap/recovery, UI and all released fixes; native HP cost, no added MP cost',
  'formal_log_and_collaboration_package':'wait for user acceptance'}
 (folder/'installation-four-features-v9.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
