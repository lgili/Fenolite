## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`fenolite-component-catalog`, `design-dsl`, `design-model`, `package-layering`), and record under this task, with the date and the base commit:
  - whether c0246 and c0247 are archived. If c0246 is, rebase the move of the unit parser (task 1.1) on its `Range`. Check that c0247's hooks `Part._end(index)` and `must_connect_pins(component, device)` are the ones `design.md` extends;
  - which open change holds a delta of "Allowed import edges" (c0173, c0195, c0222's successors, c0251 and others in this batch). If one was archived, regenerate the MODIFIED block from the living text. Record that the living text names `dsl` → `model` while the import-graph test also allows `schematic`, and align the block with the test;
  - which open change holds a delta of "Connections and pin designators";
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0248-device-catalog --strict`; `make check-fast`.

## 1. Units, model and layering

- [ ] 1.1 Move the exact unit parser to `src/fenolite/core/quantities.py` (stdlib only), and keep the public names of `fenolite.dsl.quantity`. Add the units `degC` and the integer conversion to µV, µA, µW and m°C. Proof: `uv run pytest tests/unit/dsl/test_quantity.py tests/unit/core/test_quantities.py -q`.
- [ ] 1.2 Add `DeviceDef`, `DevicePin`, `Rating`, `DeviceProvenance` and `Library.devices` to `model/library.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Device round trip", "Devices stay out of the layer files", "Pins in code-point order", "No float in a device"). Proof: `uv run pytest tests/unit/model/test_library.py -k device -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 1.3 Add the edge `dsl` → `catalog` to the import-graph test (scenario "The DSL reads the catalog, not the reverse"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.

## 2. Device records in the catalog

- [ ] 2.1 Add `catalog/devices.py` with `parse_device`, `device_text`, `device_digest`, `load_devices` and `check_device`, and author the test records under `tests/data/devices/` (each opens with the authored-for-Fenolite line, and datasheets on `example.invalid`). Scenarios: "A device record is read", "Unknown key", "Shipped namespace needs sources", "Reserved key", "Three spellings", "Refused pin tables", "Ratings read exactly", "Refused ratings", "Canonical text round trip". Proof: `uv run pytest tests/unit/catalog/test_devices.py -q`.
- [ ] 2.2 Add provenance and edit detection (scenarios "Reformatting keeps the digest", "Reformatting is not an edit"; "A hand edit is detected" at the record level). Register `H-G-DEVICE-RECORD` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/catalog/test_devices.py -k provenance -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 2.3 Author the ten shipped generic devices under `src/fenolite/catalog/devices/`, with `shipped_devices()` and the package-data entry (scenarios "Every shipped device agrees with the catalog", "The LED keeps the cathode-first map"). Proof: `uv run pytest tests/unit/catalog/test_devices.py -k shipped -q`; `make residue`.

## 3. DSL

- [ ] 3.1 Add `dsl/devices.py` (the registry, its context variable, and precedence with `device.overrides-builtin`), `Design.devices`, and the device loading of `cli/_script.py` from `devices/` beside the script (scenarios "Project device beside the script", "Override of a shipped device", "One id in two files"). Proof: `uv run pytest tests/unit/dsl/test_device_registry.py tests/unit/cli/test_script.py -k devices -q`.
- [ ] 3.2 Add `Part(device=...)`, `Design.part`, `Module.part`, `part.device`, the merged properties and the lowering in `to_model` (scenarios "Neither or both", "Unknown device", "Created in a module", "A part from a device", "Footprint given with a device", "A generic device takes a value", "Conflicting MPN", "Designs without devices are unchanged"). Proof: `uv run pytest tests/unit/dsl/test_device_parts.py tests/unit/dsl/test_ids.py -q`.
- [ ] 3.3 Add checked pin access: `__getattr__`, the checked `__getitem__`, `PinNameError`, `__dir__` and the closest-name message (scenarios "Pin by function", "Non-device parts are unchanged", "A typo names the closest pin", "Wrong case", "Part attributes win", "Private names", "Device part checked at the call", "LED ends follow the anode"). Extend c0247's `Part._end` and `must_connect_pins` hooks and accept `part.pad(function)` (see `design.md`, decision 5). Proof: `uv run pytest tests/unit/dsl/test_device_pins.py -q`.

## 4. Build

- [ ] 4.1 Resolve function designators, add `check_device` to the build with `build.device-mismatch`, `unused_pads`, the `Datasheet` field and the reserved properties, and add the three codes to `BUILD_ISSUE_CODES` and `explain.toml` (scenarios "Function joins its pins", "Device disagrees with its symbol", "Unused pad declared", "Datasheet field"). Proof: `uv run pytest tests/unit/lens/test_build_devices.py tests/unit/lens/test_build_issues.py -q`.
- [ ] 4.2 Add `result.devices`, the device files in `input`, and `DEVICE_EVIDENCE` with `H-K-BUILD-DEVICE` (scenarios "Result lists the devices", "No devices, no rows", "Device file in the input"). Proof: `uv run pytest tests/unit/cli/test_build_devices.py -q`.
- [ ] 4.3 Author `examples/devices/` (a 12 V to 3.3 V board with the illustrative `Example:BUCK_6V_2A` and the generic devices) and the KiCad oracle test (scenario "Device build passes the KiCad oracle"). Proof: `uv run pytest tests/unit/test_examples.py -k devices -q`; `uv run pytest tests/kicad/build/test_device_build.py -rA` (in CI).

## 5. Catalog command

- [ ] 5.1 Extend `fenolite catalog` with `--kind device` for `list` and `show`, and with `shadowed`, `digest` and `edited` (scenarios "List devices", "Show a device"). Proof: `uv run pytest tests/unit/cli/test_catalog.py -k device -q`.
- [ ] 5.2 Add `catalog import`, with its plan, the stamp, `catalog.pin-without-pad`, `catalog.pad-unmapped` and the `FEN-7001` refusal (scenarios "Import a template", "A pin without a pad", "Grouped names", "Re-import over a hand edit", "Re-import of an unedited file", "A hand edit is detected"). Proof: `uv run pytest tests/unit/cli/test_catalog_import.py -q`; `uv run pytest tests/consistency -q`.

## 6. Closing

- [ ] 6.1 Docs: `docs/devices.md` (the format, its spellings, ratings and units, precedence, provenance, and how to review a pin map), a "Devices" section of `docs/dsl.md`, `catalog import` in `docs/cli-contract.md`, and links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 6.2 Agent guide: add tested lines to `parts.md` for `design.part(..., device=...)`, pin access by function and `catalog import`, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 6.3 Residue and evidence: every authored file carries its authored-for-Fenolite line, no real manufacturer part number is shipped, the hypotheses are registered, and the evidence matrix is regenerated. Proof: `make residue`; `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 6.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
