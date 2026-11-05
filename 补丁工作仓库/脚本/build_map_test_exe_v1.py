"""Build a single-file Windows tool; preview sampling matches the original Tk UI."""
import argparse,hashlib,json,math,shutil,struct,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
import pefile
import flash_v4 as pe
from settings_toggle_v1 import imports
from portable_map_bridge_v1 import GATES,FRAME_RVA,SAVE_RVA
from map_test_bridge_v1 import dimensions

ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'补丁工作仓库'
DATA=WORK/'地图开发/地图测试工具';OUT=WORK/'候选版本/map-test-exe-v1'
STAGE=OUT/'bundle';NAME='新仙剑地图传送器'

def profiles():
 result={}
 for file,label,expected in [
  (ROOT/'NewPAL_Release.exe.orig-ufa','Steam原版','6052097e0cf03216f41efffbae74844badb73493'),
  (WORK/'发布补丁/NewPAL_协作开发包_20261102_v5/NewPAL_Release.exe','正式补丁v5','0b08e7ef78f101fd19a4b7e0d823903724e1c5db')]:
  data=file.read_bytes();sha=hashlib.sha1(data).hexdigest();assert sha==expected
  def read(rva,n):at=pe.rva_offset(data,rva);return data[at:at+n]
  frame=read(FRAME_RVA,5);assert frame[0]==0xe8
  save=read(SAVE_RVA,5);assert save==bytes.fromhex('55 8b ec 6a ff')
  gates=[]
  for i,(rva,n,skip) in enumerate(GATES):
   old=read(rva,n);target=None
   if old[0]==0xe9:target=rva+5+int.from_bytes(old[1:5],'little',signed=True)
   else:assert old==[bytes.fromhex('85c00f84c2010000'),bytes.fromhex('668915e8285600'),bytes.fromhex('66a3e8285600'),bytes.fromhex('668915e8285600')][i]
   gates.append(dict(old=old.hex(),normal_target_rva=target))
  image=pefile.PE(data=data);relocs=[e.rva for block in getattr(image,'DIRECTORY_ENTRY_BASERELOC',[]) for e in block.entries if e.type==3]
  result[sha]=dict(label=label,frame_old=frame.hex(),frame_target_rva=FRAME_RVA+5+int.from_bytes(frame[1:],'little',signed=True),save_old=save.hex(),gates=gates,ticks_iat_rva=imports(data)['SDL_GetTicks']-0x400000,loader_signature=read(0x9dc40,32).hex(),relocations=relocs,image_size=image.OPTIONAL_HEADER.SizeOfImage)
 return result

def prepare():
 OUT.mkdir(parents=True,exist_ok=True);target=STAGE/'work/地图开发/地图测试工具';target.mkdir(parents=True,exist_ok=True)
 ps=profiles();(DATA/'支持版本.json').write_text(json.dumps(ps,ensure_ascii=False,indent=2),encoding='utf-8');(DATA/'运行桥地图尺寸.bin').write_bytes(dimensions()[0])
 for name in ['支持版本.json','运行桥地图尺寸.bin','原生格数据.zip']:shutil.copy2(DATA/name,target/name)
 catalog=json.loads((DATA/'可定位地图.json').read_text(encoding='utf-8-sig'));scales={};source_bytes=0;preview_bytes=0
 for row in catalog['scenes']:
  path=row['image']
  if not path:continue
  if path not in scales:
   source=WORK/path;dest=STAGE/'work'/path;dest.parent.mkdir(parents=True,exist_ok=True)
   with Image.open(source) as im:
    factor=max(1,math.ceil(im.width/780),math.ceil(im.height/570))
    # Exact [0,factor,2*factor,...] sampling, same as Tk.PhotoImage.subsample.
    sampled=Image.fromarray(np.asarray(im.convert('RGBA'))[::factor,::factor]);sampled.save(dest,optimize=True)
   scales[path]=factor;source_bytes+=source.stat().st_size;preview_bytes+=dest.stat().st_size
  row['preview_scale']=scales[path]
 (target/'可定位地图.json').write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf-8')
 for folder in ['map-test-v1','dream-map-isolation-v1','luocha-return-v1']:
  dest=STAGE/'work/候选版本'/folder;dest.mkdir(parents=True,exist_ok=True)
  for name in ['candidate.json','verification.json']:shutil.copy2(WORK/'候选版本'/folder/name,dest/name)
 report=dict(date='2026-11-04',source_preview_bytes=source_bytes,bundled_preview_bytes=preview_bytes,preview_count=len(scales),scene_count=len(catalog['scenes']),sampling='exact Tk integer subsample; original coordinate scale preserved; source artwork unchanged',profiles={sha:row['label'] for sha,row in ps.items()})
 (OUT/'build-input.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True),flush=True)

def refresh_bridge_metadata():
 for folder in ['map-test-v1','dream-map-isolation-v1','luocha-return-v1','lotus-map-v1','story-motion-v2','story-motion-v3','lotus-map-v2','map-art-runtime-v6','map-nameplates-v1']:
  source=WORK/'候选版本'/folder
  if not (source/'candidate.json').exists() or not (source/'verification.json').exists():continue
  dest=STAGE/'work/候选版本'/folder;dest.mkdir(parents=True,exist_ok=True)
  for name in ['candidate.json','verification.json']:shutil.copy2(source/name,dest/name)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--use-prepared',action='store_true');args=ap.parse_args()
 if not args.use_prepared:prepare()
 if args.prepare:return
 refresh_bridge_metadata()
 subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--noupx','--name',NAME,'--paths',str(WORK/'脚本'),'--add-data',str(STAGE/'work')+';work','--distpath',str(DATA),'--workpath',str(OUT/'build'),'--specpath',str(OUT),str(WORK/'脚本/map_test_exe_entry_v1.py')],check=True)
 exe=DATA/(NAME+'.exe');report=json.loads((OUT/'build-input.json').read_text(encoding='utf-8'));report.update(exe=str(exe.relative_to(ROOT)),exe_bytes=exe.stat().st_size,exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
 (OUT/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True),flush=True)

if __name__=='__main__':main()
