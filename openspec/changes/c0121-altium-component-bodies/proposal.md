## Why

Change c0085 was to write component bodies into the Altium PCB document and cut them "for lack of sourced facts": the saved extruded bodies hold 35 keys, and the fact page typed seven (`openspec/changes/c0085-altium-pcb-complete/design.md`, "Found on 2026-10-06", item 8). Since then each `ComponentBody` of a board is reported with `altium.not-lowered` and `body/<id>`, step X8 of Part X is "not run", and RT-A3 counts the consequence: 446 bodies of the seven public documents and 1298 of the heavy one are in the model and are not in the rewrite (`docs/evidence/altium-roundtrip.md`, "RT-A3").

The maintainer decided on 2026-10-06 that bodies become this follow-up, **fact rows first**. The facts were therefore measured while this proposal was written, on the eight public PCB documents and four public PCB libraries of the corpus manifest (1748 body records). The result, in the design ("Measured"): the saved form of an extruded body is known key by key, 33 of its 35 keys have a value rule that the corpus supports, and two do not (`MODELID` and `MODEL.CHECKSUM`); a body that names a 3D model cannot be written at all without model data that the design model does not carry; and KiCad's importer shows nothing for an extruded body, so it cannot be the oracle. The proposal says which fields are known well enough to write, which are stand-ins that only Altium can settle, and what is left out.

**How far the evidence goes.** It is thin, and the fact rows cannot be read as more than this: the extruded records come from five documents of three repositories, 1265 of the 1272 from one repository, and nothing that this change writes was opened in Altium. The rows say what Altium saved in those files; they do not say what Altium accepts.

## What Changes

- **Fact rows first.** `docs/formats/altium/pcb-bodies.md` gains the section "Written form of an extruded body": one row per binary field and per key that the writer sets, each with its value rule, source, label and hypothesis, and a corpus test that holds the rows over the public documents. A key without a row is not written; a row whose value is a stand-in says so and names the hypothesis that only an author report settles.
- **Extruded bodies in the PCB document.** A `ComponentBody` of kind `extruded` with an outline and a height above its standoff is written as one record in `ComponentBodies6` and its twin in `ShapeBasedComponentBodies6`, linked to its component by index, on a mechanical layer, with the board side of its component. Nothing else of a body is written: no model reference, no `Models` entry, no STEP data.
- **Opt-in.** `fenolite build --target altium --altium-bodies extruded` (and the same option of the model writer); the default is `off`, so every build and every committed sample keeps its bytes. The default changes only after step X8 is reported.
- **No invented geometry.** The outline and the heights are those of the model's body. A footprint without a body gets none: no body is derived from a courtyard, and no height is assumed. The design model is not changed.
- **Accounted.** `result.pcb.written.body` and `result.pcb.not_lowered.body` count every body; each body that is not written is one `altium.not-lowered` with `body/<id>` and its reason (a model body, no outline, a height not above the standoff, an unknown projection, bodies switched off).
- **Bodies of a library footprint.** `FootprintDef.bodies` of kind `extruded` are written into the PCB library as primitives of type 12 (first item of the cut order: the corpus holds one library body, and it names a model).
- **Read-back and round trips.** A written body reads back to the model's body within 2 nm; with bodies on, RT-A2 and RT-A3 compare the kind `body`, and the corpus run reports per document how many bodies were written and how many were not, by reason.
- **KiCad.** A probe records that `kicad-cli pcb import` reads the written document and shows no item for an extruded body, as it shows none on the public documents; every other kind stays equal.
- **Altium.** Step X8 of Part X is written out and its files are built outside the repository in two forms (the saved form with stand-ins, and a short form without the model keys), so that one session settles both: session 2 of the maintainer's Altium work, not session 1, whose folder he already has.

Size: 4.75 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-pcb-writer`: ADDED "Body facts before body code", "Extruded component body records", "Component bodies of a library footprint"; MODIFIED "Component bodies are reported" (of c0085: the extruded bodies are written when asked, the others reported with a reason) and "Imported boards are written from the model" (of c0090: one clause, a body that is written is no longer left out).
- `altium-build`: ADDED "Component bodies in an Altium build" (the option, the counts, the bytes of a build without it).
- `altium-verification`: ADDED "Component bodies in the round trips"; MODIFIED "RT-A2 on a written model" (of c0090: one bullet, the kind `body` when bodies were written).

## Non-goals

- No body of kind `model`: no model name, no `Models` or `ModelsNoEmbed` entry, no embedded or linked STEP data, no checksum of model data. The design says why.
- No cylinder and no sphere: the import does not tell them from an extruded body, and no saved record of either was read.
- No arc in a body outline, no hole in a body, no texture, no snap point, no override colour.
- No body derived from a courtyard, a fabrication outline or a pad box, and no default height.
- No change of the design model, of the DSL, of the catalog, of the Altium import (`adapter/bodies.py`, which change c0099 of another session edits) or of the KiCad backend. No KiCad output changes.
- No analysis of body volumes: that is c0099.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label. KiCad's importer is run as a subprocess and is not read for this change.

## Evidence level required

- The saved form of an extruded body (key set, order, constants, the links between keys, the twin record): `CORPUS-VERIFIED` under `H-A-PCBX-BODY-FORM` when the corpus test holds on rows of at least three repositories. Measured for this proposal: five documents of three repositories hold extruded bodies, 1265 of the 1272 in one repository; the label is earned by the rule and is thin, and the page says so.
- Own read-back of a written body: `INFERRED` under `H-A-PCBX-BODY-READBACK`.
- KiCad's importer on the written document: `ORACLE-VERIFIED(kicad-cli 10.0.x)` only for "the document is read and every other kind is unchanged"; it says nothing about the body.
- That Altium opens the document and shows each body with its heights: `INFERRED` until step X8 is reported; then `ALTIUM-VERIFIED(author-report; …)`. Nothing in this change is marked `ALTIUM-VERIFIED`.

## Decisions (2026-10-06)

The coordinator accepted the defaults below on the maintainer's behalf on 2026-10-06, as the conservative reading of his order "a follow-up change with fact rows before the write"; they are to be shown to him, and each keeps what switching it would cost. The design holds the alternatives.

1. **Inside v0.4**, opt-in and `experimental`, implemented before c0092; the change of the option's default waits for step X8 and may fall after v0.4.
2. **The option is `off`** until step X8 is reported.
3. **The saved form** (35 keys, two stand-in values) is written; the short form is built for X8 only.
4. **Bodies that name a 3D model** are never written by this change.
5. **No body is invented** where the model has none; a way to state a height in a script is a later change of the DSL, after v0.4.
6. **Library bodies** are written, first to be cut.
7. **Keeping `MODELID` and `MODEL.CHECKSUM` of a body that was read** is change c0129, a small change of its own, scheduled right after c0099 is on `dev`: it is what makes a rewrite carry real values instead of stand-ins.
8. **A new sample `body2`**; `board6` keeps its five files byte for byte.

## Open decisions for the maintainer

None is open; the eight above wait for his review.

## Impact

- Changed: `backends/altium/{pcbrecords,pcbdoc,pcblib,lower}.py`, `lens/altium_copper.py`, `lens/altium.py`, `backends/altium/roundtrip.py` and `rta3.py`, `cli/cmd_build.py`, `cli/data/explain.toml` (the wording of `altium.not-lowered`), `verify/kit/steps.py` (one sentence).
- Pages: `docs/formats/altium/pcb-bodies.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/altium-pcb.md` (step X8), `docs/evidence/altium-roundtrip.md`, `docs/evidence/sources.md` (S-0570, S-0571 of the block S-0570 to S-0579), `docs/hypotheses.md`.
- New files: `tests/data/altium/body2/` with manifest rows, `tests/_altium_body2.py`, the tests named in the design.
- Committed samples: none changes. `tests/data/altium/board6/` and the four older samples hold no body and are built without the option.
- Depends on: c0085 (the accounting and the requirement this change modifies), c0090 (the model writer, RT-A2 on a written model, RT-A3), c0043 (the body reader and the import that prove read-back). Followed by c0129 (the identity of a body that was read), after c0099 is on `dev`. Beside it, not a dependency: c0099 of another session (bodies on the import side and their analysis); the design says how the two fit and what this change does when c0099 is, or is not, on the branch.
