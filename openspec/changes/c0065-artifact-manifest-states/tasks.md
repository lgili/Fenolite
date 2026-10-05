## 0. Entry check

- [x] 0.1 List what this change builds on and what is there: `erc.kicad` in `STAGE_ORDER` (c0062), `sch.roundtrip_schematic` (c0060), `cmd_bom.py` and `cmd_pnp.py` (c0064). If c0064 is not archived, apply the first cut of the design (no `--manifest` on `bom` and `pnp`) and write it under this task; if c0062 is not archived, sheets stop at `roundtrip-ok` and the task says so. Re-read the living "Artefact manifest" and re-base the delta if it changed after 2026-10-04. Proof: `openspec list`; `openspec validate c0065-artifact-manifest-states --strict --no-interactive` passes.
  - 2026-10-05, on `origin/dev` at cfaedf8: `sch.roundtrip_schematic` is there (c0060); `cmd_bom.py` and
    `cmd_pnp.py` are there (c0064, not archived, its `--source kicad` not available), so `--manifest` on
    `bom` and `pnp` is kept and the `from` of a bill is the board's hash; `erc.kicad` is not in
    `STAGE_ORDER` (c0062 not started), so a sheet stops at `roundtrip-ok` and a symbol library and the
    symbol table at `checked` (design, "Corrections during implementation", 1). `build` writes no
    schematic yet (c0061) and `project_set` lists none, so the command finds `<stem>.kicad_sch` itself.
    The living "Artefact manifest" is unchanged since c0024; the delta needed no re-base.

## 1. Manifest fields and states

- [x] 1.1 Add `state`, `stale`, `from_` and `tool` to `ArtifactEntry`, `project`, `check` and `states` to `Manifest`, `STATES`, `load` and `design_kind` to `src/fenolite/exports/manifest.py`; regenerate `schemas/fenolite.artifacts.v0.json`; author `tests/data/exports/manifest_v01.json` in c0024's shape and declare it in `tests/data/MANIFEST.toml`; extend `tests/unit/exports/test_manifest.py` (MODIFIED "Artefact manifest"). Proof: `uv run pytest tests/unit/exports/test_manifest.py tests/unit/test_schema_drift.py tests/unit/test_repo_layout.py`; `uv run python tools/gen_schemas.py --check` exits 0; `uv run pyright src`.
- [x] 1.2 Write `src/fenolite/exports/states.py` and `tests/unit/exports/test_states.py` (scenarios of "Artefact states"), with a property test over generated stage mappings: the state never exceeds the lowest failing rung, a derived entry never exceeds `checked`, and no input gives `oracle-verified`. Proof: `uv run pytest tests/unit/exports/test_states.py tests/unit/test_import_graph.py`.

## 2. Merging in the producing commands

- [x] 2.1 Write `manifest.merge`, make `export --manifest` merge, and add the `manifest.*` codes to `exports/codes.py`; extend `tests/unit/cli/test_export_cmd.py` (scenarios of "Manifest merging"). Proof: `uv run pytest tests/unit/exports tests/unit/cli/test_export_cmd.py tests/consistency`.
- [x] 2.2 Add `--manifest` to `render`, `bom` and `pnp` (requirement "Manifest option of producing commands"); extend their tests. Proof: `uv run pytest tests/unit/cli/test_render_cmd.py tests/unit/cli/test_bom_cmd.py tests/unit/cli/test_pnp_cmd.py tests/consistency`.

## 3. The command

- [x] 3.1 Write `src/fenolite/cli/cmd_manifest.py` without the check: design files, artefact folders, hashes, `--no-check`, `--out`; write `tests/unit/cli/test_manifest_cmd.py` (scenarios "Hashes only" and "Artefact folder outside the project" of "Manifest command", and those of "Project manifest"). Proof: `uv run pytest tests/unit/cli/test_manifest_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
- [x] 3.2 Add the check: run the stages as `check` does, build the stage mapping and the sheet verdicts, assign the states, report the check's issues (scenarios "States from a check", "Errors still give a manifest" and "No tool"). Proof: `uv run pytest tests/unit/cli/test_manifest_cmd.py tests/unit/cli/test_check_readonly.py`; `uv run pyright src`.
  - Open for c0062: the scenario "States from a check" asked for `native-verified` on the schematic from
    `erc.kicad`. There is no such stage; the test pins `roundtrip-ok` with the reason in `held`.
  - 2026-10-05, by c0062: the stage exists; the test pins `native-verified` for both sheets and for
    `sym-lib-table`.
- [x] 3.3 Add `--verify` (scenarios "Verify an unchanged folder" and "Verify after an edit"). Proof: `uv run pytest tests/unit/cli/test_manifest_cmd.py -k verify`.

## 4. Oracle proof (both majors)

- [x] 4.1 Write `tests/kicad/export/test_manifest_oracle.py`: `examples/blink_routed` built with a schematic reaches `native-verified` for its board and its schematic and `checked` for its exported files; the unrouted blink leaves the board at `roundtrip-ok`; `--verify` passes right after, and fails after one exported file is edited. Proof: `uv run pytest tests/kicad/export/test_manifest_oracle.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
  - 2026-10-05: everything but the schematic's `native-verified` is written and passes: 3 passed on the
    local `kicad-cli` 10.0.6 and 3 passed inside the pinned `kicad/kicad:9.0.9` image. The routed blink
    gets an authored sheet next to its board (`build` writes none before c0061) and the test pins
    `roundtrip-ok` for it with the reason in `held`.
  - Open, waits for c0062 (`erc.kicad` in `STAGE_ORDER`): the schematic of the routed example reaching
    `native-verified`. The task stays unticked for that one assertion.
  - 2026-10-06, by c0062: `erc.kicad` is a stage. The test uses the schematic the build writes (no authored
    sheet) and pins `native-verified` for the board, the schematic, the two symbol libraries and their
    table of the routed blink: 3 passed on the local `kicad-cli` 10.0.6 and 3 passed inside the pinned
    9.0.9 image. `examples/blink_routed` marks its unused pins for that; its board is unchanged.


## 5. Documentation

- [x] 5.1 Update `docs/exports.md` with the five states (one line of rule each, and what the state does not claim), the merge, the `manifest` command and `--verify`; add the section "manifest" and the codes to `docs/cli-contract.md`. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0065-artifact-manifest-states --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
  - 2026-10-05, in the worktree: `make check-fast`, the residue suite and scan, `gen_schemas.py --check`
    and `openspec validate --strict` pass. Open: the full `make check` (the coordinator runs it once at
    the merge) and `gh pr checks` (the branch is not pushed).

- [x] 6.2 Evidence labels: this change registers no hypothesis. Confirm that no page or code comment claims a level for a state above the stage it comes from, and that `docs/exports.md` says `oracle-verified` is unused. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c 'oracle-verified' docs/exports.md` prints at least `1`.
- [x] 6.3 Add to `CHANGELOG.md` under Unreleased: "`fenolite manifest`: a project manifest with the SHA-256 and a state (`generated`, `checked`, `roundtrip-ok`, `native-verified`) for every design file and artefact, and `--verify` to compare it with the files on disk; `--manifest` on `export`, `render`, `bom` and `pnp` now merges into the folder's manifest". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
