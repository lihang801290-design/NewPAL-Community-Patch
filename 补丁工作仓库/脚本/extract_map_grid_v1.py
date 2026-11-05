"""MSF3 map grid extraction v1: native decompress + cell-index structure render.

Read-only against the game. Uses the game's own A5490 decompressor inside the
offline Unicorn harness; no attachment to a running process, no file changes
outside 地图开发/.
"""
import sys, struct, hashlib, json
from native_damage_harness import Machine
from unicorn.x86_const import *
import flash_v4 as pe
from pathlib import Path
from PIL import Image

ROOT = Path(pe.ROOT)
OUT = ROOT / '补丁工作仓库' / '地图开发' / '原生碎片缓存'
SRC_STAGE = 0x850000
DST = 0x900000
LENP = 0x840000
SP = 0x9ef000
SCALE = 8

PALETTE = [
    (26, 26, 26), (214, 214, 214), (156, 116, 74), (78, 140, 82),
    (122, 94, 166), (182, 92, 92), (92, 112, 186), (192, 172, 92),
    (88, 182, 182), (172, 122, 172), (142, 152, 164), (214, 142, 92),
    (110, 172, 122), (152, 152, 92), (196, 196, 196), (104, 104, 148),
]


def parse_archive(path):
    data = path.read_bytes()
    index = struct.unpack_from('<I', data, 0)[0]
    count = (len(data) - index - 1) >> 4
    rows = {}
    for i in range(count):
        off, size, rid, _ = struct.unpack_from('<4I', data, index + i * 16)
        if off < 4 or size < 0x118 or off + size > index or off + size > len(data):
            raise AssertionError(f'{path.name} entry {i} out of range')
        head = data[off:off + 0x404]
        if head[:4] != b'MSF3':
            raise AssertionError(f'{path.name} entry {i} missing MSF3')
        w, h, depth, tag, layers = struct.unpack_from('<5H', head, 0x104)
        fo, fs = struct.unpack_from('<2I', head, 12)
        if not (0 < w <= 4096 and 0 < h <= 4096 and depth in (8, 16)):
            raise AssertionError(f'{path.name} entry {i} bad dims')
        if not (0 < fo < size and 0 < fs <= size - fo):
            raise AssertionError(f'{path.name} entry {i} bad flag block')
        rows[rid] = dict(archive=path.name, map_resource_id=rid, offset=off, size=size,
                         width=w, height=h, color_depth=depth, tag=tag, layers=layers,
                         flags_offset=fo, flags_size=fs, data=data)
    return rows


def build_machine():
    src = (ROOT / 'NewPAL_Release.exe').read_bytes()
    return Machine(src)


def read_grid(m, res):
    data = res['data']
    blk = data[res['offset']:res['offset'] + res['size']]
    packed = blk[res['flags_offset']:res['flags_offset'] + res['flags_size']]
    if len(packed) >= 0x10000:
        raise AssertionError('flag block too large for harness window')
    if res['width'] * res['height'] * 4 >= 0x100000:
        raise AssertionError('grid plane exceeds harness window')
    m.u.mem_write(SRC_STAGE, packed)
    m.w(LENP, 0)
    # A5490(dst, src, srcLen, outLenPtr, 0) -- argument order verified against
    # the 0x491ef0 thin wrapper and the existing research script.
    for i, v in enumerate((0x9ff000, SRC_STAGE, len(packed), DST, LENP)):
        m.w(SP + i * 4, v)
    m.u.reg_write(UC_X86_REG_ESP, SP)
    m.u.emu_start(0x4a5490, 0x9ff000, count=5000000)
    if m.u.reg_read(UC_X86_REG_EIP) != 0x9ff000:
        raise AssertionError('decompressor did not return')
    length = m.r(LENP)
    w, h = res['width'], res['height']
    if length != w * h * 4:
        raise AssertionError(f'unexpected plane size {length} for {w}x{h}')
    raw = bytes(m.u.mem_read(DST, length))
    return raw, struct.unpack_from('<%dI' % (w * h), raw)


def render(cells, w, h, out_path):
    img = Image.new('RGB', (w * SCALE, h * SCALE), (12, 12, 12))
    px = img.load()
    for y in range(h):
        base = y * w
        for x in range(w):
            v = cells[base + x]
            if v == 0:
                r, g, b = 12, 12, 12
            else:
                r, g, b = PALETTE[(v >> 12) & 0xF]
                hi = v >> 16
                if hi & 0x4000:
                    r, g, b = r * 3 // 5, g * 3 // 5, b * 3 // 5
                elif hi & 0x0800:
                    r, g, b = min(255, r * 5 // 4), min(255, g * 5 // 4), min(255, b * 5 // 4)
            x0, y0 = x * SCALE, y * SCALE
            for yy in range(y0, y0 + SCALE):
                for xx in range(x0, x0 + SCALE):
                    px[xx, yy] = (r, g, b)
    img.save(out_path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for name in ('huge.lmf', 'huge2.lmf'):
        res.update(parse_archive(ROOT / name))
    print('resources', len(res))
    m = build_machine()
    manifest = {}
    for n, (rid, r) in enumerate(sorted(res.items()), 1):
        try:
            raw, cells = read_grid(m, r)
        except Exception as e:
            manifest[rid] = dict(error=str(e))
            print(f'[{n}/{len(res)}] {rid} FAIL {e}')
            continue
        png = OUT / f'map_{rid:04d}_{r["width"]}x{r["height"]}.png'
        render(cells, r['width'], r['height'], png)
        distinct = len(set(cells))
        manifest[rid] = dict(map_resource_id=rid, archive=r['archive'], width=r['width'],
                             height=r['height'], layers=r['layers'], color_depth=r['color_depth'],
                             tag=r['tag'], distinct_cells=distinct,
                             grid_sha256=hashlib.sha256(raw).hexdigest(),
                             image=png.name)
        if n % 25 == 0:
            print(f'[{n}/{len(res)}] done')
    payload = dict(status='derived from native MSF3 flag plane; structure render only, not original artwork',
                   exe_sha1=hashlib.sha1((ROOT / 'NewPAL_Release.exe').read_bytes()).hexdigest(),
                   cell_encoding='NOT tile indices. This is the compressed plane the loader decompresses into a '
                                 'w*h*8 buffer (param_2[6]); research ties that buffer to 0053CCE8, shared by tile '
                                 'drawing and collision. Per-bit semantics not audited. Colours only separate '
                                 'distinct DWORD values; they do not denote tileset banks.',
                   loader_evidence='FUN_00491f20: header at entry+0x100 = w,h,depth,tag,layers; plane at entry+0x118 '
                                   'is an uncompressed w*h*4*layers+4 cell-id table (sequential 1,2,3...), not tiles; '
                                   'compressed flag plane offset/size come from entry+0x0C/+0x10.',
                   scale_px=SCALE, resources=manifest)
    (ROOT / '补丁工作仓库' / '地图开发' / '原生碎片解包记录.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    ok = sum(1 for v in manifest.values() if 'error' not in v)
    print('rendered', ok, 'of', len(manifest))


if __name__ == '__main__':
    main()
