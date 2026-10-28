---
topic: board-assembly
title: Assembly, test access and libraries
summary: Designators and silkscreen, polarity and pin 1, test points and fiducials, footprints by IPC-7351, 3D bodies, and the board as the master of its library.
---

# Assembly, test access and libraries

A board is built, inspected, tested and repaired by people and machines that see only the board and its
drawings. Each of them needs marks on the board and data that agree with it. Faults here rarely stop a
board from working. They stop it from being built right, tested, or accepted in a review.

## Designators and silkscreen

- **Make every designator readable on the board,** next to its own part, so that it cannot be read as
  the neighbour's. Where the board is too dense, put it on the assembly drawing. Never leave designators
  missing at random. Use at most two reading directions on a face.
- **Keep designators off pads, vias, holes, exposed copper and other part bodies.** Measure the text
  with the target tool's real text box, then run that tool's own check: a text box estimated by eye is
  often too small.
- **Use one text height and stroke for every designator,** at or above the fabricator's minimum.
- **Let `fenolite silk` place the designators** of a KiCad board: beside each part, clear of pads,
  holes, silkscreen, courtyards and the edge, at 0 or 90°, a row of equal parts on one line. It measures
  each text with `kicad-cli`, checks every place it writes, and `--drc` has KiCad judge the result.
  `--keep` moves only the texts that sit on something; `silk.no-place` names a part without room.

```fenolite-cmd
fenolite silk board --designators --dry-run --json
fenolite silk board --designators --sizes 1mm,0.8mm --angles 0,90 --clearance 0.15mm --drc --confirm --json
fenolite silk board --designators --keep --refs "R*" --measure estimate --dry-run --json
fenolite explain silk.no-place
```

- **Clip silkscreen from pads, mask openings, drills, slots and the edge,** and check again after every
  placement change. Clip the footprint's own outline too, then keep the library in step (see
  "Libraries"), or the next update brings the ink back.
- **Let `fenolite silk --clip` cut the silkscreen** of a KiCad board at every mask opening and pad hole,
  the footprints' own outlines too, alike on every instance. `silk.footprint-changed` names each footprint
  whose library must then be written again from the board; `silk.cut-by-other` names parts too close.

```fenolite-cmd
fenolite silk board --clip --dry-run --json
fenolite silk board --clip --margin 0.1mm --designators --drc --confirm --json
fenolite library board --out lib.pretty --dry-run --json
fenolite explain silk.footprint-changed
```
- **Mark polarity and pin 1 where they stay visible after assembly:** outside the body, not under it.
  Put these marks in the library footprint, not only on the board. Check after every clean-up that
  each mark survived.
- **Mark what a person in the field needs:** each fuse's rating beside it, taken from the part that is
  actually fitted; each connector's body outline and keying side; the function of each power connector's
  pins, checked against the harness.
- **Mark the board** with its identity and revision, taken from one project parameter, so that they
  agree with every release document. Leave an area for a date code or a serial label. Add the warnings
  that the product's safety design asks for, and mark drafts as drafts. Delete any marking inherited from
  another product.

## Test access

- **Plan the tests with the test team before the layout freezes:** in-circuit, functional, or both,
  from which face, per part.
- **Give one test point to every net that the test needs,** usually every net, drawn in the schematic
  on its circuit. Keep a coverage list.
- **Place test points where a probe can land after full assembly:** clear of part bodies and tall
  neighbours, at the fixture's pitch, on the probe face. On the solder face, keep them clear of the
  joints of other nets' through-hole leads. Put each one on its own net's copper, never inside another
  net's pour.
- **Use one footprint and one parameter set for every test point.** Decide explicitly whether test pads
  get paste, on each face, and enforce it with a rule.
- **Remember the domain.** On a controller that is not isolated from the mains, the test points and the
  programming port are at mains potential. Lay out the programming port as a standard row of pads, in
  the pin order of the fixture or the programming tool.
- **Measure the coverage** with `fenolite testpoints`, against what the owner asks for. The numbers below
  are examples.

```fenolite-cmd
fenolite testpoints board --side bottom --min-coverage 100 --min-pitch 1.27mm --json
fenolite testpoints board --min-fiducials 3 -o board/testpoints.csv --dry-run --json
```

- **Close the gaps** with `--place`: one probe and its track per uncovered net, checked before it is written,
  kept by a rebuild. Read `result.place.unplaced` and each `testpoint.no-site` for the nets left over.

```fenolite-cmd
fenolite testpoints board --place --side bottom --drc --dry-run --json
fenolite testpoints board --place --nets 'SENSE_*' --grid 2.54mm --reach 5mm --size 1mm --dry-run --json
```

- **Fiducials are for the placement machines.** Each face with parts gets three global fiducials, not in
  a symmetric pattern, near the corners. Each fine-pitch part gets local fiducials when the assembler asks
  for them. A fiducial is bare copper with a mask opening and no silkscreen nearby (`design.fiducial`).
  Check them again after every move.

## Footprints

- **Verify every footprint against the drawing of the exact part that is bought,** and record that
  drawing. Name land patterns by IPC-7351, and draw them from the datasheet's recommended land pattern.
- **Size holes from the maximum lead envelope,** not from the nominal lead. Remove phantom and duplicate
  holes. Check a footprint's chirality against a known-good one.
- **Give each footprint a courtyard** that reflects the real body. Give every pad its mask and paste
  openings, and classify every pad that has no net or no symbol pin.
- **Make the symbol, the value, the part number, the package and the land pattern describe one part.**
  Treat a generic library's default values as undefined.
- **Use the house library,** where the user's organisation has one, with its names, its parameters and
  its style. Add a missing part in that style, in a separate add-on library, and list each addition for
  the librarian. `footprints` says what Fenolite infers and what a person must still check.

## 3D bodies

- **Give every part a 3D body that represents the real part,** fitted to its pads, with the right height.
  A wrong height is worse than none: it gives a false clear in the enclosure and collision checks.
- **Check the orientation** after any rotation or copy. A body copied from another board keeps that
  board's rotation. Fit it by the part's pads, not by the part's origin.
- **Edit embedded models only through the CAD tool.** An embedded model carries data, such as a checksum,
  that a file editor may not reproduce. Copy bodies that the tool itself wrote, and let the owner place
  new models in the tool. Check interference in the tool's own 3D view.

## Libraries

- **The board is the master** once anyone has edited footprints, silkscreen or 3D bodies on it. Make the
  library from the board. Never push an older library onto the board (`board-workflow`).
  `library --diff` lists how a library differs from the board's footprints, and writes nothing.

```fenolite-cmd
fenolite library board --diff lib.pretty --json
```

- **Keep the project library self-contained,** versioned, and compared by hash at every rebuild.

## Manufacturing data

- **Write a complete fabrication specification.** It gives:
  - the stack-up, from the fabricator's real options;
  - the finished copper;
  - the laminate's material group or tracking index, with no substitution;
  - the mask, the finish and the tolerances.

  Make every document agree with it.
- **Send one outline layer** that holds every cut-out and slot. Send one consistent data set, and apply
  the assembly variant to every assembly output.
- **Ask the fabricator's and the assembler's rules for each detail,** in a written list of questions,
  and track the answers. The details are:
  - the annular ring, the mask web between pads, and copper to the board edge, cut-outs and score lines;
  - drill to copper, slot aspect ratios, and acid traps;
  - paste on large thermal pads (split into windows), and the stencil;
  - vias in pads (filled and capped, or kept out of pads and their mask openings);
  - ceramic chips and tall bodies near a score line;
  - the panel's rails and fiducials (`fabrication`).
- **Agree the soldering process** before you fix the side of the through-hole parts. Give the assembler a
  list of small parts with unequal copper on their two pads.

## Typical failures

- **Silkscreen that came back.** Footprint silkscreen was clipped on the board. An update from an old
  library then restored every outline over the pads.
- **Rejected for its library.** A first board was rejected in review: its parts did not come from the
  organisation's library and did not follow its symbol style. The second version used the house library
  and an add-on library in the same style.
- **A 3D body that the tool could not save.** A model was edited and embedded by a script. The CAD tool
  showed nothing, and it crashed on save. Models must be placed by the tool.
- **Marks lost in a clean-up.** An automated silkscreen clean-up removed a diode's cathode bracket and
  an amplifier's pin-1 dot. Its check reported no silkscreen problem, because it looked only for
  collisions. An audit that checks every polarized part for its mark now runs after each clean-up.

Read next: `board-review`, `fabrication`, `footprints`.
