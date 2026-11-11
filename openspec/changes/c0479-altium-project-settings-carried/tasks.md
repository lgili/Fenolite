# Tasks: c0479-altium-project-settings-carried

- [x] 1.1 `prjpcb.carried_settings` and the `carried` merge of `write_prjpcb`, with unit tests.
  - Proof: `uv run pytest tests/unit/backends/altium/test_prjpcb_carried_c0479.py -q`
- [x] 1.2 Carry the settings from `drawing_of` through the root sheet's carrier into `ProjectSheets.project`
  and the written project (`convert.schematic`, `drawn_read`, `drawn.lower_drawn`, `project.write_project`),
  with a conversion test and a `CHANGELOG.md` entry.
  - Proof: `uv run pytest tests/unit/backends/altium/test_prjpcb_carried_c0479.py tests/unit/backends/altium/test_drawn_fidelity_c0470.py tests/unit/convert/test_schematic_c0470.py -q`
- [x] 1.3 Variations of a carried project variant name the written components (`retarget_variants`,
  `ProjectSheets.paths`), with unit and build tests.
  - Proof: `uv run pytest tests/unit/backends/altium/test_prjpcb_carried_c0479.py tests/unit/backends/altium/test_drawn_altium.py -q`
- [x] 1.4 A net label of an Altium source stays a net label on the way back from KiCad
  (`drawn.written_kind`), with a unit test.
  - Proof: `uv run pytest tests/unit/backends/altium/test_prjpcb_carried_c0479.py tests/unit/convert/test_schematic_c0470.py tests/unit/backends/altium/test_drawn_carrier.py -q`
- [x] 1.5 Maintainer board round trip (private, codes and counts only): the built and converted projects
  compile in Altium 24.5 with the source's messages.
  - Result (2026-11-11, Altium 24.5.2.23): the source, the project built from the imported Python and the
    project converted back from KiCad each compile with the one message "Compile successful, no errors
    found", the same components and nets, and the same net names.
