"""Record scripted travel positions and feather the existing atlas perimeter."""
import argparse,hashlib,json,struct,shutil
from pathlib import Path
import numpy as np
from PIL import Image
import flash_v4 as pe
import lotus_runtime_v1 as prior
import luocha_return_runtime_v1 as shared

BASE='4fcbb543ea1ff27e4a7ad4965a85c1a242bd5e61'
OUT=pe.ROOT/'补丁工作仓库/候选版本/lotus-map-v2'
N=prior.N;TOTAL=prior.TOTAL;SIZE=prior.SIZE;COUNT=prior.COUNT;MAGIC=prior.MAGIC;saved=prior.saved

def assets():
 OUT.mkdir(exist_ok=True);dest=OUT/'Resource';dest.mkdir(exist_ok=True)
 atlas=json.loads((prior.OUT/'atlas.json').read_text(encoding='utf-8'))
 yy,xx=np.indices((480,640));distance=np.minimum.reduce([xx-28,527-xx,yy-108,388-yy])
 t=np.clip(distance/24,0,1);factor=t*t*(3-2*t);alphas=[];changes=[]
 for r in atlas['rows']:
  # Preserve numbered entrances and transport identifiers at full opacity.
  protected=np.zeros((480,640),dtype=bool)
  for port in r['ports'].values():
   x,y=port['page'];protected[max(0,y-8):min(480,y+9),max(0,x-8):min(640,x+9)]=True
  source=Image.open(prior.OUT/'Resource'/r['overlay']).convert('RGBA');old=np.array(source);new=old.copy()
  f=np.where(protected,1,factor);new[:,:,3]=np.rint(old[:,:,3].astype(float)*f).astype('uint8')
  assert np.array_equal(old[:,:,:3],new[:,:,:3])
  Image.fromarray(new).save(dest/r['overlay']);alphas.append(new[:,:,3].tobytes());changes.append(r['overlay'])
 for f in (prior.OUT/'Resource').glob('*.png'):
  if f.name not in changes:shutil.copy2(f,dest/f.name)
 (OUT/'alpha.bin').write_bytes(b''.join(alphas));(OUT/'atlas.json').write_text(json.dumps(atlas,ensure_ascii=False,indent=2),encoding='utf-8')
 manifest=[dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,changed=p.name in changes) for p in sorted(dest.glob('*.png'))]
 (OUT/'assets.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 before=Image.open(prior.OUT/'Resource'/atlas['rows'][0]['base']).convert('RGBA');after=before.copy()
 before.alpha_composite(Image.open(prior.OUT/'Resource'/atlas['rows'][0]['overlay']));after.alpha_composite(Image.open(dest/atlas['rows'][0]['overlay']))
 before.save(OUT/'荷花池_柔边前.png');after.save(OUT/'荷花池_柔边后.png');pair=Image.new('RGB',(1280,480));pair.paste(before,(0,0));pair.paste(after,(640,0));pair.save(OUT/'荷花池_四边柔化对照.png')
 report=dict(status='passed; appearance acceptance pending',changed_pngs=changes,feather_width_page_pixels=24,curve='smoothstep inward from original rectangle; native positions unchanged',source_rgb_unchanged=True,number_labels_protected=True,base_ui_unchanged=True,atlas_geometry_unchanged=True,links_unchanged=True)
 (OUT/'assets-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

def candidate(source=None):
 source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source;assert hashlib.sha1(source).hexdigest()==BASE
 old=saved('lotus-map-v1');atlas=json.loads((OUT/'atlas.json').read_text(encoding='utf-8'));origin=old['origin'];previous=saved('luocha-return-v1')
 profile=dict(count=COUNT,size=SIZE,magic=MAGIC,namespace='np_lotus1_%d.dat',alpha_offset=prior.ALPHA_OFFSET,out=prior.OUT,previous=previous,exclusive_scene=True)
 nativeold=shared.payload(origin,source,atlas['rows'],atlas['links'],profile)
 at=pe.rva_offset(source,origin-pe.IMAGE_BASE);assert source[at:at+SIZE]==nativeold['blob'],'Exact lotus v1 payload required'
 profile.update(out=OUT,sample_during_events=True);p=shared.payload(origin,source,atlas['rows'],atlas['links'],profile)
 data=bytearray(source);data[at:at+SIZE]=p['blob'];patches={};paint=saved('painted-map-v1');viewer=saved('dungeon-map-v2')
 for site,key,kind,length in [(viewer['symbols']['context'],'context_dispatch',0xe9,10),(paint['symbols']['frame'],'frame',0xe9,7),(paint['symbols']['write_sidecar'],'write_wrapper',0xe9,5),(0x4b589a,'load_wrapper',0xe8,5),(0x4691a0,'reset_wrapper',0xe9,6)]:
  expected=pe.branch(kind,site,old['symbols'][key])+bytes([0x90])*(length-5);offset=pe.rva_offset(source,site-pe.IMAGE_BASE)
  assert source[offset:offset+length]==expected,(hex(site),key)
  replacement=pe.branch(kind,site,p['symbols'][key])+bytes([0x90])*(length-5);data[offset:offset+length]=replacement;patches[site-pe.IMAGE_BASE]=(expected,replacement)
 assert len(data)==len(source)
 p.update(patches=patches,header_offsets=[],payload_span=[at,at+SIZE],previous=previous,profile=profile)
 return bytes(data),p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);args=ap.parse_args();assets();data,p=candidate(args.source.read_bytes() if args.source else None)
 (OUT/'NewPAL_Release.exe').write_bytes(data)
 report={k:v for k,v in p.items() if k not in ('blob','patches','profile')};report.update(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest(),status='candidate; offline verification pending',map_test_bridge_unchanged=True,save_namespace_unchanged=True,resources_changed=['np_lp_road_27_v1.png','np_lp_road_827_v1.png'])
 (OUT/'candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(sha1=report['candidate_sha1'],code_size=p['code_size'],exe_size_unchanged=True),ensure_ascii=True))
if __name__=='__main__':main()
