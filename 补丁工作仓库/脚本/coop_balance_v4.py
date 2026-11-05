"""Native co-op + mixed growth, with a conservative party normal-hit floor."""
import hashlib,json,os,shutil,sys
import flash_v4 as pe
import four_features_v3 as v3
from install_verified_candidate import running

PREVIOUS='c1b3ab17253df5977f5e6cc1036e5ac4f16cb8b4'
SITE=0xdb253;EXPECTED=bytes.fromhex('8be55dc390');SIZE=4096

def payload(base,origin,balanced=False,boost10=False):
 a=pe.Asm(origin)
 # Own frame sits below the original D9580 frame. [ebp] points to that frame;
 # EAX is its already calculated signed HP delta. No random/global-state edits.
 a.raw('55 8b ec 83 ec 40 53 56 57 89 45 fc 85 c0' if balanced else '55 8b ec 83 ec 38 53 56 57 89 45 fc 85 c0');a.jump('0f 89','done')
 a.raw('8b 55 00 8b 42 08 89 45 f8 85 c0');a.jump('0f 84','done')
 a.raw('81 38 d0 07 00 00');a.jump('0f 8c','done');a.raw('81 38 b8 0b 00 00');a.jump('0f 8d','done')
 a.raw('8b 42 0c 89 45 f4 85 c0');a.jump('0f 84','done')
 a.raw('ff 30');a.jump('e8',base+0xd8f50);a.raw('83 c4 04 83 f8 01');a.jump('0f 85','done')
 a.raw(b'\x68'+pe.u32(0x3f2));a.jump('e8',base+0xccee0);a.raw('83 c4 04 84 c0');a.jump('0f 84','done')
 # Only the native offensive co-op skill IDs and HP damage formula families.
 a.raw(b'\xa1'+pe.u32(base+0x1998a8));a.raw('83 f8 0b');a.jump('0f 8c','done');a.raw('83 f8 2a');a.jump('0f 8f','done')
 a.raw('68 b4 00 00 00 ff 75 f8');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','done')
 a.raw('8b 00 3d a7 02 00 00');a.jump('0f 8c','done');a.raw('3d b8 02 00 00');a.jump('0f 8f','done')
 for id in (0x2b4,0x2b5):a.raw(b'\x3d'+pe.u32(id));a.jump('0f 84','done')
 # Target defense. Native field getters return null when absent.
 a.raw('c7 45 f0 00 00 00 00')
 for attr in (0x26,0x29):
  a.raw(bytes([0x6a,attr])+bytes.fromhex('ff 75 f4'));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','def_'+str(attr));a.raw('8b 00 01 45 f0');a.label('def_'+str(attr))
 if balanced:
  # Player attacks use defense as a percentage and target luck as divisor.
  a.raw('c7 45 cc 00 00 00 00')
  for attr in (0x32,0x35):
   a.raw(bytes([0x6a,attr])+bytes.fromhex('ff 75 f4'));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','luck_'+str(attr));a.raw('8b 00 01 45 cc');a.label('luck_'+str(attr))
  a.raw('8b 45 cc 85 c0');a.jump('0f 8d','luck_abs');a.raw('f7 d8')
  a.label('luck_abs');a.raw('85 c0');a.jump('0f 85','luck_nonzero');a.raw('40')
  a.label('luck_nonzero');a.raw('3d 40 42 0f 00');a.jump('0f 8f','done');a.raw('69 c0 08 07 00 00 89 45 cc')
  a.raw('b8 64 00 00 00 2b 45 f0 85 c0');a.jump('0f 8d','scale_abs');a.raw('f7 d8')
  a.label('scale_abs');a.raw('3d 74 27 00 00');a.jump('0f 8f','done');a.raw('89 45 c8')
 a.raw(b'\x8b\x3d'+pe.u32(base+0x199894));a.raw('85 ff');a.jump('0f 84','done');a.raw('8b cf');a.jump('e8',base+0xcd2d0)
 a.raw('83 f8 02');a.jump('0f 8c','done');a.raw('83 f8 03');a.jump('0f 8f','done')
 a.raw('89 45 ec 33 db c7 45 e8 00 00 00 00 c7 45 e4 00 00 00 00 c7 45 e0 00 00 00 00 c7 45 dc 00 00 00 00')
 a.label('role');a.raw('53 8b cf');a.jump('e8',base+0xcd170);a.raw('85 c0');a.jump('0f 84','next');a.raw('8b 70 04 85 f6');a.jump('0f 84','next')
 a.raw('f7 46 28 04 00 00 00');a.jump('0f 85','next');a.raw('f7 46 30 0c 00 00 00');a.jump('0f 85','next')
 a.raw('6a 11 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','next');a.raw('83 38 00');a.jump('0f 8e','next')
 a.raw('c7 45 d8 00 00 00 00 c7 45 d4 00 00 00 00')
 for attr,local in ((0x1a,0xd8),(0x1d,0xd8),(0x20,0xd4),(0x23,0xd4)):
  a.raw(bytes([0x6a,attr,0x56]));a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','stat_'+str(attr));a.raw(bytes.fromhex('8b 00 01 45')+bytes([local]));a.label('stat_'+str(attr))
 # Validate and clamp signed negative totals; bound products well below int32.
 for local in (0xd8,0xd4):
  a.raw(bytes([0x81,0x7d,local])+pe.u32(1000000));a.jump('0f 8f','done')
  a.raw(bytes([0x83,0x7d,local,0]));a.jump('0f 8d','valid_'+str(local));a.raw(bytes([0xc7,0x45,local])+pe.u32(0));a.label('valid_'+str(local))
 # Growth contribution = floor((A+S)/6)+2*level.
 a.raw('8b 45 d8 03 45 d4 33 d2 b9 06 00 00 00 f7 f1 01 45 e4')
 a.raw('6a 05 56');a.jump('e8',base+0xddd60);a.raw('83 c4 08 85 c0');a.jump('0f 84','normal')
 a.raw('8b 00 85 c0');a.jump('0f 8e','normal');a.raw('3d 10 27 00 00');a.jump('0f 8f','done');a.raw('d1 e0 01 45 e4')
 # A/0.72 upper approximation = floor(25*A/18); native uses float0.72.
 # Include positive random maximum (+5%) and one point rounding allowance.
 a.label('normal')
 if balanced:
  # ceil(A*25*abs(100-defense)/(18*abs(luck)*100)), 64-bit numerator.
  a.raw('8b 45 d8 6b c0 19 f7 65 c8 f7 75 cc 85 d2');a.jump('0f 84','core_round');a.raw('40')
  a.label('core_round');a.raw('3d 40 42 0f 00');a.jump('0f 8f','done');a.raw('89 45 d0')
  # Native weapon classes: YueRu whip(class4) type2; WuHou staff(class5)
  # type4. Other uncritical direct weapon hits use type1's base/upper range.
  a.raw('6a 03 56');a.jump('e8',base+0xdd8b0);a.raw('83 c4 08 85 c0');a.jump('0f 84','direct_hit')
  a.raw('ff 30');a.jump('e8',base+0xddea0);a.raw('83 c4 04 81 3e d2 07 00 00');a.jump('0f 85','staff_test')
  a.raw('83 f8 04');a.jump('0f 85','direct_hit');a.raw('8b 45 d0 6b c0 28');a.jump('e9','reduced_hit')
  a.label('staff_test');a.raw('81 3e d3 07 00 00');a.jump('0f 85','direct_hit');a.raw('83 f8 05');a.jump('0f 85','direct_hit');a.raw('8b 45 d0 6b c0 24')
  a.label('reduced_hit');a.raw('33 d2 b9 64 00 00 00 f7 f1 83 c0 06');a.jump('e9','normal_sum')
  a.label('direct_hit');a.raw('8b 45 d0 33 d2 b9 14 00 00 00 f7 f1 03 45 d0 40');a.jump('e9','normal_sum')
 else:
  a.raw('8b 45 d8 6b c0 19 33 d2 b9 12 00 00 00 f7 f1 2b 45 f0 85 c0');a.jump('0f 8f','positive')
  a.raw('b8 01 00 00 00');a.jump('e9','normal_sum')
  a.label('positive');a.raw('89 45 d0 33 d2 b9 14 00 00 00 f7 f1 03 45 d0 40')
 a.label('normal_sum');a.raw('01 45 e0 ff 45 e8 3b 75 f8');a.jump('0f 85','next');a.raw('c7 45 dc 01 00 00 00')
 a.label('next');a.raw('43 3b 5d ec');a.jump('0f 8c','role')
 a.raw('83 7d dc 01');a.jump('0f 85','done');a.raw('83 7d e8 02');a.jump('0f 8c','done')
 # max(original move damage + growth, ceil(1.10 * party normal upper sum)).
 if balanced:
  # Floor1.10*normal upper + bounded growth bonus; never nerf a native move.
  # bonus=min(floor(growth/8),ceil(normal_upper/10)): total <=1.20*upper+1.
  a.raw('8b 45 e0 83 c0 09 33 d2 b9 0a 00 00 00 f7 f1 89 45 c4 8b 4d e4 c1 e9 03 3b c1');a.jump('0f 8e','bonus_bounded');a.raw('8b c1')
  a.label('bonus_bounded');a.raw('89 45 d0 8b 45 e0 6b c0 0b 83 c0 09 33 d2 b9 0a 00 00 00 f7 f1 03 45 d0 8b 4d fc f7 d9 3b c1');a.jump('0f 8d','store');a.raw('8b c1')
 else:
  a.raw('8b 45 e0 6b c0 0b 83 c0 09 33 d2 b9 0a 00 00 00 f7 f1 8b 4d fc f7 d9 03 4d e4 3b c1');a.jump('0f 8d','store');a.raw('8b c1')
 a.label('store')
 if boost10:a.raw('6b c0 0b 83 c0 05 33 d2 b9 0a 00 00 00 f7 f1')
 a.raw('f7 d8 89 45 fc')
 a.label('done');a.raw('8b 45 fc 5f 5e 5b 8b e5 5d 8b e5 5d c3')
 blob=a.finish();assert len(blob)<SIZE
 return {'blob':blob+bytes(SIZE-len(blob)),'origin':origin,'length':len(blob)}

def candidate():
 old,oldplan,_=v3.candidate()
 if hashlib.sha1(old).hexdigest()!=PREVIOUS:raise ValueError('Previous build differs')
 data=bytearray(old);origin=oldplan['scratch']-0x3f0;plan=payload(pe.IMAGE_BASE,origin)
 off=pe.rva_offset(old,origin-pe.IMAGE_BASE);data[off:off+SIZE]=plan['blob']
 # Withdraw old getter replacement: run the exact native formula first.
 off=pe.rva_offset(old,v3.coop.SITE);data[off:off+5]=v3.coop.EXPECTED
 off=pe.rva_offset(old,SITE)
 if old[off:off+5]!=EXPECTED:raise ValueError('Damage epilogue differs')
 data[off:off+5]=pe.branch(0xe9,pe.IMAGE_BASE+SITE,origin)
 return bytes(data),plan,old

def main():
 data,plan,old=candidate();folder=pe.ROOT/'补丁工作仓库/候选版本';target=hashlib.sha1(data).hexdigest()
 (folder/'NewPAL_Release.four-features-v4.exe').write_bytes(data)
 if '--install' not in sys.argv:print(json.dumps({'candidate_sha1':target,'helper_bytes':plan['length']}));return
 check=json.loads((folder/'coop-balance-v4-verification.json').read_text(encoding='utf-8'))
 if check['candidate_sha1']!=target or check['status']!='passed; gameplay acceptance pending':raise ValueError('Verification differs')
 exe=pe.ROOT/'NewPAL_Release.exe';source=exe.read_bytes()
 if source==data:print('Already installed');return
 if source!=old:raise ValueError('Installed EXE differs')
 if running():print('Game running; save and exit normally; no file changed');return
 backup=pe.ROOT/'修改exe备份/NewPAL_Release.exe.orig-before-four-features-v4-20261101'
 if backup.exists():
  if backup.read_bytes()!=source:raise ValueError('Backup collision')
 else:shutil.copy2(exe,backup)
 if backup.read_bytes()!=source:raise IOError('Backup readback differs')
 temp=exe.with_name(exe.name+'.four-features-v4-installing');created=False
 try:
  with temp.open('xb') as f:created=True;f.write(data);f.flush();os.fsync(f.fileno())
  if running() or exe.read_bytes()!=source:raise RuntimeError('Game/file changed; not replaced')
  os.replace(temp,exe)
  if exe.read_bytes()!=data:raise IOError('Installed readback differs')
 finally:
  if created:temp.unlink(missing_ok=True)
 report={'status':'installed and readback verified; gameplay acceptance pending','installed_sha1':target,'backup':str(backup),
  'formula':'max(native co-op damage + sum(floor((A+S)/6)+2L), ceil(1.10*sum(upper ordinary single-hit damage against same defense)))',
  'limits':'No crit/multi-hit/status modifiers in normal-hit comparison; native immunity and status settlement preserved',
  'retained':'native HP cost, no added MP cost, native targets/animations, all prior batch and released patches',
  'formal_log_and_collaboration_package':'deferred until acceptance'}
 (folder/'installation-four-features-v4.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
