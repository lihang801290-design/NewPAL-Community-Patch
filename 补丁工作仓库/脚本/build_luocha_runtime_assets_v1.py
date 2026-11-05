"""Compile native-coordinate road geometry into a two-page code-native atlas."""
import json,hashlib,math
import heapq
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageChops
import luocha_boundary_geometry_v2 as geo
OUT=geo.WORK/'候选版本/luocha-return-v1'
N=640*480
# Common frame for each multi-floor family; separate scene identity everywhere.
# tx,ty, numerator/1000, page, label position
LAYOUT={502:(454,279,180,0,500,295),503:(165,194,100,0,320,185),506:(165,194,100,0,320,185),508:(165,194,100,0,320,185),
504:(171,80,80,0,225,75),505:(404,80,68,0,470,75),509:(20,172,80,0,70,166),507:(523,211,70,0,566,201),510:(25,345,70,0,72,337),
511:(198,213,105,1,320,205),514:(198,213,105,1,320,205),516:(198,213,105,1,320,205),512:(25,80,110,1,85,75),513:(180,84,155,1,305,76),
515:(490,200,75,1,545,192),517:(25,240,90,1,80,232),518:(525,304,140,1,570,301)}
NAMES={502:'洞外',503:'主洞·第一层',506:'主洞·第二层',508:'主洞·第三层',504:'上方短通道',505:'上方旧洞',509:'左S支洞',507:'右S支洞',510:'圆形支洞',
511:'主洞·第一层',514:'主洞·第二层',516:'主洞·第三层',512:'斜向通道',513:'狭长通道',515:'小S支洞',517:'左S支洞',518:'大殿'}

def compile_links(rows,pairs,res):
    """Route teleport dotted connectors through empty paper, never new roads."""
    byid={r['scene']:r for r in rows};blocked={};links=[]
    def obstacles(page,selected):
        key=(page,selected)
        if key in blocked:return blocked[key]
        occupied=Image.new('L',(640,480))
        for r in rows:
            if r['page']==page and (selected is None or not r['family'] or r['index']==selected):occupied=ImageChops.lighter(occupied,Image.open(res/r['overlay']).getchannel('A'))
        occupied=occupied.filter(ImageFilter.MaxFilter(7)).resize((160,120),Image.Resampling.BOX)
        b=np.asarray(occupied)>30;b[:19,:]=True;b[103:,:]=True;b[:,:4]=True;b[:,156:]=True;b[18:43,140:157]=True
        # A port adjacent to a closed hole must leave toward exterior paper;
        # the hole itself is not a connector channel.
        from build_luocha_boundary_routes_v1 import components
        labels,groups=components(~b);outside=1+max(range(len(groups)),key=lambda n:len(groups[n]));b|=labels!=outside
        blocked[key]=b;return b
    directions=[(1,0),(0,1),(-1,0),(0,-1)]
    for number,pair in enumerate(pairs,1):
        ra,rb=byid[pair['a']['scene']],byid[pair['b']['scene']]
        if ra['page']!=rb['page']:continue
        page=ra['page'];selected=ra['index'] if ra['family'] else rb['index'] if rb['family'] else None;b=obstacles(page,selected);pa=ra['ports'][str(number)]['page'];pb=rb['ports'][str(number)]['page']
        def endpoint(p,target):
            opts=[]
            for y in range(max(0,p[1]//4-7),min(120,p[1]//4+8)):
                for x in range(max(0,p[0]//4-7),min(160,p[0]//4+8)):
                    if not b[y,x]:opts.append((math.dist((x*4+2,y*4+2),p)+math.dist((x*4+2,y*4+2),target)*.07,x,y))
            assert opts,('no empty connector margin',number,p)
            _,x,y=min(opts);return x,y
        begin=endpoint(pa,pb);end=endpoint(pb,pa);initial=(*begin,4);heap=[(0,0,initial)];cost={initial:0};previous={};finish=None
        while heap:
            _,g,state=heapq.heappop(heap)
            if g!=cost[state]:continue
            x,y,dir=state
            if (x,y)==end:finish=state;break
            for n,(dx,dy) in enumerate(directions):
                xx,yy=x+dx,y+dy
                if not(0<=xx<160 and 0<=yy<120) or b[yy,xx]:continue
                nxt=(xx,yy,n);gg=g+1+(1.5 if dir!=4 and dir!=n else 0)
                if gg<cost.get(nxt,1e30):cost[nxt]=gg;previous[nxt]=state;heapq.heappush(heap,(gg+abs(xx-end[0])+abs(yy-end[1]),gg,nxt))
        assert finish is not None,('connector route missing',number)
        cells=[];now=finish
        while now!=initial:cells.append(now[:2]);now=previous[now]
        cells.append(initial[:2]);cells.reverse();points=[pa]+[[x*4+2,y*4+2] for x,y in cells]+[pb]
        simple=[points[0]]
        for k,p in enumerate(points[1:-1],1):
            a,c=points[k-1],points[k+1]
            if (p[0]-a[0])*(c[1]-p[1])!=(p[1]-a[1])*(c[0]-p[0]):simple.append(p)
        simple.append(points[-1]);im=Image.new('RGBA',(640,480));d=ImageDraw.Draw(im);distance=0
        for a,c in zip(simple,simple[1:]):
            length=math.dist(a,c)
            for i in range(math.ceil(length)):
                if int(distance+i)%6<2:
                    t=i/length if length else 0;x=a[0]+(c[0]-a[0])*t;y=a[1]+(c[1]-a[1])*t;d.ellipse((x-.5,y-.5,x+.5,y+.5),fill='#8c6942')
            distance+=length
        file=f'np_lr_link_{number:02d}_v1.png';im.save(res/file)
        links.append(dict(number=number,page=page,a=ra['index'],b=rb['index'],a_scene=ra['scene'],b_scene=rb['scene'],a_point=pa,b_point=pb,file=file,points=simple,empty_paper_grid_checked=True))
    return links

def main():
    OUT.mkdir(exist_ok=True);res=OUT/'Resource';res.mkdir(exist_ok=True)
    packet,jobs,ports=geo.data();geometry=json.loads((geo.OUT/'geometry.json').read_text(encoding='utf-8'))
    assert all(not r['missing_incoming'] for r in geometry['scenes'])
    title=ImageFont.truetype('C:/Windows/Fonts/simkai.ttf',30);sub=ImageFont.truetype('C:/Windows/Fonts/simkai.ttf',13)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',11);tiny=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',10)
    yy,xx=np.indices((480,640));noise=np.random.default_rng(20261104).normal(0,.65,(480,640))
    arr=np.zeros((480,640,3),np.uint8)
    for i,c in enumerate((229,211,174)):arr[:,:,i]=np.clip(c+noise-9*((xx-320)**2/320**2+(yy-240)**2/240**2),0,255)
    style_path=OUT/'aged-edge-style-reference.png'
    if style_path.exists():
        # Only low-frequency pigment variation is reused as a style texture.
        # The generated roads/numbers never become geometry or baked map labels.
        texture=np.asarray(Image.open(style_path).convert('RGB').resize((640,480)).filter(ImageFilter.GaussianBlur(12))).astype(float)
    else:texture=arr.astype(float)
    batch=geo.WORK/'地图开发/批量制图_20261102'
    shared_paper=batch/'共用羊皮纸底图_v1.png'
    assert hashlib.sha256(shared_paper.read_bytes()).hexdigest()=='7708c135bffba3ae61dfaa53e58d37055730e40b094445cb9869a7aa6849ab39'
    paper=Image.open(shared_paper).convert('RGBA').resize((640,480),Image.Resampling.LANCZOS)
    d=ImageDraw.Draw(paper);d.text((320,463),'M / Back：地图    Esc / B：关闭',font=small,fill='#674c30',anchor='mm')
    ui_layers=[]
    for page in ('前','后'):
        layer=Image.open(batch/f'02_{page}/统一UI层.png').convert('RGBA')
        assert layer.size==(1536,1024)
        # Reuse existing code-native title/subtitle and two legend symbols.
        # Dynamic goal work remains separate; no static quest marker is added.
        d=ImageDraw.Draw(layer);d.rectangle((1340,313,1510,393),fill=(0,0,0,0));d.rectangle((0,930,1535,1023),fill=(0,0,0,0))
        ui_layers.append(layer.resize((640,480),Image.Resampling.LANCZOS))
    rows=[];alphas=bytearray();assets=[];preview=Image.new('RGB',(1280,1440),'#e6d3ae')
    for index,r in enumerate(packet['candidate_scenes']):
        sid=r['scene_id'];w,h=r['grid'];tx,ty,num,page,lx,ly=LAYOUT[sid]
        base=paper.copy();base.alpha_composite(ui_layers[page]);d=ImageDraw.Draw(base)
        d.text((605,28),NAMES[sid],font=small,fill='#684729',anchor='rm')
        d.text((571,155),'同号相连',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',9),fill='#7f6442',anchor='lm')
        seen=set()
        for other,layout in LAYOUT.items():
            if layout[3]!=page:continue
            fragment=jobs[other]['fragment']
            if fragment in seen:continue
            seen.add(fragment);label='主洞' if other in (503,506,508,511,514,516) else NAMES[other]
            d.text((layout[4],layout[5]),label,font=small,fill='#775735',anchor='mm')
        base_name=f'np_lr_base_{sid}_v1.png';base.save(res/base_name)
        # Native coordinate scale is applied to masks and player identically.
        grid=Image.open(geo.OUT/f'{sid}-display-grid.png').convert('L')
        hi=Image.new('L',(2560,1920));size=(round(w*16*num/1000*4),round(h*16*num/1000*4))
        hi.paste(grid.resize(size,Image.Resampling.NEAREST),(tx*4,ty*4))
        mask=hi.filter(ImageFilter.GaussianBlur(3.1)).resize((640,480),Image.Resampling.LANCZOS)
        # Source geometry remains in its separate grid. This is display-only
        # antialiasing: no route search or source-image repaint occurs here.
        road=Image.new('RGBA',(640,480));rd=ImageDraw.Draw(road)
        # Light aged auxiliary margins, not a reconstruction of cave scenery.
        halo=ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(1.2)),mask)
        halo=halo.point(lambda v:round(v*.23))
        pigment=np.clip(np.array((150,112,76))+((texture-texture.mean(axis=(0,1)))*.30),0,255).astype(np.uint8)
        stain=Image.fromarray(pigment).convert('RGBA');stain.putalpha(halo);road.alpha_composite(stain)
        ink=Image.new('RGBA',road.size,'#80603e');ink.putalpha(mask.filter(ImageFilter.MaxFilter(3)).point(lambda v:round(v*.90)));road.alpha_composite(ink)
        bodyrgb=np.clip(np.array((242,225,186))+((texture-texture.mean(axis=(0,1)))*.13),0,255).astype(np.uint8)
        body=Image.fromarray(bodyrgb).convert('RGBA');body.putalpha(mask);road.alpha_composite(body)
        rd=ImageDraw.Draw(road)
        mapping={}
        for pair in ports['pairs']:
            for end in ('a','b'):
                p=pair[end]
                if p['scene']!=sid:continue
                route=next(q for q in ports['return_routes'] if q['id']==p['route_id'])
                zone=next(z for z in r['trigger_zones'] if z['tag']==p['tag'])
                wx,wy=zone['grid_center'];px=tx+(wx+.5)*16*num/1000;py=ty+(wy+.5)*16*num/1000
                # Numeric pair IDs remain the same across pages/floors.
                number=ports['pairs'].index(pair)+1;label=str(number)
                rd.rounded_rectangle((px-7,py-6,px+7,py+7),radius=2,fill='#f7e7bf',outline='#81562f')
                rd.text((px,py),label,font=tiny,fill='#57341b',anchor='mm')
                mapping[str(number)]=dict(tag=p['tag'],destination=route['destination_scene'],world=[(wx+.5)*16,(wy+.5)*16],page=[round(px),round(py)])
        # Port labels and cliff rims are revealable pixels belonging to this scene.
        alpha=road.getchannel('A');alpha_raw=alpha.tobytes();assert len(alpha_raw)==N;alphas.extend(alpha_raw)
        over_name=f'np_lr_road_{sid}_v1.png';road.save(res/over_name)
        d=ImageDraw.Draw(base)
        outgoing=sorted(mapping.items(),key=lambda kv:int(kv[0]))
        captions=[f'{k}→{NAMES[v["destination"]]}' + ('·后页' if LAYOUT[v['destination']][3]!=page and page==0 else '·前页' if LAYOUT[v['destination']][3]!=page else '') for k,v in outgoing]
        # Current scene's exits only; native data is never inferred from proximity.
        d.text((320,421),'   '.join(captions),font=small,fill='#67492b',anchor='mm')
        base.save(res/base_name)
        # Offline full-explored page review: all side caves + this main floor.
        rows.append(dict(index=index,scene=sid,width=w,height=h,tx=tx,ty=ty,numerator=num,denominator=1000,page=page,
            family=1 if sid in (503,506,508) else 2 if sid in (511,514,516) else 0,base=base_name,overlay=over_name,name=NAMES[sid],ports=mapping,
            alpha_sha256=hashlib.sha256(alpha_raw).hexdigest(),road_grid_sha256=hashlib.sha256((geo.OUT/f'{sid}-road-grid.png').read_bytes()).hexdigest()))
    links=compile_links(rows,ports['pairs'],res)
    # Full-page samples for every main layer, with all side fragments in view.
    for k,sid in enumerate((503,506,508,511,514,516)):
        current=next(r for r in rows if r['scene']==sid);page=Image.open(res/current['base']).convert('RGBA')
        for r in rows:
            if r['page']!=current['page'] or (r['family'] and r['scene']!=sid):continue
            page.alpha_composite(Image.open(res/r['overlay']).convert('RGBA'))
        for link in links:
            if link['page']!=current['page']:continue
            if any(rows[link[e]]['family'] and rows[link[e]]['scene']!=sid for e in ('a','b')):continue
            page.alpha_composite(Image.open(res/link['file']).convert('RGBA'))
        page.convert('RGB').save(OUT/f'preview-{sid}.png');preview.paste(page.convert('RGB'),(k%2*640,k//2*480))
    cursor=Image.open(geo.ROOT/'Resource/np_map_player_v2.png');cursor.save(res/'np_lr_player_v1.png')
    (OUT/'alpha.bin').write_bytes(alphas)
    for p in sorted(res.glob('*.png')):assets.append(dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (OUT/'assets.json').write_text(json.dumps(assets,indent=2),encoding='utf-8')
    (OUT/'atlas.json').write_text(json.dumps(dict(canvas=[640,480],rows=rows,collection='luocha-return',phase_flag=102,
        pairs=ports['pairs'],links=links,independent_masks=True,main_layers_auto_selected=True,
        style=dict(shared_paper=str(shared_paper.relative_to(geo.WORK)),shared_paper_sha256=hashlib.sha256(shared_paper.read_bytes()).hexdigest(),
            ui_layers=[f'地图开发/批量制图_20261102/02_{p}/统一UI层.png' for p in ('前','后')],complex_maps_only=True,decoration='thin aged auxiliary edges; no original cavern scenery recreation'),
        status='candidate; offline and gameplay tests pending'),ensure_ascii=False,indent=2),encoding='utf-8')
    preview.save(OUT/'atlas-review.png');print(json.dumps(dict(scenes=len(rows),assets=len(assets),pairs=len(ports['pairs']),alpha_bytes=len(alphas))))

if __name__=='__main__':main()
