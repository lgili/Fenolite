## Context

- **Labels.** `core/evidence.Level` orders `ALTIUM_VERIFIED_KIT` above `KICAD_VERIFIED`; `verify.release_verified` holds it. `verification-evidence`, "Evidence label grammar": the first field of the parenthesis is `kit` or `author-report`. "Author reports never promote an operation".
- **Rows waiting.** `docs/hypotheses.md`: `H-A-WRITE-SCHLIB`, `-PCBLIB`, `-SCHDOC`, `-PCBDOC` ("opens and compiles in AD 24.x without a repair prompt … kit request (v0.4): open, compile and re-save the file with the acceptance kit") and `H-A-PH-CHECKSUM`, `-ZERO-FIELDS`, `-NO-CACHE`, `-LAYOUT`. Several dozen more rows are author reports from 2026-10-02 to 2026-10-04 with "no artefact".
- **What Altium can write that Fenolite can read.** A document saved by Altium (`.SchDoc`, `.PcbDoc`, `.SchLib`, `.PcbLib`, `.PrjPcb`): Fenolite's readers were proved on such files over the public corpus (RT-A1). That is the strongest result a step can leave: Altium loaded Fenolite's file, kept its content, and wrote it in its own bytes. Text reports (messages, rule check, change order, generated outputs) are archived as they are.
- **Constraints.** Clean-room: the steps use Altium's menus as its public documentation names them. Privacy: files that Altium saves may hold a user name or a path; the verify step scans the results for them and says so before anything is recorded.

## Goals / Non-Goals

**Goals:**
- A person with Altium can run the kit in about an hour, without knowing Fenolite's internals.
- Every result that can be a file is a file, and Fenolite checks it.
- The record in the repository is small, has no personal data, and lets anyone match a published archive by digest.
- The rule for the kit label is written down and tested.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Kit layout.** `kit/` holds `kit.json` (schema `fenolite.altium-kit.v0`: kit version, Fenolite version, the samples with every file's SHA-256, the steps), `STEPS.md` (generated from the same steps), `results/` (empty, with `form.json`), and one folder per sample. `fenolite kit build --out DIR --seed … --timestamp …` is deterministic, so two people build the same kit, and its digest (`kit_sha256`, over `kit.json`) identifies it.
2. **Samples.** Five, each from a script under `examples/kit/`: `flat` (one sheet, the blink), `tree` (c0086's hierarchy with a bus), `routed` (the routed blink with rules and polygons), `board6` (c0085's sample), `libs` (a schematic library and a PCB library). Each is built in the binary form; `flat` also in the ASCII form.
3. **Steps.** A step has an id (`K<group>.<n>`), the sample, the instruction in one or two sentences, the result (`file: results/<name>` or `form: <field>` with its type), the expected value, and the hypotheses it settles. Groups: K1 open and re-save each document kind; K2 compile and messages; K3 change order into an empty board; K4 rules editor and rule check; K5 layer stack, vias, texts, keep-outs, bodies; K6 repour; K7 output job; K8 sheet template and special strings; K9 libraries (update from libraries). The steps are those of the author-report parts of c0084 to c0087 (U, X, Y, V, W), rewritten so that each ends in a file where one exists.
4. **Result files.** Re-saved documents (`results/<sample>/<name>.<ext>`), the Messages panel exported or copied to `results/<sample>/messages.txt`, the rule check report `drc.html` or `.txt` as Altium writes it, the change order report, and the list of files the output job generated (`outputs.txt`, names only). No generated fabrication file is required in the archive.
5. **`kit verify`** (read-only, exit 5 on a failed check): (1) the kit's files match `kit.json`; (2) `form.json` validates against its schema and names the Altium version; (3) for each re-saved document, Fenolite reads it (RT-A0 and RT-A1 must hold) and its import equals the sample's built model at levels 1 to 5 of `equivalent` within the kit profile, with `parity` and `copper.clearance` reporting what they report on Fenolite's own file; for `routed`, the repoured polygons must now be poured and the copper check is run with them; (4) each `form` value equals its expected value; (5) a privacy scan lists strings in the results that look like a home folder or a user name. The result is a verdict per step and per hypothesis.
6. **What a file proves, and what a form proves.** A hypothesis whose steps all end in files that passed is `kit`. One with a typed step is `kit` too, but its record line says `form`, and the row's result text says which fact was typed. Rejected: making typed steps author reports, because then no row about what Altium displays could ever be release-verified; the form is part of an archived run with the files that corroborate it.
7. **The record.** `fenolite kit record DIR --confirm` (a mutating command, dry run first) writes `docs/evidence/altium-kit/<run id>.json` with schema `fenolite.altium-kit-run.v0`: run id (`<date>-<first 8 hex of the archive digest>`), kit digest, Fenolite version, Altium version, operating system family, per step `pass`/`fail`/`skipped` and `file` or `form`, per hypothesis the verdict, and the SHA-256 and size of every file of `results/` and of the archive `results.zip` it writes beside `DIR`. No path, no user name. It prints the register rows whose label may change.
8. **Label rule.** A row may be set to `ALTIUM-VERIFIED(kit; AD <major>.<minor>; <date>; <run id>)` when a committed run record holds a passing verdict for it, the kit digest of that run is the digest of the kit that the current tree builds for the samples that the row's steps use, and the record's archive digest is published in the row's result text. A row keeps `kit` only while that holds: a change to a writer that changes a sample's bytes makes the run stale for the rows of that sample, and `tests/unit/test_hypotheses_register.py` fails until a new run is recorded or the row goes back to `INFERRED`.
9. **Kit script (decided by the maintainer on 2026-10-06).** The kit holds one script file with its digest in `kit.json`. The user opens the kit's script project in Altium and runs one procedure; for each sample it opens the project, compiles it, saves each document under its result name, exports the messages and the reports, repours the polygons of `routed`, and generates the output job's containers, writing `results/script.log` with one line per step (`K<group>.<n> done` or the error text). Rules: (a) every step the script does is also a checklist step with a manual instruction, and a run without the script is complete; (b) the script writes nothing outside `results/`; (c) each call it makes is listed in `docs/altium-kit.md` with the page of Altium's public scripting documentation that documents it, and task 2.3 registers those pages as sources before the script is written; (d) the language is the one that documentation describes for scripts run from the editor (DelphiScript unless task 2.3 finds that another is the documented default); (e) steps that need a person (reading a dialog, comparing a picture) are never scripted; (f) a step done by the script is marked `scripted` in the run record, with the script's digest. A call that the documentation does not cover is not used, and its step stays manual.
10. **Cut order.** First the privacy scan's heuristics beyond home folders, then group K9, then the script's export of reports (the saves stay), never build, verify, record and the label rule.

## Files and public API

- `src/fenolite/verify/kit/manifest.py`: `KIT_SCHEMA`, `Kit`, `build_kit(out, *, seed, timestamp) -> Kit`, `kit_digest`.
- `src/fenolite/verify/kit/steps.py`: `Step` (with `scripted: bool`), `STEPS` (the closed list), `steps_markdown()`.
- `src/fenolite/verify/kit/script.py`: `script_text(steps) -> str` (the kit script, generated from the steps so that the two cannot differ), `SCRIPT_CALLS` (each call with its source id).
- `src/fenolite/verify/kit/results.py`: `verify_results(folder) -> KitVerdict`, `privacy_scan`.
- `src/fenolite/verify/kit/record.py`: `RUN_SCHEMA`, `run_record(verdict, …)`, `stale_rows(register, records, kit)`.
- `src/fenolite/cli/cmd_kit.py`: `kit build`, `kit verify`, `kit record`, `kit status`.
- Tests: `tests/unit/verify/kit/test_{manifest,steps,results,record}.py`, `tests/unit/cli/test_kit_cmd.py`, with a simulated run: results made by Fenolite's own writers standing in for Altium's saves, marked as synthetic so that no label can come from them.

## Sources registered by this change

- Altium's public documentation of the menus the steps name (saving a document, compiling a project, the Messages panel, Update PCB Document, the PCB Rules editor and the rule check report, the Layer Stack Manager, the Polygon Manager, output jobs, sheet templates, Update From Libraries): the rows that c0032 to c0038 registered (S-0134 to S-0141, S-0164, S-0165, S-0195 to S-0198) and those of c0084 to c0087.
- No file format fact is added.
- New, for the script: the pages of Altium's public scripting documentation (the scripting system, running a script from the editor, and the reference pages of each interface the script calls), registered by task 2.3.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-KIT-RESAVE | A document that Fenolite wrote, opened in Altium and saved under another name, is read by Fenolite's readers to a model equal to the sample's at levels 1 to 5, for each of the five document kinds | kit group K1, checked by `kit verify` | RT-A0 and RT-A1 hold on each re-saved file, and `equivalent` reports no difference outside the kit profile |
| H-A-KIT-COMPILE | Each sample project compiles in Altium without an error message, and the change order into an empty board lists the components and nets of the model | kit groups K2 and K3 | `messages.txt` holds no error line; the re-saved board after the change order equals the sample's model at levels 1 and 2 |
| H-A-KIT-REPOUR | After "Repour All" and a save, the board's polygons hold poured regions and Fenolite's copper check reports no short and no clearance violation on them | kit group K6 | every polygon of the re-saved `routed` board is poured; `copper.clearance` reports nothing |
| H-A-KIT-DRC | Altium's rule check on the sample with two planted violations reports those two and no other of the kinds Fenolite judges | kit group K4 | the archived report lists two violations; the form's two counts are 1 and 1 |
| H-A-KIT-SCRIPT | The kit script, run from Altium's script menu on the kit's samples, performs every step marked `scripted` and writes the result files that the manual steps would leave | a kit run with the script, checked by `kit verify` | `script.log` holds `done` for every scripted step, and `kit verify` passes on the files the script wrote |
| H-A-KIT-STABLE | Two builds of the kit on two machines give the same `kit.json` digest | `tests/unit/verify/kit/test_manifest.py::test_deterministic` and CI on three operating systems | equal digests in the `unit` jobs of Linux, macOS and Windows |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry, registers, kit page skeleton | 0.5 |
| kit build: samples, manifest, steps | 1.5 |
| kit verify: files, form, re-saved documents, privacy scan | 1.75 |
| kit script: sources, generated script, its tests | 1 |
| kit record and the stale-row guard | 1 |
| label rule in the register tests | 0.5 |
| command, docs, simulated run | 0.75 |
| closing | 0.25 |

Total: 7.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `verification-evidence`, "Reserved id families": the families `H-A-WRITE-*` and `H-A-PH-*` are removed from the required list once their rows have kit steps; "Author-report rows" is unchanged. Task 0.1 writes the first as MODIFIED from the living text.
- `cli-contract`: the command list gains `kit`; "Experimental features in capabilities" is not touched here (c0092).
- Archive order: the code can be archived before the first real run; the rows change with the run, in c0092 or in a later evidence commit.

## Risks / Trade-offs

- [A re-saved document differs from the model in fields Altium normalises] → the kit profile lists each such field with its cause, as the triangle's exclusion list does; a field without a cause fails the step.
- [Altium versions differ] → the record names the version; the label carries it; a second version is a second run.
- [The script fails on another Altium version] → the checklist is complete without it; `script.log` names the failing step, and that step is then done by hand in the same run.
- [A scripting call is not publicly documented] → not used; the step stays manual, and `docs/altium-kit.md` says so.
- [Personal data in saved files] → the privacy scan, the record without paths, and the archive kept out of the repository; `docs/altium-kit.md` tells the user what a saved file may contain.
- [A run goes stale quickly while writers change] → the guard names the stale rows; the kit is run at the end of the milestone (c0092), not after every change.

## Migration Plan

- Additive: a new command group and a new evidence folder. Author-report rows stay as they are until a run covers them.
- Rollback: remove the command; no label depends on it until a run is recorded.

## Open Questions

- **Where is the archive published?** Decided by the maintainer on 2026-10-06: as an asset of the GitHub release that the run supports, named `altium-kit-<run id>.zip`; the record holds only its digest and size.
- **May someone other than the maintainer contribute a run?** Default: yes, by a pull request that adds a run record and names where the archive is; the label rule is the same.
- **Should the kit include the ASCII schematic form for every sample?** Default: only for `flat`.
