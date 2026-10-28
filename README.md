Rename visible regular files in the current directory to `1.pdf`, `2.pdf`, and so on, using the existing natural/version order (`ls -v`), not creation time. Existing destinations are never overwritten. Directories, symlinks, hidden files and the running script are skipped without consuming a number.

Run with `bash /path/to/rename.bash` from the directory containing the files. Requires Bash and GNU coreutils (`sort -z -V` and `mv -nT`). Filenames may contain whitespace, newlines, backslashes or leading dashes. An occupied destination is skipped; its number is not reused.

Regression tests: `python3 tests/test_rename.py -v`.
