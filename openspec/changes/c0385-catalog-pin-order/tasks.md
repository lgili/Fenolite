## 1. Evidence

- [x] 1.1 Scan the 100 catalog packages for lead order and body chirality: 51 clockwise numberings, 4
  chiral single-row bodies, 45 without chirality. Read-only cross-check against the KiCad stock footprints
  (S-0018) and the cited top views S-0410, S-0416, S-0422. Proof: design D2; `docs/formats/library/rules.md`
  "Pin order of the catalog lands (c0385)".

## 2. Data fix

- [x] 2.1 Mirror the 55 records about their X axis (pads, graphics with rects as min and max corners, pad
  and slot rotations), version `1.1.0`; remove the 48 waivers they no longer need and give the six kept
  lower-left parts and JST_XH_B4B_XH_A source-specific reasons. Proof:
  `uv run pytest tests/unit/library/test_rules.py -k shipped_catalog -q`.
- [x] 2.2 `uv run python tools/catalog/versions.py --update` (catalog `1.0.2`). Proof:
  `uv run pytest tests/unit/catalog -q -n 2`.

## 3. Rule

- [x] 3.1 `library.pin-order` in `fenolite.library.rules` (error, warning for a plain item with no record),
  run by `library check`; a `library.pin-order` waiver must name an S- or D- source. Proof:
  `uv run pytest tests/unit/library/test_rules.py -q -n 2` (positive controls: SOT-23, SOIC-8, QFN with
  exposed pad, SOT-89, TO-252 and their mirrors; negative controls: zig-zag headers, row, grid, switch,
  two-pad, staggered TO-92, terminal block, turned lands).
- [x] 3.2 Bad fixture `tests/data/library_rules/bad/pin_order.toml` with its `MANIFEST.toml` entry. Proof:
  `uv run pytest tests/unit/library/test_fixtures.py tests/corpus/test_manifest.py -q -n 2`.
- [x] 3.3 `explain.toml` entry, `docs/library-rules.md` row and waiver paragraph, `docs/formats/library/rules.md`
  "Pin order" row, agent guide line in `library-review.md`, `docs/cli-surface.json`. Proof:
  `uv run pytest tests/unit/agent/test_pages.py tests/unit/cli/test_explain_cmd.py -q -n 2`.

## 4. Ripple

- [x] 4.1 Review renderer draws Y down; gallery SVGs drawn again with
  `uv run python tools/catalog/render_footprints.py docs/catalog/previews/c0076-current-gallery.svg --page-size 20`.
- [x] 4.2 `tests/data/catalog/footprints.sha256` and `tests/data/catalog/golden.json` regenerated. Proof:
  `uv run pytest tests/unit/catalog/test_catalog_generated.py tests/unit/catalog/test_golden.py -q -n 2`.
- [x] 4.3 Unit tests that pinned mirrored coordinates pin the corrected ones; the `drawing/0` test compares
  the X-mirror. Proof: `uv run pytest tests/unit/catalog -q -n 2`.
- [x] 4.4 `tests/data/build_bytes.json` measured again (15 builds of five examples), Linux digest of the
  platform-dependent `board_40parts.PcbDoc` kept. Proof: `uv run pytest tests/unit/test_build_bytes.py -q -n 2`.
- [x] 4.5 Net-role reference boards and role benches: renumber the synthetic `Roles_Sense_Amplifier`,
  `Roles_HalfBridge_Driver` and `Roles_Cell_Monitor` pins by the mirror map so their copper keeps its
  functions (design D7); tests name the new pad labels. Proof:
  `fenolite-heavy uv run pytest tests/unit/roles tests/unit/routing tests/unit/cli/test_route_cmd.py -q -n 2`.
- [x] 4.6 Altium kit samples `routed` and `board6`: route `LED_DRV` and `VIN` to the corrected DIP-8 pins
  (design D8); re-pin the four `kit/` digests of `FORMER_DOCUMENTS`. Proof:
  `uv run pytest tests/unit/verify/kit tests/unit/backends/altium/test_lower_build_spec.py -q -n 2`.
- [x] 4.7 Plane-bench fixtures that place `SOIC_8`: `tests/data/specctra/c0107_before_planebench_norules.dsn`
  (re-recorded, only the P3 pin lines differ) and `tests/data/kicad/routing/planebench_t9_*_filled.kicad_pcb`
  (written again on local KiCad 10.0.6); `tests/unit/view/test_roles.py` names the renumbered gate pads.
  Proof: `uv run pytest tests/kicad/routing/test_fanout_oracle.py tests/unit/test_fanout_fixtures.py
  tests/unit/view/test_roles.py tests/unit/backends/specctra/test_dsn.py -q -n 2`.
- [x] 4.8 CHANGELOG line under `## [Unreleased]`, marked breaking for land patterns.

## 5. Closure

- [x] 5.1 `uv run python tools/gen_agent_guide.py` leaves no change; ruff, format, pyright, residue pass;
  `make test-fast` through `fenolite-heavy`: 23201 passed, the failures are those of 5.2 and the ones fixed in 4.7.
- [x] 5.2 New native Altium kit run for the four samples that place `DIP8_Microchip_P` (decision of
  2026-11-05: the 25 `ALTIUM-VERIFIED(kit)` rows are NOT lowered; another session records a new run in the
  Altium VM). The run `2026-10-13-87c930fa` is stale for these steps, and only these:

  | Sample | Steps to run again |
  | --- | --- |
  | `flat` | K1.1, K1.2, K1.5, K1.6, K1.8, K2.1, K3.1, K3.2, K8.2, K8.3 |
  | `libs` | K1.3, K1.4, K2.5, K9.1, K9.2 |
  | `routed` | K2.3, K4.1, K4.2, K4.3, K4.4, K6.1, K7.1, K7.2 |
  | `board6` | K2.4, K5.1, K5.2, K5.3, K5.4, K5.5 |

  These are 29 steps, carrying the 25 rows: H-A-WRITE-SCHLIB, H-A-WRITE-PCBLIB, H-A-WRITE-SCHDOC,
  H-A-WRITE-PCBDOC, H-A-PH-CHECKSUM, H-A-PH-ZERO-FIELDS, H-A-PH-NO-CACHE, H-A-PH-LAYOUT, H-A-SCHLIB-UPDATE,
  H-A-PCBX-STACK, H-A-PCBX-VIASPAN, H-A-PCBX-TEXT, H-A-PCBX-KEEPOUT, H-A-PCBX-REPOUR, H-A-OUTJOB-OPEN,
  H-A-OUTJOB-RUN, H-A-OUTJOB-RUN-2, H-A-SCHDOT-STRINGS, H-A-RULE-KINDS, H-A-RULE-SCOPE, H-A-KIT-RESAVE,
  H-A-KIT-COMPILE, H-A-KIT-REPOUR, H-A-KIT-DRC, H-A-KIT-SCRIPT. H-A-KIT-SCRIPT passes only when the script
  does every scripted step of the run. The samples `tree`, `pour`, `pour4` and `slots` are unchanged,
  and their steps keep the old run.

  Build the kit from this branch's commit:

  ```
  git fetch origin fix/c0385-catalog-pin-order
  git switch --detach origin/fix/c0385-catalog-pin-order
  uv sync --all-extras                      # the pour samples need the geo extra (exit 6 without it)
  uv run fenolite kit build --out kit --dry-run --json
  uv run fenolite kit build --out kit --confirm --json
  ```

  `kit build` writes all eight samples into one kit; it cannot build only some of them. The folders
  `kit/flat`, `kit/libs`, `kit/routed` and `kit/board6` are the ones the steps above use. Seed 0 and
  timestamp `2026-01-01T00:00:00Z` are the defaults, so the build is byte-identical for everyone. Built
  on this commit, the kit digest was `9d7e289915e57060ee95b24dd4b02428e6d35e2dfe95fce1df4573aee5af88ba`,
  and the sample digests began `flat` d06a59a54729, `libs` d49ef8ad77b4, `routed` 3fc10dcbff9b and
  `board6` 954b4d4d80fb.

  After the run in Altium, follow `docs/altium-kit.md`:

  ```
  uv run fenolite kit verify kit --json
  uv run fenolite kit record kit --out . --dry-run --json
  uv run fenolite kit record kit --out . --confirm --json
  ```

  Then set each of the 25 rows to the label and result text that `result.rows` names. Regenerate with
  `uv run python tools/gen_altium_graduation.py` and `uv run python tools/gen_evidence_matrix.py`.
  `uv run fenolite kit status --json` must list no stale row. Proof:
  `uv run python tools/gen_altium_graduation.py --check` passes, and so do
  `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/backends/test_graduation.py
  tests/unit/test_evidence_matrix_page.py tests/unit/cli/test_capabilities_altium.py -q -n 2`.
  Those six tests and that lint step fail until the run is recorded.
  Done 2026-11-05 (S-1590): a Claude agent ran the kit built at `7e0c4ba8` (kit digest `9d7e2899…`) in
  actual Altium Designer 24.5.2.23 at the maintainer's request (delegation of 2026-11-04), recorded as
  `2026-11-05-e28d0bb1` (archive `e28d0bb1…`, 2087805 bytes, kept outside the repository). The `tree` steps K1.7
  and K2.2 were run too, because `H-A-KIT-COMPILE`, `H-A-KIT-RESAVE` and `H-A-WRITE-SCHDOC` name them. `kit verify`:
  31 pass, 0 fail, 19 skipped (`pour`, `pour4`, `slots`, K8.1). 24 of the 25 rows and `H-A-SCHX-TREE` carry the
  new label; `claims.KIT_SOURCE` names the new run. `H-A-KIT-SCRIPT` was skipped: the script's `Append` on the
  missing `results/script.log` raises `EInOutError` and the script stops, so no `script.log` exists. By the
  coordinator's decision of 2026-11-05 (maintainer's delegation of 2026-11-04), which replaces the "NOT lowered"
  note above for this row, it is set back to `INFERRED`; the script fix and a K2 rerun are c0389 task 6.1.
  `kit status` lists no stale row; `gen_altium_graduation.py --check` passes; the four proof files, plus
  `tests/unit/test_altium_rows.py` and `tests/unit/verify/kit`: 265 passed.
- [ ] 5.3 Full validation (`make check`) on the pushed commit in GitHub CI, after 5.2.
- [x] 5.4 `tests/kicad/roles/test_critical_drc.py::test_critical_routes_pass_drc[half_bridge]` failed once
  on local KiCad 10.0.6 before the rebase onto `cac/lote-16`. It has one `unconnected_items`. After the
  rebase it passes on the base `7ced9816` and on this branch, one focused run each through `fenolite-heavy`
  with KiCad 10.0.6. The failure did not come back. The base brings c0332's exact neck cut of pours, and
  this test refills the zones in its gate.
