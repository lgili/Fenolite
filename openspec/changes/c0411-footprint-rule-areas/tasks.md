# Tasks: c0411

Do not start before c0409 has landed in a batch (coordinator's go).

## 1. Sources and model

- [ ] 1.1 Read and record S-1720…S-1729 (KiCad footprint zone format and rule areas, Altium footprint
  keep-outs); decide the open points of design.md.
- [ ] 1.2 `FootprintDef.keepouts` and `FootprintInstance.keepouts`; canonical JSON omits empty; schemas,
  `frozen-v0.json` and the model review inventory regenerated; `docs/design-model.md`.

## 2. Altium

- [ ] 2.1 The library and board adapters make footprint rule areas; the `footprint-keepouts` loss is gone.
- [ ] 2.2 The PcbLib and PcbDoc writers write footprint rule areas as keep-out regions.

## 3. Placement and checks

- [ ] 3.1 Placing a definition carries its rule areas (frame, side); one helper gives a board's rule areas
  for the checks.

## 4. KiCad

- [ ] 4.1 The footprint reader projects keep-out zones; the `.kicad_mod` and board writers write them; a
  read-write round trip keeps bytes.
- [ ] 4.2 Oracle: the c0410 library through Fenolite and through `fp upgrade` 10.0.6 gives the same rule
  areas; a board placing it loads in `kicad-cli pcb drc`.

## 5. Close

- [ ] 5.1 ruff, format, `pyright src`, focused tests, CHANGELOG, `openspec validate --strict`.
- [ ] 5.2 `make check-fast` on the integrated batch and the full CI (coordinator).
