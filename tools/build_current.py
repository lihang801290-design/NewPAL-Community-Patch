"""Reconstruct current patch from the user's own exact Steam original.
This replays a frozen delta; it is NOT a full source recompilation.
Does not launch, modify, or install into a running game.
"""
import argparse,base64,gzip,hashlib,json,shutil
from pathlib import Path
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--original',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();root=Path(__file__).resolve().parents[1]
 manifest=json.loads((root/'baseline.json').read_text(encoding='utf-8'))
 raw=(root/'patch/latest.json.gz').read_bytes()
 if digest(raw)!=manifest['delta_sha256']:raise ValueError('Patch data hash mismatch')
 plan=json.loads(gzip.decompress(raw));source=a.original.read_bytes()
 if digest(source)!=plan['original_sha256'] or len(source)!=plan['original_size']:
  raise ValueError('Unsupported original EXE. Use the exact supported Steam original; never force apply.')
 result=bytearray(source);end=0
 for s in plan['spans']:
  at=s['offset'];old=base64.b64decode(s['old'],validate=True);new=base64.b64decode(s['new'],validate=True)
  if at<end or not old or len(old)!=len(new) or at+len(old)>len(source) or source[at:at+len(old)]!=old:
   raise ValueError('Invalid patch span')
  result[at:at+len(old)]=new;end=at+len(old)
 result.extend(base64.b64decode(plan['tail'],validate=True))
 if len(result)!=plan['target_size'] or digest(result)!=plan['target_sha256']:raise ValueError('Target mismatch')
 if a.output.resolve()==a.original.parent.resolve():raise ValueError('Use a separate output directory; this is not an installer')
 if a.output.exists() and any(a.output.iterdir()):raise ValueError('Output directory must be empty')
 for entry in manifest['resources']:
  path=root/entry['path']
  if digest(path.read_bytes())!=entry['sha256']:raise ValueError('Resource mismatch: '+entry['path'])
 a.output.mkdir(parents=True,exist_ok=True)
 (a.output/'NewPAL_Release.exe').write_bytes(result)
 for entry in manifest['resources']:
  src=root/entry['path'];dst=a.output/entry['path'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 print('Exact patch reconstructed. Follow installation instructions; no game files were overwritten.')
if __name__=='__main__':main()
