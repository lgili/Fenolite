## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`fenolite-component-catalog`, `design-dsl`, `design-model`, `package-layering`), and record under this task, with the date and the base commit:
  - whether c0246 and c0247 are archived. If c0246 is, rebase the move of the unit parser (task 1.1) on its `Range`. Check that c0247's hooks `Part._end(index)` and `must_connect_pins(component, device)` are the ones `design.md` extends;
  - which open change holds a delta of "Allowed import edges" (c0173, c0195, c0222's successors, c0251 and others in this batch). If one was archived, regenerate the MODIFIED block from the living text. Record that the living text names `dsl` → `model` while the import-graph test also allows `schematic`, and align the block with the test;
  - which open change holds a delta of "Connections and pin designators";
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0248-device-catalog --strict`; `make check-fast`.
  Note (2026-10-29, base 3cabfe5a on `circuits-as-code`, branch `cac/c0248-device-catalog`): c0246 and c0247
  are not archived (both open, 0 tasks done), so the unit parser moved without a `Range`, and c0247's hooks
  `Part._end` and `must_connect_pins` do not exist yet; this change provides `dsl.devices.end_handle` and
  `dsl.devices.must_connect_pins` for them to call. Open deltas of "Allowed import edges": c0173, c0195,
  c0254, c0256, c0267 and this change; none is archived, so the MODIFIED block stays on the living text, now
  aligned with the import-graph test (`dsl` → `model`, `schematic`, `catalog`; `schematic` → nothing else).
  Open deltas of "Connections and pin designators": this change and c0251. `openspec validate --strict` passes.
  Done (2026-10-29, branch head 635bc180): the maintainer answered the four open questions on 2026-10-29 and
  chose every recommended answer, which this change already implements: project devices may override
  `Fenolite:` ids with `device.overrides-builtin`; the envelope level is not lowered (per-device
  `result.devices[].evidence`); the browser export is a follow-up change; attribute names do not fold case and
  the error suggests the exact spelling. Recorded under "Open questions" in `design.md`. c0246 and c0247 are
  still open, as above. Proofs passed (`openspec validate c0248-device-catalog --strict`; `make check-fast`).

## 1. Units, model and layering

- [x] 1.1 Move the exact unit parser to `src/fenolite/core/quantities.py` (stdlib only), and keep the public names of `fenolite.dsl.quantity`. Add the units `degC` and the integer conversion to µV, µA, µW and m°C. Proof: `uv run pytest tests/unit/dsl/test_quantity.py tests/unit/core/test_quantities.py -q`.
  Done (2026-10-29): `fenolite.core.quantities` (`parse`, `micro_units`, `QuantityError`, unit `celsius` read as `degC`); `fenolite.dsl.quantity` keeps its names and wraps the errors in `DslError`. Proof passed (39 tests).
- [x] 1.2 Add `DeviceDef`, `DevicePin`, `Rating`, `DeviceProvenance` and `Library.devices` to `model/library.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Device round trip", "Devices stay out of the layer files", "Pins in code-point order", "No float in a device"). Proof: `uv run pytest tests/unit/model/test_library.py -k device -q`; `uv run python tools/gen_schemas.py --check`.
  Done (2026-10-29): the four value objects and `Library.devices` (ordered), plus `DeviceDef.ends` (the `ends` key must round-trip), `DeviceDef.pad_map`, `pin()` and `rating()`; schema regenerated; `docs/design-model.md` updated. Proof passed (4 tests; `gen_schemas.py --check` clean).
- [x] 1.3 Add the edge `dsl` → `catalog` to the import-graph test (scenario "The DSL reads the catalog, not the reverse"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
  Done (2026-10-29): `dsl` → `catalog` in `ALLOWED`, two rows of the rule table and `test_dsl_reads_the_catalog_not_the_reverse`. Proof passed (55 tests).

## 2. Device records in the catalog

- [x] 2.1 Add `catalog/devices.py` with `parse_device`, `device_text`, `device_digest`, `load_devices` and `check_device`, and author the test records under `tests/data/devices/` (each opens with the authored-for-Fenolite line, and datasheets on `example.invalid`). Scenarios: "A device record is read", "Unknown key", "Shipped namespace needs sources", "Reserved key", "Three spellings", "Refused pin tables", "Ratings read exactly", "Refused ratings", "Canonical text round trip". Proof: `uv run pytest tests/unit/catalog/test_devices.py -q`.
  Done (2026-10-29): `catalog/devices.py` (`DeviceFormatError` FEN-3004, `DeviceFormatTooNewError` FEN-3002) and the authored records `tests/data/devices/{example_buck,grouped_ground,stamped}.toml`, declared in `tests/data/MANIFEST.toml`. Proof passed.
- [x] 2.2 Add provenance and edit detection (scenarios "Reformatting keeps the digest", "Reformatting is not an edit"; "A hand edit is detected" at the record level). Register `H-G-DEVICE-RECORD` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/catalog/test_devices.py -k provenance -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done (2026-10-29): `device_digest`, `is_edited`, `stamped`, `edited_issue`; `H-G-DEVICE-RECORD` and `H-K-BUILD-DEVICE` rows filled in `docs/hypotheses.md`. Proofs passed (`-k provenance`: 5 tests; register: 38 tests).
- [x] 2.3 Author the ten shipped generic devices under `src/fenolite/catalog/devices/`, with `shipped_devices()` and the package-data entry (scenarios "Every shipped device agrees with the catalog", "The LED keeps the cathode-first map"). Proof: `uv run pytest tests/unit/catalog/test_devices.py -k shipped -q`; `make residue`.
  Done (2026-10-29): ten records under `src/fenolite/catalog/devices/` read by `shipped_devices()`. The wheel is built by hatchling from `src/fenolite`, which includes the TOML files without a package-data entry. Proofs passed (`-k shipped`; `make residue`: 0 hits).

## 3. DSL

- [x] 3.1 Add `dsl/devices.py` (the registry, its context variable, and precedence with `device.overrides-builtin`), `Design.devices`, and the device loading of `cli/_script.py` from `devices/` beside the script (scenarios "Project device beside the script", "Override of a shipped device", "One id in two files"). Proof: `uv run pytest tests/unit/dsl/test_device_registry.py tests/unit/cli/test_script.py -k devices -q`.
  Done (2026-10-29): `dsl/devices.py` (context variables for the project devices and the design's records), `Design.devices`, `Container.part`, and `cli/_script.read_project_devices` (installed around the run; `ScriptRun.devices`, `device_files`). Proof passed.
- [x] 3.2 Add `Part(device=...)`, `Design.part`, `Module.part`, `part.device`, the merged properties and the lowering in `to_model` (scenarios "Neither or both", "Unknown device", "Created in a module", "A part from a device", "Footprint given with a device", "A generic device takes a value", "Conflicting MPN", "Designs without devices are unchanged"). Proof: `uv run pytest tests/unit/dsl/test_device_parts.py tests/unit/dsl/test_ids.py -q`.
  Done (2026-10-29): `Part(..., device=...)` (`value` now defaults to `None`, read as before), `part.device`, `device_origin`, merged properties and the two reserved properties in `to_model`. The blink's model texts equal those of the base commit (digest pinned in `test_device_parts.py`). Proof passed (14 tests).
- [ ] 3.3 Add checked pin access: `__getattr__`, the checked `__getitem__`, `PinNameError`, `__dir__` and the closest-name message (scenarios "Pin by function", "Non-device parts are unchanged", "A typo names the closest pin", "Wrong case", "Part attributes win", "Private names", "Device part checked at the call", "LED ends follow the anode"). Extend c0247's `Part._end` and `must_connect_pins` hooks and accept `part.pad(function)` (see `design.md`, decision 5). Proof: `uv run pytest tests/unit/dsl/test_device_pins.py -q`.
  Done except the c0247 hooks (2026-10-29): `__getattr__`, the checked `__getitem__`, `PinNameError` (exported
  from `fenolite.dsl`), `__dir__`, the closest-name message and `part.pad(function, index=)` pass their
  scenarios (`tests/unit/dsl/test_device_pins.py`, 12 tests). Left open: extending c0247's `Part._end(index)`
  and `must_connect_pins(component, device)`, and `part.a`/`part.b` of the scenario "LED ends follow the
  anode", wait until c0247 is merged; `dsl.devices.end_handle` and `dsl.devices.must_connect_pins` are the
  functions those hooks will call (tested here).

## 4. Build

- [x] 4.1 Resolve function designators, add `check_device` to the build with `build.device-mismatch`, `unused_pads`, the `Datasheet` field and the reserved properties, and add the three codes to `BUILD_ISSUE_CODES` and `explain.toml` (scenarios "Function joins its pins", "Device disagrees with its symbol", "Unused pad declared", "Datasheet field"). Proof: `uv run pytest tests/unit/lens/test_build_devices.py tests/unit/lens/test_build_issues.py -q`.
  Done (2026-10-29): `build_design(..., devices=, device_check=)` (the lens does not import the catalog: `cmd_build` passes `check_device`), function resolution in `_targets`, `unused_pads`, `embed.with_property_value` for the `Datasheet` field, the reserved properties written as `fenolite.path` is; the three codes in `BUILD_ISSUE_CODES` and `explain.toml`. Proof passed (9 tests).
- [x] 4.2 Add `result.devices`, the device files in `input`, and `DEVICE_EVIDENCE` with `H-K-BUILD-DEVICE` (scenarios "Result lists the devices", "No devices, no rows", "Device file in the input"). Proof: `uv run pytest tests/unit/cli/test_build_devices.py -q`.
  Done (2026-10-29): `result.devices`, `DEVICE_EVIDENCE`, and the issues `device.overrides-builtin` and
  `device.edited` once per device. The envelope's `input` names one file in contract v0, so the device files
  are listed in `result.device_files` (path relative to the script folder and SHA-256) and join
  `Result.depends`, which changes the plan id; the spec delta says so. A dry run exits 0, so the scenario
  "Project device beside the script" now says exit 0. The Altium target lowers device functions to pin numbers
  before its build (`lower_device_functions`). Proof passed (4 tests).
- [x] 4.3 Author `examples/devices/` (a 12 V to 3.3 V board with the illustrative `Example:BUCK_6V_2A` and the generic devices) and the KiCad oracle test (scenario "Device build passes the KiCad oracle"). Proof: `uv run pytest tests/unit/test_examples.py -k devices -q`; `uv run pytest tests/kicad/build/test_device_build.py -rA` (in CI).
  Done (2026-10-29): `examples/devices/` (listed in `examples/README.md` and the manifest). It is a 5 V to 3.3 V
  board, not 12 V: the illustrative regulator is rated 6 V at most, and a 12 V input would contradict its own
  record. `tests/kicad/build/test_device_build.py` compares the ERC and DRC findings of the device build with
  those of the same design written with plain `Part` calls. Proofs: `test_examples.py -k devices` passed (3
  tests); the KiCad oracle passed locally with kicad-cli 10.0.7 for targets 10 and 9 (findings equal:
  17 unconnected items each, before routing) and runs in CI.

## 5. Catalog command

- [x] 5.1 Extend `fenolite catalog` with `--kind device` for `list` and `show`, and with `shadowed`, `digest` and `edited` (scenarios "List devices", "Show a device"). Proof: `uv run pytest tests/unit/cli/test_catalog.py -k device -q`.
  Done (2026-10-29): `--kind device` for `list` and `show`, `record`, `digest`, `edited`, `shadowed` and the `check_device` issues. Proof passed (3 tests).
- [x] 5.2 Add `catalog import`, with its plan, the stamp, `catalog.pin-without-pad`, `catalog.pad-unmapped` and the `FEN-7001` refusal (scenarios "Import a template", "A pin without a pad", "Grouped names", "Re-import over a hand edit", "Re-import of an unedited file", "A hand edit is detected"). Proof: `uv run pytest tests/unit/cli/test_catalog_import.py -q`; `uv run pytest tests/consistency -q`.
  Done (2026-10-29): `catalog import` with `--pin`, the stamp, `CATALOG_ISSUE_CODES` (registered in `cli/explain.py` and `explain.toml`) and `FEN-7001`. The command's mutation example stays `view` (offline). Proofs passed (`test_catalog_import.py`: 10 tests; `tests/consistency`: 572 passed, 35 skipped).

## 6. Closing

- [x] 6.1 Docs: `docs/devices.md` (the format, its spellings, ratings and units, precedence, provenance, and how to review a pin map), a "Devices" section of `docs/dsl.md`, `catalog import` in `docs/cli-contract.md`, and links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
  Done (2026-10-29): `docs/devices.md`, the "Devices" section of `docs/dsl.md`, `catalog list|show --kind device` and `catalog import` in `docs/cli-contract.md`, a row in `docs/index.md`. Proof passed (69 tests).
- [x] 6.2 Agent guide: add tested lines to `parts.md` for `design.part(..., device=...)`, pin access by function and `catalog import`, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
  Done (2026-10-29): a "Parts from devices" section of `parts.md` with a design block (it uses `PinNameError`) and three `fenolite-cmd` lines; generated pages rewritten; `tests/unit/agent/test_pages_kicad.py` names the new block. Proof passed.
- [x] 6.3 Residue and evidence: every authored file carries its authored-for-Fenolite line, no real manufacturer part number is shipped, the hypotheses are registered, and the evidence matrix is regenerated. Proof: `make residue`; `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
  Done (2026-10-29): every authored device file opens with its authored-for-Fenolite line, the example MPN is illustrative, both hypotheses are registered and the evidence matrix is current. Proofs passed (`make residue`: 0 hits; register; `gen_evidence_matrix.py --check`).
- [ ] 6.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
  Left open (2026-10-29): `dev` is at the unpublished 0.6.0 and `tests/unit/test_release_record_v06.py`
  requires `## [Unreleased]` to stay empty, so the entry waits until `dev` is at `0.7.0.dev0`.
  Still open (2026-10-29): the maintainer decided on 2026-10-29 that `circuits-as-code` keeps its current base,
  version 0.6.0, until the line is ready for `dev`; the v0.6 guard requires `## [Unreleased]` to stay empty
  until then.
- [x] 6.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
  Done (2026-10-29): `make check-fast` passed (15398 passed, 46 skipped); pushed to `cac/c0248-device-catalog`;
  run 40907010241 on 5657bde7 is green in every job (unit on Linux, macOS and Windows, kicad-9, kicad-10,
  routing, mcp, viewer, wheel, dco).
