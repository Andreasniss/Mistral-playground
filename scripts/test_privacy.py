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

    def test_environment_variants(self):
        for name in ['.env', '.env.local', '.env.production']:
            self.assertTrue(privacy.inspect(name, b''))
        self.assertFalse(privacy.inspect('.env.example', b'API_KEY='))

    def test_private_paths(self):
        self.assertTrue(privacy.inspect('.' + 'agents/guide.md', b''))
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

    def test_widget_state(self):
        data = json.dumps({'nbformat': 4, 'nbformat_minor': 0, 'cells': [], 'metadata': {'widgets': {'state': 'result'}}}).encode()
        self.assertTrue(privacy.inspect('demo.ipynb', data))

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
        self.assertEqual(self.check('--range', '0' * 40, 'HEAD').returncode, 0)
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

    def test_commit_message(self):
        self.git('commit', '--allow-empty', '-qm', 'PRIVATE' + '_ONLY')
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 1)


if __name__ == '__main__':
    unittest.main()
