## Context

- **Source.** `docs/research/circuit-blocks.md` (2026-10-29), section 3.4 "Tests that ship with the block"
  and the row c0270 of section 4. Concepts only: a library package whose usage build must pass in CI is
  an idea taken from the comparison of section 1; no code, manifest key, test layout or name of another
  tool is copied.
- **What the batch gives.**
  - c0251: `@block` functions, typed ports, `design.use(block, name, **params)`, block paths.
  - c0253: `b.expect(...)`, judged by the stage `circuit.rules` with pass, unsure (warning) and fail
    (error); `design.rig(supply(...), sink(...))`, records of the rules layer that never reach an output;
    the requirement table (`summary.requirements`).
  - c0254: generators and `gen.achieved` (info) with the achieved range, also in `result.generators`.
  - c0256: `fenolite.testing.load`, `instantiate(block, **params)` (a throwaway design, ports as nets
    `dut/<port>`), `TestDesign.net/ref/connected/findings`, `TestingError`.
  - c0268: the block record (`id`, `version`, `summary`, `category`, `sources`, parameter metadata), the
    catalog and `fenolite blocks list|show|doc`. Task 0.1 records its final names.
- **The gap.** `instantiate` has no way to bring the input voltage that a block's expectations need:
  c0253 infers no voltage, so a divider's `voltage_of(HI)` is `unknown` and its expectation is
  `circuit.expect-unknown`. Nothing says where a block's tests live, nothing proves that a block still
  builds in a whole design, and nothing notices when a release changes what a block builds.

## Goals / Non-Goals

**Goals**

- One convention, the same for the shipped library, a library block item (c0273) and a project's blocks.
- A test states the outside world in one argument and reads the verdicts of the block's own
  expectations.
- A block's output is pinned by a reviewed golden file and changes only through plan and confirm.
- One command runs everything, with no pytest, no `kicad-cli` and no network.

**Non-Goals**

- See the proposal. Also: no parallel test execution, no timing budget per test, no coverage measure.

## Decisions

### 1. The convention: three files per block, found by name

```
src/fenolite/blocks/                     # or a package of c0273, or a project's blocks folder
  divider.py                             # defines Fenolite:voltage_divider
  usage/voltage_divider.py               # a whole design that uses the block; must build
  tests/test_voltage_divider.py          # plain test_* functions on fenolite.testing
  golden/voltage_divider.json            # fenolite.block-golden.v0, written by blocks test --golden
  layouts/voltage_divider.toml           # c0271, optional
```

- `<name>` is the name part of the block id (`voltage_divider` of `Fenolite:voltage_divider`). The three
  paths are relative to the folder of the module that defines the block.
- c0268's record gets them without a new decorator keyword: `fenolite blocks show` adds `tests`, `usage`
  and `golden`, each the relative path, or `null` when the file is missing.
- **Shipped blocks** (`Fenolite:`) MUST have all three; `tests/unit/blocks/test_convention.py` fails
  otherwise, and `fenolite blocks test` reports `blocks.convention-missing` as an error. A project or
  package block missing one gets the same code as a warning.
- *Alternatives considered.* Declaring the paths in `@block(tests=..., usage=...)`: rejected, a
  convention needs no keyword and cannot drift from the files. A `tests/` tree outside the package:
  rejected, an installed library could not test itself.

### 2. The usage example must build

A usage example is an ordinary design script: a board outline, the block instance or instances, the
parts that a real design would connect to the ports (a header, a connector), a rig for the outside world,
and nothing else.

```python
# src/fenolite/blocks/usage/voltage_divider.py   (authored for Fenolite)
from fenolite.blocks import voltage_divider
from fenolite.dsl import Design, Part, connect, mm, supply, volt

design = Design("voltage_divider_usage")
design.board(mm(20), mm(12))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
v12 = design.rail("V12", voltage=volt("12").pct(2))
gnd = design.ground("GND")
div = design.use(voltage_divider, "sense", vin=volt("12").pct(2), vout=volt("3.3").pct(5))
connect(v12, div.HI, j1[1])
connect(gnd, div.LO, j1[3])
connect(div.OUT, j1[2])
design.rig(supply(v12, gnd, voltage=volt("12").pct(2), name="bench"))
```

- "Builds" means: `fenolite build` exits 0 and neither the build nor the tool-free check stages (those
  of `STAGE_ORDER` not in `ORACLE_STAGES`, c0256) report a finding above `info`. A usage example that
  needs a warning states a waiver (c0114) with its reason, which the reviewer reads.
- The runner builds it with `fenolite.testing.load(path, seed=0, timestamp="2026-01-01T00:00:00Z")`, in a
  private temporary folder.
- The KiCad jobs build every shipped usage example for targets 9 and 10 and read the boards back
  (`tests/kicad/blocks/test_usage_boards.py`), as every example is.

### 3. `instantiate(..., stimulus=)`: the outside world as a c0253 rig

```python
from fenolite.blocks import voltage_divider
from fenolite.dsl import ua, volt
from fenolite.testing import draw, instantiate, stimulus


def test_output_in_range():
    with instantiate(
        voltage_divider,
        vout=volt("3.3").pct(5),
        stimulus=stimulus(HI=volt("12").pct(2), LO=volt(0), OUT=draw(ua(1))),
    ) as t:
        assert not t.findings("circuit.*", severity="error")
        row = t.requirements("dut/expect#1")[0]
        assert row.status == "pass"
```

- `stimulus(mapping=None, /, *, ref=None, **ports) -> Stimulus`. Each key is a port name, or
  `PORT.member` for a member of an interface port (given through the positional mapping). Each value is:
  - a voltage `Quantity` or c0246 `Range`: a c0253 `supply(dut/<port>, <reference>, voltage=...)`;
  - `source(voltage, current=None)`: the same supply with the current the outside world can deliver;
  - `draw(current)`: a c0253 `sink(dut/<port>, <reference>, current=...)`.
- **The reference** is `ref` when given, else the one port given exactly 0 V, else the block's one
  `Ground` port (c0252). Anything else raises `TestingError` naming the candidates. The reference port
  itself is not made a supply.
- The rig elements are named `stim_<port>` (`stim_BUS_sda` for a member) and written into the throwaway
  script after `design.use`, so they are exactly c0253's records: they bound the port nets, count as rail
  sources and loads, and never reach an output.
- The sink helper is `draw`, not `load`, because `fenolite.testing.load` is c0256's script loader.
- An unknown port, a member of a single-net port, a current given where a voltage is expected or the
  reverse raise `TestingError` before anything is built.
- `instantiate` without `stimulus` builds as c0256 specifies, unchanged.
- *Alternatives considered.* Test-only parts (a voltage source component): rejected for c0253's reason,
  a component reaches the BOM and the netlist. A `stimulus=` dict of raw ranges: rejected, a load and a
  supply need different records, and the helpers name which.

### 4. Reading verdicts and achieved values

`TestDesign` (c0256) gains two read-only queries and three fields of `PartView`:

| name | returns | from |
|---|---|---|
| `requirements(pattern="*")` | `tuple[RequirementRow, ...]`, rows whose id matches the glob, each `id`, `entities`, `quantity`, `value`, `limit` (c0246 ranges), `status` (`pass`, `unsure`, `fail`, `unknown`), `evidence` | `summary.requirements` of `circuit.rules`, run as `findings` runs it |
| `achieved(path)` | the c0246 `Range` that the generator which made the part at `path` achieved, or `TestingError` | `result.generators` of the build (c0254) |
| `PartView.at`, `rotation`, `side` | the placement on the built board: a pair of integer nanometres, integer microdegrees, `top` or `bottom` | the board read by `load` |

- `requirements` runs the tool-free stages once per `TestDesign` and caches the reply with `findings`.
- Without c0253, `requirements` raises `TestingError` ("needs the circuit stage"); without c0254,
  `achieved` does. The capabilities of `fenolite capabilities` say which are present.

### 5. Golden canonical JSON

```json
{"block": "Fenolite:voltage_divider", "circuit": {"…": "the usage build's circuit.json"},
 "rules": {"…": "the usage build's rules.json"}, "schema": "fenolite.block-golden.v0",
 "seed": 0, "timestamp": "2026-01-01T00:00:00Z", "usage": "usage/voltage_divider.py", "version": "1.0.0"}
```

- The file is the model's canonical JSON writer applied to this object (sorted keys, the model's
  separators, a final newline), so a golden diff in a pull request reads as a model diff.
- It holds the circuit (parts, values, nets, ports, block parameters) and the rules (expectations, rig,
  roles), not the board: the board is covered by the layout tests (c0271) and by the KiCad jobs.
- `fenolite blocks test` compares bytes. A difference is `blocks.golden-differs` (error) with the first
  twenty differing JSON paths (`circuit.components[3].value`), sorted, and the regenerate command.
- **Written only by** `fenolite blocks test ID --golden --dry-run`, then `--confirm --plan <id>`. The plan
  lists each golden file with its old and new SHA-256; a block whose usage does not build is refused for
  `--golden` (`blocks.usage-failed`, nothing written).
- A version of the block that differs from the golden file's `version` with equal bytes otherwise is
  `blocks.golden-differs` too: a version bump is reviewed with its golden file.
- *Alternative considered.* The whole `.fenolite/` folder: rejected, board bytes churn with placement
  and would hide the circuit change a reviewer must see.

### 6. `fenolite blocks test [ID...] [--golden] [--only KIND]`

- Selects the blocks that `fenolite blocks list` lists with the same options (c0268, c0273), or the given
  ids; an unknown id is `FEN-2001` with the three closest ids in the hint.
- For each block, in id order: the convention check, the usage build, the golden comparison, then each
  test function. `--only usage|golden|tests` runs one kind.
- **Test functions.** The module is loaded with `importlib` from its path; every module-level function
  whose name starts with `test_` and that has no required parameter is called, in name order. A return is
  a pass; an `AssertionError` (including `TestingError`) is `blocks.test-failed` with the first 500
  characters of the message; another exception is `blocks.test-failed` with its type and message. A
  function with required parameters (a pytest fixture) is skipped with `blocks.test-unsupported`
  (warning). A module that fails to import is one `blocks.test-failed` naming the module.
- **Result.** `result.blocks`: per block `id`, `version`, `usage` (`passed`/`failed`/`missing`),
  `golden` (`equal`/`differs`/`missing`/`written`), `tests` (`[{name, status, message}]`), `seconds`
  omitted (no timing in a deterministic reply). Exit 0 when nothing is above `info`, 5 with the findings.
- Read-only without `--golden`. The tests run in process with temporary folders only; a test that writes
  elsewhere is a test bug, not checked.

| code | severity | when |
|---|---|---|
| `blocks.convention-missing` | error (shipped) / warning | usage, tests or golden file missing |
| `blocks.usage-failed` | error | the usage build exits non-zero or reports a finding above `info` |
| `blocks.golden-differs` | error | golden bytes differ, or its `version` differs |
| `blocks.golden-missing` | error | no golden file, under `--only golden` or for a shipped block |
| `blocks.test-failed` | error | a test function failed or its module did not import |
| `blocks.test-unsupported` | warning | a `test_*` function needs arguments |

Each code is explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Block tests". No new
`FEN-` code.

### 7. CI and the repository's own suite

- `tests/unit/blocks/test_shipped_blocks.py` parametrises over the shipped block ids and calls the same
  runner, so `make check-fast` runs every shipped test, usage build and golden comparison (all
  tool-free).
- The unit jobs of `.github/workflows/ci.yml` also run `uv run fenolite blocks test --json` once, to prove
  the command on an installed wheel.
- The KiCad jobs run `tests/kicad/blocks/` (usage boards for targets 9 and 10, and c0271's DRC of laid-out
  usage boards).

### 8. Files and public API

- `src/fenolite/testing/stimulus.py`: `stimulus`, `source`, `draw`, `Stimulus`; exported by
  `fenolite.testing` (its frozen `__all__` grows by these four and `RequirementRow`).
- `src/fenolite/testing/design.py`: `requirements`, `achieved`, `PartView` placement.
- `src/fenolite/testing/blocks.py`: `run_block_tests(records, *, kinds, golden_plan=False) -> RunResult`,
  pure over the block records it is given; `cli/cmd_blocks.py` (c0268) gains the verb `test`.
- Layering: `testing` → anything (c0256), so the runner lives in `testing`; `cli` imports it; no block
  module imports `testing`. The import-graph test records it.

### 9. Evidence

| behaviour | level before merge |
|---|---|
| stimulus to rig, reference rule | `INFERRED`, unit tests |
| runner, codes, `--golden` plan | `INFERRED`, unit tests on authored blocks |
| golden stability | `INFERRED`, `H-G-BLOCK-GOLDEN`, measured on the three unit jobs |
| usage boards | `KICAD-VERIFIED` read-back (targets 9 and 10) |

## Risks / Trade-offs

- **Golden churn** when the model gains a field: every golden file changes in the same commit. Mitigation:
  `--golden` regenerates them all under one plan, and the diff is sorted JSON.
- **Running test code** executes the block library's Python, as building a script does. Packages of c0273
  are installed by the user; the command runs nothing it has not been asked to.
- **Slow suites**: one build per usage example and per `instantiate`. The five starter blocks stay under
  a few seconds in total; the runner reports per-block results, not timings.

## Open Questions

1. Should a project block without tests be a warning or silent? **Recommended:** a warning from
   `fenolite blocks test` only, never from `build`: a project block is often a one-off.
2. Should goldens include the board? **Recommended:** no; layouts have their own tests (c0271), and the
   circuit is what a block release promises.
3. Should `blocks test` run tests in a subprocess to isolate state? **Recommended:** no for now, in process
   like `fenolite.api.run`; revisit if a package of c0273 needs it.

## Relation to the other changes of this batch

- **c0268** owns the record, the catalog (`fenolite.cli.blocksrc`) and the `fenolite blocks` group; this
  change adds `tests`, `usage` and `golden` to `show`, and the verb `test`.
- **c0269** (block schematic): the golden file holds the schematic groups only through `circuit.json`; no
  dependency.
- **c0271** (block layouts): layout property tests use `PartView.at` and c0271's layout reader; c0271's
  KiCad DRC test of laid-out usage boards runs in the same CI folder.
- **c0272** (starter blocks): the first library under this convention.
- **c0273** (library blocks): `fenolite blocks test` runs vendored library blocks the same way; `fenolite-library`'s CI
  runs the command.
