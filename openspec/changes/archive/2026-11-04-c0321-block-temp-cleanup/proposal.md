## Why

The Windows job of public CI run 41359100272 fails in `blocks test` before its
unit suite: every usage build and test-module cleanup reports WinError 32. The
runner tries to remove its temporary working directory before restoring the
caller's working directory. Linux permits the deletion and hid this lifecycle
error in the local proofs.

## What Changes

Exit the temporary working-directory context before deleting the temporary tree,
including when authored code raises. Preserve import, argument, bytecode and
random-state isolation. Add a host-independent Windows-style cleanup constraint
and rerun the actual public block runner.

## Capabilities

- Modified: `verification-loop`.

## Impact

Only block-test isolation and its regression proofs change. No model field,
public flag, runtime dependency, native output, golden or verification level is
added. Actual Windows CI remains required after publication.
