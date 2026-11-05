"""Mouse-only blocked movement fallback through native collision validation."""
import struct,hashlib,json
import flash_v4 as pe
import mouse_motion_v2 as combined

SITE=0x5da73;EXPECTED=bytes.fromhex('e8 78 df ff ff');SIZE=4096
AXIS_SITE=0x93c4d;AXIS_EXPECTED=bytes.fromhex('83 7d b8 64 0f 8c e5 01 00 00')
VECTORS=[(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1)]
FACES=[0,7,3,5,1,6,2,4]

def payload(base,origin):
    a=pe.Asm(origin);table=origin+0x800;faces=origin+0x840;hits=origin+0xf00;state=origin+0xf20
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    def native_original():
        a.raw('ff 75 10 ff 75 0c ff 75 08');a.jump('e8',base+0x5b9f0);a.raw('83 c4 0c')
    a.raw('55 8b ec 83 ec 30 53 56 57 8b 45 0c 8b 00 89 45 fc 8b 45 10 8b 00 89 45 f8')
    a.jump('e8',origin+0xa00)
    native_original()
    # Once sliding, do not alternate between recently visited cells while the
    # user holds the same pointer position. A fresh pointer move resets history.
    op('83 3d',state,b'\x01');a.jump('0f 85','original_checked')
    a.raw('8b 45 0c 8b 00 8b 55 10 0b 02');a.jump('0f 84','original_checked')
    a.raw('8b 45 0c 8b 00 89 45 e8 8b 45 10 8b 00 89 45 e4')
    a.jump('e8',origin+0xd00);a.raw('85 c0');a.jump('0f 84','original_checked')
    a.raw('8b 45 0c c7 00 00 00 00 00 8b 45 10 c7 00 00 00 00 00')
    a.label('original_checked')
    a.raw('8b 45 0c 8b 00 8b 55 10 0b 02');a.jump('0f 85','done')
    op('83 3d',base+0x180c88,b'\x02');a.jump('0f 85','done')
    op('80 3d',base+0x180dc0,b'\x01');a.jump('0f 85','done')
    for rva in (0x131b80,0x13b8d8,0x16ffc4,0x16ffc0):
        op('83 3d',base+rva,b'\x00');a.jump('0f 85','done')
    op('c7 05',state,pe.u32(1))
    # Find requested octant; invalid/zero input never starts movement.
    a.raw('33 f6');a.label('find')
    a.raw('8b 45 fc');op('3b 04 f5',table);a.jump('0f 85','find_next')
    a.raw('8b 45 f8');op('3b 04 f5',table+4);a.jump('0f 84','found')
    a.label('find_next');a.raw('46 83 fe 08');a.jump('0f 82','find');a.jump('e9','done')
    a.label('found');a.raw('8d 46 01 83 e0 07 89 45 f0 8d 46 07 83 e0 07 89 45 ec 8d 46 02 83 e0 07 89 45 d8 8d 46 06 83 e0 07 89 45 d4')
    # Mouse vector in world coordinates, matching the native direction origin.
    a.raw('8b 7d 08 8b 5f 3c');op('a1',base+0x13b8c0);op('03 05',base+0x16c100)
    a.raw('0f b7 57 04 2b c2 8b 53 2c c1 e2 03 2b c2 89 45 e0')
    op('a1',base+0x13b8c4);op('03 05',base+0x16c104)
    a.raw('0f b7 57 06 2b c2 8b 53 30 c1 e2 03 2b c2 89 45 dc')
    # Score A minus B by dot product; prefer the pointer's side of the wall.
    a.raw('8b 75 f0 8b 7d ec');op('8b 04 f5',table);op('2b 04 fd',table);a.raw('0f af 45 e0 8b d8')
    op('8b 04 f5',table+4);op('2b 04 fd',table+4);a.raw('0f af 45 dc 03 c3 85 c0');a.jump('0f 89','ordered')
    a.raw('8b 45 f0 8b 55 ec 89 55 f0 89 45 ec')
    a.raw('8b 45 d8 8b 55 d4 89 55 d8 89 45 d4')
    a.label('ordered');a.raw('33 f6')
    a.label('try');a.raw('85 f6');a.jump('0f 85','second');a.raw('8b 7d f0');a.jump('e9','chosen')
    a.label('second');a.raw('83 fe 01');a.jump('0f 85','third');a.raw('8b 7d ec');a.jump('e9','chosen')
    a.label('third');a.raw('83 fe 02');a.jump('0f 85','fourth');a.raw('8b 7d d8');a.jump('e9','chosen')
    a.label('fourth');a.raw('8b 7d d4');a.label('chosen')
    op('8b 04 fd',table);a.raw('89 45 e8');op('8b 04 fd',table+4);a.raw('89 45 e4')
    a.raw('8d 45 e4 50 8d 45 e8 50 ff 75 08');a.jump('e8',base+0x5b9f0);a.raw('83 c4 0c')
    # Native collision may itself redirect a trial along the wall. Accept only
    # a valid nonzero octant that does not move away from the actual pointer.
    for offset in ('e8','e4'):
        a.raw('8b 45 '+offset+' 83 c0 01 83 f8 02');a.jump('0f 87','rejected')
    a.raw('8b 45 e8 0b 45 e4');a.jump('0f 84','rejected')
    a.raw('8b 45 e8 0f af 45 e0 8b 55 e4 0f af 55 dc 03 c2 85 c0');a.jump('0f 8c','rejected')
    a.jump('e8',origin+0xd00);a.raw('85 c0');a.jump('0f 85','rejected')
    a.raw('8b 55 0c 8b 45 e8 89 02 8b 55 10 8b 45 e4 89 02')
    a.raw('33 ff');a.label('face');a.raw('8b 45 e8');op('3b 04 fd',table);a.jump('0f 85','next_face')
    a.raw('8b 45 e4');op('3b 04 fd',table+4);a.jump('0f 84','face_found')
    a.label('next_face');a.raw('47');a.jump('e9','face')
    a.label('face_found');a.raw('8b 45 08 8b 40 3c');op('8b 14 bd',faces);a.raw('89 50 34');op('ff 05',hits);a.jump('e9','done')
    a.label('rejected');a.raw('46 83 fe 04');a.jump('0f 82','try')
    a.label('done');a.raw('5f 5e 5b 8b e5 5d c3')
    blob=a.finish();assert len(blob)<0x800
    blob+=bytes(0x800-len(blob))+b''.join(struct.pack('<ii',x,y) for x,y in VECTORS)+b''.join(pe.u32(x) for x in FACES)
    axis=pe.Asm(origin+0x900);axis.raw('9c 60 33 c0')
    for rva in (0x180cd0,0x180ce4,0x180cf8,0x180d0c):axis.raw(b'\xa2'+pe.u32(base+rva))
    axis.raw('61 9d 83 7d b8 64');axis.jump('0f 8c',base+0x93e3c);axis.jump('e9',base+0x93c57)
    blob+=bytes(0x900-len(blob))+axis.finish()
    prep=pe.Asm(origin+0xa00)
    def p(code,address,suffix=b''):prep.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    prep.raw('9c 60')
    p('83 3d',base+0x180c88,b'\x02');prep.jump('0f 85','reset_only')
    p('80 3d',base+0x180dc0,b'\x01');prep.jump('0f 85','reset_only')
    p('83 3d',state,b'\x01');prep.jump('0f 85','reset')
    for source_rva,state_off in [(0x13d064,4),(0x1811cc,8),(0x1811d0,12)]:
        p('a1',base+source_rva);p('3b 05',state+state_off);prep.jump('0f 85','reset')
    prep.jump('e9','record')
    prep.label('reset_only');p('c7 05',state,pe.u32(0));prep.jump('e9','finish')
    prep.label('reset');p('c7 05',state,pe.u32(0));p('c7 05',state+16,pe.u32(0));p('c7 05',state+20,pe.u32(0))
    for source_rva,state_off in [(0x13d064,4),(0x1811cc,8),(0x1811d0,12)]:
        p('a1',base+source_rva);p('a3',state+state_off)
    prep.label('record');prep.raw('8b 55 08 0f b7 42 04 c1 e8 04 0f b7 52 06 c1 ea 04 c1 e2 10 0b c2')
    p('83 3d',state+16,b'\x00');prep.jump('0f 84','append')
    p('3b 05',state+24);prep.jump('0f 84','finish')
    prep.label('append');p('a3',state+24);p('8b 0d',state+20);p('89 04 8d',state+32)
    prep.raw('41 83 e1 0f');p('89 0d',state+20)
    p('83 3d',state+16,b'\x10');prep.jump('0f 83','finish');p('ff 05',state+16)
    prep.label('finish');prep.raw('61 9d c3')
    prepb=prep.finish();assert len(prepb)<0x300
    blob+=bytes(0xa00-len(blob))+prepb
    visit=pe.Asm(origin+0xd00)
    def v(code,address,suffix=b''):visit.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    # Uses the main helper frame; scratch coordinates are e8/e4.
    visit.raw('51 52 8b 55 08 0f b7 42 04 c1 e8 04 03 45 e8 25 ff ff 00 00 0f b7 52 06 c1 ea 04 03 55 e4 c1 e2 10 0b c2')
    v('8b 0d',state+16);visit.raw(b'\xba'+pe.u32(state+32));visit.raw('85 c9');visit.jump('0f 84','not_visited')
    visit.label('loop');visit.raw('3b 02');visit.jump('0f 84','visited');visit.raw('83 c2 04 49');visit.jump('0f 85','loop')
    visit.label('not_visited');visit.raw('33 c0 5a 59 c3');visit.label('visited');visit.raw('b8 01 00 00 00 5a 59 c3')
    blob+=bytes(0xd00-len(blob))+visit.finish();blob+=bytes(SIZE-len(blob))
    return {'blob':blob,'origin':origin,'hits':hits,'patches':{SITE:pe.branch(0xe8,base+SITE,origin),
        AXIS_SITE:pe.branch(0xe9,base+AXIS_SITE,origin+0x900)+b'\x90'*5}}

def candidate(source):
    out,plans=combined.candidate(source);header,opt,sections=pe.pe_info(out);sa,fa=struct.unpack_from('<II',out,opt+32)
    align=lambda n,a:(n+a-1)//a*a
    rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);raw=align(len(out),fa)
    plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+rva);hdr=opt+struct.unpack_from('<H',out,header+20)[0]+len(sections)*40
    if hdr+40>min(s[4] for s in sections) or any(out[hdr:hdr+40]):raise ValueError('No section header room')
    off=pe.rva_offset(source,SITE)
    if source[off:off+5]!=EXPECTED:raise ValueError('Unexpected collision call')
    data=bytearray(out);data.extend(bytes(raw+SIZE-len(data)))
    struct.pack_into('<8sIIIIIIHHI',data,hdr,b'.paledge',SIZE,rva,SIZE,raw,0,0,0,0,0xe0000020)
    struct.pack_into('<H',data,header+6,len(sections)+1);struct.pack_into('<I',data,opt+56,align(rva+SIZE,sa))
    struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',data,opt+4)[0]+SIZE)
    data[raw:raw+SIZE]=plan['blob']
    for site,value in plan['patches'].items():
        off=pe.rva_offset(source,site);expected=EXPECTED if site==SITE else AXIS_EXPECTED
        if source[off:off+len(expected)]!=expected:raise ValueError('Unexpected mouse axis entry')
        data[off:off+len(value)]=value
    plans['edge']=plan
    return bytes(data),plans

def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plans=candidate(source)
    p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.mouse-combined-v1.exe';p.write_bytes(out)
    report={'status':'candidate; native and gameplay verification pending','candidate_sha1':hashlib.sha1(out).hexdigest(),
            'feature':'native validated adjacent-octant mouse edge slide plus cursor and transition fixes'}
    p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
