## ADDED Requirements

### Requirement: Meanders in the DSL
`Design.meander(key, *, track, segment, amplitude, pitch, target=None, match=None, side="left", margin=None)` SHALL record a meander intent that the build resolves, and `dsl.meanders(design)` SHALL return the recorded intents as frozen `MeanderIntent(key, track, segment, amplitude, pitch, target, match, side, margin)` of `dsl/intents.py`, in key order, every length as `int` nanometres. The DSL MUST still import only `core` and `model`, and `to_model` MUST NOT change: meanders are not model objects.
- `track` is the key of a track intent recorded before the call, and `segment` the index `i` of its segment `seg[i]`, from path element `i` to element `i + 1`. `amplitude` is the largest height of a bump from the segment's centre line, and `pitch` the distance between neighbouring legs, centre to centre. `target` is the length the track intent must reach, or `match` names another track intent whose length is the target. `side` is `"left"` or `"right"` of the segment's direction as KiCad displays the board. `margin` is the straight run kept at each end of the segment; `None` means one pitch.
- `DslError` MUST be raised at the call for: a key that does not match the copper key pattern, or that a copper intent or another meander already uses; a `track` that is not the key of a recorded track intent; a `segment` that is not an `int` with `0 ≤ segment < len(path) − 1`, or whose element `segment + 1` is an arc step; an `amplitude` or a `pitch` that is not a positive length; a negative `margin`; both or neither of `target` and `match`; a `target` that is not positive; a `match` that equals `track` or is not the key of a recorded track intent; a `side` other than the two names; a second meander on the same segment of the same track.
- `fenolite.dsl` MUST re-export `MeanderIntent` and `meanders`; "DSL package" lets later requirements add both.

#### Scenario: A meander on a pair
- **GIVEN** the track intents `usb_p` and `usb_n`, each from a pad of `U1` through two points to a pad of `J1`
- **WHEN** `uv run pytest tests/unit/dsl/test_meander_dsl.py -k record` calls `design.meander("n_tune", track="usb_n", segment=1, match="usb_p", amplitude=mm(0.5), pitch=mm(0.4))` and `meanders(design)`
- **THEN** it returns one `MeanderIntent` with key `n_tune`, track `usb_n`, segment 1, amplitude 500 000, pitch 400 000, target `None`, match `usb_p`, side `left` and margin `None`

#### Scenario: Malformed meanders fail at the call
- **WHEN** `design.meander("m1", track="nope", segment=0, target=mm(30), amplitude=mm(1), pitch=mm(1))`, `design.meander("m2", track="usb_n", segment=5, target=mm(30), amplitude=mm(1), pitch=mm(1))`, `design.meander("m3", track="usb_n", segment=1, amplitude=mm(1), pitch=mm(1))` and `design.meander("m4", track="usb_n", segment=1, target=mm(30), match="usb_p", amplitude=mm(1), pitch=mm(1))` are called
- **THEN** each raises `DslError`, the first naming `nope` and the second the segment index

### Requirement: Meanders in a build
`lens.build.build_design` SHALL accept the keyword-only argument `meanders: Sequence[MeanderIntentLike] = ()` and SHALL resolve it with `meander.resolve_meanders` (`manual-copper`, "Meanders from intents") right after `resolve_copper` and before the build checks and `Design.validate()`, with `major` the build's target; `cli/cmd_build.py` SHALL pass `dsl.meanders(design)`.
- An error of `resolve_meanders` MUST make `build_design` return no files, so `build` exits 5 and writes nothing. Its `kicad.meander.*` codes join the `build` envelope unchanged, as "Build issue codes" allows.
- `result.copper.meanders` MUST count the meanders that changed copper; it is an addition that "Copper intents in a build" allows, and the key MUST be absent from the reply of a build without meanders. An Altium build passes the meanders to the KiCad build it runs in memory, and the `kicad.meander.*` warnings and infos of that build pass with its script copper codes.
- The copper guard ("Copper guard before writing") judges the meander's copper with the rest of the board.
- A call without `meanders` MUST behave as before. `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file of a build with meanders, and a second confirmed build of the same script over the first MUST write the same bytes.

#### Scenario: A pair matched in a build
- **GIVEN** the design script that `tests/_meanderdesign.py::pair_script(tmp_path)` writes: `USB_P` and `USB_N` drawn by the script tracks `usb_p` and `usb_n` from `U1` to `J1`, `usb_n` 1.2 mm shorter, and the meander `n_tune` of "A meander on a pair"
- **WHEN** `uv run pytest tests/unit/lens/test_build_meander.py -k pair` builds it with `--dry-run --json` for target 9 and for target 10
- **THEN** the exit code is 0, `result.copper.meanders` is 1, and `length_facts` of the planned board for the target's major gives `USB_N` a total within 10 nm of the total of `USB_P`

#### Scenario: No room stops the build
- **GIVEN** the same design with `amplitude=mm(0.1)`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` hold `kicad.meander.no-room` naming `n_tune`, and nothing is written

#### Scenario: Rebuild writes the same bytes
- **GIVEN** a confirmed target-10 build of the design of "A pair matched in a build" in `B`
- **WHEN** the build runs again with `--confirm`
- **THEN** every file keeps its bytes, and `issues` hold no `kicad.copper.stale`
