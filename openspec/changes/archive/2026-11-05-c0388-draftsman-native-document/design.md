# c0388 design: gate G2 after round FPC

c0172's design (Decisions 3 to 9) stayed this change's design until the correction round reported. The
report of round FPC (S-1606, `docs/evidence/altium-draftsman.md`, "Reports") changes it. This page records
the G2 decision of task 1.1 and what ships after it.

## Decision 1: G2 fails after its correction round, so route P ships (2026-11-05)

Round FPC ran on Altium Designer 24.5.2.23, an agent run at the maintainer's request (S-1606).

| probe | what it is | outcome |
|---|---|---|
| FPC1 | FP3 with the 32 root members it lacked, taken from the F0.1 control | opens with no message |
| FPC2 | FP4, the shell view, with the same root members | opens; Import Changes leaves the view empty |
| FPC3 | FPC2 as a document template, offered through Preferences | `Object reference not set`; the new document has no board view |
| FPC4 | FP3 with only the empty style lists | does not open (the D09 error) |
| FPC5, FPC6 | the control with FP3's sheet; FPC1 at format version 24 | open with no message |
| FPC7, FPC8, FPC9, FPC11 | the writer's fabrication sheet and three variants of it | do not open (`Object reference not set`) |
| FPC10 | the writer's bottom assembly sheet with its BOM | opens; the view and the BOM stay empty after Import Changes |
| D01 to D32 | the control without one root member each | 28 open; D01, D09, D14 and D23 are refused |

The coordinator ruled that FPC2 does not pass: under the round's rule, an empty view after Import Changes
fails G2. The task asks whether the root members named by the drop series make FP3 and FP4 pass:

- **FP3 passes with them.** D01, D09, D14 and D23 name `ArrowStyles`, `DocumentOptions`, `FillStyles` and
  `LineStyles` as root members a document needs in order to open. FPC1 holds them and opens. FPC4 lacks
  `DocumentOptions` and fails like D09.
- **FP4 does not.** FPC2 holds every root member of the control, opens, and still shows an empty frame
  after Import Changes. FPC10 shows the same: Import Changes fills its view's `BoardSourceName`, and the
  view stays empty. The drop series changes only root members. It says nothing about what a view needs
  in order to draw the board, so no root member can fix the shell.
- **Route T fails too.** FPC3, the template route of Decision 9, gives a document with no board view.

So G2 fails after its one correction round, with a minimal document that opens but a shell that Import
Changes does not fill (c0172's G3 case) and a template route that does not work either. By Decision 9
and cut order 7, **route P** ships: project parameters without the document, and a procedure.

**A second Altium run would be needed for any fix**, and the one correction round is used:

- The refusals look curable: always write the four root members, and give the dimensions' `ArrowStyleId`
  an `ArrowStyles` entry. That reading is the agent's (`INFERRED`). All four refused writer probes hold
  Linear Dimensions with `ArrowStyleId` 1 and an empty `ArrowStyles`, and FPC10, with no dimension,
  opens.
- The empty view has no fix in this round's evidence. Decision 4 of c0172 named the alternative: Fenolite
  writes the view's copy of the board in Altium's drawing data. That is a large, separately measured
  change with its own kit. It is not part of this change.

## Decision 2: what route P is

- **The option.** `--altium-draftsman on` is the request. c0172's Decision 9 named a new option
  `--altium-title-parameters on` for route P, but only for the G1 case, where `--altium-draftsman` would
  not exist. It exists now and defaults to `off`, so route P reuses it. No public name is added, and
  builds without the option keep their bytes.
- **The output.** With the gate closed, a request writes the non-empty title-block fields as the project
  file's `[Parameter<n>]` sections. The order is that of `lens.altium_draftsman.title_parameters`: `Title`,
  `Revision`, `Date`, `Organization`, `DocumentNumber`, `DrawnBy`, `ApprovedBy`, then the variables by name.
  The parameters go only into a project file that the build writes. A kept project file is not rewritten.
  No `.PCBDwf` is planned, the project lists no document, and the output job gains no `PCBDrawing` output.
- **The report.** `result.draftsman` stays `null`. The info `altium.draftsman-not-written` names route P and
  says one of three things: how many fields the project file holds, that the design has none, or that the
  kept project file is not rewritten.
- **Text checks.** A parameter that the ASCII project writer cannot hold, or a variable named like a
  reserved field, is an `altium.text-unwritable` error before any write, as on the gated path.
- **The drawing specification.** `--drawing-spec` is still read, and its digest is still bound in the
  plan. Route P uses no part of it.
- **The procedure** (`docs/altium.md`, "Draftsman document"): in Altium, File » New » Draftsman Document
  with one of Altium's own templates and the built PCB document, then a title block whose texts show the
  project parameters, then Import Changes and the PDF output. For drawings without Altium, build the same
  script for KiCad and use c0117's drawings.

## Decision 3: what stays and what is cut

- **Stays:**
  - the reader and the census;
  - the writer with the round F0 members of tasks 4.1 and 4.2, behind `draftsman.NATIVE_WRITE = False`,
    with its own read-back;
  - the FPC kit builder, which a later change can use;
  - the requirements "Fabrication sheet of a Draftsman document" and "Assembly sheets of a Draftsman
    document", which describe `draftsman_spec`.
- **Cut, with the reason "route P, G2 failed after round FPC":**
  - task 3.3, superseded by round FPC;
  - the acceptance kit and its run (6.1, 6.2);
  - the gate flip (6.3);
  - the requirement "Draftsman scope round trip", whose only scenario is the F8 re-save of a native
    document.
- **Rows:** `H-A-DWF-MINIMAL`, `-IMPORT` and `-TEMPLATE` record the round in their results and keep their
  levels. The run was an agent run on 24.5, and the approved 24.5 scope raises no level. `H-A-DWF-PARAMS`
  stays `INFERRED`: route P writes the parameters, and no report has shown them in a title block.

## Risks

- **The parameters are unconfirmed in Altium.** Project parameters in the `.PrjPcb` are a format fact of the
  project file, but no report has yet shown them in a Draftsman title block. The info and the docs say so.
- **The option name says "Draftsman" while no Draftsman file is written.** The info names route P every
  time, and the help text says what `on` writes.
