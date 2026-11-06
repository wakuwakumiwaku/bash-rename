"""Directory enumeration refusal with real POSIX permissions and owned files."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "rename.bash"


class DirectoryReadTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "Real mode-bit refusal requires POSIX")
    def test_unreadable_directory_fails_without_renaming(self):
        with tempfile.TemporaryDirectory(prefix="rename-unreadable-") as directory:
            root = Path(directory)
            work = root / "files"
            work.mkdir()
            source = work / "document.txt"
            source.write_bytes(b"preserve owned document")
            canary = root / "canary"
            canary.write_bytes(b"outside stays")
            work.chmod(0o300)  # Writing/traversal allowed, directory listing denied.
            try:
                if os.access(work, os.R_OK):
                    self.skipTest("This user/filesystem can still read the permission-denied directory")
                result = subprocess.run(["bash", str(SCRIPT)], cwd=work,
                                        capture_output=True, timeout=5)
            finally:
                work.chmod(0o700)
            self.assertEqual({p.name: p.read_bytes() for p in work.iterdir()},
                             {"document.txt": b"preserve owned document"})
            self.assertEqual(canary.read_bytes(), b"outside stays")
            self.assertNotEqual(result.returncode, 0, "An unreadable directory must not look like a successful empty run")
            self.assertIn(b"Cannot read current directory", result.stderr)

    def test_readable_empty_and_populated_directories_still_succeed(self):
        with tempfile.TemporaryDirectory(prefix="rename-readable-") as directory:
            work = Path(directory)
            result = subprocess.run(["bash", str(SCRIPT)], cwd=work, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(work.iterdir()), [])
            (work / "document.txt").write_bytes(b"owned document")
            result = subprocess.run(["bash", str(SCRIPT)], cwd=work, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p.name: p.read_bytes() for p in work.iterdir()}, {"1.pdf": b"owned document"})


if __name__ == "__main__":
    unittest.main()
