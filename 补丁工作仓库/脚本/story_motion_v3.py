"""Correct the AI offset using real native actor fixtures, retaining v2 native tail."""
import argparse,hashlib,json
from pathlib import Path
import flash_v4 as pe
import monster_motion_v1 as prior

BASE='5d953f4b580295c0dd16c26d75a729ef13169731'
OUT=pe.ROOT/'补丁工作仓库/候选版本/story-motion-v3'
def candidate(source=None):
 source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
 assert hashlib.sha1(source).hexdigest()==BASE
 section=next(s for s in pe.pe_info(source)[2] if s[0]==b'.palmove');origin=0x400000+section[2]
 old=prior.payload(0x400000,origin,story_safe=True);new=prior.payload(0x400000,origin,story_safe=True,ai_offset=0x18)
 at=section[4];assert source[at:at+prior.SIZE]==old['blob']
 native=(pe.ROOT/'NewPAL_Release.exe.orig-ufa').read_bytes()
 lo=pe.rva_offset(source,0x7344c);nlo=pe.rva_offset(native,0x7344c)
 assert source[lo:lo+74]==native[nlo:nlo+74],'Native scripted speed must remain restored'
 out=bytearray(source);out[at:at+prior.SIZE]=new['blob'];assert len(out)==len(source)
 changes=[i for i,(a,b) in enumerate(zip(old['blob'],new['blob'])) if a!=b]
 assert len(changes)==4 and all(old['blob'][i]==0x1c and new['blob'][i]==0x18 for i in changes)
 return bytes(out),dict(origin=origin,state=new['state'],section_offset=at,changes=[dict(offset=at+i,old=0x1c,new=0x18) for i in changes],native_tail_retained=True,resources_changed=False)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);args=ap.parse_args()
 data,p=candidate(args.source.read_bytes() if args.source else None);OUT.mkdir(exist_ok=True)
 (OUT/'NewPAL_Release.exe').write_bytes(data);p.update(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest(),status='candidate; offline and gameplay verification pending')
 (OUT/'candidate.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(p,ensure_ascii=True))
if __name__=='__main__':main()
