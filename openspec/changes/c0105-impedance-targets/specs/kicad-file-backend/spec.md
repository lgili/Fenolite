## ADDED Requirements

### Requirement: Tuning profiles for impedance targets
`fenolite.backends.kicad.tuning.apply_profile_keys(text, design, *, target, issues=None) -> str` SHALL write the impedance targets of the design ("Impedance targets in the rules model") into a project text as KiCad 10 tuning profiles, and `write_triad` SHALL call it after `pro.apply_sheet_keys`, with the same `issues` (an addition to "Generated projects are coherent"). For target 10, this requirement takes the key path `/tuning_profiles/tuning_profiles_impedance_geometric` with every path below it, and `/net_settings/classes/*/tuning_profile`, out of the template-value, added-path and keep rules of "Project files are synthesised and preserved".
- For target 9, and for a design without targets, the text MUST be returned unchanged; the keys stay in `pro.TEN_ONLY_PATHS` ("Project files are gated by target").
- `tuning.lower_profile(target)` MUST give the entry: `profile_name` the target's name; `type` `0` for `single` and `1` for `differential`; `target_impedance` a `JsonNumber` holding the exact text of `ohms`, or `0` when it is empty; `enable_time_domain_tuning` false; `layer_entries`, one object per layer in stack order with `signal_layer`, `top_reference_layer` (the upper of two references, else `""`), `bottom_reference_layer` (the only or the lower reference), `width` and `diff_pair_gap` as integers of nanometres (`0` for a `single` target) and `delay` `0`; `via_prop_delay` `0`; `via_overrides` empty. No other key MUST be written, and no number MUST come from a `float`.
- An entry whose `profile_name` equals a target's name MUST be replaced in place; the other targets MUST be appended, sorted by name; every other entry MUST be kept in place, structurally equal and with its number spellings. No entry MUST be deleted. `tuning_profiles.meta` MUST be kept.
- The class key `tuning_profile` of every class of a target MUST be set to the target's name. When it named another, non-empty profile, `issues` MUST get the warning `kicad.project.profile-reassigned` naming the class, the old name and the new one. The key of a class without a target MUST be kept.
- `kicad.project.profile-reassigned` (warning) MUST be a row of `proerrors.ISSUE_CODES` (an addition to "Project issue codes").

#### Scenario: Two targets synthesised for target 10
- **GIVEN** a design with the single target `SE50` (rows `F.Cu` over `In1.Cu` and `B.Cu` over `In2.Cu`, 0.35 mm) and the differential target `USB90` (row `F.Cu` over `In1.Cu`, 0.2 mm, gap 0.15 mm, `ohms` `"90"`)
- **WHEN** `write_triad(design, name="z", target=10)` runs
- **THEN** `tuning_profiles_impedance_geometric` holds `SE50` then `USB90`, `USB90` has `type` 1, `target_impedance` written `90`, one entry with `width` 200000 and `diff_pair_gap` 150000, the classes `SE50` and `USB90` name their profiles, and every other key path equals the file written for the same design without targets

#### Scenario: Target 9
- **WHEN** the same design is written for target 9
- **THEN** the project has no `tuning_profiles` key and no class key `tuning_profile`, and equals the file written without targets

#### Scenario: Profiles of the user are kept
- **GIVEN** a target-10 project whose profiles are `GUI_50` (named by class `RF`) and `SE50` (width 0.3 mm), and the design of the first scenario
- **WHEN** `write_triad(…, existing_project=text, target=10)` runs
- **THEN** `GUI_50` is kept in place, structurally equal with its number spellings, `SE50` is replaced with width 350000, `USB90` is appended, and the class `RF` still names `GUI_50`

#### Scenario: Class key reassigned
- **GIVEN** the same project with the class `SE50` naming `GUI_50`
- **WHEN** it is updated with an `issues` list
- **THEN** the class `SE50` names `SE50` and `issues` hold one `kicad.project.profile-reassigned` warning naming `SE50` and `GUI_50`

### Requirement: Tuning profiles are read into impedance targets
`read_project` SHALL also return the tuning profiles of the project in `ProjectInfo.profiles`, and `apply_project` SHALL set `RuleSet.impedance` from them (an addition to "Project files are read into the model").
- Each profile named by the class key of at least one class MUST become one `ImpedanceTarget` of those classes, in `classes` order, with an id derived from the profile name: `kind` from `type` (`0` single, `1` differential); `ohms` the exact decimal text of `target_impedance`, `""` for 0; `tolerance_percent` `""`; one `TraceGeometry` per entry, with the non-empty references in stack order, `width` and, for a differential profile, `gap`.
- An entry that is not an object, lacks a key of the written form, has a width or gap that is not a whole number of nanometres, or names a layer that is not a copper layer of the board MUST be skipped with the info `kicad.project.unread-entry`; a profile left without an entry gives no target.
- A profile that no class names, and a class key that names no profile, MUST give no target and no issue. The project text is not changed.

#### Scenario: Written targets read back
- **GIVEN** the files of "Two targets synthesised for target 10"
- **WHEN** they are read with `read_board`, `read_project` and `apply_project`
- **THEN** `RuleSet.impedance` holds `SE50` and `USB90` with the written kinds, classes, `ohms`, layers, references, widths and gap, and `tolerance_percent == ""`

#### Scenario: Malformed entry skipped
- **GIVEN** a project whose profile `SE50` has an entry with `"width": 350000.5`
- **WHEN** it is applied with an `issues` list
- **THEN** that entry is not a layer of the target, and `issues` hold one `kicad.project.unread-entry` info naming `SE50`
