#!/usr/bin/env bash

n=0
while IFS= read -r -d '' f; do
    [[ -f "./$f" && ! -L "./$f" ]] || continue
    [[ "./$f" -ef "${BASH_SOURCE[0]}" ]] && continue
    n=$((n + 1))
    mv -nT -- "./$f" "./$n.pdf"
done < <(printf '%s\0' * | sort -z -V)