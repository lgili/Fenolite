## Context

- **The kit today** (c0091 with its follow-ups, on `dev`): `verify/kit/results.py` checks the kit's files against `kit.json`, judges every step and scans the result files; `verify/kit/steps.py` holds the 32 steps and prints `STEPS.md`; `cli/_kit.py` holds what `verify` may not import (the readers, `equivalent`, the checks).
- **The run.** The maintainer's manual run of 2026-10-07 in Altium Designer 26, returned as folders that stay outside the repository. They were read with Fenolite's readers and with the scan; only counts and kinds were taken from them.
- **Layering.** `verify` imports the standard library, `fenolite.core` and `fenolite.verify` only (`tests/unit/verify/test_levels.py`).

## Decisions

1. **(a) Three shapes of absolute path, three readings of a file.** `DRIVE_PATH` (a drive letter, then `\`, a doubled `\` as escaped text holds it, or `/`), `SHARE_PATH` (two backslashes, a server, at least one part) and `POSIX_PATH` (from the root, at least two parts, the first starting with a letter, and not after a letter, a digit, a colon or `<`). A file is read as 8-bit text, which finds a string in ASCII, in a Western code page and in UTF-8, and as UTF-16 from byte 0 and from byte 1, because a wide string may start at an odd offset. Against flooding: a path under a home folder stays one `home-folder` finding; a drive path needs three characters after its root; nine of ten characters of a match must be letters, digits or path signs, which bytes of a compressed stream are not; relative paths, stream names (`Board6/Data`), web addresses, dates and fractions do not match by construction. A test holds that every file of a built kit gives no finding.
2. **(b) Judge the project file by its documents; do not reword K1.5.** The rewritten file listed the same five documents by the same relative names and had other bytes (a byte-order mark and every key Altium knows). What a step needs of a sample's project is its list of documents, so `results.saved_again` accepts `<sample>/<name>.PrjPcb` of a sample when the bytes list exactly the kit's files of that sample's folder. The expected list comes from the manifest that is already there (the sample's files), so a kit built before this change is judged too. The project file is text in sections; `results.project_documents` reads the `DocumentPath` of each `[Document<n>]` with the standard library, and a test holds it equal to the product's reader on every sample. Rejected: rewording K1.5 to save a copy elsewhere. Nobody observed what Altium does with a copied project whose documents are not beside it, and the next step that changes the project (K3.1 adds a document while the project is open) could make Altium write the file again anyway.
3. **(c) The value type decides how a value is printed**, never the value: `0 == False` in Python. `steps.problems` also reports an expected value whose type is not the declared one, so a number cannot be declared as a truth value by mistake.
4. **(d) K9.1 stops naming `H-A-SCH-UPDATE`.** Of the three ways out this is the smallest in which no false pass is possible. A changed library that the update must pull in would need a second library sample and a new comparison. A typed value would settle half of the row: its criterion also names the update of selected attributes, which no step of the kit runs. So the row is settled by no step and stays an author report. `H-A-SCHLIB-UPDATE` already needs the typed step K9.2 and is marked `form`.
5. **(e) Kind by content, and the stray file.** `cli/_kit.document_kind` tells a PCB document, a PCB library, a schematic library, a schematic document and a project file from the bytes. `judge_document` compares the kind of the result file with the kind of the kit's own before any check. In the returned run the schematic was saved under its own name, so the step's file was absent: `results._file_step` fails a step whose result file is absent while its folder holds a file of the same name with another ending that no step asks for.
6. **The script's version.** The registered rows S-0501 to S-0504 are pages of the Altium Designer documentation at an address without a version (S-0501, S-0502) and of the Altium DXP Developer documentation (S-0503, S-0504); none states a version of Altium Designer. This is said from the register; the pages were not read again.

## Files and public API

- `verify/kit/results.py`: `DRIVE_PATH`, `SHARE_PATH`, `POSIX_PATH`, `absolute_paths(text)`, the kind `absolute-path` of `PrivacyFinding`; `project_documents(data)`, `sample_documents(kit, project)`, `saved_again(kit, path, data)`; `KitVerdict.resaved`.
- `verify/kit/steps.py`: `expected_text(step)`; K5.1 and K9.1; two paragraphs of the checklist's head.
- `verify/kit/script.py`: `FIRST_RUN_ON`, `PAGE_VERSIONS`, `READ_AS`, two header lines.
- `verify/kit/record.py`: the field `kit_resaved`; `record_problems` refuses an absolute path.
- `cli/_kit.py`: `DOCUMENT_KINDS`, `document_kind(data)`, `kind_problems(own, saved)`.
- `cli/cmd_kit.py`: `result.kit_resaved`, the issue `kit.project-resaved`.

## Sources registered by this change

None. No file format fact is added: the project file's sections and `DocumentPath` are in `docs/formats/altium/project.md`.

## Hypotheses registered by this change

None. `H-A-SCH-UPDATE` and `H-A-SCHLIB-UPDATE` keep their rows; their test cells name author-report steps and no kit step, so the register does not change.

## Spec deltas and archive order

- `altium-verification`: five MODIFIED requirements, each copied in full from c0091's ACTIVE delta (`openspec/changes/c0091-altium-verification-kit/specs/altium-verification/spec.md` at `f17b03e9`), because c0091 is not archived. Archive order: c0091, then c0139. If c0091's delta changes before it is archived, these texts are corrected from it.
- `cli-contract`, "Kit command" (c0091's delta) is not modified: the new result field and issue code are in `docs/cli-contract.md`.

## Risks / Trade-offs

- [The scan reports a string that is no path of the machine] → it is a warning that a person reads; the cap per file stays 20.
- [A path in an encoding the scan does not read] → the scan reads what the returned documents held (8-bit text) and UTF-16 at both alignments; a second, cruder search of the returned folders found nothing more.
- [A project file that Altium saves with another spelling of a document's name] → names are compared without regard to case; any other difference fails, as it should.
- [The stray-file rule fails a step for an unrelated file] → only a file of the same name, in the same folder, that no step asks for.
