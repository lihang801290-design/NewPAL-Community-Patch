"""Display-only distant interactable cursor; native click eligibility unchanged."""
import hashlib,json,struct
import flash_v4 as pe
import snake_frame_v1 as snake

SIZE=4096
ENTRY=0x7493d;EXIT=0x74a4e
EXPECTED={ENTRY:bytes.fromhex('8b 15 34 ce 53 00'),EXIT:bytes.fromhex('8b e5 5d c3 cc')}

def payload(base,origin):
    a=pe.Asm(origin);state=origin+0xf00;symbols={}
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    symbols['entry']=a.pc;a.raw('9c 60 55 8b ec 83 ec 40')
    op('c7 05',state,pe.u32(0))
    for rva in (0x131b80,0x13b8d8,0x16ffc4,0x16ffc0):
        op('83 3d',base+rva,b'\x00');a.jump('0f 85','done')
    op('80 3d',base+0x180dc0,b'\x00');a.jump('0f 85','done')
    op('66 83 3d',base+0x1628e8,b'\xff');a.jump('0f 85','done')
    op('a1',base+0x13ce34);a.raw('85 c0');a.jump('0f 84','done')
    op('a1',base+0x12cda0);a.raw('83 f8 01');a.jump('0f 86','done');a.raw('3d 00 08 00 00');a.jump('0f 87','done')
    a.raw('89 45 f8 c7 45 fc 01 00 00 00')
    a.label('object');a.raw('8b 45 fc');op('3b 05',base+0x13a5fc);a.jump('0f 84','next')
    a.raw('6b c0 48 05');a.raw(pe.u32(base+0x13e8c8));a.raw('8b d8 8b 43 0c a9 00 80 00 00');a.jump('0f 84','next')
    a.raw('a9 04 00 00 00');a.jump('0f 85','next')
    a.raw('66 83 7b 1a 00');a.jump('0f 84','next')
    a.raw('66 83 7b 22 00');a.jump('0f 85','next')
    # Actual playable followers must not receive an interaction prompt.
    a.raw('0f b7 43 20 83 f8 05');a.jump('0f 87','not_party');a.raw('f7 43 0c 80 00 00 00');a.jump('0f 85','next')
    a.label('not_party');a.raw('8b 73 3c 85 f6');a.jump('0f 84','next')
    a.raw('0f b7 46 4a 0f b7 56 4c c1 e2 10 0b c2 8b f8 83 e7 0f c1 e7 05');op('8b bf',base+0x19d214)
    a.raw('c7 45 cc 00 00 00 00')
    a.label('cache');a.raw('85 ff');a.jump('0f 84','next');a.raw('3b 07');a.jump('0f 84','frame')
    a.raw('8b 7f 04 ff 45 cc 81 7d cc 00 10 00 00');a.jump('0f 82','cache');a.jump('e9','next')
    a.label('frame');a.raw('0f b7 47 14 85 c0');a.jump('0f 84','next');a.raw('89 45 f4 0f b7 47 16 85 c0');a.jump('0f 84','next');a.raw('89 45 f0')
    a.raw('0f b7 43 04 0f bf 56 10 2b c2');op('2b 05',base+0x16c100);a.raw('89 45 ec')
    a.raw('0f b7 43 06 0f bf 56 14 2b c2');op('2b 05',base+0x16c104);a.raw('89 45 e8')
    a.raw('8b 45 ec 83 e8 08 89 45 e4 8b 45 e8 83 e8 08 89 45 dc')
    a.raw('8b 45 f4 83 c0 08 81 7d f4 7f 02 00 00');a.jump('0f 86','width_ok');a.raw('b8 32 00 00 00')
    a.label('width_ok');a.raw('03 45 ec 89 45 e0 8b 45 f0 83 c0 08 81 7d f0 df 01 00 00');a.jump('0f 86','height_ok');a.raw('b8 32 00 00 00')
    a.label('height_ok');a.raw('03 45 e8 89 45 d8 81 3e cf 02 00 00');a.jump('0f 84','special719')
    a.raw('81 3e 70 02 00 00');a.jump('0f 85','rect')
    a.raw('8b 45 ec 83 c0 32 89 45 e0 8b 45 e8 83 c0 32 89 45 d8');a.jump('e9','rect')
    a.label('special719');a.raw('0f b7 43 04');op('2b 05',base+0x16c100);a.raw('8b d0 83 e8 08 89 45 e4 83 c2 50 89 55 e0 0f b7 43 06');op('2b 05',base+0x16c104)
    a.raw('8b d0 83 e8 3c 89 45 dc 83 c2 14 89 55 d8')
    a.label('rect');op('a1',base+0x13b8c0);a.raw('3b 45 e4');a.jump('0f 8e','next');a.raw('3b 45 e0');a.jump('0f 8d','next')
    op('a1',base+0x13b8c4);a.raw('3b 45 dc');a.jump('0f 8e','next');a.raw('3b 45 d8');a.jump('0f 8d','next')
    a.raw('f7 43 0c 20 00 00 00');a.jump('0f 85','done')
    op('a1',base+0x13ce34);op('a3',state);a.raw('8b 50 08');op('89 15',state+4)
    a.raw('ba 09 00 00 00 f7 43 0c 40 00 00 00');a.jump('0f 84','set');a.raw('ba 0a 00 00 00')
    a.label('set');a.raw('89 50 08');op('ff 05',state+8);a.jump('e9','done')
    a.label('next');a.raw('ff 45 fc 8b 45 fc 3b 45 f8');a.jump('0f 82','object')
    a.label('done');a.raw('8b e5 5d 61 9d');op('8b 15',base+0x13ce34);a.jump('e9',base+ENTRY+6)
    symbols['exit']=a.pc;a.raw('9c 60');op('a1',state);a.raw('85 c0');a.jump('0f 84','restored')
    op('3b 05',base+0x13ce34);a.jump('0f 85','clear');op('8b 15',state+4);a.raw('89 50 08')
    a.label('clear');op('c7 05',state,pe.u32(0))
    a.label('restored');a.raw('61 9d 8b e5 5d c3')
    blob=a.finish();assert len(blob)<0xf00
    return {'blob':blob+bytes(SIZE-len(blob)),'origin':origin,'state':state,'symbols':symbols,
            'patches':{ENTRY:pe.branch(0xe9,base+ENTRY,symbols['entry'])+b'\x90',EXIT:pe.branch(0xe9,base+EXIT,symbols['exit'])}}

def candidate(source):
    out,_=snake.candidate(source);header,opt,sections=pe.pe_info(out);sa,fa=struct.unpack_from('<II',out,opt+32)
    align=lambda n,a:(n+a-1)//a*a
    rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);raw=align(len(out),fa);hdr=opt+struct.unpack_from('<H',out,header+20)[0]+len(sections)*40
    if hdr+40>min(s[4] for s in sections) or any(out[hdr:hdr+40]):raise ValueError('No header room')
    plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+rva);data=bytearray(out);data.extend(bytes(raw+SIZE-len(data)))
    struct.pack_into('<8sIIIIIIHHI',data,hdr,b'.palhov',SIZE,rva,SIZE,raw,0,0,0,0,0xe0000020);struct.pack_into('<H',data,header+6,len(sections)+1)
    struct.pack_into('<I',data,opt+56,align(rva+SIZE,sa));struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',data,opt+4)[0]+SIZE);data[raw:raw+SIZE]=plan['blob']
    for site,value in plan['patches'].items():
        off=pe.rva_offset(source,site)
        if source[off:off+len(EXPECTED[site])]!=EXPECTED[site]:raise ValueError('Cursor draw gate differs')
        data[off:off+len(value)]=value
    return bytes(data),plan

if __name__=='__main__':
    out,plan=candidate((pe.ROOT/'NewPAL_Release.exe').read_bytes());p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.window-snake-hover-v1.exe';p.write_bytes(out)
    report={'status':'candidate; native/gameplay pending','target_sha1':hashlib.sha1(out).hexdigest(),'scope':'draw-only distant hand hints; native interaction selection untouched'}
    p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
