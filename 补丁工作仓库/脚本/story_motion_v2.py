"""Remove legacy global /3 tail; keep bounded ordinary-AI slowdown only."""
import argparse,hashlib,json
from pathlib import Path
import flash_v4 as pe
import monster_motion_v1 as prior

BASE='361ce26cc62f8599c39db98d9131c244dfb80b46'
OUT=pe.ROOT/'补丁工作仓库/候选版本/story-motion-v2'
NATIVE_SHA='6052097e0cf03216f41efffbae74844badb73493'
TAIL_START=0x7344c;TAIL_END=0x73496

def candidate(source=None):
 source=(pe.ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
 assert hashlib.sha1(source).hexdigest()==BASE,'Expected exact installed lotus validation baseline'
 native=(pe.ROOT/'NewPAL_Release.exe.orig-ufa').read_bytes();assert hashlib.sha1(native).hexdigest()==NATIVE_SHA
 section=next(s for s in pe.pe_info(source)[2] if s[0]==b'.palmove');origin=0x400000+section[2]
 old=prior.payload(0x400000,origin);new=prior.payload(0x400000,origin,story_safe=True)
 assert source[section[4]:section[4]+prior.SIZE]==old['blob'],'Installed motion helper differs'
 at=pe.rva_offset(source,prior.SITE);assert source[at:at+7]==old['patches'][prior.SITE]
 at=pe.rva_offset(source,TAIL_START);native_at=pe.rva_offset(native,TAIL_START);tail=native[native_at:native_at+TAIL_END-TAIL_START];before=source[at:at+len(tail)]
 assert before.startswith(bytes.fromhex('89 d0 ba 56 55 55 55 f7 ea')) and before!=tail,'Expected legacy unconditional /3 tail'
 out=bytearray(source);out[section[4]:section[4]+prior.SIZE]=new['blob'];out[at:at+len(tail)]=tail
 assert len(out)==len(source)
 report=dict(origin=origin,state=new['state'],tail_rva=TAIL_START,tail_bytes=len(tail),motion_section_offset=section[4],motion_section_size=prior.SIZE,changes=[dict(offset=section[4],old_sha256=hashlib.sha256(old['blob']).hexdigest(),new_sha256=hashlib.sha256(new['blob']).hexdigest(),size=prior.SIZE),dict(offset=at,old_hex=before.hex(),new_hex=tail.hex(),size=len(tail))],native_tail_restored=True,legacy_fallback_no_longer_scaled=True)
 return bytes(out),report

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path);args=ap.parse_args();data,p=candidate(args.source.read_bytes() if args.source else None)
 OUT.mkdir(exist_ok=True);(OUT/'NewPAL_Release.exe').write_bytes(data);p.update(baseline_sha1=BASE,candidate_sha1=hashlib.sha1(data).hexdigest(),status='candidate; offline and gameplay verification pending',resources_changed=False)
 (OUT/'candidate.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(candidate_sha1=p['candidate_sha1'],native_tail_bytes=p['tail_bytes'],resources_changed=False),ensure_ascii=True))

if __name__=='__main__':main()
