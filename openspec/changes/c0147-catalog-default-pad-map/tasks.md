## 0. Entry check

- [x] 0.1 Read c0144 (proposal, design, tasks, spec delta) and the maintainer's decision of 2026-10-08 on its open question. Proof: `design.md`, Context.
  - 2026-10-08: the decision is "apply the default map automatically"; the risk c0144 named (nets swap on the next build of a design wired by pin number) is answered by the warning.
- [x] 0.2 Read from the catalog data which symbols and lands form a pair with opposite pin 1 and pad 1. Proof: `uv run pytest tests/unit/catalog/test_polarity_notes.py -q`.
  - 2026-10-08: three lands (as c0144) and five symbols with pin 1 `A`, pin 2 `K` (`Diode`, `LED`, `Photodiode`, `Schottky_Diode`, `Zener_Diode`).
- [x] 0.3 Find where `pad_map` reaches each target, and where the closed sets of build codes live. Proof: `design.md`, Context and Decisions 2 and 4.
  - 2026-10-08: both targets read `Component.pin_pad_map` of the model that `cmd_build` makes; the codes live in `lens.build.BUILD_ISSUE_CODES` (held by `tests/unit/lens/test_build_issues.py`), `src/fenolite/cli/data/explain.toml`, `docs/cli-contract.md` and the `design-dsl` spec. `dsl` and `lens` may not import `catalog` (`tests/unit/test_import_graph.py`).

## 1. The default map

- [x] 1.1 `fenolite.catalog`: `CATHODE_FIRST_LANDS`, `ANODE_FIRST_SYMBOLS`, `CATHODE_FIRST_PAD_MAP`, `default_pad_map`; the test holds them to the data. Proof: `uv run pytest tests/unit/catalog -q`.
  - 2026-10-08: passed (see 3.1 for the counts).
- [x] 1.2 `fenolite.cli._padmap.apply_default_pad_maps`, called by `cmd_build` (both targets), `_kit.build_sample` and `cmd_sync`. Proof: `uv run pytest tests/unit/lens/test_build_pad_map_default.py -q`.
  - 2026-10-08: 11 passed: the pad nets of both targets, the explicit map, other lands and symbols, an authored symbol or land, the kit samples.

## 2. The warning

- [x] 2.1 `build.pad-map-default` in `BUILD_ISSUE_CODES`, `cmd_build.pad_map_issues`, `explain.toml`, `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/lens/test_build_issues.py tests/unit/lens/test_build_pad_map_default.py tests/unit/cli/test_explain_cmd.py tests/consistency -q`.
  - 2026-10-08: passed.
- [x] 2.2 No pinned build, golden or kit sample moves. Proof: `uv run pytest tests/unit/lens/test_build_bytes_pinned.py tests/unit/verify/kit tests/unit/cli/test_kit_cmd.py -q`; `git diff --stat -- tests/data tests/unit/lens/test_build_bytes_pinned.py examples` is empty.
  - 2026-10-08: passed, no pin edited, the diff is empty.

## 3. Documents

- [x] 3.1 `docs/catalog/sources.md`, `docs/catalog/coverage.md`, `docs/dsl.md`, `CHANGELOG.md`; c0144 task 3.3 points here. Proof: `make check-fast`; `uv run python tools/gen_*.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
  - 2026-10-08: see the commit message for the counts.
- [x] 3.2 `openspec validate c0147-catalog-default-pad-map --no-interactive` and `openspec validate --all --strict --no-interactive` adds no error. Proof: the two commands with openspec 1.14.1.
  - 2026-10-08: the change is valid; with `--strict` it gives two "requirement text is very long" warnings, as most specs of the tree do with 1.14.1 (on the base 67 of 74 items fail `--all --strict` for that warning). `--all --strict` reports five errors, all in the older changes c0084, c0085, c0086 and c0128, none in this one. With 1.12.0 the change is valid with `--strict`. The MODIFIED requirement of `fenolite-component-catalog` is the one c0144 adds, so c0144 must be archived before this change (the CLI says so as an info).
- [ ] 3.3 Build a design of a 0.2.x user with one of these lands and no map in KiCad and Altium Designer and look at the swapped pads and the warning.
  - Open (2026-10-08): nothing was opened in KiCad or Altium for this change; the pads are proved by Fenolite's readers only.
