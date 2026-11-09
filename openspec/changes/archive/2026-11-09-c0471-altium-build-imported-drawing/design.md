# Design: c0471

## Context

In `backends/altium/drawn.py`:

- `_carried_harnesses(drawn)` inspects `sheet.opaques` for `drawn_read.is_harness_text(o.altium)`. Currently
  `lower_drawn` only calls `_carried_harnesses(drawn)` when `carry=True`. Calling `_carried_harnesses(drawn)`
  unconditionally is a no-op on drawings without harness opaque items and enables harness stand-in pruning and
  `HARNESSTYPE` resolution on `build --target altium` when `schematic.toml` came from an Altium import.
- Inside `_Sheet.drawing`, an `opaque.altium` entry may be a multi-line subtree written by
  `drawn_read.subtree_text`: line 0 is the root record (e.g. `RECORD=43` `WarningSign` / parameter set, or
  `RECORD=215` `HarnessConnector`), and lines `number > 0` have `OWNERINDEX=@<line>` naming an earlier line in
  the same `opaque.altium`. Allowing `child = number > 0 and owner.startswith("@")` and
  `harness = number == 0 and drawn_read.is_harness_text(opaque.altium)` (and passing
  `read=self.carry or len(lines) > 1 or harness` to `self.add`) lets `build --target altium` write those
  imported subtrees while keeping the `FEN-3004` guard for root `_MODELLED` records and raw `OWNERINDEX` keys.
- In `_read_native`, `document.document.of_type(sch.UnknownRecord)` is used to detect corrupt or unknown
  records on readback. Records `209` (`Note`) and `225` (`CompileMask`) are the two Altium record ids that
  `drawn_read.record_class` classifies as opaque annotations/directives while `read.sch` keeps them as
  `UnknownRecord`. Filtering `of_type(sch.UnknownRecord)` to records other than `209` and `225` lets the
  readback guard verify sheets that carry `Note` or `CompileMask` records.
