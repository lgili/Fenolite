# c0408 tasks

Source: c0384 finding 1.4 (flat_hierarchy, 67 `net_conflict` of the build against its own sheets);
coordinator decision of 2026-11-05 approving (a) and (b), (b) on the board side only.

## 1. Fixes

- [x] 1.1 (a) `netnames.unconnected_name` treats a pin name equal to the pad number as no name (S-1490).
  Proof: `uv run pytest tests/unit/backends/kicad/test_netnames.py -q`, and
  `tests/kicad/schematic/test_naming_probes.py::test_a_pin_named_like_its_number_is_named_as_without_a_name`
  (kicad-needed) asserting that netnames gives KiCad's name for every pin of probe
  `sch-unconnected-samename`, on 10.0.6 and 9.0.9, through the heavy-run lock.
- [x] 1.2 (b) `lens.build.sheet_spellings` reads the sheets the drawn build writes and keeps KiCad's name of
  each label-named sheet-path net as the `stored` pair of the net's `kicad` bag (`lower_for_schematic`);
  `pcb.stored_net_name` writes it. No schematic generator file changes.
  Proof: `uv run pytest tests/unit/lens/test_sheet_spellings.py -q`.
- [x] 1.3 Parity regression on an authored flat_hierarchy-shaped case: sheet-path nets named by a local and a
  hierarchical label on a child sheet and a part with pins named like their numbers, left open.
  Proof: `tests/kicad/schematic/test_drawn_sheet_net_names.py` (kicad-needed, skipped by check-fast) on
  10.0.6 and 9.0.9 through the heavy-run lock: empty parity list, and the control respelling is reported.
  - 2026-11-05 on b845eb00 plus this change, wired layout: no parity item and control 2 `net_conflict` on
    10.0.6 and on 9.0.9 (pinned image); the samename probe pins all `equal` to netnames on both;
    `test_sheet_spellings.py` 3 passed, including a global label `/X` stored `{slash}X` in a drawn and in a
    wired generated build (coordinator's request).

## 2. Evidence, docs and changes in flight

- [x] 2.1 The S-1490 fact row of `docs/formats/kicad/schematic.md` and the `H-K-SCH-UNCONNECTED` note say the
  rule is applied; a fact row records the parity of a sheet-path net stored with raw slashes, with its test.
- [x] 2.2 `CHANGELOG.md` line under `## [Unreleased]`; every golden or snapshot that changes is listed in
  `design.md` and in the commit body, one line each with its reason.
- [x] 2.3 c0384 task 1.4 points here.
- [x] 2.4 `openspec validate c0408-built-net-spelling --strict`.

## 3. Closure

- [x] 3.1 Root-owned: `ci-complete` on the exact commit (coverage audit included), then archive.

  Closed on lote-23 CI 42081905514 (all jobs green, ci-complete with coverage audit) on 5ab9d6452, fast-forwarded to dev.
