"""Keep native move formulas; add growth appropriate to each formula family."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import coop_boost_v10 as prior
from install_verified_candidate import running

BASE='7f7c223087679664daeb914923d5da0c5ebc0a37'

def payload(base,origin):
 a=pe.Asm(origin)
 a.raw('55 8b ec 83 ec 38 53 56 57 89 45 fc 85 c0');a.jump('0f 89','done')
 a.raw('8b 55 00 8b 42 08 89 45 f8 85 c0');a.jump('0f 84','done')
 a.raw('81 38 d0 07 00 00');a.jump('0f 8c','done');a.raw('81 38 b8 0b 00 00');a.jump('0f 8d','done')
 a.raw('8b 42 0c 89 45 cc 85 c0');a.jump('0f 84','done');a.raw('ff 30');a.jump('e8',base+0xd8f50);a.raw('83 c4 04 83 f8 01');a.jump('0f 85','done')
 a.raw(b'\x68'+pe.u32(0x3f2));a.jump('e8',base+0xccee0);a.raw('83 c4 04 84 c0');a.jump('0f 84','done')
 a.raw('68 b4 00 00 00 ff 75 f8');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','done')
 a.raw('8b 00 3d a7 02 00 00');a.jump('0f 8c','done');a.raw('3d b8 02 00 00');a.jump('0f 8f','done')
 for id in (0x2b4,0x2b5):a.raw(b'\x3d'+pe.u32(id));a.jump('0f 84','done')
 a.raw(b'\xa1'+pe.u32(base+0x1998a8));a.raw('89 45 f4')
 for type in (0x1f,0x21):a.raw(bytes([0x83,0xf8,type]));a.jump('0f 84','physical')
 for type in (0x20,0x22,0x23):a.raw(bytes([0x83,0xf8,type]));a.jump('0f 84','spirit')
 a.raw('83 f8 0b');a.jump('0f 84','spell_physical');a.raw('83 f8 15');a.jump('0f 8c','done');a.raw('83 f8 1a');a.jump('0f 8f','done')
 a.raw('c7 45 f0 04 00 00 00');a.jump('e9','scale')
 a.label('physical');a.raw('c7 45 f0 00 00 00 00');a.jump('e9','scale')
 a.label('spirit');a.raw('c7 45 f0 01 00 00 00');a.jump('e9','scale')
 a.label('spell_physical');a.raw('c7 45 f0 03 00 00 00')
 a.label('scale');a.raw('c7 45 d0 64 00 00 00 83 7d f0 04');a.jump('0f 85','party')
 # The same target element property pair used by the native spell formula.
 a.raw('c7 45 d0 00 00 00 00 8b 45 f4 83 e8 15 6b c0 06 83 c0 38 89 45 d4')
 for index in (0,1):
  a.raw('8b 45 d4')
  if index:a.raw('83 c0 03')
  a.raw('50 ff 75 cc');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','element_'+str(index));a.raw('8b 00 01 45 d0');a.label('element_'+str(index))
 a.raw('8b 45 d0 85 c0');a.jump('0f 8d','scale_positive');a.raw('f7 d8')
 a.label('scale_positive');a.raw('3d 10 27 00 00');a.jump('0f 8f','done');a.raw('89 45 d0')
 a.label('party');a.raw(b'\x8b\x3d'+pe.u32(base+0x199894));a.raw('85 ff');a.jump('0f 84','done');a.raw('8b cf');a.jump('e8',base+0xcd2d0)
 a.raw('83 f8 02');a.jump('0f 8c','done');a.raw('83 f8 03');a.jump('0f 8f','done')
 a.raw('89 45 ec 33 db c7 45 e8 00 00 00 00 c7 45 e4 00 00 00 00 c7 45 e0 00 00 00 00')
 a.label('role');a.raw('53 8b cf');a.jump('e8',base+0xcd170);a.raw('85 c0');a.jump('0f 84','next');a.raw('8b 70 04 85 f6');a.jump('0f 84','next')
 a.raw('f7 46 28 04 00 00 00');a.jump('0f 85','next');a.raw('f7 46 30 0c 00 00 00');a.jump('0f 85','next')
 a.raw('6a 11 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','next');a.raw('83 38 00');a.jump('0f 8e','next')
 a.raw('ff 45 e4 3b 75 f8');a.jump('0f 85','stats');a.raw('c7 45 e0 01 00 00 00 83 7d f0 03');a.jump('0f 8d','next')
 a.label('stats');a.raw('c7 45 dc 00 00 00 00 c7 45 d8 00 00 00 00')
 for attr,local in ((0x1a,0xdc),(0x1d,0xdc),(0x20,0xd8),(0x23,0xd8)):
  a.raw(bytes([0x6a,attr,0x56]));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','stat_'+str(attr));a.raw(bytes.fromhex('8b 00 01 45')+bytes([local]));a.label('stat_'+str(attr))
 for local in (0xdc,0xd8):
  a.raw(bytes([0x81,0x7d,local])+pe.u32(1000000));a.jump('0f 8f','done');a.raw(bytes([0x83,0x7d,local,0]));a.jump('0f 8d','valid_'+str(local));a.raw(bytes([0xc7,0x45,local])+pe.u32(0));a.label('valid_'+str(local))
 a.raw('83 7d f0 03');a.jump('0f 8d','spell_growth')
 # Missing native player-stat scaling: physical(3A+S)/8+L or spirit(A+3S)/8+L.
 a.raw('8b 45 dc 8b 55 d8 83 7d f0 00');a.jump('0f 85','spirit_growth');a.raw('6b c0 03');a.jump('e9','fixed_sum')
 a.label('spirit_growth');a.raw('6b d2 03')
 a.label('fixed_sum');a.raw('03 c2 c1 e8 03 01 45 e8 6a 05 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','next')
 a.raw('8b 00 85 c0');a.jump('0f 8e','next');a.raw('3d 10 27 00 00');a.jump('0f 8f','done');a.raw('01 45 e8');a.jump('e9','next')
 # Native stat-based moves already include the caster: add teammates only,
 # using their original physical-spell or elemental-spell weights.
 a.label('spell_growth');a.raw('83 7d f0 03');a.jump('0f 85','element_growth');a.raw('8b 45 dc c1 e8 02 01 45 e8 8b 45 d8');a.jump('e9','twelfth')
 a.label('element_growth');a.raw('8b 45 d8 c1 e8 02 01 45 e8 8b 45 dc')
 a.label('twelfth');a.raw('33 d2 b9 0c 00 00 00 f7 f1 01 45 e8')
 a.label('next');a.raw('43 3b 5d ec');a.jump('0f 8c','role')
 a.raw('83 7d e0 01');a.jump('0f 85','done');a.raw('83 7d e4 02');a.jump('0f 8c','done')
 a.raw('8b 45 e8 83 7d f0 04');a.jump('0f 85','append');a.raw('f7 65 d0 b9 64 00 00 00 f7 f1')
 a.label('append');a.raw('8b 4d fc 2b c8 89 4d fc')
 a.label('done');a.raw('8b 45 fc 5f 5e 5b 8b e5 5d 8b e5 5d c3')
 blob=a.finish();assert len(blob)<4096
 return blob+bytes(4096-len(blob))

def candidate():
 old,_,off=prior.candidate()
 if hashlib.sha1(old).hexdigest()!=BASE:raise ValueError('Expected installed v10')
 section=next(s for s in pe.pe_info(old)[2] if s[4]<=off<s[4]+s[3]);origin=pe.IMAGE_BASE+section[2]+off-section[4]
 data=bytearray(old);data[off:off+4096]=payload(pe.IMAGE_BASE,origin);return bytes(data),old,off

def main():
 data,old,off=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';sha=hashlib.sha1(data).hexdigest();(folder/'NewPAL_Release.coop-native-growth-v11.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':sha}));return
 check=json.loads((folder/'coop-native-growth-v11-verification.json').read_text(encoding='utf-8'))
 if check['candidate_sha1']!=sha or check['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=old:raise ValueError('Installed EXE differs')
 if running():print('Game still running; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-coop-native-growth-v11-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.coop-native-growth-v11-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 report={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':sha,'backup':str(backup),
  'change':'native formula + per-family growth; fixed physical(3A+S)/8+L, fixed spirit(A+3S)/8+L for all eligible; native stat spells add teammates only with original weights and elemental factor',
  'removed':'all normal-attack floors and extra global10% multiplier',
  'retained':'original move constants, power, target/animation/HP cost, ordinary spells/attacks, all unrelated patches; menu still research only; public ZIP remains integrated-v3'}
 (folder/'installation-coop-native-growth-v11.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
