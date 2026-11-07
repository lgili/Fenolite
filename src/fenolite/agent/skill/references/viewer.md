---
topic: viewer
title: Viewing boards and reviewing findings
summary: Drawings, findings and reviewed actions.
---

# Viewing boards and reviewing findings

A person uses the viewer to inspect a drawing and its findings. The CLI reply gives an agent the same
counts and evidence without opening a browser.

For more than counts, `net`, `pads`, `region` and `neighbors` (pages `routing`, `placement`) read any
KiCad board. To look at a board or an Altium sheet, or at every one of a project, without its tool:

```fenolite-cmd
fenolite view blink/altium/blink.PrjPcb --json
fenolite view blink/altium/blink.PrjPcb --doc blink.SchDoc --json
fenolite view blink/build/blink.kicad_pcb --export blink/views/board.html --dry-run --json
fenolite view blink/build/blink.kicad_pcb --check checks.json --report conversion.json --report fabrication.json --json
fenolite view blink/build/blink.kicad_pcb --serve --run-timeout 900 --no-browser --port 0
fenolite view blink/build/blink.kicad_pcb --serve --no-run --no-browser
fenolite view blink/build/blink.kicad_pcb --serve --allow-actions --no-browser
fenolite view blink/build/blink.kicad_pcb --serve --edit --no-browser
fenolite view blink/build/blink.kicad_pcb --roles run --export blink/views/roles.html --dry-run --json
```

`view` replies with the project's documents and a summary of one board, or of the one `--doc` names;
`--compare OLD` draws what changed since OLD (a board or sheet) and counts it in `result.compare`; `--variant NAME` shows an Altium variant; `--check FILE|run` draws `check` findings and counts them in `result.check`; `--select REF` opens at a part or net; `--marks FILE` lists a person's review marks (`fenolite.review.v0`) in `result.marks`; `--theme` takes a KiCad colour theme; `--export` plans one HTML page that a person opens, and `--serve`
(for a person, not an agent) serves it live. A served page can run `check`, `analyze`, `ready` and
`equivalent` itself, read-only, one at a time, stopped after `--run-timeout SECONDS` (600); `--no-run`
serves recorded results only, and `result.serve.runs` counts the runs by final state.
`--allow-actions` lets the person write through the page: fill, tidy, silk, test points, DRC waivers,
moves, exports and BOM, each a reviewed plan confirmed with `--confirm --plan`; `result.serve.writes`
lists the receipts, and `fenolite restore` undoes one. `--roles FILE|run` draws the net roles of `fenolite
roles BOARD --check` on each board (role colours, loops, Kelvin pairs, role findings) and counts them in
`result.roles`; a served page with `--allow-actions` can confirm inferred roles as a reviewed plan.

`--edit` aliases `--allow-actions`. A loaded build/sync conflict shows base, code and CAD values in
Properties. **Take code** or **Take CAD** plans a build from its bound source; review the source execution
context, all inputs and writes in the plan dialog, then confirm or cancel. A changed source needs a new
build reply. Static pages retain the copyable take commands.

`result.review` and the page's Review panel distinguish not-run, passed, failed and limited stages.
`--report FILE` loads a recorded convert/export reply, once per command; use `--check` for checks.
Loading does not run the operation. Missing/mismatched input hashes remain historical and limited;
a matching hash binds only the named document. Original hints and Locate support reviewing findings,
not marking them fixed. Export generation alone does not attest successful readback or fabrication readiness.

## Route proposals

After the critical routes and power copper, inspect the remaining connections with `--proposals run`
or load a saved proposal reply with `--proposals FILE`. Candidate facts stay `INFERRED` unless a named
check supplies stronger evidence. There is no score or automatic selection. With `--allow-actions`,
the person can accept or reject a candidate through a reviewed plan; page `board-routing` covers the
CLI decision and replay commands.

```fenolite-cmd
fenolite view blink/build/blink.kicad_pcb --proposals run --export blink/views/proposals.html --dry-run --json
```

An edit-conflict finding keeps its two copyable `build --take ... --dry-run` command lines in the
inspector. Copy one to the terminal to review its plan; selecting the finding runs neither command.
Finding subjects remain listed, and a role finding can locate the pads of its named group.

KiCad inter-sheet reference text uses the actual owning project and sheet instance. With references
enabled, repeated sheets have explicit logical instance document IDs: choose one with `--doc`.
An ambiguous physical child path refuses; it never selects the first instance. Project/hierarchy
changes invalidate scene caches and live views, and missing inputs keep the last good scene with an
error. Native visible reference text without an explicit field pose refuses instead of guessing.


## Layer presentation order

In the viewer's Layers panel, **Order layers** changes a draft with Move up/down or `Alt+↑` / `Alt+↓`.
Apply saves it for that document/source hash in this browser; Cancel or Escape discards it. Reset to
default followed by Apply restores **Default viewer order**, a viewer fallback rather than a universal
Altium order. Browser storage failures keep the choice only for this page session. Selection, visibility,
opacity, source bytes and drawing order do not change; no empty native layer is invented.

Read next: `files`, `checks`, `board-routing`.
