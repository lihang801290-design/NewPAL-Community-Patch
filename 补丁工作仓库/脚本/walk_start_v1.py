"""Fix first full-deflection joystick event being left in walk mode.

Keep the original +/-8000 deadzone, +/-30000 run thresholds and all keyboard
paths. Four JNE instructions gating on the freshly-set edge bit become NOPs.
"""
import hashlib
import json
from pathlib import Path
import flash_v4 as glow

SITES = (0xA89AC, 0xA8A57, 0xA8BEA, 0xA8C95)
EXPECTED = bytes.fromhex('75 29')
PATCH = b'\x90\x90'


def apply(data):
    out=bytearray(data)
    for site in SITES:
        off=glow.rva_offset(data,site)
        if data[off:off+2]!=EXPECTED:
            raise ValueError('unexpected joystick guard at '+hex(site))
        out[off:off+2]=PATCH
    return bytes(out)


def main():
    source=(glow.ROOT/'NewPAL_Release.exe').read_bytes()
    glow.verify_baseline(source)
    flashed,_=glow.build_candidate(source)
    candidate=apply(flashed)
    output=glow.ROOT/'补丁工作仓库/候选版本/NewPAL_Release.flash-v4-walk-v1.exe'
    output.write_bytes(candidate)
    assert output.read_bytes()==candidate
    manifest={'baseline_sha1':glow.GOLDEN,'candidate_sha1':hashlib.sha1(candidate).hexdigest(),
              'features':['10s encounter protection','party-only glow','immediate joystick full-deflection run'],
              'keyboard_rules':'WASD keeps R toggle; cursor keys unchanged',
              'status':'offline candidate; joystick gameplay validation pending',
              'joystick_sites':{hex(s):PATCH.hex() for s in SITES}}
    output.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
