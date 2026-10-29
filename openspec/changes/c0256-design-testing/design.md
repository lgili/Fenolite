## Context

Source: `docs/research/circuit-as-code.md`, section 14 "Diagnostics, reviews and tests", and core change K
of "What changes in the core". Concepts only, paraphrased from public documentation: tscircuit's typed
diagnostics linked to an element, its image snapshots compared in CI and its net "x-ray" render; JITX's
report of an object created but never attached, with its file and line. No code, schema, name or table of
those projects is used.

What `dev` (0.6.0) already has, and this change reuses:

- `fenolite.api.run(command, *args, cwd=, seed=, timestamp=)` runs every command in process with the
  envelope of `--json`, and keeps the mutation protocol (`python-api`).
- `fenolite.cli._script.run_design_script` runs a `design.py` in process and locates a failure by
  `line:<n>` of the deepest frame in the script (`design-dsl`, "Design scripts").
- The model gives every object of a script a derived id (`design-model`, "Identifier derivation"):
  `cmp_…` from `component:<path>`, `pin_…` from `pin:<path>:<number>`, `net_…` from `net:<name>`.
- `fenolite render BOARD --region X1,Y1,X2,Y2 -o DIR` draws a rectangle of the board from the model, with
  no tool, into `region.svg`; every element carries a `class` and `data-*` keys naming its net, layer and
  item, in millimetres with the exact digits of their nanometres, and the same board gives the same bytes
  (`manufacturing-exports`, "Region renders" and "Region render elements"; change c0211).
- `fenolite check` stages that need no tool: everything in `STAGE_ORDER` but `ORACLE_STAGES` (today
  `model.validate`, `copper.clearance`, `length.rules`, `placement.rules`, `roles.rules`, `parity`,
  `roundtrip`; c0253 adds `circuit.rules`).
- `fenolite view --check FILE` places findings by parsing `where` (`@x,y`, `R1-2`, `R1`, a net name)
  (`check-overlay`; `view/check_overlay.py`).

Gaps: no assertion API, no golden comparison, no net highlight, no subject ids on findings, and no report
of lost objects.

## Goals / Non-Goals

Goals:

- Tests of a design that run in the fast suite: no `kicad-cli`, no corpus, no KiCad library (catalog parts
  only), no network, deterministic.
- One new public package, `fenolite.testing`, small and frozen-able: three functions (`load`, `instantiate`, `assert_render`), the `TestDesign` methods and their records.
- Golden renders that a reviewer reads in a diff (SVG text, one element per line), regenerated only through
  `render --confirm`.
- Findings whose subjects a program (the viewer of c0245, an agent) selects by id.
- A warning, with file and line, for each object the script built and lost.

Non-goals: a pytest plugin; raster or fuzzy image comparison; changing the envelope's issue object; new
measures (every judgement is an existing stage's); a usage-example harness for devices.

## Decisions

### 1. `fenolite.testing` is a top-level package that builds through `fenolite.api.run`

`load(path, *, seed=0, timestamp="2026-01-01T00:00:00Z", kicad_version=None) -> TestDesign`:

1. creates a private temporary folder (`tempfile.mkdtemp`, removed by `TestDesign.close()`, by the context
   manager and by a `weakref.finalize`);
2. runs `fenolite.api.run("build", path, "--out", tmp, "--dry-run", ...)`, then `--confirm --plan <id>`
   with the reviewed plan id, so the write follows the protocol exactly as an agent would;
3. reads `.fenolite/` with `model.canonical.load_dir` and the board through the backend registry.

A failed build raises `TestingError` (a subclass of `AssertionError`, so a test fails rather than errors)
whose message holds the error object of stderr: `code`, `message`, `where` (with `:line:<n>`), `hint`.

Alternatives considered: (a) call `to_model` directly, without a build: faster, but the board, pads and
library resolution would differ from what `check` judges, so `connected(copper=True)` and `findings()`
could not reuse the stages; rejected. (b) Write into the user's `tmp_path`: needs pytest; rejected, the
caller MAY pass `workdir=` instead. (c) Put the helpers in `fenolite.api`: `api` is frozen for 1.0 and
must not grow assertion semantics; rejected.

Layering: `testing` → any `fenolite` package, like `cli`; no package imports `testing`. It imports no
third-party module, pytest included.

### 2. The `TestDesign` surface

```python
from fenolite.testing import load, assert_render
from fenolite.dsl import volt


def test_rails():
    with load("design.py") as d:  # built in a private temp folder, no kicad-cli
        assert d.net("3V3").voltage.within(volt("3.3").pct(5))  # Range of c0246 on a Rail of c0252
        assert d.connected(d.ref("U1").VDD, d.ref("C5").a)  # same net in the circuit
        assert d.connected("U1-4", "C5-1", copper=True) is False  # not yet joined by copper
        assert not d.findings("circuit.*")  # c0253's stage, tool-free
```

| name | returns | from |
|---|---|---|
| `net(name)` | `NetView(name, id, netclass, role, voltage, pins)`; `pins` as `REF-PIN`, sorted; `role` the c0222 role kind or `None`; `voltage` a `Range` (c0246) of the rail (c0252) or `None` | circuit model, `RuleSet.roles` |
| `ref(ref)` | `PartView(ref, id, value, footprint, device, pins)`; attribute and item access give `PinView(where, id, net)` by pin name or number (checked like `Part.__getitem__`) | circuit model |
| `connected(a, b, *, copper=False)` | `bool`: same circuit net; with `copper=True`, joined by copper of the board (`analysis.connectivity` on the board-frame pads) | model, `analysis` |
| `findings(pattern="*", *, stages=None, severity=None)` | `tuple[Finding, ...]`, each `code`, `severity`, `message`, `where`, `subjects` | `api.run("check", tmp, "--stages", ...)` |
| `close()` | removes the folder | — |

`instantiate(block, **params) -> TestDesign` tests one c0251 block alone, as c0251's open question 1
recommends: it writes a throwaway script into the temporary folder that creates a design with a board large
enough for the block, calls `design.use(block, "dut", **params)`, and loads it as `load` does; every port of
the block becomes a net named `dut/<port>`, so `net("dut/VOUT")` reads the port.

An unknown net or ref raises `TestingError` naming the three closest names (the hint of `fenolite net`).
`a` and `b` accept a `PinView`, a `REF-PIN` text or a `NetView`.

`findings` runs, by default, every stage of `STAGE_ORDER` not in `ORACLE_STAGES`; a `stages=` that names an
oracle stage raises `TestingError` ("needs kicad-cli; run fenolite check instead"). `pattern` is a glob on
the code (`fnmatch.fnmatchcase`). The check's evidence is kept on the returned tuple's `evidence`.

### 3. Golden renders are `render` outputs, compared in memory

```python
def test_ground_layout():
    assert_render("design.py", "tests/golden/gnd.svg", net="GND", layers=("F.Cu", "B.Cu"))
```

`assert_render(path, golden, *, net=(), region=None, layers=None, seed=0, timestamp=...)` builds as `load`
does, draws with the same function as `fenolite render --net/--region` (decision 4), and compares bytes with
the file `golden`. It writes nothing. On a difference it raises `AssertionError`:

```
golden tests/golden/gnd.svg differs (2 added, 1 removed, 0 changed; first 20 shown)
+ <path class="track net-hi" data-net="GND" data-layer="B.Cu" data-item="trk_6c1f…" d="M12 8 L18 8"/>
- <path class="track net-hi" data-net="GND" data-layer="B.Cu" data-item="trk_6c1f…" d="M12 8 L17 8"/>
regenerate after review:
  fenolite render design.py --net GND --layers F.Cu,B.Cu -o tests/golden --dry-run   (then --confirm --plan <id>)
```

The diff (`testing/svgdiff.py`, standard library `xml.etree`) keys elements by `(class, data-item,
data-layer)` and reports added, removed and changed elements, sorted by key; unkeyed elements (grid, labels)
are compared as text lines. A missing golden file raises `AssertionError` with the same regenerate line.

Why not write the golden on mismatch with an environment variable (the usual snapshot workflow): Fenolite
writes files only through plan/confirm with a receipt, and a test that writes into the repository is a write
nobody reviewed. CI prints the diff from the assertion; a reviewer regenerates with the printed command.

Alternatives considered: PNG through `kicad-cli` (needs the tool, bytes vary by version and fonts:
rejected); the viewer's scene JSON (not a picture a reviewer reads in a pull request: rejected for v0, kept
as an open question).

### 4. `fenolite render --net NAME`

`fenolite render PATH --net NAME [--net NAME ...] [--region X1,Y1,X2,Y2] [--layers L1,L2] -o DIR`:

- draws, with `analysis.region.draw_region`, the whole board (the region is the board's bounding box grown
  by 1 mm) or the given region;
- every item of a named net gets the class `net-hi` and full colour; every other copper item the class
  `net-dim` (drawn at 20 % opacity by the embedded style); board edge, holes and grid are unchanged;
- writes one file per call: `DIR/net-<name>.svg` for one net, `DIR/nets.svg` for several (names in
  `result.region.nets`); with `--region` and no `--net`, `region.svg` as today;
- `--layers` keeps only those copper layers (plus edge and holes); an unknown layer is `FEN-2001`;
- an unknown net exits 2 with `FEN-2001`, `where` `--net`, and the three closest names in the hint, as
  `fenolite net` does;
- `--net` with `--svg` or `--png` is `FEN-2001` (the plots are `kicad-cli`'s and cannot highlight);
- `result.region` gains `nets` (the highlighted names) and `highlighted` (`{pads, tracks, arcs, vias,
  zones}` counts).

The existing `--nets` (net labels on pads) keeps its meaning; `--net NAME` is an option of its own.
argparse matches an exact option name before it tries abbreviations, so `--net` and `--nets` never take
each other's place, and a test pins it (`test_render_net.py -k option_names`). The alternative name
`--highlight` was considered; `--net` is kept because it reads as `fenolite net NAME` does (open question 5).

`render` with `--region` or `--net` accepts a `design.py`: it is built in memory exactly as `build
--dry-run` builds it (same seed and timestamp handling), and `input` names the script. `depends` holds the
script. A design without a board is `build.no-board` (exit 5), as `build`.

### 5. Finding subjects, beside the envelope's issues

`checks.stages.StageResult` gains `subjects: tuple[tuple[Subject, ...], ...] = ()`, either empty or of the
length of `issues`. `Subject(kind, id, name)` with `kind` in the closed tuple `SUBJECT_KINDS = ("component",
"pin", "pad", "net", "netclass", "interface", "track", "arc", "via", "zone", "rule_area", "rule")`, `id` the
model id (`cmp_…`, `pin_…`) and `name` the human form (`U1`, `U1-4`, `3V3`).

`fenolite check`'s `result` gains `subjects`: a list of `{issue, items}` where `issue` is the index of the
issue in the envelope's `issues` and `items` its subjects, in the stage's order; issues without subjects are
not listed. The envelope and its issue object are unchanged, so every existing consumer keeps working.

```json
"subjects": [
  {"issue": 3, "items": [
    {"kind": "component", "id": "cmp_2b1e…", "name": "C1"},
    {"kind": "net", "id": "net_91a0…", "name": "V12"}]}
]
```

Stages that fill subjects in this change: `circuit.rules` (c0253: built from the `entities` of its
requirement-table rows) and `copper.clearance`, `length.rules`, `placement.rules`, `roles.rules` (the entities they
already know). DRC and ERC findings of `kicad-cli` keep resolving by `where` (their native ids map through
`drc_json.item_locations`); a later change may add them.

`view/check_overlay.py` resolves a finding by its subjects first (an id found in the scene's `comps`, pads or
nets), then by `where` as today; the panel shows each subject's name. The c0245 viewer, when it lands,
selects the items by id.

Alternative considered: add `subjects` to the issue object. It changes `fenolite.envelope.v0` ("exactly the
top-level keys" of each issue) for every command; recommended for the contract v1 (c0216), not here.

### 6. Unattached objects: `build.unattached`

`Part.__init__`, `Net.__init__` and `Interface.__init__` record their creation site: the deepest frame of
the stack whose file lies in the script folder (the same rule as `_locator`), as `(relative path, line)`,
only while `run_design_script` runs (a context variable set by it; outside a build nothing is recorded and
the cost is nil). After the script returns, the build compares the recorded objects (held weakly) with the
design: a `Part` not in `design.parts`, a `Net` not in `design.nets`, an `Interface` not in
`design.interfaces` gives one `build.unattached` warning:

| code | severity | when |
|---|---|---|
| `build.unattached` | warning | a `Part`, `Net` or `Interface` created while the script ran never reached the design |

`where` is `<script-relative path>:line:<n>`, the message names the kind and the ref or name, the hint is
"add it with design.add(...) or connect it, or delete it". The warnings are sorted by `where` then name,
so the output is deterministic. An object created by Fenolite itself (inside `fenolite/`) is never
reported. An object garbage-collected before the check is not reported: a weak reference that died is an
object nobody kept, so there is nothing to attach (documented; the common case, `r5 = Part(...)` at module
level, stays alive in the module globals that `run_path` returns).

Alternative considered: an error. A lost object is often scaffolding while a design grows; a warning keeps
`build` exit 0 and is visible in the reply and in `findings()`.

### 7. Files and public API

- `src/fenolite/testing/__init__.py`: `load`, `instantiate`, `assert_render`, `TestDesign`, `NetView`, `PartView`,
  `PinView`, `Finding`, `TestingError`; `__all__` frozen with them.
- `src/fenolite/testing/design.py`, `golden.py`, `svgdiff.py`.
- `src/fenolite/checks/subjects.py`: `Subject`, `SUBJECT_KINDS`.
- `src/fenolite/dsl/_sites.py`: the creation-site recorder (context variable, weak list).
- `docs/testing.md` (new page, linked from `docs/index.md` and `docs/dsl.md`).

### 8. Evidence per behaviour

| behaviour | level before merge |
|---|---|
| `load`, `net`, `ref`, `connected` | the build's evidence (unchanged) |
| `connected(copper=True)` | `analysis.connectivity`'s, `INFERRED` |
| `findings` | `Evidence.combine` of the stages run, unchanged |
| net and golden renders | `INFERRED`, `H-G-RENDER-DETERMINISTIC` (same bytes on Linux, macOS, Windows, Python 3.11 to 3.13, measured by the unit jobs) |
| `build.unattached` | `INFERRED`, measured on authored scripts |
| subjects | the stage's evidence; the ids are those of `design-model` |

## Relation to the other changes of this batch

- c0246 (ranges) gives `Range.within`, used by `NetView.voltage`; c0252 (parametric interfaces) gives
  rails whose voltage `net()` reads. Without them, `voltage` is `None`.
- c0248 (devices) gives `PartView.device`; c0249 (lock) is written by the build `load` runs, inside the
  temporary folder only.
- c0251 (blocks): `ref()` accepts block paths (`buck/U1`); `instantiate` answers its open question 1;
  unattached detection covers block-local objects.
- c0253 (electrical contracts) adds `circuit.rules`, the main producer of subjects; this change gives it the
  field and the overlay.
- c0247 (connection helpers) creates parts inside helpers: their creation site is the user's call line,
  because the recorder takes the deepest frame in the script folder.
- c0245 (viewer, another branch) consumes `result.subjects`.
- c0257 and c0258 reuse `findings()` and subjects for their stages.

## Risks / Trade-offs

- A build per `load` costs time (about the time of `build --dry-run` plus a write); the example tests stay
  under a second each on the reference design. `load` is cheap to share with a module-level fixture the user
  writes.
- Golden files churn when the render style changes. Mitigation: the style is versioned in the SVG
  (`data-render="fenolite.region.v1"`); a style change regenerates every golden of the repository's own
  examples in the same commit, and the assertion message says when the version differs.
- Creation sites cost a stack walk per object during a build; measured on the largest example before merge.
- Subjects beside issues are two lists to keep aligned; the constructor of `StageResult` refuses a length
  mismatch.

## Open Questions

1. Should `fenolite.testing` be frozen for 1.0 with `fenolite.api`? **Recommended:** yes, its functions
   and records, once c0253 has shipped; marked experimental in `capabilities` until then.
2. Should `assert_render` also compare the viewer's scene JSON? **Recommended:** no for now; SVG is what a
   reviewer reads in a pull request. Revisit when c0245 lands.
3. Should subjects move into the issue object at contract v1? **Recommended:** yes, in c0216, keeping
   `result.subjects` one release as an alias.
4. Is `build.unattached` raised for an unused `Net` that only a rule names? **Recommended:** no: a net named
   by a rule or an interface reached the design; only a net that nothing in the design holds is reported.
5. `--net` next to the existing `--nets`, or `--highlight NET`? **Recommended:** `--net`, as the research
   and `fenolite net` name it; the help text of `--nets` says "labels", that of `--net` "highlight".
