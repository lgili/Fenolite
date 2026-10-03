## Context

- **Scope.** Plan item 0015 (plan day 20: "`fill.py` skeleton: temporary directory and the major requirement"; "temporary fill re-absorbed in the target version"). The roadmap row: "zone fill through `kicad-cli` 10 for both targets; fills read back from the saved board and merged by zone uuid, RT1 kept". c0013's design left the runner's container mode to this change.
- **Only 10.0 refills.** `pcb drc --refill-zones` and `--save-board` exist in 10.0 only (`H-K-01`, `KICAD-VERIFIED`; S-0022, S-0037). `--save-board` saves the board in the running version's format, so the saved copy of a target-9 board has version `20260206`.
- **The model already holds fills.** `model.board.ZoneFill(layer, polygon, island)` and `Zone.fills` exist since c0009; the reader lifts `filled_polygon` and the writer emits it. c0031 adds `Zone.settings`, `Zone.filled` and, for target 9, `(filled_areas_thickness no)` on created zones (`H-K-ZONE-FAT9`).
- **Rebuilds keep current fills.** c0019's `zone_digest` and `fill_inputs_digest` decide which fills a rebuild keeps, and `drop_stale_fills` drops the others with `zone.fill-stale` (living `layout-lens`, "Zone fills and the staleness digest"). Its premise, `H-K-LENS-FILL`, names this change's test `tests/kicad/fill/test_fill_oracle.py::test_kept_fill_matches_refill`.
- **The board is the layout authority** (`design-model`, "Layout authority"). A command that edits the board is kept by the next `build`.
- **Runner.** c0009's `KicadCli.run` copies its inputs into a fresh temporary directory and returns every file the run created or changed in `CliRun.outputs`; `KicadCli._require_ten` raises `KicadCliVersionError` (`FEN-6002`) below 10. c0013's `projectset.project_set` plans the files a DRC run reads, and `KicadOracle` wraps the runner behind `backends.base.Oracle`.
- **Observed at proposal time (2026-10-03, S-0020).** With `kicad-cli` 10.0.6 on c0013's authored project (`tests/_projects.py::authored_project`, one `GND` zone on `B.Cu`), for targets 9 and 10:
  - `pcb drc --format json --severity-all --refill-zones --save-board` exits 0 and its outputs hold the board, `<stem>.kicad_prl` and the report; the saved board has `(version 20260206)` and `(generator "pcbnew")`;
  - the saved board keeps the zone's uuid and holds one fill of 16 points on `B.Cu`;
  - the original model with those fills, written by `write_board` for its own target, loads on 10.0.6 with the violation types `isolated_copper`, `lib_footprint_issues` and `unconnected_items`;
  - the target-9 text loads on 9.0.9 (pinned image) with the same types; 9.0.9 prints "Legacy zone fill strategy is not supported anymore. Zone fills will be converted on best-effort basis." (the board had no `filled_areas_thickness`, c0031's flag);
  - two refills of the written board give equal fills, and they equal the lifted fills, point for point in nanometres.
- **Constraints.** Stdlib only. `checks` imports only `core`, `model`, `geometry` and `backends.base`. The roadmap gives this change 5 days.

## Goals / Non-Goals

**Goals:**
- `fenolite fill PATH`: fills computed by `kicad-cli` 10, written into the board for the board's own major, with every other byte of content kept by c0017's writer.
- The user's files are only replaced through the mutation protocol; `kicad-cli` sees copies.
- `check` says whether the board's fills are current, with the same oracle.
- A machine with KiCad 9 only can still fill, through a container.
- `H-K-LENS-FILL` settled.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A fill cache, or a fill inside `build`.
- `Oracle.upgrade` (c0020 owns the round-trip oracle).

## Decisions

1. **Probe first.** Task group 2 pins five facts before `fill.py` relies on them: the save (`fill-save-t9`, `fill-save-t10`), the lift (`fill-lift-t9`, `fill-lift-t10`), repeatability (`fill-repeat`), loading on 9.0.9 (`fill-load9`) and the kept-fill premise (`fill-kept`). Each has a fallback: Decision 5 (a saved board that drops a zone), Decision 6 (a lift that a second refill does not reproduce), Decision 9 (9.0.9 refusing lifted fills).
   - Rejected: writing the command first. c0006 to c0008 overran that way.

2. **Refill on the copy set, through the runner.** `KicadCli.refill(board, *, files=None) -> RefillRun` runs `pcb drc --format json --severity-all --refill-zones --save-board -o drc.json <board>` and returns the run and the saved board bytes (`CliRun.outputs[<board name>]`, or `None` when KiCad did not change the board). It calls `_require_ten("pcb drc --refill-zones")` first.
   - `KicadOracle.refill(project) -> FillOutcome` passes `project.files` without the board key, as `KicadOracle.drc` does, and never stages the canary: the refill must see the user's rules unchanged.
   - Rejected: a separate `pcb upgrade` and a refill-only command. `kicad-cli` has no refill-only command (S-0022).
   - Rejected: reading the DRC report of this run. `check` owns verdicts; the report is only named in `tool_writes`.

3. **Neutral types in `backends.base`.** `ZoneFills(zone_id: str, fills: tuple[ZoneFill, ...], filled: bool)`, `FillOutcome(zones: tuple[ZoneFills, ...] | None, tool_version: str, outcome: Literal["exit", "timeout"] = "exit", returncode: int | None = 0, message: str = "", supported: bool = True, evidence: Evidence = Evidence())` and the protocol `FillOracle` (`name`, `refill(project: ProjectSet) -> FillOutcome`).
   - `supported` is false when the tool cannot refill (major below 10); `zones` is then `None` and no run happens, so `checks` needs no version logic.
   - `zones` is `None` when no board was saved or the saved board did not read; `message` says why.
   - Rejected: returning a `Design`. `checks` needs only the fills, and a whole design would invite comparing more than fills.

4. **Lifting keeps the original model.** `fill.lift_fills(original: Design, refilled: Design) -> LiftResult` replaces, for each zone of `original`, `fills` and `filled` by those of the zone with the same id in `refilled`. Everything else stays `original`'s: settings are inputs of the fill (c0031's hand-over), and the saved copy is in another format version.
   - Zone ids are the uuids (c0009), and KiCad keeps them (`H-K-FILL-SAVE`).
   - Rule areas are untouched: they have no fill.
   - `LiftResult(design, changed: tuple[str, ...], unmatched: tuple[str, ...], counts)`; `changed` names the zones whose fills or flag differ.
   - Without c0031's `Zone.filled`, the flag part is skipped (Open Questions).

5. **A zone missing on one side is an error.** A zone of the original that the saved board lacks, or a new zone in the saved board, gives `zone.fill-mismatch` (error) naming the uuid, and nothing is written. `H-K-FILL-SAVE` says this does not happen; the error keeps a wrong lift from being silent if it does.
   - Rejected: dropping the fills of unmatched zones. A silent partial fill is worse than a refusal.

6. **Write for the board's own major.** `fill.fill_board(text, refilled_text, *, file="") -> FillResult` reads both texts with `read_board`, lifts, and writes with `write_board(design, target=<major of text>)`, the major coming from `versions.inspect`. `--kicad-version` is not consulted: `fill` never changes a board's format.
   - A KiCad 8 board is refused by `write_board` with `FEN-7003` (living `cli-contract`, "Legacy board edits are refused").
   - The written text MUST pass `roundtrip.rt1`, and c0017's "Written boards keep read content" keeps every other slot. A board saved by KiCad is rewritten in Fenolite's form, as c0019's first rebuild does; a second `fill` then changes nothing.
   - **Self-check.** Before returning, `fill_board` re-reads its text and requires the fills to equal the lifted ones; a difference raises `FormatError`. This catches a writer that cannot express a fill (for example a polygon with arcs).
   - Fallback if `fill-lift-*` records `different`: the row gets a `-2` successor recording what differs, `fill` reports `zone.fill-unstable` (warning) for those zones, and the stage of Decision 8 treats them as unchecked.
   - Rejected: copying `filled_polygon` text from the saved file. The saved file is in the 10.0 format; lifting through the model is what lets a target-9 board stay a target-9 board.

7. **`fenolite fill PATH`** (`cli/cmd_fill.py`, `mutates=True`). `PATH` resolves with `projectset.resolve_board`. Flags: `--kicad-cli PATH`, `--timeout SECONDS` (default 300), `--from REFILLED` and `-o/--out FILE`.
   - `--from REFILLED` lifts from a board that was already refilled and saved (by `kicad-cli` 10 elsewhere, or by the KiCad editor), and runs no tool. The same zone matching and self-check apply. It serves machines without a 10.0 binary, and it is the command's hermetic path.
   - `--out FILE` writes the filled board there, relative to the working directory, instead of replacing `PATH`'s board.
   - Without `--from`, pre-flight as `check`'s: no binary gives `FEN-6001`; a major below 10 gives `FEN-6002` with a hint naming `--from` and `--kicad-cli docker:<image>`.
   - No zone with a net: exit 0, `result.changed == false`, an info `zone.none`.
   - Fills already current (`LiftResult.changed` empty and the board already in Fenolite's form): no `PlannedWrite`, `changed == false`.
   - Otherwise one `PlannedWrite` for the board, relative to the working directory; the dispatcher's plan, backup and receipt apply.
   - `result`: `board`, `target`, `changed`, `zones` (`[{id, name, layers, fills, islands, filled}]` sorted by name then id), `tool_version`, `tool_writes`.
   - Issues: the read issues of the original board, `zone.fill-mismatch`, `zone.fill-unstable`, `zone.none`.
   - Evidence: `fill.EVIDENCE` with oracle `kicad-cli <version>`; with `--from`, the oracle is the `generator_version` of the refilled file and the level is `INFERRED`, because Fenolite did not run the tool.
   - `example_args` is `(EXAMPLE_UNFILLED, "--from", EXAMPLE_REFILLED, "--out", "fenolite-filled.kicad_pcb", "--dry-run")` and `mutation_example_args` the same without `--dry-run`: both run no subprocess, from any working directory (`cli/_examples.py`, as c0013's `EXAMPLE_BOARD`). `EXAMPLE_UNFILLED` is the authored target-9 board of Decision 11 without fills, and `EXAMPLE_REFILLED` the copy that `kicad-cli` 10.0.6 saved.

8. **Stage `zone.fill` in `check`.** `checks/fill.py::fill_stage(oracle: FillOracle, project, design) -> StageResult` runs before `drc.kicad` and compares each zone's fills with the oracle's, as sets of `(layer, island, normalised ring)`.
   - `zone.unfilled` (warning): the refill has fills and the board has none for that zone.
   - `zone.fill-stale` (warning): both have fills and they differ; the code and severity are c0019's.
   - `zone.fill-unchecked` (info): the tool cannot refill (`supported == false`); the stage is then `skipped` with reason `oracle-unsupported`, which this stage defines.
   - No report or a timeout gives `check.oracle-failed`, as in `drc.kicad`.
   - The stage needs the board model, so a refused read skips it with `read-refused`.
   - `STAGE_ORDER` becomes `model.validate`, `erc.lite`, `zone.fill`, `drc.kicad`, `roundtrip` (c0020 inserts its own stage after `drc.kicad`). The stage is selected by default and runs one more `kicad-cli` call.
   - Stage evidence: `FillOutcome.evidence`, lowered to `UNVERIFIED` when it reports `zone.fill-stale` or `zone.unfilled`.
   - Rejected: adding `--refill-zones` to the DRC run. DRC would then judge a board that is not the user's file.
   - Rejected: error severity. A stale fill is a state of the user's board that the next `fill` repairs; DRC still judges what is in the file.

9. **Target 9.** The flow is the same for both targets; only the writer differs. `fill-load9` proves on 9.0.9 that a target-9 board with fills computed by 10.0.6 loads, from a committed fixture (Decision 11).
   - c0031 archives first, so created zones carry `(filled_areas_thickness no)` and 9.0.9 plots the lifted fills at their size (`H-K-ZONE-FAT9`).
   - Fallback if 9.0.9 refuses the fills: `fill` writes target-9 boards unfilled, with `zone.unfilled` (the roadmap's later question), and the row gets a `-2` successor. The proposal-time run makes this unlikely.

10. **Container runner.** `backends/kicad/cli.py::DockerCli(KicadCli)` overrides the subprocess call: `docker run --rm --platform linux/amd64 -v <tmp>:/w -w /w -e KICAD_CONFIG_HOME=/w/config -e LANG=C -e LC_ALL=C <image> kicad-cli <args>`. The copy, the outputs diff and the sanitising stay `KicadCli.run`'s.
    - `find_kicad_cli` accepts `docker:<image>` as an explicit value and in `FENOLITE_KICAD_CLI`, and returns a marker that `cli_for(path, timeout)` turns into a `DockerCli`; `check`, `fill` and later commands build their runner with `cli_for`.
    - The image is never pulled by Fenolite: a missing image makes `docker run` fail, which gives `FEN-6001` with the hint to `docker pull` it.
    - `doctor` is unchanged: it lists files, and a container is not a file.
    - Rejected: the oracle harness's `--docker` (living "Execution modes"), which re-runs the whole harness inside the image and needs the repository mounted.

11. **Three committed fixtures** under `tests/data/kicad/fill/`: `triad_t9.kicad_pcb` (the authored target-9 project board, unfilled), `triad_t9_refilled.kicad_pcb` (the copy that `kicad-cli` 10.0.6 saved from it) and `triad_t9_filled.kicad_pcb` (what `fill_board` writes from the two). The 9.0.9 image has no 10.0 binary, so `fill-load9` needs the third; the first two are the command's example. `tests/kicad/fill/test_fill_oracle.py::test_fixture_is_current` regenerates the second and third on 10.0.6 and compares the fills and, for the third, the bytes. All three are declared in `tests/data/MANIFEST.toml`.

12. **`H-K-LENS-FILL`.** `test_kept_fill_matches_refill` builds the blink for the running target, fills it, rebuilds without a change (the fills are kept), refills the rebuilt board and requires equal fills. The same test changes a class clearance and requires `zone.fill-stale` and, after a new `fill`, different fills.

13. **Determinism.** `fill` output holds no temporary path and no date. Zones are sorted by name then id; fills by layer, island flag and points. Two `fill --confirm` runs give the same board bytes (`H-K-FILL-REPEAT`).

14. **No model, schema or FEN-code change.** `STAGE_ORDER` and `checks.codes.ISSUE_CODES` gain rows through ADDED requirements (c0013's Decision 10); no requirement of another change is MODIFIED.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` (extended) | `ZoneFills`, `FillOutcome`, `FillOracle` (Decision 3) |
| `src/fenolite/backends/kicad/cli.py` (extended) | `RefillRun(run: CliRun, board: bytes \| None)`; `KicadCli.refill(board, *, files=None) -> RefillRun`; `DockerCli(KicadCli)`; `DOCKER_PREFIX = "docker:"`; `cli_for(path, *, timeout) -> KicadCli` |
| `src/fenolite/backends/kicad/fill.py` (new) | `EVIDENCE`; `LiftResult`; `FillResult(text, changed, zones, issues)`; `lift_fills(original, refilled) -> LiftResult`; `fill_board(text, refilled_text, *, file="") -> FillResult`; `zone_fills(design) -> tuple[ZoneFills, ...]`; `ISSUE_CODES` |
| `src/fenolite/backends/kicad/oracle.py` (extended) | `KicadOracle.refill(project) -> FillOutcome` |
| `src/fenolite/checks/fill.py` (new) | `fill_stage(oracle, project, design) -> StageResult` |
| `src/fenolite/checks/{stages,codes}.py` (extended) | `zone.fill` in `STAGE_ORDER`; `run_checks(…, fill_oracle=None)`; rows `zone.unfilled`, `zone.fill-stale`, `zone.fill-unchecked` |
| `src/fenolite/cli/cmd_fill.py` (new) | `COMMAND` (`fill`, `mutates=True`; `PATH`, `--kicad-cli`, `--timeout`) |
| `tests/kicad/fill/` (new) | `_fillcases.py` (probes), `test_fill_probes.py`, `test_fill_oracle.py` |
| `tests/unit/backends/kicad/test_fill.py`, `test_docker_cli.py`; `tests/unit/checks/test_fill_stage.py`; `tests/unit/cli/test_fill_cmd.py` (new) | hermetic tests with `tests/_fakecli.py` (extended with `refill_board`) and a fake `docker` |
| `tests/data/kicad/fill/triad_t9_filled.kicad_pcb` (new) | Decision 11 |
| `docs/formats/kicad/board.md`, `cli.md`; `docs/cli-contract.md` | fill facts, the refill command and the container form, the `fill` section |

Layering: `backends.base` gains plain data; `checks.fill` imports `core`, `model` and `backends.base`; `cmd_fill` imports `backends` and `checks`. No `package-layering` change.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0205 | https://docs.docker.com/reference/cli/docker/container/run/ | to verify on the page | `docker run` options `--rm`, `--platform`, `-v`, `-w` and `-e` used by the container runner |

Rows of other changes cited here: S-0020 (observed `kicad-cli` 10.0.6 and 9.0.9 behaviour), S-0022 and S-0037 (CLI manuals), S-0029 (the pinned images), S-0010 and S-0038 (zone semantics). Task 1.1 widens S-0020 (the refill run, its outputs and the 9.0.9 message), S-0022 (`--refill-zones`, `--save-board`) and S-0029 (running `kicad-cli` from the images). S-0206 to S-0209 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-FILL-SAVE | `kicad-cli` 10.0 `pcb drc --refill-zones --save-board` saves the board with every zone uuid kept and with `filled_polygon` children for each zone that has copper, for boards of format 9 and 10 (S-0022, S-0020) | `tests/kicad/fill/test_fill_probes.py::test_save` | on 10.0.6, for the authored project of targets 9 and 10: the saved board is among the outputs, its zone ids equal the original's, and the `GND` zone has at least one fill; probes `fill-save-t9` and `fill-save-t10` = `present` |
| H-K-FILL-LIFT | The original model with the lifted fills, written by `write_board` for its own major, is reproduced by a second refill: equal fills per zone, layer and island flag (S-0020) | `tests/kicad/fill/test_fill_probes.py::test_lift` | on 10.0.6, targets 9 and 10: probes `fill-lift-t9` and `fill-lift-t10` = `equal` |
| H-K-FILL-REPEAT | Two refills of one board give equal fills (S-0020) | `tests/kicad/fill/test_fill_probes.py::test_repeat` | on 10.0.6: probe `fill-repeat` = `equal` over three runs of the authored project and of the built blink |
| H-K-FILL-LOAD9 | A target-9 board whose fills were computed by `kicad-cli` 10.0 loads on 9.0, and its DRC reports no violation type that the unfilled board lacks other than `isolated_copper` (S-0037, S-0020) | `tests/kicad/fill/test_fill_probes.py::test_load9` | on 9.0.9, for `triad_t9_filled.kicad_pcb`: probe `fill-load9` = `load`; the type sets of the filled and unfilled fixture differ at most by `isolated_copper` |
| H-K-CLI-DOCKER | `docker run` of the pinned `kicad/kicad` images with the run folder mounted gives the outputs that a local binary of the same version gives (S-0029, S-0205) | `tests/kicad/fill/test_docker_cli.py::test_container_matches_local` (skipped without Docker) | where Docker and the 10.0.6 image are present: equal `fill_board` text through `DockerCli` and through the local binary; the outcome is recorded in `docs/evidence/kicad-fill.md`, never in the probe files |

`H-K-LENS-FILL` (c0019) is settled by task 5.2 with its own row. Ids used without changing their level: `H-K-01`, `H-K-ZONE-FAT9`, `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-K-CHECK-COPYSET`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Refill and save | KICAD-VERIFIED (10.0.x), `H-K-FILL-SAVE` | `test_fill_probes.py::test_save` |
| Lift and write for the board's major | KICAD-VERIFIED (10.0.x), `H-K-FILL-LIFT` | `::test_lift` |
| Repeatable fills | KICAD-VERIFIED (10.0.x), `H-K-FILL-REPEAT` | `::test_repeat` |
| Target-9 fills load on 9.0 | KICAD-VERIFIED (9.0.x), `H-K-FILL-LOAD9` | `::test_load9` |
| Kept fills stay current | KICAD-VERIFIED (10.0.x), `H-K-LENS-FILL` | `test_fill_oracle.py::test_kept_fill_matches_refill` |
| `fill` command, lifting, self-check | mechanical | `test_fill.py`, `test_fill_cmd.py` |
| `zone.fill` stage | `fill.EVIDENCE` with the run's oracle; UNVERIFIED when unsupported | `test_fill_stage.py`, `test_fill_oracle.py -k stage` |
| Container runner | mechanical; KICAD-VERIFIED where run (`H-K-CLI-DOCKER`) | `test_docker_cli.py` |

`fill.EVIDENCE` starts `INFERRED` (`H-K-FILL-SAVE`, `H-K-FILL-LIFT`, `H-K-FILL-REPEAT`) and is raised in the closing task only when all three are `KICAD-VERIFIED (10.0.x)`.

## Budget (6.0 days; the roadmap gives 5)

| work | days |
|---|---|
| registers, format rows | 0.25 |
| probes, fixture | 1.0 |
| `refill`, types, `fill.py` | 1.25 |
| `fill` command | 0.75 |
| `zone.fill` stage | 0.75 |
| container runner | 1.0 |
| oracle proofs, `H-K-LENS-FILL` | 0.5 |
| docs, closing | 0.5 |
| **total** | **6.0** |

Cut order: (1) the container runner moves to c0025, and target-9 users need a 10.0 binary; (2) the `zone.fill` stage moves to v0.2a, and `check` then says nothing about fills. Not optional: the refill, the lift for both targets, the 9.0.9 load proof and `H-K-LENS-FILL`.

## Risks / Trade-offs

- [KiCad's fills differ between runs on real boards, as its DRC report does on some demo boards (c0013's evidence page)] → `fill-repeat` runs three times; the `zone.fill` stage compares against one refill, and a board whose two refills differ gives `zone.fill-unchecked` instead of a false `zone.fill-stale` (task 4.2 measures the 21 demo boards and records counts).
- [A fill with arcs or holes that the model cannot hold] → the self-check of Decision 6 refuses the write and names the zone; nothing is half-written.
- [c0031 moves to v0.2a] → this change takes its target-9 flag task (+0.25 day) and skips the `filled` flag (c0031's design, "Budget").
- [`check` gets slower by one `kicad-cli` run] → the stage can be left out with `--stages`.
- [Docker absent in CI jobs that run inside a container] → the container runner is proved with a fake `docker` in `unit`, and with the real images only locally.

## Migration Plan

Additive: a command, a stage, a module and a runner subclass. To roll back, remove them and drop `zone.fill` from `STAGE_ORDER` with its three codes.

## Open Questions

- **A saved KiCad file as a fixture.** `EXAMPLE_REFILLED` is written by `kicad-cli` 10.0.6 from a board authored for Fenolite, as c0010's `empty_10.kicad_pro` was saved by the KiCad editor. Default: commit it with its row in `tests/data/MANIFEST.toml`, and regenerate it only in `test_fixture_is_current`. To confirm.
- **`--from` and trust.** A refilled file from elsewhere may come from another board. Default: the zone uuids must match exactly, and any other difference between the two boards outside fills (footprints, tracks, rules cannot be compared: only the board is given) is not judged; `check`'s `zone.fill` stage is the proof of currency.
- **Severity of `zone.unfilled` in `check`.** Default: warning. The agent loop always runs `fill` before `check`; an error would fail every freshly built board.
- **Fill inside `build`.** Default: no. `build` stays hermetic; the loop calls `fill`.
- **Container default image.** Default: none; the user names it. c0025 may add a pinned default to the agent guide.
