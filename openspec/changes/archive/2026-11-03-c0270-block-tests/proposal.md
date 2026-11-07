## Why

A block of c0251 can be instantiated alone by c0256's `fenolite.testing.instantiate`, but nothing says what
a *library* block must ship to be trusted. Section 3.4 of `docs/research/circuit-blocks.md` (2026-10-29)
finds that one tool of the comparison requires a usage build per package in its CI, and that no tool ships
tests or requirements with a block. A block whose test cannot bring its own input voltage cannot check its
own expectations (c0253 judges only stated values), and a block whose output silently changes between
releases is not reusable.

## What Changes

- **The shipped test convention.** Each block of a block library has, beside its module:
  - `usage/<name>.py`: a complete design script that uses the block and **must build** (exit 0, nothing
    above `info` from the build and from the tool-free check stages);
  - `tests/test_<name>.py`: plain `test_*` functions on `fenolite.testing` (no pytest import) covering
    the arithmetic, the ratings, the netlist and, once the block has a layout (c0271), the layout's
    properties;
  - `golden/<name>.json`: the canonical JSON (`fenolite.block-golden.v0`) of the usage build's
    `circuit.json` and `rules.json` under `--seed 0 --timestamp 2026-01-01T00:00:00Z`.

  Shipped (`Fenolite:`) blocks must have all three; a project block missing one gets a warning.
- **`instantiate(block, *, stimulus=None, **params)`**: `stimulus(HI=volt("12").pct(2), LO=volt(0))`
  states the outside world on the block's ports as c0253 rig elements (`supply`, `sink`), so the block's
  expectations are judged in the test. A rig never reaches an output (c0253).
- **`TestDesign.requirements(pattern)`** returns c0253's requirement-table rows; **`TestDesign.achieved(path)`**
  returns what a c0254 generator achieved; **`PartView`** gains `at`, `rotation` and `side` from the built board.
- **`fenolite blocks test [ID...] [--golden]`** builds each usage example, compares its golden file, and
  runs the test functions, reporting each result as a finding; `--golden` regenerates golden files
  through `--dry-run` / `--confirm --plan`.
- **CI** runs `fenolite blocks test` for the shipped library in the unit jobs, and builds every usage
  example for KiCad targets 9 and 10 in the KiCad jobs.

## Non-goals

- No pytest plugin, fixture or entry point; no test discovery beyond the convention.
- No raster or render goldens here (c0256's `assert_render` stays available to block tests).
- No sandbox: a block's tests are Python code run in process, as a design script is.
- No block content: the starter blocks are c0272.

## Evidence level required

- The runner, stimulus and goldens: `INFERRED`, unit-tested on authored blocks.
- Golden stability across systems: `INFERRED` with `H-G-BLOCK-GOLDEN` (same bytes on Linux, macOS and
  Windows, Python 3.11 to 3.13), measured by the unit jobs.
- Usage boards: `KICAD-VERIFIED` read-back of connectivity for targets 9 and 10, as any build.

## Dependencies

c0256 (`fenolite.testing`, `instantiate`), c0253 (rig, expectations, requirement table), c0251 (blocks,
ports), c0268 (block records and the `fenolite blocks` command group). Uses c0254 (`gen.achieved`) and
c0271 (layout properties) when present. Implemented after c0268 and c0256, before c0272.

## Impact

- New: `src/fenolite/testing/stimulus.py`, `src/fenolite/testing/blocks.py` (the runner),
  `cli/cmd_blocks.py` verb `test`, `tests/unit/testing/test_stimulus.py`,
  `tests/unit/blocks/test_runner.py`,
  `tests/data/blocks/` (authored blocks), `examples/blocks/`.
- Changed: `testing/__init__.py`, `testing/design.py`, `explain.toml`, `.github/workflows/ci.yml`,
  `docs/testing.md`, `docs/cli-contract.md`, guide page `design-script`, `CHANGELOG.md`.
- Size: about 4 design-days (S).
