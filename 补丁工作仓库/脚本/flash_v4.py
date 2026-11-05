"""Build a guarded glow candidate; never overwrite the installed game.

Runtime and offline verification use exactly the same address-aware payload.
Only the v9.1 SHA1 below is accepted. No automatic baseline restoration.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = "899ec146cd8019ec550eb4cb5e5433a8ca0a680a"
IMAGE_BASE = 0x400000
DURATION_MS = 10000
TIMER_SITES = (0x2D0E7, 0x70FA1, 0x779FC, 0x83CC8)
EXPECTED = {
    0x8BF47: bytes.fromhex("66 8b 0c 48 66 89 0a"),
    0x8BFD0: bytes.fromhex("66 8b 04 42 66 89 01"),
    0x7011E: bytes.fromhex("0d 80 00 00 00"),
    # Include the return and ten padding bytes; do not touch the next function.
    0x8C42D: bytes.fromhex("8b e5 5d c3") + b"\xcc" * 10,
}
EXPECTED.update({rva: bytes.fromhex("3d 98 3a 00 00") for rva in TIMER_SITES})


def u32(v):
    return struct.pack("<I", v & 0xffffffff)


def branch(op, origin, target):
    return bytes([op]) + u32(target - origin - 5)


class Asm:
    """Tiny two-pass byte builder; near conditional jumps are always six bytes."""
    def __init__(self, origin):
        self.origin, self.buf, self.labels, self.fixups = origin, bytearray(), {}, []

    @property
    def pc(self):
        return self.origin + len(self.buf)

    def raw(self, value):
        self.buf.extend(bytes.fromhex(value) if isinstance(value, str) else value)

    def label(self, name):
        if name in self.labels:
            raise ValueError("duplicate label: " + name)
        self.labels[name] = self.pc

    def jump(self, opcode, target):
        self.raw(bytes.fromhex(opcode))
        self.fixups.append((len(self.buf), target))
        self.raw(b"\x00" * 4)

    def finish(self):
        for pos, target in self.fixups:
            address = self.labels[target] if isinstance(target, str) else target
            self.buf[pos:pos+4] = u32(address - (self.origin + pos + 4))
        return bytes(self.buf)


def build_payload(base, origin):
    """base is the real module base; origin is any allocated 32-bit code region."""
    level = origin + 0x3f0
    wave = origin + 0x3f8
    a = Asm(origin)
    symbols = {}

    def start(name):
        symbols[name] = a.pc
        a.label(name)

    def absop(op, address, suffix=b""):
        a.raw(bytes.fromhex(op) + u32(address) + suffix)

    start("pixel")
    # Input/output CX only; every other register and EFLAGS must survive.
    a.raw("9c 50 53 52")                  # pushfd; push eax, ebx, edx
    absop("0f b6 05", level)
    a.raw("85 c0")
    a.jump("0f 84", "pixel_done")
    a.raw("8d 14 c5 00 00 00 00")        # edx = level * 8
    a.raw("0f b7 c1 c1 e8 0b 03 c2 83 f8 1f")
    a.jump("0f 8e", "red_ok")
    a.raw("b8 1f 00 00 00")
    a.label("red_ok")
    a.raw("c1 e0 0b 8b d8")
    a.raw("0f b7 c1 c1 e8 05 83 e0 3f d1 e2 03 c2 83 f8 3f")
    a.jump("0f 8e", "green_ok")
    a.raw("b8 3f 00 00 00")
    a.label("green_ok")
    a.raw("c1 e0 05 0b d8 d1 ea")
    a.raw("0f b7 c1 83 e0 1f 03 c2 83 f8 1f")
    a.jump("0f 8e", "blue_ok")
    a.raw("b8 1f 00 00 00")
    a.label("blue_ok")
    a.raw("0b d8 66 89 d9")
    a.label("pixel_done")
    a.raw("5a 5b 58 9d c3")

    start("pixel_site1")
    a.raw("66 8b 0c 48")
    a.jump("e8", "pixel")
    a.raw("66 89 0a")
    a.jump("e9", base + 0x8BF4E)

    start("pixel_site2")
    a.raw("66 8b 04 42 51 66 89 c1")
    a.jump("e8", "pixel")
    a.raw("66 89 c8 59 66 89 01")
    a.jump("e9", base + 0x8BFD7)

    start("draw")
    a.raw("55 8b ec 9c 60")              # standard frame, flags + all regs
    absop("c6 05", level, b"\x00")
    # 0x531B7C is a transition flag, NOT a sufficient battle guard.
    for rva in (0x131B7C, 0x199814):
        absop("83 3d", base + rva, b"\x00")
        a.jump("0f 85", "draw_original")
    absop("66 83 3d", base + 0x1628E8, b"\xff")
    a.jump("0f 85", "draw_original")
    absop("81 3d", base + 0x12C144, u32(0x80000000))
    a.jump("0f 84", "draw_original")
    a.jump("e8", base + 0x109BED)
    absop("2b 05", base + 0x12C144)
    a.raw(b"\x3d" + u32(DURATION_MS))
    a.jump("0f 83", "draw_original")    # unsigned elapsed >= duration
    a.raw("c1 e8 06 83 e0 07")
    absop("0f b6 80", wave)              # movzx eax, byte [eax + wave]
    absop("a2", level)
    a.label("draw_original")
    for offset in (0x18, 0x14, 0x10, 0x0c, 0x08):
        a.raw(bytes([0xff, 0x75, offset]))
    a.jump("e8", base + 0x8BA20)          # FIVE arguments, not six
    a.raw("83 c4 14")
    absop("c6 05", level, b"\x00")
    a.raw("61 9d 8b e5 5d c3")

    start("route")
    a.raw("51 52")                      # preserve ecx, edx; eax is output
    # Preserve original effect modes (0x10 etc), clipping flags and mirroring.
    a.raw("8b c8 81 e1 fc ff ff 3f 85 c9")
    a.jump("0f 85", "not_player")
    a.raw("8b 55 08 85 d2")
    a.jump("0f 84", "not_player")
    a.raw("0f b7 4a 20 85 c9")
    a.jump("0f 84", "not_player")
    a.raw("83 f9 64")
    a.jump("0f 83", "not_player")
    a.raw("8b 52 3c 81 fa 00 00 01 00")
    a.jump("0f 82", "not_player")
    a.raw("66 39 0a")
    a.jump("0f 85", "not_player")
    # The same low-numbered identities also include story NPCs/Bosses.
    # Match the game's own leader-or-follower eligibility (FUN_004c4ed0):
    # active leader = object_table[current_leader_index], follower = flag 0x80.
    a.raw("8b 55 08 f7 42 0c 80 00 00 00")
    a.jump("0f 85", "is_player")
    absop("8b 0d", base + 0x13A5FC)
    a.raw("81 f9 00 08 00 00")
    a.jump("0f 83", "not_player")
    a.raw("6b c9 48")
    absop("81 c1", base + 0x13E8C8)
    a.raw("3b d1")
    a.jump("0f 85", "not_player")
    a.label("is_player")
    a.raw("5a 59 0d 88 00 00 00")
    a.jump("e9", base + 0x70123)
    a.label("not_player")
    a.raw("5a 59 0d 80 00 00 00")
    a.jump("e9", base + 0x70123)

    blob = a.finish()
    if len(blob) > 0x3f0:
        raise ValueError("payload overlaps writable state")
    blob += bytes(0x3f0 - len(blob)) + bytes(8) + bytes([0, 1, 2, 3, 3, 2, 1, 0])
    patches = {
        0x8BF47: branch(0xe9, base + 0x8BF47, symbols["pixel_site1"]) + b"\x90\x90",
        0x8BFD0: branch(0xe9, base + 0x8BFD0, symbols["pixel_site2"]) + b"\x90\x90",
        0x7011E: branch(0xe9, base + 0x7011E, symbols["route"]),
        # Replace the epilogue in place; no jump into padding or extra call.
        0x8C42D: bytes.fromhex("c7 05") + u32(base + 0x175118)
                    + u32(symbols["draw"]) + bytes.fromhex("8b e5 5d c3"),
    }
    patches.update({rva: b"\x3d"+u32(DURATION_MS) for rva in TIMER_SITES})
    return {"blob": blob, "symbols": symbols, "level": level,
            "patches": patches, "base": base, "origin": origin}


def pe_info(data):
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    count = struct.unpack_from("<H", data, pe+6)[0]
    opt = pe+24
    sizeopt = struct.unpack_from("<H", data, pe+20)[0]
    sections = []
    for i in range(count):
        pos = opt+sizeopt+i*40
        name, vs, va, rs, rp = struct.unpack_from("<8sIIII", data, pos)
        sections.append((name.rstrip(b"\0"), vs, va, rs, rp))
    return pe, opt, sections


def rva_offset(data, rva):
    for name, vs, va, rs, rp in pe_info(data)[2]:
        if va <= rva < va+rs:
            return rp + rva-va
    raise ValueError("RVA is not file-backed: " + hex(rva))


def verify_baseline(data):
    if hashlib.sha1(data).hexdigest() != GOLDEN:
        raise ValueError("EXE is not the verified v9.1 baseline; refusing to restore or modify it")
    pe, opt, sections = pe_info(data)
    if struct.unpack_from("<I", data, opt+28)[0] != IMAGE_BASE:
        raise ValueError("unexpected image base")
    if struct.unpack_from("<H", data, opt+70)[0] & 0x40:
        raise ValueError("static absolute addresses require the existing non-ASLR baseline")
    for rva, expected in EXPECTED.items():
        off = rva_offset(data, rva)
        if data[off:off+len(expected)] != expected:
            raise ValueError("original bytes differ at " + hex(rva))


def build_candidate(data):
    verify_baseline(data)
    pe, opt, sections = pe_info(data)
    sa, fa = struct.unpack_from("<II", data, opt+32)
    align = lambda n, a: (n+a-1)//a*a
    rva = align(max(s[2]+max(s[1], s[3]) for s in sections), sa)
    raw = align(len(data), fa)
    plan = build_payload(IMAGE_BASE, IMAGE_BASE+rva)
    hdr = opt+struct.unpack_from("<H", data, pe+20)[0]+len(sections)*40
    if hdr+40 > min(s[4] for s in sections) or any(data[hdr:hdr+40]):
        raise ValueError("no free PE section header")
    out = bytearray(data)
    # This EXE has free header space; append a new section instead of borrowing
    # a code cave or the read-only data/padding after .text.
    size = align(len(plan["blob"]), fa)
    out.extend(bytes(raw+size-len(out)))
    struct.pack_into("<8sIIIIIIHHI", out, hdr, b".palglw\0", len(plan["blob"]), rva,
                     size, raw, 0, 0, 0, 0, 0xe0000020)
    struct.pack_into("<H", out, pe+6, len(sections)+1)
    struct.pack_into("<I", out, opt+56, align(rva+len(plan["blob"]), sa))
    struct.pack_into("<I", out, opt+4, struct.unpack_from("<I", out, opt+4)[0]+size)
    struct.pack_into("<I", out, opt+64, 0)  # no stale optional PE checksum
    out[raw:raw+len(plan["blob"])] = plan["blob"]
    for site, patch in plan["patches"].items():
        off = rva_offset(data, site)
        if len(patch) != len(EXPECTED[site]):
            raise ValueError("patch length mismatch at " + hex(site))
        out[off:off+len(patch)] = patch
    return bytes(out), plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=ROOT/"NewPAL_Release.exe")
    ap.add_argument("--output", type=Path, default=ROOT/"补丁工作仓库/候选版本/NewPAL_Release.flash-v4.exe")
    args = ap.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.resolve() == (ROOT/"NewPAL_Release.exe").resolve():
        raise ValueError("candidate output must not replace the installed game")
    baseline = args.source.read_bytes()
    candidate, plan = build_candidate(baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate)
    if args.output.read_bytes() != candidate:
        raise IOError("candidate readback differs")
    manifest = {"baseline_sha1": GOLDEN, "candidate_sha1": hashlib.sha1(candidate).hexdigest(),
                "status": "offline candidate; gameplay validation pending",
                "duration_ms": DURATION_MS,
                "origin": hex(plan["origin"]),
                "symbols": {k: hex(v) for k,v in plan["symbols"].items()},
                "sites": {hex(k): v.hex() for k,v in plan["patches"].items()}}
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
