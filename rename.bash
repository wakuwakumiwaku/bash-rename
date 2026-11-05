#!/usr/bin/env bash

# Keep failures from enumeration and from any rename visible to the caller.
set -o pipefail
# An empty record cannot be a filename. Send it only after a successful sort,
# then buffer the complete list before making any filesystem changes.
printf '%s\0' * | { sort -z -V && printf '\0'; } | {
    files=()
    complete=0
    while IFS= read -r -d '' f; do
        if [[ -z "$f" ]]; then
            complete=1
            break
        fi
        files+=("$f")
    done
    [[ $complete == 1 ]] || exit 1

    n=0
    status=0
    for f in "${files[@]}"; do
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