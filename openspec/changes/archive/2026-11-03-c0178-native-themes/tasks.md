## 0. Entry check

- [x] 0.1 Read c0176's and c0177's specs, `docs/formats/kicad/schematic.md` and `libraries.md`, and `LEGAL.md` block A. Note under this task, with the date, the maintainer's choice of colour source and the facts the theme reader needs. Proof: `openspec validate c0178-native-themes --strict --no-interactive`.
  - 2026-10-25: asked in the session, the maintainer chose "a palette in KiCad's manner, plus the user's own theme". The other options were transcribing KiCad's built-in values, which block A forbids for GPL sources, or the user's theme alone.
  - The theme facts come from S-0813 and S-0814: the form of the theme file, the key names, the `colors` folder and the settings folders. The placement rule comes from `schematic.md` (`H-K-SCH-PINFRAME`, `H-K-SCH-PINFRAME-ORDER`).
  - This change is on `c0177-schematic-viewer` (`39b7e7a`). Proof passed.

## 1. Themes

- [x] 1.1 Write `docs/formats/kicad/color-theme.md`, add its sources and the hypothesis `H-K-THEME`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-25: proof passed (with `test_evidence_matrix_page.py`: 70 passed).
- [x] 1.2 Add `fenolite.view.themes` with the two palettes, the theme per backend, the theme file reader and the folder lookup (scenarios "Each backend gets its palette" and "An authored theme file"). Proof: `uv run pytest tests/unit/view/test_themes.py -q`.
  - 2026-10-25: proof passed (8 tests).

## 2. KiCad schematics

- [x] 2.1 Add `fenolite.view.kicad_schematic` (scenarios "Counts and pin points of a KiCad sheet" and "Wires carry their label's net"). Proof: `uv run pytest tests/unit/view/test_kicad_schematic.py -q`.
  - 2026-10-25: proof passed (6 tests). On three sheets, every visible pin's line starts at `schlayout.pin_point`, which `test_pin_frame_oracle.py` checks against `kicad-cli`. Every `.kicad_sch` under `tests/` builds a scene without an error.
- [x] 2.2 Mark `.kicad_sch` as viewable (scenario "A lone KiCad sheet"). Proof: `uv run pytest tests/unit/view/test_project.py -q`.
  - 2026-10-25: proof passed.

## 3. Page and command

- [x] 3.1 Theme the page (scenario "The page reads the theme"). Proof: `uv run pytest tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed.
- [x] 3.2 Add `--theme` and the KiCad sheet scenes to `fenolite view` (scenario "A theme file on a KiCad board"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view tests/consistency -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-25: proof passed (444 passed, 24 skipped). The skill folder holds fewer than 150 000 bytes after the paragraph of the guide page `files` was shortened.
- [x] 3.3 Review in a browser a KiCad project (`tests/data/acceptance/board_40parts_t10/` or the schematic fixtures) and the Altium test projects. Record the date, the browser and what was checked. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on exported standalone pages, read from screenshots:
    - **`board_40parts_t10`:** the navy board with red and blue copper and the KiCad palette's note.
    - **`board6.PcbDoc`:** the black board with the Altium palette.
    - **`flat.kicad_sch`, KiCad palette:**
      - the A4 paper with its frame, zones and title block;
      - the dotted grid and green wires with a junction;
      - dark red symbols on pale yellow bodies;
      - global labels as flags;
      - stroke texts;
      - the power symbols.
    - **`flat.kicad_sch`, an authored dark theme file:** every role took the file's colours.
  - No defect was found that needed a change of code. One note was misleading: the Altium board's note offered `--theme`, which only applies to KiCad documents, and was corrected.
- [x] 3.4 The maintainer reviews a KiCad project of their own, with and without their KiCad theme. Proof: the record under this task.
  - 2026-11-03: after selecting Fenolite-authored inputs, the maintainer reviewed the actual default/authored PCB and schematic comparison packet and replied “Revisei e aprovo a correspondência de cores”. All30manifest files were reverified unchanged. See `maintainer-colour-review.json` for exact packet, theme and exporter hashes. This closes only the visual review; exact-head CI and independent native/electrical gates remain pending.
  - 2026-10-25: WAITS on the maintainer. `H-K-THEME` stays open until a theme file that KiCad wrote has been read.

## 4. Docs and closing

- [x] 4.1 Update `docs/viewer.md` and the `view` section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/agent -q`.
  - 2026-10-25: proof passed (81 passed, 12 skipped).
- [x] 4.2 Run the fast gate. Proof: `make check-fast`.
  - 2026-10-25, Linux container: lint, format, pyright and residue clean; 13 871 passed, 34 skipped. The full gate is left to CI.
- [x] 4.3 Evidence labels. Proof: `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-25: proof passed. The theme file and the KiCad sheet scene are `INFERRED`, and no other label changes.
- [x] 4.4 Add an entry under `## [Unreleased]` in `CHANGELOG.md` once the version after 0.5.0 is open. Proof: `uv run pytest tests/unit/test_release_record_v05.py -q`.
  - 2026-10-25: the entry is under `## [0.5.0]` of `CHANGELOG.md`, not `[Unreleased]`: by the maintainer's decision of 2026-10-25 the change ships in 0.5.0 (c0171 task 1.15). Proof passed (`tests/unit/test_release_record_v05.py`).
  - 2026-10-25: WAITS on the maintainer (the release guard of 0.5.0). The text is ready: `- **Native looks** (c0178): `fenolite view` draws each document in the look of its tool: KiCad boards and sheets in a palette in KiCad's manner (or the user's KiCad colour theme with `--theme`), Altium boards in a palette in Altium's manner, and Altium sheets in their own colours; KiCad schematics are now drawn — symbols, pins, wires, labels, power symbols, sheets, frame and title block, stroke texts — with net highlight, Navigator and cross-probing.`

## Continuation review — 2026-11-01

No user-owned project/theme comparison was supplied. Local KiCad 9.0.2 is not the maintainer review required by task 3.4.
See `docs/evidence/altium-native-acceptance.md`, "Continuation inventory", for existing reports and exact remaining dependencies. No native, paid-agent or personal-review outcome is claimed.

## Maintainer review source choice — 2026-11-03

The maintainer explicitly selected “Preparar exemplos autorais do Fenolite para minha revisão”
for this pending visual comparison. Original Fenolite-authored examples are the authorized review
inputs. This is source selection only: prepare source-bound CAD/viewer comparisons and retain
the complete original review checklist. The maintainer has not yet reviewed or approved those
comparisons; the human-review task remains unchecked. Preparation and evidence requirements
are recorded in `docs/evidence/native-viewer-maintainer-review-plan.md`.

- [x] 3.4a Prepare an external source-bound Fenolite-authored comparison packet with actual viewer export, original input hashes, criterion checklist and precise native handoff. Keep missing native captures/theme creation/F0.5 measurements explicit; source choice is not human acceptance. Proof: export dry-run/exact confirmation, fixture provenance and packet manifest. The parent human-review task stays open.

  - 2026-11-03 partial preparation: source bfda2ac4 has local standalone candidate/default exports and exact native handoff;39focused controls passed. The real KiCad-written authored theme (c0178) and nativeF0.5 drawing (c0180) are missing, so this preparation and parent human-review task remain open. No UI/configuration or native outcome was invented.

- [x] 3.4b Investigate official installed KiCad10 CLI/IPC headless theme persistence without GUI, user configuration changes or GPL imports. If unsupported, record version-bounded primary facts, actual CLI discovery and exact native GUI handoff; do not manufacture a KiCad-written file or tick3.4/3.4a. Proof: CLI version/help receipt, primary API/manual references and strict spec validation.

  - 2026-11-03: four isolated KiCad10.0.6 CLI discovery subprocesses exited0. Official primary IPC scope confirms9/10 needs GUI; no supported headless theme-persistence path was established. No GPL import, native UI, theme file, themed viewer export or maintainer outcome is claimed. Exact GUI creation/automatic-save/capture handoff prepared externally. S-1298 facts;3.4/3.4a remain open.

Native preparation2026-11-03: actual isolated KiCadGUI10.0.6 authored/persisted the theme;4native matched captures,4actual standalone viewer dry/exactconfirm exports fromclean11bfefd0 and5embedded RGBslots verified.10originalinputs andnativeJSONSHA unchanged. External30filepacket manifest and all links/digests verified; no native JSON/vendorpalette/CAD/screenshots copied into core. Native/browser limitations and launch recovery are explicit in native-gui-preparation-proof.json. Human3.4 and requiredCI remain open. The separate c0180F0.5 drawing is outside this c0178preparation and stays pending in its own tasks.


## Scoped implementation closure — 2026-11-03

The maintainer clarified that problematic geometry was already outside this
closure CI batch before the run. Close only this specification’s implementation
on tested source 985f59a1d01a612b2eac0219243199896c24075a and reviewed
archival documentation. Run 41708879698 remains FAILURE: the27known c0332
geometry failures are DEFERRED_NOT_PASSED, not passed tests. KiCad9 and all
five unit jobs succeeded. The relevant KiCad10 module results are inferred
from complete unfiltered collection and the exhaustive -ra non-pass report;
no nominal PASSED line or green KiCad10 job is claimed.

`scoped-ci-985f59a1.json` binds the exact tests, explicit KiCad9 positive
lines, complete log hashes, reused fast proof and existing scoped records.
The isolated runtime/tests/tools/configuration remain byte-identical to985;
this does not validate later CAC runtime, close c0355 or replace subsequent
integration CI. Existing authored/native/default-map proofs and limitations
remain intact. No suite, native CAD test or CI rerun was started for archive.

The already recorded special gate is verified, without asking for a new
review: actual maintainer approval. Its exact record and scope are bound in the
portable receipt; original limits and no-results statements remain intact.
