"""Read-only publication preflight. Reports locations/types, NEVER matched values.

This heuristic scanner cannot certify privacy. Binary/visual metadata and Git
history require separate review. Reports are private and must not be published.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

TEXT = {'.py','.c','.cpp','.h','.hpp','.rs','.js','.jsx','.ts','.tsx','.ps1',
        '.bat','.cmd','.sh','.md','.txt','.json','.jsonl','.yaml','.yml','.toml',
        '.ini','.cfg','.conf','.env','.xml','.html','.htm','.csv','.tsv','.svg',
        '.sql','.log','.vdf','.url','.gitignore','.gitattributes'}
SKIP_DIR = {'.git','__pycache__','node_modules','.venv','venv','工具环境',
            '隐私核查_仅本机'}
RULES = [
    ('private_key', 'block', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----')),
    ('service_token', 'block', re.compile(r'\b(?:github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|xox[baprs]-[A-Za-z0-9-]{20,}|AIza[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16})\b')),
    ('bearer_or_jwt', 'review', re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}|\bBasic\s+[A-Za-z0-9+/]{20,}={0,2}|\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}')),
    ('url_credentials', 'block', re.compile(r'(?i)https?://[^\s/:@]+:[^\s/@]{3,}@')),
    ('email_address', 'review', re.compile(r'(?i)\b[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]{1,253}\.[A-Z]{2,24}\b')),
    ('local_user_path', 'review', re.compile(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\x27<>]+')),
    ('account_identifier', 'review', re.compile(r'(?i)\b(?:steamid|accountname|account_id|login_name|用户名|账号)\b\s*["\x27]?\s*[:=]\s*["\x27]?[^\s,"\x27}]{3,}')),
]
ASSIGN = re.compile(r'''(?im)(?<![a-z0-9_])["']?(?:[a-z0-9_]{0,80}(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|private[_-]?key|session[_-]?cookie))["']?\s*[:=]\s*["']([^"'\r\n]{6,4096})["']''')
PLACEHOLDER = re.compile(r'(?i)^(?:none|null|false|true|example|dummy|test|placeholder|redacted|your[_-]|replace|changeme|<|\$\{|os\.|process\.|env\.|getenv|填|示例|密钥|请填)')
PRIVATE_NAME = re.compile(r'(?i)(^|/)(?:\.env(?:\..*)?|\.npmrc|\.pypirc|\.netrc|id_rsa|id_ed25519|credentials(?:\.[^/]*)?|secrets?(?:\.[^/]*)?|[^/]*\.(?:pfx|p12|key|dmp)|[^/]*(?:存档|crash-dumps|cookies|loginusers)[^/]*)(?:/|$)')
MAX_TEXT = 8 * 1024 * 1024
MAX_ARCHIVE = 256 * 1024 * 1024

def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def decode(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16', errors='replace')
    if b'\0' in raw[:4096]:
        return None
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(encoding)
        except UnicodeError:
            pass
    return raw.decode('utf-8', errors='replace')

def textual(name):
    p = Path(name)
    return p.suffix.lower() in TEXT or p.name.lower() in {'license','readme','dockerfile','.npmrc','.pypirc','.netrc'} or p.name.startswith('.env')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    if root == out or not root.is_dir():
        parser.error('Use an existing root and a separate private output directory.')
    findings, examined, skipped = [], [], []
    stats = collections.Counter()
    cache = {}

    def scan_raw(raw):
        digest = hashlib.sha256(raw).hexdigest()
        if digest in cache:
            return digest, cache[digest]
        text = decode(raw)
        hits = []
        if text is not None:
            for kind, severity, rule in RULES:
                for match in rule.finditer(text):
                    hits.append({'kind':kind, 'severity':severity,
                                 'line':text.count('\n', 0, match.start()) + 1})
            for match in ASSIGN.finditer(text):
                value = match.group(1).strip()
                if not PLACEHOLDER.search(value) and len(set(value)) >= 6:
                    hits.append({'kind':'credential_assignment', 'severity':'review',
                                 'line':text.count('\n', 0, match.start()) + 1})
        cache[digest] = hits
        return digest, hits

    def inspect_bytes(name, raw):
        digest, hits = scan_raw(raw)
        examined.append({'path':name,'bytes':len(raw),'sha256':digest})
        stats['text_inputs'] += 1
        for hit in hits:
            findings.append({'path':name, **hit})

    def name_check(name):
        if PRIVATE_NAME.search(name.replace('\\','/')):
            findings.append({'path':name,'kind':'private_filename','severity':'review','line':None})

    for directory, folders, files in os.walk(root, followlinks=False):
        here = Path(directory)
        kept = []
        for folder in sorted(folders):
            item = here / folder
            if folder in SKIP_DIR or item.resolve() == out or item.is_symlink():
                skipped.append({'path':item.relative_to(root).as_posix(),'reason':'excluded_directory'})
            else:
                kept.append(folder)
        folders[:] = kept
        for filename in sorted(files):
            path = here / filename
            name = path.relative_to(root).as_posix()
            name_check(name)
            try:
                if path.is_symlink():
                    skipped.append({'path':name,'reason':'symlink'}); continue
                if path.suffix.lower() == '.zip':
                    stats['archives'] += 1
                    with zipfile.ZipFile(path) as archive:
                        budget = 0
                        for info in archive.infolist():
                            if info.is_dir(): continue
                            member = name + '!' + info.filename
                            name_check(member)
                            if textual(info.filename) and info.file_size <= MAX_TEXT and budget + info.file_size <= MAX_ARCHIVE:
                                inspect_bytes(member, archive.read(info))
                                budget += info.file_size
                            else:
                                skipped.append({'path':member,'reason':'archive_binary_large_or_budget'})
                    examined.append({'path':name,'bytes':path.stat().st_size,'sha256':sha_file(path),'kind':'archive_container'})
                elif textual(name) and path.stat().st_size <= MAX_TEXT:
                    inspect_bytes(name, path.read_bytes())
                else:
                    stats['binary_or_large_inputs'] += 1
                    skipped.append({'path':name,'reason':'binary_or_large'})
            except Exception as error:
                skipped.append({'path':name,'reason':'read_error','error_type':type(error).__name__})
    counts = collections.Counter(hit['kind'] for hit in findings)
    report = {'schema_version':1,'private_local_only':True,
              'scanner_sha256':sha_file(Path(__file__)),
              'result':'needs_review_not_publication_approval',
              'scope_root':str(root),'statistics':dict(stats),
              'counts_by_kind':dict(counts),'findings':findings,
              'examined':examined,'skipped':skipped,
              'limits':['Heuristic patterns; no guarantee of absence.',
                        'No binary strings, image OCR, PSD content, EXIF/XMP, SQLite contents or Git history scan.',
                        'ZIP text scanned with per-member and per-archive limits; nested archives not recursively scanned.',
                        'Files may change during scan; release requires a fresh scan of frozen staging and artifacts.',
                        'Matched values and surrounding source text are never included.']}
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'privacy-report.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(target),'statistics':dict(stats),
                      'counts_by_kind':dict(counts),'result':report['result']},ensure_ascii=False))

if __name__ == '__main__':
    main()
