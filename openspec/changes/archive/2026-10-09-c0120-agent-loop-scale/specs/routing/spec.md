## ADDED Requirements

### Requirement: Router runs reported for progress and resumption
`fenolite.routing.protocol` SHALL let a router report each of its tool processes while it works, so that the command can show progress and keep what finished. "Router protocol" is unchanged: the new fields have defaults, and a router that ignores them stays valid.
- `FinishedRun(nets: tuple[str, ...], tracks: tuple[Track, ...] = (), arcs: tuple[Arc, ...] = (), vias: tuple[Via, ...] = (), tier: int = 0, seconds: float = 0.0)` MUST be a frozen dataclass on `core` and `model` types: the copper that one tool process added and the nets it routed.
- `RoutingJob` MUST gain `on_run: Callable[[FinishedRun], None] | None = None` and `progress: Progress = NULL_PROGRESS` (`fenolite.core.progress`).
- A plugin that starts tool processes MUST report each process as one unit of progress (`step` when it starts, `done` when it ends), and MUST call `on_run` once for each process that ended with copper, with that copper, before it starts the next process. A process that failed, was cut by a time limit or gave no copper MUST NOT be reported through `on_run`.
- The KiCadRoutingTools plugin MUST treat each of its processes as a unit: one per group of nets, and one per net with `--router-option group-nets=1`. The Freerouting plugin MUST treat each tier as a unit: its one process for a job without tiers, and the optimizer run of `optimize=on` belongs to the unit of its tier. `FinishedRun.tier` is the tier of the nets of the run. The built-in direct router starts no process and MUST call neither.
- The copper of all `FinishedRun`s of one `route` call MUST equal the copper of its `RoutingResult`.
- `fenolite.routing` MUST still import only `core`, `model` and `geometry`.

#### Scenario: One call per finished process
- **GIVEN** the fake KiCadRoutingTools of the routing tests, routing three nets with one process per net (`group-nets=1`), of which the second fails
- **WHEN** `uv run pytest tests/unit/routing/test_finished_runs.py` routes a job with a recording `on_run` and a recording `Progress`
- **THEN** `on_run` was called twice, for the first and the third net, each before the next process started; the reporter saw three `step` and three `done` records; and the tracks and vias of the two runs together equal those of the result

#### Scenario: A router that ignores the fields
- **WHEN** the direct router routes the same job
- **THEN** `on_run` is never called, and the result equals the result of a job without the two fields
