## 1. Kit

- [x] 1.1 Author kit cases: a body flipped to the other side of its component, each model type the user
  interface offers, heights at the accepted limits; write the steps into the verification kit.
  - 2026-11-05: Part Z of `docs/evidence/altium-pcb.md` (cases Z1 to Z3; Z4 is c0175's model store per
    rotation) on the committed `body2` project and the authored CC0 `Box_2x1.step`; the kit builder and the
    saved-file reader are `tests/unit/backends/altium/test_part_z.py` (`-k kit`, `-k saved`). Proof: `uv run
    pytest tests/unit/backends/altium/test_part_z.py tests/unit/test_altium_verification_docs.py -q`. Kit
    built for the run: `~/fenolite-altium-checks/claude-2026-11-05/c0387-Z-bodies`.
- [x] 1.2 **Maintainer, in Altium Designer.** Run the cases and save the documents; read them with
  Fenolite's own reader and record each fact in `pcb-bodies.md` with its source and label.
  - 2026-11-05: OPEN, waiting on the Part Z run; the kit went to the altium-rounds-2 session.
  - 2026-11-05, done (S-1604). An agent ran Z1 to Z4 in AD 24.5.2.23 under the maintainer's delegation and
    the approved 24.5 scope. The four saved documents (outside the repository,
    `~/fenolite-altium-runs/2026-11-05-Z/`) were read by `FENOLITE_ALTIUM_PART_Z_SAVED=<folder> uv run pytest
    tests/unit/backends/altium/test_part_z.py -k saved -s`, 1 passed (with `FENOLITE_KIT_REVIEWED_PREFIX` for
    the VM file name in each header). The facts are in `pcb-bodies.md`, "Agent observations in AD 24.5
    (S-1604)", labelled `INFERRED`, so no level moves. The outcomes are in `docs/evidence/altium-pcb.md`,
    "Reports", 2026-11-05 Part Z.
  - Where the run differs from the steps: Place in a document leaves a body without a component, so the
    Z2 and Z4 bodies are not on `R1` or `U1`. A generic body has no height field. Z1's depth below the
    board face was not measured.
  - 2026-11-05: Z1 and Z3 saved by an agent run (S-1650) and read with Fenolite's reader after the privacy
    scan; the facts are in `pcb-bodies.md`, "Kit Part Z". Z2 (model types) and Z4 (c0175) are not saved yet.

## 2. Conversion

- [x] 2.1 Give known heights to the bodies a saved file proves; keep the others declared
  (`altium.import.body-unknown`). Proof: authored import tests and the env-gated saved files.
  - 2026-11-05: OPEN, waiting on task 1.2: no saved file proves a new case yet.
  - 2026-11-05, done for Z1 and Z3 (S-1650): a top part's body of projection 1 now gets the interval
    `-(T + overall)` to `-(T + standoff)` below the board (`adapter/bodies.py`); a bottom part's body of
    projection 0, a library body of the other face, model types other than 0 and 1 (Z2 not saved) and
    reversed heights (Z3: the panel never writes them) stay declared. The extrusion's start face is
    inferred, not measured; altium-rounds-2 was asked how far Z1's block lies below the board. Proof: `uv run
    pytest tests/unit/backends/altium/test_body_volume_import.py -q` and `FENOLITE_ALTIUM_PART_Z_SAVED=<saved>
    FENOLITE_KIT_REVIEWED_PREFIX=<VM work folder> uv run pytest tests/unit/backends/altium/test_part_z.py -k
    saved` passed.
  - 2026-11-05, corrected on Z1 to Z4 (coordinator, 2026-11-05): no reading gives the depth of Z1's block, so a
    top part's body of projection 1 stays declared again, and the conversion above is withdrawn. Z2 (S-1604)
    proves model types 2 (cylinder) and 3 (sphere): they now get the interval standoff to overall height,
    with their record's outline, the square around the shape. Proof: `uv run pytest
    tests/unit/backends/altium/test_body_volume_import.py -q` and the saved-file run of `test_part_z.py -k
    saved` on Z1 to Z4 passed.

## 3. Close

- [x] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.

  Closed on lote-23 CI 42081905514 (all jobs green, ci-complete with coverage audit) on 5ab9d6452, fast-forwarded to dev.
