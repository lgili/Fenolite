# Impedance targets

An impedance target says that the tracks of a net class, or of a differential pair, must have a given
characteristic impedance, and gives the geometry that makes it on each layer (change c0105). Fenolite
never computes that geometry into a design: you give every width and gap, from your fabricator's stack-up
table or a field solver. Fenolite checks that the board is drawn at it, tells KiCad 10 about it, and
hands the fabricator a table.

## In the script

```python
from fenolite.dsl import USB2, ohm, mm, trace

design.rules.netclass("SE50", clearance=mm(0.2), nets=(clk, clk2))
design.rules.impedance(
    "SE50",
    ohms=ohm(50),
    netclass="SE50",
    tolerance=10,
    layers=(
        trace("F.Cu", refs="In1.Cu", width=mm(0.35)),
        trace("B.Cu", refs="In2.Cu", width=mm(0.35)),
    ),
)

usb = USB2(usb_p, usb_n)
design.rules.netclass("USB90", clearance=mm(0.2), nets=(usb_p, usb_n))
design.rules.impedance(
    "USB90", ohms=90, pair=usb, layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.15)),)
)
design.stackup(..., impedance_controlled=True)
```

- `ohms` is `ohm(…)`, an `int` or a decimal string; a `float` is refused. `tolerance` is in percent.
- `netclass` names one or more classes; `pair` takes a `DiffPair` or `USB2` (or several) and governs the
  class of its two nets, which must be one class.
- `trace(layer, refs=…, width=…, gap=…)`: one or two reference layers, the width, and for a pair the gap
  between the two tracks. A target is differential when its traces carry a gap.
- The model holds the target in `RuleSet.impedance` (`docs/design-model.md`, "Impedance targets").

## What each KiCad major gets

- **Both majors.** Per trace, a `track_width` rule on that layer with `min` = `opt` = `max` = the width,
  named `track_width_<target>_<layer>`, and for a pair a `diff_pair_gap` rule the same way, named
  `diff_pair_gap_<target>_<layer>`, at priority 1 (the `priority` argument). They are written after the class
  minimums and govern on their layers, so KiCad's DRC reports a track that is wider or narrower. The
  limits are exact: a deliberate neck-down near a fine-pitch pad needs a rule scoped to a rule area at a
  higher priority (`select.area`), which the build does not flag.
- **KiCad 10.** Also one tuning profile per target in the project, named by the class key
  `tuning_profile` of each class of the target, so the interactive router and the length tuner see the
  same per-layer numbers, and the profile's gap relaxes the pair's own clearance. Profiles of the project
  that no target names are kept. A profile edited in KiCad's GUI is replaced at the next build when it is
  named like a target: copy its values into the script, or rename it.
- **KiCad 9** has no profile: the rules carry the check (`build.impedance-rules-only`).

## Build checks

| code | severity | when |
|---|---|---|
| `build.impedance-layer` | error | a trace's layer or reference is not a copper layer of the board |
| `build.impedance-shadowed` | warning | a later rule of the same kind selects a target class, a pair of it or the whole board on a trace's layer |
| `build.impedance-class-width` | warning | a class value (`track_width`, or `diff_pair_width`/`diff_pair_gap` for a pair) differs from a trace: routers lay tracks at the class value |
| `build.impedance-gap-clearance` | warning | KiCad 9: a pair's gap is below its class clearance and the class has no pair gap at or below it |
| `build.impedance-stackup` | warning | the board has no stack-up, or it is not marked `impedance_controlled` |
| `build.impedance-rules-only` | info | KiCad 9: the targets are written as rules only |

The stack-up flag stays yours: `design.stackup(…, impedance_controlled=True)` makes the Gerber job file
state `ImpedanceControlled` and the dielectric constants the fabricator needs.

## The table for the fabricator

`fenolite impedance PATH [--estimate] [--out FILE]` lists one row per target and layer: the kind, the
structure (`microstrip` for one reference on an outer layer, `stripline` for two on an inner layer), the
references, ohms, tolerance, width, gap, the heights to each reference and the permittivity from the
stack-up, the classes and their nets. `--out FILE` writes it as CSV with the mutation protocol
(`docs/cli-contract.md`, "impedance"). It reads the `.fenolite/` model of a built project, or the KiCad
board with its project, whose profiles that a class names become targets. It reads no Altium document.

## Estimates

`--estimate` adds, for single-ended surface microstrip and stripline rows only, a quasi-static estimate
from two public closed forms and the width (a multiple of 1 µm) whose estimate is nearest the target
(`docs/analyses.md`, "Impedance estimates", which lists every constant with its source). They are
`INFERRED` advice:

- The microstrip form claims an error below 1 % in most cases and below 2 % always; the stripline form
  0.5 % where its range holds (`in_range`); an offset stripline is a rough estimate for small offsets.
- They leave out solder mask, etch angle, frequency, loss and copper roughness, and pairs get none.
- The estimate is returned and never written into the design. Confirm every geometry with your
  fabricator.

## Altium

An Altium build keeps the targets in the model and in `.fenolite/` only and names them in one
`altium.not-lowered` info at `impedance`. Their derived rules are reported one by one as any rule the PCB
document cannot hold (`design-rules/track_width`, `scope-unsupported`; `design-rules/diff_pair_gap`,
`no-counterpart`). No Altium file changes. `build.impedance-layer` refuses the build as in KiCad.
