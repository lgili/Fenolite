## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`fenolite-component-catalog`, `cli-contract`, and `fenolite-library` once c0279 is archived) and the changes it builds on (c0279 phase A, c0259, c0262; c0260, c0261, c0254). Write under this task, with the date and the base commit:
  - c0279's item, provenance and lock-section names as implemented, and whether `fenolite get` copies into `fenolite_library/<kind folder>/`;
  - c0259's record module and `load_tree` rules, and c0262's command and job names used by the library CI;
  - which open change holds a delta of "Build resolves built-in definitions" (regenerate the MODIFIED block from the living text);
  - the final verb list of `fenolite library` (c0260, c0261, c0262, c0264, c0265, c0279), so `seed` joins it;
  - the maintainer's answers to the open questions of `design.md`;
  - the next free `S-` numbers (the LibrePCB format documentation and the LibrePCB library).

  Proof: `openspec validate c0266-device-packs --strict`; `make check-fast`.

## 1. Vendored records in the core

- [ ] 1.1 `src/fenolite/catalog/vendored.py`: `load_vendored` over `fenolite_library/symbols`, `fenolite_library/footprints` and `fenolite_library/devices`, pairing records with their `item.json`. Author the vendored fixture `tests/data/library/project/`, each file with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/catalog/test_vendored.py -q`.
- [ ] 1.2 Runner precedence, `library.overrides-item`, `library.item-conflict`, the origin `library` in the build (scenarios "Authored record wins", "Two vendored items, one id", "Unused vendored item changes nothing", "Vendored definition resolved offline"). Proof: `uv run pytest tests/unit/cli/test_build_vendored.py tests/unit/lens -k vendored -q`.
- [ ] 1.3 Offline guard and the `get` hint for library ids (scenarios "Build with vendored records and no network", "Hint for a library id"). Register `H-G-DEVICE-PACKS` with its new statement (vendored records from a local release resolve the same records and build bytes as the library tree, offline). Proof: `uv run pytest tests/unit/cli/test_build_vendored.py -k "offline or hint" tests/unit/test_hypotheses_register.py -q`.
- [ ] 1.4 c0254 picks of vendored rows record `catalog = "library:device/<id>@<version>"`. Proof: `uv run pytest tests/unit/cli/test_pick.py -k library -q`.

## 2. Device kinds in the library audit

- [ ] 2.1 Device-kind rules in `fenolite library audit` (c0279): record id and licence equal to the item's, reserved namespace, `sources.toml` ids, `shippable()` (scenarios "Device item read", "Reserved namespace", "Unregistered source", "Version step missing"). Proof: `uv run pytest tests/unit/library/test_audit_devices.py -q`.

## 3. LibrePCB seed

- [ ] 3.1 `docs/formats/librepcb/library.md` from public LibrePCB documentation only (elements, files, units, axes, rotations, signal roles), each fact with source and evidence label; no parser code read. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
- [ ] 3.2 `src/fenolite/backends/librepcb/`: its tokenizer and element reader written from that page; authored fixtures under `tests/data/librepcb/demo/`. Proof: `uv run pytest tests/unit/backends/librepcb -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 3.3 `library seed`: licence gate, commit check, mapping to items and records, item files and `PROVENANCE.json`, ids, skips, plan and confirm, no overwrite of reviewed records, the `seed` verb and its `capabilities` entry (scenarios "Seed items carry their origin", "Not a CC0 library", "Commit mismatch", "Same bytes twice", "Custom pad outline skipped", "Reviewed record kept", "Board path form unchanged"). Proof: `uv run pytest tests/unit/cli/test_library_seed.py tests/unit/cli/test_library_cmd.py -q`.

## 4. The library repository

- [ ] 4.1 In `lgili/fenolite-library`: the `sources.toml`, the device-kind jobs `records`, `regenerate`, `versions`, `origin` and `renders` in `check.yml`, the seed risk in the README, and `reviews/`. Proof: the library's first pull request with device items green.
- [ ] 4.2 First device items (authored `FenoliteDevices` items and, after review of the run, a seeded LibrePCB set), released by c0279's release job. Proof: `fenolite library audit . --json` exits 0 in the library on the release tag.

## 5. Closing

- [ ] 5.1 Docs: `docs/library-devices.md` (kinds, authored and seeded items, vendored records, precedence, origin labels, lock pins, offline use, seed and its risk), `library seed` in `docs/cli-contract.md`, links from `docs/index.md`, `docs/library-records.md` and `docs/library-repo.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 5.2 Agent guide: tested lines in `parts.md` for `fenolite get device <id>` with vendored records and for `fenolite library seed`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Example `examples/library-devices/` (a design using one demo device vendored from a local release folder, its lock, offline). Proof: `uv run pytest tests/unit/test_examples.py -k library_devices tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 5.4 Run `uv run pytest tests/residue -q` and update evidence labels. Proof: `uv run pytest tests/residue tests/unit/test_inferred_hypotheses.py -q`.
- [ ] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit, KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
