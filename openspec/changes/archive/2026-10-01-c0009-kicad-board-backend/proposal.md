## Why

Every later v0.1 change reads boards. Fenolite parses any `.kicad_pcb` as a tree (c0006) and knows its versions and tokens (c0007), but nothing maps a board to the neutral model yet. That reader must lose nothing: KiCad rejects unknown tokens in most heads (`H-K-TOK-STRICT`), and a board holds far more than v0.1 models (S-0001, S-0021). Parsing is not enough: the model must match KiCad's own exports (S-0022, S-0037). `kicad-cli` writes files next to the board it opens (S-0020), so oracle runs need one runner that works only on copies.

## What Changes

- `backends/base.py` and `backends/registry.py` (new): `Backend` protocol, `ReadResult`, `CapabilityReport`, registry. `fenolite capabilities` fills `result.backends`. ADR-0002 "KiCad file backend".
- `backends/kicad/cli.py` (new): the package `kicad-cli` runner (`find_kicad_cli`, `KicadCli`) on temporary copies in an isolated environment. `backends/kicad/ipcd356.py`: the IPC-D-356 parser, moved out of a test.
- `backends/kicad/pcb.py` (new): `read_board`, `rebuild_board`, `opaque_count`, `opaque_digests`; also `layers.py` and `_fpmap.py` (pad and graphic mapping shared with `mod.py`).
  - Reads 8.0 and newer; future headers are read but not editable.
  - Models the header, layers, nets in both forms, footprints and pads, tracks, arcs, vias, zones and fills, rule areas, points-only graphics and texts. Everything else stays an opaque slot in place.
  - Synthesises a circuit from footprints and pads.
- Model: `FootprintInstance.attributes`, `Via.via_type`, `ZoneFill.island`, `Zone.name`, the pad frame and import rules; `board.json` regenerated.
- Authored CC0 board `tests/data/kicad/board/two_layer.kicad_pcb`.
- Corpus read and same-version round trip (RT1) over the demos and upgraded third-party copies; placements and pads cross-checked with `pcb export pos` and `pcb export ipcd356`.
- `docs/formats/kicad/board.md`; source S-0050; hypotheses `H-K-PCB-*`, `H-K-UUID-KEEP`.

Estimate: 7.75 days (design, "Budget"). Writing and the rest of plan item 0009 move to c0017 and c0018.

## Capabilities

### New Capabilities
- `backend-protocol`: backend protocol, read results, capability reports, registry, layering of backend modules.
- `kicad-file-backend`: typed `.kicad_pcb` reading with slots, version policy, layers, nets, pad frame, zones, numbers, ids, issue codes, same-version rebuild and opaque counts.

### Modified Capabilities
- `design-model`: board entities read from file backends; components synthesised from a board (ADDED).
- `cli-contract`: backends in `capabilities` (ADDED).
- `corpus-policy`: upgraded copies keep their origin (ADDED).
- `kicad-oracle`: package runner; typed board reads agree with `kicad-cli` exports (ADDED).

## Non-goals

- Writing at a target, net-form conversion, created content, embedding, `--kicad-version`, `--allow-lossy` (c0017).
- `.kicad_mod`/`.kicad_dru` writers (c0018), `.kicad_pro` (c0010), `.kicad_wks` (c0012).
- `inspect --summary` (c0013), DRC reports (c0017), the runner's Docker mode (c0015).
- Settling the flip rule and pad-angle convention (c0017); byte identity, path census, throughput (c0020).
- Modelling setup, stackup, title block, groups, dimensions, teardrops, text effects, fill settings, footprint graphics; mixed line/arc contours (v0.2); outline assembly (c0022); boards over 20 MB and streaming parse.

## Evidence level required

- Lossless read and same-version rebuild: `CORPUS-VERIFIED` (`H-K-PCB-READ`) over two origins: non-heavy KiCad demos at 10.0.6 and 9.0.9.1, and third-party boards upgraded with `pcb upgrade --force` on 10.0.6. Census labels (`H-K-UNIT`, `H-K-PCB-UUID`, `H-K-PCB-ZONE`) need both origins.
- Placements, relative pad positions, pad nets: `KICAD-VERIFIED` against `pcb export pos` and `pcb export ipcd356` (`H-K-PCB-POS`); demos on 10.0.6 (`kicad-10`), the authored board on 10.0.6 and 9.0.9 (`kicad-9`). Rebuilt boards load on the same versions.
- Field meanings, layer kinds, circuit synthesis: `INFERRED` (`H-K-PCB-READ`). The pad-angle convention stays `INFERRED` (`H-G-PAD-ANGLE-ABS`) until c0017.
- Runner, protocol, registry: mechanical (unit tests, fake `kicad-cli`).

## Impact

- New modules `backends/base.py`, `backends/registry.py`, `backends/kicad/{backend,cli,ipcd356,layers,_fpmap,pcb}.py`; tests under `tests/unit/backends`, `tests/corpus`, `tests/kicad/board`.
- Model: four defaulted fields, one `Design.validate()` rule, `board.json` regenerated. No runtime dependency; `capabilities` gains backend entries.
- Rows in `PROVENANCE.md`, `LEGAL-ANNEX.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`.
- Depends on c0014 (machine-checked register) and c0006–c0008 (`sexpr`, `slots`, `versions`, token inventory, `mod.py`).
