---
topic: board-routing
title: Routing practice
summary: Count the crossings of each barrier first, critical nets first, a clean octilinear style, sensitive nets, vias, and an external router's input.
---

# Routing practice

Routing is the last step of a design that is already decided. When placement, power and grounds are
right, routing is mostly short and straight. When a net will not route, the cause is nearly always
upstream: a barrier with too few ways across it, or a part on the wrong side. Change the cause, not the
router's settings. The page `routing` gives the routers and the commands.

## Count the crossings

Before you route, find each barrier on the board:
- a row of pins on a large part;
- a bank of capacitors;
- a slot, or the border of a high-voltage region;
- a keep-out around a screw or a heat sink.

For each barrier, count the nets that must cross it, and the ways across it on each face. A way is a
gap wide enough for one track and its clearances. If there are more nets than ways, move parts now:
routing will not find ways that do not exist. Then assign each crossing net to a way, and route those
nets first.

Watch for limits that are not copper:
- a via is not allowed near a part whose pins swing at high voltage;
- a face is closed under a part body;
- a corridor narrows at a mounting hole.

Old stitching vias can close a new corridor. Look again after every placement change.

Prove the hardest area first: route it alone, on a copy, before you route anything else. And never relax
a rule to make a route pass. A route that needs a smaller clearance needs a decision, not a setting.

## Order

1. **Critical nets, by hand or by script:** Kelvin sense pairs, gate loops, feedback and reference
   lines, crystals, differential pairs. Each one has a shape that matters. Write it as scripted copper
   (`design.track`, `design.via`) or draw it, and lock it.
2. **Power bands** (`board-power`).
3. **The rest, with a router.** Route by groups of nets with `--nets`, most constrained first
   (`--order`). Check after each group.
4. **Ground last.** Make the final fix-up of a ground domain (stitching, the single tie) after the
   signals are in. A ground pour placed early takes the ways that signals need.

Check each group with `fenolite check` before the next one. Treat a router's output as a draft that you
review, straighten and accept, not as a result. Keep hand routes as data, each with its reason, so that a
later step can lay them again.

- **Keep a power path on one layer, without vias.** Let the signals change layer instead.
- **Route signals around a bank of bulk capacitors,** not through it. Feed the bank like a comb, one
  short branch per capacitor from a straight trunk, not in a zig-zag from one capacitor to the next.
- **A track that stops just short of a pad is an open connection,** even when it looks connected in a
  picture. Join every end to its pad's copper.

```fenolite-cmd
fenolite route board --router freerouting --nets "SENSE_*" --require-complete --dry-run --json
fenolite route board --router freerouting --nets "*" --order "GATE_*" --order "SENSE_*" --dry-run --json
fenolite net board SENSE_P --json
```

## Style

A reviewer reads routing as a drawing. Clean copper is easier to check, to probe and to change.
- **Use corners of 45° by default.** A 90° corner is acceptable where it makes a run straighter. An
  acute angle is never acceptable: it traps etchant and it looks careless.
- **Use few jogs.** Prefer straight runs and few bends. A router's output often steps every few
  tenths of a millimetre. Straighten it before you hand it over: merge collinear segments, remove small
  jogs, and check the clearance after each change.
- **Run parallel tracks at an even pitch,** and bend them together.
- **Clean before you judge.** Merge collinear micro-segments before you count the angles, and remove
  dangling stubs, vias joined on one layer, and duplicate or zero-length tracks. Prove that the clean-up
  changed no connection.
- **Stay on a grid** where the parts allow it. Bend on the grid. A turn hidden inside a pad or a via is
  acceptable.
- **Use pours that look drawn:** bands of straight edges and chamfered steps (`board-power`).

## Sensitive nets

- **Keep amplifier inputs, references, feedback and clock lines away from the switching nodes.**
  Switching nodes are the phase outputs, the bootstrap capacitors and the gate tracks. Never route a
  sensitive net under or between the pins of a switching part.
- **Keep the reference plane whole under a sensitive net** (`board-grounds`, "Return paths").
- **Use a minimum of vias on sensitive nets.** Each one adds inductance and needs a return via beside
  it.
- **Width follows function.** Do not route signals at the fabricator's minimum width without a reason:
  wider tracks are cheaper to make and easier to repair. Size power by current (`board-power`).

## External routers

An external router reads an exported description of the board, with the nets, the classes, the widths
and the clearances, and routes against that description, not against the board. Before you blame the
placement for a poor result, read what the router was given:
- **Widths.** A width rule with a preferred value can become the width of every track in the export.
  Every net then routes at that width, and little fits.
- **Clearances.** A rule that holds one class against all other classes, or a class against itself,
  can be raised to the largest clearance for every pair in the export. A dense region then closes.
- **Pours and keep-outs.** A router that does not see a pour, or that treats it as passable, routes
  through it. Block the real shape of the pour, not a large rectangle around it.
- **Item identities.** Items that are named by their index in a list change names after a deletion.
  Identify them by position or by a stable id.

Judge the routed board with `fenolite check`, not with the router's report.

## Typical failures

- **Hours on a barrier with too few ways.** Three nets had to cross the pin row of a power module,
  where only a few ways existed. Many routes failed before anyone counted them. Moving the part that
  needed them left one pair crossing.
- **A router that closed one connection in six.** An external router closed about one connection in
  six. Its input gave every track a preferred width of several millimetres, and raised one-sided
  clearance rules to all pairs. With both fixed in its input, the open connections dropped by three
  quarters, and no new clearance error appeared.
- **Routing rejected for its jogs.** A router's output was rejected for its many small steps. The
  owner's rule became: straight runs and few bends, 45° by default, 90° where it straightens, never
  acute.

Read next: `routing`, `board-grounds`, `board-review`.
