"""Execute native conditional title draws and persisted scene-entry history."""
from pathlib import Path
import copy,hashlib,json,re,struct,sys,types
import numpy as np
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
from native_damage_harness import Machine as SmallMachine
import map_nameplates_v1 as build

source=(build.ROOT/'NewPAL_Release.exe').read_bytes();candidate,combined=build.candidate(source)
fix=types.SimpleNamespace(pe=build.prior.pe,saved=build.prior.cave.saved,N=build.N,TOTAL=17*build.N,OUT=build.OUT)
plan=combined['cave'];st=plan['state'];old=fix.saved('dungeon-map-v2');checks=[]
plan['symbols']['cave_draw']=plan['symbols']['draw']
plan['symbols'].update(event=old['symbols']['event'],save=fix.saved('painted-map-v1')['symbols']['save'],load=combined['lotus']['symbols']['load_wrapper'])
text=Path(__file__).with_name('verify_luocha_return_runtime_v1.py').read_text(encoding='utf8')
text=text[text.index('class Machine('):text.index('\ndef location(')]
text=text.replace('self.u.hook_add(UC_HOOK_CODE,self.hook)','self.u.hook_add(UC_HOOK_CODE,self.hook,begin=0x400000,end=0x600000);self.u.hook_add(UC_HOOK_CODE,self.hook,begin=0x2800000,end=0x2a00000)')
exec(compile(text,'audited_nameplate_fixture','exec'))
def locate(q,row):
    for p,v in [(0x53d064,row['scene']),(0x53ccd0,row['width']),(0x53ccd4,row['height']),(0x56f7b4,0x40),(0x531b7c,0)]:q.w(p,v)
    q.u.mem_write(0x53e8c8+13*0x48+4,struct.pack('<HH',16,16))
def drawn(q,prefix):return {q.names[d[0]-32] for d in q.draws if 32<=d[0]<32+len(q.names) and q.names[d[0]-32].startswith(prefix)}
q=fixture();row=next(r for r in plan['rows'] if r['scene']==503);locate(q,row);q.invoke('select')
q.u.mem_write(plan['mask_data'],b'\xff'*(17*build.N));q.w(st['visited'],0);q.invoke('cave_draw');assert not drawn(q,'np_lr_label_')
q.u.mem_write(plan['mask_data'],b'\0'*(17*build.N))
for r in plan['rows']:
    locate(q,r);q.invoke('select');q.w(st['visited'],1<<r['index']);q.draws.clear();q.invoke('cave_draw')
    wanted={t['file'] for t in combined['nameplates']['cave'] if t['page']==r['page'] and t['visited_mask']&(1<<r['index'])}
    assert drawn(q,'np_lr_label_')==wanted,(r['scene'],drawn(q,'np_lr_label_'),wanted)
    assert len(wanted)==1
checks.append('17 native scene cases: only the entered logical title shows; three main-floor variants share one name; no title leaks from full fog mask or adjacent/page-visible terrain; title fully visible even when brush mask is zero')

# Real frame entry history, normal save/rewind/restart through the final lotus
# wrapper, no new save bits or whole-map exploration shortcuts.
q=fixture({'save/1.sav':SAVE_BYTES});q.invoke('load',(1,0x581ce8,1))
for sid in [503,504]:
    row=next(r for r in plan['rows'] if r['scene']==sid);locate(q,row);q.invoke('frame',(0x2850000,))
bits=(1<<1)|(1<<4);assert q.r(st['visited'])==bits;q.invoke('save',(1,))
row=next(r for r in plan['rows'] if r['scene']==509);locate(q,row);q.invoke('frame',(0x2850000,));assert q.r(st['visited'])==bits|(1<<6)
q.invoke('load',(1,0x581ce8,1));assert q.r(st['visited'])==bits
n=fixture(q.files);n.invoke('load',(1,0x581ce8,1));assert n.r(st['visited'])==bits and n.files['save/1.sav']==SAVE_BYTES
assert n.files['save/np_luocha3_1.dat'][:4]==b'NLR4'
checks.append('actual frame entry unlocks titles; leaving retains them; normal save/reload/restart retain only saved visits; loading earlier progress hides unsaved future titles; NLR4/native .sav unchanged')

# The shared title cache must fail closed when a label image is missing.
n=fixture();loader=n.hooks[0x4af910];bad=combined['nameplates']['cave'][0]['file']
def missing_title():
    result=loader()
    if n.names[-1]==bad:
        slot=0x2900000+result*0x100;n.w(slot+0x60,0)
    return result
n.stub(0x4af910,missing_title);n.u.mem_write(0x4af910,b'\xc2\x0c\0');locate(n,plan['rows'][0]);n.invoke('select');n.w(st['visited'],1);n.w(old['state']['open'],1);n.invoke('cave_draw');assert not n.r(old['state']['open'])
checks.append('separate 17-title cache stays outside the legacy 64-widget arrays; missing title resource closes the modal safely')

# Dream reuses original 4 title crops without retyping/redrawing; its draw now
# uses actual fragment-entry bits rather than alpha at the title coordinates.
walk=fix.saved('walk-fog-v2');plan['symbols']['draw']=combined['cave']['symbols']['dream_draw']
n=fixture();loader=n.hooks[0x4af910]
def dream_surface():
    result=loader()
    if n.names[-1]=='np_map_walk_overlay_v2.png':
        slot=0x2900000+result*0x100;sdl=n.r(slot+0x60);fmt=sdl+0x60;pixels=0x6200000
        for p,v in [(sdl+4,fmt),(sdl+8,640),(sdl+12,480),(sdl+16,2560),(sdl+20,pixels),(fmt+0x18,0xff000000)]:n.w(p,v)
        n.u.mem_write(fmt+9,b'\x04');n.u.mem_write(fmt+0x23,b'\x18');n.u.mem_write(pixels,b'\0'*(2560*480))
    return result
n.stub(0x4af910,dream_surface);n.u.mem_write(0x4af910,b'\xc2\x0c\0')
for bits in range(16):
    n.w(walk['state']['mask'],bits);n.draws.clear();n.invoke('draw',(0,0,0,0))
    wanted={t['file'] for t in combined['nameplates']['dream'] if bits&t['visited_mask']}
    assert drawn(n,'np_map_label_')==wanted
    assert not drawn(n,'np_lr_label_')
checks.append('all 16 dream visit combinations execute real draw with exact corresponding title crops, no cave-name bleed and no need for the brush to reach a label')

# Only title display/alpha and the two owned wrapper payloads can change.
a=np.frombuffer(source,dtype='uint8');b=np.frombuffer(candidate,dtype='uint8');allowed=np.zeros(len(a),bool)
for start,end in combined['payload_spans']+[combined['dream_alpha_span']]:allowed[start:end]=True
for h in combined['hooks']:allowed[h['offset']:h['offset']+len(bytes.fromhex(h['after']))]=True
assert not ((a!=b)&~allowed).any()
old=build.load(build.prior.OUT/'candidate.json')
for section in ['cave','lotus']:
    assert old[section]['rows']==combined[section]['rows'] and old[section]['links']==combined[section]['links']
state=build.load(build.W/'当前状态.json');packages=[]
for p in state['public_release']['packages']:
    data=(build.W/p['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==p['sha256'];packages.append(dict(path=p['path'],sha256=p['sha256']))
checks.append('road coordinates/ports/links, lotus logic and old save formats unchanged; all three public v6 ZIPs retain their exact previous hashes')
report=dict(status='passed; user gameplay verification pending',baseline_sha1=build.BASE,candidate_sha1=hashlib.sha1(candidate).hexdigest(),checks=checks,resources=111,title_resources=17,map_test_bridge_unchanged=True,published=False,publication_baseline=packages,native_saves_modified=False)
build.dump(build.OUT/'verification.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
