---
topic: signal-topologies
title: Ordered signals, delay and loss budgets
summary: Ordered pad trees, explicit timing and loss inputs, protocol budgets and rule precedence.
---

# Ordered signals, delay and loss budgets

Use a topology when a clock must visit loads in order or a series part splits its path across nets.
Every number below is an example. Obtain real delay, loss and protocol limits from the user's product
requirements and stack-up. Fenolite ships no protocol numbers and computes no field solution.

## Declare the path and its inputs

```fenolite-design
from fenolite.dsl import Design, Net, Part, connect, db, fs, hertz, mdb, mm, ns, protocol, ps

design = Design("timed")
design.board(mm(40), mm(20))
driver = Part("J1", device="Fenolite:Conn_1x2_P2.54")
load = Part("J2", device="Fenolite:Conn_1x2_P2.54")
resistor = Part("R1", device="Fenolite:R_0402", value="33")
design.add(driver, load, resistor)
connect(Net("CLK_A"), driver[1], resistor[1])
connect(Net("CLK_B"), resistor[2], load[1])
design.bridge(resistor, 1, 2, delay=fs(25), loss=mdb(2))
clock = design.topology("clk", driver[1] >> resistor[1], resistor[2] >> load[1])
clock.delay(driver[1], load[1], min=ps(10), max=ns(1))
clock.loss(driver[1], load[1], max=db("1.5"))
clock.stub(max=mm(2))
clock.order()
design.constrain(clock, protocol.Clock(delay_max=ns(1)))
design.propagation("F.Cu", per_mm=fs(5_900))
design.propagation(via=ps(10))
design.loss("F.Cu", per_mm=mdb(4), at=hertz("1G"))
design.loss(via=mdb(2), at=hertz("1G"))
driver.place(mm(5), mm(5))
resistor.place(mm(15), mm(5))
load.place(mm(25), mm(5))
```

`fs`, `ps`, `ns`, `mdb` and `db` accept integers or exact decimal text. Floats, negatives and fractions
of a femtosecond or milli-decibel are refused. `a >> (b, c)` branches; continue a branch in another
chain starting at that pin. Cycles and disconnected trees are refused. A missing series bridge is a
build error. A device record may declare its bridge instead of `design.bridge`.

After routing, `topology.rules` measures pad paths and judges delay, skew, loss, stubs and order. Its
evidence is `INFERRED`: the sum depends on the inputs. Delay maxima round each segment up, minima
down. A missing input gives `topology.input-missing` and `UNVERIFIED`; an unrouted end gives
`topology.unrouted`; a connection through zone copper gives `topology.path-through-zone`. Those
constraints are not judged. Native pad time tokens with unproven units are treated as missing input.

```fenolite-cmd
fenolite check timed/out --stages topology.rules --json
fenolite check timed/out --stages model.validate --explain-rules --json
```

## Protocol bundles and governing rules

`protocol.Usb2` binds only to `USB2` or `DiffPair`; `protocol.Clock` binds to a topology. Give every
limit explicitly. Pair members are measured separately and their delays compared. A delay converts
to a KiCad length rule only when its complete two-terminal track path and one propagation establish
equivalence; pair skew has the same restriction. Endpoint skew on one net, bridges, loss and order
remain in Fenolite, with `rules.topology-not-lowered` info.

`--explain-rules` gives `result.rules`, sorted by subject and kind: governing rule, rank and the
overridden rules. Default precedence remains KiCad's priority/name/id order. `rules.shadowed` says a
less specific rule governed over a more specific rule; set `priority=` or opt into
`design.rules.precedence("specificity")`. Explicit priorities keep their value. The explanation runs
no extra tool.

Read next: `rules`, `board-routing`, `checks`.
