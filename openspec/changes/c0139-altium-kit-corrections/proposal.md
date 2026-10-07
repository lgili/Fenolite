## Why

On 2026-10-07 the maintainer made the first manual run of the verification kit (change c0091) in Altium Designer 26 and returned the folders. The run is recorded as an author report; **no kit label came from it**, and no run record exists. Reading the returned folders showed five defects of the kit itself, none of what Fenolite writes:

- **(a) Privacy.** The privacy scan lists paths under a home folder and login names. A PCB document that Altium saves names its own file with the folder it was saved in (the board record's `FILENAME`), on whatever drive that is: a path on another drive was not listed. The archive of a run is meant to be published, so this comes first.
- **(b) The project step.** Saving the project (step K1.5, "Save Project As") made Altium write the kit's own `flat/flat.PrjPcb` again in place, with every key it knows and the same five documents. The manifest check then failed all ten steps of `flat`, and `kit record` would have refused the run.
- **(c) Expected values.** `STEPS.md` printed `expected false` for the number steps K3.2 and K9.2 and `expected true` for K4.3 and K4.4: a map of truth values was applied to 0 and 1.
- **(d) The update step.** Step K9.1 let `H-A-SCH-UPDATE` pass from a saved sheet that cannot show whether "Update From Libraries" ran.
- **(e) The board step.** Step K5.1 wants the PCB document of `board6`; the schematic was saved, under its own name. `kit verify` passed the step over as not done.

## What Changes

- **The privacy scan reports any absolute path of the machine**: a path from a drive letter, on a share, or from a POSIX root, as the new kind `absolute-path`, beside `home-folder` and `login-name`. A file is read as 8-bit text and as UTF-16 at both alignments. Relative paths, stream names and web addresses are not reported, and the documents that Fenolite writes give no finding. The run record refuses such a string too.
- **A sample's project file that the tool saved again is accepted** when it still lists exactly the sample's documents: it is reported (`kit.project-resaved`, info; `result.kit_resaved`; `kit_resaved` in the run record) and fails nothing. Any other changed file of the kit, and a project file with another list of documents, fails as before. Step K1.5 keeps its wording; `STEPS.md` says what Altium does.
- **`STEPS.md` prints an expected value by the step's value type**, and `steps.problems` reports an expected value of another type than its step declares.
- **Step K9.1 no longer names `H-A-SCH-UPDATE`**; no step of the kit settles that row. `H-A-SCHLIB-UPDATE` keeps K9.1 and the typed step K9.2, so it passes only with a typed value and is marked `form`.
- **Step K5.1 names "the PCB document" in bold.** `kit verify` tells a result file by its content: a file of another kind of document than the step wants fails with one reason that names both kinds; a file of the same name with another ending, where the step's own file is absent, fails the step and is named.
- **The script says which version it was written and run for**: no registered page states the version of Altium Designer it describes, and the first run is on Altium Designer 26 (`script.PAGE_VERSIONS`, `script.FIRST_RUN_ON`, the script's header).

**The kit digest changes.** `STEPS.md` and the script are files of the kit, and the steps are part of `kit.json`: (b), (c), (d), (e) and the script's header each change them. No run record exists under `docs/evidence/altium-kit/`, so no row can become stale.

**A run already made.** The returned kit folder was built by the kit before this change. Checked again with this change, its project file is accepted, and the ten steps of `flat` are judged on their own results instead of failing for the manifest.

Size: 1 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: MODIFIED "Verification kit contents", "Kit steps settle hypotheses", "Kit script", "Kit result verification" and "Kit run record". c0091 is implemented and not archived, so each text is copied in full from c0091's active delta, with only the changes of this proposal; c0139 is archived after c0091.

## Non-goals

- No file, path or name of the returned folders enters the repository, a test or a log: every test authors its own document with an invented path of the same shape.
- No new run: nothing is started in Altium, and no row changes its level.
- No change of what Fenolite writes into an Altium document.
- No rewording of step K1.5 that would rest on behaviour of Altium that nobody observed.

## Evidence level required

- The corrections are ordinary code with unit tests. What Altium Designer 26 did to the project file and what a saved document holds are observations of the maintainer's run, an author report: they explain the corrections and settle no row.
- `H-A-SCH-UPDATE` and `H-A-SCHLIB-UPDATE` keep their level and their result text.

## Impact

- Changed: `src/fenolite/verify/kit/` (`results.py`, `steps.py`, `script.py`, `record.py`), `src/fenolite/cli/_kit.py`, `src/fenolite/cli/cmd_kit.py`, `src/fenolite/cli/data/explain.toml`, `docs/altium-kit.md`, `docs/cli-contract.md`.
- The run record gains the field `kit_resaved`; `result` of `kit verify` gains `kit_resaved`; one issue code is new, `kit.project-resaved`.
- Depends on: c0091.
