"""Passive mouse motion must not steal native map movement input."""
import hashlib
import json
import flash_v4 as pe
import incense_link_v1 as combined

SITE=0xAEC16
EXPECTED=bytes.fromhex('c7 05 88 0c 58 00 02 00 00 00')
SIZE=512


def payload(base,origin):
    a=pe.Asm(origin)
    def op(code,address,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    a.raw('9c 60 83 7d bc 00');a.jump('0f 85','original')
    for rva in (0x131B80,0x13B8D8,0x16FFC4,0x16FFC0):
        op('83 3d',base+rva,b'\x00');a.jump('0f 85','original')
    op('f7 05',base+0x13B628,pe.u32(0x40));a.jump('0f 85','original')
    op('66 83 3d',base+0x1628E8,b'\xff');a.jump('0f 85','original')
    # Keep cursor coordinates current, but skip mode/virtual-joystick changes.
    a.raw('8b 45 c0');op('a3',base+0x1811CC)
    a.raw('8b 45 c4');op('a3',base+0x1811D0)
    a.raw('61 9d');a.jump('e9',base+0xAF0A3)
    a.label('original');a.raw('61 9d');op('c7 05',base+0x180C88,pe.u32(2));a.jump('e9',base+SITE+10)
    blob=a.finish()
    if len(blob)>SIZE:raise ValueError('Mouse helper too large')
    return {'blob':blob+bytes(SIZE-len(blob)),
            'patches':{SITE:pe.branch(0xe9,base+SITE,origin)+b'\x90'*5},'origin':origin}


def candidate(source):
    out,plans=combined.candidate(source);data=bytearray(out)
    off=pe.rva_offset(source,SITE)
    if source[off:off+10]!=EXPECTED:raise ValueError('Mouse motion mode store differs')
    section=pe.pe_info(out)[2][-1]
    if section[0]!=b'.palrule':raise ValueError('Expected rule section')
    offset=section[4]+0x600;origin=pe.IMAGE_BASE+section[2]+0x600
    plan=payload(pe.IMAGE_BASE,origin)
    if any(data[offset:offset+SIZE]):raise ValueError('Mouse helper storage occupied')
    data[offset:offset+SIZE]=plan['blob'];data[off:off+10]=plan['patches'][SITE]
    plans['mouse']=plan
    return bytes(data),plans


def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plans=candidate(source)
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.stage-20261030.exe';path.write_bytes(out)
    report={'candidate_sha1':hashlib.sha1(out).hexdigest(),'status':'candidate; native verification pending',
            'features':['cry and 37.5% glow','slow movement recovery','half chase radius; requested chase speed +1/3',
                        'native incense link','passive mouse motion does not steal map control'],
            'not_included':'single-click destination movement remains next development task'}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
