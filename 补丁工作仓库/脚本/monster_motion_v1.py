"""Carry signed per-route remainders instead of rounding every slow step away."""
import hashlib
import json
import struct
import flash_v4 as pe
import battle_entry_v5 as audio

SITE=0x73445
EXPECTED=bytes.fromhex('8b 4d e4 0f bf 51 16')
RADIUS_SITE=0x600A6
RADIUS_EXPECTED=bytes.fromhex('0f b7 51 04 c1 e2 04')
SIZE=8192


def payload(base,origin,story_safe=False,ai_offset=0x1c):
    # Preserve v2 byte reproducibility by default. Native live AI is at +18;
    # v3 explicitly supplies that offset, validated against real scene actors.
    assert ai_offset in (0x18,0x1c)
    a=pe.Asm(origin);state=origin+0x800
    def op(code,addr,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(addr)+suffix)
    a.raw('9c 60 8b 7d ec 0f b7 47 20 3d 00 10 00 00');a.jump('0f 82','fallback')
    a.raw('3d f0 ff 00 00');a.jump('0f 83','fallback')
    if story_safe:
        # Actor IDs alone also include props/story objects. Use the native
        # AI/route field; do not confuse it with the adjacent event fields.
        a.raw(bytes.fromhex('66 83 7f')+bytes([ai_offset,0]));a.jump('0f 84','fallback')
        a.raw(bytes.fromhex('66 83 7f')+bytes([ai_offset,255]));a.jump('0f 84','fallback')
        a.raw('f7 47 0c 80 00 00 00');a.jump('0f 85','fallback')
        op('f7 05',base+0x13b628,pe.u32(0x61));a.jump('0f 85','fallback')
        for offset in (0x131b80,0x131b7c,0x16ffc0,0x16ffc4):
            op('83 3d',base+offset,b'\0');a.jump('0f 85','fallback')
    a.raw('0f b7 45 f8 83 f8 48');a.jump('0f 83','fallback')
    a.raw('c1 e0 05');a.raw(b'\x05'+pe.u32(state));a.raw('8b f0 8b 5d e4')
    # AI's common chase block selects run animation 16. Restore a visible,
    # slower acceleration: patrol raw/3, chase raw*2/3, using the same carry.
    a.raw('31 d2 8b 4f 3c 85 c9');a.jump('0f 84','mode_done')
    a.raw('83 79 08 10');a.jump('0f 84','chase_mode')
    a.raw('f7 47 0c 00 00 00 04');a.jump('0f 84','mode_done')
    a.label('chase_mode');a.raw('ba 00 00 01 00')
    a.label('mode_done')
    # Key state by actor, raw vector, target and route command index.
    a.raw('39 3e');a.jump('0f 85','reset')
    a.raw('8b 43 16 39 46 04');a.jump('0f 85','reset')
    a.raw('8b 43 04 39 46 08');a.jump('0f 85','reset')
    a.raw('0f b7 43 02 25 ff 7f 00 00 09 d0 39 46 0c');a.jump('0f 84','calculate')
    a.label('reset');a.raw('89 3e 8b 43 16 89 46 04 8b 43 04 89 46 08')
    a.raw('0f b7 43 02 25 ff 7f 00 00 09 d0 89 46 0c c7 46 10 00 00 00 00 c7 46 14 00 00 00 00')
    # A live patch/save may start mid-cell with positions left by old rounding.
    # Recover only to the next grid boundary, holding the arrived axis there.
    a.raw('0f b7 47 04 0f b7 57 06 09 d0 83 e0 0f 89 46 1c')
    for axis,raw_offset,target_offset in [(4,0x16,0x18),(6,0x18,0x1a)]:
        label='recover_'+str(axis)
        a.raw(bytes.fromhex('0f b7 47')+bytes([axis]))
        a.raw(bytes.fromhex('66 83 7b')+bytes([raw_offset])+b'\x00')
        a.jump('0f 84',label+'_store');a.jump('0f 8c',label+'_floor')
        a.raw('83 c0 0f')
        a.label(label+'_floor');a.raw('25 f0 ff 00 00')
        a.label(label+'_store');a.raw(bytes.fromhex('66 89 46')+bytes([target_offset]))
    a.label('calculate')
    a.raw('b9 03 00 00 00 0f bf 43 16 f7 46 0c 00 00 01 00');a.jump('0f 84','divide_x')
    a.raw('01 c0')
    a.label('divide_x');a.raw('03 46 10 99 f7 f9 89 45 dc 89 56 10')
    a.raw('0f bf 43 18 f7 46 0c 00 00 01 00');a.jump('0f 84','divide_y')
    a.raw('01 c0')
    a.label('divide_y');a.raw('03 46 14 99 f7 f9 89 45 d4 89 56 14')
    a.raw('83 7e 1c 00');a.jump('0f 84','done')
    a.raw('8b 45 dc 0f b7 4f 04 0f b7 56 18');a.jump('e8','clamp');a.raw('89 45 dc')
    a.raw('8b 45 d4 0f b7 4f 06 0f b7 56 1a');a.jump('e8','clamp');a.raw('89 45 d4')
    a.label('done')
    a.raw('61 9d');a.jump('e9',base+0x73496)
    a.label('fallback');a.raw('61 9d');a.raw(EXPECTED);a.jump('e9',base+SITE+7)
    a.label('clamp');a.raw('29 ca 85 d2');a.jump('0f 8f','forward');a.jump('0f 8c','backward')
    a.label('zero');a.raw('31 c0 c3')
    a.label('forward');a.raw('85 c0');a.jump('0f 8e','zero')
    a.raw('39 d0');a.jump('0f 8e','clamped');a.raw('89 d0 c3')
    a.label('backward');a.raw('85 c0');a.jump('0f 8d','zero')
    a.raw('39 d0');a.jump('0f 8d','clamped');a.raw('89 d0')
    a.label('clamped');a.raw('c3')
    blob=a.finish()
    if len(blob)>0x400:raise ValueError('Motion code overlaps radius helper')
    radius=pe.Asm(origin+0x400)
    radius.raw('0f b7 51 04 50 8b 45 fc 0f b7 40 20 3d 00 10 00 00');radius.jump('0f 82','full')
    radius.raw('3d f0 ff 00 00');radius.jump('0f 83','full')
    if story_safe:
        radius.raw(bytes.fromhex('8b 45 fc 66 83 78')+bytes([ai_offset,0]));radius.jump('0f 84','full')
        radius.raw(bytes.fromhex('66 83 78')+bytes([ai_offset,255]));radius.jump('0f 84','full')
        radius.raw('f7 40 0c 80 00 00 00');radius.jump('0f 85','full')
        radius.raw(bytes.fromhex('f7 05')+pe.u32(base+0x13b628)+pe.u32(0x61));radius.jump('0f 85','full')
    radius.raw('66 83 79 02 f1');radius.jump('0f 84','half')
    radius.raw('66 83 79 02 fe');radius.jump('0f 85','full')
    radius.label('half');radius.raw('c1 e2 03 58');radius.jump('e9',base+RADIUS_SITE+7)
    radius.label('full');radius.raw('c1 e2 04 58');radius.jump('e9',base+RADIUS_SITE+7)
    helper=radius.finish();blob+=bytes(0x400-len(blob))+helper;blob+=bytes(SIZE-len(blob))
    return {'blob':blob,'origin':origin,'state':state,
            'patches':{SITE:pe.branch(0xe9,base+SITE,origin)+b'\x90'*2,
                       RADIUS_SITE:pe.branch(0xe9,base+RADIUS_SITE,origin+0x400)+b'\x90'*2}}


def candidate(source):
    out,audio_plan=audio.candidate(source);off=pe.rva_offset(source,SITE)
    if source[off:off+7]!=EXPECTED:raise ValueError('Slow movement entry differs')
    radius_off=pe.rva_offset(source,RADIUS_SITE)
    if source[radius_off:radius_off+7]!=RADIUS_EXPECTED:raise ValueError('AI distance threshold differs')
    header,opt,sections=pe.pe_info(out);sa,fa=struct.unpack_from('<II',out,opt+32)
    align=lambda n,a:(n+a-1)//a*a
    rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);raw=align(len(out),fa)
    plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+rva)
    hdr=opt+struct.unpack_from('<H',out,header+20)[0]+len(sections)*40
    if hdr+40>min(s[4] for s in sections) or any(out[hdr:hdr+40]):raise ValueError('No section room')
    data=bytearray(out);data.extend(bytes(raw+SIZE-len(data)))
    struct.pack_into('<8sIIIIIIHHI',data,hdr,b'.palmove',SIZE,rva,SIZE,raw,0,0,0,0,0xe0000020)
    struct.pack_into('<H',data,header+6,len(sections)+1)
    struct.pack_into('<I',data,opt+56,align(rva+SIZE,sa))
    struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',data,opt+4)[0]+SIZE)
    data[raw:raw+SIZE]=plan['blob']
    for site,patch in plan['patches'].items():
        position=pe.rva_offset(source,site);data[position:position+len(patch)]=patch
    # User-approved 37.5% party glow; same rhythm, duration and identity filter.
    glow=next(s for s in sections if s[0]==b'.palglw');chunk=data[glow[4]:glow[4]+glow[3]]
    needle=bytes.fromhex('8d 14 c5 00 00 00 00');index=chunk.find(needle)
    if index<0 or chunk.find(needle,index+1)>=0:raise ValueError('Glow scale differs')
    pos=glow[4]+index;data[pos:pos+7]=bytes.fromhex('8d 14 40 90 90 90 90')
    return bytes(data),{'audio':audio_plan,'motion':plan}


def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=candidate(source)
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.audio-v5-motion-v1-glow-middle.exe';path.write_bytes(out)
    report={'candidate_sha1':hashlib.sha1(out).hexdigest(),'status':'candidate only; native/gameplay checks pending',
            'features':['922ms measured cry window','signed motion remainder','37.5% approved party glow']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
