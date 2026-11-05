"""Batch pure battle-entry initialization commands while preserving their order.

This version does not skip asset loading, readiness checks, music or animation
commands. It removes per-frame spacing between a short whitelist of assignments
observed in the live battle-entry trace. Requires the installed cb6c90fd build.
"""
from pathlib import Path
import hashlib
import json
import struct
import flash_v4 as pe

BASELINE='cb6c90fdef019e06c95cac2e6704d347294b0a6a'
EXPECTED={0xD07A0:bytes.fromhex('55 8b ec 6a ff'),
          0xCBAB0:bytes.fromhex('55 8b ec e8 18 f9 ff ff 5d c3')}
PURE=(0x7f302014,0x7f102010,0x7f20201b,0x7f402048,0x7f202013)


def payload(base,origin):
    a=pe.Asm(origin);remaining=origin+0x3f0;symbols={}
    def absop(op,address,suffix=b''):a.raw(bytes.fromhex(op)+pe.u32(address)+suffix)
    symbols['mark_entry']=a.pc
    absop('c7 05',remaining,pe.u32(64))
    a.raw(EXPECTED[0xD07A0]);a.jump('e9',base+0xD07A5)
    symbols['dispatch']=a.pc
    # EBP locals: previous node, last original EAX, per-frame call budget.
    a.raw('55 8b ec 83 ec 0c 53 56 57 c7 45 f4 20 00 00 00')
    a.label('loop')
    absop('a1',base+0x199368);a.raw('89 45 fc')
    a.jump('e8',base+0xCB3D0);a.raw('89 45 f8')
    absop('83 3d',remaining,b'\x00');a.jump('0f 84','done')
    absop('83 3d',base+0x131B80,b'\x01');a.jump('0f 85','disable')
    absop('83 3d',base+0x199814,b'\x00');a.jump('0f 85','disable')
    absop('8b 15',base+0x199368);a.raw('85 d2');a.jump('0f 84','done')
    a.raw('3b 55 fc');a.jump('0f 84','done') # stalled cursor: yield normally
    a.raw('8b 52 04 85 d2');a.jump('0f 84','done')
    a.raw('8b 02')
    for opcode in PURE:
        a.raw(b'\x3d'+pe.u32(opcode));a.jump('0f 84','again')
    a.jump('e9','done')
    a.label('again')
    absop('ff 0d',remaining);a.raw('ff 4d f4');a.jump('0f 85','loop')
    a.jump('e9','done')
    a.label('disable');absop('c7 05',remaining,bytes(4))
    a.label('done');a.raw('8b 45 f8 5f 5e 5b 8b e5 5d c3')
    code=a.finish()
    if len(code)>0x3f0:raise ValueError('payload exceeds code area')
    code+=bytes(0x400-len(code))
    patches={0xD07A0:pe.branch(0xe9,base+0xD07A0,symbols['mark_entry']),
             0xCBAB0:pe.branch(0xe9,base+0xCBAB0,symbols['dispatch'])+b'\x90'*5}
    return {'blob':code,'patches':patches,'symbols':symbols,'remaining':remaining,
            'base':base,'origin':origin}


def candidate(source):
    if hashlib.sha1(source).hexdigest()!=BASELINE:raise ValueError('unexpected installed baseline')
    for rva,wanted in EXPECTED.items():
        off=pe.rva_offset(source,rva)
        if source[off:off+len(wanted)]!=wanted:raise ValueError('site differs '+hex(rva))
    header,opt,sections=pe.pe_info(source);sa,fa=struct.unpack_from('<II',source,opt+32)
    align=lambda n,a:(n+a-1)//a*a
    rva=align(max(x[2]+max(x[1],x[3]) for x in sections),sa);raw=align(len(source),fa)
    plan=payload(pe.IMAGE_BASE,pe.IMAGE_BASE+rva)
    hdr=opt+struct.unpack_from('<H',source,header+20)[0]+len(sections)*40
    if hdr+40>min(x[4] for x in sections) or any(source[hdr:hdr+40]):raise ValueError('no section header room')
    out=bytearray(source);size=align(len(plan['blob']),fa);out.extend(bytes(raw+size-len(out)))
    struct.pack_into('<8sIIIIIIHHI',out,hdr,b'.palfast',len(plan['blob']),rva,size,raw,0,0,0,0,0xe0000020)
    struct.pack_into('<H',out,header+6,len(sections)+1)
    struct.pack_into('<I',out,opt+56,align(rva+len(plan['blob']),sa))
    struct.pack_into('<I',out,opt+4,struct.unpack_from('<I',source,opt+4)[0]+size)
    struct.pack_into('<I',out,opt+64,0)
    out[raw:raw+len(plan['blob'])]=plan['blob']
    for site,patch in plan['patches'].items():
        off=pe.rva_offset(source,site);out[off:off+len(patch)]=patch
    return bytes(out),plan


def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=candidate(source)
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.battle-entry-v1.exe'
    path.write_bytes(out);assert path.read_bytes()==out
    report={'baseline_sha1':BASELINE,'candidate_sha1':hashlib.sha1(out).hexdigest(),
            'status':'candidate only; offline and gameplay validation pending',
            'scope':'entry assignment batching only; assets/music/animations preserved',
            'entry_budget':64,'per_frame_limit':32,
            'symbols':{k:hex(v) for k,v in plan['symbols'].items()}}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
