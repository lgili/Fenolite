## Exact failure

Run `41359100272`, job `125005408687`, exact source
`96d687d18450f429bcc57b60087f9e6f43dfb707`, Linux Python 3.13: the unit job failed 25 tests. Two
additional failures beyond the local 23 were the strict data-manifest check and block-runner state
restoration check. The emitted path was the fixture's `__pycache__/test_divider.cpython-313-pytest-9.1.1.pyc`.
Do not accept that file, hide it from the manifest validator or use a no-bytecode environment as proof.

## Payload inventory — Decided 2026-11-01

The maintainer delegated recommended fixes. The exact frozen tree has three test-shaped Python files
under `examples/` and `tests/data/`:

| file | role | collection decision |
|---|---|---|
| `tests/data/blocks/lib/tests/test_divider.py` | declared CC0 authored block self-test fixture, executed by `run_block_tests` | ignore only this exact file during automatic repository collection |
| `examples/blocks/tests/test_divider.py` | declared CC0 block-example self-test, executed through the block convention | leave unchanged; examples are outside default repository `testpaths` |
| `examples/testing/test_design.py` | declared regular pytest tutorial with explicit example proof | leave unchanged and explicitly runnable |

`tests/conftest.py` owns the collection boundary through a relative `collect_ignore` entry for
`data/blocks/lib/tests/test_divider.py`. No glob for all data/examples is justified. Nearby ordinary test files remain
collectable. The existing runtime runner already isolates bytecode and restores the caller's state;
the source fixture must remain clean before it is copied into that runner.

## Implementation and proof

Add `tests/unit/test_fixture_collection.py`, separate from the Windows-owned runner test file.
A subprocess uses copies of the actual pytest configuration, conftest/resource helper and authored
block fixture. Remove inherited `PYTHONDONTWRITEBYTECODE` and `PYTHONPYCACHEPREFIX`, assert bytecode
is enabled, and prove ordinary/neighboring public tests collect and write their normal caches while
the payload neither collects nor gains a cache. This control must fail on the old collection policy.

A second subprocess calls the actual block runner with bytecode enabled before/after the call. The
authored self-test must pass; a deliberately failing appended function must be observed, proving the
runner executes the payload rather than skips it. A separate manifest control injects an undeclared
cache file and requires the existing validator to reject it. Do not edit that validator or runtime code.

The own offline environments and test temporary folders stay separate from the frozen source. No
whole suite or push is performed here. The exact CI gate remains coordinator-owned.
