"""Apply shared UI typography and cave-theme RGB materials to the existing atlas.

Never invokes geometry generation. All 55 PNG alpha planes, 17 mappings,
runtime executable, fog storage and links' endpoint identities stay fixed.
"""
from pathlib import Path
import json,hashlib,math,shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageChops
import luocha_boundary_geometry_v2 as geo

W=Path(__file__).resolve().parents[1];ROOT=W.parent
SRC=W/'候选版本/luocha-return-v1';OUT=W/'候选版本/luocha-style-v2-20261104'
SPEC=W/'地图开发/界面模板/地图视觉范式_v2.json';S=4
TOKENS=json.loads(SPEC.read_text(encoding='utf-8'))
DISPLAY_NAMES={509:'左侧支洞',507:'右侧支洞',517:'左侧支洞',515:'小曲支洞'}

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def font(size,number=False):return ImageFont.truetype('C:/Windows/Fonts/timesbd.ttf' if number else 'C:/Windows/Fonts/simkai.ttf',round(size*S))
def tile(im,size=(640,480)):
    a=np.asarray(im.convert('RGB'));yy,xx=np.indices((size[1],size[0]));return a[yy%a.shape[0],xx%a.shape[1]].astype(float)

def geometric_mask(r):
    grid=Image.open(geo.OUT/f'{r["scene"]}-display-grid.png').convert('L')
    hi=Image.new('L',(2560,1920));size=(round(r['width']*16*r['numerator']/r['denominator']*4),round(r['height']*16*r['numerator']/r['denominator']*4))
    hi.paste(grid.resize(size,Image.Resampling.NEAREST),(r['tx']*4,r['ty']*4))
    return hi.filter(ImageFilter.GaussianBlur(3.1)).resize((640,480),Image.Resampling.LANCZOS)

def text_width(text,f):return f.getlength(text)/S
def box(cx,cy,w,h):return [round(cx-w/2),round(cy-h/2),round(cx+w/2),round(cy+h/2)]

def nameplates(atlas,geom):
    # Shared label positions per logical fragment, valid for every floor state.
    from build_luocha_runtime_assets_v1 import LAYOUT,NAMES
    NAMES={**NAMES,**DISPLAY_NAMES}
    places={};checks=[]
    for page in [0,1]:
        obstacle=np.zeros((480,640),bool)
        for r in atlas['rows']:
            if r['page']==page:obstacle|=np.asarray(geom[r['scene']])>32
        used=[]
        for r in atlas['rows']:
            if r['page']!=page:continue
            key='主洞' if r['family'] else str(r['scene'])
            if (page,key) in places:continue
            label='主洞' if r['family'] else NAMES[r['scene']]
            cx,cy=LAYOUT[r['scene']][4:];fw=math.ceil(text_width(label,font(TOKENS['typography']['fragment_name_px']))+2*TOKENS['layout']['nameplate_pad_x']);height=TOKENS['layout']['nameplate_height']
            candidates=[]
            for dy in [0,-3,-6,-9,-12,3,6,9,12]:
                for dx in [0,-4,4,-8,8]:
                    b=box(cx+dx,cy+dy,fw,height)
                    if b[0]<12 or b[2]>628 or b[1]<63 or b[3]>410:continue
                    if any(not(b[2]<q[0] or b[0]>q[2] or b[3]<q[1] or b[1]>q[3]) for q in used):continue
                    pad=obstacle[max(0,b[1]-2):min(480,b[3]+2),max(0,b[0]-2):min(640,b[2]+2)]
                    collisions=int(pad.sum());candidates.append((collisions*100+abs(dx)+abs(dy),b,collisions,[cx+dx,cy+dy]))
            assert candidates,('no label position',page,label)
            _,b,collisions,center=min(candidates,key=lambda q:q[0]);used.append(b)
            places[page,key]=dict(text=label,box=b,center=center)
            checks.append(dict(page=page,label=label,box=b,road_clearance_pixel_conflicts=collisions))
    return places,checks

def draw_plate(base,plate,swash):
    b=plate['box'];stamp=swash.resize(((b[2]-b[0])*S,(b[3]-b[1])*S),Image.Resampling.LANCZOS)
    base.alpha_composite(stamp,(b[0]*S,b[1]*S));d=ImageDraw.Draw(base)
    d.text((plate['center'][0]*S,(plate['center'][1]-.2)*S),plate['text'],font=font(TOKENS['typography']['fragment_name_px']),fill='#fff0cf',anchor='mm',stroke_width=1)

def caption_lines(items,f,maxwidth):
    lines=[];current=''
    for item in items:
        proposal=current+'   '+item if current else item
        if text_width(proposal,f)<=maxwidth:current=proposal
        else:
            if current:lines.append(current)
            current=item
    if current:lines.append(current)
    assert len(lines)<=2,lines
    return lines

def base_asset(r,atlas,plates,swash,paper):
    from build_luocha_runtime_assets_v1 import NAMES
    NAMES={**NAMES,**DISPLAY_NAMES}
    batch=W/'地图开发/批量制图_20261102';pagename='前' if r['page']==0 else '后'
    im=paper.copy();ui=Image.open(batch/f'02_{pagename}/统一UI层.png').convert('RGBA')
    d=ImageDraw.Draw(ui);d.rectangle((1340,313,1510,393),fill=(0,0,0,0));d.rectangle((0,930,1535,1023),fill=(0,0,0,0))
    im.alpha_composite(ui.resize(im.size,Image.Resampling.LANCZOS))
    d=ImageDraw.Draw(im)
    # Only the layer state uses the top-right slot. Fragment names use seals.
    state=r['name'] if r['family'] else '当前位置：'+NAMES[r['scene']]
    d.text((618*S,50*S),state,font=font(10),fill='#80664b',anchor='rm')
    for (page,_),plate in plates.items():
        if page==r['page']:draw_plate(im,plate,swash)
    d=ImageDraw.Draw(im)
    d.text((594*S,156*S),'同号相连',font=font(9),fill='#80664b',anchor='mm')
    d.text((594*S,168*S),'虚线为换图',font=font(9),fill='#80664b',anchor='mm')
    captions=[]
    for number,p in sorted(r['ports'].items(),key=lambda x:int(x[0])):
        other=next(v for v in atlas['rows'] if v['scene']==p['destination'])
        dest='主洞' if other['family'] else NAMES[p['destination']]
        if other['page']!=r['page']:dest+='〔'+('前' if other['page']==0 else '后')+'页〕'
        captions.append(number+'→'+dest)
    lines=caption_lines(captions,font(10),385)
    for i,line in enumerate(lines):d.text((332*S,(421+(i-(len(lines)-1)/2)*14)*S),line,font=font(10),fill='#67492b',anchor='mm')
    d.text((320*S,464*S),'M / Back：地图    Esc / B：关闭',font=font(10),fill='#67492b',anchor='mm')
    return im.resize((640,480),Image.Resampling.LANCZOS),lines

def road_asset(r,old,mask,papertex,rocktex):
    a=np.asarray(old).copy();alpha=a[:,:,3].copy();core=np.asarray(mask)>127
    # A bounded display band supplies shallow mineral shading within the old
    # alpha extent. It never changes the walking-region geometry or fog mask.
    distance=np.zeros(core.shape,float);eroded=Image.fromarray(core.astype('uint8')*255)
    for _ in range(7):distance+=np.asarray(eroded)>0;eroded=eroded.filter(ImageFilter.MinFilter(3))
    outside=np.zeros(core.shape,float);dilated=Image.fromarray(core.astype('uint8')*255)
    for _ in range(5):outside+=np.asarray(dilated)==0;dilated=dilated.filter(ImageFilter.MaxFilter(3))
    signed=distance-outside
    gy,gx=np.gradient(signed);norm=np.sqrt(gx*gx+gy*gy)+.001
    light=np.clip((gx/norm)*.35-(gy/norm)*.65,-1,1)
    body=papertex*.66+np.array([245,229,198])*.34
    mineral=rocktex*.78+np.array([133,113,98])*.22
    mineral+=light[:,:,None]*18
    # Irregular ink/texture makes the rim hand drawn instead of a plastic bevel.
    rock_luma=rocktex.mean(2)
    variation=np.clip((rock_luma-125)/100,-.6,.6)
    rim=np.clip((3.1+variation-distance)/2.1,0,1)
    rim=np.where(core,rim,np.ones_like(rim))
    rgb=body*(1-rim[:,:,None])+mineral*rim[:,:,None]
    edge=(distance>0)&(distance<=1);rgb[edge]=rgb[edge]*.66+np.array([63,49,39])*.34
    # Keep the outer translucent wash close to paper; alpha is the original.
    rgb[~core]=mineral[~core]*.68+np.array([160,133,108])*.32
    rgb=np.clip(rgb,0,255).astype('uint8')
    # Port labels are shared UI components in their existing exact bounding box.
    high=Image.fromarray(rgb).resize((2560,1920),Image.Resampling.LANCZOS);d=ImageDraw.Draw(high)
    for number,p in r['ports'].items():
        x,y=p['page'];b=((x-7)*S,(y-6)*S,(x+7)*S,(y+7)*S)
        d.rounded_rectangle(b,radius=2*S,fill='#f4e5c4',outline='#705138',width=S)
        d.text((x*S,(y+.3)*S),number,font=font(TOKENS['typography']['connection_number_px'],True),fill='#593c25',anchor='mm')
    rgb=np.asarray(high.resize((640,480),Image.Resampling.LANCZOS));visible=alpha>0;a[:,:,:3][visible]=rgb[visible]
    assert np.array_equal(a[:,:,3],alpha)
    return Image.fromarray(a,'RGBA')

def main():
    OUT.mkdir(exist_ok=True);res=OUT/'Resource';res.mkdir(exist_ok=True)
    atlas=load(SRC/'atlas.json');spec=load(SPEC);assert spec['logical_canvas']==atlas['canvas']==[640,480]
    current=load(SRC/'installation.json');assert hashlib.sha1((ROOT/'NewPAL_Release.exe').read_bytes()).hexdigest()==current['installed_sha1']
    originals={p['file']:p['sha256'] for p in current['resources']}
    for n,h in originals.items():assert sha(ROOT/'Resource'/n)==h,n
    material=Image.open(OUT/'梦境画风材质参考.png').convert('RGBA')
    # Isolated reference swatches; only sampled RGB/pigment enters terrain.
    papertex=tile(material.crop((110,770,650,955)).resize((400,140),Image.Resampling.LANCZOS))
    rocktex=tile(material.crop((840,547,1470,617)).resize((380,50),Image.Resampling.LANCZOS))
    swash=material.crop((775,745,1510,962))
    paper=Image.open(W/'地图开发/批量制图_20261102/共用羊皮纸底图_v1.png').convert('RGBA').resize((2560,1920),Image.Resampling.LANCZOS)
    geom={r['scene']:geometric_mask(r) for r in atlas['rows']};plates,label_checks=nameplates(atlas,geom)
    captions={};resources=[];checks=[]
    for r in atlas['rows']:
        base,lines=base_asset(r,atlas,plates,swash,paper);base.save(res/r['base']);captions[r['scene']]=lines
        road=road_asset(r,Image.open(ROOT/'Resource'/r['overlay']).convert('RGBA'),geom[r['scene']],papertex,rocktex);road.save(res/r['overlay'])
    for link in atlas['links']:
        p=ROOT/'Resource'/link['file'];a=np.asarray(Image.open(p).convert('RGBA')).copy();visible=a[:,:,3]>0;a[:,:,:3][visible]=[112,81,56];Image.fromarray(a,'RGBA').save(res/link['file'])
    shutil.copy2(ROOT/'Resource/np_lr_player_v1.png',res/'np_lr_player_v1.png')
    for p in sorted(res.glob('*.png')):
        old=Image.open(ROOT/'Resource'/p.name).convert('RGBA');new=Image.open(p).convert('RGBA');a=np.asarray(old);b=np.asarray(new)
        assert old.size==new.size==(640,480) if p.name!='np_lr_player_v1.png' else old.size==new.size
        assert np.array_equal(a[:,:,3],b[:,:,3]),('alpha changed',p.name)
        resources.append(dict(file=p.name,sha256=sha(p)))
        checks.append(dict(file=p.name,alpha_sha256=hashlib.sha256(a[:,:,3].tobytes()).hexdigest(),alpha_identical=True,changed_rgb_pixels=int((a[:,:,:3]!=b[:,:,:3]).any(2).sum())))
    assert len(resources)==55
    # Existing atlas/masks remain authoritative, not reserialized replacements.
    for sid in [503,506,508,511,514,516]:
        r=next(r for r in atlas['rows'] if r['scene']==sid);im=Image.open(res/r['base']).convert('RGBA')
        for row in atlas['rows']:
            if row['page']==r['page'] and (not row['family'] or row['scene']==sid):im.alpha_composite(Image.open(res/row['overlay']).convert('RGBA'))
        for link in atlas['links']:
            if link['page']!=r['page']:continue
            if any(atlas['rows'][link[e]]['family'] and atlas['rows'][link[e]]['scene']!=sid for e in ['a','b']):continue
            im.alpha_composite(Image.open(res/link['file']).convert('RGBA'))
        im.convert('RGB').save(OUT/f'preview-{sid}.png')
    review=Image.new('RGB',(1280,1440))
    for k,sid in enumerate([503,511,506,514,508,516]):review.paste(Image.open(OUT/f'preview-{sid}.png'),(k%2*640,k//2*480))
    review.save(OUT/'atlas-review-v2.png')
    dump(OUT/'assets.json',resources)
    dump(OUT/'style-verification.json',dict(status='RGB-only candidate; visual review required',base_exe_sha1=current['installed_sha1'],
         baseline_assets=originals,resources=checks,alpha_identical_all=True,alpha_bin_sha256=sha(SRC/'alpha.bin'),atlas_sha256=sha(SRC/'atlas.json'),
         nameplates=label_checks,captions=captions,style_spec_sha256=sha(SPEC),theme='cave only; shared UI rules apply to other environment themes',
         source_geometry_unchanged=True,position_transforms_unchanged=True,number_pairing_unchanged=True,exploration_format_unchanged=True,installed=False))
    print(json.dumps(dict(resources=55,alpha_unchanged=True,nameplates=len(label_checks),label_conflicts=[v for v in label_checks if v['road_clearance_pixel_conflicts']],output=str(OUT)),ensure_ascii=False))

if __name__=='__main__':main()
