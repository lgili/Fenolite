## 1. The rule and its tests

- [x] 1.1 Write the failing tests: in `tests/unit/exports/test_bom.py`, the scenario "DNP parts never share a line with fitted parts" for parts from `parts_from_model` and from `parts_from_kicad`, the order by first reference, the unchanged keys when `group_by` names `dnp` or is empty, and the scenario "A DNP part becomes fitted"; in `tests/unit/cli/test_bom_cmd.py`, `fenolite bom` with `--source model` on an authored board and with the `kicad` source through the fake `kicad-cli` (a bill with a value that is not ASCII), each with `exclude_dnp` false and true. Proof: `uv run pytest tests/unit/exports/test_bom.py tests/unit/cli/test_bom_cmd.py -q` fails in the new tests only.
  - 2026-10-06, before the change of `group`: 6 failed (the two sources of the scenario, the order, the difference, and the two command tests), 38 passed. The test of the unchanged keys passes before and after, as it must.
- [x] 1.2 Change `group` in `src/fenolite/exports/bom.py` (design Decisions 1 to 4) and the docstrings of the module, of `BomLine` and of `group`. Proof: `uv run pytest tests/unit/exports tests/unit/cli/test_bom_cmd.py tests/unit/cli/test_pnp_cmd.py -q` passes.
  - 2026-10-06: 202 passed.

## 2. Docs and records

- [x] 2.1 Update `docs/assembly.md` (what a line is, where DNP lines sort, the `dnp` field, `exclude_dnp`, `--against`, "Things to watch") and `docs/cli-contract.md` (`bom`: the rule and the `key` of a change). Check `docs/release/v0.2.md`, row "v0.2a item 5", for a limit about DNP grouping and write under this task what was found. Proof: `uv run pytest tests/unit/exports/test_assembly_guide.py tests/unit/test_release_record_v02.py -q` passes; `grep -c 'share one line and one quantity' docs/assembly.md` prints `0`.
  - 2026-10-06: the row "v0.2a item 5" says `met` and has no entry under "Recorded limits"; the record does not mention DNP grouping anywhere, so it is unchanged. No golden CSV and no printed example changes.
- [x] 2.2 Add the entry to `CHANGELOG.md` under `### Fixed` of `[0.2.0]` (the release cut exists, so not under Unreleased) and the row `c0094` to the id table of `openspec/README.md`. Proof: `uv run pytest tests/unit/test_release_record_v02.py tests/unit/test_release_record.py -q` passes; `grep -c '| c0094 |' openspec/README.md` prints `1`.

## 3. Closing checks

- [x] 3.1 Run the closing checks, each with its log in a file and its exit code read. Proof: `openspec validate --all --strict --no-interactive` passes; `make check-fast` passes; `uv run pytest tests/corpus/test_manifest.py -q` passes; `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/assembly -q` passes on the local `kicad-cli` 10.0.6 and the same folder passes inside the pinned 9.0.9 image; `python3 tools/dco_check.py int-batch11..HEAD` prints nothing.
  - 2026-10-06, every exit code 0: `openspec validate --all --strict` 54 passed; `make check-fast` 8547 passed, 16 skipped; the corpus manifest test 47 passed; `tests/kicad/assembly` 23 passed on `kicad-cli` 10.0.6 and 23 passed in the 9.0.9 image; the sign-off check printed nothing.

_Note: the full `make check` is run once by the coordinator at the merge. The change is archived by the coordinator._
