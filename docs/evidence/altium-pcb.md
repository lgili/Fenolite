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
| `tests/data/altium/blink/blink.PcbDoc` | `5e084d8537812021ad65ca87b11163ae82aaa669221862d27feaef75162e894f` |
| `tests/data/altium/blink/blink.PcbLib` | `8fca33bda63bc3846e99478aa76f20e248026aefa0addd6e6e4ce9e9314c0082` |
| `tests/data/altium/blink/blink.PrjPcb` | `6d022f120a50b3959d3f35f0ce45686ae852d203b1cd42221fa456df9bc3b18e` |
| `tests/data/altium/blink/blink.SchDoc` | `e35c86d80da829e2cf7eba288fe2b5fff482619a921617c1e7bc3032692b1944` |
| `tests/data/altium/blink/blink.SchLib` | `4f3accb1f9634c7cedd305240493e6d6e9a2cfde3d3e0ff0aee0a75e6387517e` |

### Report of 2026-10-03 and the files since

The maintainer opened the first `blink.PcbLib` (SHA-256 `dbe1aef8…025a`, the stream set of AltiumSharp
version 1 alone) in an Altium Designer trial: a "catastrophic" error, and the same for a library without
footprints. The library is since written in the form Altium saves (`docs/formats/altium/pcb-library.md`:
the 53-byte `FileHeader`, the whole board record in `Library/Data`, the `Library` side streams), and
`blink.PcbDoc` carries the id block of `FileHeaderSix`; the digests above are the new files. Step D1 is to
be repeated on them. If the library opens but a footprint looks wrong, report which of pads, lines or arcs:
their records keep the short forms of `pcb-records.md` (`H-A-PCB-PAD`, `H-A-PCB-GRAPHICS`).

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

### The document

`blink.PcbDoc` is experimental: a 50 × 30 mm two-layer board whose lower-left corner lies at (1000 mil,
1000 mil), the three components at their script placements, their pads, silkscreen, fabrication and
courtyard graphics, the designators (comments hidden) and the nets on the pads; no routing.

| component | layer | rotation | footprint |
|---|---|---|---|
| `D1` | BOTTOM | 0 | `Mini_LED_THT_3mm` |
| `R1` | TOP | 0 | `Mini_R_0603` |
| `U1` | TOP | 0 | `Mini_QFP-32_7x7mm_P0.8mm` |

Pad nets (every other pad has no net):

| ref | pad | net |
|---|---|---|
| D1 | 1 | GND |
| D1 | 2 | LED_A |
| R1 | 1 | LED_DRV |
| R1 | 2 | LED_A |
| U1 | 1 | LED_DRV |
| U1 | 9 | VIN |
| U1 | 10 | GND |

## Part P: the Altium 365 Viewer

No licence is needed. Upload only the files named here.

- **P1** (`blink.PcbDoc`, SHA-256 above): upload the document alone. Expected: the board outline, three
  components with their pads and designators, the silkscreen arcs and lines, and `D1` on the bottom side
  (its graphics on Bottom Overlay, Mechanical 14 and 16). Settles `H-A-PCB-DOC-VIEWER`, and supports
  `H-A-PCB-PAD`, `H-A-PCB-GRAPHICS` and `H-A-PCB-DOC-BOTTOM` for what the Viewer shows.
- **P2** (a Zip of `blink.PrjPcb`, `blink.SchDoc`, `blink.SchLib`, `blink.PcbLib` and `blink.PcbDoc`): upload
  the Zip as one project. Note whether the Viewer lists the project, the library and the document;
  supports `H-A-PCB-DOC-VIEWER` (the Viewer does not list `.PcbLib` among its inputs, S-0149).

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

- **D3** (`blink.PcbDoc` with the project, SHA-256 above, on a copy): open the document. Expected: no repair
  prompt, two copper layers, the board at the offset frame. Then run "Design » Update PCB Document" from
  `blink.SchDoc`: no component is added or removed (the unique ids match), no net changes, and `D1` stays
  on the bottom as in its KiCad build. Settles `H-A-PCB-DOC-OPEN`, `H-A-PCB-DOC-LINK`, `H-A-PCB-DOC-NETS`
  and `H-A-PCB-DOC-BOTTOM`.

Report per step: the tool and version, the date, and one generic outcome (as expected, or the first
message shown). Do not describe Altium's internals beyond what the step asks.
