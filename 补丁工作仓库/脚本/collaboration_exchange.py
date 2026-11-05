"""Portable, standard-library-only NewPAL collaboration exchange tool."""
import argparse,base64,hashlib,json,struct,zipfile
from pathlib import Path,PurePosixPath

def sha(data):return hashlib.sha256(data).hexdigest()
def b64(data):return base64.b64encode(data).decode('ascii')
def unb64(data):return base64.b64decode(data,validate=True)
def pe_info(data):
 if data[:2]!=b'MZ':raise ValueError('Not PE')
 h=struct.unpack_from('<I',data,0x3c)[0]
 if data[h:h+4]!=b'PE\0\0' or struct.unpack_from('<H',data,h+4)[0]!=0x14c:raise ValueError('Expected x86 PE')
 count=struct.unpack_from('<H',data,h+6)[0];opt=h+24;table=opt+struct.unpack_from('<H',data,h+20)[0]
 result=[]
 for i in range(count):
  s=table+i*40;name=data[s:s+8].rstrip(b'\0').decode('ascii','replace');vs,rva,size,offset=struct.unpack_from('<IIII',data,s+8)
  if offset+size>len(data):raise ValueError('Section exceeds file')
  result.append({'name':name,'rva':hex(rva),'virtual_size':vs,'raw_offset':offset,'raw_size':size})
 return {'image_base':hex(struct.unpack_from('<I',data,opt+28)[0]),'sections':result}

def make_patch(base,candidate,allow_unchanged=False):
 pe_info(base);pe_info(candidate)
 if len(candidate)<len(base):raise ValueError('Shrinking EXE is not supported by this exchange format')
 spans=[];i=0
 while i<len(base):
  if base[i]==candidate[i]:i+=1;continue
  start=i
  while i<len(base) and base[i]!=candidate[i]:i+=1
  spans.append({'offset':start,'old':b64(base[start:i]),'new':b64(candidate[start:i])})
 if not spans and len(base)==len(candidate) and not allow_unchanged:raise ValueError('Candidate has no changes')
 return {'format':'newpal-return-v1','base_sha256':sha(base),'base_sha1':hashlib.sha1(base).hexdigest(),
  'target_sha256':sha(candidate),'target_sha1':hashlib.sha1(candidate).hexdigest(),
  'base_size':len(base),'target_size':len(candidate),'spans':spans,'tail':b64(candidate[len(base):])}

def reconstruct(base,manifest):
 if manifest.get('format')!='newpal-return-v1' or sha(base)!=manifest['base_sha256'] or len(base)!=manifest['base_size']:
  raise ValueError('BASE MISMATCH: review/rebase source; never force-apply or binary-merge')
 result=bytearray(base);end=0
 for s in manifest['spans']:
  offset=s['offset'];old=unb64(s['old']);new=unb64(s['new'])
  if not isinstance(offset,int) or offset<end or not old or len(old)!=len(new) or offset+len(old)>len(base):raise ValueError('Invalid/overlapping span')
  if base[offset:offset+len(old)]!=old:raise ValueError('Old bytes differ')
  result[offset:offset+len(old)]=new;end=offset+len(old)
 result.extend(unb64(manifest['tail']))
 if len(result)!=manifest['target_size'] or sha(result)!=manifest['target_sha256']:raise ValueError('Target hash/size differs')
 pe_info(result);return bytes(result)

def safe_name(name):
 p=PurePosixPath(name.replace('\\','/'))
 if p.is_absolute() or '..' in p.parts or ':' in name:raise ValueError('Unsafe attachment path')
 return str(p)

def resource_state(root,entries):
 result=[]
 for item in entries:
  name=safe_name(item['path']);p=(root/name).resolve();p.relative_to(root.resolve())
  if not name.startswith('Resource/') or p.suffix.lower()!='.png':raise ValueError('Only explicit PNG baseline resources are supported')
  actual=sha(p.read_bytes()) if p.is_file() else None
  result.append({'path':name,'matches':actual==item['sha256']})
 return result

def export(root,candidate,proposal_path,output):
 baseline=json.loads((root/'baseline.json').read_text(encoding='utf-8'));base=(root/'NewPAL_Release.exe').read_bytes()
 if sha(base)!=baseline['sha256']:raise ValueError('Package baseline EXE changed; restore it first')
 resources=baseline.get('resources',[])
 if not all(r['matches'] for r in resource_state(root,resources)):raise ValueError('Package baseline PNG changed; use a candidate copy')
 proposal=json.loads(proposal_path.read_text(encoding='utf-8-sig'))
 for key in ('title','problem','reproduction','change','validation','risks'):
  if not proposal.get(key):raise ValueError('Missing proposal field: '+key)
 attachments=[]
 for name in proposal.get('files',[]):
  name=safe_name(name);p=(root/name).resolve();p.relative_to(root.resolve())
  if p.suffix.lower() in ('.exe','.dll','.dat','.tsw','.act','.lmf','.dmp'):raise ValueError('Use diff for EXE; do not attach game resources')
  payload=p.read_bytes()
  if len(payload)>10*1024*1024:raise ValueError('Attachment too large')
  attachments.append((name,payload))
 payloads=dict(attachments);pins={r['path']:r['sha256'] for r in resources};changes=[]
 for item in proposal.get('resource_changes',[]):
  name=safe_name(item['path']);attachment=safe_name(item['candidate_file'])
  if not name.startswith('Resource/') or PurePosixPath(name).suffix.lower()!='.png':raise ValueError('Only explicit PNG resource proposals are supported')
  if attachment not in payloads:raise ValueError('Resource candidate must also be listed in files')
  expected=pins.get(name)
  if item.get('base_sha256')!=expected:raise ValueError('Resource baseline hash differs')
  changes.append({'path':name,'base_sha256':expected,'target_sha256':sha(payloads[attachment]),'attachment':attachment})
 if len({c['path'] for c in changes})!=len(changes):raise ValueError('Duplicate resource proposal')
 data=candidate.read_bytes();manifest=make_patch(base,data,allow_unchanged=bool(changes))
 assert reconstruct(base,manifest)==data
 manifest['review_state']='pending_owner_review';manifest['base_resources']=resources;manifest['resource_changes']=changes
 manifest['attachments']=[{'path':name,'sha256':sha(payload),'size':len(payload)} for name,payload in attachments]
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('xb') as stream,zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('return.json',json.dumps(manifest,indent=2));z.writestr('proposal.json',json.dumps(proposal,ensure_ascii=False,indent=2))
  for name,payload in attachments:z.writestr('files/'+name,payload)
 return {'bundle':str(output),'base_sha256':sha(base),'target_sha256':sha(data),'changed_spans':len(manifest['spans']),'review_state':'pending_owner_review'}

def review(bundle,base_path,output=None):
 with zipfile.ZipFile(bundle) as z:
  infos=z.infolist()
  if len({i.filename for i in infos})!=len(infos) or sum(i.file_size for i in infos)>64*1024*1024:raise ValueError('Duplicate names or oversized bundle')
  for i in infos:safe_name(i.filename)
  if z.testzip() is not None:raise ValueError('ZIP CRC failure')
  manifest=json.loads(z.read('return.json'));proposal=json.loads(z.read('proposal.json'))
  for item in manifest.get('attachments',[]):
   payload=z.read('files/'+safe_name(item['path']))
   if len(payload)!=item['size'] or sha(payload)!=item['sha256']:raise ValueError('Attachment differs')
 base=base_path.read_bytes();match=sha(base)==manifest['base_sha256']
 resource_checks=resource_state(base_path.resolve().parent,manifest.get('base_resources',[]))
 for item in manifest.get('resource_changes',[]):
  name=safe_name(item['path']);p=(base_path.resolve().parent/name).resolve();p.relative_to(base_path.resolve().parent)
  if not name.startswith('Resource/') or p.suffix.lower()!='.png':raise ValueError('Invalid resource target')
  with zipfile.ZipFile(bundle) as z:payload=z.read('files/'+safe_name(item['attachment']))
  if sha(payload)!=item['target_sha256']:raise ValueError('Resource target payload hash differs')
  resource_checks.append({'path':name,'matches':(sha(p.read_bytes()) if p.is_file() else None)==item['base_sha256']})
 resources_match=all(r['matches'] for r in resource_checks)
 exe_match=match;match=match and resources_match
 result={'title':proposal.get('title'),'base_matches':match,'review_state':'pending_owner_review',
  'spans':len(manifest['spans']),'files':[a['path'] for a in manifest.get('attachments',[])],
  'target_sha256':manifest['target_sha256'],'proposal':proposal,'exe_base_matches':exe_match,
  'resources_base_match':resources_match,'resource_checks':resource_checks,'resource_changes':manifest.get('resource_changes',[])}
 if match:
  target=reconstruct(base,manifest);result['reconstruction_verified']=True
  if output:
   if output.resolve()==base_path.resolve():raise ValueError('Cannot overwrite baseline/game EXE')
   output.parent.mkdir(parents=True,exist_ok=True)
   with output.open('xb') as f:f.write(target)
   result['candidate_written']=str(output)
 elif output:raise ValueError('BASE MISMATCH: no output written; request a rebase')
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
 sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('inspect');s.add_argument('--exe',type=Path)
 s=sub.add_parser('export');s.add_argument('--candidate',type=Path,required=True);s.add_argument('--proposal',type=Path,required=True);s.add_argument('--out',type=Path,required=True)
 s=sub.add_parser('review');s.add_argument('--bundle',type=Path,required=True);s.add_argument('--base',type=Path,required=True);s.add_argument('--out',type=Path)
 args=p.parse_args();root=args.root.resolve()
 if args.command=='inspect':
  path=args.exe or root/'NewPAL_Release.exe';data=path.read_bytes();pinned=json.loads((root/'baseline.json').read_text(encoding='utf-8'))
  resources=resource_state(path.resolve().parent,pinned.get('resources',[]))
  result={'path':str(path),'sha256':sha(data),'sha1':hashlib.sha1(data).hexdigest(),'size':len(data),
   'matches_package_baseline':sha(data)==pinned['sha256'] and all(r['matches'] for r in resources),'resource_checks':resources,**pe_info(data)}
 elif args.command=='export':result=export(root,args.candidate,args.proposal,args.out)
 else:result=review(args.bundle,args.base,args.out)
 print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
