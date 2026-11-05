# Design: c0385 catalog pin order

## Context

The footprint frame is X right, Y down. The catalog package records were written from datasheet coordinates
that are Y up. For example, S-0372 lists the SOT-223 leads at y −3.10 mm, below the body, and the records
kept that sign. The result: in the top view, pad 1 sits where the part's pin 1 is seen from below, and the
leads run clockwise. `drawing = 0` of the family generators reproduces the 0.6 placement byte for byte, so
it carries the same mirror. `drawing = 1` was already counter-clockwise.

Three things hid the mirror:

- `library.pin1-location` waivers with the reason "Legacy shipped catalog drawing keeps its established
  orientation …";
- no rule judged the order of the pads, only where pad 1 sits;
- `tools/catalog/render_footprints.py` drew Y up, so a mirrored land looked like its datasheet in the
  review gallery.

## Decisions

### D1: Mirror about the X axis only

Every chiral record is mirrored with y → −y. This applies to pad positions, graphic points (a rect is
stored again as its min and max corners), and pad and slot rotations ((−r) mod 180°). Pad numbers, sizes,
kinds, drills and layers stay as they are.

A per-package choice (transpose, a 180° turn, and so on) could keep pad 1 at the upper left in more parts.
Instead, X-mirror is used everywhere, for three reasons:

- the change is one uniform rule a reviewer can check;
- the rotation of each part on the board stays as it was;
- the interface digest (pad numbers and kinds) does not change, so no device, pin map or symbol changes.

Each mirrored record is raised to version `1.1.0`, the MINOR step a changed output requires
(`records.version_problems`). `tools/catalog/versions.py --update` rewrote `VERSIONS.toml` and raised
the catalog version by PATCH to `1.0.2`.

### D2: Which records change

The scratch scan ran `library.pin-order` and looked at the body outline of every catalog package.

**Changed (55 records):**

- **51 records whose numbered leads turn clockwise:**
  - DIP: DIP4_Vishay_VO617A, DIP6_Vishay_CNY17, DIP8/14/16/20_Microchip_P, DIP28_Microchip_SP
  - SOIC: SOIC_8, SOIC14_TI_D0014A, SOIC16_TI_D0016A, SOIC20_TI_DW0020A, SOIC24_Microchip_K3X,
    SOIC28_MPS_Wide
  - TSSOP, MSOP, SSOP: TSSOP8/14/20_Diodes, TSSOP16_Diodes_A1, TSSOP24_TI_PW0024A,
    TSSOP28_Microchip_NRB, MSOP8/10_Diodes, SSOP16_Diodes_CJ
  - SOT-23 class: SOT23_3, SOT23_5, SOT23_6_TI_DBV0006A, SC70_5, SC70_6_TI_DCK0006A,
    SOT323_3_Diodes_Standard, SOT523_3_Diodes, SOT563_6_Diodes, SOT883_3_Nexperia_DFN1006,
    SOT143_4_Diodes
  - QFP: LQFP32_P0.8, LQFP48_TI_PT0048A, LQFP64_TI_PM0064A, LQFP100_TI_PZ0100A, TQFP44_Microchip_PT
  - QFN, DFN: QFN16_Diodes_W3030_A1, QFN20_Diodes_U4040, QFN24_Diodes_W4040_SWP_A1,
    QFN28_Diodes_W5050_A1, QFN32_Diodes_W5050, QFN48_TI_RGZ0048A, DFN6_Diodes_W2020_US,
    DFN8_Diodes_W3030_UXF
  - Others: Crystal_3225_Abracon_ABM8, LED5050_Worldsemi_WS2812B_V6, SOT89_3
  - Tab parts: SOT223_3_Diodes, TO252_3_Diodes_Standard, TO263_3_Diodes_Standard. Their tab pad hid the
    turn from a plain shoelace sum; the rule reads their lead row against the tab.
- **4 single-row parts whose body outline is chiral:**
  - JST_XH_B2B_XH_A and JST_XH_B4B_XH_A: the housing edge stands 2.35 mm on one side of the pad line
    and 3.4 mm on the other;
  - MicroUSB_B_Wurth_629105150521: signal pads, then shell pegs, then the board edge;
  - TO220_3_Diodes_Vertical: the tab side of the body.

  Their pads alone show no order, so `library.pin-order` cannot judge them. They were mirrored so that
  the body and pads stay one consistent part:
  - S-0410 page 2 PCB-top view puts JST pin 1 at the right with the 2.35 mm edge below the pad line;
  - the KiCad stock footprints (S-0018, read only as a cross-check) agree for the JST, USB and TO-220
    parts.

**Unchanged:** lands without chirality.

- Two-pad parts: chips, molded diodes, LEDs, crystals with two pads, fuses.
- Header_1xN: a single row read backwards is the same row turned 180°.
- Header_2x3 and Header_2x5: a mirrored zig-zag is the same zig-zag numbered from the adjacent corner,
  which is the same land turned.
- SW_Tact parts: the common pairs stay pairs.
- Mounting holes and the test point.

### D3: The waivers

- **Removed:** 48 `library.pin1-location` waivers, because pad 1 now sits above-left of the centroid.
- **Kept, with a source-specific reason:** six parts whose cited top view itself draws pad 1 at the
  lower left keep that orientation, now numbered counter-clockwise as the source numbers them. These
  are Crystal_3225_Abracon_ABM8 (S-0416), SOT143_4_Diodes, SOT89_3, SOT223_3_Diodes,
  TO252_3_Diodes_Standard and TO263_3_Diodes_Standard. They keep a `library.pin1-location` waiver whose
  reason names that source.
- **JST_XH_B4B_XH_A:** keeps its pin1-location waiver, with a reason that names S-0410.
- **`library.pin1-marker` waivers:** kept wherever they still match a finding; the check reports any
  that do not (`library.waiver-unused`).

### D4: The rule `library.pin-order`

`pin_order(footprint)` returns `"counter-clockwise"`, `"clockwise"` or `None` (not judged). The rule is
an error when the result is `"clockwise"`.

1. Only the electrical pads numbered `1`, `2`, ... count. Each number's lead is its smallest pad.
2. A pad larger than `TAB_AREA_RATIO = 2` times the median pad area is a tab or exposed pad, not a lead.
3. Leads on one line are judged only against one tab beside the middle of the row (SOT-89, SOT-223,
   TO-252, TO-263). All of the following must hold:
   - the leads run strictly one way;
   - the tab projects inside the row;
   - every lead stands less than half the tab's distance from the line.

   Leads on one line without such a tab give `None`. This covers headers, terminal blocks with two pads
   per number, JST and TO-220.
4. Otherwise the leads must outline the land:
   - three leads: the SOT-23 shape;
   - four leads: pairs 1-2 and 3-4 on opposite sides;
   - five or more leads: on the sides of their bounding box, each side one run of the numbering.

   Anything else gives `None`: zig-zags, grids, switch pairs, two-pad parts, staggered TO-92 rows.
5. Around the centre of the pads' extent, every turn from one lead to the next must have one sign. That
   sign is the answer.

All arithmetic is integer: cross products, and the centre in doubled coordinates.

**False-positive survey.** Read only, against the installed KiCad 9 stock library, about 15,450
footprints: 2,248 counter-clockwise, 13,029 not judged, 173 clockwise. The clockwise ones are mostly:

- parts the library itself marks clockwise: `*_ClockwisePinNumbering` (Bosch LGA, ROHM SOT-457,
  Mini-Circuits), `*_CW` PLCC-4 LEDs, `SOT-143R`, `*_Reverse`;
- devices numbered by their own maker's scheme: transformers, relays, XLR jacks, power modules,
  current sensors, displays.

So the rule is right for perimeter-numbered IC outlines and cannot know a maker's private scheme. For
that reason:

- **Records:** the rule is an error, and a record of a part numbered clockwise by its maker waives it.
  The waiver must name the source (D5).
- **Plain library items with no record** (a `.kicad_mod`, `.pretty` or Altium library checked as is):
  the finding is a `warning`. Such an item has no waiver to carry, and an error that cannot be silenced
  would refuse every library holding one Bosch LGA. `ISSUE_CODES["library.pin-order"]` lists
  `warning`, and `check_footprint(..., recorded=False)` gives it.

### D5: A pin-order waiver names its source

`apply_waivers` raises `FormatError` (`library.record-invalid`) for a `library.pin-order` waiver whose
reason names no S- or D- source id (`\b[SD]-\d{4}\b`). A generic reason ("legacy orientation") is the
exact mechanism that let the mirror ship, so it is refused. The reviewer still judges whether the cited
source really numbers the part clockwise; the rule only guarantees there is a citation to check.

### D6: The review renderer draws Y down

`tools/catalog/render_footprints.py` now draws the footprint frame as KiCad does. The gallery SVGs were
drawn again. The 55 mirrored lands render as before: the old Y-up picture of the mirrored land equals
the new Y-down picture of the corrected one. The achiral lands now render as they really are, flipped
vertically against the old pictures.

### D7: The net-role reference boards keep their copper; their synthetic symbols are renumbered

The net-role reference boards (`examples/roles/{buck_shunt,half_bridge,bms}`) and the role benches of
the routing tests place three synthetic symbols of `tests/data/libs/Roles.kicad_sym` on mirrored catalog
lands:

- `Roles_Sense_Amplifier` on `SOT23_5`;
- `Roles_HalfBridge_Driver` on `SOIC_8`;
- `Roles_Cell_Monitor` on `SOIC14_TI_D0014A`.

Their hand-drawn copper (tracks to fixed waypoints, zones, vias) was laid out for the mirrored lands. On
the corrected lands, about 144 role tests (`tests/unit/roles`, `tests/unit/routing/test_roleroute.py`,
`test_propose.py`, `tests/unit/cli/test_route_cmd.py`) failed: builds refused with copper shorts, and
loops and Kelvin entries were measured on other pads.

Each symbol's own description says "not a device pinout". So the change renumbers their pins instead of
redrawing three boards and their designed findings. The X-mirror puts pad σ(n) where pad n was, and σ is
its own inverse:

| Package | σ |
| --- | --- |
| `SOT23_5` | 1↔3, 4↔5 |
| `SOIC_8` | 1↔4, 2↔3, 5↔8, 6↔7 |
| `SOIC14_TI_D0014A` | 1↔7, 2↔6, 3↔5, 8↔14, 9↔13, 10↔12 |

Each pin numbered n is now numbered σ(n), and every `u.pad(n)` of those parts in the boards and benches
is now `u.pad(σ(n))`. Every function therefore sits on the same copper position as before. The boards,
their geometry and their designed findings are unchanged.

The tests that name those pads by label now name the new numbers. For example, the buck's Kelvin
receiver `U3-3`/`U3-4` is now `U3-1`/`U3-5`, and the half bridge's gate return `U2-6` is now `U2-7`.
These tests are in `test_infer_reference.py`, `test_routes.py`, `test_critical_reference.py` and
`test_reference_boards.py`. No assertion changed its kind or its tolerance.

### D8: The Altium kit samples route to the corrected DIP-8 pads

The kit samples `routed` and `board6` (`examples/kit/`) place `DIP8_Microchip_P` and draw their copper in
`kit_model`. Their `LED_DRV` and `VIN` tracks ended where pins 2 and 1 used to be, which is now where
pins 3 and 4 are. A simulated kit run failed K4.2 and K6.1 with two shorts each. Unlike the Roles symbols,
`Fenolite:Microcontroller` is a catalog symbol, so the copper is redrawn instead. In both samples:

- `LED_DRV` now leaves pin 2 to the right, between the two rows of pins, and joins the old path at
  y = 6 mm;
- `VIN` follows its old path below the part to x = 12 mm, then climbs to pin 1.

The planted violations, vias, polygon, keep-out and every other item are unchanged, and the simulated
kit run passes every step again. The PCB documents the build writes do not hold `kit_model` copper.

## Regenerated pins and why

Each file below was regenerated with the repository's own tool. No assertion was loosened.

| File | Tool | Why it changed |
| --- | --- | --- |
| `src/fenolite/catalog/data/VERSIONS.toml` | `uv run python tools/catalog/versions.py --update` | 55 records at `1.1.0` with new output digests; catalog `1.0.1` → `1.0.2` |
| `tests/data/catalog/footprints.sha256` | `write_footprint` for KiCad 9 and 10 over `list_entries(kind="footprint")` | 110 of 200 lines: the 55 mirrored footprints × 2 targets; the other 45 are byte-identical |
| `tests/data/catalog/golden.json` | `uv run python tools/catalog/golden.py` | 55 definition digests; the `examples/catalog` build (`board.json`, `build.json`, `catalog.kicad_pcb`, `lib/Fenolite.pretty/SOT23_3.kicad_mod`), because that example places a SOT23_3; `render_footprints`, because the renderer draws Y down |
| `tests/data/build_bytes.json` | `uv run python tests/_buildbytes.py` | 15 example builds whose board places a mirrored package, for targets 9, 10 and `altium`: `catalog` (SOT23_3), `devices` (SOT23_6_TI_DBV0006A), `lock` (SOT223_3_Diodes), `pins` (LQFP32_P0.8, SOT23_6_TI_DBV0006A) and `symbols` (SOIC_8). Changed: `.fenolite/board.json`, the board file, and the written footprint (KiCad) or `PcbLib` (Altium). No other example and no other file changed. The macOS run also wrote the platform-dependent `board_40parts.PcbDoc` digest; the recorded Linux digest was kept (`test_build_bytes.py` pins the per-platform variants) |
| `docs/catalog/previews/c0076-current-gallery*.svg` | `uv run python tools/catalog/render_footprints.py docs/catalog/previews/c0076-current-gallery.svg --page-size 20` | renderer Y down (D6) |
| `docs/cli-surface.json` | `uv run python tools/gen_cli_surface.py` | the new `library.pin-order` explain entry |
| `tests/data/specctra/c0107_before_planebench_norules.dsn` | `FENOLITE_GOLDEN_WRITE=1 FENOLITE_C0107_RECORD=1 uv run pytest tests/unit/backends/specctra/test_dsn.py -k unchanged` | The plane bench places `SOIC_8`. Only the eight `pin` lines of image `P3` changed; the rest of the text is byte-identical. Its `MANIFEST.toml` note says so |
| `tests/data/kicad/routing/planebench_t9_{before,after}_filled.kicad_pcb` | `FENOLITE_PROBES_WRITE=1 uv run pytest tests/kicad/routing/test_fanout_oracle.py` on local `kicad-cli` 10.0.6 | The same plane bench as built and as routed. Its `SOIC_8` pads moved, so the direct fan-out vias moved with them. The oracle test also passed on this run: `fenolite check` and KiCad DRC found no finding |
| `tests/unit/backends/altium/test_lower_build_spec.py` `FORMER_DOCUMENTS` | the PCB document of each example built through `built_document`, both sheet modes | the four `kit/` entries (`board6`, `flat`, `libs`, `routed`), which place `DIP8_Microchip_P`; the eight other entries are byte-identical. The test still asserts that the lowered specification writes these exact bytes |

Unit tests updated:

- `tests/unit/catalog/test_catalog.py` pinned the mirrored coordinates; each pinned y now has the
  opposite sign, and nothing else changed. For example: SOT-23 pad 1 now at y −950000, the DIP pitch
  now +2540000, the QFN `pads[0]` at −half_run, and the micro-USB signals now at y −5500000.
- `tests/unit/catalog/footprints/test_drawing.py`: `drawing/0` still reproduces the 0.6 placement,
  which is the mirror. The test now compares the X-mirror of the `drawing/0` output with the corrected
  catalog entry (Chip_0603 is achiral and compared as is). The assertion remains exact equality.

## The private board

The bug report came from a private board rebuild. Nothing from that board enters the repository. The
test fixtures (`tests/unit/library/test_rules.py`, `tests/data/library_rules/bad/pin_order.toml`) are
authored for Fenolite.

## fenolite-library (read only)

`../fenolite-library` was scanned with the final rule; nothing there was edited.

| Checkout | Fenolite records | Flagged clockwise |
| --- | --- | --- |
| main, `first-boards` | none (KiCad demo boards only) | upstream demo footprints only: `SOT23EBC` (×2) and `LED_Wurth_150044M155260` |
| worktree `claude/library-growth-af26a4` | 14 judged counter-clockwise, 34 not judged, 0 clockwise; its generated records use `drawing = 1` | the same demo footprints plus one easyeda2kicad USB-C footprint |
| `fenolite-library-completion` (`cac/library-completion`) | 3 records, not judged | only `SOT23EBC` |

The Fenolite-authored items in fenolite-library do not show the catalog's mirror. The flagged items are
third-party demo footprints numbered by their own scheme. For example, `SOT23EBC` names its pads E, B, C,
which is not the JEDEC 1-2-3 order.

## Risks

- **Breaking change:** a design that placed one of the 55 packages gets the corrected land on its next
  build, and its copper must be routed and checked again. The CHANGELOG says so.
- **Narrow coverage:** the rule judges only perimeter numberings it recognises. A mirrored land of an
  unusual shape can still pass, and the four single-row parts of D2 show that. The review gallery now
  draws the true frame, so a reviewer can see such a land.

## Open: the Altium kit run is stale; a new run is planned

Four kit samples place `DIP8_Microchip_P`: `flat`, `routed`, `board6` and `libs`. Their built bytes
changed, so 29 steps of the native kit run `2026-10-13-87c930fa` are stale on those samples. That makes 25
`ALTIUM-VERIFIED(kit; …)` rows of `docs/hypotheses.md` stale. The other samples are unchanged.

The decision of 2026-11-05 is not to lower those rows: another session records a new kit run in the
Altium VM. Task 5.2 lists the steps, the rows and the commands.

Until that run is recorded, the following fail:

- `uv run python tools/gen_altium_graduation.py --check` (lint);
- `tests/unit/test_hypotheses_register.py::test_kit_labels_of_the_register_have_their_record`;
- `tests/unit/backends/test_graduation.py::test_matrix_current_kit_matches_committed_claims`;
- `tests/unit/test_evidence_matrix_page.py` (3);
- `tests/unit/cli/test_capabilities_altium.py::test_packaged_decisions_match_repository_rule`.
