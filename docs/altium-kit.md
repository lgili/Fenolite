# The Altium verification kit

Altium Designer cannot run in CI, and Fenolite never starts or drives it. The kit is how a person with
Altium on their own machine confirms what Fenolite writes: a fixed acceptance run whose results are files
that Fenolite checks and that are archived. It is the base of the label `ALTIUM-VERIFIED(kit)`
(capability `altium-verification`, "Verification kit contents" to "Kit run record"; capability
`verification-evidence`, "Kit label rows").

## What the kit is

`fenolite kit build --out DIR --confirm` writes a folder that is the same for everyone, byte for byte:

- `kit.json`: the kit's version, Fenolite's version, every file of the kit with its SHA-256, and every
  step. The SHA-256 of this file is the kit's digest.
- `STEPS.md`: the numbered checklist, generated from the steps of `kit.json`.
- one folder per sample, with the Altium project that Fenolite builds from the sample's script under
  `examples/kit/`;
- `kit_script.pas`: a script that the user may start from inside Altium for the steps marked `scripted`;
- `results/`: empty but for `form.json`, the form that the user fills in.

Nothing in the kit comes from outside this repository, and nothing that the kit builds is committed.

## What a run proves

A run proves the kit's samples on one Altium version on one machine. Each step ends in a file that Altium
writes into `results/` (a document saved under a given name, an exported report), or, where no file exists,
in a value typed into `results/form.json`.

- A file is checked by `fenolite kit verify`: a re-saved document is read by Fenolite's readers and
  compared with the model its sample was built from.
- A typed value is recorded as typed. A register row that rests on one is marked `form` in the run record,
  and its result text says which fact was typed.
- A run says nothing about a design that is not a sample, about another Altium version, or about a kit
  with another digest: a change to a writer that changes a sample's bytes makes the run stale for the rows
  of that sample.

## What a saved file may contain

A file that Altium saves may hold more than the design: the name of the user account, the path of the
folder it was saved in, the name of the machine, the licence holder. `fenolite kit verify` scans the result
files for strings that look like a home folder, any other absolute path of the machine (on a drive, on a
share, or from a POSIX root) or a login name, and lists them, with the file and the offset, before anything
is recorded. A document that Altium saves holds its own full file name: the board record of a PCB document
has a `FILENAME` with the folder it was saved in, on whatever drive that is. The scan reads each file as
8-bit text and as UTF-16 at both alignments; a relative path, a stream name and a web address are not
reported. Read that list before publishing an archive. The run record that is
committed holds no path, no user name and no machine name: only digests, sizes, versions and verdicts.

## Building the kit

```
fenolite kit build --out kit --dry-run --json
fenolite kit build --out kit --confirm --json
```

The command runs in a source checkout: it builds the five scripts under `examples/kit/` (`--samples DIR`
names another folder). Without `--seed` and `--timestamp` it uses seed 0 and `2026-01-01T00:00:00Z`, so
everyone who builds the same commit gets the same kit and the same `kit_sha256`. No external tool runs.

| sample | script | what it is for |
|---|---|---|
| `flat` | `examples/kit/flat/design.py` | one sheet with a drawing sheet and a title block, a board without copper; also built in the ASCII form (`flat/ascii/flat.SchDoc`) |
| `tree` | `examples/kit/tree/design.py` | four sheets in three levels with a bus; no board |
| `routed` | `examples/kit/routed/design.py` | tracks, vias, one unpoured polygon, five rules, two planted violations, an output job |
| `board6` | `examples/kit/board6/design.py` | six copper layers with a plane, blind and buried vias, texts, graphics, a keep-out, a hole |
| `libs` | `examples/kit/libs/design.py` | a schematic library and a PCB library of seven parts |

The kit also holds `templates/iso5457_generic.SchDot`, the sheet template of group K8. It is built from the
shipped specification when the kit is built: no template file is kept in the repository.

## The steps

`STEPS.md` of a built kit is the checklist; this table is its outline. The minutes are estimates made
without a run, not measurements.

| group | what | samples | steps | minutes (estimate) |
|---|---|---|---|---|
| K1 | Open and save each document kind | flat, libs, tree | 8 | 10 |
| K2 | Compile and messages | board6, flat, libs, routed, tree | 5 | 8 |
| K3 | Change order into an empty board | flat | 2 | 8 |
| K4 | Rules editor and rule check | routed | 4 | 8 |
| K5 | Layer stack, vias, texts, keep-outs | board6 | 5 | 10 |
| K6 | Repour | routed | 1 | 4 |
| K7 | Output job | routed | 2 | 6 |
| K8 | Sheet template and special strings | flat, kit | 3 | 5 |
| K9 | Libraries | libs | 2 | 5 |

Together about 64 minutes, plus the time to fill the form. A run may leave groups out: their steps are
`skipped`, and the rows they settle stay as they are. Group K9 is the first to leave out.

Step K9.1 leaves the sheet of `libs` saved after "Update From Libraries". That file shows that the nets
are kept; it cannot show that the update ran, and the kit runs only the full replacement. So `H-A-SCH-UPDATE`
(what the update does to a part, and the update of selected attributes) is settled by no step and stays an
author report, and `H-A-SCHLIB-UPDATE` passes only with the typed value of step K9.2 and is marked `form`.

Fenolite writes no component body, so no step reads one. The DSL has no bus, so the sample `tree` gets its
bus from its script's `kit_model`; no step reads the bus in Altium, and `H-A-SCHX-BUS` stays an author
report.

## The script

`kit_script.pas` is a DelphiScript file, generated from the steps marked `scripted`. Open a sample project
of the kit and give it the focus, open `kit_script.pas`, run File » Run Script and choose `FenoliteKitRun`;
do that once per sample project. For the project in focus the script compiles it, writes the messages to
`results/<sample>/messages.txt` and adds one line to `results/script.log`: the step and `done`, or the
step and an error text. It writes nothing outside `results/`. Nothing in Fenolite starts Altium or the
script.

The names and signatures of the script's calls were read from a text rendering of each documentation
page on 2026-10-06, not from the page itself (`script.SOURCE_PAGES`, `script.READ_AS`), and the script
has not run in Altium. So the first step of a run that uses it is to open `kit_script.pas` in Altium's
script editor and compile it. If a line is refused, report that line and do the scripted steps by hand:
a wrong signature then costs a minute, not the run.

No page that was read states the version of Altium Designer it describes (`script.PAGE_VERSIONS`): the
pages of the DelphiScript routines and keywords are in the Altium Designer documentation at an address
without a version, and the pages of the interfaces are in the Altium DXP Developer documentation, which
names none. The first run of the script is on Altium Designer 26 (`script.FIRST_RUN_ON`), so a name or a
signature may have changed since a page was written.

The script was written from Altium's public scripting documentation only, read for the names and the
signatures of the calls. Nothing was transcribed: no example, no snippet, no forum post and no vendor or
third-party script was used. Every routine, method and property it uses:

| call | what the script uses it for | source |
|---|---|---|
| `GetWorkspace` | the workspace manager | S-0503 |
| `DM_FocusedProject` | the project that has the focus | S-0503 |
| `DM_MessagesManager` | the Messages panel's manager | S-0503 |
| `ClearMessages` | empties the panel before the compile | S-0503 |
| `MessagesCount` | the number of messages | S-0503 |
| `Messages` | one message by index | S-0503 |
| `MsgClass` | the class of a message | S-0503 |
| `Text` | the text of a message | S-0503 |
| `Source` | the source of a message | S-0503 |
| `DM_Compile` | compiles the project | S-0504 |
| `DM_ProjectFileName` | the project's file name, which names the sample | S-0504 |
| `DM_ProjectFullPath` | the project's path, from which the kit's folder follows | S-0504 |
| `AssignFile` | names a text file | S-0501 |
| `Append` | opens `results/script.log` to add a line | S-0501 |
| `Rewrite` | creates a text file | S-0501 |
| `Writeln` | writes a line | S-0501 |
| `CloseFile` | closes the file | S-0501 |
| `Copy` | a part of a string | S-0501 |
| `Length` | the length of a string | S-0501 |
| `UpperCase` | compares the project's file name without regard to case | S-0501 |

Its keywords (`And`, `Begin`, `Do`, `Else`, `End`, `Except`, `Function`, `If`, `Nil`, `Not`, `Procedure`, `Result`, `Then`, `Try`, `Var`, `While`) are those of the keywords page (S-0502).

What the design of the kit asked of the script and it does not do, because no public page documents a
call for it; these steps are manual:

- **opening a project**: the reference pages give two forms of `DM_OpenProject` (one and two arguments), and a person must see whether a repair prompt appears; the script works on the project that has the focus.
- **saving a document under its result name**: the page of `IServerDocument` (S-0505) describes `DoSafeChangeFileNameAndSave` only as a test of whether the save is possible, and `DoFileSave` as a save in place in a format whose names it does not list for current versions; no page says that either writes the file under a new name.
- **the rule check report, Repour All and the containers of the output job**: the page of the server processes (S-0506) names no process for them, and the rule check opens a dialog.
- **the change order and Update From Libraries**: both open dialogs that a person reads.

So the script performs the five compile steps of group K2 and nothing else. It was never run in Altium:
`H-A-KIT-SCRIPT` is `INFERRED`. Four things about it are inferred and not documented: that a script file
opened without a script project is offered by File » Run Script, that `Messages` counts from 0, that
`DM_ProjectFullPath` ends in the project's file name, and that `Append` on a file that does not exist
raises an error that Try-Except catches. If one of them is wrong, the script logs an error or writes
nothing, and the step is done by hand: every scripted step is a complete manual step.

## What `kit verify` checks

`fenolite kit verify DIR --json` reads the kit folder after a run and writes nothing. Exit 5 when a step
failed, when a file of the kit differs from `kit.json`, or when the form is not sound; exit 3 for a folder
without `kit.json`.

1. Every file of the kit matches its digest in `kit.json`. A changed sample fails every step of that sample.
   One change is accepted: Altium writes a sample's own project file again, with every key it knows, when
   the project is saved (step K1.5 does that). A project file of a sample whose bytes differ and that still
   lists exactly the sample's documents, each by its name in the sample's folder, is reported as
   `kit.project-resaved`, fails nothing, and is named in the run record (`kit_resaved`). A project file
   with another list of documents, and any other file of the kit that changed, fails as before. Files that
   the tool adds beside the kit's (a history folder, a structure file) are not in the manifest and are not
   read.
2. `results/form.json` has its schema and names the tool as `AD <major>.<minor>`, the system (`Windows`,
   `Linux` or `macOS`) and the date.
3. Every `file` step, by its checks:

| check | what it does |
|---|---|
| `resave` | the re-saved document passes RT-A0 and RT-A1, and its import equals the import of the kit's own document at every level of `equivalent` that the document holds |
| `netlist` | the document's import equals the import of the kit's own document at levels 1 and 2 of `equivalent` (components and nets) |
| `poured` | every polygon of the re-saved board holds poured copper |
| `messages` | the file holds at least one line and no line of the class Error or Fatal Error |
| `listing` | the file holds at least one line, and no line holds a folder |
| `present` | the file exists and is not empty |

   Before any of these, a result file is told by its content: when it is of another kind of document than
   the step wants (a schematic saved under the name of the board, a library under the name of a sheet), the
   step fails with one reason that names both kinds, not with a read error.
   When the result file is absent and its folder holds a file of the same name with another ending that
   no step asks for (`board6.SchDoc` where step K5.1 wants `board6.PcbDoc`), the step fails and names that
   file; it is not passed over as not done.

4. Every `form` value equals its expected value.
5. The privacy scan (above).

The reference of a re-saved document is Fenolite's reading of the kit's own document, at every level of
`equivalent` that the document holds (1 and 2 for a schematic, up to 5 for a routed board). The model of a
build is not the reference, because it holds no placed footprint. A library is compared by its symbols with
their pins and its footprints with their pads; a project file by the documents it lists.

The kit profile lists what a comparison leaves out, each with its cause (`fenolite.cli._kit.KIT_PROFILE`).
It holds one entry: a free hole is imported as a part without a designator, which level 1 cannot pair by
reference on any comparison. A difference that no entry names fails its step. An entry for something that
Altium normalises is added only with the cause that a run showed.

A hypothesis passes when every step that names it passes, and is marked `form` when one of them is a typed
value. `H-A-KIT-SCRIPT` passes only in a run where the script did every scripted step.

**The parity check.** The steps that leave a schematic or a PCB document of a sample with both (K1.1, K1.2,
K1.6, K3.1, K5.1, K6.1, K9.1) also run the stage `parity` of `fenolite check` (change c0088) on a temporary
copy of the sample's project in which the saved document takes the place of the kit's own. Its findings
must be those of the kit's own project, which are none on the five samples; the copy is removed and
nothing of the kit is written. The sample `tree` has no board and is not judged by it.

**The copper check.** The check `copper.clearance` of the steps K4.2 and K6.1 is the stage of that name of
`fenolite check` (change c0088). The sample `routed` plants one clearance violation, between `VIN` and
`LED_A`. For K4.2 the check runs on the kit's own board and must find that one violation, no other and no
short; Altium's report of the step is archived as it is, and the two counts typed from it are steps K4.3
and K4.4. For K6.1 it runs on the board that Altium repoured and saved: the same one violation, no short,
and no polygon left out of the check (none unpoured, none without a clearance to judge it by). No check
is pending today. Nothing of the kit needs the write-back of an imported board (c0090); the first real run
waits for it all the same.

## Recording a run

```
fenolite kit record kit --out . --dry-run --json
fenolite kit record kit --out . --confirm --json
```

`record` writes `results.zip` beside the kit folder and the run record
`docs/evidence/altium-kit/<run id>.json` into the repository named by `--out`. It refuses a synthetic run,
a kit whose own files differ from `kit.json`, and a form that is not sound. `result.rows` lists the register
rows whose label may change, with the label text and the text their result cell must hold.

The archive is a Zip with stored members, sorted names and one fixed date, so the same result files give
the same bytes everywhere. **Publish it as an asset of the GitHub release that the run supports, named
`altium-kit-<run id>.zip`**; the record holds only its SHA-256 and size. Read `result.privacy` first: the
archive holds the files as Altium saved them.

## The label rule

A register row may be set to `ALTIUM-VERIFIED(kit; AD <major>.<minor>; <date>; <run id>)` when a committed
run record holds a passing verdict for it, its result text names the archive digest of that run (and says
`form` when the verdict rests on a typed value), and the run is not stale. A run is stale for a row when a
sample that the row's steps use has other bytes in the kit that the tree builds now.
`tests/unit/test_hypotheses_register.py` fails for a kit label without all of that, and
`fenolite kit status` lists the committed runs and the stale rows. A stale row goes back to the level it
had, with the stale run named in its result, until a new run is recorded. A synthetic run never gives a
record, and an author report is never recorded as a kit run.

## What is not there yet

- No run is recorded: no row carries the kit label. The maintainer made a first manual run in Altium
  Designer 26 on 2026-10-07; it is an author report, it was made on a kit with another digest than the
  tree builds now, and what it found was corrected by change c0139 (the privacy scan, the project file
  that Altium saves again, the expected values printed for number steps, the update step, the wording of
  step K5.1).
- No JSON Schema file is generated for `kit.json` and for the run record: `schemas/` is generated from
  dataclasses, and both documents are built as plain mappings. `record.record_problems` and
  `results.form_problems` check their form.
