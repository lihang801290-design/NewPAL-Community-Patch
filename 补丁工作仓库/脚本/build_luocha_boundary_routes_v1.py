"""Boundary-first cave atlas. Native cells and audited portals are the inputs."""
import json, hashlib, zipfile
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from collections import deque

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'补丁工作仓库'
CASE=WORK/'地图开发/逐图开发/02_罗刹山洞（二次进入）'
OUT=CASE/'边界线路_v1'
FONT='C:/Windows/Fonts/msyh.ttc'
# Local side markers read from native boundary diagrams (grid coordinates).
# They label which side is road/void; they never bridge blocked native cells.
ROAD_MARKERS={503:[(10,25),(20,20),(35,14),(45,23),(54,26),(68,31),(78,35),(90,39),(110,47),(132,50),(150,54),(61,7),(76,6),(94,14),(98,8),(100,29),(119,6),(137,12),(148,14)]}
VOID_MARKERS={503:[(10,5),(63,19),(80,61),(20,70),(145,85),(108,108)],506:[(10,10),(78,39),(120,67)],508:[(10,10)],
 504:[(25,21),(55,44)],505:[(32,15),(80,32),(62,59)],509:[(40,22),(32,49),(42,70)],507:[(53,16),(51,47),(15,70)],
 510:[(49,26),(40,49)],511:[(30,8),(72,42),(50,76),(130,90)],514:[(10,10)],516:[(10,10)],517:[(29,29),(42,49)]}

def inputs():
    packet=json.loads((CASE/'数据核对_v1/地图数据包.json').read_text(encoding='utf-8'))
    ports=json.loads((CASE/'数据核对_v1/原生出口核对.json').read_text(encoding='utf-8'))
    return packet,ports

def diagnostic():
    OUT.mkdir(exist_ok=True)
    packet,ports=inputs()
    rows={r['scene_id']:r for r in packet['candidate_scenes']}
    sheet=Image.new('RGB',(1440,1200),'#e9dcc0');d=ImageDraw.Draw(sheet)
    with zipfile.ZipFile(WORK/'地图开发/地图测试工具/原生格数据.zip') as z:
        for k,id in enumerate((503,506,508)):
            r=rows[id];w,h=r['grid'];raw=z.read(str(r['resource_id'])+'.bin')
            assert hashlib.sha256(raw).hexdigest()==r['grid_sha256']
            v=np.frombuffer(raw,dtype='<u4').reshape(h,w)
            free=(v&0x60800000)==0
            rgb=np.full((h,w,3),(45,39,35),dtype=np.uint8)
            rgb[free]=(195,188,168)
            rgb[free&((v&0xf000)!=0)]=(73,160,104)
            # Red cells are native boundary-blocked cells, never inferred by RGB.
            rgb[(~free)&((v&255)>0)]=(187,87,70)
            im=Image.fromarray(rgb).resize((640,480),Image.Resampling.NEAREST)
            x,y=(k%2)*720,(k//2)*600
            sheet.paste(im,(x+40,y+45));d.text((x+40,y+12),str(id),font=ImageFont.truetype(FONT,22),fill='#35271e')
            for t in r['trigger_zones']:
                if any(p['source_scene']==id and p['tag']==t['tag'] for p in ports['return_routes']):
                    xx=x+40+t['grid_center'][0]*4;yy=y+45+t['grid_center'][1]*4
                    d.ellipse((xx-4,yy-4,xx+4,yy+4),fill='#e22a17');d.text((xx+5,yy),str(t['tag']),fill='#191111')
            for p in ports['return_routes']:
                if p['destination_scene']==id:
                    xx=x+40+p['arrival_grid'][0]*4;yy=y+45+p['arrival_grid'][1]*4
                    d.ellipse((xx-3,yy-3,xx+3,yy+3),fill='#164eea')
    sheet.save(OUT/'boundary-diagnostic.png')
    print(str(OUT/'boundary-diagnostic.png'))

def components(mask):
    h,w=mask.shape;labels=np.zeros((h,w),np.int32);groups=[]
    for y,x in zip(*np.where(mask)):
        if labels[y,x]:continue
        q=[(int(x),int(y))];label=len(groups)+1;labels[y,x]=label
        for xx,yy in q:
            for nx,ny in ((xx-1,yy),(xx+1,yy),(xx,yy-1),(xx,yy+1)):
                if 0<=nx<w and 0<=ny<h and mask[ny,nx] and not labels[ny,nx]:
                    labels[ny,nx]=label;q.append((nx,ny))
        groups.append(q)
    return labels,groups

class Cut:
    def __init__(self,n):self.g=[[] for _ in range(n)]
    def edge(self,u,v,c,reverse=0):
        a=[v,c,None];b=[u,reverse,a];a[2]=b;self.g[u].append(a);self.g[v].append(b)
    def solve(self,s,t):
        sys.setrecursionlimit(100000)
        while True:
            level=[-1]*len(self.g);level[s]=0;q=deque([s])
            while q:
                u=q.popleft()
                for v,c,_ in self.g[u]:
                    if c and level[v]<0:level[v]=level[u]+1;q.append(v)
            if level[t]<0:break
            pos=[0]*len(self.g)
            def flow(u,f):
                if u==t:return f
                while pos[u]<len(self.g[u]):
                    e=self.g[u][pos[u]];v,c,back=e
                    if c and level[v]==level[u]+1:
                        sent=flow(v,min(f,c))
                        if sent:e[1]-=sent;back[1]+=sent;return sent
                    pos[u]+=1
                return 0
            while flow(s,1000000):pass
        return np.array([l>=0 for l in level])

def boundary_partition(v,anchors,scene):
    """Seal missing boundary edges by shortest cell cut between road/exterior markers.

    Native blocked cells are absolute barriers. Nonzero native floor fields and
    audited landings identify the road side only; they do not define its edge.
    No image brightness/color enters this operation.
    """
    h,w=v.shape;free=(v&0x60800000)==0
    seed=free&((v&0xf000)!=0)
    labels,groups=components(seed)
    seed=np.isin(labels,[n for n,g in enumerate(groups,1) if len(g)>=25])
    for x,y in anchors:
        if 0<=x<w and 0<=y<h and free[y,x]:seed[y,x]=True
    def nearest(x,y):
        pts=[(xx,yy) for yy in range(max(0,y-3),min(h,y+4)) for xx in range(max(0,x-3),min(w,x+4)) if free[yy,xx]]
        return min(pts,key=lambda p:(p[0]-x)**2+(p[1]-y)**2) if pts else None
    for x,y in ROAD_MARKERS.get(scene,[]):
        p=nearest(x,y)
        if p:seed[p[1],p[0]]=True
    dist=np.full((h,w),999,np.int32);dist[seed]=0;q=deque((int(x),int(y)) for y,x in zip(*np.where(seed)))
    while q:
        x,y=q.popleft()
        for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0<=nx<w and 0<=ny<h and dist[ny,nx]>dist[y,x]+1:
                dist[ny,nx]=dist[y,x]+1;q.append((nx,ny))
    exterior=np.zeros_like(free)
    for y in (1,2,h-2,h-3):exterior[y]|=free[y]&(dist[y]>3)
    for x in (1,2,w-2,w-3):exterior[:,x]|=free[:,x]&(dist[:,x]>3)
    for x,y in VOID_MARKERS.get(scene,[]):
        p=nearest(x,y)
        if p:
            xx,yy=p
            # A contrary field marker is not silently overridden.
            assert not seed[yy,xx],(scene,'conflicting side marker',p)
            q=deque([(xx,yy,0)]);seen={(xx,yy)}
            while q:
                px,py,n=q.popleft();exterior[py,px]=True
                if n>=7:continue
                for nx,ny in ((px-1,py),(px+1,py),(px,py-1),(px,py+1)):
                    if 0<=nx<w and 0<=ny<h and free[ny,nx] and dist[ny,nx]>2 and (nx,ny) not in seen:
                        seen.add((nx,ny));q.append((nx,ny,n+1))
    cut=Cut(w*h+2);s=w*h;t=s+1
    for y,x in zip(*np.where(free)):
        i=int(y*w+x)
        if seed[y,x]:cut.edge(s,i,1000000)
        if exterior[y,x]:cut.edge(i,t,1000000)
        for nx,ny in ((x+1,y),(x,y+1)):
            if nx<w and ny<h and free[ny,nx]:cut.edge(i,int(ny*w+nx),1,1)
    road=cut.solve(s,t)[:w*h].reshape(h,w)&free
    # Retain native trigger cells only at audited, active portals.
    return road,seed,exterior

def partition_review():
    OUT.mkdir(exist_ok=True);packet,ports=inputs()
    sheet=Image.new('RGB',(1440,2100),'#eadfc8');d=ImageDraw.Draw(sheet);reports=[]
    with zipfile.ZipFile(WORK/'地图开发/地图测试工具/原生格数据.zip') as z:
        for k,r in enumerate(packet['candidate_scenes']):
            w,h=r['grid'];v=np.frombuffer(z.read(str(r['resource_id'])+'.bin'),dtype='<u4').reshape(h,w)
            free=(v&0x60800000)==0;seed=free&((v&0xf000)!=0)
            anchors=[p['arrival_grid'] for p in ports['return_routes'] if p['destination_scene']==r['scene_id']]
            # NPC placements are not automatically floor seeds.
            road,seed,exterior=boundary_partition(v,anchors,r['scene_id'])
            labels,groups=components(road);chosen=list(range(1,len(groups)+1))
            rgb=np.full((h,w,3),(74,63,50),np.uint8);rgb[free]=(170,158,132);rgb[road]=(239,225,182);rgb[seed]=(92,156,108)
            im=Image.fromarray(rgb);im.thumbnail((340,290));im=im.resize((im.width*min(340//im.width,290//im.height),im.height*min(340//im.width,290//im.height)),Image.Resampling.NEAREST)
            x=k%4*360;y=k//4*420;sheet.paste(im,(x+(350-im.width)//2,y+35))
            d.text((x+5,y+5),str(r['scene_id']),font=ImageFont.truetype(FONT,18),fill='#312318')
            reports.append(dict(scene=r['scene_id'],groups=[dict(cells=len(g),seeds=sum(int(seed[y,x]) for x,y in g),edge=any(x in(0,w-1) or y in(0,h-1) for x,y in g)) for g in groups if len(g)>10],selected=chosen))
            Image.fromarray((road*255).astype(np.uint8)).save(OUT/f'{r["scene_id"]}-partition.png')
    sheet.save(OUT/'partition-review.png')
    (OUT/'partition-review.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print(json.dumps([dict(scene=r['scene'],large=[g for g in r['groups'] if g['cells']>100],selected=r['selected']) for r in reports]))

if __name__=='__main__':
    raise SystemExit('STOP: v1 automatic min-cut/closure was rejected. Use luocha_boundary_geometry_v2.py; source-check local missing edges. components() remains a generic grid utility only.')




