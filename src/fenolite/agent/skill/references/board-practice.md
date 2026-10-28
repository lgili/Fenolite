---
topic: board-practice
title: Designing a good board
summary: The order of work for a real board, what a check cannot see, whose numbers apply, and the practice pages that go with each step.
---

# Designing a good board

`fenolite check` judges what a rule can express: shorts, clearances against the board's rules, open
connections, the schematic against the board. A board can pass all of that and still be a bad board. It
can carry its power current around half the board, tie two grounds in three places, sense a current
through copper that also carries it, hide bus copper under a part, or have a silkscreen that no one can
read. A reviewer rejects such a board, or worse, it fails in the field. This page and the pages it names
teach the practice that prevents this. They state practice, not features of Fenolite; where a command
answers a question, the page names it.

## Whose numbers apply

No practice page gives a limit. Clearances, creepage distances, current capacities, temperature rises,
spacings and drill sizes come from three places:
- **The user's standard** and the product's requirements: insulation, temperature, environment.
- **The fabricator's** capability: minimum track, gap, drill, annular ring, mask web.
- **The datasheets** of the parts: pad geometry, keep-outs, thermal pads, layout recommendations.

When a number is missing, ask for it. Do not take one from an example: every number on these pages is
either marked as an example or named as the input of a public method. Write each number you use into the
design with its source, so that a reviewer can trace it.

## The order of work

Work in this order. Each step constrains the next, and going back is cheap only while the copper is not
drawn yet.

1. **Requirements, schematic and domains.** Read the schematic as a set of functions and voltage domains:
   power input, rectifier and bus, power stage, gate drive, sensing, control, communication, protective
   earth. Write down the currents, the voltages between the domains, and the mechanical constraints
   (outline, holes, connectors, heat sinks, enclosure heights). Fix in the schematic what the board will
   inherit: net classes, ratings, fuses, protections. See `board-schematic` and `board-insulation`.
2. **Floorplan.** Place the regions first, then the parts that close the large current loops, then the
   rest. Leave the connectors and the mechanical parts where the enclosure wants them. See
   `board-floorplan`.
3. **Power and grounds.** Decide the current paths, the copper they need, the ground domains and the
   single tie between them before any signal is routed. See `board-power` and `board-grounds`.
4. **Sensitive signals and EMC.** Sense lines, references, feedback, clocks and gate drives come next,
   short and away from the switching nodes. Plan their ways across the board before you route anything.
   Arrange the mains entry, the filter and the earth bond. See `board-emc`.
5. **Routing.** Route the critical nets first, by hand or by script. Then route the rest, with a router
   or by hand, in a consistent style. See `board-routing`.
6. **Pours and stitching.** Pour the planes, apply the cut-outs, stitch the planes, then check that
   every pin of a poured net is still connected.
7. **Checks.** Run `fenolite check`, `fenolite analyze` against the user's requirements, and
   `fenolite ready`. One fix per iteration. See `checks` and `rules`.
8. **Assembly and documentation.** Do designators, polarity, test access, fiducials, 3D bodies and the
   drawings. See `board-assembly`.
9. **Review.** Review your own board against the checklist before handing it over, and record every
   decision and open item. See `board-review`.

After the pours (step 6) and before the review, run the practice kinds of `analyze`. A zone whose fill is
missing or older than its cut-outs is poured again on a raster, and every row says which copper it used.
Rows of your requirements file (`[[decoupling]]`, `[[body_copper]]`, `[[current]]`) turn facts into
findings; the coupling score only ranks pairs.

```fenolite-cmd
fenolite analyze board.kicad_pcb --kinds connectivity,dead,decoupling,relief --dead-distance 5mm --json
fenolite analyze board.kicad_pcb --kinds coupling --aggressor 'SW_*' --victim 'ADC_*' --json
```

Throughout, keep the habits of `board-workflow`. The owner edits the same files, and a lost edit costs
more than any layout fault.

## What a check cannot see

Look for these yourself. Each one is on a practice page with the way to look for it.

| fault | why no rule finds it | page |
|---|---|---|
| a net class that exists only on the board | the next update removes it, and the default rule then holds | `board-schematic` |
| an AC-rated part interrupting a DC bus | ratings are not in the board file | `board-schematic` |
| a large loop area in a switching path | every track is wide enough and every gap is legal | `board-power` |
| filtered and raw mains copper overlapping through the board | they are different nets at a legal distance | `board-emc` |
| two grounds tied in several places | the nets are one net, as the schematic says | `board-grounds` |
| a sense pair that also carries the power current | the connection exists, so nothing is open | `board-grounds` |
| high voltage under a metal-cased part | the part's body is not copper | `board-insulation` |
| a creepage path around the end of a slot | the clearance rule measures through air on one face | `board-insulation` |
| a signal routed across a split plane | the plane is not its net | `board-routing` |
| a barrier that nets cannot cross | the router reports open nets, not why | `board-routing` |
| decoupling far from its pin | the capacitor is connected | `board-floorplan` |
| unreadable or misplaced designators | silkscreen rules check overlap, not meaning | `board-assembly` |
| a net that no probe can reach | nothing requires a test point | `board-assembly` |
| a library that differs from the board | the board is valid on its own | `board-workflow` |

## The habits that matter most

- **Copy a reference design by pads, not by eye.** Where a part's datasheet or a reference board shows
  a layout for a critical block (a regulator, a gate driver, a power module), reproduce its geometry:
  the relative pad positions, the loop, the ground return. Rotate and move it as one block. Fit it by
  the pads, and check the fit with `fenolite pads`.
- **One change, then check.** After each change run the check that judges it, and look at the result.
  A batch of ten changes that fails cannot be untangled.
- **Look at the board.** Render it (`fenolite render`) and look at each region at the scale of a
  reviewer. Many faults on these pages are obvious in a picture and invisible in a report.
- **Say what you did not do.** A board handed over with "creepage not measured on the bottom face" is
  honest; one handed over as "done" is not.
- **Ask before you change the owner's decisions.** A placement, a part choice or a copper shape that
  the owner set is a decision, even when you would do it otherwise. Propose the change with its reason,
  and wait for the answer.

```fenolite-cmd
fenolite check board --format concise --json
fenolite ready board --no-kicad --json
fenolite render board -o board/views --svg --dry-run --json
```

Read next: `board-floorplan`, `board-review`, `board-workflow`.
