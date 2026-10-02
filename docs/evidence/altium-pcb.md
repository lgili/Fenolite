# Altium PCB writers: the maintainer's check

This page is the protocol by which the maintainer checks the PCB files that `fenolite build --target
altium` writes for `examples/blink_2layer/design.py` (change c0035, capability altium-build, "PCB author
reports"). The files are committed under `tests/data/altium/blink/`; they are built from the authored CC0
mini library (`tests/data/libs/Mini_v9.*`), so they may be uploaded and shared.

- Results are recorded in `docs/hypotheses.md` as `ALTIUM-VERIFIED(author-report; <tool>; <YYYY-MM-DD>;
  no artefact)`, the tool being `A365 Viewer` or `AD <major>.<minor or x>`, with one generic outcome per
  step. No file made in Altium enters the repository.
- **Licence rule.** Part P uses the free Altium 365 Viewer (S-0149), which needs no licence. Part D needs
  Altium Designer under a licence the maintainer may use for Fenolite (`LEGAL.md`, block A, P3 and P4). A
  result obtained with an employer's licence, or any licence the maintainer may not use for this purpose,
  is **not recorded**: the rows it would settle stay `INFERRED` with a result that starts with
  `pending (author report)`.
- The KiCad oracles (`tests/kicad/altium/test_pcblib_oracle.py`, `test_pcbdoc_oracle.py`) check only what
  KiCad's importer reads; they never settle an Altium row.

## The committed files

`tests/unit/lens/test_altium_pcb_golden.py` checks that fresh builds give these bytes and that this table
names them.

| file | SHA-256 |
|---|---|
| `tests/data/altium/blink/blink.PcbLib` | `dbe1aef899cb7a8d16ad0dfb88fa10fe44715612c1144c66ec4cce948e05025a` |
| `tests/data/altium/blink/blink.PrjPcb` | `352fcc0d17f675eb84781538a5189a7a6c0c01de9c4e43289906e05d2494f75f` |
| `tests/data/altium/blink/blink.SchDoc` | `e35c86d80da829e2cf7eba288fe2b5fff482619a921617c1e7bc3032692b1944` |
| `tests/data/altium/blink/blink.SchLib` | `4f3accb1f9634c7cedd305240493e6d6e9a2cfde3d3e0ff0aee0a75e6387517e` |

### Pads of the library

Sizes and holes in binary units (1 unit = 2.54 nm; 708661 units = 1.8 mm, 354331 = 0.9 mm). "rounded" is a
round pad with alternate shape 9 and corner percentage 50 (KiCad ratio 0.25). Through-hole pads lie on
Multi-Layer, surface pads on the Top Layer.

| footprint | pad | shape | size | hole |
|---|---|---|---|---|
| `Mini_LED_THT_3mm` | 1 | rectangle | 708661 × 708661 | 354331 |
| `Mini_LED_THT_3mm` | 2 | round | 708661 × 708661 | 354331 |
| `Mini_QFP-32_7x7mm_P0.8mm` | 1…32 | rounded | 590551 × 216535 | 0 |
| `Mini_R_0603` | 1…2 | rounded | 354331 × 374016 | 0 |

Graphics: silkscreen lines and two arcs on Top Overlay; the fabrication outline (rectangle or circle) on
Mechanical 13; the courtyard on Mechanical 15. The filled pin-1 triangle of the QFP is not written
(`altium.primitive-dropped`); texts, properties and 3D model links are not written.

## Part D: Altium Designer

Each step needs a licence the maintainer may use for Fenolite (licence rule above). Work on copies.

- **D1** (`blink.PrjPcb`, `blink.SchDoc`, `blink.SchLib`, `blink.PcbLib`, SHA-256 above): open the project.
  Check that the project lists the PCB library, then open `blink.PcbLib`: the PCB Library panel lists the
  three footprints with no repair prompt; each footprint's pads, holes and shapes equal the pad table;
  the silkscreen, fabrication and courtyard graphics are visible on Top Overlay, Mechanical 13 and
  Mechanical 15. Settles `H-A-PCB-LIB-OPEN`, `H-A-PCB-PAD`, `H-A-PCB-GRAPHICS` and `H-A-PCB-PRJ`. When a
  footprint with a name longer than 31 characters is added to a test build, its full name is shown
  (`H-A-PCB-LIB-NAME`).
- **D2** (same files): add a new blank PCB document to the project and run "Design » Update PCB Document"
  from `blink.SchDoc`. Expected: every footprint is found in `blink.PcbLib`; no "footprint not found".
  Settles `H-A-PCB-ECO`.

Report per step: the tool and version, the date, and one generic outcome (as expected, or the first
message shown). Do not describe Altium's internals beyond what the step asks.
