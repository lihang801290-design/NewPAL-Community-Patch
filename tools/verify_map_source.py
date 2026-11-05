"""Read-only regeneration check of current cave and lotus x86 code from source.

This does not install, execute game code or certify gameplay correctness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    baseline=json.loads((root/'baseline.json').read_text(encoding='utf-8'))
    source=args.exe.read_bytes()
    if hashlib.sha256(source).hexdigest()!=baseline['target_sha256']:
        raise ValueError('Expected exact current baseline EXE, not a modified or original EXE')
    work=root/'补丁工作仓库'
    sys.path.insert(0,str(work/'脚本'))
    import luocha_return_runtime_v1 as cave
    import lotus_runtime_v2 as lotus
    import lotus_runtime_v1 as lotus1
    def load(name):return json.loads((work/'候选版本/map-nameplates-v1'/name).read_text(encoding='utf-8'))
    plan=load('candidate.json');atlas=load('cave-atlas.json');plates=load('nameplates.json')
    out=work/'候选版本/map-nameplates-v1'
    cave.OUT=out
    c=cave.payload(plan['cave']['origin'],source,atlas['rows'],atlas['links'],
        migration=plan['migration'],nameplates=plates['cave'],dream_nameplates=plates['dream'])
    la=load('lotus-atlas.json')
    profile=dict(count=lotus.COUNT,size=lotus.SIZE,magic=lotus.MAGIC,
        namespace='np_lotus1_%d.dat',alpha_offset=lotus1.ALPHA_OFFSET,
        out=work/'候选版本/map-art-runtime-v6/lotus-data',previous=c,
        exclusive_scene=True,sample_during_events=True)
    l=cave.payload(plan['lotus']['origin'],source,la['rows'],la['links'],profile)
    checks=[]
    for name,item in [('cave',c),('lotus',l)]:
        at=cave.pe.rva_offset(source,item['origin']-cave.pe.IMAGE_BASE)
        size=item['code_size']
        equal=source[at:at+size]==item['blob'][:size]
        checks.append({'module':name,'code_bytes':size,'identical':equal})
    print(json.dumps({'checks':checks,'scope':'source regeneration; no emulation or gameplay'},indent=2))
    if not all(x['identical'] for x in checks):raise SystemExit(1)

if __name__=='__main__':main()
