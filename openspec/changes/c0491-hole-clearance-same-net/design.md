# Design: c0491

## D1 Root cause

`checks/copper.py::_holes`:

```python
net_id = None if record.kind == "np_thru_hole" else record.net_id
```

`_hole_clearance_findings` skips copper of the hole's net only when `hole.net_id is not None`. So an
unplated hole has no net, and every copper item near it is judged.

## D2 The rule

A hole has the net of its item: the pad's net for a pad, plated or not, and the via's net for a via. A board
hole has no net. `_hole_clearance_findings` leaves out copper of the hole's net, as it does today for plated
holes. `resolver.subject(kind, hole.net_id, …)` already takes the net, so a `hole_clearance` rule with a
same-net condition still matches and still decides.

## D3 Evidence (task 1.1)

- KiCad: an authored board with an NPTH pad of net `GND` (KiCad stores a net on an NPTH pad), a `GND` zone
  and a `GND` via 0.1 mm from its wall, under a 0.25 mm board hole clearance. `kicad-cli pcb drc` on
  9.0 and 10.0. The expected result is no `hole_clearance`. The control is the same board with the via on
  net `N1`, which reports one. The result goes in `docs/formats/kicad/rules.md` with `H-G-HOLE-SAME-NET`.
- Altium: the net scope of the Clearance rule (`DifferentNets`) is already a recorded fact. Task 1.1 adds
  the public documentation page that states the hole cell of the clearance matrix (S-0460 family) and
  records the row. An Altium kit run is a request, not a blocker.

If KiCad reports the same-net case, the KiCad rules view gets a flag
`DesignRules.hole_clearance_same_net = True` that keeps the net out of the skip, and the row records the
difference.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-G-HOLE-SAME-NET` | KiCad's DRC and Altium's Clearance rule report no hole-to-copper clearance between a hole and copper of the hole's own net, unplated holes included |
