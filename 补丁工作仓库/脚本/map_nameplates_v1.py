"""Unpublished local build: fragment names reveal on actual scene-entry history."""
from pathlib import Path
import hashlib,json,copy,shutil
import numpy as np
from PIL import Image,ImageDraw
import map_art_runtime_v6 as prior
import preview_luocha_compact_v5 as compositor

W=prior.W;ROOT=prior.pe.ROOT;OUT=W/'候选版本/map-nameplates-v1'
BASE='a3ada144aa8d4b051005deb155dbd283acc0fc00'
N=640*480
load=prior.load;dump=prior.dump;sha=prior.sha
DREAM=[(502,'洞外入口',1,[519,425,601,444]),(498,'主洞',2,[88,207,153,229]),
       (499,'上層通道',4,[378,67,451,88]),(518,'羅剎大殿',8,[40,51,124,73])]

def assets():
    OUT.mkdir(exist_ok=True);res=OUT/'Resource';res.mkdir(exist_ok=True)
    for p in (prior.OUT/'Resource').glob('*.png'):shutil.copy2(p,res/p.name)
    atlas=load(prior.OUT/'cave-atlas.json');style=load(W/'候选版本/luocha-style-v2-20261104/style-verification.json')
    positions=load(W/'候选版本/luocha-compact-v6-preview/verification.json')['labels']
    compositor.init_ui();ui=compositor.ui;labels=[]
    for i,p in enumerate(positions):
        page=p['page'];sid=p['scene'];row=next(r for r in atlas['rows'] if r['scene']==sid)
        group=[r['scene'] for r in atlas['rows'] if r['family']==row['family']] if row['family'] else [sid]
        bits=sum(1<<r['index'] for r in atlas['rows'] if r['scene'] in group)
        b=p['new_box'];hi=Image.new('RGBA',(2560,1920));d=ImageDraw.Draw(hi)
        hi.alpha_composite(ui.SEAL.resize(((b[2]-b[0])*4,(b[3]-b[1])*4),Image.Resampling.LANCZOS),(b[0]*4,b[1]*4))
        d.text(((b[0]+b[2])*2,(b[1]+b[3])*2),p['label'],font=ui.font(13),anchor='mm',fill='#fff0cf')
        box=[b[0]-2,b[1]-2,b[2]+2,b[3]+2];file=f'np_lr_label_{i:02d}_v1.png'
        hi.resize((640,480),Image.Resampling.LANCZOS).crop(box).save(res/file)
        labels.append(dict(kind='cave',label=p['label'],file=file,page=page,scenes=group,visited_mask=bits,x=box[0],y=box[1]))
    # Recompose clean bases from original paper/title/caption components. Do not
    # cover existing labels by pasting a differently colored paper rectangle.
    for row in atlas['rows']:
        im=ui.base({},'front' if row['page']==0 else 'back',state=row['name'])
        im=ui.core.captions(im,style['captions'][str(row['scene'])]);im.save(res/row['base'])
        check=im.copy()
        for t in labels:
            if t['page']==row['page']:check.alpha_composite(Image.open(res/t['file']).convert('RGBA'),(t['x'],t['y']))
        before=np.array(Image.open(prior.OUT/'Resource'/row['base']).convert('RGBA')).astype(int)
        assert np.abs(before-np.array(check).astype(int)).max()<=4,'All-visited label recomposition changed the approved layout'
    # Dream labels were already in the revealable terrain. Separate them so
    # entering the fragment reveals its complete name even away from the brush.
    im=Image.open(res/'np_map_walk_overlay_v2.png').convert('RGBA');arr=np.array(im);dream=[]
    for sid,name,bits,box in DREAM:
        file=f'np_map_label_{sid}_v1.png';im.crop(box).save(res/file)
        x0,y0,x1,y1=box;arr[y0:y1,x0:x1,3]=0
        dream.append(dict(kind='dream',label=name,file=file,scenes=[sid],visited_mask=bits,x=x0,y=y0,box=box))
    Image.fromarray(arr).save(res/'np_map_walk_overlay_v2.png')
    (OUT/'dream-alpha.bin').write_bytes(arr[:,:,3].tobytes())
    dump(OUT/'nameplates.json',dict(cave=labels,dream=dream,rule='actual entered scene history; never proximity/fog alpha or page visibility'))
    for name in ['alpha.bin','lotus-alpha.bin','cave-atlas.json','lotus-atlas.json']:shutil.copy2(prior.OUT/name,OUT/name)
    entries=[dict(path='Resource/'+p.name,sha256=sha(p.read_bytes()),size=p.stat().st_size,existed=(ROOT/'Resource'/p.name).exists(),changed=not (ROOT/'Resource'/p.name).exists() or p.read_bytes()!=(ROOT/'Resource'/p.name).read_bytes()) for p in sorted(res.glob('*.png'))]
    assert len(entries)==111;dump(OUT/'assets.json',entries)

def candidate(source):
    assert hashlib.sha1(source).hexdigest()==BASE
    backup=load(ROOT/'.newpal-integrated-v6-install.json')['exe_backup'];pre_v6=(ROOT/backup).read_bytes()
    old_exe,old=prior.candidate(pre_v6);assert old_exe==source,'Installed v6 differs from its recorded exact rebuild'
    plates=load(OUT/'nameplates.json');atlas=load(OUT/'cave-atlas.json');saved_out=prior.cave.OUT
    try:
        prior.cave.OUT=OUT
        c=prior.cave.payload(old['cave']['origin'],source,atlas['rows'],atlas['links'],migration=old['migration'],nameplates=plates['cave'],dream_nameplates=plates['dream'])
    finally:prior.cave.OUT=saved_out
    out=bytearray(source);cat=old['payload_spans'][0][0];out[cat:cat+prior.cave.SIZE]=c['blob']
    la=load(OUT/'lotus-atlas.json');lpold=old['lotus']
    profile=dict(count=prior.lotus.COUNT,size=prior.lotus.SIZE,magic=prior.lotus.MAGIC,namespace='np_lotus1_%d.dat',alpha_offset=prior.lotus1.ALPHA_OFFSET,out=prior.OUT/'lotus-data',previous=c,exclusive_scene=True,sample_during_events=True)
    lp=prior.cave.payload(lpold['origin'],source,la['rows'],la['links'],profile)
    lat=old['payload_spans'][1][0];out[lat:lat+prior.lotus.SIZE]=lp['blob'];hooks=[]
    for h in old['hooks']:
        site=h['site'];key=next(k for k in ['context_dispatch','frame','write_wrapper','load_wrapper','reset_wrapper'] if prior.pe.branch(0xe8 if site==0x4b589a else 0xe9,site,lpold['symbols'][k]).hex()==h['after'][:10])
        kind=0xe8 if site==0x4b589a else 0xe9;size=len(bytes.fromhex(h['after']));offset=h['offset']
        before=bytes.fromhex(h['after']);assert source[offset:offset+size]==before
        after=prior.pe.branch(kind,site,lp['symbols'][key])+b'\x90'*(size-5);out[offset:offset+size]=after
        hooks.append(dict(site=site,offset=offset,before=before.hex(),after=after.hex()))
    walk=prior.cave.saved('walk-fog-v2');site=walk['symbols']['draw'];at=prior.pe.rva_offset(source,site-prior.pe.IMAGE_BASE)
    before=source[at:at+5];assert before==bytes.fromhex('55 8b ec 9c 60')
    after=prior.pe.branch(0xe9,site,c['symbols']['dream_draw']);out[at:at+5]=after;hooks.append(dict(site=site,offset=at,before=before.hex(),after=after.hex()))
    da=prior.pe.rva_offset(source,walk['alpha']-prior.pe.IMAGE_BASE)
    assert source[da:da+N]==Image.open(prior.OUT/'Resource/np_map_walk_overlay_v2.png').getchannel('A').tobytes()
    out[da:da+N]=(OUT/'dream-alpha.bin').read_bytes();assert len(out)==len(source)
    details=dict(cave={k:v for k,v in c.items() if k!='blob'},lotus={k:v for k,v in lp.items() if k!='blob'},migration=old['migration'],hooks=hooks,payload_spans=old['payload_spans'],dream_alpha_span=[da,da+N],nameplates=plates)
    return bytes(out),details

def previews():
    atlas=load(OUT/'cave-atlas.json');labels=load(OUT/'nameplates.json');dest=OUT/'预览';dest.mkdir(exist_ok=True)
    # Named fragments deliberately show full labels on entry, independent of
    # whether the character's reveal brush has reached the nameplate location.
    from preview_map_visual_v3 import fog_layer
    player=Image.open(OUT/'Resource/np_lr_player_v1.png').convert('RGBA')
    for scene in [503,511]:
        row=next(r for r in atlas['rows'] if r['scene']==scene);page=row['page'];bit=1<<row['index'];point=tuple(next(iter(row['ports'].values()))['page'])
        terrain=Image.open(OUT/'Resource'/row['overlay']).convert('RGBA')
        for title,visited in [('仅当前片区',bit),('全部片区',(1<<17)-1),('未进入任何片区',0)]:
            im=Image.open(OUT/'Resource'/row['base']).convert('RGBA')
            for r in atlas['rows']:
                if r['page']==page and (not r['family'] or r['scene']==scene) and visited&(1<<r['index']):
                    layer=Image.open(OUT/'Resource'/r['overlay']).convert('RGBA');im.alpha_composite(layer if title=='全部片区' else fog_layer(layer,[point]))
            if title=='全部片区':
                for l in atlas['links']:
                    if l['page']==page and all(not atlas['rows'][l[k]]['family'] or atlas['rows'][l[k]]['scene']==scene for k in ['a','b']):im.alpha_composite(Image.open(OUT/'Resource'/l['file']).convert('RGBA'))
            for t in labels['cave']:
                if t['page']==page and visited&t['visited_mask']:im.alpha_composite(Image.open(OUT/'Resource'/t['file']).convert('RGBA'),(t['x'],t['y']))
            if visited:im.alpha_composite(player,(point[0]-12,point[1]-12))
            im.save(dest/f'罗刹{["前","后"][page]}_{title}.png')
    for title,visited in [('仅洞外已进入',1),('全部片区',15),('未进入任何片区',0)]:
        im=Image.open(OUT/'Resource/np_map_fog_base_v1.png').convert('RGBA');layer=Image.open(OUT/'Resource/np_map_walk_overlay_v2.png').convert('RGBA')
        if visited:im.alpha_composite(layer if visited==15 else fog_layer(layer,[(531,371)]))
        for t in labels['dream']:
            if visited&t['visited_mask']:im.alpha_composite(Image.open(OUT/'Resource'/t['file']).convert('RGBA'),(t['x'],t['y']))
        im.save(dest/f'梦境_{title}.png')
    review=Image.new('RGB',(1280,1440))
    for i,(a,b) in enumerate([('梦境_仅洞外已进入.png','梦境_全部片区.png'),('罗刹前_仅当前片区.png','罗刹前_全部片区.png'),('罗刹后_仅当前片区.png','罗刹后_全部片区.png')]):
        review.paste(Image.open(dest/a),(0,i*480));review.paste(Image.open(dest/b),(640,i*480))
    review.save(dest/'进入才显示标题_左局部右全探索.png')

def main():
    assets();source=(ROOT/'NewPAL_Release.exe').read_bytes();target,p=candidate(source);(OUT/'NewPAL_Release.exe').write_bytes(target)
    dump(OUT/'candidate.json',dict(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(target).hexdigest(),status='candidate; offline checks pending',**p));previews()
    print(json.dumps(dict(candidate_sha1=hashlib.sha1(target).hexdigest(),cave_code=p['cave']['code_size'],separate_titles=17,resources=111,published=False),ensure_ascii=False))
if __name__=='__main__':main()
