## 1. Kit

- [x] 1.1 Author kit cases: a body flipped to the other side of its component, each model type the user
  interface offers, heights at the accepted limits; write the steps into the verification kit.
  - 2026-11-05: Part Z of `docs/evidence/altium-pcb.md` (cases Z1 to Z3; Z4 is c0175's model store per
    rotation) on the committed `body2` project and the authored CC0 `Box_2x1.step`; the kit builder and the
    saved-file reader are `tests/unit/backends/altium/test_part_z.py` (`-k kit`, `-k saved`). Proof: `uv run
    pytest tests/unit/backends/altium/test_part_z.py tests/unit/test_altium_verification_docs.py -q`. Kit
    built for the run: `~/fenolite-altium-checks/claude-2026-11-05/c0387-Z-bodies`.
- [ ] 1.2 **Maintainer, in Altium Designer.** Run the cases and save the documents; read them with
  Fenolite's own reader and record each fact in `pcb-bodies.md` with its source and label.
  - 2026-11-05: OPEN, waiting on the Part Z run; the kit went to the altium-rounds-2 session.

## 2. Conversion

- [ ] 2.1 Give known heights to the bodies a saved file proves; keep the others declared
  (`altium.import.body-unknown`). Proof: authored import tests and the env-gated saved files.
  - 2026-11-05: OPEN, waiting on task 1.2: no saved file proves a new case yet.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
