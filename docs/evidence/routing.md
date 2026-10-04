# Routing evidence

The feasibility gate runs KiCadRoutingTools `v0.22.1` against the built blink for target 9 under
`kicad-cli` 9.0.9 and target 10 under `kicad-cli` 10.0.6. Outcomes are recorded here and in a
tag-specific JSON result when the optional CI job runs. `equal` for each route means there are no
unconnected items and no new error-severity DRC types versus the unrouted board. Repeatability is
recorded but does not gate the change.

Tool setup: source tag `v0.22.1`, commit `023d3f79027d5406e4ea8e68291f588c5c135673`; macOS arm64,
CPython 3.13.5. The `grid_router-macos-arm64.so` asset was downloaded from that GitHub release with
`gh release download` and checked against its release API SHA-256
`2c7f22829e0a32f328e6e75e0f587e544cd19316eed6c75580b0abdb027893a5`; it was installed at
`rust_router/grid_router.so` in the checkout outside this repository. `build_router.py --tag v0.22.1`
could not reach GitHub from Python and Rust is not installed here; the direct, digest-checked release
asset runs successfully. The tool states its version in the checkout's `VERSION` file (`0.22.1`).

For target 9, the same checkout's Linux x86_64 release asset (`grid_router-linux-x86_64.so`) was
downloaded into `/tmp/fenolite-c0016-kicadroutingtools-linux/rust_router/grid_router.so`; its SHA-256
`652b67e266c58b1e373e503bcf9b5d0b0d3dd4756e1c306100f23edf3d3f989b` matches the GitHub release API
digest. The gate ran in the pinned `kicad/kicad:9.0.9` Linux x86_64 image with CPython 3.11.2,
KiCad 9.0.9 and pytest 9.1.1. A separate temporary venv held pytest and the tool's dependencies; Fenolite
was imported from the mounted worktree. The pinned image ran under x86_64 emulation on the macOS arm64
host.

| probe | target 9 / KiCad 9.0.9 | target 10 / KiCad 10.0.6 | meaning |
|---|---|---|---|
| `krt-cli` | present | present | command arguments, output board and passed track width |
| `krt-route` | equal | equal | unconnected items and new error types |
| `krt-keep` | equal | equal | equality of all non-copper model content |
| `krt-repeat` | equal | equal | route geometry from two runs |

Verdict: passed. Both target-major route outcomes are equal: no unconnected items and no new DRC error types.

- `krt-cli-t10`: `present` (`v0.22.1`).
- `krt-route-t10`: `equal` (`v0.22.1`).
- `krt-keep-t10`: `equal` (`v0.22.1`).
- `krt-repeat-t10`: `equal` (`v0.22.1`).
- `krt-cli-t9`: `present` (`v0.22.1`).
- `krt-route-t9`: `equal` (`v0.22.1`).
- `krt-keep-t9`: `equal` (`v0.22.1`).
- `krt-repeat-t9`: `equal` (`v0.22.1`).

The integrated router gate and `build` → `place` → `route` → rebuild → `fill` → `check` loop also
passed on both target majors in CI run 37197766881 (KiCad 9.0.9 and 10.0.6).
- `krt-cli-t9`: `present` (`v0.22.1`).
- `krt-keep-t9`: `equal` (`v0.22.1`).
- `krt-repeat-t9`: `equal` (`v0.22.1`).

## Freerouting (c0023)

What was observed when Freerouting was run on design files written by `fenolite.backends.specctra`.
The machine-readable outcomes are in `routing/freerouting-2.4.1.json`.

### The tool

| item | value |
|---|---|
| tool | Freerouting 2.4.1 (S-0223), GPL-3.0, run as a subprocess; never imported, vendored or downloaded by Fenolite (ADR-0006) |
| file | `freerouting-2.4.1.jar`, from the release page of the tag `v2.4.1`, installed by the maintainer outside the repository on 2026-10-04 |
| size | 64 076 787 bytes |
| SHA-256 | `251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9`, checked on the installed file; equal to the digest the release lists |
| what it prints | `Freerouting v2.4.1 (build-date: 2026-09-03)`; `-help` prints its usage |
| Java | OpenJDK 26.0.2 (Homebrew build), which satisfies the Java 25 the release asks for |
| platform | macOS 26.6 on arm64 (Darwin 25.6.0) |
| command | `java -jar <jar> -de board.dsn -do board.ses -mp 20 -mt 1 -da --gui.enabled=false`, in a fresh temporary folder that is also `HOME` |
| test | `tests/routing/test_freerouting_gate.py`, marker `needs_freerouting`, `FENOLITE_FREEROUTING_JAR` |

### Outcomes on 2026-10-04

| outcome | value | hypothesis | what was seen |
|---|---|---|---|
| `dsn-accept` | `present` | `H-G-DSN-ACCEPT` | a readable session for the two-pad board (1 wire) and for the built blink of target 10 (5 wires, 1 via); no list the reader does not know |
| `dsn-units` | `equal` | `H-G-DSN-UNITS` | the route of the two-pad board ends on both pad centres: largest distance 0 nm |
| `dsn-protect` | `equal` | `H-G-DSN-PROTECT` | with `LED_A` of the blink routed beforehand, the session repeats that wire unchanged with its `protect` type, and `to_copper` returns nothing on the net |
| `dsn-route-t10` | `equal` | `H-G-DSN-ROUTE` | the built blink of target 10 under the local `kicad-cli` 10.0.6, routed with `fenolite route --router freerouting` and filled: 3 nets selected, 11 tracks and 1 via; 3 unconnected items before, 0 after, no new error type. The same result came first from a helper that merged the session's copper with `routing.merge.apply` (the day-6 gate) |
| `dsn-route-t9` | `equal` | `H-G-DSN-ROUTE` | the built blink of target 9, routed the same way on the host and judged by `kicad-cli` 9.0.9 in the pinned image `kicad/kicad:9.0.9` (already local, run under emulation): 11 tracks and 1 via; 3 unconnected items before, 0 after, no new error type |
| `dsn-repeat` | `equal` | `H-G-DSN-REPEAT` | two runs on the blink's design file with `-mt 1` gave the same 5 wires and 1 via |

**Day-6 gate of c0023: passed on 2026-10-04.** `dsn-accept` and `dsn-route-t10` hold.

`dsn-offline` = `present`, recorded on 2026-10-04. The image `ghcr.io/freerouting/freerouting:2.4.1` (index digest `sha256:67794b10c4565c259461343cf6db4158e6a5c5baa7c2f93030d045974f313074`, `linux/arm64`) was pulled by the maintainer's decision and run with `--network none`: it wrote a session with one track for the two-pad board. The image's default command starts its API server, so the plugin runs `java -jar /app/freerouting-executable.jar` followed by its own arguments; the first attempt, which passed the arguments alone, failed in the image's entry script. The plugin's `sends_data_offsite` is `False` since this run.

The loop `build` → `place` → `route --router freerouting` → rebuild → `fill` → `check` (`tests/routing/test_freerouting_oracle.py::test_loop`) passed on the local KiCad 10.0.6: the second build kept every routed track and via, and the DRC found no unconnected item. Its KiCad 9 run is left to the `routing` CI job, which runs inside the 9.0.9 image.

### What the sessions showed

- The session repeats the placement of every component, under its own `(resolution um 10)`, in database
  units, with `front`, rotation 0 and the lock. The reader was narrowed to that: a placement that declares
  a resolution is read as database units only.
- The session's `routes` section declares `(resolution um 10)`; its numbers are whole database units.
- The via padstack keeps the name the writer gave it; the session quotes it.
- Protected input wiring is repeated in `network_out`, marked `(type protect)`.
- Nothing but `board.dsn` and `board.ses` was left in the run folder.
- No fact of `docs/formats/specctra/` was refuted. The labels of the fact pages and of the hypothesis rows
  stay `INFERRED` until task 6.2 of c0023 raises them from this record.

The runs with the jar say nothing about the network: `-da` was passed. The run without a network
(`H-G-DSN-OFFLINE`) is the container run recorded above.
