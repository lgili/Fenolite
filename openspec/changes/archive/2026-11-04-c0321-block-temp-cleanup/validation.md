# Cleanup validation

On 2026-11-01, against public parent
`96d687d18450f429bcc57b60087f9e6f43dfb707` with this bounded change:

- Before the implementation fix, all five new regressions failed. Four use
  actual temporary trees and reject deleting the current directory or its
  ancestor, across successful and exceptional bodies. The fifth runs the
  actual authored usage, golden and test conventions under the same guard.
- After the fix, `uv run pytest tests/unit/blocks/test_runner.py -q` passed
  all 25 tests. The original authored exception survives cleanup; import,
  arguments, random state and bytecode settings are restored.
- `uv run fenolite blocks test --json` exited 0: all five shipped usages
  passed, all five goldens were equal, all 16 authored tests passed, and
  there were no issues.
- The neighboring CLI, starter and load proofs passed all 19 tests.
- Repository lint and formatting passed; `pyright src` reported zero errors,
  warnings or information diagnostics. The residue scan found zero hits;
  strict OpenSpec validation reported this change valid without warnings.

The guard reproduces Windows directory-lock semantics on the local Linux
host. Actual Windows and required published-head CI remain open in task 2.2.
The historical Windows job on the parent remains a failure; it is not
reclassified by these local proofs. No model, schema, public argument,
dependency, golden or native output baseline changes.
