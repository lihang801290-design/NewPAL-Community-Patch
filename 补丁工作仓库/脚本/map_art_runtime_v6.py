"""Integrate approved cave/lotus art and migrate old exploration in native x86."""
from pathlib import Path
import hashlib,json,shutil,struct
from PIL import Image,ImageDraw,ImageFilter
import flash_v4 as pe
import luocha_return_runtime_v1 as cave
import lotus_runtime_v2 as lotus
import lotus_runtime_v1 as lotus1

W=pe.ROOT/'补丁工作仓库';OUT=W/'候选版本/map-art-runtime-v6'
BASE='202d55090f16852968c4d97f4f8974999539bd73'
N=640*480
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()

def player():
    # A clean, code-native icon, with a retained 400px master. Final game PNGs
    # remain 25px so the existing widget and exact marker center are unchanged.
    k=16;im=Image.new('RGBA',(25*k,25*k));d=ImageDraw.Draw(im)
    halo=Image.new('RGBA',im.size);h=ImageDraw.Draw(halo)
    h.ellipse((3*k,1*k,22*k,25*k),fill=(247,213,119,90));halo=halo.filter(ImageFilter.GaussianBlur(k))
    outline='#68431b';gold='#efb72f';light='#ffe59b'
    d.ellipse((9*k,2*k,16*k,9*k),fill=gold,outline=outline,width=k)
    d.rounded_rectangle((8*k,9*k,17*k,18*k),radius=3*k,fill=gold,outline=outline,width=k)
    d.rounded_rectangle((10*k,14*k,15*k,24*k),radius=k,fill=gold,outline=outline,width=k)
    d.line((11*k,4*k,12*k,3*k,14*k,4*k),fill=light,width=k)
    d.line((10*k,11*k,10*k,16*k),fill=light,width=k)
    halo.alpha_composite(im);halo.save(OUT/'统一金色小人_高清原件400.png')
    final=halo.resize((25,25),Image.Resampling.LANCZOS)
    for name in ['np_lr_player_v1.png','np_map_player_v1.png','np_map_player_v2.png']:final.save(OUT/'Resource'/name)

def assets():
    OUT.mkdir(exist_ok=True);(OUT/'Resource').mkdir(exist_ok=True)
    cv=W/'候选版本/luocha-compact-v6-preview';lv=W/'候选版本/map-visual-v4-preview'
    for folder in [cv,lv]:
        for p in (folder/'Resource').glob('*.png'):
            if folder==lv and p.name.startswith('np_lr_'):continue
            shutil.copy2(p,OUT/'Resource'/p.name)
    shutil.copy2(cv/'atlas.json',OUT/'cave-atlas.json');shutil.copy2(cv/'alpha.bin',OUT/'alpha.bin')
    atlas=load(OUT/'cave-atlas.json')
    for row in atlas['rows']:row['alpha_sha256']=sha(Image.open(OUT/'Resource'/row['overlay']).getchannel('A').tobytes())
    dump(OUT/'cave-atlas.json',atlas)
    shutil.copy2(lv/'lotus-alpha.bin',OUT/'lotus-alpha.bin')
    shutil.copy2(W/'候选版本/lotus-map-v2/atlas.json',OUT/'lotus-atlas.json')
    player()
    # Include every runtime dependency, including unchanged dream/menu pieces.
    for p in (pe.ROOT/'Resource').glob('np_*.png'):
        if not (OUT/'Resource'/p.name).exists():shutil.copy2(p,OUT/'Resource'/p.name)
    manifest=[dict(path='Resource/'+p.name,sha256=sha(p.read_bytes()),size=p.stat().st_size,changed=p.read_bytes()!=(pe.ROOT/'Resource'/p.name).read_bytes()) for p in sorted((OUT/'Resource').glob('*.png'))]
    assert len(manifest)==94
    dump(OUT/'assets.json',manifest)

def candidate(source):
    assert hashlib.sha1(source).hexdigest()==BASE
    old=cave.saved('luocha-return-v1');origin=old['origin'];native=load(W/'候选版本/luocha-return-v1/atlas.json')
    previous_out=cave.OUT
    old_payload=cave.payload(origin,source,native['rows'],native['links'])
    at=pe.rva_offset(source,origin-pe.IMAGE_BASE)
    assert source[at:at+cave.SIZE]==old_payload['blob'],'Cave baseline payload differs'
    atlas=load(OUT/'cave-atlas.json');deltas=[(r['tx']-o['tx'],r['ty']-o['ty']) for o,r in zip(native['rows'],atlas['rows'])]
    migration=dict(old_magic=cave.MAGIC,magic=int.from_bytes(b'NLR4','little'),deltas=deltas)
    try:
        cave.OUT=OUT
        new=cave.payload(origin,source,atlas['rows'],atlas['links'],migration=migration)
    finally:cave.OUT=previous_out
    out=bytearray(source);out[at:at+cave.SIZE]=new['blob']
    lpold=lotus.saved('lotus-map-v2');la=load(OUT/'lotus-atlas.json');lp_origin=lpold['origin'];lat=pe.rva_offset(source,lp_origin-pe.IMAGE_BASE)
    profile=dict(count=lotus.COUNT,size=lotus.SIZE,magic=lotus.MAGIC,namespace='np_lotus1_%d.dat',alpha_offset=lotus1.ALPHA_OFFSET,out=lotus.OUT,previous=old,exclusive_scene=True,sample_during_events=True)
    lp_before=cave.payload(lp_origin,source,la['rows'],la['links'],profile)
    assert source[lat:lat+lotus.SIZE]==lp_before['blob'],'Lotus baseline payload differs'
    # The shared builder expects alpha.bin; use a distinct child directory.
    alpha_dir=OUT/'lotus-data';alpha_dir.mkdir(exist_ok=True);shutil.copy2(OUT/'lotus-alpha.bin',alpha_dir/'alpha.bin')
    profile.update(out=alpha_dir,previous=new)
    lp=cave.payload(lp_origin,source,la['rows'],la['links'],profile)
    out[lat:lat+lotus.SIZE]=lp['blob']
    # Lotus owns the five external hooks. They currently remain at stable
    # addresses, but verify/rewrite them rather than assuming that property.
    hooks=[];paint=cave.saved('painted-map-v1');viewer=cave.saved('dungeon-map-v2')
    for site,key,kind,size in [(viewer['symbols']['context'],'context_dispatch',0xe9,10),(paint['symbols']['frame'],'frame',0xe9,7),(paint['symbols']['write_sidecar'],'write_wrapper',0xe9,5),(0x4b589a,'load_wrapper',0xe8,5),(0x4691a0,'reset_wrapper',0xe9,6)]:
        offset=pe.rva_offset(source,site-pe.IMAGE_BASE);before=pe.branch(kind,site,lpold['symbols'][key])+b'\x90'*(size-5)
        assert source[offset:offset+size]==before
        after=pe.branch(kind,site,lp['symbols'][key])+b'\x90'*(size-5);out[offset:offset+size]=after
        hooks.append(dict(site=site,offset=offset,before=before.hex(),after=after.hex()))
    assert len(out)==len(source)
    plan=dict(cave={k:v for k,v in new.items() if k!='blob'},lotus={k:v for k,v in lp.items() if k!='blob'},migration=migration,hooks=hooks,payload_spans=[[at,at+cave.SIZE],[lat,lat+lotus.SIZE]])
    return bytes(out),plan

def main():
    assets();source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();target,plan=candidate(source)
    (OUT/'NewPAL_Release.exe').write_bytes(target)
    dump(OUT/'candidate.json',dict(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(target).hexdigest(),candidate_sha256=sha(target),size=len(target),**plan,status='candidate; offline tests pending'))
    print(json.dumps(dict(sha1=hashlib.sha1(target).hexdigest(),cave_code=plan['cave']['code_size'],lotus_code=plan['lotus']['code_size'],resources=94),ensure_ascii=False))
if __name__=='__main__':main()
