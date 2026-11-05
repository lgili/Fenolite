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

## 2. Conversion

- [ ] 2.1 Give known heights to the bodies a saved file proves; keep the others declared
  (`altium.import.body-unknown`). Proof: authored import tests and the env-gated saved files.
  - 2026-11-05: OPEN, waiting on task 1.2: no saved file proves a new case yet.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
