# Tasks: c0411

## 1. Sources and model

- [x] 1.1 Read and record S-1720…S-1729 (KiCad footprint zone format and rule areas, Altium footprint
  keep-outs); decide the open points of design.md. S-1720 and S-1721 recorded (the Altium side needed no
  new source: S-1710 of c0410); decisions in design.md.
- [x] 1.2 `FootprintDef.keepouts` and `FootprintInstance.keepouts`; canonical JSON omits empty; schemas,
  `frozen-v0.json` and the model review inventory regenerated; `docs/design-model.md`.

## 2. Altium

- [x] 2.1 The library and board adapters make footprint rule areas; the `footprint-keepouts` loss is gone.
  Proof: `uv run pytest tests/unit/backends/altium/adapter/test_keepout_primitives.py -q`.
- [x] 2.2 The PcbLib and PcbDoc writers write footprint rule areas as keep-out regions. Proof:
  `uv run pytest tests/unit/backends/altium/test_footprint_keepouts.py -q`.

## 3. Placement and checks

- [x] 3.1 Placing a definition carries its rule areas (frame, side); one helper gives a board's rule areas
  for the checks (`model.board.rule_areas`, `area_owners`). Proof: the placement tests of
  `test_footprint_zones.py` and `test_footprint_keepouts.py`, and the focused run of the consumers.

## 4. KiCad

- [x] 4.1 The footprint reader projects keep-out zones; the `.kicad_mod` and board writers write them; a
  read-write round trip keeps bytes. Proof: `uv run pytest tests/unit/backends/kicad/test_footprint_zones.py -q`.
- [x] 4.2 Oracle: the c0410 library through Fenolite and through `fp upgrade` 10.0.6 gives the same rule
  areas; a board placing it loads in `kicad-cli pcb drc`. Proof:
  `uv run pytest tests/kicad/altium/test_keepout_import.py -q` (local `kicad-cli` 10.0.6, 2026-11-05).

## 5. Close

- [x] 5.1 ruff, format, `pyright src`, focused tests, CHANGELOG, `openspec validate --strict`. Proof: ruff and format clean on the 42 touched files, `pyright src` 0 errors, `openspec validate --strict` valid, generators `--check` clean; focused run (heavy lock, -n 2) 20 failed, 15 099 passed, the 20 the same as on clean 8872e092; touched files pass on 3.11.
- [ ] 5.2 `make check-fast` on the integrated batch and the full CI (coordinator).
