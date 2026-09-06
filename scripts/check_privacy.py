#!/usr/bin/env python3
"""Check Git objects before public upload. No dependency or network access."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(['git', *args], stderr=subprocess.PIPE)


PATTERNS = [
    ('private marker', re.compile(rb'PRIVATE[-_ ](?:ONLY|EDITORIAL)|BEGIN[ ]PRIVATE')),
    ('private key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('AWS access key', re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('GitHub token', re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b')),
    ('provider token', re.compile(rb'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{30,}\b')),
    ('local user path', re.compile(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/')),
    ('image authoring field', re.compile(rb'["\x27](?:style_prompt|image_prompt|generation_prompt)["\x27]\s*:', re.I)),
]
PRIVATE_PARTS = {'.agents', '.agent', '.obsidian', 'transcripts', 'chat-history', 'private-authoring'}
PRIVATE_NAMES = {'writing-style.md', 'website-editorial-private.md', 'credentials.json'}
PRIVATE_SUFFIXES = {'.pem', '.key', '.p12', '.pfx', '.har', '.log', '.sqlite', '.sqlite3', '.psd', '.xcf'}


def inspect(name, data, mode='100644', notebook_baseline=None):
    """Return categories only, never matching contents."""
    problems = []
    p = PurePosixPath(name.lower())
    if mode not in ('100644', '100755'):
        problems.append('symlink, submodule, or unresolved index entry')
    if any(part in PRIVATE_PARTS for part in p.parts) or p.name in PRIVATE_NAMES:
        problems.append('private authoring path')
    if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
        problems.append('environment file')
    if p.suffix in PRIVATE_SUFFIXES:
        problems.append('private or raw artifact type')
    for label, pattern in PATTERNS:
        if pattern.search(data):
            problems.append(label)
    if p.suffix == '.ipynb':
        try:
            notebook = json.loads(data)
            cells = notebook['cells']
            if not isinstance(cells, list) or any(not isinstance(c, dict) for c in cells):
                raise ValueError('invalid cells')
            dirty = any(c.get('outputs') or c.get('execution_count') is not None for c in cells)
            digest = hashlib.sha256(data).hexdigest()
            if dirty and (notebook_baseline or {}).get(name) != digest:
                problems.append('unreviewed notebook execution output')
        except (ValueError, KeyError, TypeError):
            problems.append('invalid notebook')
    return problems


def entries(ref):
    if ref == ':':
        rows = git('ls-files', '--stage', '-z')
    else:
        rows = git('ls-tree', '-r', '-z', ref)
    for row in rows.split(b'\0'):
        if not row:
            continue
        meta, path = row.split(b'\t', 1)
        fields = meta.decode().split()
        mode, oid = (fields[0], fields[1]) if ref == ':' else (fields[0], fields[2])
        if ref == ':' and fields[2] != '0':
            mode = 'unmerged'
        yield path.decode('utf-8', 'surrogateescape'), mode, oid


def check_refs(refs):
    failures = 0
    seen = set()
    for ref in refs:
        files = list(entries(ref))
        baseline = {}
        for name, mode, oid in files:
            if name == '.privacy-notebooks.json':
                baseline = json.loads(git('cat-file', 'blob', oid))
                if not isinstance(baseline, dict):
                    raise ValueError('invalid notebook baseline')
        baseline_key = json.dumps(baseline, sort_keys=True)
        for name, mode, oid in files:
            key = (name, mode, oid, baseline_key)
            if key in seen:
                continue
            seen.add(key)
            data = git('cat-file', 'blob', oid) if mode in ('100644', '100755', '120000') else b''
            problems = inspect(name, data, mode, baseline)
            if problems:
                # A filename can itself contain sensitive material. Do not print it.
                failures += 1
                print('BLOCKED object ' + oid[:12] + ': ' + ', '.join(problems), file=sys.stderr)
        if ref != ':':
            message = git('show', '-s', '--format=%B', ref)
            for label, pattern in PATTERNS:
                if pattern.search(message):
                    failures += 1
                    print('BLOCKED commit metadata: ' + label, file=sys.stderr)
    if failures:
        print('Inspect flagged objects locally. Do not paste their contents into public issues or logs.', file=sys.stderr)
        return 1
    print(f'Privacy check passed: {len(seen)} Git objects across {len(refs)} snapshots. Human confidentiality review remains required.')
    return 0


def outgoing(base, head):
    git('rev-parse', '--verify', head + '^{commit}')
    args = ['rev-list', '--reverse', head]
    if base and set(base) != {'0'}:
        git('rev-parse', '--verify', base + '^{commit}')
        args.append('^' + base)
    return git(*args).decode().splitlines() or [head]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--staged', action='store_true')
    group.add_argument('--head', action='store_true')
    group.add_argument('--range', nargs=2, metavar=('BASE', 'HEAD'))
    group.add_argument('--pre-push', metavar='REMOTE')
    args = parser.parse_args()
    if args.staged:
        refs = [':']
    elif args.head:
        refs = ['HEAD']
    elif args.range:
        refs = outgoing(*args.range)
    else:
        refs = []
        for line in sys.stdin:
            local_ref, local_oid, remote_ref, remote_oid = line.split()
            if set(local_oid) == {'0'}:
                continue
            if set(remote_oid) == {'0'}:
                # New branches: exclude only objects known on this remote.
                refs.extend(git('rev-list', '--reverse', local_oid, '--not', '--remotes=' + args.pre_push).decode().splitlines())
                refs.append(local_oid)
            else:
                refs.extend(outgoing(remote_oid, local_oid))
    return check_refs(list(dict.fromkeys(refs)))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, ValueError, OSError) as error:
        print('Privacy check could not complete (' + type(error).__name__ + '). Resolve missing Git history or invalid input before upload.', file=sys.stderr)
        sys.exit(2)
