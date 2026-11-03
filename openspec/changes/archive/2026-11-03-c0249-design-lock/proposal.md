## Why

Every reference designator in a Fenolite script is typed by hand. Repeated blocks number them by
arithmetic (`f"U{base + 1}"` in `examples/yardstick/design.py`). Adding a part means finding a free number, and a
generated block cannot know which numbers the rest of the design took. Part picks (c0254) and pin choices
(c0257) will also need a place where a choice, once made, stays made until someone reviews a change. The
research page (`docs/research/circuit-as-code.md`, section 3 and core change C) proposes a design lock:
identity is the hierarchical path, refs are assigned automatically and recorded, and a release build
refuses to let any of it move.

Fenolite already keys ids and layout on paths (`design-model`, "Identifier derivation"; `layout-lens`,
"Footprint matching"), and `design.moved()` carries a path across a rename. What is missing is a part
whose path does not contain its ref, and a reviewed file for the refs.

## What Changes

- **Part keys.** A part may be created without a ref: `design.part(device=...)`,
  `design.part(name="pull_sda", device=...)` or `Part(lib_id=..., prefix="R")`. Its path segment is
  `name`, else the explicit ref, else its reference prefix, which must then be free in its container.
  Explicit refs keep working, and their paths are unchanged.
- **Automatic refs.** Refs are assigned per prefix (from `prefix=`, the device's `ref_prefix`, or the
  catalog symbol), in a documented natural order of paths, using the lowest free number. A ref in the lock
  is kept. An explicit ref always wins.
- **The lock file** `<script stem>.lock` beside the script (schema `fenolite.lock.v0`, canonical TOML)
  holds `[refs]` (path → ref) and the reserved sections `[picks]` (c0254) and `[pins]` (c0257). A
  non-empty reserved section is refused until its change lands. Hand edits are honoured.
- **Written through plan and confirm.** `fenolite build` plans the lock as one more write, only when its
  content changes and only for a design that has an automatic ref or already has a lock. Designs with only
  explicit refs build byte for byte as before and get no lock.
- **`design.moved()`** carries lock entries from the old path to the new one. An entry whose path is gone
  is released with a warning.
- **`build --frozen`** refuses any change to the lock (refs, picks, pins) with exit 7 and the new code
  `FEN-7004`, listing every change. Nothing is written.
- `result.lock` reports the file, whether it is written, and each change with its reason.

## Non-goals

- No hierarchical numbering scheme (such as `U101` per block); c0251 may add one on top of the lock.
- No part picks or pin choices: only their sections and the frozen comparison.
- No back-annotation of refs edited in KiCad; c0250 owns edits made in the CAD tool.
- No renumbering command. Deleting the lock, or editing it, renumbers.
- No change to ids: they stay derived from paths, never from refs.

## Evidence level required

- Assignment, lock reading and writing, aliases and frozen comparison: `INFERRED`, unit-tested
  (hypothesis `H-G-LOCK-REFS`).
- Builds with automatic refs: `INFERRED`. In CI, the KiCad job runs ERC on the lock example and reports no
  duplicate or unannotated reference.

## Impact

- New: `src/fenolite/dsl/lock.py`, `examples/lock/`, tests under `tests/unit/dsl`, `tests/unit/cli`,
  `tests/unit/lens` and `tests/kicad/build`.
- Changed: `dsl/part.py`, `dsl/module.py`, `dsl/design.py`, `dsl/convert.py` (`to_model(..., refs=)`),
  `cli/cmd_build.py` (`--frozen`, `--lock`), `cli/errors.py` and `explain.toml` (`FEN-7004`),
  `lens/build.py` (codes), `docs/dsl.md`, `docs/lens.md`, `docs/cli-contract.md`, the guide pages
  `design-script.md` and `files.md`, `CHANGELOG.md`.
- Depends on: c0248 (device `ref_prefix`, `design.part`). It is implemented together with c0248. c0250,
  c0251, c0254 and c0257 build on it.
- Size: about 5 design-days.
