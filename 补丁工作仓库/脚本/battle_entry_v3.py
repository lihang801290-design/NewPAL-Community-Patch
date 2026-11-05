"""Preserve the matched encounter cry and defer BGM without delaying scripts."""
import hashlib
import json
import struct
import flash_v4 as pe
import battle_entry_v2 as v2

BASELINE = '825ae475f87fb31f5eb25abe156a81844ea3c23b'
CLEANUP = 0xA7E8D
MUSIC = 0xE7820
EXTRA = {CLEANUP: bytes.fromhex('6a ff e8 1d 1d 06 00 83 c4 04'),
         MUSIC: bytes.fromhex('55 8b ec 83 7d 08 00')}
SIZE = 8192


def payload(base, origin):
    plan = v2.payload(base, origin)
    a = pe.Asm(origin + 0x800)
    data = {name: origin + 0x1800 + 4*i for i, name in enumerate(
        ('phase', 'slot', 'chunk', 'channel', 'pending', 'captured', 'protected', 'queued', 'played'))}
    filename = origin + 0x1900
    symbols = plan['symbols']
    def op(code, addr, suffix=b''):
        a.raw(bytes.fromhex(code) + pe.u32(addr) + suffix)
    def store(name, value):
        op('c7 05', data[name], pe.u32(value))
    def start(name):
        symbols[name] = a.pc
        a.label(name)
    def alive(fail):
        op('a1', data['slot']); a.raw('85 c0'); a.jump('0f 84', fail)
        op('8b 0d', data['chunk']); a.raw('85 c9'); a.jump('0f 84', fail)
        a.raw('39 48 04'); a.jump('0f 85', fail)
        op('8b 15', base + 0x180AE8); a.raw('85 d2'); a.jump('0f 84', fail)
        op('8b 0d', data['channel']); a.raw('83 f9 10'); a.jump('0f 83', fail)
        a.raw('3b 04 8a'); a.jump('0f 85', fail)

    # Called only inside v2's complete encounter-template match, EDX=script.
    start('capture')
    store('phase', 0); store('pending', 0)
    a.raw('0f b7 5a f8')
    op('8b 35', base + 0x180AE8); a.raw('85 f6'); a.jump('0f 84', 'capture_done')
    a.raw('31 ff')
    a.label('find_slot'); a.raw('8b 04 be 85 c0'); a.jump('0f 84', 'find_next')
    a.raw('39 18'); a.jump('0f 85', 'find_next')
    a.raw('8b 48 04 85 c9'); a.jump('0f 84', 'find_next')
    # Repeated/looping sounds are not eligible; normal one-shot finish owns free.
    a.raw('83 78 08 01'); a.jump('0f 87', 'find_next')
    op('a3', data['slot']); op('89 0d', data['chunk']); op('89 3d', data['channel'])
    store('phase', 1); op('ff 05', data['captured']); a.jump('e9', 'capture_done')
    a.label('find_next'); a.raw('47 83 ff 10'); a.jump('0f 82', 'find_slot')
    a.label('capture_done'); a.raw('c3')

    start('mark_audio')
    a.raw('9c 60')
    op('83 3d', data['phase'], b'\x01'); a.jump('0f 85', 'mark_clear')
    store('phase', 2); a.jump('e9', 'mark_done')
    a.label('mark_clear'); store('phase', 0); store('pending', 0)
    a.label('mark_done'); a.raw('61 9d'); a.jump('e9', symbols['mark_entry'])

    # Already inside the original cleanup's validated EBP frame.
    start('cleanup')
    a.raw('9c 60')
    a.raw(b'\x81\x7d\xf4' + pe.u32(base + 0x180448)); a.jump('0f 85', 'cleanup_fallback')
    op('a1', data['phase']); a.raw('83 f8 01'); a.jump('0f 84', 'cleanup_check')
    a.raw('83 f8 02'); a.jump('0f 85', 'cleanup_fallback')
    op('83 3d', base + 0x131B80, b'\x01'); a.jump('0f 85', 'cleanup_cancel')
    a.label('cleanup_check'); alive('cleanup_fallback')
    op('ff 05', data['protected'])
    a.raw('31 db')
    a.label('cleanup_loop'); op('3b 1d', data['channel']); a.jump('0f 84', 'cleanup_next')
    a.raw('53'); op('ff 15', base + 0x10D290); a.raw('83 c4 04')
    op('a1', base + 0x180AE8); a.raw('8b 34 98 85 f6'); a.jump('0f 84', 'cleanup_next')
    a.raw('8b 46 04 85 c0'); a.jump('0f 84', 'cleanup_next')
    a.raw('50'); op('ff 15', base + 0x10D2A0); a.raw('83 c4 04 c7 46 04 00 00 00 00')
    a.label('cleanup_next'); a.raw('43 83 fb 10'); a.jump('0f 82', 'cleanup_loop')
    a.raw('61 9d'); a.jump('e9', base + 0xA7EEB)
    a.label('cleanup_cancel'); store('phase', 0); store('pending', 0)
    a.label('cleanup_fallback'); a.raw('61 9d 6a ff')
    a.jump('e8', base + 0x109BB1); a.raw('83 c4 04'); a.jump('e9', base + 0xA7E97)

    start('music')
    a.raw('55 8b ec 53 56 57')
    op('83 3d', data['phase'], b'\x02'); a.jump('0f 85', 'music_fallback')
    op('83 3d', base + 0x131B80, b'\x01'); a.jump('0f 85', 'music_fallback')
    alive('music_fallback')
    a.raw('8b 75 08 85 f6'); a.jump('0f 84', 'music_fallback')
    a.raw('8b 76 0c 85 f6'); a.jump('0f 84', 'music_fallback')
    a.raw(b'\xbf' + pe.u32(filename) + b'\xb9' + pe.u32(259))
    a.label('copy'); a.raw('ac aa 84 c0'); a.jump('0f 84', 'music_queue')
    a.raw('49'); a.jump('0f 85', 'copy')
    # No truncated filenames: fall back to the original command on overflow.
    a.jump('e9', 'music_fallback')
    a.label('music_queue'); store('pending', 1); op('ff 05', data['queued'])
    op('c7 05', base + 0x19C2A0, bytes(4))
    a.raw('6a 01'); a.jump('e8', base + 0xCBA50); a.raw('83 c4 04 5f 5e 5b 5d c3')
    a.label('music_fallback'); a.raw('5f 5e 5b 5d')
    a.raw(EXTRA[MUSIC]); a.jump('e9', base + MUSIC + 7)

    start('tick')
    a.raw('9c 60')
    op('83 3d', data['phase'], b'\x02'); a.jump('0f 85', 'tick_done')
    op('83 3d', base + 0x131B80, b'\x01'); a.jump('0f 85', 'tick_cancel')
    alive('tick_finished'); a.jump('e9', 'tick_done')
    a.label('tick_finished'); store('phase', 0)
    op('83 3d', data['pending'], b'\x01'); a.jump('0f 85', 'tick_done')
    store('pending', 0); op('ff 05', data['played'])
    a.raw(b'\x6a\x01\x68' + pe.u32(filename) + b'\x68' + pe.u32(filename))
    a.jump('e8', base + 0xF3260); a.raw('83 c4 0c'); a.jump('e9', 'tick_done')
    a.label('tick_cancel'); store('phase', 0); store('pending', 0)
    a.label('tick_done'); a.raw('61 9d c3')
    start('dispatch_audio')
    a.jump('e8', symbols['tick']); a.jump('e9', symbols['dispatch'])
    extra = a.finish()
    if 0x800 + len(extra) > 0x1800:
        raise ValueError('Audio code overlaps state')
    blob = bytearray(plan['blob'])
    needle = bytes.fromhex('ff 05') + pe.u32(plan['wait_hits'])
    where = blob.find(needle, 0x500)
    if where < 0 or blob.find(needle, where+1) >= 0:
        raise ValueError('v2 capture site differs')
    blob[where:where+6] = pe.branch(0xe8, origin+where, symbols['capture']) + b'\x90'
    blob.extend(bytes(0x800-len(blob))); blob.extend(extra)
    blob.extend(bytes(SIZE-len(blob)))
    plan['blob'] = bytes(blob)
    plan['patches'].update({
        0xD07A0: pe.branch(0xe9, base+0xD07A0, symbols['mark_audio']),
        0xCBAB0: pe.branch(0xe9, base+0xCBAB0, symbols['dispatch_audio']) + b'\x90'*5,
        CLEANUP: pe.branch(0xe9, base+CLEANUP, symbols['cleanup']) + b'\x90'*5,
        MUSIC: pe.branch(0xe9, base+MUSIC, symbols['music']) + b'\x90'*2,
    })
    plan['audio'] = data; plan['filename'] = filename
    return plan


def candidate(source):
    if hashlib.sha1(source).hexdigest() != BASELINE:
        raise ValueError('Expected installed battle-entry-v2')
    header, opt, sections = pe.pe_info(source)
    name, vs, va, rs, rp = sections[-1]
    if name != b'.palfast':
        raise ValueError('Last section differs')
    old = v2.payload(pe.IMAGE_BASE, pe.IMAGE_BASE+va)
    for site, expected in {**old['patches'], **EXTRA}.items():
        off = pe.rva_offset(source, site)
        if source[off:off+len(expected)] != expected:
            raise ValueError('Site differs ' + hex(site))
    plan = payload(pe.IMAGE_BASE, pe.IMAGE_BASE+va)
    fa, sa = struct.unpack_from('<I', source, opt+36)[0], struct.unpack_from('<I', source, opt+32)[0]
    size = (len(plan['blob'])+fa-1)//fa*fa
    data = bytearray(source); data.extend(bytes(rp+size-len(data)))
    hdr = opt+struct.unpack_from('<H',source,header+20)[0]+(len(sections)-1)*40
    struct.pack_into('<I',data,hdr+8,len(plan['blob'])); struct.pack_into('<I',data,hdr+16,size)
    struct.pack_into('<I',data,opt+4,struct.unpack_from('<I',source,opt+4)[0]+size-rs)
    struct.pack_into('<I',data,opt+56,(va+len(plan['blob'])+sa-1)//sa*sa)
    data[rp:rp+size] = plan['blob'] + bytes(size-len(plan['blob']))
    for site, patch in plan['patches'].items():
        off = pe.rva_offset(source,site); data[off:off+len(patch)] = patch
    return bytes(data), plan


def main():
    source = (pe.ROOT/'NewPAL_Release.exe').read_bytes()
    output, plan = candidate(source)
    path = pe.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.battle-entry-v3.exe'
    path.write_bytes(output)
    report = {'baseline_sha1': BASELINE, 'candidate_sha1': hashlib.sha1(output).hexdigest(),
              'status': 'candidate only; offline and gameplay verification pending',
              'symbols': {k: hex(v) for k,v in plan['symbols'].items()}}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__': main()
