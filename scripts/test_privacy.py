"""Behavioral checks for Git-index and outgoing-history privacy boundaries."""
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('check_privacy.py').resolve()
SPEC = importlib.util.spec_from_file_location('privacy', SCRIPT)
privacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy)


class ContentChecks(unittest.TestCase):
    def test_public_prompt(self):
        self.assertEqual(privacy.inspect('prompts/system.txt', b'Answer using synthetic evidence.'), [])

    def test_private_markers_in_paths(self):
        for name in ['PRIVATE' + '_ONLY-client.md', 'docs/BEGIN' + ' PRIVATE.txt', 'notes/private' + '-only-client.md', 'PRIVATE' + ' ONLY - client.md', 'notes/gh' + 'p_' + 'Z' * 40 + '.txt']:
            self.assertTrue(privacy.inspect(name, b'Neutral body'))

    def test_bom_encoded_private_text(self):
        for encoding in ['utf-16', 'utf-32', 'utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be']:
            for text in ['PRIVATE' + '_ONLY', 'image' + '_prompt: recipe']:
                self.assertTrue(privacy.inspect('note.txt', text.encode(encoding)))

    def test_mixed_encoding_keeps_raw_scan(self):
        self.assertTrue(privacy.inspect('note.txt', 'public'.encode('utf-16') + b'PRIVATE' + b'_ONLY'))

    def test_environment_variants(self):
        for name in ['.env', '.env.local', '.env.production', '.envrc', '.envrc.local']:
            self.assertTrue(privacy.inspect(name, b''))
        self.assertFalse(privacy.inspect('.env.example', b'API_KEY='))

    def test_private_paths(self):
        self.assertTrue(privacy.inspect('.' + 'agents/guide.md', b''))
        self.assertTrue(privacy.inspect('.direnv/environment', b'Neutral body'))
        for folder in ['logs', '.venv', 'venv', '__pycache__']:
            self.assertTrue(privacy.inspect(folder + '/data.txt', b'Neutral body'))
        self.assertTrue(privacy.inspect('notes/' + 'writing' + '-style.md', b''))

    def test_secrets_and_private_markers(self):
        for value in [b'AK' + b'IA' + b'Z' * 16, b'gh' + b'p_' + b'Z' * 40,
                      b'PRIVATE' + b'_ONLY', b'/Us' + b'ers/demo/file',
                      b'{"image' + b'_prompt": "recipe"}']:
            self.assertTrue(privacy.inspect('data.txt', value))

    def test_private_key_variants(self):
        for prefix in ['ENCRYPTED', 'DSA', 'RSA', 'EC', 'OPENSSH']:
            data = ('-----BEGIN ' + prefix + ' PRIVATE' + ' KEY-----').encode()
            self.assertTrue(privacy.inspect('neutral.txt', data))

        self.assertTrue(privacy.inspect('key.asc', ('-----BEGIN PGP' + ' PRIVATE KEY BLOCK-----').encode()))

    def test_widget_state(self):
        data = json.dumps({'nbformat': 4, 'nbformat_minor': 0, 'cells': [], 'metadata': {'widgets': {'state': 'result'}}}).encode()
        self.assertTrue(privacy.inspect('demo.ipynb', data))

    def test_windows_user_paths(self):
        for path in ['C:' + chr(92) + 'Users' + chr(92) + 'demo' + chr(92) + 'note.txt',
                     chr(92) * 2 + 'server' + chr(92) + 'Users' + chr(92) + 'demo' + chr(92) + 'note.txt']:
            self.assertTrue(privacy.inspect('data.txt', path.encode()))
            self.assertTrue(privacy.inspect('data.json', json.dumps(path).encode()))
            spaced = path.replace('demo', 'Jane Doe')
            self.assertTrue(privacy.inspect('data.txt', spaced.encode()))
            self.assertTrue(privacy.inspect('data.json', json.dumps(spaced).encode()))

    def test_home_directory_without_child(self):
        for path in ['/ro' + 'ot/project/file', '/ho' + 'me/alice', '/ho' + 'me/andré/file', '/ho' + 'me/李/file', '/Us' + 'ers/Élodie/file', '/Us' + 'ers/Jane Doe/file', '/Us' + 'ers/alice', 'C:' + chr(92) + 'Users' + chr(92) + 'alice']:
            self.assertTrue(privacy.inspect('data.txt', path.encode()))

    def test_unquoted_authoring_fields(self):
        for delimiter in [':', '=']:
            self.assertTrue(privacy.inspect('data.yaml', ('image' + '_prompt' + delimiter + ' recipe').encode()))

    def test_marker_case_and_generation_spellings(self):
        for marker in ['Note: Private' + '_Only', 'Private' + '_Only', 'private' + '-editorial', 'Begin' + ' Private', 'private' + ' editorial', 'Private' + ' Editorial:', 'NOTE: PRIVATE' + ' ONLY: do not publish', 'Note: Private' + '-Only: do not publish', 'Note: private' + '-only: do not publish', 'NOTE: PRIVATE' + ' ONLY. do not publish', 'NOTE: PRIVATE' + ' EDITORIAL. do not publish', 'NOTE: PRIVATE' + ' EDITORIAL: do not publish', '<!-- Private' + ' Editorial: do not publish -->']:
            self.assertTrue(privacy.inspect('data.txt', marker.encode()))
        self.assertFalse(privacy.inspect('README.md', b'Keep private editorial methods elsewhere.'))
        self.assertFalse(privacy.inspect('README.md', b'Builds reject private-only files.'))
        for key in ['negative' + '_prompt', 'generation' + 'Prompt', 'image' + 'Prompt', 'baseStyle' + 'Prompt']:
            self.assertTrue(privacy.inspect('data.json', json.dumps({key: 'recipe'}).encode()))

    def test_upstream_example_exception_is_exact_and_narrow(self):
        data = ('image' + '_prompt: dict\n' + '/ro' + 'ot/.cache/pip').encode()
        baseline = {'example.txt': hashlib.sha256(data).hexdigest()}
        self.assertFalse(privacy.inspect('example.txt', data, notebook_baseline=baseline))
        self.assertTrue(privacy.inspect('example.txt', data + b' ', notebook_baseline=baseline))
        secret = ('PRIVATE' + '_ONLY').encode()
        baseline = {'example.txt': hashlib.sha256(secret).hexdigest()}
        self.assertTrue(privacy.inspect('example.txt', secret, notebook_baseline=baseline))

    def test_symlink(self):
        self.assertTrue(privacy.inspect('asset.txt', b'elsewhere', '120000'))

    def test_notebook(self):
        clean = {'nbformat': 4, 'nbformat_minor': 0, 'metadata': {},
                 'cells': [{'cell_type': 'code', 'metadata': {}, 'source': [],
                            'outputs': [], 'execution_count': None}]}
        self.assertFalse(privacy.inspect('demo.ipynb', json.dumps(clean).encode()))
        clean['cells'][0]['outputs'] = [{'output_type': 'stream', 'text': ['result']}]
        data = json.dumps(clean).encode()
        self.assertTrue(privacy.inspect('demo.ipynb', data))
        baseline = {'demo.ipynb': hashlib.sha256(data).hexdigest()}
        self.assertFalse(privacy.inspect('demo.ipynb', data, notebook_baseline=baseline))
        self.assertTrue(privacy.inspect('demo.ipynb', data + b' ', notebook_baseline=baseline))
        self.assertTrue(privacy.inspect('demo.ipynb', b'{}'))
        self.assertTrue(privacy.inspect('demo.ipynb', b'{"cells":[]}'))


class GitChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'work'
        self.root.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Privacy test')
        self.git('config', 'user.email', 'privacy@example.invalid')
        self.git('config', 'core.hooksPath', '/dev/null')
        remote = str(Path(self.temp.name) / 'remote.git')
        self.git('init', '--bare', '-q', remote)
        self.git('remote', 'add', 'origin', remote)
        (self.root / 'readme.txt').write_text('Public example')
        self.git('add', '.')
        self.git('commit', '-qm', 'Base')
        self.base = self.git('rev-parse', 'HEAD').strip()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, env=self.env, text=True, stderr=subprocess.PIPE)

    def check(self, *args, input_text=None):
        return subprocess.run(['python3', str(SCRIPT), *args], cwd=self.root, env=self.env,
                              input=input_text, text=True, capture_output=True)

    def test_staged_bytes_not_worktree(self):
        p = self.root / 'readme.txt'
        p.write_text('PRIVATE' + '_ONLY')
        self.git('add', '.')
        p.write_text('Public again')
        result = self.check('--staged')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(p.read_text(), result.stderr)
        self.assertNotIn('PRIVATE' + '_ONLY', result.stderr)

    def test_deleted_secret_in_intermediate_commit(self):
        p = self.root / '.env.local'
        p.write_text('SECRET=sample')
        self.git('add', '.')
        self.git('commit', '-qm', 'Intermediate')
        self.git('rm', '-q', '.env.local')
        self.git('commit', '-qm', 'Cleanup')
        self.assertEqual(self.check('--head').returncode, 0)
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 1)

    def test_missing_base_fails_closed(self):
        self.assertEqual(self.check('--range', 'f' * 40, 'HEAD').returncode, 2)

    def test_pre_push_new_branch(self):
        head = self.git('rev-parse', 'HEAD').strip()
        line = 'refs/heads/topic ' + head + ' refs/heads/topic ' + '0' * 40 + '\n'
        self.assertEqual(self.check('--pre-push', 'origin', input_text=line).returncode, 0)

    def test_zero_base_excludes_existing_remote_history(self):
        p = self.root / '.env.local'
        p.write_text('OLD=sample')
        self.git('add', '.')
        self.git('commit', '-qm', 'Historical material')
        self.git('rm', '-q', '.env.local')
        self.git('commit', '-qm', 'Historical cleanup')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.git('commit', '--allow-empty', '-qm', 'New branch')
        baseline = self.git('merge-base', 'refs/remotes/origin/main', 'HEAD').strip()
        self.assertEqual(self.check('--range', baseline, 'HEAD').returncode, 0)
        self.assertEqual(self.check('--range', '0' * 40, 'HEAD').returncode, 1)
        p.write_text('NEW=sample')
        self.git('add', '.')
        self.git('commit', '-qm', 'New disclosure')
        self.assertEqual(self.check('--range', '0' * 40, 'HEAD').returncode, 1)

    def test_candidate_cannot_authorize_output(self):
        data = json.dumps({'nbformat': 4, 'nbformat_minor': 0, 'metadata': {},
                           'cells': [{'cell_type': 'code', 'source': [], 'metadata': {},
                                      'execution_count': None, 'outputs': [{'text': ['result']}]}]}).encode()
        (self.root / 'demo.ipynb').write_bytes(data)
        (self.root / '.privacy-notebooks.json').write_text(json.dumps(
            {'demo.ipynb': hashlib.sha256(data).hexdigest()}))
        self.git('add', '.')
        self.assertEqual(self.check('--staged').returncode, 1)
        self.git('commit', '-qm', 'Candidate exception')
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 1)

    def test_stale_tracking_ref_cannot_hide_new_history(self):
        p = self.root / '.env.local'
        p.write_text('SAMPLE=value')
        self.git('add', '.')
        self.git('commit', '-qm', 'Intermediate')
        self.git('rm', '-q', '.env.local')
        self.git('commit', '-qm', 'Cleanup')
        self.git('update-ref', 'refs/remotes/origin/stale', 'HEAD')
        head = self.git('rev-parse', 'HEAD').strip()
        line = 'refs/heads/topic ' + head + ' refs/heads/topic ' + '0' * 40 + '\n'
        self.assertEqual(self.check('--pre-push', 'origin', input_text=line).returncode, 1)

    def test_ci_resolves_annotated_tag_ref(self):
        self.git('tag', '-a', 'release', '-m', 'PRIVATE' + '_ONLY')
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/check_privacy.py').write_bytes(SCRIPT.read_bytes())
        workflow = SCRIPT.parent.parent.joinpath('.github/workflows/privacy.yml').read_text()
        command = workflow.split('        run: |\n')[-1]
        command = '\n'.join(line[10:] for line in command.splitlines())
        env = dict(self.env, GITHUB_REF_TYPE='tag', GITHUB_REF='refs/tags/release',
                   BASE_SHA=self.base, HEAD_SHA=self.base)
        result = subprocess.run(['bash', '-e', '-c', command], cwd=self.root, env=env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(self.git('rev-parse', 'release').strip()[:12], result.stderr)

    def test_bom_encoded_tag_annotation(self):
        for encoding in ['utf-16', 'utf-32', 'utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be']:
            annotation = Path(self.temp.name) / 'annotation.txt'
            annotation.write_bytes(('PRIVATE' + '_ONLY').encode(encoding))
            self.git('tag', '-fa', 'encoded', '-F', str(annotation))
            oid = self.git('rev-parse', 'encoded').strip()
            self.assertNotEqual(self.check('--range', self.base, oid).returncode, 0)
            line = 'refs/tags/encoded ' + oid + ' refs/tags/encoded ' + '0' * 40 + '\n'
            self.assertNotEqual(self.check('--pre-push', 'origin', input_text=line).returncode, 0)

    def test_unknown_tag_encoding_fails_closed(self):
        annotation = Path(self.temp.name) / 'annotation.txt'
        annotation.write_bytes(('PRIVATE' + '_ONLY').encode('cp037'))
        self.git('tag', '-a', 'encoded', '-F', str(annotation))
        oid = self.git('rev-parse', 'encoded').strip()
        self.assertNotEqual(self.check('--range', self.base, oid).returncode, 0)

    def test_sensitive_destination_ref(self):
        for name in ['PRIVATE' + '_ONLY-client', 'gh' + 'p_' + 'Z' * 40]:
            line = 'refs/heads/topic ' + self.base + ' refs/heads/' + name + ' ' + '0' * 40 + '\n'
            result = self.check('--pre-push', 'origin', input_text=line)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(name, result.stderr)
            self.assertEqual(self.check('--head', '--ref-name', 'refs/heads/' + name).returncode, 1)

    def test_unsupported_tag_header_encoding(self):
        prefix = ('object ' + self.base + '\ntype commit\ntag sample\ntagger ').encode()
        raw = prefix + ('PRIVATE' + '_ONLY').encode('cp037') + b' <test@example.invalid> 1 +0000\n\nPublic annotation\n'
        oid = subprocess.check_output(['git', 'hash-object', '-t', 'tag', '-w', '--stdin'],
                                      cwd=self.root, env=self.env, input=raw).decode().strip()
        self.assertNotEqual(self.check('--range', self.base, oid).returncode, 0)

    def test_updated_annotated_tag(self):
        self.git('tag', '-a', 'v1', '-m', 'Public version')
        old = self.git('rev-parse', 'v1').strip()
        self.git('commit', '--allow-empty', '-qm', 'New version')
        self.git('tag', '-fa', 'v1', '-m', 'PRIVATE' + '_ONLY')
        tag = self.git('rev-parse', 'v1').strip()
        line = 'refs/tags/v1 ' + tag + ' refs/tags/v1 ' + old + '\n'
        result = self.check('--pre-push', 'origin', input_text=line)
        self.assertEqual(result.returncode, 1)
        self.assertIn(tag[:12], result.stderr)
        self.assertEqual(self.check('--range', old, tag).returncode, 1)
        self.assertNotIn('PRIVATE' + '_ONLY', result.stderr)

    def test_hook_uses_push_destination_not_fetch_remote(self):
        p = self.root / '.env.local'
        p.write_text('SAMPLE=value')
        self.git('add', '.')
        self.git('commit', '-qm', 'Intermediate')
        self.git('rm', '-q', '.env.local')
        self.git('commit', '-qm', 'Cleanup')
        self.git('push', '-q', 'origin', 'HEAD:refs/heads/existing')
        target = str(Path(self.temp.name) / 'destination.git')
        self.git('init', '--bare', '-q', target)
        self.git('remote', 'set-url', '--push', 'origin', target)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/check_privacy.py').write_bytes(SCRIPT.read_bytes())
        hooks = self.root / 'hooks'
        hooks.mkdir()
        hook = hooks / 'pre-push'
        hook.write_bytes(SCRIPT.parent.parent.joinpath('.githooks/pre-push').read_bytes())
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', str(hooks))
        result = subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/topic'],
                                cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BLOCKED', result.stderr)
        self.assertEqual(self.git('ls-remote', '--refs', target).strip(), '')

    def test_nested_annotated_tags(self):
        self.git('tag', '-a', 'inner', '-m', 'PRIVATE' + '_ONLY')
        inner = self.git('rev-parse', 'inner').strip()
        self.git('tag', '-a', 'outer', 'inner', '-m', 'Public annotation')
        outer = self.git('rev-parse', 'outer').strip()
        line = 'refs/tags/outer ' + outer + ' refs/tags/outer ' + '0' * 40 + '\n'
        result = self.check('--pre-push', 'origin', input_text=line)
        self.assertEqual(result.returncode, 1)
        self.assertIn(inner[:12], result.stderr)
        self.assertEqual(self.check('--range', self.base, outer).returncode, 1)

    def test_replace_refs_cannot_hide_published_objects(self):
        (self.root / 'readme.txt').write_text('PRIVATE' + '_ONLY')
        self.git('add', '.')
        self.git('commit', '-qm', 'Blocked content')
        bad = self.git('rev-parse', 'HEAD').strip()
        self.git('replace', bad, self.base)
        self.assertEqual(self.check('--range', self.base, bad).returncode, 1)
        line = 'refs/heads/topic ' + bad + ' refs/heads/topic ' + '0' * 40 + '\n'
        self.assertEqual(self.check('--pre-push', 'origin', input_text=line).returncode, 1)

    def test_shallow_ancestry_fails_closed(self):
        shallow = self.root / '.git/shallow'
        shallow.write_text(self.base + '\n')
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 2)

    def test_grafts_cannot_hide_intermediate_history(self):
        p = self.root / '.env.local'
        p.write_text('SAMPLE=value')
        self.git('add', '.')
        self.git('commit', '-qm', 'Intermediate')
        self.git('rm', '-q', '.env.local')
        self.git('commit', '-qm', 'Cleanup')
        head = self.git('rev-parse', 'HEAD').strip()
        (self.root / '.git/info/grafts').write_text(head + '\n')
        self.assertEqual(self.check('--range', self.base, head).returncode, 2)

    def test_declared_commit_encoding(self):
        tree = self.git('rev-parse', 'HEAD^{tree}').strip()
        headers = ('tree ' + tree + '\nparent ' + self.base +
                   '\nauthor Test <test@example.invalid> 1 +0000\ncommitter Test <test@example.invalid> 1 +0000\nencoding ')
        for encoding in ['IBM037', 'unsupported-example-encoding']:
            raw = (headers + encoding + '\n\n').encode() + ('PRIVATE' + '_ONLY').encode('cp037')
            oid = subprocess.check_output(['git', 'hash-object', '-t', 'commit', '-w', '--stdin'],
                                          cwd=self.root, env=self.env, input=raw).decode().strip()
            self.assertNotEqual(self.check('--range', self.base, oid).returncode, 0)

    def test_nul_interleaved_commit_message(self):
        tree = self.git('rev-parse', 'HEAD^{tree}').strip()
        header = ('tree ' + tree + '\nparent ' + self.base +
                  '\nauthor Test <test@example.invalid> 1 +0000\ncommitter Test <test@example.invalid> 1 +0000\n\n').encode()
        raw = header + ('PRIVATE' + '_ONLY').encode('utf-16-le')
        oid = subprocess.check_output(['git', 'hash-object', '--literally', '-t', 'commit', '-w', '--stdin'],
                                      cwd=self.root, env=self.env, input=raw).decode().strip()
        self.assertNotEqual(self.check('--range', self.base, oid).returncode, 0)

    def test_commit_message_ignores_display_encoding(self):
        self.git('commit', '--allow-empty', '-qm', 'PRIVATE' + '_ONLY')
        self.git('config', 'i18n.logOutputEncoding', 'UTF-16LE')
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 1)

    def test_commit_message(self):
        self.git('commit', '--allow-empty', '-qm', 'PRIVATE' + '_ONLY')
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 1)


if __name__ == '__main__':
    unittest.main()
