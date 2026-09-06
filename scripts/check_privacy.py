#!/usr/bin/env python3
"""Check Git objects before public upload. No third-party dependencies; pre-push confirms destination refs."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(['git', *args], stderr=subprocess.PIPE, timeout=30)


PATTERNS = [
    ('private marker', re.compile(rb'PRIVATE[-_ ](?:ONLY|EDITORIAL)|BEGIN[ ]PRIVATE')),
    ('private key', re.compile(rb'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----')),
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
            if (not isinstance(notebook, dict) or notebook.get('nbformat') != 4
                    or type(notebook.get('nbformat_minor')) is not int
                    or notebook['nbformat_minor'] < 0
                    or not isinstance(notebook.get('metadata'), dict)):
                raise ValueError('invalid notebook header')
            cells = notebook['cells']
            if not isinstance(cells, list) or any(not isinstance(c, dict) for c in cells):
                raise ValueError('invalid cells')
            for cell in cells:
                source = cell.get('source')
                if (cell.get('cell_type') not in ('code', 'markdown', 'raw')
                        or not isinstance(cell.get('metadata'), dict)
                        or not (isinstance(source, str) or
                                isinstance(source, list) and all(isinstance(x, str) for x in source))):
                    raise ValueError('invalid cell')
                if cell['cell_type'] == 'code':
                    if (not isinstance(cell.get('outputs'), list)
                            or 'execution_count' not in cell
                            or cell['execution_count'] is not None and type(cell['execution_count']) is not int):
                        raise ValueError('invalid code cell')
            dirty = bool(notebook.get('metadata', {}).get('widgets')) or any(
                c.get('outputs') or c.get('execution_count') is not None for c in cells)
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


# Exact pre-existing upstream revision reviewed during the initial rollout.
# Candidate files cannot grant themselves output exceptions. Changes to this
# code, like changes to the checker itself, require review.
UPSTREAM_NOTEBOOK_COMMIT = 'a9fa8b3ed3962e16d0538a9b26920c02fa85c895'


def legacy_notebooks():
    try:
        git('cat-file', '-e', UPSTREAM_NOTEBOOK_COMMIT + '^{commit}')
    except subprocess.CalledProcessError:
        return {}
    return {name: hashlib.sha256(git('cat-file', 'blob', oid)).hexdigest()
            for name, mode, oid in entries(UPSTREAM_NOTEBOOK_COMMIT)
            if name.endswith('.ipynb') and mode == '100644'}


def check_refs(refs):
    failures = 0
    seen = set()
    baseline = legacy_notebooks()
    for ref in refs:
        files = list(entries(ref))
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
            message = git('show', '-s', '--format=%B', ref + '^{commit}')
            if git('cat-file', '-t', ref).strip() == b'tag':
                message += git('cat-file', 'tag', ref)
            for label, pattern in PATTERNS:
                if pattern.search(message):
                    failures += 1
                    print('BLOCKED metadata object ' + git('rev-parse', ref).decode().strip()[:12] + ': ' + label, file=sys.stderr)
    if failures:
        print('Inspect flagged objects locally. Do not paste their contents into public issues or logs.', file=sys.stderr)
        return 1
    print(f'Privacy check passed: {len(seen)} Git objects across {len(refs)} snapshots. Human confidentiality review remains required.')
    return 0


def outgoing(base, head):
    git('rev-parse', '--verify', head + '^{commit}')
    if base and set(base) == {'0'}:
        base = git('merge-base', 'refs/remotes/origin/main', head).decode().strip()
    args = ['rev-list', '--reverse', head]
    if base and set(base) != {'0'}:
        git('rev-parse', '--verify', base + '^{commit}')
        args.append('^' + base)
    return list(dict.fromkeys(git(*args).decode().splitlines() + [head]))


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
                # Trust the destination's live advertisement, never stale tracking refs.
                exclusions = []
                for row in git('ls-remote', '--refs', args.pre_push).splitlines():
                    oid = row.split()[0].decode()
                    if not re.fullmatch(r'[0-9a-f]{40,64}', oid):
                        raise ValueError('invalid advertised object')
                    try:
                        git('cat-file', '-e', oid + '^{commit}')
                    except subprocess.CalledProcessError:
                        continue
                    exclusions.append('^' + oid)
                refs.extend(git('rev-list', '--reverse', local_oid, *exclusions).decode().splitlines())
            else:
                refs.extend(outgoing(remote_oid, local_oid))
            refs.append(local_oid)  # Include annotated-tag metadata as well as commits.
    return check_refs(list(dict.fromkeys(refs)))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (subprocess.SubprocessError, ValueError, OSError, TypeError, AttributeError) as error:
        print('Privacy check could not complete (' + type(error).__name__ + '). Resolve missing Git history or invalid input before upload.', file=sys.stderr)
        sys.exit(2)
