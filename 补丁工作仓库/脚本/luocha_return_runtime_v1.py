"""Two-page return-cave viewer; seventeen independent fog masks, native controls.

Append-only payload. Existing dream UI and test bridge remain independent.
No running-process injection, native map/collision/save modification, or release.
"""
import json,struct,hashlib,math
import flash_v4 as pe
from settings_toggle_v1 import imports
from build_luocha_runtime_assets_v1 import OUT
BASE='b5a0b8cd39ec092653fa78a643c6e156c0792b47'
N=640*480;COUNT=17;TOTAL=N*COUNT;SIZE=0xa0c000
MAGIC=int.from_bytes(b'NLR3','little')

def saved(name):return json.loads((OUT.parent/name/'candidate.json').read_text(encoding='utf-8'))

def payload(origin,source,rows,links,profile=None,migration=None,nameplates=None,dream_nameplates=None):
    # Opt-in reuse for subsequent maps. None reproduces the accepted cave blob.
    cfg=profile or {};COUNT=cfg.get('count',globals()['COUNT']);TOTAL=N*COUNT
    SIZE=cfg.get('size',globals()['SIZE']);MAGIC=cfg.get('magic',globals()['MAGIC'])
    if migration:MAGIC=migration['magic']
    namespace=cfg.get('namespace','np_luocha3_%d.dat');alpha_offset=cfg.get('alpha_offset',0x510000)
    old=saved('dungeon-map-v2');walk=saved('walk-fog-v2');paint=saved('painted-map-v1')
    a=pe.Asm(origin);sy={};iat=imports(source)
    fields=['current','point','page','bit','px','py','last_point','last_index','visited','loaded','dirty','pixel_x','pixel_y','center_x','center_y','changed',
            'surface','alpha_offset','row_skip','render','front_layer','back_layer','count','read_ok','io_error','matched']
    st={k:origin+0x8000+i*4 for i,k in enumerate(fields)}
    if migration:st['migrate_pending']=origin+0x8000+len(fields)*4
    ids=origin+0x8400;ptrs=origin+0x8500;dirty=origin+0x8700
    names=[r['base'] for r in rows]+[r['overlay'] for r in rows]+['np_lr_player_v1.png']+[r['file'] for r in links]
    assert len(names)<=64,'Widget ID area holds 64 entries; split the map or expand the layout explicitly'
    # Titles have their own small cache; do not overflow the original 64-entry
    # road/widget arrays when a stitched atlas has many named fragments.
    titles=list(nameplates or [])+list(dream_nameplates or [])
    title_ids=origin+0x9000;title_ptrs=origin+0x9100;title_loaded=origin+0x9200
    assert len(titles)<=64
    strings=origin+0xa000;text={};rawstrings=bytearray()
    for s in [namespace,*names,*[r['file'] for r in titles]]:text[s]=strings+len(rawstrings);rawstrings.extend(s.encode('ascii')+b'\0')
    assert len(rawstrings)<=0x1000,'strings/brush overlap'
    filename=origin+0x8800;brush=origin+0xb000;record=origin+0x10000;mask=record+28;alpha=origin+alpha_offset
    def op(s,p,end=b''):a.raw(bytes.fromhex(s)+pe.u32(p)+end)
    def store(p,v):op('c7 05',p,pe.u32(v))
    def cmp(p,v):op('81 3d',p,pe.u32(v))
    def start(n):sy[n]=a.pc;a.label(n)
    def call(n):a.jump('e8',n)
    def push(v):a.raw(b'\x68'+pe.u32(v))
    def manager(fn):a.raw(b'\xb9'+pe.u32(0x570b38));call(fn)
    def iatcall(n):op('ff 15',iat[n])

    start('select')
    if not profile:op('f6 05',0x56f7b4,b'\x40');a.jump('0f 84','select_bad')
    op('8b 1d',0x53a5fc);op('a1',0x52cda0);a.raw('85 c0');a.jump('0f 84','select_bad');a.raw('3d 00 08 00 00');a.jump('0f 87','select_bad')
    a.raw('3b d8');a.jump('0f 83','select_bad');a.raw('6b db 48 81 c3'+pe.u32(0x53e8c8).hex()+' 0f b7 4b 04 0f b7 73 06');op('a1',0x53d064)
    for r in rows:a.raw(b'\x3d'+pe.u32(r['scene']));a.jump('0f 84','sel_'+str(r['scene']))
    a.jump('e9','select_bad')
    for r in rows:
        i=r['index'];a.label('sel_'+str(r['scene']))
        for p,v in ((0x53ccd0,r['width']),(0x53ccd4,r['height'])):cmp(p,v);a.jump('0f 85','select_bad')
        a.raw('81 f9'+pe.u32(r['width']*16).hex());a.jump('0f 83','select_bad');a.raw('81 fe'+pe.u32(r['height']*16).hex());a.jump('0f 83','select_bad')
        # Exactly the same rational transform as geometry; no nearest road search.
        for mov,target,offset in (('8b c1','px',r['tx']),('8b c6','py',r['ty'])):
            a.raw(mov+' 69 c0'+pe.u32(r['numerator']).hex()+' 31 d2 bf e8 03 00 00 f7 f7 05'+pe.u32(offset).hex());op('a3',st[target])
        op('a1',st['py']);a.raw('c1 e0 10');op('0b 05',st['px']);op('a3',st['point'])
        store(st['current'],i);store(st['page'],r['page']);store(st['bit'],1<<i)
        if r['family']:store(st['front_layer' if r['family']==1 else 'back_layer'],i)
        a.raw('b8 01 00 00 00 c3')
    a.label('select_bad');a.raw('31 c0 c3')

    # Old context callers expect all registers except EAX to be preserved.
    start('context');a.raw('53 51 52 56 57');call('select');a.raw('85 c0');a.jump('0f 84','context_bad')
    for p in (0x531b80,0x56ffc4,0x56ffc0):cmp(p,0);a.jump('0f 85','context_bad')
    if cfg.get('sample_during_events'):cmp(0x531b7c,0);a.jump('0f 85','context_bad')
    op('f7 05',0x53b628,pe.u32(0x61));a.jump('0f 85','context_bad')
    for p in (0x53a605,0x5813d5):op('80 3d',p,b'\0');a.jump('0f 85','context_bad')
    op('80 3d',0x5813d4,b'\0');a.jump('0f 84','context_bad');op('66 83 3d',0x5628e8,b'\xff');a.jump('0f 85','context_bad')
    a.raw('b8 01 00 00 00');a.jump('e9','context_done');a.label('context_bad');a.raw('31 c0');a.label('context_done');a.raw('5f 5e 5a 59 5b c3')
    start('context_dispatch')
    if profile:
        for r in rows:cmp(0x53d064,r['scene']);a.jump('0f 84','context')
        a.jump('e9',cfg['previous']['symbols']['context_dispatch'])
    else:
        op('f6 05',0x56f7b4,b'\x40');a.jump('0f 85','context');a.jump('e9',saved('dream-map-isolation-v1')['origin'])

    start('paint');store(st['changed'],0);store(st['pixel_y'],0)
    a.label('paint_row');op('a1',st['py']);a.raw('83 e8 3c');op('03 05',st['pixel_y']);a.raw('3d e0 01 00 00');a.jump('0f 83','paint_nextrow')
    a.raw('69 d8 80 02 00 00');op('a1',st['current']);a.raw('69 c0'+pe.u32(N).hex()+' 03 d8');store(st['pixel_x'],0)
    a.label('paint_pixel');op('a1',st['px']);a.raw('83 e8 3c');op('03 05',st['pixel_x']);a.raw('3d 80 02 00 00');a.jump('0f 83','paint_nextpixel')
    a.raw('8d 3c 03 80 bf'+pe.u32(alpha).hex()+' 00');a.jump('0f 84','paint_nextpixel')
    op('a1',st['pixel_y']);a.raw('6b c0 79');op('03 05',st['pixel_x']);a.raw('0f b6 80'+pe.u32(brush).hex()+' 38 87'+pe.u32(mask).hex());a.jump('0f 83','paint_nextpixel')
    a.raw('88 87'+pe.u32(mask).hex());store(st['changed'],1)
    a.label('paint_nextpixel');op('ff 05',st['pixel_x']);cmp(st['pixel_x'],121);a.jump('0f 82','paint_pixel')
    a.label('paint_nextrow');op('ff 05',st['pixel_y']);cmp(st['pixel_y'],121);a.jump('0f 82','paint_row')
    cmp(st['changed'],0);a.jump('0f 84','paint_done');op('a1',st['current']);a.raw('c7 04 85'+pe.u32(dirty).hex()+' 01 00 00 00')
    a.label('paint_done');a.raw('c3')

    start('visit');op('a1',st['bit']);op('09 05',st['visited']);op('a1',st['point']);op('3b 05',st['last_point']);a.jump('0f 85','visit_new')
    op('a1',st['current']);op('3b 05',st['last_index']);a.jump('0f 84','visit_done')
    a.label('visit_new');op('a1',st['point']);op('a3',st['last_point']);op('a1',st['current']);op('a3',st['last_index']);call('paint')
    a.label('visit_done');a.raw('c3')

    start('widgets');cmp(st['loaded'],0);a.jump('0f 85','widgets_check');store(st['loaded'],1)
    for i,name in enumerate(names):
        push(1);push(text[name]);push(0);manager(0x4af910);op('a3',ids+i*4);a.raw('31 d2');call(old['symbols']['valid_widget']);op('a3',ptrs+i*4)
    a.label('widgets_check')
    for i in range(len(names)):
        op('8b 15',ptrs+i*4);a.raw('85 d2');a.jump('0f 84','widgets_bad');op('a1',ids+i*4);call(old['symbols']['valid_widget']);a.raw('85 c0');a.jump('0f 84','widgets_bad')
    a.raw('b8 01 00 00 00 c3');a.label('widgets_bad');a.raw('31 c0 c3')

    start('surface');op('a1',st['render']);a.raw('83 3c 85'+pe.u32(dirty).hex()+' 00');a.jump('0f 84','surface_ok')
    a.raw('8b 04 85'+pe.u32(ptrs+COUNT*4).hex()+' 8b 40 04 8b 30');op('89 35',st['surface'])
    for off,val in ((8,640),(12,480)):a.raw(bytes([0x81,0x7e,off])+pe.u32(val));a.jump('0f 85','surface_bad')
    a.raw('8b 46 04 85 c0');a.jump('0f 84','surface_bad');a.raw('80 78 09 04');a.jump('0f 85','surface_bad')
    a.raw('0f b6 48 23 f6 c1 07');a.jump('0f 85','surface_bad');a.raw('83 f9 18');a.jump('0f 87','surface_bad');a.raw('ba ff 00 00 00 d3 e2 3b 50 18');a.jump('0f 85','surface_bad')
    a.raw('c1 e9 03');op('89 0d',st['alpha_offset']);a.raw('56');iatcall('SDL_LockSurface');a.raw('83 c4 04 85 c0');a.jump('0f 85','surface_bad')
    a.raw('8b 7e 14 8b 46 10 2d 00 0a 00 00');op('a3',st['row_skip']);op('03 3d',st['alpha_offset']);op('8b 1d',st['render']);a.raw('69 db'+pe.u32(N).hex());store(st['pixel_y'],480)
    a.label('surface_row');a.raw('b9 80 02 00 00')
    a.label('surface_pixel');a.raw('0f b6 83'+pe.u32(alpha).hex()+' 0f b6 93'+pe.u32(mask).hex()+' 0f af c2 05 80 00 00 00 8b d0 c1 ea 08 03 c2 c1 e8 08 88 07 83 c7 04 43 49');a.jump('0f 85','surface_pixel')
    op('03 3d',st['row_skip']);op('ff 0d',st['pixel_y']);a.jump('0f 85','surface_row');op('ff 35',st['surface']);iatcall('SDL_UnlockSurface');a.raw('83 c4 04')
    op('a1',st['render']);a.raw('c7 04 85'+pe.u32(dirty).hex()+' 00 00 00 00')
    a.label('surface_ok');a.raw('b8 01 00 00 00 c3');a.label('surface_bad');a.raw('31 c0 c3')

    if titles:
        start('title_widgets');cmp(title_loaded,0);a.jump('0f 85','title_widgets_check');store(title_loaded,1)
        for j,t in enumerate(titles):
            push(1);push(text[t['file']]);push(0);manager(0x4af910);op('a3',title_ids+j*4);a.raw('31 d2');call(old['symbols']['valid_widget']);op('a3',title_ptrs+j*4)
        a.label('title_widgets_check')
        for j in range(len(titles)):
            op('8b 15',title_ptrs+j*4);a.raw('85 d2');a.jump('0f 84','title_widgets_bad');op('a1',title_ids+j*4);call(old['symbols']['valid_widget']);a.raw('85 c0');a.jump('0f 84','title_widgets_bad')
        a.raw('b8 01 00 00 00 c3');a.label('title_widgets_bad');a.raw('31 c0 c3')
    start('draw');call('widgets');a.raw('85 c0');a.jump('0f 84','draw_bad');iatcall('SteamAPI_RunCallbacks')
    push(0);push(0);push(0);op('a1',st['current']);a.raw('ff 34 85'+pe.u32(ids).hex());manager(0x4afa10)
    for r in rows:
        i=r['index'];skip='draw_skip_'+str(i);cmp(st['page'],r['page']);a.jump('0f 85',skip)
        if profile and cfg.get('exclusive_scene'):cmp(st['current'],i);a.jump('0f 85',skip)
        op('f7 05',st['visited'],pe.u32(1<<i));a.jump('0f 84',skip)
        if r['family']:cmp(st['front_layer' if r['family']==1 else 'back_layer'],i);a.jump('0f 85',skip)
        store(st['render'],i);call('surface');a.raw('85 c0');a.jump('0f 84','draw_bad')
        push(0);push(0);push(0);op('ff 35',ids+(COUNT+i)*4);manager(0x4afa10);a.label(skip)
    for j,link in enumerate(links):
        skip='link_skip_'+str(j);cmp(st['page'],link['page']);a.jump('0f 85',skip)
        if profile and cfg.get('exclusive_scene'):cmp(st['current'],link['a']);a.jump('0f 85',skip)
        bits=(1<<link['a'])|(1<<link['b']);op('a1',st['visited']);a.raw(b'\x25'+pe.u32(bits)+b'\x3d'+pe.u32(bits));a.jump('0f 85',skip)
        for end in ('a','b'):
            i=link[end];r=rows[i]
            if r['family']:cmp(st['front_layer' if r['family']==1 else 'back_layer'],i);a.jump('0f 85',skip)
            x,y=link[end+'_point'];op('80 3d',mask+i*N+y*640+x,b'\x80');a.jump('0f 82',skip)
        if link.get('active_actors'):
            active='link_actor_active_'+str(j)
            for actor in link['active_actors']:
                a.raw(b'\xba'+pe.u32(actor));call('actor_enabled');a.raw('85 c0');a.jump('0f 85',active)
            a.jump('e9',skip);a.label(active)
        for condition in link.get('conditions',[]):
            assert condition['kind']=='native_variable_ge'
            value=origin+0x8100;store(value,0);push(1);push(value);push(condition['parameter']);push(condition['actor']);call(0x49e2f0);a.raw('83 c4 10 85 c0');a.jump('0f 84',skip)
            cmp(value,condition['value']);a.jump('0f 82' if condition['value_is_true'] else '0f 83',skip)
        push(0);push(0);push(0);op('ff 35',ids+(COUNT*2+1+j)*4);manager(0x4afa10);a.label(skip)
    if nameplates:
        call('title_widgets');a.raw('85 c0');a.jump('0f 84','draw_bad')
        for j,t in enumerate(titles):
            if t.get('kind')!='cave':continue
            skip='title_skip_'+str(j);cmp(st['page'],t['page']);a.jump('0f 85',skip)
            op('f7 05',st['visited'],pe.u32(t['visited_mask']));a.jump('0f 84',skip)
            push(t['y']);push(t['x']);push(0);op('ff 35',title_ids+j*4);manager(0x4afa10);a.label(skip)
    op('a1',st['py']);a.raw('83 e8 0c 50');op('a1',st['px']);a.raw('83 e8 0c 50');push(0);op('ff 35',ids+COUNT*8);manager(0x4afa10)
    a.raw('c3');a.label('draw_bad');call(old['symbols']['close']);a.raw('c3')

    if dream_nameplates:
        # Replace only the dream draw entry. Reuse its already-verified widgets
        # and alpha update; titles follow scene history independently of brush.
        start('dream_draw');a.raw('55 8b ec 9c 60');call(walk['symbols']['widgets']);a.raw('85 c0');a.jump('0f 84','dream_titles_bad')
        call(walk['symbols']['surface']);a.raw('85 c0');a.jump('0f 84','dream_titles_bad')
        for i in range(2):push(0);push(0);push(0);op('ff 35',walk['ids']+i*4);manager(0x4afa10)
        call('title_widgets');a.raw('85 c0');a.jump('0f 84','dream_titles_bad')
        for j,t in enumerate(titles):
            if t.get('kind')!='dream':continue
            skip='dream_title_skip_'+str(j);op('f7 05',walk['state']['mask'],pe.u32(t['visited_mask']));a.jump('0f 84',skip)
            push(t['y']);push(t['x']);push(0);op('ff 35',title_ids+j*4);manager(0x4afa10);a.label(skip)
        a.jump('e9','dream_titles_done');a.label('dream_titles_bad');call(old['symbols']['close']);a.label('dream_titles_done');a.raw('61 9d 8b e5 5d c2 10 00')

    if cfg.get('sample_during_events'):
        # Exploration observes real positions during scripted transport. Map input
        # still uses the stricter context gate; no script/input state is changed.
        start('sample')
        for p in (0x531b80,0x531b7c):cmp(p,0);a.jump('0f 85','sample_done')
        # Script-owned control-enable bytes may be off while a lotus is moving;
        # they gate opening the UI, not passive recording of validated positions.
        op('80 3d',0x53a605,b'\0');a.jump('0f 85','sample_done')
        op('66 83 3d',0x5628e8,b'\xff');a.jump('0f 85','sample_done')
        cmp(0x53b8d8,0);a.jump('0f 84','sample_visit');cmp(0x53b8d8,0x40000000);a.jump('0f 85','sample_done')
        a.label('sample_visit');call('visit');a.label('sample_done');a.raw('c3')
    start('frame');a.raw('9c 60');call('select');a.raw('85 c0');a.jump('0f 84','frame_dream')
    if cfg.get('sample_during_events'):call('sample')
    call('context');a.raw('85 c0');a.jump('0f 84','frame_invalid')
    call('visit');cmp(old['state']['open'],0);a.jump('0f 84','frame_native');cmp(0x53b8d8,0x40000000);a.jump('0f 85','frame_invalid');call('draw');a.raw('61 9d c3')
    a.label('frame_invalid');call(old['symbols']['close']);a.label('frame_native');a.raw('61 9d');a.jump('e9',0x4653b0)
    a.label('frame_dream');a.raw('61 9d');a.jump('e9','dream_trampoline')
    start('dream_trampoline')
    if profile:a.jump('e9',cfg['previous']['symbols']['frame'])
    else:a.raw('9c 60');call(paint['symbols']['visit']);a.jump('e9',paint['symbols']['frame']+7)

    start('clear');a.raw('31 c0 bf'+pe.u32(record).hex()+' b9'+pe.u32((TOTAL+28)//4).hex()+' fc f3 ab');store(st['visited'],0);store(st['matched'],0)
    if migration:store(st['migrate_pending'],0)
    store(st['last_point'],0xffffffff);store(st['last_index'],0xffffffff);store(st['front_layer'],0 if profile else next(r['index'] for r in rows if r['scene']==503));store(st['back_layer'],0 if profile else next(r['index'] for r in rows if r['scene']==511))
    a.raw('b8 01 00 00 00 bf'+pe.u32(dirty).hex()+' b9'+pe.u32(COUNT).hex()+' fc f3 ab c3')
    start('checksum');a.raw('b8 c5 9d 1c 81 be'+pe.u32(record).hex()+' b9 06 00 00 00')
    a.label('checksum_header');a.raw('33 06 69 c0 93 01 00 01 83 c6 04 49');a.jump('0f 85','checksum_header')
    a.raw('83 c6 04 b9'+pe.u32(TOTAL//4).hex());a.label('checksum_data');a.raw('33 06 69 c0 93 01 00 01 83 c6 04 49');a.jump('0f 85','checksum_data');a.raw('c3')
    def path():
        op('ff 35',walk['state']['slot']);push(text[namespace]);push(filename);call(0x41a240);a.raw('83 c4 0c');push(filename);a.raw(b'\xb9'+pe.u32(0x5352e0));call(0x458cf0)
    def fopen(write=False):
        push(2 if write else 3);push(0);push(0);push(0x40000000 if write else 0x80000000);a.raw('50');call(0x458f60);a.raw('83 c4 14 85 c0')
    def rw(read,size):
        store(st['count'],0);push(st['count']);push(size);push(record);a.raw('56');call(0x459110 if read else 0x459190);a.raw('83 c4 10')
    def fclose():a.raw('56');call(0x458f40);a.raw('83 c4 04')
    start('read');cmp(walk['state']['signature_ok'],1);a.jump('0f 85','read_bad');path();fopen();a.jump('0f 84','read_bad');a.raw('8b f0');rw(True,TOTAL+29)
    a.raw('0f b6 c0');op('a3',st['read_ok']);fclose();a.raw('84 c0');a.jump('0f 84','read_bad');cmp(st['read_ok'],0);a.jump('0f 84','read_bad');cmp(st['count'],TOTAL+28);a.jump('0f 85','read_bad')
    if migration:
        store(st['migrate_pending'],0);cmp(record,MAGIC);a.jump('0f 84','read_magic_ok')
        cmp(record,migration['old_magic']);a.jump('0f 85','read_bad');store(st['migrate_pending'],1);a.label('read_magic_ok')
    else:cmp(record,MAGIC);a.jump('0f 85','read_bad')
    for off,name in ((4,'slot'),(8,'hash1'),(12,'hash2'),(16,'total')):op('a1',record+off);op('3b 05',walk['state'][name]);a.jump('0f 85','read_bad')
    # Header bits17..20 retain the last displayed main layer for each page.
    # Side caves do not change that layer, including after save/load/restart.
    if profile:
        op('a1',record+20);a.raw(b'\xa9'+pe.u32(~((1<<COUNT)-1)));a.jump('0f 85','read_bad')
    else:
        op('a1',record+20);a.raw('a9 00 00 e0 ff');a.jump('0f 85','read_bad')
        for shift in (17,19):
            op('a1',record+20);a.raw(bytes([0xc1,0xe8,shift])+bytes.fromhex('83 e0 03 83 f8 03'));a.jump('0f 84','read_bad')
    call('checksum');op('3b 05',record+24);a.jump('0f 85','read_bad')
    op('a1',record+20);a.raw(b'\x25'+pe.u32((1<<COUNT)-1) if profile else bytes.fromhex('25 ff ff 01 00'));op('a3',st['visited'])
    if not profile:
        for shift,offset,name in ((17,1,'front_layer'),(19,9,'back_layer')):
            op('a1',record+20);a.raw(bytes([0xc1,0xe8,shift])+bytes.fromhex('83 e0 03 83 c0')+bytes([offset]));op('a3',st[name])
    if migration:
        cmp(st['migrate_pending'],1);a.jump('0f 85','read_migration_done');call('migrate_layout');a.label('read_migration_done')
    store(st['matched'],1);a.raw('c3');a.label('read_bad');call('clear');a.raw('c3')
    if migration:
        # In-place memmove plus clearing wrapped columns is exactly a cropped
        # 2D rigid translation. No scratch buffer or native .sav writes needed.
        start('migrate_layout');a.raw('9c 60')
        assert len(migration['deltas'])==COUNT
        for i,(dx,dy) in enumerate(migration['deltas']):
            assert abs(dx)<640 and abs(dy)<480
            base=mask+i*N;offset=dy*640+dx
            if offset>0:
                a.raw(b'\xbe'+pe.u32(base+N-1-offset)+b'\xbf'+pe.u32(base+N-1)+b'\xb9'+pe.u32(N-offset)+bytes.fromhex('fd f3 a4 fc 31 c0'))
                a.raw(b'\xbf'+pe.u32(base)+b'\xb9'+pe.u32(offset)+bytes.fromhex('f3 aa'))
            elif offset<0:
                a.raw(b'\xbe'+pe.u32(base-offset)+b'\xbf'+pe.u32(base)+b'\xb9'+pe.u32(N+offset)+bytes.fromhex('fc f3 a4 31 c0'))
                a.raw(b'\xbf'+pe.u32(base+N+offset)+b'\xb9'+pe.u32(-offset)+bytes.fromhex('f3 aa'))
            if dx:
                width=abs(dx);left=0 if dx>0 else 640-width
                a.raw(b'\xbf'+pe.u32(base+left)+b'\xbb'+pe.u32(480)+bytes.fromhex('31 c0 fc'));a.label('migrate_columns_'+str(i))
                a.raw(b'\xb9'+pe.u32(width)+bytes.fromhex('f3 aa 81 c7')+pe.u32(640-width)+bytes.fromhex('4b'));a.jump('0f 85','migrate_columns_'+str(i))
        store(record,MAGIC);call('checksum');op('a3',record+24);store(st['migrate_pending'],0)
        a.raw('61 9d c3')
    start('write');store(st['io_error'],1);cmp(walk['state']['signature_ok'],1);a.jump('0f 85','write_done');store(record,MAGIC)
    for off,name in ((4,'slot'),(8,'hash1'),(12,'hash2'),(16,'total')):op('a1',walk['state'][name]);op('a3',record+off)
    if profile:op('a1',st['visited']);op('a3',record+20)
    else:op('a1',st['front_layer']);a.raw('83 e8 01 c1 e0 11');op('0b 05',st['visited']);a.raw('8b d0');op('a1',st['back_layer']);a.raw('83 e8 09 c1 e0 13 0b c2');op('a3',record+20)
    call('checksum');op('a3',record+24);path();fopen(True);a.jump('0f 84','write_done');a.raw('8b f0');rw(False,TOTAL+28)
    a.raw('0f b6 c0');op('a3',st['read_ok']);fclose();a.raw('84 c0');a.jump('0f 84','write_done');cmp(st['read_ok'],0);a.jump('0f 84','write_done');cmp(st['count'],TOTAL+28);a.jump('0f 85','write_done');store(st['io_error'],0)
    a.label('write_done');a.raw('c3')
    start('write_wrapper');a.raw('9c 60');call(cfg['previous']['symbols']['write_wrapper'] if profile else walk['symbols']['write_sidecar']);call('write');a.raw('61 9d c3')
    start('load_wrapper');a.raw('55 8b ec ff 75 10 ff 75 0c ff 75 08');call(cfg['previous']['symbols']['load_wrapper'] if profile else walk['symbols']['load']);a.raw('83 c4 0c 9c 60 83 7d 10 01');a.jump('0f 85','load_done');call('clear');call('read');a.label('load_done');a.raw('61 9d 8b e5 5d c3')
    start('reset_wrapper');a.raw('9c 60');call('clear');a.raw('61 9d');a.jump('e9',cfg['previous']['symbols']['reset_wrapper'] if profile else walk['symbols']['reset'])
    if any(link.get('active_actors') for link in links):
        start('actor_enabled');a.raw('51 52 56');op('8b 0d',0x52cda0);a.raw('85 c9');a.jump('0f 84','actor_bad');a.raw('81 f9 00 08 00 00');a.jump('0f 87','actor_bad');a.raw(b'\xbe'+pe.u32(0x53e8c8))
        a.label('actor_loop');a.raw('66 39 56 20');a.jump('0f 85','actor_next');a.raw('0f b7 46 1a 66 39 d0 0f 94 c0 0f b6 c0');a.jump('e9','actor_done')
        a.label('actor_next');a.raw('83 c6 48 49');a.jump('0f 85','actor_loop');a.label('actor_bad');a.raw('31 c0');a.label('actor_done');a.raw('5e 5a 59 c3')
    code=a.finish();assert len(code)<0x8000,(len(code),'code/state overlap')
    blob=bytearray(SIZE);blob[:len(code)]=code;blob[0xa000:0xa000+len(rawstrings)]=rawstrings
    rawalpha=(cfg.get('out',OUT)/'alpha.bin').read_bytes();assert len(rawalpha)==TOTAL;blob[alpha_offset:alpha_offset+TOTAL]=rawalpha
    brushdata=bytes(round(255*max(0,min(1,(60-math.hypot(x,y))/24))**2*(3-2*max(0,min(1,(60-math.hypot(x,y))/24)))) for y in range(-60,61) for x in range(-60,61))
    blob[0xb000:0xb000+len(brushdata)]=brushdata
    for p,v in ((st['last_point'],0xffffffff),(st['last_index'],0xffffffff),(st['front_layer'],0 if profile else 1),(st['back_layer'],0 if profile else 9)):
        struct.pack_into('<I',blob,p-origin,v)
    for i in range(COUNT):struct.pack_into('<I',blob,dirty-origin+i*4,1)
    result=dict(blob=bytes(blob),symbols=sy,state=st,ids=ids,ptrs=ptrs,dirty=dirty,record=record,mask_data=mask,alpha=alpha,brush=brush,origin=origin,code_size=len(code),rows=rows,links=links)
    if titles:result.update(nameplates=titles,title_ids=title_ids,title_ptrs=title_ptrs,title_loaded=title_loaded)
    return result

def candidate(source=None):
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
    assert hashlib.sha1(source).hexdigest()==BASE,'Expected exact current development baseline'
    atlas=json.loads((OUT/'atlas.json').read_text(encoding='utf-8'));rows=atlas['rows'];assert len(rows)==COUNT and [r['index'] for r in rows]==list(range(COUNT))
    h,o,secs=pe.pe_info(source);last=secs[-1];assert last[4]+last[3]==len(source)
    origin=pe.IMAGE_BASE+last[2]+last[3];p=payload(origin,source,rows,atlas['links']);out=bytearray(source);out.extend(p['blob']);patches={}
    old=saved('dungeon-map-v2');walk=saved('walk-fog-v2');paint=saved('painted-map-v1')
    isolation=saved('dream-map-isolation-v1')
    specs=[(old['symbols']['context'],pe.branch(0xe9,old['symbols']['context'],isolation['origin'])+b'\x90'*5,pe.branch(0xe9,old['symbols']['context'],p['symbols']['context_dispatch'])+b'\x90'*5),
       (paint['symbols']['frame'],b'\x9c\x60'+pe.branch(0xe8,paint['symbols']['frame']+2,paint['symbols']['visit']),pe.branch(0xe9,paint['symbols']['frame'],p['symbols']['frame'])+b'\x90'*2),
       (paint['symbols']['write_sidecar'],pe.branch(0xe9,paint['symbols']['write_sidecar'],walk['symbols']['write_sidecar']),pe.branch(0xe9,paint['symbols']['write_sidecar'],p['symbols']['write_wrapper'])),
       (0x4b589a,pe.branch(0xe8,0x4b589a,paint['symbols']['load']),pe.branch(0xe8,0x4b589a,p['symbols']['load_wrapper'])),
       (0x4691a0,pe.branch(0xe9,0x4691a0,paint['symbols']['reset'])+b'\x90',pe.branch(0xe9,0x4691a0,p['symbols']['reset_wrapper'])+b'\x90')]
    for site,before,after in specs:
        off=pe.rva_offset(source,site-pe.IMAGE_BASE);assert source[off:off+len(before)]==before,('hook differs',hex(site),source[off:off+len(before)].hex())
        out[off:off+len(after)]=after;patches[site-pe.IMAGE_BASE]=(before,after)
    sh=o+struct.unpack_from('<H',source,h+20)[0]+(len(secs)-1)*40;size=last[3]+SIZE
    for at in (sh+8,sh+16):struct.pack_into('<I',out,at,size)
    for at,v in ((o+56,last[2]+size),(o+4,struct.unpack_from('<I',source,o+4)[0]+SIZE),(o+64,0)):struct.pack_into('<I',out,at,v)
    p.update(patches=patches,header_offsets=[sh+8,sh+16,o+56,o+4,o+64]);return bytes(out),p

def main():
    data,p=candidate();(OUT/'NewPAL_Release.exe').write_bytes(data)
    report={k:v for k,v in p.items() if k not in ('blob','patches')};report.update(status='candidate; verification pending',baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest(),
        pages=2,independent_fog_records=COUNT,save_namespace='np_luocha3_%d.dat / NLR3',native_saves_modified=False,test_bridge_code_unchanged=True)
    (OUT/'candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('candidate_sha1','code_size','pages','independent_fog_records')}))

if __name__=='__main__':main()

