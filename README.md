Rename visible regular files in the current directory to `1.pdf`, `2.pdf`, and so on, using the existing natural/version order (`ls -v`), not creation time. Existing destinations are never overwritten. Directories, symlinks, hidden files and the running script are skipped without consuming a number.

Run with `bash /path/to/rename.bash` from the directory containing the files. Requires Bash and GNU coreutils (`sort -z -V` and `mv -nT`). Filenames may contain whitespace, newlines, backslashes or leading dashes. An occupied destination is skipped; its number is not reused.

A failed rename or failed sorting command exits nonzero, even if a later entry is
skipped or renamed successfully. The entire sorted list must be produced successfully before any rename starts; even a sorter that emits partial output and then fails leaves all files untouched. Processing continues after individual rename
failures; completed renames are not rolled back. Occupied destinations still count
as ordinary skips, not errors.

Regression tests: `python3 -m unittest discover -s tests -v`.
