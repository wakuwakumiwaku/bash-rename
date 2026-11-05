"""Failed enumeration must not publish a partially renamed directory."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "rename.bash"
BASH = shutil.which("bash")
SORT = shutil.which("sort")
assert BASH is not None and SORT is not None, "Bash and GNU sort are required"


class SortPreflightTests(unittest.TestCase):
    def test_partial_sort_output_never_reaches_mv(self):
        for partial in (False, True):
            with self.subTest(partial=partial), tempfile.TemporaryDirectory(prefix="rename-sort-") as temp:
                root = Path(temp)
                work, tools = root / "work", root / "bin"
                work.mkdir()
                tools.mkdir()
                names = ["a\nname.txt", "z.txt"]
                before = {name: name.encode() for name in names}
                for name, data in before.items():
                    (work / name).write_bytes(data)
                sorter = tools / "sort"
                output = "printf 'a\\nname.txt\\0'" if partial else f"{shlex.quote(SORT)} \"$@\""
                sorter.write_text("#!/bin/sh\n" + output + "\nexit 73\n")
                sorter.chmod(0o700)
                mover = tools / "mv"
                mover.write_text("#!/bin/sh\nprintf 'mv invoked despite sorter failure\\n' >&2\nexit 91\n")
                mover.chmod(0o700)
                env = {"PATH": str(tools), "HOME": str(root), "TMPDIR": str(root), "LC_ALL": "C"}
                result = subprocess.run([BASH, str(SCRIPT)], cwd=work, env=env,
                                        capture_output=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"mv invoked", result.stderr, "sort failure must abort before any rename")
                self.assertEqual({p.name: p.read_bytes() for p in work.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
