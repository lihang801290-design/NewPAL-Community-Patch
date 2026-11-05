"""Keep each encounter cry for the original skipped-wait window, not full asset."""
import hashlib
import json
import flash_v4 as pe
import battle_entry_v3 as v3

BASELINE=v3.BASELINE
SIZE=v3.SIZE
MUSIC=v3.MUSIC
CLEANUP=v3.CLEANUP
EXTRA=v3.EXTRA
RESTORED_MS=800


def payload(base,origin):
    plan=v3.payload(base,origin);old=bytes(plan['blob']);blob=bytearray(old)
    a=pe.Asm(origin+0xc00);d=plan['audio'];d['deadline']=origin+0x1824;d['timed_end']=origin+0x1828
    symbols=plan['symbols']
    def op(code,addr,suffix=b''):a.raw(bytes.fromhex(code)+pe.u32(addr)+suffix)
    def start(name):symbols[name]=a.pc;a.label(name)
    start('capture_timed')
    op('c7 05',d['deadline'],bytes(4));a.jump('e9',symbols['capture'])
    start('cleanup_deadline')
    op('ff 05',d['protected'])
    op('83 3d',d['deadline'],b'\x00');a.jump('0f 85','deadline_done')
    op('ff 15',base+0x10D250);a.raw(b'\x05'+pe.u32(RESTORED_MS))
    op('a3',d['deadline'])
    a.label('deadline_done');a.raw('c3')
    start('tick_timed')
    a.raw('9c 60')
    op('83 3d',d['phase'],b'\x02');a.jump('0f 85','timed_done')
    op('83 3d',base+0x131B80,b'\x01');a.jump('0f 85','timed_done')
    op('83 3d',d['deadline'],b'\x00');a.jump('0f 84','timed_done')
    op('ff 15',base+0x10D250);op('2b 05',d['deadline']);a.jump('0f 88','timed_done')
    op('a1',d['slot']);a.raw('85 c0');a.jump('0f 84','timed_done')
    op('8b 0d',d['chunk']);a.raw('85 c9');a.jump('0f 84','timed_done')
    a.raw('39 48 04');a.jump('0f 85','timed_done')
    op('8b 15',base+0x180AE8);a.raw('85 d2');a.jump('0f 84','timed_done')
    op('8b 0d',d['channel']);a.raw('83 f9 10');a.jump('0f 83','timed_done')
    a.raw('3b 04 8a');a.jump('0f 85','timed_done')
    op('ff 05',d['timed_end']);a.raw('51');op('ff 15',base+0x10D290);a.raw('83 c4 04')
    # Normally ChannelFinished owns cleanup; handle a disabled callback safely.
    op('8b 35',d['slot']);op('a1',d['chunk']);a.raw('39 46 04');a.jump('0f 85','timed_done')
    a.raw('50');op('ff 15',base+0x10D2A0);a.raw('83 c4 04 c7 46 04 00 00 00 00')
    a.label('timed_done');a.raw('61 9d');a.jump('e9',symbols['tick'])
    extra=a.finish()
    if 0xc00+len(extra)>=0x1800:raise ValueError('timed code overlaps state')
    patches=[]
    def change(needle,new):
        where=old.find(needle)
        if where<0 or old.find(needle,where+1)>=0:raise ValueError('ambiguous code site')
        replacement=new(origin+where)
        if len(replacement)!=len(needle):raise ValueError('replacement length')
        blob[where:where+len(needle)]=replacement
        patches.append({'offset':where,'old':list(needle),'new':list(replacement)})
    # The original call's rel32 depends on its position, find it by target.
    capture_call=next(i for i in range(0x500,0x800) if old[i:i+1]==b'\xe8' and
        (origin+i+5+int.from_bytes(old[i+1:i+5],'little',signed=True))==symbols['capture'])
    change(old[capture_call:capture_call+6],lambda pc:pe.branch(0xe8,pc,symbols['capture_timed'])+b'\x90')
    change(b'\xff\x05'+pe.u32(d['protected']),lambda pc:pe.branch(0xe8,pc,symbols['cleanup_deadline'])+b'\x90')
    offset=symbols['dispatch_audio']-origin
    change(old[offset:offset+5],lambda pc:pe.branch(0xe8,pc,symbols['tick_timed']))
    blob[0xc00:0xc00+len(extra)]=extra
    plan['blob']=bytes(blob);plan['live_changes']=patches;plan['timed_code']=list(extra)
    return plan


def candidate(source):
    out,old=v3.candidate(source);plan=payload(pe.IMAGE_BASE,old['origin'])
    sections=pe.pe_info(out)[2];rp=sections[-1][4]
    data=bytearray(out);data[rp:rp+len(plan['blob'])]=plan['blob']
    return bytes(data),plan


def main():
    source=(pe.ROOT/'NewPAL_Release.exe').read_bytes();out,plan=candidate(source)
    path=pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.battle-entry-v4.exe';path.write_bytes(out)
    report={'candidate_sha1':hashlib.sha1(out).hexdigest(),'baseline_sha1':BASELINE,
            'status':'candidate; native/gameplay verification pending',
            'cry_window':'original cleanup time + removed 800ms; any matched sound ID'}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
