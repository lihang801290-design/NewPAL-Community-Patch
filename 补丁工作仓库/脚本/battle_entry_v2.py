"""v1 entry batching plus removal of the matched wild-encounter cry pause.

Only a verified script template (play sound, stop encountered actor, wait 800,
then enter battle) on the global encounter object with a monster ID is changed.
Other dialogue waits, story Bosses, sounds and resource calls remain intact.
"""
import hashlib
import json
import struct
import flash_v4 as pe
import battle_entry_v1 as v1

WAIT_SITE=0x98795
EXPECTED={**v1.EXPECTED,WAIT_SITE:bytes.fromhex('89 0d 08 e9 57 00')}


def payload(base,origin):
    plan=v1.payload(base,origin);a=pe.Asm(origin+0x500)
    def absop(op,address,suffix=b''):a.raw(bytes.fromhex(op)+pe.u32(address)+suffix)
    a.raw(b'\x89\x0d'+pe.u32(base+0x17E908)) # restore original wait store
    a.raw('9c 60 81 f9 20 03 00 00');a.jump('0f 85','done')
    a.raw(b'\x81\x7d\x08'+pe.u32(base+0x1628C8));a.jump('0f 85','done')
    absop('0f b7 05',base+0x1628E8)
    a.raw('3d 00 10 00 00');a.jump('0f 82','done')
    a.raw('3d f0 ff 00 00');a.jump('0f 83','done')
    a.raw('8b 55 f0 85 d2');a.jump('0f 84','done')
    absop('a1',base+0x13B8A8);a.raw('85 c0');a.jump('0f 84','done')
    a.raw('83 c0 0a 3b d0');a.jump('0f 82','done')
    # Local_14 is the current script opcode pointer. Check surrounding template.
    for offset,value in [(0,0x43),(2,800),(4,0x309),(-2,0),(-4,0xfff1),(-6,0xa),(-10,0x3b)]:
        if offset==0:a.raw(b'\x66\x81\x3a'+struct.pack('<H',value))
        else:a.raw(b'\x66\x81\x7a'+bytes([offset&255])+struct.pack('<H',value))
        a.jump('0f 85','done')
    absop('c7 05',base+0x17E908,bytes(4)) # allow next frame; do not skip sound
    absop('ff 05',origin+0x3f4) # diagnostic hit count, independent of game state
    a.label('done');a.raw('61 9d');a.jump('e9',base+WAIT_SITE+6)
    plan['blob']+=bytes(0x500-len(plan['blob']))+a.finish()
    plan['symbols']['cry_wait']=origin+0x500
    plan['wait_hits']=origin+0x3f4
    plan['patches'][WAIT_SITE]=pe.branch(0xe9,base+WAIT_SITE,origin+0x500)+b'\x90'
    return plan


def candidate(source):
    out,old=v1.candidate(source)
    wait_off=pe.rva_offset(source,WAIT_SITE)
    if source[wait_off:wait_off+6]!=EXPECTED[WAIT_SITE]:raise ValueError('wait store differs')
    plan=payload(pe.IMAGE_BASE,old['origin'])
    header,opt,sections=pe.pe_info(out);name,vs,va,rs,rp=sections[-1]
    if name!=b'.palfast':raise ValueError('last section differs')
    fa=struct.unpack_from('<I',out,opt+36)[0]
    new_size=(len(plan['blob'])+fa-1)//fa*fa
    hdr=opt+struct.unpack_from('<H',out,header+20)[0]+(len(sections)-1)*40
    data=bytearray(out);data.extend(bytes(rp+new_size-len(data)))
    struct.pack_into('<I',data,hdr+8,len(plan['blob']));struct.pack_into('<I',data,hdr+16,new_size)
    struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',data,opt+4)[0]+new_size-rs)
    data[rp:rp+len(plan['blob'])]=plan['blob']
    data[wait_off:wait_off+6]=plan['patches'][WAIT_SITE]
    return bytes(data),plan


def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=candidate(source)
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.battle-entry-v2.exe'
    path.write_bytes(out);assert path.read_bytes()==out
    manifest={'baseline_sha1':v1.BASELINE,'candidate_sha1':hashlib.sha1(out).hexdigest(),
              'status':'candidate; runtime and gameplay validation pending',
              'features':['entry assignment batching','matched 800ms cry pause -> next frame'],
              'preserved':['sound playback','resource loading','other script waits','keyboard and previous fixes']}
    path.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
