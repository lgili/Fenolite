# A library of whole boards as code

Status: **research, nothing here is implemented**. Date: 2026-10-29. Not legal advice; the licence
readings are INFERRED from the licence texts.

The goal is a library of complete public boards, **schematic and layout**, stored as Fenolite code. It
serves three purposes:

- users can start from a real board;
- marketing can show real boards;
- the boards become a corpus to test and improve Fenolite's generators.

This means reading public open-hardware projects and converting them to `design.py`, with a proof that
the code rebuilds the original.

## 1. Where Fenolite stands

- **Reads:** KiCad 8–10 boards and schematics and Altium documents, into the design model. Older KiCad
  files are refused with a hint to run `kicad-cli pcb upgrade` / `sch upgrade`.
- **Converts:** KiCad ↔ Altium (`fenolite convert`), reporting what is kept, changed or lost.
- **Compares:** `fenolite equivalent` at five levels (components, netlist, footprints and pads,
  placement, routing), plus `diff`, `parity`, `roundtrip` and a visual compare.
- **Has no board → code path.** Nothing writes a `design.py` from a board. `sync --to-source` writes only
  `placements.toml` for an existing script.
- **The schematic is generated, not drawn:** no bent wires, junctions, buses, hierarchical labels or
  repeated sheets. A hand-drawn sheet cannot be reproduced.
- **What the DSL cannot express yet:**
  - copper counts other than 2/4/6/8;
  - copper text and logos;
  - custom pads in authored footprints (a vendored footprint works);
  - teardrops, groups, images, most dimension types;
  - footprint-instance overrides.
- **Corpus policy:** the corpus manifest declares 405 public files, all non-embeddable. Derived or
  upgraded copies may never be committed. AGENTS.md forbids examples taken from any organisation.

## 2. Sources

| Source | Size | Format | Licence | Use |
|---|---|---|---|---|
| **KiCad `demos/`** | 18 projects | KiCad 9/10, no upgrade needed | per project: Apache-2.0 (`jetson-agx-thor-baseboard`, `tiny_tapeout`), CERN-OHL-P (`royalblue54L_feather`), CERN-OHL-S (`cm5_minima`), CC BY-SA 4.0 (`openair-max`), CERN-OHL (`vme-wren`), GPL-2+ (older demos); **`stickhub` is CC BY-NC-SA, excluded** | **first** |
| **Antmicro** | dozens | KiCad 6+ (a few Altium) | Apache-2.0 | second: professional, permissive |
| CERN OHWR, MNT Research, Libre Solar, Olimex (KiCad era) | hundreds | KiCad, Altium | CERN-OHL v1.2/v2 | third: complex, well known; modification notices required; MNT forbids its logos on derivatives |
| OSHWA certified directory | about 2 900 | any | a licence triple per project; no NC/ND allowed | discovery index (token API); confirm each repo's licence |
| SparkFun, Adafruit (KiCad era), Raspberry Pi CM4/CM5 IO | many | KiCad (older: Eagle) | CC BY-SA, CC BY, CC0, BSD | later; Eagle only as import tests |
| GitHub long tail | 5 000+ `kicad` repos | KiCad 4–10 | often none | last; allow-listed licences only, API at modest rate |
| EasyEDA / OSHWLab | very large | EasyEDA | terms forbid scraping, bulk collection and AI training | **never** |
| Altium's bundled examples, Pine64, Raspberry Pi SBCs, repos without a licence | — | — | no redistribution grant or layout not released | **never** |

Sources:
- KiCad: gitlab.com/kicad/code/kicad (`demos/`) and its per-project LICENSE files; the Debian copyright file.
- Antmicro: openhardware.antmicro.com.
- OSHWA: certification.oshwa.org/requirements.html.
- GitHub rules: docs.github.com (search API limits, Acceptable Use Policy).
- EasyEDA: easyeda.com/legal §VII.
- Trademarks: arduino.cc trademark guide; MNT Reform handbook, credits.

## 3. Licences

**A conversion is treated as a derivative (modified source) under every licence.**
- CERN-OHL v2 asks for:
  - a dated modification notice;
  - kept notices and a Source Location;
  - the same licence.
- CC BY-SA 4.0 lets a pure format change stay "Licensed Material" (§2(a)(4)), but attribution and the
  same licence still apply.

| Licence | What a converted board must carry | Allowed |
|---|---|---|
| CERN-OHL-P/W/S v2, v1.2 | upstream notices, dated modification notice, same licence, Source Location | yes |
| CC BY 4.0, CC BY-SA 4.0/3.0/2.5, CC0 | attribution, "indicate changes", same licence for SA | yes |
| MIT, BSD, Apache-2.0, Solderpad | copyright and licence, NOTICE and stated changes (Apache, Solderpad) | yes |
| GPL-2+/3, TAPR OHL | source (the Python *is* the source), notices, changes marked | yes |
| CC BY-NC, ND, no licence, platform-restricted | — | **no** |

- **AI and training:** CC licences say nothing about training. Their conditions attach when models or
  outputs are shared. Platform terms override this (EasyEDA forbids it), and the community is hostile to
  unannounced harvesting. Fenolite uses the boards as **test and benchmark inputs** and says so publicly.
  Any training use is a separate, announced decision that respects machine-readable opt-outs.
- **Marketing:** show attribution next to every image ("converted from the open-source design X by Y,
  licence Z") and use renders made by Fenolite. Never use third-party logos or names in a way that implies
  endorsement: "an Arduino-compatible board", not "an Arduino board".
- **Others' mistakes to avoid:** blanket relicensing of a scraped dataset (the "Open Schematics" case) and
  per-board licences dropped (PCBWorld, PCBench). Fenolite keeps a licence and a provenance record **per
  board**.

## 4. The proposal

### 4.1 Board → code

```
fenolite import upstream/cm5_minima/cm5_minima.kicad_pro --to python --out boards/cern-ohl-s/cm5_minima --dry-run
fenolite import ... --confirm --plan <id>
```

It writes:

```
boards/cern-ohl-s/cm5_minima/
  design.py              # parts, nets, rules, stackup, outline, zones, tracks, vias, placements: all as code
  schematic.toml         # the drawn schematic: symbol poses, wires, junctions, labels, buses, sheets (4.2)
  lib/                   # footprints and symbols used, vendored from the project (fenolite library)
  LICENSE  NOTICE  PROVENANCE.json  README.md
```

```python
# design.py (excerpt, generated)
# SPDX-License-Identifier: CERN-OHL-S-2.0
# Converted from https://gitlab.com/kicad/code/kicad/-/tree/<sha>/demos/cm5_minima by Fenolite 0.7.0
# on 2026-10-30; modified: format conversion to the Fenolite DSL. Original notices in NOTICE.
from fenolite.dsl import Design, Net, Part, connect, mm, via_step

design = Design("cm5_minima")
design.board(outline=OUTLINE, copper=4)
design.stackup(*STACK)
u1 = Part("U1", "cm5_minima:CM5", footprint="cm5_minima:CM5_Connector", value="CM5")
u1.place(mm("42.5"), mm("31.75"), rot=0, locked=True)
...
connect(Net("+5V"), u1["77"], c12[1], j1[1])
design.track("t0001", u1.pad("77"), (mm("40.1"), mm("28.0")), c12.pad(1), layer="F.Cu", width=mm("0.5"))
design.via("v0001", (mm("40.1"), mm("28.0")), net="+5V", diameter=mm("0.6"), drill=mm("0.3"))
design.zone("GND", layers=("In1.Cu",), outline=OUTLINE, priority=0)
design.load_schematic("schematic.toml")  # the drawn schematic, not the generated one
```

- **Design choices:**
  - The emitter writes **explicit code** (every item keyed, locked), so a foreign board joins the lens
    without guessing.
  - Large boards split into modules per sheet.
  - Repeated copper uses compact helper tables instead of one call per segment.
- **Input versions:** older KiCad files are upgraded with `kicad-cli` as a subprocess on a copy, with the
  versions and SHA-256s recorded. Altium boards use Fenolite's own reader.

### 4.2 A drawn schematic

The generated schematic stays the default. A board imported from elsewhere needs its drawing kept: a
`schematic.toml` (schema `fenolite.drawn-schematic.v0`) holds:
- symbol poses;
- wire polylines;
- junctions, labels (local, global, hierarchical) and buses;
- sheets and sheet pins, including repeated sheets.

The writer emits it as KiCad (and Altium) instead of the generator's layout. `fenolite check` verifies
that its connectivity equals the code's netlist, so code and drawing cannot drift apart.

### 4.3 DSL coverage

Close the holes a real board hits:
- copper layer counts 1 to 32;
- copper text and graphics;
- custom, chamfered and trapezoid pads;
- teardrops;
- groups;
- images;
- radial, leader and centre dimensions;
- zone arcs;
- footprint-instance overrides (clearances, edited pads, field fonts);
- 3D model references by name.

Each one is either expressible or kept as a **verbatim opaque item** with a finding, never silently
dropped.

### 4.4 The fidelity proof

```
fenolite verify-source boards/cern-ohl-s/cm5_minima/design.py --against upstream/cm5_minima/
```

It builds the code in a temporary folder and compares the result with the original:

| Level | What | Today |
|---|---|---|
| 1–4 | components, netlist, footprints and pads, placement | exists |
| 5 strict | every track, arc and via matched item by item (not only connectivity and length) | **new** |
| 6 | rules: net classes, clearances, custom rules, stackup | **new** |
| 7 | exact geometry: outline, zones (outline, not fill), drawings, text | **new** |
| 8 | presentation: rendered images of every layer and the schematic compared pixel by pixel within a tolerance | **new** |
| S | schematic: drawn connectivity and geometry against the original | **new** |

- A board enters the library **only with a passing proof at every level**, or with each difference
  written down and accepted in `PROVENANCE.json`.
- The proof runs in the library's CI on every Fenolite version, so a regression in a reader, the DSL or a
  writer shows up as a failed board.
- This is what turns the library into a **benchmark**.

### 4.5 The library repository

- **`fenolite-library`, separate from the tool:**
  - one folder per board, grouped by licence family;
  - each folder carries its upstream LICENSE, NOTICE and a `PROVENANCE.json`, holding:
    - upstream URL and commit;
    - authors and SPDX id;
    - Fenolite version and conversion steps;
    - tool versions;
    - proof result.
- **Licences:** an allow-list and a deny-list (section 3), checked by CI. The top README says "each
  directory keeps its upstream licence".
- **CI:** regenerates each board from its pinned upstream commit, so every conversion is reproducible.
- **Gallery:** a static page of renders made by Fenolite, each with attribution and licence. Marketing
  uses only this.
- **The tool repository** stays Apache-2.0 with no third-party board. AGENTS.md gains one sentence saying
  that converted third-party boards live only in `fenolite-library`, under their own licences, with
  provenance. That requires the maintainer's decision.
- **Courtesy:** tell the authors of featured boards and link back to them; ask Antmicro, CERN and MNT
  before featuring their boards in marketing.

### 4.6 First boards

1. The KiCad demos with a usable licence: Apache-2.0, CERN-OHL-P/S, CC BY-SA, GPL-2+. Not `stickhub`.
2. A handful of Antmicro boards (Apache-2.0).
3. One CERN-OHL board each from CERN OHWR, MNT and Libre Solar.

Then the OSHWA index, filtered to KiCad sources.

## 5. Proposed changes

| Id | Change | Depends on | Size |
|---|---|---|---|
| c0275 | `board-to-code`: `fenolite import --to python` emitter (code, modules per sheet, vendored lib, provenance header), lens adoption of imported boards, upgrade of old files through `kicad-cli` on copies | c0249 | L |
| c0276 | `drawn-schematic`: `fenolite.drawn-schematic.v0`, writer for KiCad and Altium, connectivity check against the code | c0269 | L |
| c0277 | `dsl-board-coverage`: the expressiveness holes of 4.3, each expressible or kept as an opaque item with a finding | — | L |
| c0278 | `fidelity-proof`: equivalence level 5 strict, levels 6–8 and S, `fenolite verify-source`, a round-trip test category | c0275, c0276 | M |
| c0279 | `board-library`: the `fenolite-library` repository layout, provenance schema, licence lists, CI regeneration and proof, gallery with attribution, the AGENTS.md sentence (maintainer decision), first boards | c0275–c0278 | M |

## 6. Questions for the maintainer

1. **AGENTS.md:** may converted third-party boards live in a separate `fenolite-library` repository under
   their own licences? Recommended: yes, never in the tool repository.
2. **Split by licence:** one repository with licence folders (recommended), or two repositories
   (permissive and copyleft)?
3. **Training:** keep the boards as test and benchmark inputs only, and decide training separately and
   publicly. Recommended: yes.
4. **Featured boards in marketing:** ask the authors first. Recommended: yes for organisations, and
   attribution always.
