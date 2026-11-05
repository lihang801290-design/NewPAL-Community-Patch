"""Guarded parallel presentation of ordinary enemy death templates; candidate only."""
import hashlib,json,struct
import flash_v4 as pe
from research_group_death_v1 import script_record

BASE='a1f1d3f777684bfd84872412b57389ee5ab4d01a'
SIZE=0x4000;MAX=16
ENTRY=0xe6d1c;LAUNCH=0xecae2;INIT=0xd07a0

def templates():
 audit=json.loads((pe.ROOT/'补丁工作仓库/候选版本/group-death-research-v1.json').read_text(encoding='utf-8'))
 raw=(pe.ROOT/'gitem.dat').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=audit['resource_sha256']['gitem.dat']:raise ValueError('gitem source differs')
 rows=[]
 for id in audit['parallel_template_research']['compatible_script_ids']:
  rec=script_record(raw,id);cmd=rec['commands'];sound=next((x['args'][0] for x in cmd if x['opcode']=='0x7f002038'),0xffffffff)
  records=[raw[x['offset']:x['offset']+4+4*len(x['args'])] for x in cmd]
  rows.append((id,sound,records))
 if len(rows)!=60:raise ValueError('Template set differs')
 return rows

def payload(origin,reset_target,rows):
 a=pe.Asm(origin);symbols={};s=origin+0x1800;table=origin+0x2000;desc=origin+0x2400
 fields=['mode','total','started','parent_script','parent_actor','continuation','enemy_list','sound_count','batches','objects','sounds','fallbacks']
 d={n:s+i*4 for i,n in enumerate(fields)};d.update(records=s+0x100,sound_ids=s+0x200)
 def op(code,addr,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(addr)+suffix)
 def store(n,val):op('c7 05',d[n],pe.u32(val))
 def cmp(n,val):op('81 3d',d[n],pe.u32(val))
 def push(v):a.raw(b'\x68'+pe.u32(v))
 def call(v):a.jump('e8',v)
 def start(n):symbols[n]=a.pc;a.label(n)
 def get_attr(attr):push(attr);a.raw('56');call(0x4ddd60);a.raw('83 c4 08 85 c0')
 def native():a.raw('ff 75 0c ff 75 08');call(0x4ec840);a.raw('83 c4 08')
 def parent_restore():
  for n,addr in [('parent_script',0x531b88),('parent_actor',0x531bc0)]:op('a1',d[n]);op('a3',addr)

 start('reset');a.raw('9c 60');store('mode',0);a.raw('61 9d');a.jump('e9',reset_target)

 # EAX script ID -> table entry, or0. Byte-compare every loaded command; no ID-only trust.
 start('validate');a.raw('55 8b ec 83 ec 0c 53 56 57 c7 45 fc 00 00 00 00')
 a.raw(b'\xbe'+pe.u32(table)+b'\xb9'+pe.u32(len(rows)))
 a.label('find');a.raw('3b 06');a.jump('0f 84','found');a.raw('83 c6 10 49');a.jump('0f 85','find');a.jump('e9','validate_done')
 a.label('found');a.raw('89 75 fc 50');call(0x4cb7c0);a.raw('83 c4 04 85 c0');a.jump('0f 84','invalid')
 a.raw('8b 58 08 85 db');a.jump('0f 84','invalid');a.raw('8b 45 fc 8b 78 08 8b 07 3b 43 04');a.jump('0f 85','invalid')
 a.raw('89 45 f8 83 c7 04 8b 1b')
 a.label('record');a.raw('85 db');a.jump('0f 84','invalid');a.raw('8b 0f 83 f9 60');a.jump('0f 87','invalid')
 a.raw('3b 0b');a.jump('0f 85','invalid');a.raw('8b 73 04 85 f6');a.jump('0f 84','invalid')
 a.raw('83 c7 04 fc f3 a6');a.jump('0f 85','invalid');a.raw('8b 5b 10 ff 4d f8');a.jump('0f 85','record')
 a.raw('85 db');a.jump('0f 85','invalid');a.jump('e9','validate_done')
 a.label('invalid');a.raw('c7 45 fc 00 00 00 00')
 a.label('validate_done');a.raw('8b 45 fc 5f 5e 5b 8b e5 5d c3')

 start('preflight');a.raw('55 8b ec 83 ec 10 53 56 57');store('total',0)
 op('8b 3d',0x599898);a.raw('85 ff');a.jump('0f 84','pre_fail');a.raw('8b 47 04 83 f8 02');a.jump('0f 82','pre_fail')
 a.raw('83 f8 10');a.jump('0f 87','pre_fail');a.raw('89 45 fc')
 op('a1',0x59c510);a.raw('85 c0');a.jump('0f 84','queue_empty');a.raw('83 78 04 00');a.jump('0f 85','pre_fail')
 a.label('queue_empty')
 # Touch the parent cache first so preloading <=16 death scripts cannot evict it.
 op('a1',0x531b88);a.raw('85 c0');a.jump('0f 88','pre_fail');a.raw('50');call(0x4cb7c0);a.raw('83 c4 04 85 c0');a.jump('0f 84','pre_fail')
 a.raw('31 db')
 a.label('scan');a.raw('53 8b cf');call(0x4cd170);a.raw('85 c0');a.jump('0f 84','pre_fail');a.raw('8b 70 04 85 f6');a.jump('0f 84','pre_fail')
 get_attr(0x11);a.jump('0f 84','pre_fail');a.raw('83 38 00');a.jump('0f 85','scan_next')
 a.raw('f7 46 28 04 00 00 00');a.jump('0f 85','pre_fail');a.raw('f7 46 50 01 00 00 00');a.jump('0f 85','pre_fail')
 a.raw('83 7e 04 03');a.jump('0f 85','pre_fail');a.raw('8b 06 85 c0');a.jump('0f 8e','pre_fail');a.raw('3d d0 07 00 00');a.jump('0f 83','pre_fail')
 a.raw('83 7e 70 00');a.jump('0f 84','pre_fail')
 get_attr(0xb6);a.jump('0f 84','pre_fail');a.raw('8b 00 3d ff ef 00 00');a.jump('0f 85','have_id');a.raw('b8 40 1f 00 00')
 a.label('have_id');call('validate');a.raw('85 c0');a.jump('0f 84','pre_fail')
 # Save validated object, concrete actor ID, resolved script ID and sound.
 a.raw('50');op('a1',d['total']);a.raw('c1 e0 04 05'+pe.u32(d['records']).hex()+' 8b d0 58')
 a.raw('89 32 8b 0e 89 4a 04 8b 08 89 4a 08 8b 48 04 89 4a 0c');op('ff 05',d['total'])
 a.label('scan_next');a.raw('43 3b 5d fc');a.jump('0f 82','scan')
 op('a1',d['total']);a.raw('83 f8 02');a.jump('0f 83','pre_done')
 a.label('pre_fail');store('total',0);a.raw('31 c0')
 a.label('pre_done');a.raw('5f 5e 5b 8b e5 5d c3')

 # Called ONLY at EC840's death-script launch, not at general CB710 dispatch.
 start('launch');a.raw('55 8b ec 9c 60');cmp('mode',1);a.jump('0f 85','launch_native')
 op('a1',d['started']);op('3b 05',d['total']);a.jump('0f 83','launch_abort')
 a.raw('c1 e0 04 05'+pe.u32(d['records']).hex()+' 8b f8 8b 5f 04');op('3b 1d',0x531bc0);a.jump('0f 85','launch_abort')
 a.raw('8b 45 08 3b 47 08');a.jump('0f 85','launch_abort');a.raw('8b 37')
 for v in (0,7,0,0,0):push(v)
 a.raw('53');push(3);call(0x4ee540);a.raw('83 c4 1c f7 46 28 00 00 00 08');a.jump('0f 84','launch_abort')
 push(1);push(0);a.raw('53');call(0x4eebd0);a.raw('83 c4 0c 8b 5f 0c 83 fb ff');a.jump('0f 84','launched')
 op('8b 0d',d['sound_count']);a.raw(b'\xbe'+pe.u32(d['sound_ids']))
 a.raw('85 c9');a.jump('0f 84','sound_new')
 a.label('sound_seen');a.raw('3b 1e');a.jump('0f 84','launched');a.raw('83 c6 04 49');a.jump('0f 85','sound_seen')
 a.label('sound_new');a.raw('89 1e');op('ff 05',d['sound_count']);a.raw('53');call(0x4f3280);a.raw('83 c4 04');op('ff 05',d['sounds'])
 a.label('launched');op('ff 05',d['started']);op('ff 05',d['objects']);a.raw('61 9d b8 01 00 00 00 8b e5 5d c3')
 a.label('launch_abort');store('mode',0);op('ff 05',d['fallbacks'])
 a.label('launch_native');a.raw('61 9d 8b e5 5d');a.jump('e9',0x4cb710)

 start('entry');a.raw('55 8b ec 8d 64 24 fc 9c 60')
 a.raw('83 7d 08 00');a.jump('0f 85','native')
 cmp('mode',2);a.jump('0f 84','waiting')
 a.raw('81 7d 0c 40 06 00 00');a.jump('0f 85','native')
 op('83 3d',0x599814,b'\x06');a.jump('0f 83','native')
 call('preflight');a.raw('85 c0');a.jump('0f 84','native')
 for n,addr in [('parent_script',0x531b88),('parent_actor',0x531bc0),('enemy_list',0x599898)]:op('a1',addr);op('a3',d[n])
 a.raw('8b 45 0c');op('a3',d['continuation']);store('mode',1);store('started',0);store('sound_count',0);op('ff 05',d['batches'])
 a.label('collect');op('a1',d['started']);a.raw('89 45 fc');native();cmp('mode',1);a.jump('0f 85','entry_done')
 op('a1',d['started']);a.raw('2b 45 fc 83 f8 01');a.jump('0f 85','entry_abort')
 parent_restore();op('a1',d['started']);op('3b 05',d['total']);a.jump('0f 82','collect')
 store('mode',2);a.jump('e9','yield')
 a.label('waiting')
 for n,addr in [('parent_script',0x531b88),('enemy_list',0x599898)]:op('a1',addr);op('3b 05',d[n]);a.jump('0f 85','entry_abort_native')
 a.raw('8b 45 0c');op('3b 05',d['continuation']);a.jump('0f 85','entry_abort_native')
 op('a1',0x59c510);a.raw('85 c0');a.jump('0f 84','complete');a.raw('83 78 04 00');a.jump('0f 85','yield')
 a.label('complete');store('mode',0);a.jump('e9','native')
 a.label('entry_abort_native');store('mode',0);op('ff 05',d['fallbacks']);a.jump('e9','native')
 a.label('entry_abort');store('mode',0);op('ff 05',d['fallbacks']);a.jump('e9','entry_done')
 a.label('yield');op('83 0d',0x59937c,b'\x01');a.jump('e9','entry_done')
 a.label('native');native()
 a.label('entry_done');a.raw('61 9d 8b e5 5d c3')
 blob=a.finish();assert len(blob)<0x1800
 tabledata=bytearray();rawdesc=bytearray()
 for id,sound,commands in rows:
  tabledata+=pe.u32(id)+pe.u32(sound)+pe.u32(desc+len(rawdesc))+pe.u32(0)
  rawdesc+=pe.u32(len(commands))
  for command in commands:rawdesc+=pe.u32(len(command))+command
 assert len(tabledata)<=0x400 and 0x2400+len(rawdesc)<=SIZE
 blob+=bytes(0x2000-len(blob))+tabledata;blob+=bytes(0x2400-len(blob))+rawdesc;blob+=bytes(SIZE-len(blob))
 return dict(blob=blob,origin=origin,symbols=symbols,state=d,table=table,code_size=len(a.buf),templates=len(rows))

def candidate(source=None):
 source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
 if hashlib.sha1(source).hexdigest()!=BASE:raise ValueError('Expected accepted v4 baseline')
 h,o,sections=pe.pe_info(source);last=sections[-1]
 if last[0]!=b'.palhov' or last[1]!=0x4000 or last[3]!=0x4000 or last[4]+last[3]!=len(source):raise ValueError('Last section differs')
 reset_off=pe.rva_offset(source,INIT);old_reset=source[reset_off:reset_off+5]
 if old_reset[0]!=0xe9:raise ValueError('Existing initialization chain differs')
 reset_target=pe.IMAGE_BASE+INIT+5+int.from_bytes(old_reset[1:],'little',signed=True)
 plan=payload(pe.IMAGE_BASE+last[2]+last[3],reset_target,templates());out=bytearray(source);out.extend(plan['blob'])
 hdr=o+struct.unpack_from('<H',source,h+20)[0]+(len(sections)-1)*40
 struct.pack_into('<I',out,hdr+8,0x8000);struct.pack_into('<I',out,hdr+16,0x8000)
 struct.pack_into('<I',out,o+56,last[2]+0x8000);struct.pack_into('<I',out,o+4,struct.unpack_from('<I',source,o+4)[0]+SIZE);struct.pack_into('<I',out,o+64,0)
 patches={ENTRY:(pe.branch(0xe8,pe.IMAGE_BASE+ENTRY,0x4ec840),pe.branch(0xe8,pe.IMAGE_BASE+ENTRY,plan['symbols']['entry'])),
  LAUNCH:(pe.branch(0xe8,pe.IMAGE_BASE+LAUNCH,0x4cb710),pe.branch(0xe8,pe.IMAGE_BASE+LAUNCH,plan['symbols']['launch'])),
  INIT:(old_reset,pe.branch(0xe9,pe.IMAGE_BASE+INIT,plan['symbols']['reset']))}
 for site,(old,new) in patches.items():
  off=pe.rva_offset(source,site)
  if source[off:off+len(old)]!=old:raise ValueError('Patch site differs '+hex(site))
  out[off:off+len(new)]=new
 assert out[pe.rva_offset(out,0xecb90):][:9]==bytes.fromhex('e9 e5 fc ff ff 90 90 90 90')
 plan.update(patches=patches,reset_target=reset_target);return bytes(out),plan

if __name__=='__main__':
 data,p=candidate();path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.group-death-v1.exe';path.write_bytes(data)
 report={k:v for k,v in p.items() if k not in ('blob','patches')};report.update(status='candidate; offline and gameplay validation pending',baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest())
 path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
