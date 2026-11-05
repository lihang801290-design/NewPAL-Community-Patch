"""Replace one verified corrupt original snake NW image by a clean phase frame."""
import hashlib,json
import flash_v4 as pe
import window_mouse_v1 as window

BASELINE='abeab444bc503649626dc527ef99bafce32fe238'
WINDOW='c5c404168d78f3a86790f11a89e571e9f54d0d8b'
SIZE=256
EXPECTED={0xfe520:bytes.fromhex('55 8b ec 0f b7 45 0c'),0xfe1a0:bytes.fromhex('55 8b ec c7 05 dc d1 59 00 00 00 00 00')}

def payload(base,origin):
    a=pe.Asm(origin);patches={}
    for site in EXPECTED:
        here=a.pc;patches[site]=pe.branch(0xe9,base+site,here)+b'\x90'*(len(EXPECTED[site])-5)
        label='original_'+str(site)
        a.raw('55 8b ec 9c 66 81 7d 08 e1 03');a.jump('0f 85',label)
        a.raw('66 83 7d 0c 01');a.jump('0f 85',label)
        a.raw('c7 45 0c 03 00 00 00');a.label(label);a.raw('9d')
        if site==0xfe520:a.raw('0f b7 45 0c')
        else:a.raw(bytes.fromhex('c7 05')+pe.u32(base+0x19d1dc)+bytes(4))
        a.jump('e9',base+site+len(EXPECTED[site]))
    blob=a.finish();assert len(blob)<=SIZE
    return {'blob':blob+bytes(SIZE-len(blob)),'patches':patches,'origin':origin}

def candidate(source):
    sha=hashlib.sha1(source).hexdigest()
    if sha==BASELINE:out,_=window.candidate(source)
    elif sha==WINDOW:out=source
    else:raise ValueError('Expected abeab444 or accepted window version')
    section=next(s for s in pe.pe_info(out)[2] if s[0]==b'.palwin');origin=pe.IMAGE_BASE+section[2]+0xf00;off=section[4]+0xf00
    if any(out[off:off+SIZE]):raise ValueError('Snake helper area occupied')
    plan=payload(pe.IMAGE_BASE,origin);data=bytearray(out);data[off:off+SIZE]=plan['blob']
    for site,value in plan['patches'].items():
        off=pe.rva_offset(source,site)
        if source[off:off+len(EXPECTED[site])]!=EXPECTED[site]:raise ValueError('Image entry differs')
        data[off:off+len(value)]=value
    return bytes(data),plan

if __name__=='__main__':
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=candidate(source)
    p=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.window-snake-v1.exe';p.write_bytes(out)
    report={'status':'candidate; gameplay pending','target_sha1':hashlib.sha1(out).hexdigest(),
            'mapping':{'bank':993,'bad_frame':1,'replacement_frame':3},'scope':'only original snake NW corrupt image; same timing; original files unchanged'}
    p.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
