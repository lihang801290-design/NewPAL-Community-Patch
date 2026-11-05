"""Suppress post-battle protection/glow while native ten-mile incense is active."""
import hashlib
import json
import struct
import flash_v4 as pe
import monster_motion_v1 as motion

SIZE=4096


def glow_info(base,origin):
    p=pe.build_payload(base,origin);draw=p['symbols']['draw'];offset=draw-origin+19
    if p['blob'][offset:offset+2]!=b'\x0f\x85':raise ValueError('Glow exit branch differs')
    target=origin+offset+6+int.from_bytes(p['blob'][offset+2:offset+6],'little',signed=True)
    return {'draw':draw,'original':target,'level':p['level']}


def payload(base,origin,glow_origin):
    a=pe.Asm(origin);symbols={};g=glow_info(base,glow_origin);hits=origin+0xf00
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    def start(name):symbols[name]=a.pc;a.label(name)
    start('active')
    a.raw('31 c0');op('81 3d',base+0x16F338,pe.u32(4996));a.jump('0f 85','inactive')
    op('f6 05',base+0x16F7AA,b'\x01');a.jump('0f 84','inactive')
    op('83 3d',base+0x16F334,b'\x00');a.jump('0f 8c','inactive')
    a.raw('b8 01 00 00 00')
    a.label('inactive');a.raw('c3')
    patches={};expected={}
    for index,site in enumerate(pe.TIMER_SITES):
        start('gate_'+str(index));a.raw('50');a.jump('e8',symbols['active']);a.raw('85 c0')
        a.jump('0f 84','normal_'+str(index))
        op('ff 05',hits+4*index)
        a.raw(b'\xb8'+pe.u32(10000)+b'\x3d'+pe.u32(10000)+b'\x58')
        a.jump('e9',base+site+5)
        a.label('normal_'+str(index));a.raw(b'\x58\x3d'+pe.u32(10000));a.jump('e9',base+site+5)
        patches[site]=pe.branch(0xe9,base+site,symbols['gate_'+str(index)])
        expected[site]=b'\x3d'+pe.u32(10000)
    start('draw')
    # Reproduce the existing glow callback's standard frame and saved registers.
    a.raw('55 8b ec 9c 60');a.jump('e8',symbols['active']);a.raw('85 c0');a.jump('0f 84','draw_normal')
    op('ff 05',hits+16);op('c6 05',g['level'],b'\x00');a.jump('e9',g['original'])
    a.label('draw_normal');a.jump('e9',g['draw']+5)
    patches[g['draw']-base]=pe.branch(0xe9,g['draw'],symbols['draw'])
    expected[g['draw']-base]=bytes.fromhex('55 8b ec 9c 60')
    blob=a.finish()
    if len(blob)>=0xf00:raise ValueError('Rules code overlaps diagnostic counters')
    blob+=bytes(SIZE-len(blob))
    return {'blob':blob,'patches':patches,'expected':expected,'symbols':symbols,'hits':hits,
            'origin':origin,'glow':g}


def candidate(source):
    out,plans=motion.candidate(source);data=bytearray(out)
    glow=next(s for s in pe.pe_info(out)[2] if s[0]==b'.palglw')
    section=pe.pe_info(out)[2][-1]
    if section[0]!=b'.palmove':raise ValueError('Motion section not last')
    # The rule payload gets its own section so its 4096 bytes never touch state.
    header,opt,sections=pe.pe_info(out);sa,fa=struct.unpack_from('<II',out,opt+32)
    align=lambda n,a:(n+a-1)//a*a
    va=align(max(s[2]+max(s[1],s[3]) for s in sections),sa);rp=align(len(out),fa)
    plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+va,pe.IMAGE_BASE+glow[2])
    hdr=opt+struct.unpack_from('<H',out,header+20)[0]+len(sections)*40
    if hdr+40>min(s[4] for s in sections) or any(out[hdr:hdr+40]):raise ValueError('No section room')
    data.extend(bytes(rp+SIZE-len(data)))
    struct.pack_into('<8sIIIIIIHHI',data,hdr,b'.palrule',SIZE,va,SIZE,rp,0,0,0,0,0xe0000020)
    struct.pack_into('<H',data,header+6,len(sections)+1)
    struct.pack_into('<I',data,opt+56,align(va+SIZE,sa))
    struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',data,opt+4)[0]+SIZE)
    data[rp:rp+SIZE]=plan['blob']
    for site,patch in plan['patches'].items():
        off=pe.rva_offset(out,site)
        if out[off:off+len(patch)]!=plan['expected'][site]:raise ValueError('Protection site differs '+hex(site))
        data[off:off+len(patch)]=patch
    plans['rules']=plan
    return bytes(data),plans


def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plans=candidate(source)
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.audio-chase-incense-glow.exe';path.write_bytes(out)
    report={'candidate_sha1':hashlib.sha1(out).hexdigest(),'status':'candidate only; native/gameplay verification pending',
        'features':['measured cry duration','fractional slow movement with recovery','half chase radius and reduced chase acceleration',
                    '37.5 percent glow','native incense disables post-battle protection and glow']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
