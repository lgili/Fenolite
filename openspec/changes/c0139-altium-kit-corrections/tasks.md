## 0. Entry check

- [x] 0.1 Read `openspec list`, c0091's active deltas and `docs/evidence/altium-kit/`. Write under this task, with the date: whether c0091 is archived (then copy the five requirements from the living spec instead), whether another active change holds a delta of them, and whether a run record exists that a new kit digest could make stale. Proof: `openspec validate c0139-altium-kit-corrections --strict --no-interactive`.

## 1. Privacy first

- [x] 1.1 Write the tests of an absolute path in a saved document, of every shape of path, of UTF-16 at both alignments and of what is not a path; then `DRIVE_PATH`, `SHARE_PATH`, `POSIX_PATH` and the kind `absolute-path` in `privacy_scan`; refuse such a string in `record_problems` (scenario "A path on another drive"). Proof: `uv run pytest tests/unit/verify/kit/test_results.py tests/unit/verify/kit/test_record.py -q`.
  - 2026-10-08: done first and committed on its own before the rest. The tests failed before the scan was changed (4 of 6). On the returned kit folder the scan of `results/` went from 0 findings to 1: a path from a drive letter, in 8-bit text, in the value of the key `FILENAME` of a PCB document; a second, cruder search found nothing more.

## 2. The kit's steps and checks

- [x] 2.1 Accept a sample's project file that the tool saved again with the same documents (scenarios "A project file that the tool saved again" and "A project file with another list of documents"); `kit_resaved` in the result and in the run record; the issue `kit.project-resaved` with its explanation. Proof: `uv run pytest tests/unit/verify/kit tests/unit/cli/test_kit_cmd.py tests/unit/cli/test_explain_cmd.py -q`.
  - 2026-10-08: done. The returned project file starts with a UTF-8 byte-order mark, which `project_documents` skips. On the returned kit folder: before, 1 kit problem and 10 of 10 steps of `flat` failed for the manifest; after, 0 kit problems, 1 file in `resaved`, and the ten steps are judged on their own results (3 pass, 7 are skipped for an absent file or value, none fails).
- [x] 2.2 Print expected values by their type and report an expected value of another type (scenario "Expected values by their type"). Proof: `uv run pytest tests/unit/verify/kit/test_steps.py -q`.
  - 2026-10-08: done; every value type is tested with 0, 1, true, false and texts that read like them.
- [x] 2.3 Take `H-A-SCH-UPDATE` from step K9.1 (scenario "The update step"). Proof: `uv run pytest tests/unit/verify/kit/test_steps.py tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-08: done. The register does not change: the test cells of both rows name author-report steps, and no kit step.
- [x] 2.4 Name the PCB document in step K5.1; tell a result file by its content and name a file of another kind (scenario "A document of another kind"). Proof: `uv run pytest tests/unit/verify/kit/test_results.py tests/unit/cli/test_kit_cmd.py -q`.
  - 2026-10-08: done. Found on the returned folder: the schematic was saved under its own name, so the step's file was absent and the step was `skipped`. A step whose file is absent while its folder holds a file of the same name with another ending that no step asks for now fails and names that file.
- [x] 2.5 Say in the script's header and in `script.READ_AS` which version the pages are for and where the script runs first (scenario "The version of the pages and of the first run"). Proof: `uv run pytest tests/unit/verify/kit/test_script.py -q`.
  - 2026-10-08: done from the register rows S-0501 to S-0504; the pages were not read again.

## 3. Closing

- [x] 3.1 Update `docs/altium-kit.md`, `docs/cli-contract.md`, `CHANGELOG.md` and `docs/roadmap.md`. Proof: `uv run pytest tests/consistency tests/unit/cli/test_kit_cmd.py -q`.
  - 2026-10-08: done.
- [x] 3.2 Build the kit twice and compare the digests; run the simulated run through `kit verify` and `kit record --dry-run`. Proof: equal digests; exit codes as the tests state them.
  - 2026-10-08: two builds give `93d28676…` (42 files, equal folders); the digest at `f17b03e9` was `4ce65198…`. The simulated run through the command: `kit verify` exits 5 with 31 steps passed and K6.1 failed, as before this change (Fenolite writes every polygon unpoured, so its own board cannot stand in for a repoured one); `kit record --dry-run` refuses the synthetic run and plans the archive and the record for the run whose form does not say synthetic.
- [x] 3.3 Run the residue and the fast suites, and the unit suite on Python 3.11. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check-fast` passes; `openspec validate --all --strict --no-interactive` passes.
  - 2026-10-08: see the hand-over report for the counts of each run.
- [x] 3.4 The full `make check` and the CI run on three operating systems. Proof: `make check` passes; `gh pr checks` shows `unit` passing.
  - Open: left to the coordinator, who runs the one full suite at the merge.
  - 2026-10-09: closed by the full `make check` of 2026-10-08 on the release branch (c0154 task 4.3: exit 0, ruff clean, 1772 files formatted, pyright 0 errors, residue 0 hits with 11 waivers, `13828 passed, 2374 skipped` on Python 3.11.15; the residue and manifest tests are part of it) and the CI runs of `release-0.4.0` and its pull request #17, every job green (`unit` on Ubuntu with 3.11, 3.12 and 3.13, on macOS and on Windows, `kicad-9`, `kicad-10`, `routing` on KiCad 9 and 10, `wheel`, `dco`): 37836186018 (`32a19b3`), 37860490303 and 37860486308 (`acba81b`, whose tree is the released `591dc00` and `dev` at `a8732fc`); `openspec validate --all --strict --no-interactive` on 2026-10-09 reports only the known errors (c0084, c0085 twice, c0086, c0128) and long-requirement warnings, none for this change.
