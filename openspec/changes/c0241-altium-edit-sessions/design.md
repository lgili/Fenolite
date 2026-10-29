## Context

- **Origin.** Package 12 of c0175 ("Native Altium edit sessions", `design.md` section 12, tasks 6.1 to 6.7
  and its `altium-edit` delta), moved here on 2026-10-29. Its sixth place in c0175's cut order stands.
- **What exists** on `dev` at `1559f1b`:
  - the lossless readers of PCB documents, PCB libraries and schematics (`backends/altium/read/`), with the
    records view of `fenolite diff` and the resave rule of c0207 (`H-A-RD-RESAVE`);
  - the compound-file writer (`backends/altium/cfb.py`) and the document writers, which build whole
    documents from a model, never edit one;
  - the Altium verification kit (`docs/altium-kit.md`) and the Part-letter kits of earlier changes (Part S
    of c0168, Part Q of c0173, Part F of c0172), built by a test into a folder outside the repository.
- **Facts known.** The fact rows of `docs/formats/altium/pcb-document.md` (the unique-id table lists pads
  only, its `PRIMITIVEINDEX` is the pad's position), `pcb-pour.md` (pieces carry `SUBPOLYINDEX`; 8 of 81
  public polygons hold numbers with gaps), `pcb-copper.md` (`POURINDEX` from 0, unique) and `pcb-bodies.md`
  (every body that names a model has its entry). Nothing public says what an edit in Altium Designer changes.

## Goals / Non-goals

- **Goals:** typed edits of a saved Altium document that the native tool opens and saves again; a check
  that finds the faults that make it fail; every fact behind an operation measured first.
- **Non-goals:** the proposal's.

## Decisions

### 1. Facts by observation before any write code

Task 1.1 registers the hypotheses and builds kit phase A; task 1.2 is the maintainer's run. No module of
`backends/altium/edit/` is written before task 1.2 is recorded. Phase A asks Altium Designer to make each
edit the session will make, on documents authored for Fenolite, and to save each under its own name.
Fenolite compares each saved file with the plain resave of case J1 in the records view, so what a save
rewrites anyway (J1 against the kit's document, J2 against J1) is kept apart from what the edit changed.

Alternative rejected: writing the session from the readers' knowledge and testing it in phase B only. A
fault found there would not say which index the session missed.

### 2. Kit Part J

`docs/evidence/altium-edit.md`, Part J, in the form of Part Q: phase A cases J1 to J22 (J22 sends the
folder), phase B cases J23 to J33 (J33 sends it). `tests/unit/backends/altium/test_part_j.py -k phase_a`
builds phase A into the folder named by `FENOLITE_ALTIUM_PART_J`, by default under the test's own folder:

- `board/`: `tests/data/altium_edit/edit.py` built with `--target altium --altium-pour outline`, with a
  fixed seed and timestamp, without the build's cache. The pour mode `outline` keeps the kit independent of
  the `geo` extra and of the pour engine; case J16 asks Altium for the pieces.
- `expected.md`: every item the cases name, read back with Fenolite's reader.
- `README.md` (Brazilian Portuguese, `tests/data/altium_edit/kit/README-phase-a.md`), `PART-J.md` (the page's
  Part J) and `SHA256SUMS`.

Phase B files (`written/`, `faults/`, `expected-b.md`) are built by task 4.1, once the session exists.

### 3. Hypotheses registered by this change

| id | statement |
|---|---|
| H-A-EDIT-RESAVE | a plain save keeps every record, order and index entry; J1, J2 |
| H-A-EDIT-MOVE | a move changes only coordinates; J3, J4 |
| H-A-EDIT-PROPERTY | a property change changes only its field (and its wide-string entry); J5 to J7 |
| H-A-EDIT-ROTATE | a turn changes rotation and the primitives' places; J8 |
| H-A-EDIT-FLIP | a flip moves primitives to the paired layers, mirrored; J9 |
| H-A-EDIT-DELETE | a deletion renumbers every positional index; J10, J11, J17 |
| H-A-EDIT-CLONE | a pasted record has its source's form; J12 |
| H-A-EDIT-ADD | a placed component adds its records and entries; J13 |
| H-A-EDIT-IDS | new ids are unique, of the held form, unrelated to content; J12, J13, J23 |
| H-A-EDIT-LAYER | a layer change moves both layer fields together; J14 |
| H-A-EDIT-RULE | a rule change keeps the record's id and place; J15 |
| H-A-EDIT-SCH | schematic edits change only the part's records; J18 to J20 |
| H-A-EDIT-LIBRARY | a library pad move changes only that pad; J21 |
| H-A-EDIT-KIT | documents the session writes open, save and reopen; J23 to J25 |
| H-A-INTEG-SUBPOLY | gaps in sub-indices fail the tool (evidence against it); J16, J26 |
| H-A-INTEG-POURINDEX | duplicate pour indices fail the tool; J17, J27 |
| H-A-INTEG-ID | duplicate ids fail the tool; J12, J13, J28 |
| H-A-INTEG-PARAMCOUNT | a wrong parameter-group count fails the tool; J1, J6, J29 |
| H-A-INTEG-PARAMORPHAN | orphan parameter records fail the tool; J11, J30 |
| H-A-INTEG-MODEL | unused or missing model-store entries fail the tool; J31 |
| H-A-INTEG-LAYER | two disagreeing layer fields fail the tool; J14, J32 |

The full statements, criteria and kit requests are the rows of `docs/hypotheses.md`.

### 4. The integrity check (`backends/altium/edit/integrity.py`)

A document stage `altium.integrity` of `fenolite check`, read-only, beside the stages of
`checks/documents.py`. Each rule is a function of the decoded document that yields findings with the
stream, the record's position and the rule's row. Severity is `error` when the row is confirmed, `warning`
otherwise; the finding's evidence names the row. Codes `altium.integrity.<rule>`.

### 5. The session (`backends/altium/edit/session.py`, `ops.py`, `indices.py`, `commit.py`)

- `open(path) -> Session` reads the compound file and keeps every stream's bytes.
- An operation names its item by kind, geometry and net (a component by designator), must hit exactly one,
  and states each old value: otherwise `altium.edit.assertion` (exit 5) at commit, nothing written.
- A new record is a copy of a record of the same kind and layer held by the document, with the stated
  changes (`altium.edit.no-template` otherwise).
- `indices.py` keeps the unique-id table, the pad and via caches, polygon indices, wide strings, parameter
  groups and model store in step, as the confirmed rows say. New ids come from `secrets`, in the held form,
  unique in the document.
- `commit(out) -> Receipt` writes through the mutation protocol, reads the result back strictly, compares
  it with the input and refuses an undeclared change (`altium.edit.unexpected-change`), an undeclared
  connectivity or net-signature change (`altium.edit.connectivity`) and any `error` of the integrity stage.
- Gates: `edit.GATES`, one entry per operation, all false; an operation behind a false gate is refused
  with the gate and its rows named. A gate is set only by a recorded phase B case.

### 6. Evidence

`INFERRED` for the check and the hypotheses; the writes stay experimental until c0092's graduation rule
gives `ALTIUM-VERIFIED(kit)` per operation.

## Risks / Trade-offs

- **Phase A may contradict a rule.** `H-A-INTEG-SUBPOLY` already has public evidence against it; a
  contradicted rule is refuted and dropped, not tuned.
- **Fault probes may crash the maintainer's Altium.** The page tells him to work on a copy and to close other
  work first; each fault is in its own file.
- **Save As in a project** renames the project's entry in memory; the steps tell him not to save the project.
- **Size.** Two kit runs gate the work; the check (task 2.1) is useful alone and comes first after phase A.

## Open questions

1. Should phase B fault probes include a body with a model, which needs a model file authored for Fenolite?
   The recommendation is yes, with the smallest valid model, in task 4.1.
2. Should a session refuse a document saved by an Altium version older than the kit's? The recommendation
   is a warning naming the version, since the kit covers one version.
