"""Read-only exported map catalogue plus original flag planes for test landing checks."""
import hashlib,json,sqlite3,struct,sys,zipfile
from pathlib import Path
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP
import flash_v4 as pe
from map_test_catalog_rules_v1 import testable,display_name,NON_MAP_SCENES

OUT=pe.ROOT/'补丁工作仓库/地图开发/地图测试工具'

def main():
 OUT.mkdir(exist_ok=True);work=pe.ROOT/'补丁工作仓库';c=sqlite3.connect((work/'地图开发/地图索引/scene_export_index.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 raw_scenes=[dict(r) for r in c.execute('SELECT * FROM scenes WHERE map_exists=1 ORDER BY scene_id')];scenes=[s for s in raw_scenes if testable(s['scene_id'])];resources={r['resource_id']:dict(r) for r in c.execute('SELECT * FROM resources')};c.close()
 exe=(pe.ROOT/'NewPAL_Release.exe').read_bytes();u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x400000);u.mem_map(0x800000,0x200000)
 for _,_,rva,rs,rp in pe.pe_info(exe)[2]:u.mem_write(0x400000+rva,exe[rp:rp+rs])
 grids={};rows=[]
 with zipfile.ZipFile(OUT/'原生格数据.zip','w',zipfile.ZIP_DEFLATED) as z:
  for s in scenes:
   id=s['scene_id'];rid=s['map_resource_id'];w,h=s['grid_width'],s['grid_height'];resource=resources[rid]
   if rid not in grids:
    with (pe.ROOT/resource['archive']).open('rb') as f:
     f.seek(resource['archive_offset']);head=f.read(0x404);fo,fs=struct.unpack_from('<II',head,12);f.seek(resource['archive_offset']+fo);packed=f.read(fs)
    assert len(packed)<0x10000 and w*h*4<0x100000
    u.mem_write(0x850000,packed);sp=0x9ef000
    for i,v in enumerate((0x9ff000,0x850000,len(packed),0x900000,0x840000)):u.mem_write(sp+i*4,pe.u32(v))
    u.reg_write(UC_X86_REG_ESP,sp);u.emu_start(0x4a5490,0x9ff000,count=5000000)
    assert u.reg_read(UC_X86_REG_EIP)==0x9ff000 and struct.unpack('<I',u.mem_read(0x840000,4))[0]==w*h*4
    data=bytes(u.mem_read(0x900000,w*h*4));z.writestr(f'{rid}.bin',data);grids[rid]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
   image=work/s['artwork_image'] if s['artwork_image'] else None
   rows.append(dict(scene_id=id,resource_id=rid,name=display_name(id,rid,s['native_name']),native_name=s['native_name'],width=w,height=h,category=s['category_name'],
    image=s['artwork_image'] if image and image.is_file() else None,grid_sha256=grids[rid]['sha256'],grid_bytes=w*h*4))
 report=dict(version=2,scene_count=len(rows),resource_count=len(grids),raw_indexed_scene_count=len(raw_scenes),excluded_scene_ids=sorted(NON_MAP_SCENES),excluded_reason='user confirmed835-877 are illustrations/credits rather than playable maps',world_units_per_grid=16,
  landing_rule='candidate: !(flags&0x60800000), flags&0xf000 !=0, flags&0xff==0; dynamic object/script blockers need in-game confirmation',scenes=rows)
 (OUT/'可定位地图.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(scenes=len(rows),resources=len(grids),out=str(OUT)),ensure_ascii=True))

if __name__=='__main__':main()
