## Why

The public history scan reports the path component of a public HTTPS reference as
an absolute user directory. This blocks the history proof despite the blob
containing a URL rather than a local path.

## What Changes

Recognize HTTP(S) path components when applying the existing absolute-user-path
pattern. Keep filesystem paths, file URIs, query/fragment values, private tokens
and the other residue patterns subject to their existing checks. Add authored
regressions and inspect the previously reported historical blob again.

## Capabilities

- Modified: `residue-scan`.

## Impact

The residue scanner uses the standard library only. No public command, pattern
identifier, waiver, dependency, history rewrite or box implementation is added.
