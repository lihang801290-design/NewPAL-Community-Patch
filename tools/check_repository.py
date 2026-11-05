"""Offline integrity checks; no network, installs or external code execution."""
import ast
import hashlib
import json
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    baseline=json.loads((root/'baseline.json').read_text(encoding='utf-8'))
    errors=[]
    for item in baseline['resources']:
        path=(root/item['path']).resolve()
        try:path.relative_to(root)
        except ValueError:errors.append('Resource path escapes repository');continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            errors.append('Resource mismatch: '+item['path'])
    expected={x['path'] for x in baseline['resources']}
    actual={x.relative_to(root).as_posix() for x in (root/'Resource').glob('*.png')}
    if actual!=expected:errors.append('Unexpected/missing resource files')
    if hashlib.sha256((root/'patch/latest.json.gz').read_bytes()).hexdigest()!=baseline['delta_sha256']:
        errors.append('Delta hash mismatch')
    sources=json.loads((root/'docs/source-modules.json').read_text(encoding='utf-8'))
    for item in sources['modules']:
        path=root/item['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            errors.append('Source changed since manifest: '+item['path'])
    count=0
    for path in root.rglob('*.py'):
        if '__pycache__' not in path.parts:
            ast.parse(path.read_text(encoding='utf-8-sig'));count+=1
    print(json.dumps({'resource_count':len(expected),'python_syntax_checked':count,
        'source_modules':len(sources['modules']),'errors':errors,
        'privacy_and_gameplay':'separate checks required'},indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
