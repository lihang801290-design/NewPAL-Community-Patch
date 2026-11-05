"""Offline shared-UI review only. Never installs or rebinds native geometry."""
from pathlib import Path
import hashlib,json,math,shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageEnhance

W=Path(__file__).resolve().parents[1];ROOT=W.parent;OUT=W/'候选版本/map-visual-v3-preview';S=4
REF=W/'地图开发/界面模板/梦境基准_v3'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def font(size):return ImageFont.truetype('C:/Windows/Fonts/simkai.ttf',size*S)

def components():
 sheet=Image.open(OUT/'共享标题与提示_生图原稿.png').convert('RGBA');a=np.array(sheet);components={}
 # Only connected lettering bands, discard any weak alpha speckles outside ink.
 for name,(lo,hi),height in [('lotus',(95,305),28),('front',(345,545),28),('back',(590,790),28),('footer',(850,995),10)]:
  part=a[lo:hi].copy();ink=(part[:,:,3]>150)&(part[:,:,:3].max(2)<160)
  counts=ink.sum(1);ys=np.flatnonzero(counts>12);assert len(ys)
  xs=np.flatnonzero(ink[ys[0]:ys[-1]+1].sum(0)>3);assert len(xs)
  part=part[ys[0]:ys[-1]+1,xs[0]:xs[-1]+1];ink=(part[:,:,3]>100)&(part[:,:,:3].max(2)<160)
  part[:,:,3]=np.where(ink,part[:,:,3],0)
  if name=='footer':part[:,:,:3]=[104,78,49]
  im=Image.fromarray(part);im=im.resize((round(im.width*height/im.height),height),Image.Resampling.LANCZOS)
  components[name]=im;im.save(OUT/f'共享组件_{name}.png')
 assert components['footer'].width<380
 return components

def paper_base(parts,title=None,transport=False,state=None):
 im=Image.open(REF/'00_梦境已安装纸面_原样.png').convert('RGBA')
 if title:
  # Local compositor patch on the existing editable UI; never regenerate a page.
  box=(222,10,412,44);patch=im.crop((222,225,412,259));mask=Image.new('L',patch.size,255)
  im.paste(patch,box,mask);glyph=parts[title];im.alpha_composite(glyph,(320-glyph.width//2,14))
 # The unimplemented quest-target slot becomes the same connection-note slot.
 box=(566,162,632,198);im.paste(im.crop((480,162,546,198)),box)
 high=Image.new('RGBA',(640*S,480*S));d=ImageDraw.Draw(high)
 for y,text in [(175,'同號相連'),(187,'虛線乘蓮' if transport else '虛線換圖')]:
  d.text((597*S,y*S),text,font=font(9),fill='#80664b',anchor='mm')
 if state:d.text((619*S,51*S),state,font=font(9),fill='#80664b',anchor='rm')
 im.alpha_composite(high.resize((640,480),Image.Resampling.LANCZOS))
 footer=parts['footer'];im.alpha_composite(footer,(320-footer.width//2,459))
 return im

def captions(im,lines):
 high=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(high)
 for i,line in enumerate(lines):d.text((320*S,(424+(i-(len(lines)-1)/2)*14)*S),line,font=font(10),fill='#67492b',anchor='mm')
 out=im.copy();out.alpha_composite(high.resize((640,480),Image.Resampling.LANCZOS));return out

def lotus_terrain():
 # RGB is only presentation. These color choices never infer collision/roads.
 native=Image.open(OUT/'inputs/荷花_已核定位_无UI地形.png').convert('RGBA');a=np.array(native);rgb=a[:,:,:3].astype(float)
 water=(rgb[:,:,2]>rgb[:,:,0]*1.2+4)&(rgb[:,:,2]>rgb[:,:,1]*1.05+2)&(a[:,:,3]>0)
 land=(~water)&(a[:,:,3]>0)
 core=Image.fromarray(land.astype('uint8')*255);wash=np.array(core.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4))).astype(float)/255
 alpha=np.where(land,255,np.rint(wash*84)).astype('uint8');alpha[a[:,:,3]==0]=0
 toned=np.array(ImageEnhance.Color(native.convert('RGB')).enhance(.55)).astype(float)
 toned=toned*.74+np.array([230,213,176])*.26
 toned[water]=[90,113,119]
 result=np.dstack([np.clip(toned,0,255).astype('uint8'),alpha]);im=Image.fromarray(result)
 im.save(OUT/'荷花_原生位置_局部水纹透明层.png')
 return im,land

def markers(im,row):
 high=im.resize((2560,1920),Image.Resampling.NEAREST);d=ImageDraw.Draw(high);nf=ImageFont.truetype('C:/Windows/Fonts/timesbd.ttf',11*S)
 for key,p in row['ports'].items():
  x,y=p['page'];n=str(key).split(':')[-1];box=((x-6)*S,(y-6)*S,(x+6)*S,(y+6)*S)
  d.rounded_rectangle(box,radius=2*S,fill='#f4e5c4',outline='#593c25',width=S);d.text((x*S,y*S),n,font=nf,fill='#593c25',anchor='mm')
 return high.resize((640,480),Image.Resampling.LANCZOS)

def links(atlas):
 colors=['#705138','#536f78','#767345','#905e50'];images=[]
 for link in atlas['links']:
  n=link['number'];color=colors[(n-1)%4];dash,gap=[(4,3),(7,3),(2,3)][((n-1)//4)%3];phase=0
  im=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(im)
  for a,b in zip(link['points'],link['points'][1:]):
   length=math.dist(a,b)
   if not length:continue
   for s in np.arange(0,length,.2):
    if (phase+s)%(dash+gap)<dash:
     t=s/length;x=(a[0]+(b[0]-a[0])*t)*S;y=(a[1]+(b[1]-a[1])*t)*S
     d.ellipse((x-1.7,y-1.7,x+1.7,y+1.7),fill=color)
   phase+=length
  im=im.resize((640,480),Image.Resampling.LANCZOS);images.append((link,im));im.save(OUT/'Resource'/link['file'])
 return images

def fog_layer(im,points):
 yy,xx=np.indices((480,640));mask=np.zeros((480,640))
 for x,y in points:
  t=np.clip((60-np.hypot(xx-x,yy-y))/24,0,1);mask=np.maximum(mask,t*t*(3-2*t))
 a=np.array(im);a[:,:,3]=np.rint(a[:,:,3]*mask).astype('uint8');return Image.fromarray(a)

def preview(name,base,overlays,parts,point,partial_points):
 full=base.copy();terrain=Image.new('RGBA',(640,480))
 for im,xy in overlays:terrain.alpha_composite(im,xy)
 full.alpha_composite(terrain);player=Image.open(ROOT/'Resource/np_lr_player_v1.png').convert('RGBA')
 full.alpha_composite(player,(point[0]-12,point[1]-12));full.save(OUT/f'{name}_完整.png')
 partial=base.copy();partial.alpha_composite(fog_layer(terrain,partial_points));partial.alpha_composite(player,(point[0]-12,point[1]-12));partial.save(OUT/f'{name}_局部探索.png')
 full.resize((1280,960),Image.Resampling.LANCZOS).save(OUT/f'{name}_完整_2倍.png')
 return full,partial

def return_base(row,atlas,style,parts):
 base=paper_base(parts,'front' if row['page']==0 else 'back',state=row['name'])
 old=Image.open(ROOT/'Resource'/row['base']).convert('RGBA')
 for plate in style['nameplates']:
  if plate['page']==row['page']:
   box=tuple(plate['box']);base.alpha_composite(old.crop(box),(box[0],box[1]))
 return captions(base,style['captions'][str(row['scene'])])

def main():
 (OUT/'Resource').mkdir(exist_ok=True);parts=components();pages=[];checks={}
 # Dream geometry/ink remains as installed; only shared UI/footnote changes.
 dream=paper_base(parts);dream.save(OUT/'Resource/np_map_fog_base_v1.png');reg=load(W/'候选版本/painted-map-v1/registration.json')
 layers=[(Image.open(ROOT/'Resource'/r['file']).convert('RGBA'),(r['x'],r['y'])) for r in reg['layers']]
 pages.append(preview('01_梦境',dream,layers,parts,(531,371),[(531,371),(491,374),(451,364)]))
 # Return-cave geometry, terrain and existing seal labels are retained.
 atlas=load(W/'候选版本/luocha-return-v1/atlas.json');style=load(W/'候选版本/luocha-style-v2-20261104/style-verification.json')
 for row in atlas['rows']:
  base=return_base(row,atlas,style,parts);base.save(OUT/'Resource'/row['base'])
 for sid in [503,511,506,514,508,516]:
  r=next(r for r in atlas['rows'] if r['scene']==sid);base=Image.open(OUT/'Resource'/r['base']).convert('RGBA');layers=[]
  for row in atlas['rows']:
   if row['page']==r['page'] and (not row['family'] or row['scene']==sid):layers.append((Image.open(ROOT/'Resource'/row['overlay']).convert('RGBA'),(0,0)))
  for link in atlas['links']:
   if link['page']==r['page'] and all(not atlas['rows'][link[e]]['family'] or atlas['rows'][link[e]]['scene']==sid for e in ['a','b']):layers.append((Image.open(ROOT/'Resource'/link['file']).convert('RGBA'),(0,0)))
  port=next(iter(r['ports'].values()))['page'];name=f'02_羅剎{["前","後"][r["page"]]}_{sid}'
  result=preview(name,base,layers,parts,tuple(port),[tuple(port)])
  if sid in [503,511]:pages.append(result)
 # Lotus alpha changes preserve native coordinates, never use drifting art.
 atlas=load(W/'候选版本/lotus-map-v2/atlas.json');terrain,land=lotus_terrain();linkimages=links(atlas)
 for row in atlas['rows']:
  base=captions(paper_base(parts,'lotus',transport=True),['14 ← 仙靈島岩徑　　15 → 桃樹林','蓮葉路線隨機關狀態變化']);base.save(OUT/'Resource'/row['base'])
  overlay=markers(terrain,row);overlay.save(OUT/'Resource'/row['overlay'])
  if row['scene']==27:pages.append(preview('03_荷花池',base,[(overlay,(0,0))]+[(im,(0,0)) for link,im in linkimages[:13]],parts,(87,353),[(63,363),(76,359),(87,353)]))
 # Review montage is presentation, not a claim of runtime exploration state.
 montage=Image.new('RGB',(1280,1920))
 for i,(full,partial) in enumerate(pages):montage.paste(full,(0,i*480));montage.paste(partial,(640,i*480))
 montage.save(OUT/'四页统一预览_左完整右局部.png')
 allfloors=Image.new('RGB',(1280,1440))
 for i,sid in enumerate([503,511,506,514,508,516]):
  r=next(r for r in load(W/'候选版本/luocha-return-v1/atlas.json')['rows'] if r['scene']==sid);name=f'02_羅剎{["前","後"][r["page"]]}_{sid}_完整.png';allfloors.paste(Image.open(OUT/name),(i%2*640,i//2*480))
 allfloors.save(OUT/'再入罗刹_六层文字排版检查.png')
 # Same exact footer component, placement and untouched primary UI evidence.
 fbox=(320-parts['footer'].width//2,459,320-parts['footer'].width//2+parts['footer'].width,469)
 crops=[np.array(Image.open(OUT/name).convert('RGBA').crop(fbox)) for name in ['01_梦境_完整.png','02_羅剎前_503_完整.png','02_羅剎後_511_完整.png','03_荷花池_完整.png']]
 footer_delta=max(int(np.abs(crops[0].astype(int)-a.astype(int)).max()) for a in crops[1:])
 assert footer_delta<=4,'Shared footer differs beyond subpixel compositing fringe'
 baseline=np.array(Image.open(REF/'00_梦境已安装纸面_原样.png').convert('RGBA'));sample=np.array(paper_base(parts,'lotus',transport=True))
 assert np.array_equal(baseline[96:153,567:631],sample[96:153,567:631]),'Original legend altered'
 report=dict(status='complete visual previews ready; user approval and gameplay pending',installed=False,game_files_changed=False,footer=dict(text='M / Back：地圖    Esc / B：關閉',height=10,y=459,shared_component_and_position=True,composite_background_max_channel_difference=footer_delta),dream_legend_original_pixels=True,return_rows=17,return_layer_previews=6,geometry_and_ports='existing native geometry retained; no registration changes',lotus_generation='generated terrain quarantined due drift; native-position display matte used instead',lotus_display_matte='visual blue-water suppression only, not collision/path qualification',lotus_art_status='native geometry plus restrained color/water presentation; generated hand-drawn terrain NOT certified',mock_exploration=True,mock_player_markers=True,base_exe_sha1=hashlib.sha1((ROOT/'NewPAL_Release.exe').read_bytes()).hexdigest(),prompts='生成提示词.json',imagegen_mode='built-in',resource_manifest=[dict(file=p.name,sha256=sha(p)) for p in sorted((OUT/'Resource').glob('*.png'))])
 save(OUT/'preview-verification.json',report);print(json.dumps(dict(preview_pages=len(pages),return_layers=6,resources=len(report['resource_manifest']),installed=False,output=str(OUT)),ensure_ascii=True))
if __name__=='__main__':main()
