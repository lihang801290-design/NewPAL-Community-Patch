"""Exactly +10% to the existing guarded co-op result, rounded to nearest."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import four_features_v9 as v9
from install_verified_candidate import running

BASE='8024bcb68173b5b47f9c03202fff293f68dba5a6'
def candidate():
 old,_,_=v9.candidate()
 if hashlib.sha1(old).hexdigest()!=BASE:raise ValueError('Expected integrated-v3 source')
 v5=v9.v8.v7.v6.v5;_,prior,_=v5.candidate()
 plan=v5.v4.payload(pe.IMAGE_BASE,prior['origin'],balanced=True,boost10=True)
 blob=plan['blob']
 if blob.count(v9.v8.BEFORE)!=1:raise ValueError('Co-op base ratio differs')
 blob=blob.replace(v9.v8.BEFORE,v9.AFTER)
 data=bytearray(old);off=pe.rva_offset(old,prior['origin']-pe.IMAGE_BASE);data[off:off+4096]=blob
 return bytes(data),old,off

def main():
 data,old,off=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';sha=hashlib.sha1(data).hexdigest()
 (folder/'NewPAL_Release.coop-boost-v10.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':sha}));return
 check=json.loads((folder/'coop-boost-v10-verification.json').read_text(encoding='utf-8'))
 if check['candidate_sha1']!=sha or check['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=old:raise ValueError('Installed version differs')
 if running():print('Game still running; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-coop-boost-v10-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.coop-boost-v10-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 report={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':sha,'backup':str(backup),
  'change':'round(existing guarded co-op damage*1.10); original HP cost, targets and all other patches retained',
  'menu_option':'research only; still fixed10s; published integrated-v3 ZIP remains8024 until explicitly rebuilt'}
 (folder/'installation-coop-boost-v10.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
