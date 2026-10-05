# Isolate the worksheet version oracle

## Why

CI run 37294184733 at 2e82ee6 failed only in `test_worksheet_boundary`: the future-version drawing sheet produced an SVG without the expected rejection diagnostics. The process also reported an invalid shared KiCad lock. A parallel probe in the pinned KiCad 10.0.6 container as UID 1001 reproduced missing rejection diagnostics with an unwritable default configuration directory. The CI job runs as root; UID 1001 is an additional environment stress case, not an exact reproduction of that job. The exact configuration state of the failed CI process is unknown.

## What changes

Run each worksheet boundary probe through the existing `KicadCli` executor, with fresh working copies, a private configuration directory and the C locale. Give every probe its own home, XDG cache/data directories and OS temporary directory so instance locks are not shared. Require successful export output as well as the existing strict rejection diagnostics. No version constant, runtime behavior or skip is changed.

## Impact

Only the worksheet oracle test and its documentation change. The commit stays local on dev; the user will batch the next CI run with other commits.
