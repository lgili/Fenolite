## ADDED Requirements

### Requirement: Read and write throughput is measured
`tests/unit/backends/kicad/test_throughput.py::test_read_write_5mib` SHALL measure, when `FENOLITE_CENSUS_OUT` names a file and only then, how fast Fenolite reads and writes a board of at least 5 MiB, and SHALL assert no time limit.
- The board MUST be built in memory by `tests/_boards.py::large_board(min_bytes=5 * 2**20)` from created entities with deterministic ids on the two-copper layer stack, and written with `write_board` for target 10.
- The test MUST time `read_board(text)` and `write_board(design, target=10)` with `time.perf_counter_ns` (S-0090), keeping the best of three runs of each, and MUST then measure the peak traced memory of one read and one write with `tracemalloc` (S-0091) in a separate pass.
- It MUST write the size in bytes, both times, the MiB per second of each, both peaks, the Python version and the platform through `tests/_boards.py::census`, and the numbers MUST be copied into `docs/evidence/kicad-board-read.md` with the machine described.
- Without `FENOLITE_CENSUS_OUT` the test MUST skip, so the `unit` job does not pay for it.

#### Scenario: Benchmark recorded
- **GIVEN** `FENOLITE_CENSUS_OUT` naming a file in a temporary folder
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_throughput.py -rA` runs
- **THEN** the census file holds a board of at least 5 242 880 bytes with read and write times, MiB per second and peak memory, and `git status --porcelain` is unchanged

#### Scenario: Skipped by default
- **GIVEN** `FENOLITE_CENSUS_OUT` unset
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_throughput.py` runs
- **THEN** the test is skipped and no board is built

### Requirement: Edge.Cuts outlines chain exactly
`tests/corpus/test_outline_census.py::test_edge_cuts_chain` (marker `needs_corpus`) and `tests/kicad/board/test_board_upgraded.py::test_outline_census` (markers `needs_kicad`, `needs_corpus`, `kicad_min_major(10)`) SHALL measure whether the board outlines of the corpus chain into closed rings by exact endpoint equality, which answers c0005's open question on a snapping tolerance for `assemble_rings`.
- **Pieces.** For each board, every root `Graphic` on a layer of kind `edge` MUST become pieces: a `line` one `Segment`, an `arc` one `Arc` through its three points, a `rect` four `Segment`s and a `polygon` one `Segment` per side. A `circle` is a closed ring by itself and MUST be counted, not chained. Zero-length segments MUST be counted and left out, as callers of `assemble_rings` do. Edge items inside footprints stay opaque and MUST only be counted.
- **Outcome.** `assemble_rings(pieces)` either returns rings, which MUST be counted, or raises `GeometryError`, whose code MUST be counted. For `geometry.open-contour`, the smallest distance between two loose endpoints MUST be recorded in whole nanometres, rounded up, in the buckets up to 1 µm, up to 10 µm, and larger.
- **Origins.** The 21 readable non-heavy native demos and the 3 upgraded third-party copies MUST be counted per origin through `tests/_boards.py::census` and copied into `docs/evidence/kicad-board-read.md`.
- **Verdict.** `H-G-EDGE-EXACT` holds when no board of either origin has two loose endpoints within 1 µm of each other. The tests MUST NOT fail on any outcome; the hypothesis row records it.

#### Scenario: Native demos measured
- **GIVEN** the `rt0` corpus cached
- **WHEN** `uv run pytest tests/corpus/test_outline_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** the census file holds, for the native demos, the boards whose outline chained, the failure codes with their counts, and the gap buckets

#### Scenario: Upgraded copies measured
- **GIVEN** the cached third-party rows and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py -k outline_census` runs
- **THEN** the same counts are written for origin `third-party`

#### Scenario: Small gap bucketed
- **GIVEN** four `Graphic` lines on `Edge.Cuts` that form a square, with one end moved 500 nm away from its neighbour
- **WHEN** `uv run pytest tests/corpus/test_outline_census.py -k gap` runs the census function on them
- **THEN** it records `geometry.open-contour` and a smallest gap of 500 nm in the bucket up to 1 µm
