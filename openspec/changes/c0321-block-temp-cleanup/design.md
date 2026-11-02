## Context

Observed 2026-11-01 on exact public commit
`96d687d18450f429bcc57b60087f9e6f43dfb707`, CI run 41359100272, Windows job
125005408770. Lint, format, types and residue passed; the public shipped-block
step failed with ten WinError 32 findings while the authored assertions themselves
passed. No successful Windows cleanup is claimed by that run.

## Decisions

Decided 2026-11-01: nest standard-library `contextlib.chdir` inside the existing
temporary-directory context. Reverse context exit order restores the caller's
working directory before deletion, on successful and exceptional exits. The
package already requires Python 3.11 or later.

Decided 2026-11-01: preserve the outer import/argv/bytecode/random-state cleanup.
Use an actual temporary directory with a cleanup guard that rejects deletion of
the active directory on every host. Test both body success and an original body
exception, plus the real public block runner. This is a lifecycle proof, not a
replacement for the exact Windows CI job.

## Evidence

The failing public CI log and repository implementation establish the internal
defect. Tests use only authored fixture code. No external format fact, copied
parser or third-party CAD fixture is introduced.
