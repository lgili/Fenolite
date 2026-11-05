## 1. Hypotheses and kit phase A

Tasks 1.1 to 3.4 are tasks 6.1 to 6.7 of c0175 (`openspec/changes/c0175-board-engineering-tools/`), moved
here on 2026-10-29 and renumbered: 6.1 is 1.1, 6.2 is 1.2, 6.3 is 2.1, 6.4 to 6.7 are 3.1 to 3.4.

- [x] 1.1 Write the hypotheses of the edit session and of the integrity rules into `docs/hypotheses.md`, each with its kit case. Build kit phase A, with documents authored for Fenolite and the cases to open, save and reopen in Altium. No write code before this task is ticked. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_verification_docs.py -q`.
  - 2026-10-29, on the branch of `1559f1b`: 21 rows, `H-A-EDIT-*` (14) and `H-A-INTEG-*` (7), each `INFERRED` with its kit request (design, Decision 3); `H-A-INTEG-SUBPOLY` records the public evidence against it (8 of 81 polygons hold numbers with gaps). Part J of `docs/evidence/altium-edit.md`: phase A cases J1 to J22 and phase B cases J23 to J33, each with its expected outcome. The board `tests/data/altium_edit/edit.py` (authored, declared in `tests/data/MANIFEST.toml`) and the steps in Brazilian Portuguese (`tests/data/altium_edit/kit/README-phase-a.md`); `tests/unit/backends/altium/test_part_j.py -k phase_a` builds `board/`, `expected.md`, `README.md`, `PART-J.md` and `SHA256SUMS`, the same bytes on every run. No module of `backends/altium/edit/` exists. The proof passes (52 tests with `test_part_j.py`); `uv run python tools/gen_evidence_matrix.py --check` passes.
- [ ] 1.2 **Maintainer, in Altium Designer.** Build phase A with `FENOLITE_ALTIUM_PART_J=~/fenolite-altium-checks/session-7/J-edit uv run pytest tests/unit/backends/altium/test_part_j.py -k phase_a`, run J1 to J22 and send back the folder, the version, the date and the SHA-256 of each saved file. Record the report under "Reports" of `docs/evidence/altium-edit.md` in the form of the native acceptance inventory, register its source, and write what each case measured into the result of its rows. OPEN until Altium was run; nothing is marked `ALTIUM-VERIFIED` by it. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j tests/unit/test_hypotheses_register.py -q`.
  - 2026-11-04 (S-1577): a Claude agent ran J1 to J22 at the maintainer's request in the actual Altium Designer 24.5.2.23 of the maintainer's VM, on a kit built at `7074a68e`. All 21 files were saved and recorded under "Reports" of `docs/evidence/altium-edit.md`, with their SHA-256 and record diffs, and the thirteen phase A rows hold the observation. Six cases used a scripted edit, J13 placed the project's SchLib part, and the run is an agent run under the approved 24.5 scope, so no level changes and the task stays open for the maintainer's report.
  - 2026-11-04 evening, S-1582: at the maintainer's second request the agent tried to redo J7, J9, J14, J18, J19 and J21 through the Properties panel. The Properties panel could not be reached through UI Automation (the dock held the Components panel, the Properties tab lay off screen, and View » Panels » Properties and F11 did not bring it back). No case was redone and nothing was saved. J12 was already a UI case. The task stays open for the maintainer.

## 2. Integrity check

- [x] 2.1 Add the integrity check stage, with warnings for unconfirmed rules (scenarios "A gap in polygon sub-indices", "Two pads with one unique id", "Two layer fields that disagree"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_integrity.py -q`.
  - 2026-11-04: `backends/altium/edit/integrity.py`, the stage `altium.integrity` (opt-in, `checks/documents.py`, through the protocol `backends.base.DocumentIntegrity`) and the codes in `explain`. Facts from the phase A files saved by an agent run on 2026-11-04 (S-1420, `INFERRED`; its report S-1316 is on the unmerged branch `claude/altium-pending-rounds-5d4baa`), not from task 1.2. No finding on the 18 saved PCB documents J01 to J17 nor on the kit board. Proof: `tests/unit/backends/altium/edit/test_integrity.py` 11 passed, `test_stage.py` 4 passed.

## 3. Edit session

- [x] 3.1 Add the session with `delete`, `move`, `rotate` and `set_property`, the assertions, the cloning and the index upkeep, behind a gate that is off by default (scenarios "A move written and read back", "A move refused on a wrong old value", "No record to clone from", "A deleted component leaves no index behind", "An operation behind its gate"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_session.py -q`.
  - 2026-11-04: `backends/altium/edit/{records,state,ops,session}.py`; `edit.GATES` all off. Proof: `tests/unit/backends/altium/edit/test_session.py` 10 passed.
- [x] 3.2 Add the commit gates (scenario "An undeclared connectivity change"). Proof: `uv run pytest tests/unit/backends/altium/edit/test_commit.py -q`.
  - 2026-11-04: `session.verify` (strict read-back, stream and record diffs, `edit/connectivity.py`, new integrity findings). Proof: `test_commit.py` 6 passed.
- [x] 3.3 Add `flip`, `clone`, `add_component`, `remap_layer` and `set_rule`, each behind its own gate. Proof: `uv run pytest tests/unit/backends/altium/edit -q`.
  - 2026-11-04: each behind its own gate in `edit.GATES`. Proof: `uv run pytest tests/unit/backends/altium/edit -q` passed (with `test_ops.py` 10 passed).
- [x] 3.4 Add the schematic session with the net-signature guard. Proof: `uv run pytest tests/unit/backends/altium/edit/test_schematic.py -q`.
  - 2026-11-04: `backends/altium/edit/schematic.py`, `SCHEMATIC_GATES` all off. Proof: `test_schematic.py` 5 passed.

## 4. Kit phase B

- [x] 4.1 Build phase B (`written/`, `faults/`, `expected-b.md`) from the files of task 1.2 with each gate forced on for the kit only. Proof: `uv run pytest tests/unit/backends/altium/test_part_j.py -k phase_b -q`.
  - 2026-11-04: `phase_b()` in `test_part_j.py` writes the nine PCB and three schematic documents of `written/` and the four faults of `faults/` (`tests/unit/backends/altium/edit/faults.py`), with `expected-b.md` and `SHA256SUMS`. With `FENOLITE_ALTIUM_PART_J_SAVED=<saved/board of phase A>` it starts from `J01-resave.PcbDoc` (`J16-repour.PcbDoc` for `subpoly-gap`), as J23 asks; run so on the agent's files of 2026-11-04, every written document read back strictly with no integrity finding. Without the variable it starts from the kit board (unit test only). Not written: `edit-library.PcbLib` (J25, no library session), the parameter faults (J29, J30: no parameter group in phase A) and the model faults (J31: the kit embeds no model). Proof: `test_part_j.py -k phase_b` 1 passed.
- [ ] 4.2 **Maintainer, in Altium Designer.** Run J23 to J33 and give the report; record it as task 1.2 does and set the rows `H-A-EDIT-KIT` and `H-A-INTEG-*`. Set an operation's gate only when its case passes. OPEN until Altium was run. Proof: `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j tests/unit/test_hypotheses_register.py -q`.
  - 2026-11-04 night (agent run, S-1588): OPEN. A Claude agent ran J23 to J32 at the maintainer's request in Altium 24.5.2.23 on the phase B kit built at `aa49b069` from the agent's phase A files. Seven of the nine PCB operations show as expected and survive a save: move, rotate, flip, set_property, delete, clone and add_component. `remap_layer` leaves the track on Mechanical 13: its record still holds 13 beside the new layer byte. `set_rule` is shown and saved with the `GENERICCLEARANCE` value, not the written `GAP`. J24 passes, with nets not compared. J26, J28: the faults open and save, and the findings stay. J27, J32: Altium renumbers the Pour Index and follows `V7_LAYER`, and the saved files give no finding. J25, J29–J31 are dropped. An agent run raises no level and sets no gate. See `docs/evidence/altium-edit.md`.

## 5. Teaching

- [x] 5.1 Add a tested line for the stage `altium.integrity` and for the session to the closest page of the agent guide; run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-11-04: `references/altium.md` names the stage and the edit gate, tested by `test_altium_teaches_the_integrity_stage_and_the_edit_gate`; `tools/gen_agent_guide.py` run. Proof: `tests/unit/agent` 177 passed, 1 failed (`test_pages_kicad.py::test_kicad_table_names_every_design_block`, `board-practice`, failing on the base commit too).

## 6. Closing

- [ ] 6.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch.
  - 2026-11-04, OPEN (exact blocker): `make check-fast` passed on the change's tree except one drift that was fixed in the same commit (`docs/cli-surface.json` regenerated: 22675 passed before the fix, 55 passed in `test_cli_surface.py` after); the CI jobs of the batch that carries it (`cac/lote-14`, run 41945588359) were still running at 23:30, so the task waits on their result on the exact commit.
- [ ] 6.2 Update the evidence labels of the rows `H-A-EDIT-*` and `H-A-INTEG-*` and the matrix. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  - 2026-11-04, BLOCKED (exact blocker): the labels move only on the maintainer's reports of tasks 1.2 and 4.2 (Altium runs J1 to J22 and J23 to J33); phase B is built and waiting at the agent's kit folder `c0241-J/phase-b` (task 4.1).
- [x] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q`.

## Observation intake preparation

- [x] 1.3 Prepare a read-only intake harness for phase A: scan with the kit's path/privacy rules before interpretation, compare J1/J2 controls separately from edited files, expose only counts/digests, and keep native verdicts unjudged. Proof: `uv run pytest tests/unit/cli/test_altium_observations.py tests/unit/backends/altium/test_part_j.py -q`.

## Continuation review — 2026-11-01

Altium Designer is unavailable per the maintainer. No phase A saves/report arrived; Decision 1 forbids edit modules before those observations. Phase B and all native gates remain open.
See `docs/evidence/altium-native-acceptance.md`, "Continuation inventory", for existing reports and exact remaining dependencies. No native, paid-agent or personal-review outcome is claimed.

Intake proof — 2026-11-01: `tests/unit/cli/test_altium_observations.py` and `test_part_j.py`: 8 passed. Raw/decoded privacy guards, changed-member/record counts, plain-resave controls and unjudged native verdicts are covered. No edit operation is implemented or graduated.

Task 6.3 proof — 2026-11-01: the Unreleased entry records the closed read-only intake task; `tests/unit -k "release_record or changelog"` passes (167 passed, 1 optional SDK skip, 17466 deselected). Task 6.2 stays open for the actual native phase A/B measurements; no `H-A-EDIT-*` or `H-A-INTEG-*` level is raised by the authored harness. Full/CI task 6.1 stays with the coordinating branch.

## Approved pending-native scope — 2026-11-03

The maintainer explicitly authorized the pending Altium validations on the
available Altium Designer 24.5.2.23: "tenho so o24.5, mas eu autorizo as
validacoes serem no24, nao precisa ser na26". This replaces the version
prerequisite of pending runs only. Record the actual tool/build, input hashes
and each observed outcome. It does not complete a case, open a write gate,
raise evidence, prove26.5 equivalence or replace any historical26.5 report.
Do not combine different versions/input digests into one fictional kit run.
All existing acceptance criteria, facts-before-code rules and final CI remain.
The kit form keeps its existing AD major.minor dialect: use AD 24.5; keep full
build 24.5.2.23 in the separate native observation report, not a new form key.
