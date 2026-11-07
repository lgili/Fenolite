## 0. Entry check

- [x] 0.1 c0195 is archived, or this change waits for it: its `mcp-server` delta MODIFIES "Commands not exposed",
  which c0195 adds. Note the order under this task. Proof: `openspec validate c0196-mcp-design-and-images --strict --no-interactive`.
  - 2026-10-26: c0195 is open (its optional task 5.4 waits on the maintainer); this change is implemented on a
    branch from `c0195-mcp-server` and archives after c0195. The maintainer accepted every recommended answer
    (design, "Open Questions"; roadmap row 47). Proof passed.

## 1. The edit command

- [x] 1.1 `cmd_edit.py`: the two forms, the file kinds and size, the parse checks, the plan's `result` with the
  diff (scenarios "An exact edit planned and written", "An edit that breaks the script is refused", "An old
  text found twice"). Proof: `uv run pytest tests/unit/cli/test_edit_cmd.py tests/consistency -q`.
  - 2026-10-26: proof passed (11 tests; with tests/consistency and tests/unit/agent 519 passed). The example
    edits a committed script with its own text (no write); the mutation example writes a prepared copy
    (`tests/_cliexamples.py`). A script that would write a file when run is only parsed (`test_script_is_never_run`).
- [x] 1.2 `docs/cli-contract.md` ("## edit"), the tested line of `edit` on the guide page `design-script`, and
  `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-26: proof passed (the generator's check 0); the page `design-script` gains "Edits without an editor".

## 2. The server

- [x] 2.1 `fenolite_edit`: `content` or `edits`, the input file in the state folder and its removal, the opt-in
  `--allow-edit` (scenarios "Edit through the server", "Edit listed only on request", "Edit not listed by
  default"). Proof: `uv run pytest tests/unit/mcp tests/unit/cli/test_mcp_cmd.py -q`.
  - 2026-10-26: proof passed (61 tests). The tool takes `content` or `edits`, never the file arguments; the
    input file is `<state>/mcp-inputs/<sha256>.txt|.json` and is removed after each call; a confirmation with
    another content is refused by the command line (`FEN-4002`); `--allow-edit` lists the tool and
    `--read-only` wins over it.
- [x] 2.2 Images: the PNG rows of a plan or a receipt as image content, the caps, the note of what was left out
  (scenario "A dry run of a render is seen"; skipped without `kicad-cli`, and run in the job `mcp` with it if the
  job installs it, else in `kicad-10`). Proof: `uv run pytest tests/unit/mcp/test_images.py -q`.
  - 2026-10-26: proof passed (2 tests, a fake writer of five PNGs: four sent and the fifth named; an error reply
    carries none), and `tests/kicad/mcp/test_render_images.py` passed with `kicad-cli` 10.0.6 here: the dry
    run of `render --png` at 400 by 300 sends two PNGs whose SHA-256 are the plan's rows, and writes nothing.
    The render test lives under `tests/kicad`, which the job `kicad-10` runs (the jobs that run `tests/unit` have
    no `kicad-cli`).
- [x] 2.3 The official client reads the image content the server sends, in `test_sdk_oracle.py` (a server whose
  backend returns a PNG: the job `mcp` has no `kicad-cli`, and the real render is checked by `kicad-10` in 2.2).
  Proof: the job `mcp` passes in CI.
  - 2026-10-26, OPEN until CI: the local proof passed (3 tests of `test_sdk_oracle.py`, the official client 2.3.0
    reads `type` `image`, `mimeType` `image/png` and the base64 data).
  - 2026-10-26: CLOSED. The job `mcp` passed in CI run https://github.com/lgili/Fenolite/actions/runs/40261423201
    at `e16afa9`, and `kicad-10` with it (the real render of 2.2). The same run failed `unit` on Windows: the
    example of `edit` names a file on the checkout's drive while the suite runs on another, and
    `os.path.relpath` raises across drives; `edit` now shows such a path absolute (`test_path_on_another_drive`).

## 3. Documents and closing

- [x] 3.1 `docs/mcp.md` (the edit option and its risk, the images and their caps), the guide page `recovery`,
  `README.md`, `openspec/README.md`. Proof: `uv run pytest tests/unit/agent tests/unit/test_agent_skill.py -q`.
  - 2026-10-26: proof passed (111 tests; the guide generator re-run for `--allow-edit`). `docs/mcp.md` gives the
    option's risk in bold before its use, the edit tool and the images; residue scan clean.
- [x] 3.2 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
  - 2026-10-26: two entries under Added of `[Unreleased]`.
- [x] 3.3 `make check-fast`. Proof: `make check-fast`.
  - 2026-10-26: exit 0, 14 079 passed, 35 skipped; lint, format, types and the residue scan clean.


## Scoped CI verification and archival — 2026-11-03

c0195 was actually archived first, creating the living MCP server contract.
Its optional personal-client task remains optional and does not block this
change. The maintainer clarified that problematic geometry was already
outside the closure CI batch before the run; apply that existing scope.

In run 41708879698 on exact source
985f59a1d01a612b2eac0219243199896c24075a, official-client MCP job 126171394030
and all five unit jobs completed successfully. This covers the SDK image
content and edit-tool unit proofs. The real-render result is inferred from
the completed KiCad10 job's exhaustive report, not a printed nominal PASSED
line: its command collected all tests/kicad and tests/corpus; this ordinary
single-test module has no skip/xfail condition or collection exclusion;
required-resource mode includes KiCad. The configured -ra report accounts
for all 27 failures, 168 skips and 3 xfails, reaches 100 percent, and includes
neither this module nor an interruption or collection error. The remaining
3992 results passed. Source, test, collector and workflow hashes are bound
to the unchanged tested bytes in the external scoped receipt.

The whole KiCad10 job and complete workflow still FAILED in the separately
excluded c0332 geometry; no job-wide success, geometry acceptance or release
acceptance is claimed here. Existing focused/fast proofs are reused, with
no suite, CAD or CI rerun. All post-source changes in this archival tree are
reviewed OpenSpec/CHANGELOG documentation; runtime, tests, tools and
configuration remain byte-identical to the tested source.
