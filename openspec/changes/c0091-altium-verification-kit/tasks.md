## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-verification`, `verification-evidence` and `cli-contract` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code; and which of c0084 to c0090 are archived: the steps of a group whose change is not archived are written and marked `pending`, and the first real run waits for all of them. Proof: `openspec validate c0091-altium-verification-kit --strict --no-interactive` passes.

## 1. Registers and page

- [ ] 1.1 Add the five rows to `docs/hypotheses.md`; write the skeleton of `docs/altium-kit.md` (what the kit is, what a run proves, what a saved file may contain) and `docs/evidence/altium-kit/README.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_repo_layout.py`.

## 2. Kit build

- [ ] 2.1 Author the five sample scripts under `examples/kit/` and write `manifest.py` (scenarios of "Verification kit contents"). Proof: `uv run pytest tests/unit/verify/kit/test_manifest.py tests/residue`; `uv run pyright src`.
- [ ] 2.2 Write `steps.py` with the groups K1 to K9 and the generated `STEPS.md` (scenario "Steps and register agree"); set the settling test of `H-A-WRITE-*` and `H-A-PH-*` to their steps. Proof: `uv run pytest tests/unit/verify/kit/test_steps.py tests/unit/test_hypotheses_register.py`.
- [ ] 2.3 Register the pages of Altium's public scripting documentation that the script relies on (one source row per page, read for facts), list every call with its source in `SCRIPT_CALLS` and in `docs/altium-kit.md`, then write `script.py` and mark the steps it performs `scripted` (scenarios of "Kit script"). A call without a public page is not used and its step stays manual; say which under this task. Proof: `uv run pytest tests/unit/verify/kit/test_script.py tests/unit/verify/kit/test_steps.py tests/unit/test_provenance.py`.

## 3. Kit verify

- [ ] 3.1 Write `results.py`: manifest check, form schema, re-saved documents, the kit profile and the privacy scan (scenarios of "Kit result verification"), with the simulated run. Proof: `uv run pytest tests/unit/verify/kit/test_results.py`.

## 4. Record and label

- [ ] 4.1 Write `record.py` and `stale_rows` (scenarios of "Kit run record"). Proof: `uv run pytest tests/unit/verify/kit/test_record.py`.
- [ ] 4.2 Add the kit label rule to the register test (scenarios of "Kit label rows"). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify`.

## 5. Command and documentation

- [ ] 5.1 Write `cmd_kit.py` (scenarios of "Kit command"). Proof: `uv run pytest tests/unit/cli/test_kit_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
- [ ] 5.2 Finish `docs/altium-kit.md` with the steps, the time each group takes, and how to publish the archive; link it from `README.md` and `docs/evidence/README.md`. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py`.
- [ ] 5.3 Hand the kit to the maintainer for a first run on his machine (the design, "Decisions", lists the groups). The run is recorded by c0092's task, or here when c0084 to c0090 are archived: `fenolite kit verify`, `fenolite kit record`, commit the record. Proof: `fenolite kit status --json` lists the run and no stale row.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0091-altium-verification-kit --strict --no-interactive` passes; `gh pr checks` shows `unit` passing.
- [ ] 6.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite kit` builds the Altium verification kit, checks the files a run leaves and records the run: the base of the label `ALTIUM-VERIFIED(kit)`". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
