# Number the catalog lands counter-clockwise and refuse clockwise pin order

## Why

Fenolite's footprint frame is X right, Y down (`docs/formats/kicad/frame.md`). The catalog's package
records were written with Y up: `SOT23_3` holds pad 1 at (−1.05, +0.95) mm and pad 2 at (−1.05, −0.95) mm,
so pad 1 is at the lower left and the pads run clockwise in the top view. The JEDEC/IPC convention, the
cited outline drawings and every stock library number them counter-clockwise from pin 1 at the upper
left. The land is the mirror image of the part: a SOT-23, SC-70 or SOT-89 soldered on it has pins 1 and 2
swapped, a QFP has every pin but the diagonal ones on the wrong pad. A private board rebuild found it
independently (every SOT-23, SC-70 and SOT-89 part and one LQFP-32 fitted with swapped nets).

Three things let it ship. Each mirrored record carried `[[waiver]] code = "library.pin1-location"` with
the reason "Legacy shipped catalog drawing keeps its established orientation …", which silenced the only
geometric check. No rule looked at the order of the pads, only at where pad 1 sits. And the review
gallery (`tools/catalog/render_footprints.py`) drew the lands with Y up, so every review sheet showed
the mirrored land the way the datasheet draws the part.

A scan of the 100 catalog packages finds 51 whose numbered leads turn clockwise (the 48 the coordinator
listed, plus `SOT223_3_Diodes`, `TO252_3_Diodes_Standard` and `TO263_3_Diodes_Standard`, whose tab pad hid
the turn from a plain shoelace sum), and four single-row parts whose body outline is mirrored the same way
(`JST_XH_B2B_XH_A`, `JST_XH_B4B_XH_A`, `MicroUSB_B_Wurth_629105150521`, `TO220_3_Diodes_Vertical`).

## What Changes

- **BREAKING (land patterns).** The 55 package records are mirrored about their X axis (y → −y for pads,
  graphics and slot rotations), each at version `1.1.0`; their pad numbers, sizes and kinds are kept, so
  no device or pin map changes. A design that placed one of them gets the corrected land on the next
  build; its routed copper must be checked again.
- The `library.pin1-location` waivers the mirrored lands no longer need are removed (48). The six parts
  whose cited top view puts pad 1 at the lower left (`Crystal_3225_Abracon_ABM8`, `SOT143_4_Diodes`,
  `SOT89_3`, `SOT223_3_Diodes`, `TO252_3_Diodes_Standard`, `TO263_3_Diodes_Standard`) keep the source's
  orientation with a waiver naming that source; `JST_XH_B4B_XH_A` keeps its waiver with a reason naming
  S-0410.
- New library rule `library.pin-order` (error): the numbered leads of a perimeter-numbered land must turn
  counter-clockwise in the top view; zig-zag headers, grid arrays, two-pad parts, single rows and other
  numberings without a perimeter order are not judged. A `library.pin-order` waiver is refused unless its
  reason names the S- or D- source that numbers the part clockwise.
- The catalog review renderer draws Y down; the gallery pages are drawn again.
- The synthetic symbols of the net-role reference boards (`Roles_Sense_Amplifier`, `Roles_HalfBridge_Driver`,
  `Roles_Cell_Monitor`, "not a device pinout") are renumbered by the mirror map, so the boards' hand-drawn
  copper keeps its functions on the corrected lands (design D7).
- Regenerated pins: `src/fenolite/catalog/data/VERSIONS.toml`, `tests/data/catalog/footprints.sha256`,
  `tests/data/catalog/golden.json`, `tests/data/build_bytes.json` and the gallery SVGs; the unit tests that
  pinned the mirrored coordinates now pin the corrected ones.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `library-rules`: new requirement "Pin order rule"; "Waivers" gains the source rule for `library.pin-order`.
- `fenolite-component-catalog`: "Catalog footprints come from the generators" and "Family entries
  reproduced under drawing 0" follow the corrected lands; new requirement "Catalog lands numbered
  counter-clockwise".

## Impact

Catalog package records and `VERSIONS.toml`, `fenolite.library.rules`, `library check`, `explain.toml`,
`docs/library-rules.md`, `docs/formats/library/rules.md`, the agent guide page `library-review`, the
catalog review renderer, golden digests and the catalog unit tests. `fenolite-library` is out of scope
(read only; see design).
