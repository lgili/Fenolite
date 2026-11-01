# Signal topologies

An ordered topology states which pads a signal visits, including a branch or a series part.
`topology.rules` checks the current routed KiCad board without an external tool. Delay and loss
judgements are `INFERRED` calculations from the user's inputs. Fenolite supplies no propagation,
dielectric, loss or protocol default.

## Exact units and inputs

`fs`, `ps` and `ns` produce a frozen `Delay` holding integer femtoseconds. `mdb` and `db` produce a
frozen `Loss` holding integer milli-decibels. Integers and decimal strings convert exactly; floats,
negatives and fractional base units raise `DslError`. `ps("12.5").fs == 12500`,
`ns("1.2").fs == 1200000` and `db("1.5").mdb == 1500`; `ps("0.0001")` is refused.

Every number here is an **example input**, not a material or protocol recommendation:

```python
from fenolite.dsl import fs, hertz, mdb

design.propagation("F.Cu", per_mm=fs(5_900))
design.propagation("In1.Cu", per_mm=fs(6_900))
design.propagation(via=fs(10_000))
design.loss("F.Cu", per_mm=mdb(4), at=hertz("1G"))
design.loss(via=mdb(2), at=hertz("1G"))
```

Per-mm propagation must be positive; via delay and loss may be zero. Declare each layer/via input
once. Frequency is optional exact Hz; layers on one loss path cannot state different frequencies.
Missing inputs give `topology.input-missing`, leave that constraint unjudged and make the stage
evidence `UNVERIFIED`.

## Trees, pins and bridges

Connect pins to nets before declaring a topology. `a >> b >> c` is ordered; `a >> (b, c)` fans out
and finishes that chain. Continue a branch with a chain starting at its endpoint. Chains join at
shared pins, or through two bridge pins of one part. Cycles, repeated branches, disconnected trees
and consecutive pins on different nets without a bridge raise `DslError` at the script call.

```python
design.bridge(r1, 1, 2, delay=fs(25), loss=mdb(2))  # example inputs
clk = design.topology("clk", u1[1] >> r1[1], r1[2] >> u2[1] >> u3[1])
```

Device function names resolve to a single pin; ambiguous functions are refused. `design.bridge`
states connectivity; omitted delay/loss explicitly declare an ideal bridge (zero). A device record
can instead carry `[[bridges]]`, `between = ["P1", "P2"]` (functions or pin numbers), and optional
non-negative integer `delay_fs` and `loss_mdb`. The reader rejects unknown keys, duplicate bridges
and unknown ends. Records without this optional field keep their prior bytes. A series part joining
separate chains without a bridge gives `topology.bridge-missing` at build and plans no write.

## Constraints and judgement

```python
from fenolite.dsl import db, mm, ps

clk.delay(u1[1], u3[1], min=ps(10), max=ps(900))  # example limits
clk.skew(u2[1], u3[1], max=ps(50))
clk.loss(u1[1], u3[1], max=db("1.5"))
clk.stub(max=mm(2))
clk.order()
```

Each accepts `severity="error"` or `"warning"`. Ends must belong to the tree; skew needs at least
two ends, and delay needs at least one bound. Limits carry the unit their constraint requires.

Each net edge uses the shortest continuous copper centre-line path between its pads. Tracks split
at junctions and pad locations; arcs use the integer geometry kernel's arc length; vias join only
their spanned layers. Exact pad copper respects the component's pin/pad map. Equal paths resolve
deterministically by model identity. Portions of one source track/arc recombine before rounding.

Each segment contributes `length_nm * per_mm_fs / 1_000_000`: a maximum rounds up, a minimum rounds
down. Vias and bridges add integer inputs once per traversal; known model pad die delays add
`die_delay_fs`. The authored bench's 30 mm at 5900 fs/mm, one 10000 fs via, and 20 mm at 6900 fs/mm
sum to **325000 fs**. Loss uses milli-decibel inputs and rounds up. No float enters these sums.

Skew compares root-to-end delays rounded up per segment with the longest; the longest has zero
skew, including ties. The reported signed result is each rounded delay minus the longest. Order reports a later descendant visited on the path to an earlier one, or
copper loops. A stub is the centre-line distance from a measured tree path to an unlisted branch end.

An unrouted path gives `topology.unrouted` (info). Connectivity requiring filled zone copper gives
`topology.path-through-zone` (warning), without guessing a length. Both leave the constraint
unjudged. Continuous routed copper is preferred when measurable. Junctions require centre-line
contact; width-only contacts and unrepresented curve intersections can remain unrouted. Approximate
pad copper never establishes connectivity.

KiCad 10's native `die_delay` token is preserved, but its units have no completed Fenolite probe.
Such a path gives `topology.input-missing`; its number is not interpreted as the explicitly typed
`die_delay_fs` model input. Native time-domain writing remains deferred too.

The KiCad-only stage follows `length.rules` and skips with `no-topology` when none is stored.
Its summary counts topologies, constraints by kind, `judged` and `not_judged`; each finding carries
topology, pin/pad and net subjects. Evidence combines the read with `INFERRED` (`H-G-TOPO-DELAY`).

## Protocol bundles

`protocol.Usb2` and `protocol.Clock` are frozen records of `delay_min`, `delay_max`, `skew_max`,
`loss_max` and severity. Unset limits are absent; at least one user limit is required, with **no
numeric default**. `design.constrain(usb, protocol.Usb2(skew_max=ps(10)))` is an example, not a USB
specification value. `Usb2` requires a `USB2` or `DiffPair`; `Clock` requires this design's topology.
A wrong kind raises `DslError`.

USB members each need exactly two connected pins. They expand to independent delay/loss topologies,
and `ProtocolSkew` compares their measured delays. No cross-net edge is invented. Endpoint ordering
is deterministic by pin name. Clock limits expand from root to leaves; clock skew needs two leaves.

## KiCad lowering and specificity

Conversion is `INFERRED`; the existing length and pair-skew kinds are `KICAD-VERIFIED`. A delay
becomes `topology:<name>:delay` only when the routed board proves one complete two-terminal net:
an unbranched straight-track chain, no via/zone/arc/die offset, and one positive propagation on every
used layer, exact integer-fs segment products and no pad shortcut at a junction. Bounds are `min_nm = ceil(min_fs * 10^6 / per_mm_fs)` and
`max_nm = floor(max_fs * 10^6 / per_mm_fs)`. Example: 295000 fs at 5900 fs/mm gives 50 mm.

Pair skew becomes `pair:<interface>:skew` when both member paths meet those conditions, share one
propagation and have KiCad pair names. Endpoint skew on one net stays in Fenolite: KiCad compares
whole nets. Other constraints retain `rules.topology-not-lowered` (info). Native tuning-profile time
keys are not emitted; `H-K-PRO-TIME-DOMAIN` remains `UNKNOWN` pending a probe.

The [design-rule specificity table](dsl.md#design-rules) ranks selector scope. Default precedence
remains priority zero first, positive priorities descending (one last), then name/id; the last match
governs. A less specific governing rule gives one `rules.shadowed` info per overridden rule pair.
`design.rules.precedence("specificity")` derives priorities only for calls without `priority=`;
explicit priorities remain. Existing designs keep their lowered bytes.

`fenolite check PROJECT --stages model.validate --explain-rules --json` adds sorted `result.rules`
rows: subject, kind, governing rule, rank and overridden rules, each with name/id/priority/rank.
They reuse `rule_precedence` and run no extra tool. The catalog-only
[clock and USB example](../examples/topologies/design.py) includes routed tracks and a tested check.
