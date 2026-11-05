"""Keep native cursor/hover coordinates current without stealing movement mode."""
import hashlib,json
import flash_v4 as pe
import mouse_motion_v1 as old
import mouse_transition_v1 as transition

EXTRA_EXPECTED={0x74970:bytes.fromhex('e9 d9 00 00 00'),0x5c2dd:pe.u32(450)}
EXTRA={0x74970:b'\x90'*5,0x5c2dd:pe.u32(90)}

def payload(base,origin):
    a=pe.Asm(origin)
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    a.raw('9c 60 83 7d bc 00');a.jump('0f 85','original')
    for rva in (0x131b80,0x13b8d8,0x16ffc4,0x16ffc0):
        op('83 3d',base+rva,b'\x00');a.jump('0f 85','original')
    op('f7 05',base+0x13b628,pe.u32(0x40));a.jump('0f 85','original')
    op('66 83 3d',base+0x1628e8,b'\xff');a.jump('0f 85','original')
    # Idle mouse motion may select the mouse so its normal cursor can render.
    # Keep keyboard/controller ownership only while its direction is held.
    op('a1',base+0x180c88);a.raw(b'\xb9'+pe.u32(base+0x180cd0)+bytes.fromhex('ba 04 00 00 00'))
    a.label('direction');a.raw('39 41 0c');a.jump('0f 85','next_direction')
    a.raw('80 39 01');a.jump('0f 84','passive')
    a.raw('80 39 03');a.jump('0f 84','passive')
    a.label('next_direction');a.raw('83 c1 14 4a');a.jump('0f 85','direction')
    a.jump('e9','original')
    # Only omit the mode=2 store; execute all original coordinate conversion.
    a.label('passive')
    a.raw('61 9d');a.jump('e9',base+old.SITE+10)
    a.label('original');a.raw('61 9d');op('c7 05',base+0x180c88,pe.u32(2));a.jump('e9',base+old.SITE+10)
    blob=a.finish();assert len(blob)<=old.SIZE
    return {'origin':origin,'blob':blob+bytes(old.SIZE-len(blob)),
            'patches':{old.SITE:pe.branch(0xe9,base+old.SITE,origin)+b'\x90'*5,**EXTRA}}

def candidate(source):
    out,t=transition.candidate(source);out=bytearray(out)
    section=next(s for s in pe.pe_info(source)[2] if s[0]==b'.palrule')
    origin=pe.IMAGE_BASE+section[2]+0x600;off=section[4]+0x600
    previous=old.payload(pe.IMAGE_BASE,origin)
    if source[off:off+old.SIZE]!=previous['blob']:raise ValueError('Expected installed passive helper')
    plan=payload(pe.IMAGE_BASE,origin);out[off:off+old.SIZE]=plan['blob']
    for site,value in EXTRA.items():
        off=pe.rva_offset(source,site)
        if source[off:off+len(value)]!=EXTRA_EXPECTED[site]:raise ValueError('Cursor activity site differs')
        out[off:off+len(value)]=value
    return bytes(out),{'transition':t,'cursor':plan}

def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plans=candidate(source)
    p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.mouse-cursor-transition.exe';p.write_bytes(out)
    report={'status':'candidate; cursor gameplay verification pending','baseline_sha1':transition.BASELINE,
            'candidate_sha1':hashlib.sha1(out).hexdigest(),
            'features':['cross-map held mouse continuity','native passive cursor and hover coordinate refresh without stealing mode']}
    p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
