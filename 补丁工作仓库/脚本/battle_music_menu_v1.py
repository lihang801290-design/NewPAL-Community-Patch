"""Keep this battle's deferred music while a child menu is open."""
import argparse
import hashlib
from pathlib import Path

import flash_v4 as pe


BASE_SHA256 = "e7ec3c67c1f5d0d82b696e8cfd6d35ae0997dd9c3b69851c78e52b0a72c60fac"
MODE = 0x531B80
PREVIOUS_MODE = 0x599314
CAVE = 0x5E0D00

# Existing v5 phase-2 checks and their original taken branches.
GUARDS = (
    (0x5DF8E7, "0f85a5000000", "cleanup", 0x5DF992, 0x5DF8ED),
    (0x5DFAA6, "0f858f000000", "defer", 0x5DFB3B, 0x5DFB4F),
    (0x5DFC49, "0f859e000000", "expiry", 0x5DFCED, 0x5DFC4F),
)


def build(source):
    digest = hashlib.sha256(source).hexdigest()
    if digest != BASE_SHA256:
        raise ValueError(f"Expected the complete beta.3 base, got {digest}")

    # Mode 2 only belongs to this battle when the underlying mode is 1.
    # Keep the original cry deadline and cleanup handling, but defer the
    # music request itself until the battle screen is restored.
    asm = pe.Asm(CAVE)
    targets = {}
    for _, _, name, original_branch, battle_overlay_branch in GUARDS:
        targets[name] = asm.pc
        asm.raw(b"\x83\x3d" + pe.u32(MODE) + b"\x02")
        asm.jump("0f 85", original_branch)
        asm.raw(b"\x83\x3d" + pe.u32(PREVIOUS_MODE) + b"\x01")
        asm.jump("0f 85", original_branch)
        asm.jump("e9", battle_overlay_branch)

    payload = asm.finish()
    changes = [(CAVE, bytes(len(payload)), payload)]
    for address, old, name, _, _ in GUARDS:
        offset = targets[name] - (address + 6)
        changes.append((address, bytes.fromhex(old), b"\x0f\x85" + pe.u32(offset & 0xFFFFFFFF)))

    result = bytearray(source)
    for address, before, after in changes:
        offset = pe.rva_offset(source, address - pe.IMAGE_BASE)
        if source[offset:offset + len(before)] != before:
            raise ValueError(f"Unexpected bytes at {address:#x}")
        result[offset:offset + len(after)] = after
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build(args.source.read_bytes())
    with args.output.open("xb") as handle:
        handle.write(result)
    print(hashlib.sha256(result).hexdigest())


if __name__ == "__main__":
    main()
