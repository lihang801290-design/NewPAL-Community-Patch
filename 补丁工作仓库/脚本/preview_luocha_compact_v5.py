"""Compact the two return-cave pages. Offline review; never installs files.

Native road grids and paired exits are immutable. Per-scene display translation,
cliff pigment, label placement and empty-paper connectors are separate outputs.
"""
from pathlib import Path
import copy, hashlib, heapq, json, math, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
import preview_map_visual_v4 as ui
import style_luocha_assets_v2 as art
from build_luocha_boundary_routes_v1 import components

W=ui.W;ROOT=ui.ROOT;S=4
OUT=W/'候选版本/luocha-compact-v5-preview'
SRC=W/'候选版本/map-visual-v4-preview'
DELTA={502:(-24,48),503:(-5,-5),506:(-5,-5),508:(-5,-5),
       504:(-5,5),505:(-65,15),509:(5,10),507:(-83,10),510:(10,-25),
       511:(-5,-10),514:(-5,-10),516:(-5,-10),512:(35,0),513:(35,-5),
       515:(-48,28),517:(15,-10),518:(-156,26)}
SID_LABEL={502:'洞外',503:'主洞',504:'上方短通道',505:'上方旧洞',509:'左侧支洞',507:'右侧支洞',510:'圆形支洞',
           511:'主洞',512:'斜向通道',513:'狭长通道',515:'小曲支洞',517:'左侧支洞',518:'大殿'}
COLORS=['#765233','#586976','#797047','#8c584b']
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def init_ui():
    ui.OUT=OUT
    ui.ORIGINAL=Image.open(ui.core.REF/'00_梦境已安装纸面_原样.png').convert('RGBA')
    ui.CLEAN=Image.open(SRC/'共用纸底_旧字迹局部清理.png').convert('RGBA')
    # return pages always use cleaned paper; the flame mask is unnecessary here.
    for name in ['front','back','footer']:
        ui.RAWS[name]=Image.open(SRC/f'原始组件/{name}_原生裁片.png').convert('RGBA')
    ui.SEAL=Image.open(SRC/'原始组件/朱赭名牌_透明笔触.png').convert('RGBA')

def terrain(r):
    mask=art.geometric_mask(r)
    core=np.array(mask)>127
    # Signed distance from the confirmed native display footprint, not artwork.
    inner=np.zeros((480,640),float);outer=np.zeros_like(inner)
    er=Image.fromarray(core.astype('uint8')*255);di=er.copy()
    for i in range(12):
        inner+=np.array(er)>0;outer+=np.array(di)==0
        er=er.filter(ImageFilter.MinFilter(3));di=di.filter(ImageFilter.MaxFilter(3))
    distance=12-outer # 0 at far exterior, 12 at the native road
    outside=12-distance
    material=Image.open(W/'候选版本/luocha-style-v2-20261104/梦境画风材质参考.png')
    paper=art.tile(material.crop((110,770,650,955)).resize((260,90),Image.Resampling.LANCZOS))
    swatch=np.array(material.convert('RGBA').crop((840,547,1470,617)))
    valid=(swatch[:,:,3]>245)&(swatch[:,:,:3].mean(2)>45)
    color=swatch[:,:,:3].astype(float)
    # A transparent source's RGB can be black/garbage. Fill only the pigment
    # swatch holes before sampling, never let those holes become map shadows.
    for _ in range(90):
        if valid.all():break
        total=np.zeros_like(color);count=np.zeros(valid.shape)
        for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
            v=np.roll(valid,(dy,dx),(0,1));total+=np.roll(color,(dy,dx),(0,1))*v[:,:,None];count+=v
        fill=(~valid)&(count>0);color[fill]=total[fill]/count[fill,None];valid|=fill
    color[~valid]=[143,118,105]
    rock=art.tile(Image.fromarray(np.clip(color,0,255).astype('uint8')).resize((250,28),Image.Resampling.LANCZOS))
    yy,xx=np.indices(core.shape)
    # Coherent, repeatable ink edge; irregularity affects cliff silhouette only.
    rng=np.random.default_rng(5083+r['scene'])
    noise=Image.fromarray(rng.integers(0,256,(120,160),dtype='uint8')).resize((640,480),Image.Resampling.BICUBIC)
    jag=(np.array(noise).astype(float)-127)/127
    signed=inner-outside;gy,gx=np.gradient(signed);norm=np.hypot(gx,gy)+.001
    # Broad textured mineral skirt and broken ridge, rather than a smooth bevel.
    width=4.5+1.8*jag+np.clip(gy/norm,0,1)*2.0
    cliff=np.clip(width+.8-outside,0,1)
    alpha=np.where(core,255,cliff*242)
    wash=np.clip(9-outside,0,5)/5*.14
    alpha=np.maximum(alpha,wash*255)
    shade=np.clip((gx/norm)*.2-(gy/norm)*.25,-.4,.4)
    mineral=rock*.90+np.array([154,128,105])*.10+shade[:,:,None]*20
    # Fine uneven ink at the rock crest, sampled from the original dream sheet.
    mineral*=np.where((outside<1.5)&(~core),.77,1)[:,:,None]
    body=paper*.80+np.array([245,227,190])*.20
    ridge=np.clip((1.3+jag*.7-inner)/1.2,0,.65)
    rgb=np.where(core[:,:,None],body*(1-ridge[:,:,None])+mineral*ridge[:,:,None],mineral)
    rgb=np.clip(rgb,0,255).astype('uint8')
    image=Image.fromarray(np.dstack([rgb,np.rint(alpha).astype('uint8')]))
    # Badges are independent UI; their centers follow the same rigid transform.
    high=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(high)
    for number,p in r['ports'].items():
        x,y=p['page'];color=COLORS[(int(number)-1)%4]
        d.rounded_rectangle(((x-7)*S,(y-6)*S,(x+7)*S,(y+6)*S),radius=2*S,fill='#f4e5c4',outline=color,width=S)
        d.text((x*S,(y+.2)*S),number,font=ui.font(11,True),fill=color,anchor='mm')
    image.alpha_composite(high.resize((640,480),Image.Resampling.LANCZOS))
    image.save(OUT/'Resource'/r['overlay'])
    # Keep a cropped, independently editable fragment with explicit placement.
    box=image.getbbox();image.crop(box).save(OUT/'独立片区'/f'S{r["scene"]}_{r["name"]}.png')
    return image,core,box

def label_positions(atlas,style,images):
    checks=[]
    for page in [0,1]:
        blocked=np.zeros((480,640),bool)
        for r in atlas['rows']:
            if r['page']==page:blocked|=np.array(images[r['scene']])[:,:,3]>40
        for link in atlas['links']:
            if link['page']==page and (OUT/'Resource'/link['file']).exists():
                blocked|=np.array(Image.open(OUT/'Resource'/link['file']).getchannel('A').filter(ImageFilter.MaxFilter(5)))>25
        used=[]
        for p in [v for v in style['nameplates'] if v['page']==page]:
            sid=next(sid for sid,label in SID_LABEL.items() if label==p['label'] and next(r for r in atlas['rows'] if r['scene']==sid)['page']==page)
            old=p['box'];dx,dy=DELTA[sid];cx=(old[0]+old[2])/2+dx;cy=(old[1]+old[3])/2+dy
            bw=old[2]-old[0];bh=old[3]-old[1];opts=[]
            for oy in range(-121,122,2):
                for ox in range(-115,116,2):
                    x=round(cx+ox-bw/2);y=round(cy+oy-bh/2);b=[x,y,x+bw,y+bh]
                    if x<16 or x+bw>625 or y<66 or y+bh>405:continue
                    if x+bw>553 and y<223:continue
                    if any(not(b[2]+4<q[0] or b[0]-4>q[2] or b[3]+4<q[1] or b[1]-4>q[3]) for q in used):continue
                    n=int(blocked[y-2:y+bh+2,x-2:x+bw+2].sum())
                    opts.append((n*10000+math.hypot(ox,oy),n,b))
            _,hits,b=min(opts);assert hits==0,(p['label'],hits)
            used.append(b);ui.PLATES[page,p['label']]=b
            checks.append(dict(page=page,scene=sid,label=p['label'],old_box=old,new_box=b,overlap_pixels=hits))
    return checks

def compile_connectors(atlas,images,labels):
    result=[];checks=[]
    for old in atlas['links']:
        link=copy.deepcopy(old);ra,rb=[atlas['rows'][link[k]] for k in ['a','b']];n=link['number']
        pa,pb=[r['ports'][str(n)]['page'] for r in [ra,rb]]
        link['a_point']=pa;link['b_point']=pb
        selected=ra['index'] if ra['family'] else rb['index'] if rb['family'] else None
        occupancy=Image.new('L',(640,480))
        for r in atlas['rows']:
            if r['page']==link['page'] and (selected is None or not r['family'] or r['index']==selected):
                alpha=images[r['scene']].getchannel('A')
                small=np.array(alpha.resize((320,240),Image.Resampling.BOX))>35
                lab,groups=components(~small);largest=1+max(range(len(groups)),key=lambda i:len(groups[i]))
                hole=Image.fromarray(((lab!=largest)*255).astype('uint8')).resize((640,480),Image.Resampling.NEAREST)
                occupancy=ImageChops.lighter(occupancy,ImageChops.lighter(alpha,hole))
        occupancy=occupancy.filter(ImageFilter.MaxFilter(5));d=ImageDraw.Draw(occupancy)
        for label in labels:
            if label['page']==link['page']:
                x0,y0,x1,y1=label['new_box'];d.rectangle((x0-3,y0-3,x1+3,y1+3),fill=255)
        d.rectangle((0,0,639,72),fill=255);d.rectangle((0,410,639,479),fill=255)
        d.rectangle((552,63,639,224),fill=255);d.rectangle((0,0,14,479),fill=255);d.rectangle((625,0,639,479),fill=255)
        blocked=np.array(occupancy.resize((320,240),Image.Resampling.BOX))>35
        before=blocked.copy()
        # Individual fragment holes were filled above. Never discard a valid
        # exterior corridor just because UI/other fragments split the paper.
        free_labels,_=components(~blocked)
        def endpoint(p,target):
            opts={}
            for y in range(max(0,p[1]//2-26),min(240,p[1]//2+27)):
                for x in range(max(0,p[0]//2-26),min(320,p[0]//2+27)):
                    if not blocked[y,x]:
                        score=math.dist((x*2+1,y*2+1),p)+math.dist((x*2+1,y*2+1),target)*.15
                        label=int(free_labels[y,x]);candidate=(score,x,y)
                        if candidate<opts.get(label,(1e30,0,0)):opts[label]=candidate
            if not opts:
                Image.fromarray((~before*255).astype('uint8')).resize((640,480),Image.Resampling.NEAREST).save(OUT/f'诊断_原始连接{n}.png')
                debug=Image.fromarray((~blocked*255).astype('uint8')).convert('RGB').resize((640,480),Image.Resampling.NEAREST)
                ImageDraw.Draw(debug).ellipse((p[0]-5,p[1]-5,p[0]+5,p[1]+5),fill='red');debug.save(OUT/f'诊断_连接{n}.png')
            assert opts,('no port margin',n,p)
            return opts
        aa=endpoint(pa,pb);bb=endpoint(pb,pa);common=set(aa)&set(bb)
        assert common,('no common exterior margin',n)
        component=min(common,key=lambda k:aa[k][0]+bb[k][0]);begin=tuple(aa[component][1:]);end=tuple(bb[component][1:])
        start=(*begin,4);heap=[(0,0,start)];cost={start:0};prev={};endstate=None
        while heap:
            _,g,state=heapq.heappop(heap)
            if g!=cost[state]:continue
            x,y,direction=state
            if (x,y)==end:endstate=state;break
            for k,(dx,dy) in enumerate([(1,0),(0,1),(-1,0),(0,-1)]):
                xx,yy=x+dx,y+dy
                if not(0<=xx<320 and 0<=yy<240) or blocked[yy,xx]:continue
                nxt=(xx,yy,k);gg=g+1+(2.5 if direction!=4 and direction!=k else 0)
                if gg<cost.get(nxt,1e30):cost[nxt]=gg;prev[nxt]=state;heapq.heappush(heap,(gg+abs(xx-end[0])+abs(yy-end[1]),gg,nxt))
        if endstate is None:
            debug=Image.fromarray((~blocked*255).astype('uint8')).convert('RGB').resize((640,480),Image.Resampling.NEAREST)
            d=ImageDraw.Draw(debug)
            for x,y in [pa,pb]:d.ellipse((x-3,y-3,x+3,y+3),fill='red')
            debug.save(OUT/f'诊断_不通连接{n}.png');dump(OUT/'诊断_标签.json',labels)
        assert endstate is not None,('no connector',n)
        cells=[];s=endstate
        while s!=start:cells.append(s[:2]);s=prev[s]
        cells.append(start[:2]);cells.reverse();points=[pa]+[[x*2+1,y*2+1] for x,y in cells]+[pb];simple=[points[0]]
        for i,p in enumerate(points[1:-1],1):
            a,c=points[i-1],points[i+1]
            if (p[0]-a[0])*(c[1]-p[1])!=(p[1]-a[1])*(c[0]-p[0]):simple.append(p)
        simple.append(points[-1]);link['points']=simple
        high=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(high);phase=0;color=COLORS[(n-1)%4]
        for a,b in zip(simple,simple[1:]):
            length=math.dist(a,b)
            for s in np.arange(0,length,.3):
                if (phase+s)%6<2:
                    x=(a[0]+(b[0]-a[0])*s/length)*S;y=(a[1]+(b[1]-a[1])*s/length)*S;d.ellipse((x-1.7,y-1.7,x+1.7,y+1.7),fill=color)
            phase+=length
        # No connector ink crosses badge text, including another port's badge.
        alpha=high.getchannel('A');d=ImageDraw.Draw(alpha)
        for r in atlas['rows']:
            if r['page']!=link['page']:continue
            for p in r['ports'].values():
                x,y=p['page'];d.rectangle(((x-8)*S,(y-7)*S,(x+8)*S,(y+7)*S),fill=0)
        high.putalpha(alpha);high.resize((640,480),Image.Resampling.LANCZOS).save(OUT/'Resource'/link['file'])
        def length(points):return sum(math.dist(a,b) for a,b in zip(points,points[1:]))
        checks.append(dict(number=n,old_length=round(length(old['points']),1),new_length=round(length(simple),1),endpoint_mapping_exact=True,exterior_cells_checked=len(cells)))
        result.append(link)
    atlas['links']=result;return checks

def main():
    OUT.mkdir(exist_ok=True);(OUT/'Resource').mkdir(exist_ok=True);(OUT/'独立片区').mkdir(exist_ok=True)
    exe=ROOT/'NewPAL_Release.exe';exe_sha=sha(exe)
    installed={p.name:sha(p) for p in (ROOT/'Resource').glob('np_*.png')}
    init_ui();original=load(W/'候选版本/luocha-return-v1/atlas.json');atlas=copy.deepcopy(original)
    style=load(W/'候选版本/luocha-style-v2-20261104/style-verification.json');moves=[];images={};cores={}
    for r in atlas['rows']:
        old=copy.deepcopy(r);dx,dy=DELTA[r['scene']];r['tx']+=dx;r['ty']+=dy
        for p in r['ports'].values():p['page']=[p['page'][0]+dx,p['page'][1]+dy]
        image,core,box=terrain(r);images[r['scene']]=image;cores[r['scene']]=core
        moves.append(dict(scene=r['scene'],page=r['page'],delta=[dx,dy],old_transform=[old['tx'],old['ty'],old['numerator'],old['denominator']],new_transform=[r['tx'],r['ty'],r['numerator'],r['denominator']],fragment_bbox=box,native_source_unchanged=True))
        a=np.array(image)[:,:,3];assert not(a[63:224,553:639]>30).any(),('legend hit',r['scene'])
        assert not(a[410:]>30).any(),('caption hit',r['scene'])
        for number,p in r['ports'].items():
            q=old['ports'][number];assert p['world']==q['world'] and p['destination']==q['destination'] and p['tag']==q['tag']
    connectors=compile_connectors(atlas,images,[])
    labels=label_positions(atlas,style,images)
    for r in atlas['rows']:
        im=ui.return_base(r,atlas,style,{});im.save(OUT/'Resource'/r['base'])
    ui.core.OUT=OUT
    outputs=[]
    for sid in [503,511,506,514,508,516]:
        row=next(r for r in atlas['rows'] if r['scene']==sid);layers=[]
        for r in atlas['rows']:
            if r['page']==row['page'] and(not r['family'] or r['scene']==sid):layers.append((images[r['scene']],(0,0)))
        for link in atlas['links']:
            if link['page']==row['page'] and all(not atlas['rows'][link[k]]['family'] or atlas['rows'][link[k]]['scene']==sid for k in ['a','b']):layers.append((Image.open(OUT/'Resource'/link['file']).convert('RGBA'),(0,0)))
        point=tuple(next(iter(row['ports'].values()))['page']);name=f'羅剎山洞-{["前","後"][row["page"]]}_S{sid}'
        full,part=ui.core.preview(name,Image.open(OUT/'Resource'/row['base']).convert('RGBA'),layers,{},point,[point])
        outputs.append(name)
    montage=Image.new('RGB',(1280,1440))
    for i,name in enumerate(outputs):montage.paste(Image.open(OUT/f'{name}_完整.png'),(i%2*640,i//2*480))
    montage.save(OUT/'前后_全部楼层预览.png')
    for page,sid in [(0,503),(1,511)]:
        name=f'羅剎山洞-{["前","後"][page]}_S{sid}';old=Image.open(SRC/f'02_羅剎{["前","後"][page]}_{sid}_完整.png')
        review=Image.new('RGB',(1280,480));review.paste(old,(0,0));review.paste(Image.open(OUT/f'{name}_完整.png'),(640,0));review.save(OUT/f'{["前","後"][page]}_左旧右新.png')
    overlaps=[]
    for i,r in enumerate(atlas['rows']):
        for q in atlas['rows'][:i]:
            if r['page']!=q['page'] or(r['family'] and r['family']==q['family']):continue
            hits=int((cores[r['scene']]&cores[q['scene']]).sum());assert hits==0,('road collision',r['scene'],q['scene'],hits)
            overlaps.append(dict(a=r['scene'],b=q['scene'],road_overlap=hits))
    for family in [1,2]:
        assert len({(r['tx'],r['ty'],r['numerator']) for r in atlas['rows'] if r['family']==family})==1
    (OUT/'alpha.bin').write_bytes(b''.join(images[r['scene']].getchannel('A').tobytes() for r in atlas['rows']))
    dump(OUT/'atlas.json',atlas);dump(OUT/'片区位移与定位映射.json',moves)
    assert sha(exe)==exe_sha and installed=={p.name:sha(p) for p in (ROOT/'Resource').glob('np_*.png')}
    report=dict(status='offline complete preview; user review and runtime integration pending',installed=False,game_files_unchanged=True,base_exe_sha256=exe_sha,scene_count=17,logical_fragment_count=13,native_pairs_unchanged=21,same_page_connectors=len(connectors),labels=labels,moves=moves,connectors=connectors,source_native_geometry_unchanged=True,main_family_transform_shared=True,all_native_port_identities_unchanged=True,road_overlap_checks=overlaps,legend_and_caption_clear=True,resources=len(list((OUT/'Resource').glob('*.png'))),mock_player_and_exploration=True,limits='Candidate display atlas and alpha require corresponding EXE mapping integration after preview approval. Existing exploration migration must be handled; do not install PNGs alone.')
    dump(OUT/'verification.json',report)
    print(json.dumps(dict(output=str(OUT),old_total_link_length=round(sum(x['old_length'] for x in connectors)),new_total_link_length=round(sum(x['new_length'] for x in connectors)),installed=False),ensure_ascii=False))
if __name__=='__main__':main()
