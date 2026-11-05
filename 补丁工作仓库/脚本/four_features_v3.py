"""Pending batch: clearer status/main-menu numbers; mixed-stat co-op basis."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import four_features_v2 as v2
import coop_scaling_v1 as coop
from install_verified_candidate import running

PREVIOUS='1a0d5b550e6f2c8d07babc758f4c21a56282b048'
# Status: current values another3px left, slash/max stay at v2 positions.
# Main menu: actual digit reserve10px, both rows share anchors; 2px added
# between the small slash and maximum. This is scene0's menu/HUD renderer.
PATCHES={0xbf910:('83e92d','83e930'),0xbfa55:('83e92d','83e930'),
 0xbe911:('c1e003','6bc00a'),0xbeb7a:('c1e003','6bc00a'),
 0xbeb6a:('83c669','83c670'),0xbec1d:('83c06d','83c074'),
 0xbea48:('83c27b','83c27d'),0xbeca0:('83c074','83c07d')}

def candidate():
 old,plan=v2.candidate(v2.baseline())
 if hashlib.sha1(old).hexdigest()!=PREVIOUS:raise ValueError('Previous build differs')
 data=bytearray(old)
 for rva,(before,after) in PATCHES.items():
  off=pe.rva_offset(old,rva);before=bytes.fromhex(before);after=bytes.fromhex(after)
  if old[off:off+len(before)]!=before:raise ValueError('Layout site differs')
  data[off:off+len(after)]=after
 origin=plan['scratch']-0x3f0;newplan=coop.payload(pe.IMAGE_BASE,origin,mixed=True)
 off=pe.rva_offset(old,origin-pe.IMAGE_BASE);data[off:off+len(newplan['blob'])]=newplan['blob']
 return bytes(data),newplan,old

def main():
 data,plan,old=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本'
 target=hashlib.sha1(data).hexdigest();(folder/'NewPAL_Release.four-features-v3.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':target}));return
 check=json.loads((folder/'four-features-v3-verification.json').read_text(encoding='utf-8'))
 if check['candidate_sha1']!=target or check['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=old:raise ValueError('Installed EXE differs')
 if running():print('Game running; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v3-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.four-features-v3-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 report={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':target,
  'backup':str(backup),'changes':'status current value3px left; main menu aligned HP/MP with wider digit reserve and slash gap; co-op contribution floor((attack+spirit)/2) per eligible participant then party sum/2; native targets unchanged',
  'formal_log_and_collaboration_package':'deferred until acceptance'}
 (folder/'installation-four-features-v3.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
