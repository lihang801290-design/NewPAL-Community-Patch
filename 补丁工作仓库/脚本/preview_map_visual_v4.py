"""Direct-source compositing: remove pasted paper, align labels, clarify links.

Offline PNG review only. No Photoshop/PSD export, installation, or geometry edits.
"""
from pathlib import Path
import hashlib,json,math,shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageEnhance
import preview_map_visual_v3 as core

W=core.W;ROOT=core.ROOT;PREV=core.OUT;OUT=W/'候选版本/map-visual-v4-preview';S=4
HI_PAPER=W/'地图开发/逐图开发/01_罗刹山洞（首次梦中进入）/美术预览/标题修订_v1/底纸_线路图.png'
RAWS={};ORIGINAL=None;CLEAN=None;FLAME=None;SEAL=None;PLATES={};LABEL_CHECKS=[];LINK_CHECKS=[];LINK_HIGH={}
COLORS=['#74502e','#416d78','#69713c','#96554a']
ORIGINAL_PREVIEW=core.preview
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def font(n,number=False):return ImageFont.truetype('C:/Windows/Fonts/timesbd.ttf' if number else 'C:/Windows/Fonts/simkai.ttf',n*S)
def ink_crop(a,lo,hi):
 part=a[lo:hi].copy();ink=(part[:,:,3]>150)&(part[:,:,:3].max(2)<160);ys=np.flatnonzero(ink.sum(1)>12);xs=np.flatnonzero(ink[ys[0]:ys[-1]+1].sum(0)>3)
 part=part[ys[0]:ys[-1]+1,xs[0]:xs[-1]+1];part[:,:,3]=np.where((part[:,:,3]>100)&(part[:,:,:3].max(2)<160),part[:,:,3],0)
 return Image.fromarray(part)

def prepare():
 global ORIGINAL,CLEAN,FLAME,SEAL
 OUT.mkdir(exist_ok=True);(OUT/'Resource').mkdir(exist_ok=True);(OUT/'原始组件').mkdir(exist_ok=True);(OUT/'inputs').mkdir(exist_ok=True)
 shutil.copy2(PREV/'inputs/荷花_已核定位_无UI地形.png',OUT/'inputs/荷花_已核定位_无UI地形.png')
 sheet=Image.open(PREV/'共享标题与提示_生图原稿.png').convert('RGBA');a=np.array(sheet)
 for name,(lo,hi) in {'lotus':(95,305),'front':(345,545),'back':(590,790),'footer':(850,995)}.items():
  RAWS[name]=ink_crop(a,lo,hi);RAWS[name].save(OUT/'原始组件'/f'{name}_原生裁片.png')
 ORIGINAL=Image.open(core.REF/'00_梦境已安装纸面_原样.png').convert('RGBA')
 source=Image.open(HI_PAPER).convert('RGBA');edited=Image.open(OUT/'底纸清理_生图原稿.png').convert('RGBA');assert source.size==edited.size
 raw=np.array(source);replacement=np.array(edited);mask=np.zeros(raw.shape[:2],dtype='uint8');flame=np.zeros_like(mask)
 # Only erase obsolete ink footprints, never paste a whole paper rectangle.
 def erase(box,target,kind):
  x0,y0,x1,y1=box;part=raw[y0:y1,x0:x1,:3].astype(int)
  isink=(part.max(2)<170) if kind=='title' else ((part[:,:,2]<132)|(part.max(2)<160))
  small=Image.fromarray(isink.astype('uint8')*255).filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.GaussianBlur(3));v=np.array(small);v[isink]=255;target[y0:y1,x0:x1]=v
 erase((515,17,985,100),mask,'title');erase((1327,346,1486,431),flame,'legend');mask=np.maximum(mask,flame)
 target=raw.copy();weight=mask[:,:,None].astype(float)/255;target[:,:,:3]=np.rint(raw[:,:,:3]*(1-weight)+replacement[:,:,:3]*weight).astype('uint8')
 Image.fromarray(target).save(OUT/'共用纸底_原始分辨率清理.png')
 changed=Image.fromarray(target).resize((640,480),Image.Resampling.LANCZOS)
 lowmask=Image.fromarray(mask).resize((640,480),Image.Resampling.LANCZOS);CLEAN=ORIGINAL.copy();CLEAN.paste(changed,(0,0),lowmask)
 FLAME=Image.fromarray(flame).resize((640,480),Image.Resampling.LANCZOS)
 CLEAN.save(OUT/'共用纸底_旧字迹局部清理.png');lowmask.save(OUT/'纸底清理范围_仅旧字像素.png')
 untouched=np.asarray(lowmask)==0;assert np.array_equal(np.array(CLEAN)[untouched],np.array(ORIGINAL)[untouched])
 # High-resolution genuine brush swatch; make its own paper/background transparent.
 material=Image.open(W/'候选版本/luocha-style-v2-20261104/梦境画风材质参考.png').convert('RGBA');swatch=np.array(material.crop((775,745,1510,962)))
 color=swatch[:,:,:3].astype(float);t=np.clip((color[:,:,0]-color[:,:,1]-26)/22,0,1);yy,xx=np.indices(t.shape);edge=np.minimum.reduce([xx,yy,t.shape[1]-1-xx,t.shape[0]-1-yy]);t*=np.clip(edge/7,0,1);swatch[:,:,3]=np.rint(t*255).astype('uint8');SEAL=Image.fromarray(swatch);SEAL.save(OUT/'原始组件/朱赭名牌_透明笔触.png')

def components():
 parts={}
 for name,raw in RAWS.items():
  h=10 if name=='footer' else 28;im=raw.copy()
  if name=='footer':a=np.array(im);a[:,:,:3]=[104,78,49];im=Image.fromarray(a)
  im=im.resize((round(im.width*h/im.height),h),Image.Resampling.LANCZOS);parts[name]=im;im.save(OUT/f'共享组件_{name}.png')
 return parts

def base(parts,title=None,transport=False,state=None):
 im=CLEAN.copy() if title else ORIGINAL.copy()
 if not title:im.paste(CLEAN,(0,0),FLAME)
 overlay=Image.new('RGBA',(2560,1920))
 if title:
  raw=RAWS[title];h=28*S;g=raw.resize((round(raw.width*h/raw.height),h),Image.Resampling.LANCZOS);overlay.alpha_composite(g,(320*S-g.width//2,14*S))
 d=ImageDraw.Draw(overlay)
 for y,text in [(175,'同號相連'),(189,'虛線乘蓮' if transport else '虛線換圖')]:d.text((597*S,y*S),text,font=font(10),fill='#67492b',anchor='mm')
 if state:d.text((619*S,51*S),state,font=font(9),fill='#80664b',anchor='rm')
 raw=RAWS['footer'];g=raw.resize((round(raw.width*40/raw.height),40),Image.Resampling.LANCZOS);a=np.array(g);a[:,:,:3]=[104,78,49];g=Image.fromarray(a);overlay.alpha_composite(g,(320*S-g.width//2,459*S))
 im.alpha_composite(overlay.resize((640,480),Image.Resampling.LANCZOS));return im

def plate_positions(atlas,style):
 # All main-floor states share label locations; stay clear of roads AND legend.
 for page in [0,1]:
  obstacle=np.zeros((480,640),bool)
  for row in atlas['rows']:
   if row['page']==page:obstacle|=np.array(Image.open(ROOT/'Resource'/row['overlay']).convert('RGBA'))[:,:,3]>90
  used=[]
  for plate in [p for p in style['nameplates'] if p['page']==page]:
   old=plate['box'];cx=(old[0]+old[2])//2;cy=(old[1]+old[3])//2;bw=old[2]-old[0];bh=old[3]-old[1];candidates=[]
   for dy in range(-60,61,3):
    for dx in range(-90,91,3):
     x=cx+dx;y=cy+dy;b=[x-bw//2,y-bh//2,x+(bw+1)//2,y+(bh+1)//2]
     if b[0]<12 or b[2]>629 or b[1]<65 or b[3]>409:continue
     if b[2]>558 and b[0]<636 and b[3]>63 and b[1]<220:continue
     if any(not(b[2]+3<=q[0] or b[0]-3>=q[2] or b[3]+3<=q[1] or b[1]-3>=q[3]) for q in used):continue
     hits=int(obstacle[max(0,b[1]-2):b[3]+2,max(0,b[0]-2):b[2]+2].sum());candidates.append((hits*1000+math.hypot(dx,dy),hits,b))
   assert candidates,(page,plate['label']);_,hits,b=min(candidates);used.append(b);PLATES[page,plate['label']]=b;LABEL_CHECKS.append(dict(page=page,label=plate['label'],old_box=old,new_box=b,road_overlap_pixels=hits,legend_overlap=False))

def return_base(row,atlas,style,parts):
 im=base(parts,'front' if row['page']==0 else 'back',state=row['name']);high=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(high)
 for plate in style['nameplates']:
  if plate['page']!=row['page']:continue
  b=PLATES[row['page'],plate['label']];stamp=SEAL.resize(((b[2]-b[0])*S,(b[3]-b[1])*S),Image.Resampling.LANCZOS);high.alpha_composite(stamp,(b[0]*S,b[1]*S));d.text(((b[0]+b[2])*S/2,(b[1]+b[3])*S/2),plate['label'],font=font(13),anchor='mm',fill='#fff0cf')
 im.alpha_composite(high.resize((640,480),Image.Resampling.LANCZOS));return core.captions(im,style['captions'][str(row['scene'])])

def lotus_terrain():
 src=Image.open(W/'地图开发/逐图开发/03_荷花池/数据核对_v1/27_完整静态复合.png').convert('RGBA');raw=np.array(src);rgb=raw[:,:,:3].astype(float)
 water=(rgb[:,:,2]>rgb[:,:,0]*1.2+4)&(rgb[:,:,2]>rgb[:,:,1]*1.05+2);land=~water;green=(rgb[:,:,1]>rgb[:,:,0]*1.06)&(rgb[:,:,1]>rgb[:,:,2]*1.02)&land
 # Palette/ink treatment affects presentation only; no walking-map decisions.
 luma=rgb.mean(2)/255;t=np.clip(luma,0,1)**.72
 stone=np.array([69,48,31])+(np.array([242,224,184])-np.array([69,48,31]))*t[:,:,None]
 leaf=np.array([61,70,32])+(np.array([192,184,101])-np.array([61,70,32]))*np.clip(t*1.14,0,1)[:,:,None]
 toned=np.where(green[:,:,None],leaf,stone);toned[water]=[91,116,122]
 seed=Image.fromarray(land.astype('uint8')*255);wash=np.array(seed.filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.GaussianBlur(17))).astype(float)/255
 alpha=np.where(land,255,np.rint(wash*80)).astype(float)
 yy,xx=np.indices(alpha.shape);edge=np.minimum.reduce([xx,yy,alpha.shape[1]-1-xx,alpha.shape[0]-1-yy]);t=np.clip(edge/24,0,1);alpha=np.rint(alpha*t*t*(3-2*t)).astype('uint8')
 result=Image.fromarray(np.dstack([np.clip(toned,0,255).astype('uint8'),alpha]))
 # Same fixed uniform native-to-page transform, no warp or feature relocation.
 hi=Image.new('RGBA',(2560,1920));hi.alpha_composite(result.resize((1997,1123),Image.Resampling.LANCZOS),(112,432));hi.save(OUT/'荷花地形_原件工作尺寸.png');im=hi.resize((640,480),Image.Resampling.LANCZOS);im.save(OUT/'荷花_原生路线_水纹退纸显示层.png');return im,land

def markers(im,row):
 high=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(high)
 for key,p in row['ports'].items():
  n=int(str(key).split(':')[-1]);x,y=p['page'];color=COLORS[(n-1)%4] if n<=13 else '#593c25';b=((x-6)*S,(y-6)*S,(x+6)*S,(y+6)*S)
  d.rounded_rectangle(b,radius=2*S,fill='#f4e5c4',outline=color,width=S);d.text((x*S,y*S),str(n),font=font(11,True),fill=color,anchor='mm')
 out=im.copy();out.alpha_composite(high.resize((640,480),Image.Resampling.LANCZOS));return out

def lane_graph(links):
 graph={r['number']:set() for r in links}
 def parallel_overlap(a,b,c,d):
  if abs(a[0]-b[0])<.1 and abs(c[0]-d[0])<.1 and abs(a[0]-c[0])<.6:return min(max(a[1],b[1]),max(c[1],d[1]))-max(min(a[1],b[1]),min(c[1],d[1]))>5
  if abs(a[1]-b[1])<.1 and abs(c[1]-d[1])<.1 and abs(a[1]-c[1])<.6:return min(max(a[0],b[0]),max(c[0],d[0]))-max(min(a[0],b[0]),min(c[0],d[0]))>5
  return False
 for i,r in enumerate(links):
  for q in links[:i]:
   if any(parallel_overlap(a,b,c,d) for a,b in zip(r['points'],r['points'][1:]) for c,d in zip(q['points'],q['points'][1:])):graph[r['number']].add(q['number']);graph[q['number']].add(r['number'])
 lanes={}
 for n in sorted(graph,key=lambda n:-len(graph[n])):
  occupied={lanes[p] for p in graph[n] if p in lanes};lanes[n]=next(i for i in range(8) if i not in occupied)
 return graph,lanes

def links(atlas):
 result=[];graph,lanes=lane_graph(atlas['links']);offsets=[0,1.2,-1.2,2.4,-2.4,3,-3,3.6]
 for link in atlas['links']:
  n=link['number'];pts=np.array(link['points'],dtype=float);normals=[]
  for a,b in zip(pts,pts[1:]):
   v=b-a;length=np.linalg.norm(v);normals.append(np.array([-v[1],v[0]])/(length or 1))
  off=offsets[lanes[n]];vertex_normals=[normals[0]]
  for j in range(1,len(pts)-1):
   v=normals[j-1]+normals[j];v/=np.linalg.norm(v) or 1;vertex_normals.append(v)
  vertex_normals.append(normals[-1]);lengths=[float(np.linalg.norm(b-a)) for a,b in zip(pts,pts[1:])];total=sum(lengths);distance=0;moved=[]
  for j,(a,b) in enumerate(zip(pts,pts[1:])):
   length=lengths[j]
   if not length:continue
   for s in sorted(set([0,min(8,length/3),max(length-8,length*2/3),length])):
    t=s/length;v=(1-t)*vertex_normals[j]+t*vertex_normals[j+1];v/=np.linalg.norm(v) or 1;ramp=max(0,min(1,(distance+s)/8,(total-distance-s)/8));moved.append(a+(b-a)*t+off*v*ramp)
   distance+=length
  moved=np.array(moved);moved[0]=pts[0];moved[-1]=pts[-1]
  # Endpoints stay exact. Tiny display lanes do not change native travel paths.
  assert np.array_equal(moved[0],pts[0]) and np.array_equal(moved[-1],pts[-1]);LINK_CHECKS.append(dict(number=n,lane=off,shared_with=sorted(graph[n]),endpoints_unchanged=True))
  hi=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(hi);phase=0;dash,gap=[(4,3),(7,3),(2,3)][((n-1)//4)%3];color=COLORS[(n-1)%4]
  for a,b in zip(moved,moved[1:]):
   length=np.linalg.norm(b-a)
   for s in np.arange(0,length,.2):
    if (phase+s)%(dash+gap)<dash:
     x,y=(a+(b-a)*(s/length))*S;d.ellipse((x-1.8,y-1.8,x+1.8,y+1.8),fill=color)
   phase+=length
  # Route strokes run beneath every numbered badge, never through a digit.
  alpha=hi.getchannel('A');ad=ImageDraw.Draw(alpha)
  for port in atlas['rows'][0]['ports'].values():
   x,y=port['page'];ad.rectangle(((x-7)*S,(y-7)*S,(x+7)*S,(y+7)*S),fill=0)
  hi.putalpha(alpha);LINK_HIGH[n]=hi;im=hi.resize((640,480),Image.Resampling.LANCZOS);im.save(OUT/'Resource'/link['file']);result.append((link,im))
 return result

def preview(name,background,overlays,parts,point,partial_points):
 full,partial=ORIGINAL_PREVIEW(name,background,overlays,parts,point,partial_points)
 if name=='03_荷花池':
  # Match native endpoint-based link visibility rather than showing a sliver of
  # an unvisited boat route merely because it crosses the explored entrance.
  brush=np.array(core.fog_layer(Image.new('RGBA',(640,480),(255,255,255,255)),partial_points))[:,:,3]
  partial=background.copy();partial.alpha_composite(core.fog_layer(overlays[0][0],partial_points),overlays[0][1])
  routes=core.load(W/'候选版本/lotus-map-v2/atlas.json')['links']
  for (image,xy),route in zip(overlays[1:],routes):
   if all(brush[p[1],p[0]]>=128 for p in [route['a_point'],route['b_point']]):partial.alpha_composite(image,xy)
  player=Image.open(ROOT/'Resource/np_lr_player_v1.png').convert('RGBA');partial.alpha_composite(player,(point[0]-12,point[1]-12));partial.save(OUT/f'{name}_局部探索.png')
 return full,partial

def clear_lotus_previews():
 # A genuine high-source composite, not an enlargement of the 640px preview.
 # UI uses raw typography crops, original paper and native 2560px lotus pixels.
 background=Image.open(OUT/'共用纸底_原始分辨率清理.png').convert('RGBA').resize((2560,1920),Image.Resampling.LANCZOS)
 g=RAWS['lotus'];g=g.resize((round(g.width*112/g.height),112),Image.Resampling.LANCZOS);background.alpha_composite(g,(1280-g.width//2,56))
 d=ImageDraw.Draw(background)
 for y,text in [(175,'同號相連'),(189,'虛線乘蓮')]:d.text((597*S,y*S),text,font=font(10),fill='#67492b',anchor='mm')
 for y,text in [(417,'14 ← 仙靈島岩徑　　15 → 桃樹林'),(431,'蓮葉路線隨機關狀態變化')]:d.text((320*S,y*S),text,font=font(10),fill='#67492b',anchor='mm')
 g=RAWS['footer'];g=g.resize((round(g.width*40/g.height),40),Image.Resampling.LANCZOS);a=np.array(g);a[:,:,:3]=[104,78,49];g=Image.fromarray(a);background.alpha_composite(g,(1280-g.width//2,1836))
 terrain=Image.open(OUT/'荷花地形_原件工作尺寸.png').convert('RGBA');d=ImageDraw.Draw(terrain);row=core.load(W/'候选版本/lotus-map-v2/atlas.json')['rows'][0]
 for key,p in row['ports'].items():
  n=int(str(key).split(':')[-1]);x,y=p['page'];color=COLORS[(n-1)%4] if n<=13 else '#593c25';b=((x-6)*S,(y-6)*S,(x+6)*S,(y+6)*S);d.rounded_rectangle(b,radius=2*S,fill='#f4e5c4',outline=color,width=S);d.text((x*S,y*S),str(n),font=font(11,True),fill=color,anchor='mm')
 full=background.copy();full.alpha_composite(terrain)
 for n in range(1,14):full.alpha_composite(LINK_HIGH[n])
 player=Image.open(ROOT/'Resource/np_lr_player_v1.png').convert('RGBA').resize((100,100),Image.Resampling.LANCZOS);full.alpha_composite(player,(87*S-48,353*S-48));full.save(OUT/'荷花池_清晰整图预览_2560.png')
 yy,xx=np.indices((1920,2560));mask=np.zeros((1920,2560))
 for x,y in [(63,363),(76,359),(87,353)]:
  t=np.clip((240-np.hypot(xx-x*S,yy-y*S))/96,0,1);mask=np.maximum(mask,t*t*(3-2*t))
 a=np.array(terrain);a[:,:,3]=np.rint(a[:,:,3]*mask).astype('uint8');partial=background.copy();partial.alpha_composite(Image.fromarray(a))
 for route in core.load(W/'候选版本/lotus-map-v2/atlas.json')['links'][:13]:
  if all(mask[p[1]*S,p[0]*S]>=128/255 for p in [route['a_point'],route['b_point']]):partial.alpha_composite(LINK_HIGH[route['number']])
 partial.alpha_composite(player,(87*S-48,353*S-48));partial.save(OUT/'荷花池_清晰局部探索预览_2560.png')

def main():
 prepare();atlas=core.load(W/'候选版本/luocha-return-v1/atlas.json');style=core.load(W/'候选版本/luocha-style-v2-20261104/style-verification.json');plate_positions(atlas,style)
 core.OUT=OUT;core.components=components;core.paper_base=base;core.return_base=return_base;core.lotus_terrain=lotus_terrain;core.markers=markers;core.links=links;core.preview=preview
 core.main()
 report=core.load(OUT/'preview-verification.json');report.update(revision='v4 transparent original-source compositing',raw_source_glyphs=True,whole_paper_rectangles_pasted=False,local_inpaint_only_on_obsolete_ink=True,clear_paper_original_size=[1500,1049],nameplates=LABEL_CHECKS,connections=LINK_CHECKS,terrain_warped=False,source_road_geometry_changed=False,style_acceptance='pending user PNG review',imagegen_mode='built-in: localized clean-paper edit only; original typography/material sources reused',limits='Offline art/layout candidate, not installed. Ink/palette changes only for lotus; coordinates, scripts and collision are unchanged. Display lanes are decorative and keep endpoints exact.')
 save(OUT/'preview-verification.json',report)
 # Future integration must use this alpha, not the old rectangular lake alpha.
 (OUT/'lotus-alpha.bin').write_bytes(b''.join(Image.open(OUT/'Resource'/f'np_lp_road_{scene}_v1.png').convert('RGBA').getchannel('A').tobytes() for scene in [27,827]))
 review=Image.new('RGB',(1280,960))
 for i,n in enumerate(['01_梦境','02_羅剎前_503','02_羅剎後_511','03_荷花池']):review.paste(Image.open(OUT/f'{n}_完整.png'),(i%2*640,i//2*480))
 review.save(OUT/'四图_完整排版预览.png')
 pair=Image.new('RGB',(1280,480));pair.paste(Image.open(PREV/'03_荷花池_完整.png'),(0,0));pair.paste(Image.open(OUT/'03_荷花池_完整.png'),(640,0));pair.save(OUT/'荷花池_左旧右新.png')
 # Magnified detail review uses nearest pixels so seams cannot hide in resampling.
 for name,box in [('标题',(190,5,450,70)),('图例',(555,60,638,219))]:
  Image.open(OUT/'03_荷花池_完整.png').crop(box).resize(((box[2]-box[0])*4,(box[3]-box[1])*4),Image.Resampling.NEAREST).save(OUT/f'荷花池_{name}_像素核对.png')
 clear_lotus_previews()
 print(json.dumps(dict(revision='v4',label_conflicts=[p for p in LABEL_CHECKS if p['road_overlap_pixels']],installed=False,output=str(OUT)),ensure_ascii=True))
if __name__=='__main__':main()
