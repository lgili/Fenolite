## 1. Scope and entry

- [x] 1.1 Inspect v0.5.0, README, viewer, release record and repository metadata; validate this change strictly.

  - 2026-10-26: inspected release tag 3a0bfb7d, PyPI 0.5.0, empty GitHub description/topics and authored viewer fixtures. Strict OpenSpec validation passed before implementation.

## 2. First experience and media

- [x] 2.1 Add and execute a quickstart using the released CLI, authored examples and reviewed write plans; document prerequisites and expected outputs.
- [x] 2.2 Add a repeatable capture recipe, actual screenshots, animated viewer demo and original social card; inspect images and record provenance.

## 3. Public presentation

- [x] 3.0 Open the post-release development version as 0.6.0.dev0 in the core and alias, preserving published 0.5.0. Proof: package metadata and release-record tests. The release guard requires an empty Unreleased only while the running version equals the published release.

- [x] 3.1 Rewrite README and documentation landing page, update package metadata, and check all local links and visible support claims.
- [x] 3.2 Prepare bilingual announcement drafts, release highlights, exact repository settings and publication instructions; leave publishing pending review.

## 4. Validation

- [x] 4.1b Repair the historical fixture guard exposed by this full-history checkout: commit 5a75bc73 deliberately added only AllowPortNetNames=0 and AllowSheetEntryNetNames=0 to hier/altium_hier.PrjPcb. Assert exactly those two additions over the c0085 baseline and preserve every other byte comparison; change no fixture. Proof: the failed historical fixture case, affected file tests and manifest checks.

- [x] 4.1a Preserve the executable ten-command README loop in a collapsed section, the released status and installation guards, and the assembly guide link. Adjust only the negative test's release-link spelling to its new URL. Proof: agent-skill, assembly-guide and public-presentation tests.

- [x] 4.0 Reconcile the missing 2026-W44 release-provenance row reported by main CI 40248595381. Record the actual 2026-10-26 release/presentation audit and the already documented origins of format work carried by the release merge, without inventing a new format-research session or changing the weekly guard. Proof: tests/unit/test_provenance.py.

- [x] 4.1 Add focused documentation/asset checks, update Unreleased changelog and pass focused proofs.
- [x] 4.2 Run make check-fast, strict OpenSpec validation and diff checks. Record results; full CI and publication remain pending.

### Focused proof record, 2026-10-26

- 2.1: reviewed CLI plans built/routed the starter and exported the viewer. A separate fresh environment installed PyPI 0.5.0 and passed init, build, direct route and HTML export; the live viewer returned HTTP 200. No CAD verification or fabrication export ran (capabilities probes installed tool versions).
- 2.2: Chromium 148.0.7778.96 reported zero page errors; four 960 by 600 frames make a twenty-second GIF. The social PNG is 1280 by 640 below 1 MB. Inspected PNGs and rendered README; design inputs unchanged against v0.5.0. Sources and reproduction in docs/media/README.md.
- 3.0/3.1/3.2/4.1: package, release-record and presentation checks passed 59 tests before adding the validation-report link; package source distribution and wheel build passed. No history or published artifact changed. Launch drafts and settings remain unexecuted.
- 4.0: inspected failed main CI 40248595381; its Ubuntu/Python 3.13 log reports only the missing 2026-W44 session row. Added a truthful release/presentation audit, retaining original format-session attribution and the weekly guard. All 8 provenance tests passed.

- 4.1a: agent-skill, assembly-guide, presentation, package, release and provenance checks passed together: 88 tests. The executable loop and existing negative guards remain active.
- 4.1b: historical fixture file tests and manifest checks passed: 63 tests. No fixture changed.

- 4.2: final make check-fast passed with 13950 passed, 74 skipped in 372.53 seconds (8 workers, worksteal). Ruff, format, guide generators, Pyright, residue, strict OpenSpec and git diff --check passed. The initial completed run had 8 failures; corrections and focused proofs are recorded in docs/launch/validation.md.

- [x] 4.3 After authorization to commit and publish the branch, run complete CI on that exact commit; review required jobs before merge/archive. GitHub settings, release publication and announcements follow the separate launch checklist.

## 5. Audit corrections, 2026-10-27

- [x] 5.1 Reallocate this uncommitted draft to c0208-public-presentation because c0197-router-input is already published on another branch. Keep prior proof records and record the alias; update only this draft's references. Proof: strict OpenSpec validation and presentation checks.
- [x] 5.2 Correct the MCP installation claim for release 0.5, link the existing catalog from the documentation index, and place the routed starter screenshot beside its routing step. Proof: inspect released capabilities, presentation/agent-skill checks, and rendered diff review.
- [x] 5.3 Rerun make check-fast after these edits and preserve full CI as pending.

- 5.1/5.2 proof, 2026-10-27: strict validation and 30 presentation/agent-skill tests passed. Published-version parser has no mcp command; no server install is promised. Catalog links resolve, and the routed screenshot accompanies the routing step.

- 5.3 proof, 2026-10-27: make check-fast passed (13950 passed, 74 skipped, 343.69s); complete CI remains pending commit/push authorization.

## 6. Allocation reconciliation

- [x] 6.1 Rename this uncommitted draft and branch to c0228-public-presentation after the committed c0208-copper-tidy collision, preserve previous proof/allocation records, and update current references. Proof: strict OpenSpec, presentation/release-record checks and diff checks.

## 7. Integration CI findings

- [x] 7.1 Read every public-presentation text fixture explicitly as UTF-8 after Windows CI exposed locale-dependent decoding of the Portuguese launch heading. Preserve content assertions and public document bytes. Proof: focused presentation tests with implicit text decoding rejected, format/lint checks and make check-fast.
  - 2026-10-29: Windows job 122940177289 of CI 40723421798 exposed the implicit decoding. All 14 presentation tests passed with a temporary Path.read_text guard rejecting implicit decoding of repository Markdown/TOML. Ruff and format passed; make check-fast passed 14406 with 37 skipped in 425.83s. No public document or assertion was changed.

- Allocation follow-up, 2026-10-28: the draft moved from c0208-public-presentation to c0228-public-presentation. Earlier proofs retain their former allocation; c0197-public-presentation is the original alias. No implementation or media bytes changed.
- 6.1 proof, 2026-10-28: strict c0228 validation, 63 presentation/release-record checks and diff checks passed. The branch is now codex/c0228-public-presentation; the existing worktree path is retained. No commit or publication occurred.

- Final integration allocation, 2026-10-28: this draft is c0228-public-presentation, formerly c0216-public-presentation (earlier c0208/c0197 aliases). Earlier proof records refer to the same presentation implementation. Publication and squash integration were authorized by the maintainer; final CI still gates archival/integration.

- Implementation CI proof, 2026-10-29: GitHub run 40743806475 completed successfully with all 13 jobs on 8c2fa27048cf36543b93ee01c873aec0673f5d7d (https://github.com/lgili/Fenolite/actions/runs/40743806475). That revision tested this implementation as `c0228-public-presentation`; its final identity is `c0237-public-presentation` after the fetched-ref collision audit. Prior proof IDs are retained as aliases. The final archived revision has its own CI gate before dev advances.
