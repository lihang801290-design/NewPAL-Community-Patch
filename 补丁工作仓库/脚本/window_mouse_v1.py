"""Scoped SDL window confinement for held map walking, with angle-based edges.

Preserves the accepted cursor/transition candidate; excludes unaccepted sliding.
Only the native per-frame main-loop call acquires/releases a drag-owned grab.
"""
import struct,hashlib,json
import flash_v4 as pe
import mouse_motion_v2 as combined
import edge_walk_v1 as axis_source

FRAME=0xaf27c;BORDER=0x93b2c;SIZE=4096
EXPECTED={FRAME:bytes.fromhex('e8 3f a5 ff ff'),BORDER:bytes.fromhex('83 3d c0 b8 53 00 32'),
          axis_source.AXIS_SITE:axis_source.AXIS_EXPECTED}
NAMES=['SDL_GetKeyboardFocus','SDL_GetMouseState','SDL_GetWindowGrab','SDL_SetWindowGrab','SDL_GetHint']

def payload(base,origin):
    a=pe.Asm(origin);symbols={};data=origin+0xe00
    attempt=data;owned=data+4;prior=data+8;mx=data+12;my=data+16;hits=data+20;releases=data+24;handle=data+28
    pointers={name:data+32+i*4 for i,name in enumerate(NAMES)}
    strings={};rawstrings=bytearray()
    for name in ['SDL2.dll',*NAMES,'SDL_GRAB_KEYBOARD']:
        strings[name]=origin+0xd00+len(rawstrings);rawstrings.extend(name.encode('ascii')+b'\0')
    assert len(rawstrings)<0x100
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    def f(name):op('ff 15',pointers[name])
    def start(name):symbols[name]=a.pc;a.label(name)
    start('frame');a.jump('e8',base+0xa97c0);a.raw('9c 60');a.jump('e8','resolve')
    for name in NAMES:
        op('83 3d',pointers[name],b'\x00');a.jump('0f 84','release')
    f('SDL_GetKeyboardFocus');a.raw('85 c0');a.jump('0f 84','physical_up');a.raw('8b f0')
    op('83 3d',owned,b'\x00');a.jump('0f 84','context')
    op('3b 35',owned);a.jump('0f 85','release')
    a.label('context')
    for rva in (0x131b80,0x13b8d8,0x16ffc4,0x16ffc0):
        op('83 3d',base+rva,b'\x00');a.jump('0f 85','release')
    op('f7 05',base+0x13b628,pe.u32(0x40));a.jump('0f 85','release')
    op('83 3d',base+0x180c88,b'\x02');a.jump('0f 85','release')
    op('80 3d',base+0x180dc0,b'\x01');a.jump('0f 85','release')
    a.raw(b'\x68'+pe.u32(my)+b'\x68'+pe.u32(mx));f('SDL_GetMouseState');a.raw('83 c4 08 a9 01 00 00 00');a.jump('0f 84','physical_up')
    op('83 3d',owned,b'\x00');a.jump('0f 85','done')
    # A drag must start inside the current game viewport.
    for coord,offset,extent in [(mx,0x1812d4,0x1812dc),(my,0x1812d8,0x1812e0)]:
        op('a1',coord);op('2b 05',base+offset);a.raw('85 c0');a.jump('0f 88','physical_up')
        op('3b 05',base+extent);a.jump('0f 83','physical_up')
    a.raw('56');f('SDL_GetWindowGrab');a.raw('83 c4 04');op('a3',prior)
    a.raw('85 c0');a.jump('0f 85','acquired')
    # Do not introduce keyboard grabbing if a user/Steam hint requests it.
    a.raw(b'\x68'+pe.u32(strings['SDL_GRAB_KEYBOARD']));f('SDL_GetHint');a.raw('83 c4 04 85 c0');a.jump('0f 84','grab')
    a.raw('80 38 31');a.jump('0f 84','done')
    a.label('grab');a.raw('6a 01 56');f('SDL_SetWindowGrab');a.raw('83 c4 08 56');f('SDL_GetWindowGrab');a.raw('83 c4 04 85 c0');a.jump('0f 84','done')
    a.label('acquired');op('89 35',owned);op('ff 05',hits);a.jump('e9','done')
    a.label('physical_up');a.jump('e8','stop_mouse');a.jump('e9','release')
    start('cleanup');a.raw('9c 60')
    a.label('release');op('a1',owned);a.raw('85 c0');a.jump('0f 84','done')
    op('83 3d',pointers['SDL_SetWindowGrab'],b'\x00');a.jump('0f 84','done')
    op('ff 35',prior);a.raw('50');f('SDL_SetWindowGrab');a.raw('83 c4 08')
    op('c7 05',owned,pe.u32(0));op('ff 05',releases);a.jump('e8','stop_mouse')
    a.label('done');a.raw('61 9d c3')
    # Clear only mouse-synthesized movement, preserving WASD and other devices.
    start('stop_mouse');op('83 3d',base+0x180c88,b'\x02');a.jump('0f 85','stop_done')
    op('80 3d',base+0x180dc0,b'\x01');a.jump('0f 85','stop_done')
    op('c6 05',base+0x180dc0,b'\x00')
    for i,rva in enumerate((0x180cd0,0x180ce4,0x180cf8,0x180d0c)):
        label='next_slot_'+str(i)
        op('83 3d',base+rva+12,b'\x02');a.jump('0f 85',label)
        op('83 3d',base+rva+16,b'\x00');a.jump('0f 85',label)
        op('c6 05',base+rva,b'\x00');a.label(label)
    a.label('stop_done');a.raw('c3')
    start('resolve');op('83 3d',attempt,b'\x00');a.jump('0f 85','resolved')
    op('c7 05',attempt,pe.u32(1));a.raw(b'\x68'+pe.u32(strings['SDL2.dll']));op('ff 15',base+0x10d238)
    a.raw('83 c4 04 85 c0');a.jump('0f 84','resolved');op('a3',handle)
    for name in NAMES:
        a.raw(b'\x68'+pe.u32(strings[name]));op('ff 35',handle);op('ff 15',base+0x10d23c);a.raw('83 c4 08');op('a3',pointers[name])
    a.label('resolved');a.raw('c3')
    blob=a.finish();assert len(blob)<0xc00
    # Original mouse direction generation, without the stale orthogonal axis.
    axis=pe.Asm(origin+0xc00);axis.raw('9c 60 33 c0')
    for rva in (0x180cd0,0x180ce4,0x180cf8,0x180d0c):axis.raw(b'\xa2'+pe.u32(base+rva))
    axis.raw('61 9d 83 7d b8 64');axis.jump('0f 8c',base+0x93e3c);axis.jump('e9',base+0x93c57)
    blob+=bytes(0xc00-len(blob))+axis.finish();blob+=bytes(0xd00-len(blob))+rawstrings;blob+=bytes(SIZE-len(blob))
    return {'blob':blob,'origin':origin,'symbols':symbols,'data':data,'owned':owned,'hits':hits,
            'patches':{FRAME:pe.branch(0xe8,base+FRAME,symbols['frame']),
                       BORDER:pe.branch(0xe9,base+BORDER,base+0x93c4d)+b'\x90'*2,
                       axis_source.AXIS_SITE:pe.branch(0xe9,base+axis_source.AXIS_SITE,origin+0xc00)+b'\x90'*5}}

def candidate(source):
    out,plans=combined.candidate(source);header,opt,sections=pe.pe_info(out);sa,fa=struct.unpack_from('<II',out,opt+32)
    align=lambda n,a:(n+a-1)//a*a
    rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);raw=align(len(out),fa)
    plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+rva);hdr=opt+struct.unpack_from('<H',out,header+20)[0]+len(sections)*40
    if hdr+40>min(s[4] for s in sections) or any(out[hdr:hdr+40]):raise ValueError('No section room')
    data=bytearray(out);data.extend(bytes(raw+SIZE-len(data)))
    struct.pack_into('<8sIIIIIIHHI',data,hdr,b'.palwin',SIZE,rva,SIZE,raw,0,0,0,0,0xe0000020)
    struct.pack_into('<H',data,header+6,len(sections)+1);struct.pack_into('<I',data,opt+56,align(rva+SIZE,sa));struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',data,opt+4)[0]+SIZE)
    data[raw:raw+SIZE]=plan['blob']
    for site,value in plan['patches'].items():
        off=pe.rva_offset(source,site)
        if source[off:off+len(EXPECTED[site])]!=EXPECTED[site]:raise ValueError('Unexpected window input site')
        data[off:off+len(value)]=value
    plans['window']=plan
    return bytes(data),plans

def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plans=candidate(source)
    p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.mouse-window-v1.exe';p.write_bytes(out)
    report={'status':'candidate; native and gameplay checks pending','candidate_sha1':hashlib.sha1(out).hexdigest(),
            'feature':'held map drag stays in window; release/focus/UI ends scoped grab; edge angle preserved',
            'not_included':'experimental auto edge sliding'}
    p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
