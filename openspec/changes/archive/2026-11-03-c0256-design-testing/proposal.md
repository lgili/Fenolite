## Why

A Fenolite design is a Python script, but its author cannot test the circuit as code is tested: a test
cannot ask "is U1's VDD on C5's net?" without parsing envelopes, a layout change is never compared with a
reviewed picture, a `Part` or `Net` created and never added disappears silently, and circuit findings
(c0253) name their subjects only in the free text of `where`, so the viewer cannot select them.

The research of 2026-10-29 (`docs/research/circuit-as-code.md`, section 14, core change K) takes three
concepts from public documentation: typed diagnostics linked to the offending item and visual snapshot
tests in CI (tscircuit), and a report of objects created but never attached, with file and line (JITX).

## What Changes

- **`fenolite.testing`** (new package, standard library only, no pytest import): `load(path)` builds a
  design script in a private temporary folder through `fenolite.api.run("build", ...)` and returns a
  `TestDesign` (also from `instantiate(block, **params)` for one c0251 block) with `net(name)`, `ref(ref)`, `connected(a, b, *, copper=False)`, `findings(pattern)` and
  `close()`. `findings` runs only the tool-free stages of `check`, so no `kicad-cli`, corpus or KiCad
  library is needed.
- **Golden renders.** `assert_render(path, golden, *, net=None, region=None, layers=None)` draws the
  model render of `render --region`/`--net` in memory, compares bytes with a committed golden file, and
  on a difference raises `AssertionError` with an element-level diff (added, removed, changed elements by
  their `data-*` keys) and the exact `fenolite render` line that regenerates the golden file. It never
  writes; the golden file is written by `render --confirm`, reviewed in git.
- **`fenolite render --net NAME`** (repeatable): the Fenolite-drawn render of the whole board, or of
  `--region`, with the copper of the named nets drawn in full colour and every other item dimmed, into
  `DIR/net-<name>.svg`. `render` with `--region` or `--net` also accepts a `design.py`, built in memory as
  `build --dry-run` does.
- **Finding subjects.** `StageResult` gains `subjects`, aligned with its issues, and the `check` result
  gains `result.subjects`: for each issue that names model entities, `{issue, items}` with each item's
  `kind`, model `id` and `name`. The envelope's issue object is unchanged. The check overlay selects a
  finding's items by id first and by name second.
- **Unattached objects.** A build reports `build.unattached` (warning) for each `Part`, `Net` or
  `Interface` that the script created and that never reached the design, with `where` =
  `<script>:line:<n>` of its creation.

Depends on: c0253 (the `circuit.*` stage whose findings carry subjects) and the steps before it
(c0246 to c0252). Implemented seventh in the batch, after c0254 and c0255.

## Non-goals

- No pytest plugin, fixture or entry point: the helpers are plain functions that raise `AssertionError`.
- No raster comparison, no tolerance on pixels: golden renders are canonical SVG text, compared exactly.
- No `kicad-cli` render in `assert_render`; the plots of `render --svg/--png` stay review views.
- No change to the envelope's issue object (`{code, severity, message, where, hint, retryable}`); folding
  subjects into it is left to the contract v1 (c0216).
- No usage-example harness for catalog devices (atopile's tested examples); a later change may add one.

## Evidence level required

- `fenolite.testing` reads: the evidence of the build and of each stage it runs, unchanged; the helpers
  add no claim of their own.
- Net and golden renders: `INFERRED`, the evidence of `analysis.region` today; the bytes are
  deterministic (`H-G-RENDER-DETERMINISTIC`, registered by this change).
- `build.unattached`: `INFERRED`, measured on authored scripts.

## Impact

- New: `src/fenolite/testing/`, `docs/testing.md`, `examples/testing/`, `tests/unit/testing/`.
- Changed: `cli/cmd_render.py`, `cli/_region.py`, `analysis/region.py`, `checks/stages.py`,
  `cli/cmd_check.py`, `view/check_overlay.py`, `cli/_script.py`, `dsl/part.py`, `dsl/interfaces.py`,
  `lens/build.py`, the import-graph test, `explain.toml`, `docs/dsl.md`, `docs/exports.md`,
  `docs/cli-contract.md`, `docs/viewer.md`, the guide pages `checks` and `design-script`. Full list in
  `design.md`.
- Size: about 6 design-days.
