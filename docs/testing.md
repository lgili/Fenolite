# Testing a design as code

`fenolite.testing` is an experimental, standard-library-only package. It uses the real build and check
commands in process. It needs neither pytest nor a CAD installation; catalog-only designs need no
external libraries. Design scripts execute as your own Python code, as with `fenolite build`.

```python
from fenolite.testing import assert_render, instantiate, load

with load("design.py") as d:
    assert d.net("GND").pins == ("R1-1", "R2-1")
    assert d.ref("R1")[1].net == "GND"
    assert d.connected("R1-1", "R2-1")
    assert d.connected("R1-1", "R2-1", copper=True)
    assert not d.findings("build.unattached")

assert_render("design.py", "golden/net-GND.svg", net="GND")
```

The authored [example](../examples/testing/test_design.py) runs without a test plugin. Its circuit is a
connectivity fixture, not a functional powered product. Run it with `uv run pytest examples/testing -q`.

## Lifecycle and queries

`load(path, *, seed=0, timestamp="2026-01-01T00:00:00Z", kicad_version=None, workdir=None)` uses a
private folder, previews the build, then confirms that exact plan. The script runs once. The returned
`TestDesign` exposes `model`, `board`, `evidence` and the built `path`. Use its context manager or `close()`;
its finalizer also removes owned files. A caller-provided `workdir` is never removed. Build failures raise
`TestingError`, an `AssertionError` retaining the original code, location and hint.

- `net(name)` returns name, model id, netclass, role, voltage and sorted logical `REF-PIN` members.
- `ref(ref)` returns a `PartView`; `part[1]`, `part["pin_name"]` and `part.pin_name` return a `PinView`.
  Numbers take precedence; an ambiguous name is refused. Item access also works for a pin whose name
  collides with a record field. Unknown names include nearby known names.
- `connected(a, b)` accepts a `PinView`, `NetView` or `REF-PIN` text. Unconnected pins are never joined
  merely because both have no net. `copper=True` measures the written board and its logical pin-to-pad
  map. All pads of both endpoints must belong to one copper island. Unsupported geometry cannot prove
  a connection. A net endpoint includes all of that net's member pads.
- `findings(pattern="*", *, stages=None, severity=None)` returns a tuple of frozen findings with
  `.evidence`. Each finding has code, severity, message, where and subjects. Code filtering uses a
  case-sensitive glob. By default only stages not in `ORACLE_STAGES` run. An oracle stage is refused
  before any command runs. Exit 5 means findings, not an exception. Unattached warnings from the build
  are included, combining evidence conservatively.

`PartView.device` and `NetView.voltage` are `None` in this version. `findings("circuit.*")` runs the
tool-free stage `circuit.rules` on the private build, with authored `devices/` records followed by vendored
records and the shipped catalog. Conflicting vendored identities remain error findings. Each finding's
subjects name the part and the nets of its requirement row (a ground net only when
the row names no other). A rating that fails stops the build itself (`fenolite build` refuses to write),
so `load` raises `TestingError` naming the finding, such as `circuit.rating-voltage at C1`.

## A block alone

`instantiate(block, *, stimulus=None, **params)` tests one block (`@block`) without a design of its own. It writes a
throwaway script in its private folder that makes a design with a 100 mm square board, uses the block
once as `dut` with `params`, and loads it as `load` does. A part reads by its block path
(`d.ref("dut/U1")`) and a port as the net `dut/<port>`; a port of several members, such as a `Rail`,
reads as its main member (`dut/VOUT` is `dut/VOUT.hv`). The project devices beside the block's file, or
beside its package, are copied in. For a vendored block, the private bench also carries its owning
project's authored records and vendored symbol, footprint and device items, including native references.
Nothing is written outside the private folder.

```python
with instantiate(divider, bottom="3000") as d:
    assert d.ref("dut/R_BOT").value == "3000"
    assert d.connected(d.ref("dut/R_TOP")[2], d.net("dut/MID"))
```

## Golden SVGs

Block circuit/rules goldens use the separate [block convention](#testing-blocks) below.

`assert_render(path, golden, *, net=(), region=None, layers=None, seed=0, timestamp=...)` builds privately
and compares the same canonical SVG bytes as model renders. `net` accepts one name or a sequence;
`region` accepts the CLI rectangle string, a `Region`, or four integer nanometre coordinates. Copper
layer filtering preserves holes and board edges. It never changes the reference or writes outside its
private build folder. Comparisons are exact, including style and labels, with no pixel tolerance.

A difference reports added, removed and changed SVG elements keyed by class, model item and layer,
retaining repeated keys, with at most twenty diff lines and commands to regenerate after review:

```sh
fenolite render examples/testing/design.py --net GND -o examples/testing/golden --seed 0 --timestamp 2026-01-01T00:00:00Z --dry-run
fenolite render examples/testing/design.py --net GND -o examples/testing/golden --seed 0 --timestamp 2026-01-01T00:00:00Z --confirm --plan PLAN_ID
```

Replace `PLAN_ID` with the reviewed result. Golden tests never update themselves. Use the canonical
filename `net-GND.svg` (`nets.svg` for several nets, `region.svg` with no highlights). If a custom golden
filename is supplied, the failure explicitly names the actual output and the manual rename needed after
review; it does not pretend the render command writes that custom name.

The SVG root records `data-render="fenolite.region.v1"`. Review a render-version change along with all
updated goldens. CI's unit jobs run the committed example golden on their operating systems; deterministic
bytes are evidence of stable rendering, not proof that the circuit is electrically correct.

## Testing blocks

A block carries three files beside its defining module, with the name part of its id:
`usage/<name>.py`, `tests/test_<name>.py` and `golden/<name>.json`. Shipped `Fenolite:` blocks require
all three. Missing project files give warnings from `blocks test`. A usage example is a complete design
with a board, real connections to every required port, and an explicit rig. Its build and all tool-free
checks must have no finding above info; a reasoned waiver can accept a known finding.

`stimulus(mapping=None, /, *, ref=None, **ports)` supplies the outside world for `instantiate`. A voltage
quantity/range creates a rig supply; `source(voltage, current=None)` also states available current, and
`draw(current)` creates a rig sink. Interface members use mapping keys such as `"BUS.sda"`. The
reference is the explicit `ref` port, otherwise the sole port at exactly 0 V, otherwise the block's one
`Ground` port. Ambiguous references, unknown ports/members and wrong dimensions raise `TestingError`
before any build or temporary folder. A single-net port is named without its member. A supplied reference
must be exactly 0 V. The reference gets no supply of its own. Rig names are `stim_HI` or `stim_BUS_sda`;
rig elements remain in the rules layer and never enter the board, netlist or BOM.

```python
from fenolite.dsl import amp, volt
from fenolite.testing import draw, instantiate, source, stimulus

with instantiate(
    divider,
    stimulus=stimulus(
        HI=source(volt(12).pct(2), current=amp("1m")),
        LO=volt(0),
        OUT=draw(amp("1u")),
    ),
) as design:
    assert design.requirements("dut/*")[0].status == "pass"
    assert not design.findings("circuit.*", severity="error")
```

`requirements(pattern="*")` returns immutable `RequirementRow` views with `id`, `entities`, `quantity`,
`value`, `limit`, `status` and `evidence`. Value and limit are DSL `Range` objects or `None` when unknown;
expectation ids are their block paths (`dut/expect#1`), without the native table's `circuit.expect:`
prefix. Other requirement ids retain their native form, and statuses also include `deferred`.
The default `findings` and `requirements` share one cached tool-free check. Custom stage selections have
their own cache. Missing circuit-stage support raises `TestingError`.

`achieved(path)` reads the outward-rounded range recorded by the generator that made the part. For
example, `achieved("dut/ratio_top")` and `achieved("dut/ratio_bot")` return the same divider range. A
part without a generator raises `TestingError`. `PartView.at` is a pair of integer nanometres in the
script's board frame, `rotation` is integer microdegrees, and `side` is `top` or `bottom`.

Run `fenolite blocks test [ID...] [--from FILE.py]... --json`. The runner uses id order, then function
name order, and runs only module-level plain `test_*` functions. Required arguments and async functions
are skipped with a warning. Assertions and other exceptions become findings with a 500-character
message. It captures output and restores import, working-folder and random state; tests are trusted Python,
not sandboxed. The temporary working folder is removed after the run. No subprocess, network or pytest
is needed. `--only usage|golden|tests` selects one kind. With no `--from`, local modules that have a
matching usage or tests file are also discovered. Exit 5 includes warnings about incomplete tests.
Vendored usage examples run in a private copy of their namespace with the same device records and
authored overrides as the owning project. Their original files and locks are unchanged.

Goldens use `fenolite.block-golden.v0`, seed 0, timestamp `2026-01-01T00:00:00Z`, the block id/version,
usage path and canonical `circuit` and `rules` objects. They exclude the board. Comparison is exact;
`blocks.golden-differs` names at most twenty sorted JSON paths. Regenerate under the write protocol:

```sh
fenolite blocks test Example:divider --from examples/blocks/divider.py --golden --dry-run --json
fenolite blocks test Example:divider --from examples/blocks/divider.py --golden --confirm --plan PLAN_ID --json
```

Review `result.plan` and `result.golden_plan` (old/new SHA-256), then replace `PLAN_ID` with its id.
Confirmation replays the reviewed bytes; a changed module, usage, test, device input or target invalidates the plan.
A failing usage build plans no write. The [authored example](../examples/blocks/README.md) carries the
complete convention. CI runs its stable-byte proof across the unit matrix; KiCad jobs read back every
shipped usage board on targets 9 and 10. Cross-platform results remain pending until those jobs pass.
