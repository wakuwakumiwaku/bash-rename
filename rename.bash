#!/usr/bin/env bash

# Keep failures from enumeration and from any rename visible to the caller.
set -o pipefail
printf '%s\0' * | sort -z -V | {
    n=0
    status=0
    while IFS= read -r -d '' f; do
        [[ -f "./$f" && ! -L "./$f" ]] || continue
        [[ "./$f" -ef "${BASH_SOURCE[0]}" ]] && continue
        n=$((n + 1))
        # A no-clobber skip is not an I/O failure (GNU mv versions differ in
        # their exit status for -n skips). Keep -nT for races after this check.
        [[ -e "./$n.pdf" || -L "./$n.pdf" ]] && continue
        if ! mv -nT -- "./$f" "./$n.pdf"; then
            status=1
        fi
    done
    exit "$status"
}