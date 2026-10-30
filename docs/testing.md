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
tool-free stage `circuit.rules` on the private build, with the device records of `devices/` beside the
script; each finding's subjects name the part and the nets of its requirement row (a ground net only when
the row names no other). A rating that fails stops the build itself (`fenolite build` refuses to write),
so `load` raises `TestingError` naming the finding, such as `circuit.rating-voltage at C1`.

## A block alone

`instantiate(block, **params)` tests one block (`@block`) without a design of its own. It writes a
throwaway script in its private folder that makes a design with a 100 mm square board, uses the block
once as `dut` with `params`, and loads it as `load` does. A part reads by its block path
(`d.ref("dut/U1")`) and a port as the net `dut/<port>`; a port of several members, such as a `Rail`,
reads as its main member (`dut/VOUT` is `dut/VOUT.hv`). The project devices beside the block's file, or
beside its package, are copied in. Nothing is written outside the private folder.

```python
with instantiate(divider, bottom="3000") as d:
    assert d.ref("dut/R_BOT").value == "3000"
    assert d.connected(d.ref("dut/R_TOP")[2], d.net("dut/MID"))
```

## Golden SVGs

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
