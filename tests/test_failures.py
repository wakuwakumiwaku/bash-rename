"""Real command failures must be visible to callers; all files are disposable."""
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'rename.bash'


def require_tool(name):
    path = shutil.which(name)
    if path is None:
        raise RuntimeError('Required test tool not found: ' + name)
    return path


BASH = require_tool('bash')
SORT = require_tool('sort')
MV = require_tool('mv')


class FailureStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rename-failures-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / 'work'
        self.work.mkdir()

    def run_script(self, env=None):
        return subprocess.run([BASH, str(SCRIPT)], cwd=self.work, env=env,
                              capture_output=True, timeout=5)

    def readonly(self):
        if os.geteuid() == 0:
            self.skipTest('Permission-denial fixture requires an unprivileged user')
        self.work.chmod(0o555)
        self.addCleanup(self.work.chmod, 0o755)

    def test_failed_move_followed_by_skipped_directory_is_nonzero(self):
        (self.work / 'a.txt').write_bytes(b'preserve original')
        (self.work / 'z-directory').mkdir()
        self.readonly()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0, 'a later skipped entry must not hide mv failure')
        self.assertIn(b'mv:', result.stderr)
        self.assertEqual((self.work / 'a.txt').read_bytes(), b'preserve original')
        self.assertFalse((self.work / '1.pdf').exists())

    def test_failed_move_followed_by_successful_noop_is_nonzero(self):
        (self.work / '0.txt').write_bytes(b'first')
        (self.work / '2.pdf').write_bytes(b'last')
        self.readonly()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0, 'a later successful mv must not hide an earlier failure')
        self.assertEqual((self.work / '0.txt').read_bytes(), b'first')
        self.assertEqual((self.work / '2.pdf').read_bytes(), b'last')

    def test_missing_sort_dependency_is_nonzero_without_renaming(self):
        # An actual missing command, not a fake sorter or a stubbed filesystem.
        tools = self.root / 'tools'
        tools.mkdir()
        (tools / 'mv').symlink_to(MV)
        (self.work / 'source.txt').write_bytes(b'original')
        result = self.run_script(dict(os.environ, PATH=str(tools)))
        self.assertNotEqual(result.returncode, 0, 'failed input enumeration must not report success')
        self.assertEqual((self.work / 'source.txt').read_bytes(), b'original')
        self.assertFalse((self.work / '1.pdf').exists())

    def test_failure_does_not_stop_later_success_or_erase_failure_status(self):
        # An executable spy injects one failure; the later move uses real GNU mv.
        tools = self.root / 'tools'
        tools.mkdir()
        (tools / 'sort').symlink_to(SORT)
        mover = tools / 'mv'
        mover.write_text('#!/bin/sh\nif [ "$3" = "./a.txt" ]; then\n'
                         '  printf "injected mv failure\\n" >&2\n  exit 73\nfi\n'
                         f'exec {shlex.quote(MV)} "$@"\n')
        mover.chmod(0o755)
        (self.work / 'a.txt').write_bytes(b'first stays')
        (self.work / 'b.txt').write_bytes(b'second moves')
        result = self.run_script(dict(os.environ, PATH=str(tools)))
        self.assertNotEqual(result.returncode, 0, 'later success must not mask the first failure')
        self.assertIn(b'injected mv failure', result.stderr)
        self.assertEqual((self.work / 'a.txt').read_bytes(), b'first stays')
        self.assertFalse((self.work / '1.pdf').exists())
        self.assertFalse((self.work / 'b.txt').exists())
        self.assertEqual((self.work / '2.pdf').read_bytes(), b'second moves')

    def test_sort_failure_after_output_is_nonzero_even_when_move_succeeds(self):
        tools = self.root / 'tools'
        tools.mkdir()
        (tools / 'mv').symlink_to(MV)
        sorter = tools / 'sort'
        sorter.write_text(f'#!/bin/sh\n{shlex.quote(SORT)} "$@"\nexit 73\n')
        sorter.chmod(0o755)
        (self.work / 'source.txt').write_bytes(b'original')
        result = self.run_script(dict(os.environ, PATH=str(tools)))
        self.assertNotEqual(result.returncode, 0, 'consumer success must not mask sorter failure')
        self.assertEqual((self.work / '1.pdf').read_bytes(), b'original')

    def test_successful_run_stays_zero(self):
        (self.work / 'source.txt').write_bytes(b'original')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / '1.pdf').read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
