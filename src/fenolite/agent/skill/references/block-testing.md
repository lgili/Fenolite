---
topic: block-testing
title: Testing reusable blocks
summary: Ship a usage build, plain tests and a reviewed circuit/rules golden; stimulate ports and read typed verdicts.
---

# Testing reusable blocks

Keep `usage/<name>.py`, `tests/test_<name>.py` and `golden/<name>.json` beside the module defining a block.
`<name>` is the name part of its id. A shipped `Fenolite:` block requires all three. Missing project files
give `blocks.convention-missing` warnings. A usage example is a whole design with a board, connections
to its required ports and an explicit bench rig; build and tool-free checks must have no finding above
info. Keep arbitrary examples separate from a product's reviewed electrical limits.

```fenolite-cmd
fenolite blocks test --json
fenolite blocks test Example:divider --from divider.py --only usage --json
fenolite blocks test Example:divider --from divider.py --only tests --json
fenolite blocks test Example:divider --from divider.py --only golden --json
```

The first command tests shipped blocks and local modules that have matching convention files. Explicit
`--from` imports your Python module, as `blocks list` does. Results are in `result.blocks`, in id order;
test functions run in name order. No tool, network or pytest is needed. A required function parameter
(such as a pytest fixture) or async function is skipped with `blocks.test-unsupported`; write plain
synchronous `test_*` functions with no required arguments. Exit 5 also covers warnings about incomplete
tests. Tests are trusted Python, with a private working folder and restored import and random state.
For a vendored block, private usage builds and `instantiate` carry the owning project's device items,
native references and authored overrides. The source namespace and lock remain unchanged. Golden
plans also bind these device inputs; edit a record after review and review a new plan.

## State the outside world

The following is a complete test for a local `divider.py` with ports `HI`, `LO`, `OUT` and a block
expectation on its divided input. Port names and the expectation belong to your block's contract.

```text
from divider import divider
from fenolite.dsl import amp, volt
from fenolite.testing import draw, instantiate, source, stimulus

def test_output():
    with instantiate(divider, stimulus=stimulus(
        HI=source(volt(12).pct(2), current=amp("1m")), LO=volt(0), OUT=draw(amp("1u")),
    )) as design:
        row = design.requirements("dut/expect#1")[0]
        assert row.status == "pass"
        assert row.value.within(row.limit)
        assert not design.findings("circuit.*", severity="error")
```

`stimulus` accepts voltages directly, `source` for a voltage with available current, and `draw` for a
load current. Use a mapping for interface members, such as `stimulus({"BUS.sda": volt(3)}, ref="GND")`.
The reference is `ref` when given, otherwise the sole exactly 0 V port, otherwise the one `Ground`
port. Unknown ports, wrong dimensions and ambiguous references raise `TestingError` before building.
Stimulus becomes rig records in the rules layer; it adds no board, netlist or BOM component.

`requirements(pattern="*")` returns immutable rows with id, entities, quantity, value/limit ranges,
status and evidence. Expectations use paths like `dut/expect#1`; other rows retain their native ids.
Unknown bounds are `None`. The default `findings` and `requirements` share one cached check run.
`achieved("dut/ratio_top")` returns the outward-rounded range of the generator that made that part;
a part without a generator raises `TestingError`. A `PartView` from `ref` also gives `at` as integer
nanometres in the script's board frame, `rotation` as integer microdegrees and `side` as top/bottom.

## Review golden changes

Goldens contain the usage build's circuit and rules, its block id/version and fixed seed/timestamp.
They exclude the board. A difference reports `blocks.golden-differs` and at most twenty sorted JSON
paths. A failed usage gives `blocks.usage-failed` and cannot produce a golden write.

```fenolite-cmd
fenolite blocks test Example:divider --from divider.py --golden --dry-run --json
fenolite blocks test Example:divider --from divider.py --golden --confirm --plan PLAN_ID --json
fenolite explain blocks.golden-differs --json
```

Review `result.plan`, `result.golden_plan` and the proposed circuit change, then replace `PLAN_ID` with
the reviewed id. The old and new SHA-256 identify the bytes. Confirmation replays them without running
the tests again; changed input invalidates the plan. Commit the golden beside the block and tests.

Read next: `design-script`, `board-review`, `checks`.
