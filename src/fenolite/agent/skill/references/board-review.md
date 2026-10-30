---
topic: board-review
title: Reviewing a board before handing it over
summary: The self-review checklist, what reviewers reject, how to answer review findings, and how decisions and open items are recorded.
---

# Reviewing a board before handing it over

A board goes to a review by people who did not design it. They judge it against their standards, their
library and their experience, not against the rules in the board file. Review your own board first,
with their eyes. Fix what you can, and list what you could not fix. A reviewer who finds a fault that
you knew about and did not list stops trusting the rest of the board.

## Before the review

Run the checks that a machine can run. Read every finding, not only the count.

```fenolite-cmd
fenolite check board --format concise --json
fenolite ready board --json
fenolite analyze board/board.kicad_pcb --requirements board/requirements.toml --json
fenolite testpoints board --min-coverage 100 --json
```

`ready` says whether the project is electrically ready: open nets, KiCad's ERC and DRC, unconnected
pins, power nets without a width or a zone, and parts without a footprint or a value. A clean reply is
the floor, not the review. In the third line, the requirements file is the user's.

- **The native CAD tool is the final gate.** Offline checks, previews and models are not verification.
  The order before any output is: update from the schematic, refill, run the tool's own DRC, then make
  the outputs (`export --readback` compares them with the board before writing). A DRC report cut at a
  maximum number of items is not a clean report.
- **Check your own tools first.** When a script of yours measures the board, the counts of tracks, arcs,
  vias, pads and pours in its model must equal the board's own counts. A model that silently drops every
  arc, or ignores the pour cut-outs, reports a clean board that is not clean.
- **Beware the false green.** A check that passes because it looked at the wrong thing is worse than no
  check. Ask of each pass what it would have caught.
- **Judge an imported board on the source's own fill.** A board imported from another CAD tool may carry
  rules that the import changed, such as one clearance for every zone. Use the source's fill, or a
  simulated pour, not the imported DRC.
- **After every update, move or footprint change, run a global short and collision check.** A moved pin
  can leave an old track running into a new pad.
- **Review a frozen snapshot** with its hashes, never a file that is still being edited. Compare it with
  the previous released revision; `diff --allow` fails on any change of a kind you did not plan.

## The checklist

Walk through the board region by region, with a render at a reviewer's scale and this list.

```fenolite-cmd
fenolite render board -o board/views --region 0mm,0mm,30mm,30mm --nets --open --dry-run --json
fenolite diff released/board.kicad_pcb board/board.kicad_pcb --allow track,via,arc --json
```

**Schematic** (`board-schematic`)
- Net classes sit on the schematic, and the board's classes match them.
- Pin sets match between the schematic and the board, single-pin nets included.
- Fuses are in order. Bus parts are rated for DC. Each rating was read with its condition.

**Floorplan** (`board-floorplan`)
- Mechanical parts and keep-outs are where the enclosure needs them, and they are locked.
- The regions follow the domains, and the power flows in one direction.
- Each decoupling capacitor sits at its pin, and reference blocks match their reference pad by pad.
- The collision audit is clean.

**Power and grounds** (`board-power`, `board-grounds`)
- Each switching loop is drawn and small, with its capacitor at the switch's pins.
- Each power path's copper is measured against the user's current and temperature rise, and no neck is
  left.
- Each pair of ground domains meets at one tie, at the measuring point. The single-tie test ran on the
  last copper.
- The sense pairs leave from the sense element's pads and run together.
- Every pad of a poured net is connected after the last refill.

**Insulation and EMC** (`board-insulation`, `board-emc`)
- Every net and every piece of metal has a domain. Every pair of domains has a minimum with a source.
- Clearance and creepage are measured on the filled board, on both faces, with the slots.
- No high-voltage copper lies under a metal-cased part. Screws and heat sinks have their keep-outs.
- The filter's two sides are kept apart, and the earth bond exists in copper.

**Routing and assembly** (`board-routing`, `board-assembly`)
- The style is consistent: 45° corners, few jogs, no acute angle. Sensitive nets stay away from
  switching nodes.
- Designators are readable, and polarity marks survive. Test coverage matches what was agreed.
- Footprints come from the agreed library, and the 3D bodies have the right heights.

**Files** (`board-workflow`)
- The board is the master, and the library was made from it. The drawings point at this board.
- Every file handed over has its SHA-256 in a manifest (`fenolite manifest`).

## What reviewers reject

Each of these is cheap to avoid before routing and expensive to argue about after it.
- **Parts that are not from their library,** or symbols and footprints that do not follow their house
  style. Learn the reviewing organisation's library and checklists before the review, not after.
- **Values that are not visible,** and parts without their parameters.
- **Silkscreen that looks careless:** mixed sizes, text over pads, designators far from their parts,
  missing polarity marks.
- **Copper that looks improvised:** free-form pours, jogs, acute angles, wandering tracks.
- **Grounds that no one can explain,** and sense lines that share copper with the power current.
- **High-voltage spacing that nobody measured,** or that was measured without slots, pours or the
  second face.
- **A board that cannot be tested,** and a design that hides its open items.

## Answering findings

- **Answer each finding on its own line,** with a stable id: what you changed, where (file, version,
  region), and the check that shows the fix. When you change nothing, give the reason and who decided.
- **Verify each finding yourself** before you act. Grade it, and keep a refuted finding visible with
  the reason it was refuted.
- **Check the premises of a comment.** A request may describe a board other than the one under review.
  Ask the reviewer for missing inputs; do not invent them.
- **Ask the owner** when a finding conflicts with an earlier decision. Present options with measured
  trade-offs, studied on copies, and let the owner decide.
- **Turn each accepted DRC finding into a scoped rule** with its reason, or into an exclusion stored with
  its reason (`check --exclude`), and keep shrinking that list.
- **Run the whole checklist again** after a round of fixes. A fix in one area often moves a fault into
  another area.

## Decisions and open items

- **Record a decision** with the date, who decided, what was decided, the reason, and what it replaces.
  Examples: "phases stay on the bottom face; signals yield", or "no high-voltage copper under capacitor
  cans". Later work must find these decisions and follow them. Supersede a decision by a dated note,
  never by rewriting it.
- **Record an open item** with what is missing, who owns it, and what it blocks. A board with open items
  is handed over as such, never as finished.
- **Use reference boards as yardsticks, not as limits.** Check a reference's own quality before you copy
  it. A derating claim needs a derating policy.
- **Make no approval yourself.** Gate approval, safety approval and compliance belong to the people who
  sign for them. Report the measurements and the open items, and never write that the board passed a
  gate.

## The requirement matrix

Attach the matrix to a review: every electrical limit with a stable id, its status and the digest of
what it judged, and a receipt of the model and device records it read. It writes nothing.

```fenolite-cmd
fenolite check blink/build --matrix --json
fenolite check blink/build --matrix --text
```

- `deferred` (with `decidable` `place` or `route`): the board has not reached the stage that decides the
  row, such as a track width on a net with an open connection. It is not a pass.
- `waived`: a waiver accepted the row's finding at its `digest`. A changed rating, pick or kept value
  changes the digest: the finding is back and `check.waiver-expired` names both digests.
- Device records split each limit into `abs_max` (damage) and `operating` (the range the part needs);
  `[[limits]]` states a voltage between two pins, such as `between = ["BST", "SW"]`.

Accept a known risk by its row id without the code and the digest that the finding's hint ends with:

```fenolite-design
from fenolite.dsl import Design, Part, mm

design = Design("accepted_risk")
design.board(mm(20), mm(10))
design.add(Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="1uF"))
design.waive("circuit.rating-voltage", "C1:voltage", reason="bench is current-limited", digest="9f2c4a1b0d3e5f67")
```

## Typical failures

- **A first version rejected as a whole.** A board was blocked in review: its libraries did not follow
  the organisation's standard, its values were hidden, and it had to be rebuilt as a test board. Most of
  the findings were style points that would have been cheap before routing. The second version started
  from the house library, made visible values a rule, and kept a decisions file.
- **A short made by an update.** A pin was moved to another net in the schematic and pushed to the
  board. The old net's track now ran into the moved pad, which shorted a protective fuse. Only a global
  short check after the update found it.
- **A DRC report that stopped counting.** A native DRC returned exactly as many items as its export
  allowed. A second run with a higher cap showed the rest.
- **A rule that was explained twice.** The owner gave a placement rule ("nothing under the rectifier")
  in passing. It was not recorded, a later step broke it, and the owner had to say it again. A rule given
  in passing is a decision: write it down at once.

Read next: `board-practice`, `board-workflow`, `checks`.
