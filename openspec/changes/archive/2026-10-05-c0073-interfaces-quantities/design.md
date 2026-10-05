## Context

- **Scope.** Plan, v0.2b deliverables: "interfaces `I2C/SPI/UART/USB2` + `Quantity`"; package tree: "`dsl/`: … `interfaces.py`, `quantity.py` (v0.2b)". Plan D6: no requirement tables in Fenolite; values come from the user.
- **What exists.**
  - `fenolite.dsl.interfaces`: `Interface(name, kind, members)`, `Power(hv, lv)`, `DiffPair(p, n)`, `Harness(name, members)`; model `Interface(name, kind: str, members: role → net id)`; ids `derived_id("itf", "dsl", "interface:harness:<name>")` for harnesses.
  - A KiCad build gives one `build.interface-not-lowered` info per `diff_pair`; the Altium build gives one `altium.not-lowered` info for diff pairs and lowers harnesses to sheet entries.
  - `connect(net, *pins)` and pin handles (`u1["PB7"]`, `u1[3]`); the build resolves designators against the resolved symbol (`build.unknown-pin`).
  - `Part.value` is a string; `Length` and `mm()`/`mil()`/`inch()`/`nm()` give lengths in integer nm.
  - c0047 (archived): the requirements file holds integer values with the unit in the key name (`milliamps`, `millivolts`), and the design kept voltages off nets in the model.
- **Measured on 2026-10-05** (scratch bench of `tests/kicad/rules/_rulebench.py`, pairs of tracks 0.3 mm apart, one rule per pair with the condition `A.inDiffPair('<base>')` and a 3 mm clearance, the scoped canary; `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally, identical results): recognised as a pair: `USBA_P`/`USBA_N` (base `USBA` and `USBA_` both match), `USBB+`/`USBB-`, `USBD_DP`/`USBD_DN` (base `USBD_D`), `USBEP`/`USBEN`; not recognised: `USBC_DP`/`USBC_DM`, `USBF_p`/`USBF_n`, `USBH_P`/`USBH-`.
- **Constraints.** Stdlib only. No float anywhere. No model or schema change. No value shipped.

## Goals / Non-Goals

**Goals:**
- A bus is declared once and parts are attached to it by role, so the classic wiring mistakes cannot be written.
- What KiCad needs from interface nets (pair names) is checked at build time.
- Values in the script are exact and print one way.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **`Quantity` is exact and closed.** A `Quantity` holds a unit (`ohm`, `farad`, `henry`, `volt`, `ampere`, `hertz`, `watt`, `second`) and a `fractions.Fraction` of it.
   - Built from an `int`, a `Fraction`, or a text: a decimal number, an optional SI prefix (`p`, `n`, `u`, `µ`, `m`, `k`, `M`, `G`) and an optional symbol of the constructor's unit (`Ω` or `ohm` or `R`, `F`, `H`, `V`, `A`, `Hz`, `W`, `s`), or the IEC 60062 letter code, where the prefix letter, or `R` for ohms, stands for the decimal point (`4k7`, `2R2`, `1n5`). A `float`, a `bool`, another unit's symbol, or a text that does not parse raises `DslError`. Negative values are allowed for volts and amperes only.
   - Equality, ordering and hashing compare the unit and the exact value, so `ohm("4k7") == ohm("4.7k") == ohm(4700)`. `+` and `-` take equal units; `*` and `/` take an `int` or a `Fraction`; anything else raises `TypeError`, as Python does.
   - `text()` prints the value scaled by the largest SI prefix, in steps of 1 000 from `p` to `G`, that keeps it at least 1, as the shortest exact decimal, then the prefix and the symbol: `4.7kΩ`, `100nF`, `3.3V`, `16MHz`, with `u` for micro. A value that the step does not make a terminating decimal (built from a `Fraction` such as 1/3) raises `DslError` on printing. `text(code=True)` prints the letter code for ohms, farads and henries (`4k7`, `100n`, `2R2`).
   - Rejected: floats with a tolerance (two equal values could print differently); `Decimal` (division is not exact); a units library (a runtime dependency in the core).

2. **Part values.** `Part(value=q)` stores `q.text()`. A string keeps working unchanged. The canonical text is what makes `4k7` and `4.7k` one BOM line (c0064 groups by value text).

3. **Typed interfaces.** `I2C`, `SPI`, `UART` and `USB2` are subclasses of `Interface` with fixed roles:

   | class | kind | members |
   |---|---|---|
   | `I2C(sda, scl, *, name=None)` | `i2c` | `sda`, `scl` |
   | `SPI(sck, mosi, miso, *, cs=(), name=None)` | `spi` | `sck`, `mosi`, `miso`, `cs0` … `cs<n-1>` |
   | `UART(tx, rx, *, name=None)` | `uart` | `tx`, `rx`, named from device A |
   | `USB2(dp, dn, *, vbus=None, gnd=None, name=None)` | `usb2` | `dp`, `dn`, and `vbus`, `gnd` when given |

   - The default name is `"<first net name>/<second net name>"`, as for `Power`. Ids are `derived_id("itf", "dsl", "interface:<kind>:<name>")`.
   - The nets of one interface must be distinct. A net may belong to several interfaces (`GND` in `USB2` and in `Power`).
   - Rejected: a `Bus` base with free roles (that is `Harness`); one class per speed or mode (values are the user's).

4. **Attaching by role.** `attach(part, **roles)` connects pins of one part to the interface's nets with `connect`, so every rule of `connect` applies.
   - `I2C.attach(part, *, sda, scl)` and `USB2.attach(part, *, dp, dn, vbus=None, gnd=None)` map role to net.
   - `UART.attach(part, *, side, tx, rx)`: `side="a"` connects the part's TX pin to the `tx` net and its RX pin to the `rx` net; `side="b"` crosses them. A TX-to-TX wiring cannot be written through `attach`.
   - `SPI.attach(part, *, role, sck, mosi, miso, cs=None, cs_index=None)`: a `controller` gives one chip-select pin per `cs` net, in order; a `peripheral` gives one chip-select pin and the index of its `cs` net. MOSI and MISO are never crossed.
   - A pin argument is a pin handle of `part`, or a designator resolved as `part[designator]`.

5. **Checks in the build.** Two warnings join the closed build set:
   - `build.diff-pair-name`: the nets of a `diff_pair` (`p`, `n`) or `usb2` (`dp`, `dn`) interface, in KiCad's stored form, are not equal except for a last character that is `P` then `N`, or `+` then `-` (`H-K-DIFFPAIR-NAMES`). The hint proposes the second name that KiCad pairs with the first (`USB_DP` with `USB_DN`). KiCad's interactive differential-pair router and `inDiffPair()` find pairs by this rule, so a wrong name makes the pair invisible to them.
   - `build.i2c-pullup-missing`: an I2C line with no component of two pins (by its resolved symbol) whose other pin is on the `hv` net of a `power` interface. It is a warning: a pull-up may sit on another board.
   - `build.interface-not-lowered` (info) now also names `usb2` interfaces.

6. **Altium.** The Altium build adds the four kinds to its existing `altium.not-lowered` info for interfaces, beside diff pairs. Harness lowering does not take them: their roles are not sheet entries yet.

7. **Cut order.** First `SPI.attach` (keep the interface), then the letter code (`text(code=True)` and its parsing), never `Quantity`, the four interfaces and the pair-name check.

## Files and public API

- `src/fenolite/dsl/quantity.py`: `Quantity`, `UNITS`, `ohm`, `farad`, `henry`, `volt`, `amp`, `hertz`, `watt`, `second`.
- `src/fenolite/dsl/interfaces.py`: `I2C`, `SPI`, `UART`, `USB2` with `attach`.
- `src/fenolite/dsl/part.py`: `Part(value=Quantity | str)`.
- `src/fenolite/dsl/__init__.py`: the new names.
- `src/fenolite/lens/build.py`: `interface_checks(design, parts) -> tuple[Issue, ...]`, the two codes in `BUILD_ISSUE_CODES`.
- `src/fenolite/lens/altium.py`: the not-lowered message.
- Tests: `tests/unit/dsl/test_quantity.py`, `tests/unit/dsl/test_interfaces_typed.py`, `tests/unit/lens/test_interface_checks.py`, `tests/kicad/rules/test_diffpair_names.py`.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-DIFFPAIR-NAMES | KiCad treats two nets as one differential pair when their names are equal except for a last character `P` then `N`, or `+` then `-`, case-sensitive: `X_P`/`X_N`, `X+`/`X-`, `X_DP`/`X_DN` and `XP`/`XN` are pairs; `X_DP`/`X_DM`, `X_p`/`X_n` and `X_P`/`X-` are not (S-0020, S-0029) | `tests/kicad/rules/test_diffpair_names.py` | probes `dru-diffpair-<case>` give `present` for the four pairs and `absent` for the three others, with the canary firing, on 9.0.9 and 10.0.6 |

Ids used without changing their level: `H-K-DRU-COND`, `H-K-SCH-SLASH` (c0061, stored names).

## Risks / Trade-offs

- [A pull-up through a resistor array of four pins is not seen] → warning only, with the hint "a pull-up of more than two pins is not recognised"; the user can ignore it.
- [`text()` uses `Ω`, a character outside ASCII] → KiCad stores UTF-8 field texts; `text(code=True)` and plain strings remain for users who want ASCII.
- [Two interfaces disagree about a net's role] → no rule here; a net in two interfaces is legal.

## Migration Plan

- Additive. Existing scripts, `DiffPair`, `Power` and `Harness` behave as before; a `DiffPair` with names KiCad does not pair now gives one warning.
- Rollback: remove the four classes and the checks; `Quantity` can stay.

## Open Questions

- **Should `Part(value=q)` print the ohm symbol?** Default: yes (`4.7kΩ`); `value=q.text(code=True)` gives `4k7`.
- **Should the pull-up check accept a part of more than two pins?** Default: no in this change.
- **Should I2C, SPI and UART lower to Altium harnesses?** Default: later, with roles as entries.
