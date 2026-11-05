"""Use measured original cry window from actual playback, with mixer expiration."""
import hashlib
import json
import flash_v4 as pe
import battle_entry_v4 as v4

BASELINE=v4.BASELINE
SIZE=v4.SIZE
EXTRA={**v4.EXTRA,0xA7988:bytes.fromhex('89 45 f4 83 7d f4 ff')}
MUSIC=v4.MUSIC
CLEANUP=v4.CLEANUP
ORIGINAL_REFERENCE_MS=922  # Actual original game: 1793318851396 -> 1793318852318.


def payload(base,origin):
    plan=v4.payload(base,origin);old=bytes(plan['blob']);blob=bytearray(old)
    a=pe.Asm(origin+0xe00);d=plan['audio'];s=plan['symbols']
    d.update(expiry_fn=origin+0x182c,expiry_armed=origin+0x1830,expiry_active=origin+0x1834)
    table=origin+0x1b00;dll=origin+0x1c00;function=origin+0x1c20
    def op(code,addr,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(addr)+suffix)
    def start(name):s[name]=a.pc;a.label(name)
    start('record_playback')
    a.raw('89 45 f4 9c 60 83 f8 10');a.jump('0f 83','record_done')
    a.raw(b'\x8d\x34\xc5'+pe.u32(table))
    a.raw('8b 55 f0 89 16');op('ff 15',base+0x10D250);a.raw('89 46 04')
    a.label('record_done');a.raw('61 9d 83 7d f4 ff');a.jump('e9',base+0xA798F)
    start('capture_expiry')
    op('c7 05',d['expiry_active'],bytes(4));op('c7 05',d['deadline'],bytes(4))
    a.jump('e8',s['capture'])
    op('83 3d',d['phase'],b'\x01');a.jump('0f 85','expiry_done')
    # Two nearby monsters can start the same cry before the scene is switched.
    # Preserve the latest actual playback, not the first slot with that sound ID.
    op('ff 15',base+0x10D250);a.raw('50 6a ff')
    op('8b 35',base+0x180AE8);a.raw('31 ff')
    a.label('latest_loop');a.raw('8b 04 be 85 c0');a.jump('0f 84','latest_next')
    a.raw('39 18');a.jump('0f 85','latest_next')
    a.raw('8b 48 04 85 c9');a.jump('0f 84','latest_next')
    a.raw('83 78 08 01');a.jump('0f 87','latest_next')
    a.raw(b'\x8d\x14\xfd'+pe.u32(table));a.raw('39 0a');a.jump('0f 85','latest_next')
    a.raw('8b 52 04 8b 4c 24 04 29 d1 3b 0c 24');a.jump('0f 83','latest_next')
    a.raw('89 0c 24');op('a3',d['slot']);a.raw('8b 48 04');op('89 0d',d['chunk']);op('89 3d',d['channel'])
    a.label('latest_next');a.raw('47 83 ff 10');a.jump('0f 82','latest_loop')
    a.raw('83 c4 08')
    op('a1',d['channel']);a.raw(b'\x8d\x34\xc5'+pe.u32(table))
    op('8b 0d',d['chunk']);a.raw('39 0e');a.jump('0f 85','expiry_done')
    op('ff 15',base+0x10D250);a.raw('2b 46 04')
    a.raw(b'\xbb'+pe.u32(ORIGINAL_REFERENCE_MS)+b'\x29\xc3')
    a.raw('85 db');a.jump('0f 8f','expiry_resolve');a.raw('bb 01 00 00 00')
    a.label('expiry_resolve');op('83 3d',d['expiry_fn'],b'\x00');a.jump('0f 85','expiry_call')
    # These SDL loader functions already exist in the game's import table.
    a.raw(b'\x68'+pe.u32(dll));op('ff 15',base+0x10D238);a.raw('83 c4 04 85 c0')
    a.jump('0f 84','expiry_failed')
    a.raw(b'\x68'+pe.u32(function)+b'\x50');op('ff 15',base+0x10D23C);a.raw('83 c4 08 85 c0')
    a.jump('0f 84','expiry_failed');op('a3',d['expiry_fn']);a.jump('e9','expiry_call')
    a.label('expiry_failed');op('c7 05',d['expiry_fn'],pe.u32(1));a.jump('e9','expiry_done')
    a.label('expiry_call');op('83 3d',d['expiry_fn'],b'\x01');a.jump('0f 84','expiry_done')
    a.raw('53');op('ff 35',d['channel']);op('ff 15',d['expiry_fn']);a.raw('83 c4 08 85 c0')
    a.jump('0f 8e','expiry_done')
    op('c7 05',d['expiry_active'],pe.u32(1));op('ff 05',d['expiry_armed'])
    a.label('expiry_done');a.raw('c3')
    start('cleanup_expiry')
    op('83 3d',d['expiry_active'],b'\x01');a.jump('0f 85','cleanup_old')
    op('ff 05',d['protected']);a.raw('c3')
    a.label('cleanup_old');a.jump('e9',s['cleanup_deadline'])
    extra=a.finish()
    if 0xe00+len(extra)>=0x1800:raise ValueError('Expiry code overlaps state')
    def retarget(target,newtarget):
        hits=[i for i in range(0x500,0xc00) if old[i:i+1]==b'\xe8' and
              origin+i+5+int.from_bytes(old[i+1:i+5],'little',signed=True)==target]
        if len(hits)!=1:raise ValueError('Ambiguous call retarget '+hex(target))
        i=hits[0];blob[i:i+5]=pe.branch(0xe8,origin+i,newtarget)
    retarget(s['capture_timed'],s['capture_expiry'])
    retarget(s['cleanup_deadline'],s['cleanup_expiry'])
    blob[0xe00:0xe00+len(extra)]=extra
    blob[0x1c00:0x1c00+15]=b'SDL2_mixer.dll\0'
    blob[0x1c20:0x1c20+18]=b'Mix_ExpireChannel\0'
    if len(blob)!=SIZE:raise ValueError('Unexpected payload size')
    plan['blob']=bytes(blob)
    plan['patches'][0xA7988]=pe.branch(0xe9,base+0xA7988,s['record_playback'])+b'\x90'*2
    plan['playback_table']=table
    return plan


def candidate(source):
    out,old=v4.candidate(source);plan=payload(pe.IMAGE_BASE,old['origin']);data=bytearray(out)
    off=pe.rva_offset(source,0xA7988)
    if source[off:off+7]!=EXTRA[0xA7988]:raise ValueError('Playback record site differs')
    rp=pe.pe_info(out)[2][-1][4];data[rp:rp+SIZE]=plan['blob']
    data[off:off+7]=plan['patches'][0xA7988]
    return bytes(data),plan


def main():
    out,plan=candidate((pe.ROOT/'NewPAL_Release.exe').read_bytes())
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.battle-entry-v5.exe';path.write_bytes(out)
    report={'candidate_sha1':hashlib.sha1(out).hexdigest(),'status':'candidate; native/gameplay checks pending',
            'reference_ms':ORIGINAL_REFERENCE_MS,'scope':'any matched encounter sound; mixer-timed original window'}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
