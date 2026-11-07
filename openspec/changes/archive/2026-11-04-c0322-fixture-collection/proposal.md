## Why

The exact `96d687d1` Linux Python 3.13 CI unit job collected the authored block self-test payload
under `tests/data/blocks/lib/tests`. Pytest's assertion rewriting wrote bytecode beside that fixture.
The unchanged manifest validator then correctly rejected the undeclared file, and the block-runner
test copied the already-contaminated fixture and observed its cache. Local runs with bytecode disabled
did not expose this collection mistake.

## What changes

Exclude the one authored block-fixture test file from automatic repository pytest collection.
Keep explicitly running its self-tests through the actual block runner. Add real subprocess proofs
with ordinary bytecode enabled, neighboring collection controls, explicit runner execution and the
unchanged manifest rejection of leaked bytecode.

## Non-goals

No blanket data/example ignore, manifest allowance for caches, bytecode-suppression environment,
runner cleanup workaround, runtime/model/schema change, external tool or new dependency is added.

## Evidence level required

Repository pytest/runner behavior is proved with local Python 3.12/3.13 subprocesses. Required exact
published-head CI and the coordinator's complete gate remain open until their actual receipts exist.
No physical/native evidence label changes.
