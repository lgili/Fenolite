## ADDED Requirements

### Requirement: Anchored copper passes the oracle
`tests/kicad/frame/test_anchor_oracle.py` (markers `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli`, with the probe rules of "Script copper passes the oracle", where anchored points land, that a thermal array in a pad passes KiCad's DRC, and that anchored copper follows a part moved by `fenolite place`. Its bench, `tests/kicad/frame/_anchorbench.py`, MUST be design scripts built by `fenolite build` for the running major from the authored footprint `Frame:Frame_Anchor` and a project-authored symbol of four pins, and the DRC MUST be judged only from the JSON report read with `read_drc_report`.
- **Frame** (`H-G-FRAME-ANCHOR`). `Frame_Anchor` placed at 0° and at 90° on the top and at 30° on the bottom, each with vias of a marker net: anchored by `part.at` at the library positions of pads `1` and `3`, by `pad.at` at an offset inside pad `4`, and by `pad.at` on a 3 × 3 grid of 1 mm in pad `4`. The bench is built with `--copper-check warn`, because each marker shorts its pad on purpose.
  - `copper-anchor-frame` (majors 9 and 10): `equal` when the report names every marker via with the net of the pad its anchor names, since KiCad gives a via the net of the pad it touches (`H-K-VIA-RENET`), and no `shorting_items` names a marker; `different` otherwise.
  - `copper-anchor-frame-control` (majors 9 and 10): the offsets of the bottom part given as board points computed without the mirror; `different` when the vias of pads `1` and `3` are named with each other's nets.
- **Thermal array** (`H-K-VIA-IN-PAD`). `Frame_Anchor` with pad `4` on its own net and a stitch whose `region` is that pad, pitch 1 mm, vias of 0.6 mm and 0.3 mm, margin 0.1 mm.
  - `copper-anchor-thermal` (majors 9 and 10): with a track of the net through the via centres on the other outer layer, its points anchored with `pad.at`; `absent` when no violation and no unconnected item names a via or the track.
  - `copper-anchor-thermal-alone` (majors 9 and 10): without the track; `present` when each via gives exactly one `via_dangling` warning and nothing else names it.
  - The copper guard of both builds MUST report nothing.
- **Moved part** (`H-G-FRAME-ANCHOR`). The joined thermal bench with the part unlocked, built, then moved and turned with `fenolite place <board> --move U1=<x>,<y>,90 --confirm`, then built again.
  - `copper-anchor-moved` (majors 9 and 10): `absent` when the array lies in pad `4` at its new place: no `via_dangling` and no unconnected item; the rebuild MUST report `kicad.copper.regenerated` for each via and track of the array.
  - `copper-anchor-moved-control` (majors 9 and 10): the same array and track given to `design.via` and `Design.track` as board points; `present` when, after the same move and rebuild, its vias give `via_dangling`.
- An outcome other than the expected one MUST stop that part of the change, and the register row MUST record what KiCad showed. The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and built files MUST NOT be committed.

#### Scenario: Anchors land in their pads
- **WHEN** `uv run pytest tests/kicad/frame/test_anchor_oracle.py -k frame` runs on the local KiCad 10.0.6 and in the `kicad-9` job
- **THEN** `copper-anchor-frame` is `equal` and `copper-anchor-frame-control` is `different` on both majors

#### Scenario: A thermal array passes DRC
- **WHEN** `uv run pytest tests/kicad/frame/test_anchor_oracle.py -k thermal` runs on both majors
- **THEN** `copper-anchor-thermal` is `absent` and `copper-anchor-thermal-alone` is `present` on both

#### Scenario: Anchored copper follows a moved part
- **WHEN** `uv run pytest tests/kicad/frame/test_anchor_oracle.py -k moved` runs on both majors
- **THEN** `copper-anchor-moved` is `absent` and `copper-anchor-moved-control` is `present` on both
