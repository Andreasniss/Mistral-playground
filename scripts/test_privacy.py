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

    def test_symlink(self):
        self.assertTrue(privacy.inspect('asset.txt', b'elsewhere', '120000'))

    def test_notebook(self):
        clean = {'cells': [{'cell_type': 'code', 'outputs': [], 'execution_count': None}]}
        self.assertFalse(privacy.inspect('demo.ipynb', json.dumps(clean).encode()))
        clean['cells'][0]['outputs'] = [{'output_type': 'stream', 'text': ['result']}]
        data = json.dumps(clean).encode()
        self.assertTrue(privacy.inspect('demo.ipynb', data))
        baseline = {'demo.ipynb': hashlib.sha256(data).hexdigest()}
        self.assertFalse(privacy.inspect('demo.ipynb', data, notebook_baseline=baseline))
        self.assertTrue(privacy.inspect('demo.ipynb', data + b' ', notebook_baseline=baseline))
        self.assertTrue(privacy.inspect('demo.ipynb', b'{}'))


class GitChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Privacy test')
        self.git('config', 'user.email', 'privacy@example.invalid')
        self.git('config', 'core.hooksPath', '/dev/null')
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

    def test_commit_message(self):
        self.git('commit', '--allow-empty', '-qm', 'PRIVATE' + '_ONLY')
        self.assertEqual(self.check('--range', self.base, 'HEAD').returncode, 1)


if __name__ == '__main__':
    unittest.main()
