"""Resume a physically held native mouse walk after ordinary map transitions.

Based strictly on the installed abeab444 stage. Never writes the installed EXE.
Map-local eligibility and original hold timestamp live on the native stack.
"""
import hashlib,json
import flash_v4 as pe

BASELINE='abeab444bc503649626dc527ef99bafce32fe238'
ENTRY=0x9dc40
EXIT=0x9dd52
EXPECTED={ENTRY:bytes.fromhex('55 8b ec b9 38 0b 58 00'),EXIT:bytes.fromhex('b8 01 00 00 00 5d c3')}
SIZE=0x700

def payload(base,origin):
    a=pe.Asm(origin);symbols={};data=origin+0x600
    pointer=data;attempt=data+4;mx=data+8;my=data+12;count=data+16
    focusptr=data+20;handle=data+24
    dll=data+32;name=data+48;focusname=data+80
    context_counter=[0]
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    def start(label):symbols[label]=a.pc;a.label(label)
    def context(fail):
        for rva in (0x131b80,0x13b8d8,0x16ffc4,0x16ffc0):
            op('83 3d',base+rva,b'\x00');a.jump('0f 85',fail)
        op('83 3d',base+0x180c88,b'\x02');a.jump('0f 85',fail)
        op('f7 05',base+0x13b628,pe.u32(0x40));a.jump('0f 85',fail)
        context_counter[0]+=1;ok='map_marker_'+str(context_counter[0])
        op('66 83 3d',base+0x1628e8,b'\xff');a.jump('0f 84',ok)
        op('66 83 3d',base+0x1628e8,b'\xfd');a.jump('0f 85',fail)
        a.label(ok)
    def focus(fail):
        op('83 3d',focusptr,b'\x00');a.jump('0f 84',fail)
        op('ff 15',focusptr);a.raw('85 c0');a.jump('0f 84',fail)
    def mouse(fail):
        op('83 3d',pointer,b'\x00');a.jump('0f 84',fail)
        a.raw(b'\x68'+pe.u32(my)+b'\x68'+pe.u32(mx));op('ff 15',pointer)
        a.raw('83 c4 08 a9 01 00 00 00');a.jump('0f 84',fail)
    start('entry')
    a.raw('55 8b ec 83 ec 08 c7 45 fc 00 00 00 00 9c 60')
    context('entry_done')
    op('80 3d',base+0x180dc0,b'\x01');a.jump('0f 85','entry_done')
    a.raw('8b 45 08');op('3b 05',base+0x13d064);a.jump('0f 84','entry_done')
    a.jump('e8','resolve')
    focus('entry_done')
    mouse('entry_done')
    op('a1',base+0x180dc4);a.raw('89 45 f8 c7 45 fc 01 00 00 00')
    a.label('entry_done');a.raw('61 9d b9');a.raw(pe.u32(base+0x180b38));a.jump('e9',base+ENTRY+8)
    start('exit')
    a.raw('9c 60 83 7d fc 01');a.jump('0f 85','exit_done')
    context('exit_done');focus('exit_done');mouse('exit_done')
    # Native source reset first; then current physical position, not stale origin.
    a.raw(bytes.fromhex('6a 02 b9')+pe.u32(base+0x180b38));a.jump('e8',base+0xadf60)
    op('a1',mx);op('a3',base+0x1811cc);op('a1',my);op('a3',base+0x1811d0)
    # Y and X conversion use the original window scale and viewport offsets.
    op('a1',my);op('2b 05',base+0x1812d8);a.raw(bytes.fromhex('50 b9')+pe.u32(base+0x181280));a.jump('e8',base+0xadff0)
    a.raw('50') # save Y while converting X
    op('a1',mx);op('2b 05',base+0x1812d4);a.raw(bytes.fromhex('50 b9')+pe.u32(base+0x181280));a.jump('e8',base+0xadfa0)
    a.raw(bytes.fromhex('5a f3 0f 2a c2 51 f3 0f 11 04 24 f3 0f 2a c0 51 f3 0f 11 04 24 b9')+pe.u32(base+0x180b38))
    a.jump('e8',base+0xa8850)
    a.raw(bytes.fromhex('6a 01 6a 0f b9')+pe.u32(base+0x180b38));a.jump('e8',base+0xa9330)
    a.raw('8b 45 f8');op('a3',base+0x180dc4);op('ff 05',count)
    a.label('exit_done');a.raw('61 9d b8 01 00 00 00 8b e5 5d c3')
    start('resolve')
    op('83 3d',attempt,b'\x00');a.jump('0f 85','resolved')
    op('c7 05',attempt,pe.u32(1));a.raw(b'\x68'+pe.u32(dll));op('ff 15',base+0x10d238)
    a.raw('83 c4 04 85 c0');a.jump('0f 84','resolved')
    op('a3',handle)
    a.raw(b'\x68'+pe.u32(name)+b'\x50');op('ff 15',base+0x10d23c);a.raw('83 c4 08');op('a3',pointer)
    a.raw(b'\x68'+pe.u32(focusname));op('ff 35',handle);op('ff 15',base+0x10d23c);a.raw('83 c4 08');op('a3',focusptr)
    a.label('resolved');a.raw('c3')
    blob=a.finish()
    if len(blob)>0x600:raise ValueError('Payload too large')
    blob+=bytes(SIZE-len(blob));blob=bytearray(blob)
    blob[0x620:0x629]=b'SDL2.dll\0'
    blob[0x630:0x642]=b'SDL_GetMouseState\0'
    blob[0x650:0x665]=b'SDL_GetKeyboardFocus\0'
    assert len(blob)==SIZE
    return {'blob':bytes(blob),'origin':origin,'symbols':symbols,'data':data,
            'patches':{ENTRY:pe.branch(0xe9,base+ENTRY,symbols['entry'])+b'\x90'*3,
                       EXIT:pe.branch(0xe9,base+EXIT,symbols['exit'])+b'\x90'*2}}

def candidate(source):
    if hashlib.sha1(source).hexdigest()!=BASELINE:raise ValueError('Expected installed abeab444 stage')
    section=next(s for s in pe.pe_info(source)[2] if s[0]==b'.palrule')
    offset=section[4]+0x800;origin=pe.IMAGE_BASE+section[2]+0x800
    if any(source[offset:offset+SIZE]):raise ValueError('Reserved storage occupied')
    plan=payload(pe.IMAGE_BASE,origin);out=bytearray(source)
    for site,expected in EXPECTED.items():
        off=pe.rva_offset(source,site)
        if source[off:off+len(expected)]!=expected:raise ValueError(f'Unexpected map wrapper {site:x}')
        out[off:off+len(expected)]=plan['patches'][site]
    out[offset:offset+SIZE]=plan['blob']
    return bytes(out),plan

def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=candidate(source)
    p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.mouse-transition-v1.exe';p.write_bytes(out)
    report={'status':'candidate; native and gameplay verification pending','baseline_sha1':BASELINE,
            'candidate_sha1':hashlib.sha1(out).hexdigest(),'bytes':len(plan['blob']),
            'feature':'Preserve physically held mouse walk only across ordinary different-map transition'}
    p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
