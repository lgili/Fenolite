# Pending authored native/viewer comparisons

On2026-11-03 the maintainer selected “Preparar exemplos autorais do Fenolite para minha revisão”
for the five outstanding visual-review inputs. This authorizes preparation with original
Fenolite-authored files. It is not approval of any image, geometry, theme, native outcome or spec.

| Spec/task | Required material and review |
|---|---|
| c0177/2.4 | Authored Altium schematic project, actual Designer comparison and live viewer; text size, power ports, ports, sheet entries and title block. |
| c0178/3.4 | Authored KiCad project with and without an authored theme written by KiCad, compared with its native display. Keep palette provenance explicit. |
| c0180/2.4 | Authored drawing and actual Designer comparison covering PartF/F0.5. Keep the separate Draftsman fact and writer gates pending. |
| c0181/3.3 | Authored board compared with Designer, including layer tabs and mask openings. |
| c0186/2.2 | Authored variant compared with Designer, with fitted/not-fitted identities and the displayed variant explicit. |

For each packet record the exact input and viewer-output hashes, current renderer/core commit,
actual CAD build and selected document/view/variant/theme. Use the approved available Altium
Designer24.5.2.23 scope; do not relabel it26.5. Keep original input hashes and report any native
save separately. Capture only the owned test documents and their relevant native canvas/panels.
Theme inputs must be original and their creation provenance recorded; no vendor palette is copied.

Present the complete checklist and observable warnings or limitations beside the comparisons.
An automatic export, successful screenshot or source-selection reply does not count as the
maintainer's visual review. Record approval or refusal only after the maintainer sees the actual
packet. Preserve every native, focused-test and exact-head CI gate independently.

## Local authored preparation, source bfda2ac4

Ten standalone viewer pages were written through actual reviewed dry-run/exact confirmation; all input hashes remained unchanged.39 focused viewer/writer controls passed. The packet includes the existing authored schematic/sample hierarchy, an authored10/14point titleblock sheet, the renamed-layer/4mil-mask board and Default/Lite variant. Native screenshots, live comparison and all five human decisions remain pending. See `native-viewer-authored-preparation.json` for bounded counts and missing material.

The KiCad default board/schematic pages exist, but no actual KiCad-written authored theme is available yet; no themed output is fabricated. Draftsman parser/writer controls have standalone pages, explicitly labelled candidates; the actual nativeF0.5 drawing does not yet exist. A fresh routed author board and exactF0.1/F0.2/F0.5 handoff are prepared; its11written segments/7vias come from four copper intents. The unsupported TransmissionLineTableData notice remains visible in the reader control. These two preparation tasks remain incomplete until their real native inputs arrive. No CAD UI/session/configuration was changed.

## c0178 official headless investigation

The recorded KiCad10.0.6 discovery set used four version/help subprocesses, all exit0, with an isolated KICAD_CONFIG_HOME. The CLI exposes selection of existing export themes, not creation/persistence. Official IPC documentation limits9/10 to a running GUI; the11 headless feature was not tested or substituted. No pcbnew/GPL module was imported, no GUI/session was operated and no theme/themed viewer page was manufactured. The isolated discovery created two temporary configuration files; no user configuration change was requested.

Native handoff: on a separate owned configuration, create the original named theme through Colors/New Theme, enter and document original RGBA roles, close/reopen preferences to verify native persistence, and preserve exact JSON/version/hash and board/schematic captures. New themes inherit the previous palette; identify those inherited roles, keep the configuration external and copy no vendor palette into core. Only after the real file exists, export both viewer documents with that theme through reviewed plans. c0178/3.4 and3.4a remain open. Facts and limits: S-1298 and `docs/formats/kicad/color-theme.md`.

## c0178 preparation available

The external native-theme review packet now has actual KiCad10.0.6 GUI default/authored board and
sheet captures, a GUI-written persisted theme and four standalone viewer exports bound toclean
11bfefd0. Its30-filemanifest is pinned in c0178 native-gui-preparation-proof.json. Source ten-input
hashes and theme bytes were unchanged. This is colour-only preparation on the authored FULL
fixture, not a PCB quality/electrical gate. Inherited palette data stays external. Browser file-URL
preview was rejected by policy; static links/hashes and embedded palette mappings passed.
Human review remains pending; no source choice was converted into approval.

## c0178 maintainer decision — 2026-11-03

The maintainer reviewed the actual default/authored PCB and schematic colour packet and replied
“Revisei e aprovo a correspondência de cores”. The30manifest files were reverified unchanged;
`c0178-native-themes/maintainer-colour-review.json` binds the approval to the packet, exporter and
native-theme hashes. Task3.4 is complete. Historical preparation receipts retain their then-pending
review status. Exact-head CI and every independent electrical/native gate remain pending.
