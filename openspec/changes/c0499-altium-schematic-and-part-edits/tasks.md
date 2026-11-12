# Tasks: c0499-altium-schematic-and-part-edits

Rules for every task:

- The board this was found on is private. Nothing from it (names, nets, designators, coordinates, files)
  goes into tests, fixtures, commits or messages. Test data is the Part J kit project
  (`tests/unit/backends/altium/test_part_j.build_board`) and boards authored for Fenolite.
- Every new gate stays off in `SCHEMATIC_GATES` and `GATES`; tests open them as the existing ones do.
- Run each touched test file alone with `-n 0`.

## 1. Evidence first

- [ ] 1.1 Add `H-A-EDIT-SCH-ADD` and `H-A-EDIT-LINK` to `docs/hypotheses.md` (`INFERRED`), and write kit case
  J34 in `docs/evidence/altium-edit.md` (design, "Format evidence needed").
  - Proof: `uv run --extra dev pytest tests/unit/test_altium_verification_docs.py -k part_j -q -n 0`
- [ ] 1.2 Count the key sets of body records in the corpus. Record the counts and the key sets (no file
  names) in `docs/formats/altium/pcb-bodies.md` with their evidence label.
  - Proof: `uv run --extra dev pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q -n 0`

## 2. Bodies and models (F34)

- [ ] 2.1 `ops._same_form`: compare the 18-byte head and the vertex size for `Regions6`,
  `ShapeBasedRegions6`, `ComponentBodies6` and `ShapeBasedComponentBodies6` (design D5). Author a source
  board with a body of a smaller key set; add test `older_body`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_ops.py -k "older_body or no_template" -q -n 0`
- [ ] 2.2 `add_component` copies a missing `Models` entry and stream and shares one the target holds; test
  for "A model body copied with its model".
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_ops.py -k model_body -q -n 0`

## 3. Schematic operations (F35)

- [ ] 3.1 `add_part` with `OWNERINDEX` renumbering, `WEIGHT`, new `UNIQUEID`s and `?` designators (design D1);
  gate `add_part`; scenarios of "A part copied into a schematic sheet".
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_schematic_add.py -k add_part -q -n 0`
- [ ] 3.2 `annotate`, with `open(project=)` and the rename accepted by the net-signature guard (design D2);
  gate `annotate`; author a two-sheet project for the project scenario.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_schematic_add.py -k annotate -q -n 0`
- [ ] 3.3 `add_wire`, `add_net_label`, `add_power_port` and the automatic junction (design D3); gate `create`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_schematic_add.py -k "power_port or net_label or undeclared or gates" -q -n 0`
- [ ] 3.4 The existing schematic tests still pass.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_schematic.py -q -n 0`

## 4. Link (F36)

- [ ] 4.1 `Session.link` on the inverted `by_path` of `adapter.circuit`, the five source keys, `CHANNELOFFSET`,
  the sheet class and the footprint and comment refusal (design D4); gate `link` with its `ROWS` entry.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_link.py -q -n 0`
- [ ] 4.2 The whole job through public names only: one test copies, annotates, wires and links a part in
  the kit project, then asserts that the test module imports no name starting with `_` from
  `fenolite.backends.altium.edit`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_link.py -k public_only -q -n 0`
- [ ] 4.3 Every test that uses `OPERATIONS`, `ROWS` or the gates still passes.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit -q -n 0`

## 5. Kit case

- [ ] 5.1 Run J34 on Altium Designer 24.5.2.23 in the VM (GUI, as the maintainer allows). Record the result
  in `docs/evidence/altium-edit.md`. Raise `H-A-EDIT-SCH-ADD` and `H-A-EDIT-LINK` only if it passes. Gates
  stay off in this change either way.
  - Proof: `uv run --extra dev pytest tests/unit/test_altium_verification_docs.py -k part_j -q -n 0`

## 6. Docs, guide, changelog

- [ ] 6.1 Written forms of records 17, 25, 27 and 29 cloned by the session in
  `docs/formats/altium/schematic-records.md`, and the link keys in `pcb-document.md`, each row with source
  and label.
  - Proof: `uv run --extra dev pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q -n 0`
- [ ] 6.2 Teach the new session operations and gates in `src/fenolite/agent/skill/references/altium.md`
  (one tested line).
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 6.3 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
