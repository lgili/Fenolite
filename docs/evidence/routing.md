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

## Open connections (c0108)

`fenolite route` selects the nets that still have open connections and takes its verdict from the board
after the merge. The count per net comes from `analysis.connectivity`; this section records how it
compares with KiCad's `unconnected_items` (`H-K-CONN-PARITY`).

### The bench

`tests/kicad/copper/_openbench.py`: 19 cases, one net each. Recorded on 2026-10-07 with the local
`kicad-cli` 10.0.6 (macOS), through `tests/kicad/copper/test_open_parity.py`:

| probe | 10.0.6 | 9.0.9 |
|---|---|---|
| `copper-open-kicad` (KiCad's count per case against the table of the bench) | `equal` | not run by the committed test (CI, pinned image) |
| `copper-open-parity` (KiCad's count per case against the query's) | `equal` | not run by the committed test (CI, pinned image) |

When the change was proposed (2026-10-05) the same 19 cases were measured on 9.0.9 under the pinned image
with a script that is not committed, and gave the same counts.

### The census

`tests/corpus/test_open_census.py`, on the corpus manifest of the base of this change, local `kicad-cli`
10.0.6, 2026-10-07. The 21 readable boards that are not heavy (the two heavy demo boards were left out;
`FENOLITE_HEAVY=1` includes them):

| boards | open connections (query) | unconnected items (KiCad 10.0.6) | nets that differ |
|---|---|---|---|
| `kicad-demo-10-0-6-pcb-09` | 148 | 148 | 0 |
| `kicad-demo-10-0-6-pcb-16` | 1 | 1 | 0 |
| `kicad-demo-10-0-6-pcb-11` | 2 | 0 | 1 |
| the 18 others | 0 | 0 | 0 |

- No board reached KiCad's cap of 499 unconnected items.
- `kicad-demo-10-0-6-pcb-11` is the board whose copper drawings hold a net: two drawings on a copper
  layer carry a `net` child, KiCad counts them as copper of that net, and the model keeps a drawing's
  `net` as an opaque child. The query therefore reports 2 open connections that KiCad does not. Copper
  drawings with a net are not modelled (`docs/analyses.md`, "Open connections").
- `kicad-demo-10-0-6-pcb-14` holds four such drawings and gives equal counts.
- The census under 9.0.9 was not run here: it needs the pinned image.

### Routers on nets that hold copper

`H-G-DSN-PARTIAL` (Freerouting) and `H-K-KRT-PARTIAL` (KiCadRoutingTools) say what a router does with a
selected net that already holds copper. First record, 2026-10-05, with the Freerouting plugin called
directly by a script that is not committed: 8 nets of 7 kinds (a stub; three pads, two joined; a fan-out of
a track, a via and a `B.Cu` stub; a via beside the pad; a floating via of the net), all 8 closed by wires
that join the existing copper, 0 unconnected items by `kicad-cli` 10.0.6 after the merge. No
KiCadRoutingTools checkout was at hand.

Recorded on 2026-10-07 through `fenolite route --router freerouting --confirm`
(`tests/routing/test_open_nets.py -k freerouting`, results in
`docs/evidence/routing/freerouting-2.4.1.json`), with the jar 2.4.1 of the digest above, Java 26.0.2 and
the local `kicad-cli` 10.0.6:

| outcome | value | what was seen |
|---|---|---|
| `dsn-partial` | `equal` | the five kinds of the bench (a stub; three pads, two joined, the third nearest to a pad; a fan-out of a track, a via and a `B.Cu` stub; a via beside the pad; a floating via): 6 open connections before, 0 after by the query, no unconnected item of those nets by KiCad, every earlier copper item still on the board with its uuid; 10 tracks added, no via |
| `dsn-partial-tee` | `different` | a sixth net whose third pad lies below the middle of the track that joins the two others: the connection stays open. `result.unrouted` names the net, `result.open` gives the connection, and KiCad reports the same single unconnected item |
| `krt-partial` | not run | no KiCadRoutingTools checkout on this machine; the `routing` job records it |

What the limit is, from four more runs of that day on one net of three pads (not committed as a test):

- the third pad below the middle of the single joining track: open, also on a second run of the same net;
- the third pad nearest to a pad of the pair (left or right of it): closed;
- the pads joined by two tracks that meet in the middle, the third pad below that point: closed;
- the first case with `--rip --nets <net>`: closed (the joining track is removed and the net routed again).

So Freerouting 2.4.1 joins new copper to a pad or to the end of a protected wire, and does not split a
protected wire. `fenolite route` reports such a net under `unrouted` with its open connection;
`docs/routing.md` says what to do.

## Scale (c0109)

How the two external routers behave on a board of a hundred parts, what change c0109 built from it, and
the probes of its two Freerouting defaults.

### The record of 2026-10-05

These numbers were measured on 2026-10-05, before the change was written, by the review that proposed it;
they are copied here from the change's design ("Context"). **They were not measured again when the change
was built (2026-10-08), and the bench is not in the repository.** The design states that the bench is a
generated board made by a script written for Fenolite, whose net names (`ch01_*` and so on) and sizes are
what the generator gives for 100 parts and come from no existing board. That statement could not be
checked against the script when the change was built, because the script is not committed; task 1.2 of
the change stays open until the numbers are measured again on a bench authored for that purpose (the
yardstick board of c0119 is one).

- **Tools.** Freerouting 2.4.1 (the jar of the digest above, OpenJDK 26.0.2), the KiCadRoutingTools
  `v0.22.1` checkout, `kicad-cli` 10.0.6, macOS arm64.
- **Load.** The machine was shared with other runs (load average 33 to 88 on 10 cores), so wall times are
  upper bounds; Freerouting's own CPU seconds are given beside them.
- **Bench.** 4 copper layers, 76 × 92 mm, 100 parts (an LQFP-100 controller, 5 ICs, 90 passives,
  3 headers), 103 nets. GND is a zone on `In1.Cu` and +3V3 a zone on `In2.Cu`, and each of their 84 SMD
  pads already has a stub and a via to its plane. Classes PWR (0.4 mm track, 0.2 mm clearance) and SIG
  (0.2 mm, 0.15 mm); Default 0.2 mm and 0.2 mm. Unrouted, KiCad counts 128 unconnected items.
- **Judge.** Each routed copy was merged with `routing.merge.apply`, filled with `fenolite fill` and
  checked with `fenolite check` on KiCad 10.0.6.

Freerouting. Runs 2 to 4 call the jar directly with
`java -jar freerouting-2.4.1.jar -de board.dsn -do board.ses -mp 20 -mt 1 -da --gui.enabled=false` plus
the arguments named, on the design file the plugin wrote for the job of run 1.

| run | command | nets selected / declared | stages and time | copper added | on plane layers | KiCad after `fill` |
|---|---|---|---|---|---|---|
| 1 | `fenolite route <board> --router freerouting --timeout 900 --confirm`, the plugin before this change | 101 / 103 | fanout 21 s; autorouter on 191 items, 0 unrouted after 6 passes at 256 s (119 CPU s); optimizer from 259 s, killed at 900 s; exit 5 after 912 s | none: 101 `route.unrouted`, `route.tool-failed` | – | 128 unconnected items, as before |
| 2 | the same design file with `--router.optimizer.enabled=false` | 101 / 103 | the same passes and scores; session saved when the autorouter ended: 863 s wall under load, 203 CPU s | 1190 tracks and 197 vias on the 101 nets; 185 of the 525 session wires were on GND and +3V3 and were dropped | 661 tracks on `In1.Cu` and `In2.Cu`, which split the planes into 8 and 5 fills | 11 unconnected items, all between GND or +3V3 stubs and plane islands; `track_width` 2 (two 0.12 mm segments under the 0.15 mm minimum); Fenolite's copper check: 0 findings |
| 3 | the same, with GND and +3V3 left out of the network section (pins on no net, stubs and vias protected without a net) | 101 / 101 | autorouter on 103 items, 0 unrouted after 4 passes; session at 423 s wall, 112 CPU s (45 % less than run 2) | 1084 tracks and 190 vias; no wire on GND or +3V3 | tracks on both plane layers again (10 and 13 fills) | 21 unconnected items, all on GND and +3V3 plane islands; no `track_width`, no clearance violation. Freerouting's own score counted 256 "violations" instead of 83; KiCad found none of them |
| 4 | the built blink (3 nets), four variants | 3 / 3 | with `-mt 0` and with `-mt 1` the log shows "Optimization stage started"; with `--router.optimizer.enabled=false` none, and the session is saved when the autorouter ends | – | – | a class `IGN` holding LED_A, named with `-inc IGN` (first or last argument) or with `--router.ignore_net_classes=IGN`, was routed every time ("3 unrouted items", 2 wires on LED_A); with GND left out of the network section: "2 unrouted items", no wire on GND |

KiCadRoutingTools (run 5). Every call is
`route.py <board> <out> --nets <names> --track-width 0.2 --via-size 0.6 --via-drill 0.3 --json-out <file>`
plus the flags named, in a folder written by `write_triad`.

| nets | how | time (load) | closed | copper | KiCad |
|---|---|---|---|---|---|
| 28 (`ch01_*`) | one process per net, the plugin before this change | 527 s (27 to 45) | 28 | 345 tracks, 57 vias; 8 `route.copper-removed` | `tracks_crossing` between `ch01_M4` and `ch01_P3` (copper check: one short); one via of 0.3 mm with a 0.15 mm drill where the class asks 0.6 mm and 0.3 mm (`via_diameter`, `drill_out_of_range`, `annular_width`) |
| 28 | one process, no `--clearance`, the tool's default escalation | 136 s | 28 | "389 feature(s) on 10 net(s) delivered below the requested size" | no crossing, no short; the same three via errors |
| 28 | the same with `--escalation off` | 24 s | 28 | every track 0.2 mm, every via 0.6 mm with a 0.3 mm drill | no DRC error |
| 101 | one process, the default escalation | 296 s | 101 | 2261 features under the requested size on 43 nets, tracks down to 0.0889 mm | `track_width` 199, `via_diameter` 14, `annular_width` 14, `drill_out_of_range` 12, `hole_clearance` 6 |
| 101 | one process with `--escalation off --no-fix-drc-settings` | 70 s (13 to 22) | 94; the 7 others named by the tool's summary and open in KiCad | – | no other DRC error; copper check clean |

What the change took from it: one budget for the whole step and kept runs (run 1 lost everything at the
limit), the optimizer off (run 2), only the job's nets in the design file (run 3), one KiCadRoutingTools
process per group of equal sizes with `--escalation off` and `--no-fix-drc-settings` (run 5). `-inc` and
`-mt 0` were rejected (run 4).

### Probes on 2026-10-08

`tests/routing/test_freerouting_gate.py -k "no_optimizer or netless"`, with the jar 2.4.1 of the digest
above, OpenJDK 26.0.2 and the local `kicad-cli` 10.0.6 (macOS arm64); the machine-readable outcomes are in
`routing/freerouting-2.4.1.json`.

| outcome | value | hypothesis | what was seen |
|---|---|---|---|
| `dsn-noopt` | `absent` | `H-G-DSN-NOOPT` | the blink's design file with `--router.optimizer.enabled=false`: no "Optimization stage" line, and a session with wires |
| `dsn-mt0` | `present` | `H-G-DSN-NOOPT` | the same file with `-mt 0` and without the setting: the optimization stage is logged, as it is with `-mt 1` |
| `dsn-netless` | `present` | `H-G-DSN-NETLESS` (refuted) | `netless_bench` of `tests/_specctra.py`: the net B, in a class with a 0.4 mm clearance, left out of the network section between the routed nets A and C; default rule 0.2 mm. No session wire on B, and both routes pass 0.3 mm from the pads of B: KiCad reports 2 `clearance` violations. The same copper judged with B in the default class: 0 violations |
| `dsn-netless-declared` | `absent` | `H-G-DSN-NETLESS-2` | the same bench as `write_dsn(..., others="netless")` writes it since the fallback: B stays declared with its class, the two routes bend away (10 tracks instead of 2), and KiCad reports 0 `clearance` violations |
| `dsn-inc` | `present` | `H-G-DSN-NETLESS` | the bench with B open and declared, and `-inc WIDE` as the first and as the last argument: a session wire on B both times, so `-inc` does not keep a class out of the autorouter |
| `krt-group-t9`, `krt-group-t10` | not run | `H-K-KRT-GROUP` | no KiCadRoutingTools checkout on the machine of the implementation; `tests/routing/test_krt_gate.py::test_group` waits for the `routing` job and for the pinned 9.0.9 image |

**The fallback taken.** Freerouting 2.4.1 keeps the default rule, and no more, from pins and wiring that
have no net. A net outside the job whose class clearance is larger than the default rule therefore stays
declared in the design file, with its class (`backends.specctra.dsn`, "Nets outside the routing job in
design files"), and `route.net-declared` (info) names such nets. Every other net outside the job leaves
the network section. The cost: Freerouting also routes a declared net that is still open, and that copper
is not taken.

**Gates kept with the command lines of this change** (optimizer off, other nets left out), on the local
`kicad-cli` 10.0.6 on 2026-10-08: `test_route[t10]` of the Freerouting gate records `dsn-route-t10` =
`equal` with the same 11 tracks and 1 via as before; `tests/routing/test_acceptance_loop.py` passes (the
blink and `board_40parts`, built for KiCad 9 and 10, both judged by the local 10.0.6: 3 of 3 and 39 of 39
nets closed, no DRC violation, no unconnected item). The runs under 9.0.9 (`dsn-route-t9`, the
KiCadRoutingTools gate) were not made: they need the pinned image and the checkout.
