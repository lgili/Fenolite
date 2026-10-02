## Why

Net classes live only in the project file (S-0010, S-0038), and KiCad reads custom rules only when a project file sits next to the board; any rules error then disables every rule with exit 0 (`H-K-TOK-RULES-SILENT`). Yet `.kicad_pro` has no public specification: the developer file-format index has no project page (S-0065), and the manual only says what the file is for (S-0045). Until Fenolite writes it, the c0017 and c0018 writers give no coherent design; `build` (c0011), `check` (c0013) and layout preservation (c0019) need one.

## What Changes

- `backends/kicad/_json.py` (new): an exact JSON codec. Key order is kept and numbers stay text (`JsonNumber`, never a float).
- `backends/kicad/pro.py` (new): `PROJECT_VERSIONS = {9: (3, 4), 10: (3, 5)}`, `read_project`, `apply_project` (classes and assignment into the model), `synthesize_project` from per-target templates, and `update_project`, which edits only managed keys. `proerrors.py` (new) holds the issue codes.
- `backends/kicad/lowering.py`: `lower_netclass` writes a model `NetClass` as a project class entry and warns below a project minimum.
- `backends/kicad/triad.py` (new): `write_triad` always returns `.kicad_pcb`, `.kicad_pro` and `.kicad_dru` together, never `.kicad_prl`.
- Empty projects saved in the KiCad 10.0.6 and 9.0.9 GUIs become CC0 fixtures and the packaged templates; without a 9.0.9 save, the 9 template is derived (design Decision 5).
- Corpus rows (use `project`) for the demo `.kicad_pro` and `.kicad_dru` files at both tags: key-name census and round trips.
- Oracle tests on 9.0.9 and 10.0.6, pinned as c0017 probes: a three-way net-class proof with a canary, patterns read as wildcards and regular expressions (S-0046) with decoys, the board-setup floor, and `.kicad_pro` left untouched by `kicad-cli`.
- `docs/formats/kicad/project.md`; sources S-0065 and S-0066; hypotheses `H-K-PRO-*`, which also answer c0007's question on tuning profiles.

Estimated at 6.5 working days (design, "Budget").

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `kicad-file-backend` (c0009): ADDED codec, synthesis and update, target gating, reading, issue codes, coherent triads, format page.
- `kicad-version-gating`: ADDED "Project file versions"; the closed `FileKind` set is unchanged.
- `rules-model` (created by c0018): ADDED "Net classes lower to the project file".
- `corpus-policy`: ADDED "Project and rules corpus rows" and "Project fixtures saved by the KiCad GUI".
- `kicad-oracle`: ADDED "Net-class rules are enforced by kicad-cli" and "Project files survive kicad-cli runs".
- `backend-protocol`: MODIFIED "Write capability fields" (`lower` joins `operations`).

## Non-goals

- `text_variables`, `page_layout_descr_file` and title-block wiring (c0012).
- Reading or writing `.kicad_prl` (never).
- Synthesising 10.0-only keys such as `tuning_profiles`; they are preserved verbatim.
- `rule_severities` as model data (c0020); preserved verbatim.
- Schematic-side keys, except verbatim preservation (v0.2a).
- The `build` command (c0011) and merging over an existing layout (c0019).

## Evidence level required

- Version pairs: `KICAD-VERIFIED` (9.0.9 and 10.0.6 GUI saves, read back by `kicad-cli`); the 9.0 side stays `INFERRED` under the fallback (`H-K-PRO-VERSION`).
- Net-class enforcement, the bench pattern names and the `min_clearance` floor: `KICAD-VERIFIED` on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`), always with a canary (`H-K-PRO-NETCLASS`, `-MIN`, `-PATTERNS`, `-FLOOR`).
- `.kicad_pro` untouched by `kicad-cli`: `KICAD-VERIFIED` from the runner's changed-file list, no canary needed (`H-K-PRO-PRL`).
- Other pattern characters and forms, assignments, the class chosen among several, and the other three floors: `INFERRED` (S-0046, S-0038, `H-K-PRO-PATTERNS`).
- JSON preservation and update rules: mechanical (unit tests), with the demo round trip as supporting data.

## Impact

- New modules `_json.py`, `proerrors.py`, `pro.py`, `triad.py`; two packaged templates; tests; register and provenance rows.
- No runtime dependency, CLI option or FEN code; model and schemas unchanged. `capabilities` lists `kicad_pro` in `write_kinds` and `lower` in `operations`.
- Depends on c0017 (`write_board`, `LossyWriteError`, `read_drc_report`, `KicadCli.drc`, probes), c0018 (`lowering.py`, `lower_rules`, the `net` condition), c0009 (runner, `read_board`) and c0014 (register checks).
