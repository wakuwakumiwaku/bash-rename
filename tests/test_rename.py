import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(os.environ.get(
    "BASH_RENAME_SCRIPT", Path(__file__).resolve().parents[1] / "rename.bash"
)).resolve()


def require_tool(name):
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required test tool not found: {name}")
    return path


BASH = require_tool("bash")
SORT = require_tool("sort")
LS = require_tool("ls")


class RenameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rename-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "files"
        self.work.mkdir()
        self.canary = self.root / "canary"
        self.canary.write_bytes(b"do not change\n")
        self.env = {"PATH": os.environ["PATH"], "LC_ALL": "C"}
        for key in ("HOME", "TMPDIR"):
            directory = self.root / key.lower()
            directory.mkdir()
            self.env[key] = str(directory)

    def run_script(self, script=SCRIPT):
        result = subprocess.run(
            [BASH, str(script)], cwd=self.work, env=self.env,
            capture_output=True, timeout=10,
        )
        self.assertEqual(self.canary.read_bytes(), b"do not change\n")
        return result

    def assert_numbered(self, names):
        payloads = {}
        for i, name in enumerate(names):
            payloads[name] = f"source {i}\n".encode()
            (self.work / name).write_bytes(payloads[name])
        order = subprocess.run(
            [SORT, "-z", "-V"], input=b"\0".join(os.fsencode(n) for n in names) + b"\0",
            env=self.env, capture_output=True, check=True,
        ).stdout.rstrip(b"\0").split(b"\0")
        result = self.run_script()
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.work.iterdir()},
            {f"{i}.pdf": payloads[os.fsdecode(name)] for i, name in enumerate(order, 1)},
            result.stderr.decode(errors="replace"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ordinary_version_order_matches_ls_not_creation_time(self):
        names = ["report10.txt", "report2.txt", "report1.txt", "another.txt"]
        for name in names:
            (self.work / name).write_text(name)
        # Deliberately reverse timestamps: neither mtime nor a fabricated creation order is used.
        for i, name in enumerate(names):
            os.utime(self.work / name, (1000 + i, 1000 + i))
        order = subprocess.run(
            [LS, "-v"], cwd=self.work, env=self.env, capture_output=True, check=True,
        ).stdout.decode().splitlines()
        self.assertEqual(order, ["another.txt", "report1.txt", "report2.txt", "report10.txt"])
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {p.name: p.read_text() for p in self.work.iterdir()},
            {f"{i}.pdf": name for i, name in enumerate(order, 1)},
        )

    def test_newlines_are_part_of_a_filename(self):
        self.assert_numbered(["a\nb.pdf", "other.pdf"])

    def test_edge_spaces_and_tabs_are_preserved(self):
        self.assert_numbered([" leading.pdf", "trailing.pdf ", "\ttabbed\t.pdf\t"])

    def test_backslashes_are_preserved(self):
        self.assert_numbered(["a\\b.pdf", "c\\ d.pdf"])

    def test_options_and_shell_metacharacters_are_literal(self):
        self.assert_numbered([
            "--help", "-f", "--target-directory=..", "$(touch PWNED)",
            "semi;touch PWNED", "glob*[?].pdf", "quote'\".pdf",
        ])
        self.assertFalse((self.root / "PWNED").exists())
        self.assertFalse((self.work / "PWNED").exists())

    def test_directories_and_symlinks_do_not_consume_numbers(self):
        directory = self.work / "album"
        directory.mkdir()
        (directory / "canary").write_bytes(b"nested")
        link = self.work / "external"
        link.symlink_to(self.canary)
        (self.work / "z.pdf").write_bytes(b"document")
        result = self.run_script()
        self.assertTrue(directory.is_dir(), result.stderr)
        self.assertEqual((directory / "canary").read_bytes(), b"nested")
        self.assertTrue(link.is_symlink())
        self.assertEqual((self.work / "1.pdf").read_bytes(), b"document")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_running_script_is_not_renamed_or_counted(self):
        local_script = self.work / "rename.bash"
        local_script.write_bytes(SCRIPT.read_bytes())
        (self.work / "a.pdf").write_bytes(b"first")
        (self.work / "z.pdf").write_bytes(b"last")
        result = self.run_script(local_script)
        self.assertTrue(local_script.is_file(), result.stderr)
        self.assertEqual(local_script.read_bytes(), SCRIPT.read_bytes())
        self.assertEqual((self.work / "1.pdf").read_bytes(), b"first")
        self.assertEqual((self.work / "2.pdf").read_bytes(), b"last")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_regular_target_is_not_overwritten(self):
        for name, content in [("01.pdf", b"leading zero"), ("1.pdf", b"occupied"), ("z.pdf", b"last")]:
            (self.work / name).write_bytes(content)
        result = self.run_script()
        self.assertEqual(
            {p.name: p.read_bytes() for p in self.work.iterdir()},
            {"01.pdf": b"leading zero", "2.pdf": b"occupied", "3.pdf": b"last"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_directory_target_is_not_used_as_a_container(self):
        target = self.work / "1.pdf"
        target.mkdir()
        (target / "canary").write_bytes(b"nested")
        (self.work / "a.pdf").write_bytes(b"source")
        result = self.run_script()
        self.assertTrue(target.is_dir(), result.stderr)
        self.assertEqual({p.name for p in target.iterdir()}, {"canary"})
        self.assertEqual((target / "canary").read_bytes(), b"nested")
        self.assertTrue((self.work / "a.pdf").is_file(), result.stderr)
        self.assertEqual((self.work / "a.pdf").read_bytes(), b"source")

    def test_existing_symlink_target_is_not_followed(self):
        target = self.work / "1.pdf"
        target.symlink_to(self.canary)
        (self.work / "a.pdf").write_bytes(b"source")
        result = self.run_script()
        self.assertTrue(target.is_symlink(), result.stderr)
        self.assertTrue((self.work / "a.pdf").is_file(), result.stderr)
        self.assertEqual((self.work / "a.pdf").read_bytes(), b"source")
        self.assertEqual(self.canary.read_bytes(), b"do not change\n")

    def test_empty_and_hidden_only_directories_are_untouched(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.work.iterdir()), [])
        (self.work / ".private").write_bytes(b"hidden")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in self.work.iterdir()}, {".private": b"hidden"})


if __name__ == "__main__":
    unittest.main()
