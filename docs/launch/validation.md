# Presentation validation — 2026-10-26

## Scope

Change `c0228-public-presentation`, isolated from ongoing library work, based on released tag `v0.5.0`
(commit `3a0bfb7d`). Published 0.5.0 files, tag and commit history are unchanged. Development is opened at
`0.6.0.dev0` so Unreleased can record new work without weakening the existing release guard.

## Measured results

- Strict OpenSpec validation passed.
- Combined README/agent-loop, assembly-guide, presentation, package metadata, release-record and provenance checks: **88 passed**.
- Historical Altium fixture file and corpus-manifest checks: **63 passed**; no fixture changed.
- Provenance checks after adding the truthful release/presentation audit row: **8 passed**.
- `uv build` built a source distribution and a wheel from it for `0.6.0.dev0`.
- PNGs were visually inspected. Social preview is 1280 × 640, below 1 MB. FFmpeg reports four GIF frames,
  960 × 600, exactly twenty seconds. The capture browser reported zero page errors.
- Authored example, starter and fixture inputs are byte-for-byte unchanged against the release tag.
- The README was rendered and inspected in a local HTML preview. Remote image URLs become available
  when these files reach `main`; the local preview uses local images.

## Published-package first-use check

In a fresh virtual environment, installed `fenolite==0.5.0` from PyPI. Python 3.13, no runtime package
dependencies installed beside Fenolite. Each command below exited zero:

```console
fenolite --version
fenolite capabilities --brief --json
fenolite init blink --confirm --json
fenolite build blink/design.py --out blink/build --confirm --json
fenolite view blink/build --export blink/review.html --confirm --json
fenolite route blink/build --router direct --confirm --json
```

The live viewer was started with `--serve --no-browser` on a dedicated loopback port. HTTP returned 200
and the actual Fenolite viewer page. The test server was stopped. No CAD verification, fill, fabrication export or external routing was performed. The capabilities command
may probe installed tool versions; this does not verify a design. No fabrication/engineering acceptance is claimed.

## Existing main CI diagnosis

The [main run 40248595381](https://github.com/lgili/Fenolite/actions/runs/40248595381), on released merge
`3a0bfb7d`, has five failed unit jobs. The inspected Ubuntu/Python 3.13 job reports one failure:
`test_session_log_covers_every_week_of_format_work`, missing `2026-W44` from `LEGAL-ANNEX.md`.
Its result is 1 failed, 14127 passed, 3514 skipped. The correction records the actual release/presentation
audit, points to the pre-existing format-work sessions and leaves the weekly guard intact. Local
provenance checks pass. This is not a claim that remote CI has rerun or passed this change.

## Local quick-gate reconciliation

The first `make check-fast` run completed: **8 failed, 13941 passed, 74 skipped**. Seven failures exposed
README contracts: the executable ten-command loop, release/installation wording, negative checks and
assembly-guide link. They were restored, with the longer loop in a collapsed section; focused checks
now pass. The remaining failure was an older full-history fixture guard: c0166 commit `5a75bc73` had
intentionally added exactly two net-naming flags to the authored hierarchy project. The guard now
asserts exactly those additions and preserves all other historical byte comparisons. Its focused tests
and the fixture manifest pass, without changing the fixture.

The final `make check-fast` rerun passed: **13950 passed, 74 skipped in 372.53 seconds**
(`PYTEST_PARALLEL="-n 8 --dist worksteal"`). Ruff, formatting, both guide generators, Pyright and the residue
scan passed. Skips include optional geometry dependencies and the native Altium saved-document check;
there was no interrupted run reported as a pass. Complete validation remains a CI task.

## Pending publication

No commit, push, merge, GitHub setting, GitHub Release or social announcement has been made by this
change. Complete CI must run on the reviewed commit before merge/archive. The launch checklist remains
in [README.md](README.md). The package metadata and README changes reach PyPI with a future package
release; published 0.5.0 artifacts are not replaced.

## Audit follow-up — 2026-10-27

The uncommitted draft was reallocated from c0197-public-presentation to c0208-public-presentation
to avoid the separate c0197-router-input. The original media and release provenance remain unchanged.
The optional MCP SDK was incorrectly described as providing a server in 0.5; that claim is corrected,
with the separate implementation in PR #20 identified as awaiting integration/release. The catalog
is linked from the documentation index, and the routed image now accompanies the routing step.
Strict validation and 30 presentation/agent-skill tests passed. The follow-up `make check-fast` passed:
13950 tests passed, 74 skipped, 343.69 seconds. Complete CI still waits for an authorized commit/push.

On 2026-10-28 the still-uncommitted draft moved again to c0228-public-presentation after the committed c0208-copper-tidy collision. All earlier validation belongs to the same presentation implementation.
