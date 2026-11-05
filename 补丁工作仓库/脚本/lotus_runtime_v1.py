"""Append the lotus validation map; reuse controls/fog ABI and chain prior maps."""
import argparse,hashlib,json,struct
from pathlib import Path
import flash_v4 as pe
import luocha_return_runtime_v1 as shared

BASE='00a13b8f4fa34201dafb67f99639959c112e7698';OUT=pe.ROOT/'补丁工作仓库/候选版本/lotus-map-v1'
N=640*480;COUNT=2;TOTAL=N*COUNT;MAGIC=int.from_bytes(b'NLP1','little')
ALPHA_OFFSET=(0x10000+TOTAL+28+0xfff)&~0xfff;SIZE=(ALPHA_OFFSET+TOTAL+0xfff)&~0xfff
saved=shared.saved

def candidate(source=None):
 source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
 assert hashlib.sha1(source).hexdigest()==BASE,'Expected current installed map baseline'
 atlas=json.loads((OUT/'atlas.json').read_text(encoding='utf-8'));rows=atlas['rows'];assert [r['scene'] for r in rows]==[27,827] and [r['index'] for r in rows]==[0,1]
 h,o,secs=pe.pe_info(source);last=secs[-1];assert last[4]+last[3]==len(source)
 origin=pe.IMAGE_BASE+last[2]+last[3];previous=saved('luocha-return-v1')
 profile=dict(count=COUNT,size=SIZE,magic=MAGIC,namespace='np_lotus1_%d.dat',alpha_offset=ALPHA_OFFSET,out=OUT,previous=previous,exclusive_scene=True)
 p=shared.payload(origin,source,rows,atlas['links'],profile);out=bytearray(source);out.extend(p['blob']);patches={}
 old=saved('dungeon-map-v2');paint=saved('painted-map-v1')
 specs=[(old['symbols']['context'],pe.branch(0xe9,old['symbols']['context'],previous['symbols']['context_dispatch'])+b'\x90'*5,pe.branch(0xe9,old['symbols']['context'],p['symbols']['context_dispatch'])+b'\x90'*5),
  (paint['symbols']['frame'],pe.branch(0xe9,paint['symbols']['frame'],previous['symbols']['frame'])+b'\x90'*2,pe.branch(0xe9,paint['symbols']['frame'],p['symbols']['frame'])+b'\x90'*2),
  (paint['symbols']['write_sidecar'],pe.branch(0xe9,paint['symbols']['write_sidecar'],previous['symbols']['write_wrapper']),pe.branch(0xe9,paint['symbols']['write_sidecar'],p['symbols']['write_wrapper'])),
  (0x4b589a,pe.branch(0xe8,0x4b589a,previous['symbols']['load_wrapper']),pe.branch(0xe8,0x4b589a,p['symbols']['load_wrapper'])),
  (0x4691a0,pe.branch(0xe9,0x4691a0,previous['symbols']['reset_wrapper'])+b'\x90',pe.branch(0xe9,0x4691a0,p['symbols']['reset_wrapper'])+b'\x90')]
 for site,before,after in specs:
  at=pe.rva_offset(source,site-pe.IMAGE_BASE);assert source[at:at+len(before)]==before,('hook differs',hex(site));out[at:at+len(after)]=after;patches[site-pe.IMAGE_BASE]=(before,after)
 sh=o+struct.unpack_from('<H',source,h+20)[0]+(len(secs)-1)*40;size=last[3]+SIZE
 for at in [sh+8,sh+16]:struct.pack_into('<I',out,at,size)
 for at,value in [(o+56,last[2]+size),(o+4,struct.unpack_from('<I',source,o+4)[0]+SIZE),(o+64,0)]:struct.pack_into('<I',out,at,value)
 bridge=saved('map-test-v1');start=pe.rva_offset(source,bridge['origin']-0x400000);assert out[start:start+0x4000]==source[start:start+0x4000]
 p.update(patches=patches,header_offsets=[sh+8,sh+16,o+56,o+4,o+64],previous=previous,profile=profile)
 return bytes(out),p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);args=ap.parse_args()
 data,p=candidate(args.source.read_bytes() if args.source else None);(OUT/'NewPAL_Release.exe').write_bytes(data)
 report={k:v for k,v in p.items() if k not in ['blob','patches','profile']};report.update(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest(),status='candidate; native offline checks pending',pages=1,independent_fog_records=2,save_namespace='np_lotus1_%d.dat / NLP1',map_test_bridge_unchanged=True,art_status='native validation underlay; final painting pending',native_saves_modified=False)
 (OUT/'candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(candidate_sha1=report['candidate_sha1'],code_size=p['code_size'],append_bytes=SIZE),ensure_ascii=True))

if __name__=='__main__':main()
