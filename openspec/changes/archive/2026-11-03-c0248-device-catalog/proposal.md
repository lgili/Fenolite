## Why

A Fenolite part is a symbol and a footprint chosen apart and joined by `pad_map`; the manufacturer,
part number, datasheet and ratings are free text or missing. Pins are strings, and a typo surfaces only at build time
as `build.unknown-pin`. Nothing a later check needs, such as the ratings c0253 compares with the rails, has
one reviewed home.

Research section 1 and core change B of `docs/research/circuit-as-code.md` propose a **device**: one
reviewed record that joins symbol, footprint, the map from pin function to pad, ratings and evidence. A
part is then placed from a device.

## What Changes

- **Device records** (`fenolite.device.v0`, TOML): id, optional manufacturer, MPN and datasheet, symbol,
  footprint, reference prefix, value, a function-to-pins-and-pads map (with pin ratings and
  `must_connect`), device ratings in integer micro-units, an evidence label, sources and an optional
  provenance stamp. `DeviceDef` joins `fenolite.model.library`; the parser and shipped records live in
  `fenolite.catalog`.
- **Where devices come from.** The catalog ships a small set of generic `Fenolite:` devices (chip
  resistors and capacitors, an LED on a cathode-first land, a 2-pin header). Project devices are read from
  `devices/*.toml` beside the script, or registered with `design.devices(...)`. A project device
  overrides a shipped one, as authored symbols already do.
- **DSL.** `Part(ref, device="...")`, `design.part(ref, device=...)` and `module.part(...)` create and add
  a part whose symbol, footprint, pad map, value and BOM properties come from the device.
- **Checked pins.** On a device part, `u1.VIN` and `u1["VIN"]` are checked when they are called. A wrong
  name raises `DslError`, which lists the closest function names (`difflib`, deterministic).
- **Build.** For a device part, the build resolves function designators first. A device that disagrees
  with its symbol or footprint is the error `build.device-mismatch`. The datasheet goes into the
  `Datasheet` field. `fenolite.device` and `fenolite.device.sha256` are written as properties.
- **Provenance.** `fenolite catalog import` writes a device template from a symbol and a footprint, through
  plan and confirm, stamped with its tool, source, date and a SHA-256 of the record. A hand edit is shown as
  `device.edited`, and a re-import that would overwrite it is refused (`FEN-7001`).
- **Catalog CLI.** `catalog list|show --kind device`.
- **Layering.** `dsl` may import `catalog`.

## Non-goals

- No parametric choice of parts, and no parametric rows (c0254). No ratings check (c0253).
- No interfaces declared on devices (c0252), and no pin-assignment options (c0257). The keys
  `interfaces` and `options` are reserved.
- No automatic reference designators: the ref stays required here, and c0249 lifts that.
- No supplier lookup or network. No real-MPN device is shipped; examples use authored `Example:` devices.
- No pin map inferred from the order of pins: a map must be explicit, or an identity that is checked.

## Evidence level required

- Device parsing, digest and DSL checks: `INFERRED`, unit-tested (hypothesis `H-G-DEVICE-RECORD`).
- Builds with device parts: `INFERRED` (`H-K-BUILD-DEVICE`). In CI, the KiCad job runs ERC and DRC on the
  device example and must find no new finding.
- Shipped generic devices: `INFERRED`, with the sources of their catalog symbol and footprint.
- Each device record carries its own label. No command raises it.

## Impact

- New: `catalog/devices.py` and `catalog/devices/*.toml`, `core/quantities.py`, `dsl/devices.py`,
  `docs/devices.md`, `examples/devices/`, tests.
- Changed: `model/library.py`, `dsl/` (`part`, `module`, `design`, `convert`, `quantity`), `lens/build.py`,
  `cli/cmd_catalog.py`, `cli/_script.py`, the import-graph test, docs, the guide page `parts.md`,
  `CHANGELOG.md`.
- Depends on: c0246 (ratings read as ranges when present) and c0247 (`unused_no_connect` reads
  `must_connect`). Implemented together with c0249. c0251, c0252, c0253, c0254 and c0257 build on it.
- Size: about 9 design-days.
