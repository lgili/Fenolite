## ADDED Requirements

### Requirement: Test designs built without a tool
`fenolite.testing.load(path, *, seed=0, timestamp="2026-01-01T00:00:00Z", kicad_version=None, workdir=None) -> TestDesign` SHALL build the design script through `fenolite.api.run("build", ...)`, with `--dry-run` and then `--confirm --plan <plan id>`, into a private temporary folder or `workdir`, and SHALL read the built model and board. It MUST run no subprocess, open no connection and import no third-party module, pytest included.

#### Scenario: Built in a temporary folder
- **GIVEN** `examples/testing/design.py` and `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/testing/test_load.py -k temporary` loads it
- **THEN** the model names the parts of the script, no subprocess ran, and the working folder is unchanged

#### Scenario: Same inputs, same model
- **WHEN** the example is loaded twice with the same `seed` and `timestamp`
- **THEN** the two models are equal

### Requirement: Blocks tested alone
`fenolite.testing.instantiate(block, **params) -> TestDesign` SHALL build a throwaway design in its temporary folder that uses the c0251 block once under the name `dut` with `params`, as `load` builds a script, and every port of the block MUST be readable as the net `dut/<port>`.

#### Scenario: A buck block alone
- **GIVEN** an authored buck block (c0251) with the parameter `vout` and a `Rail` port `VOUT`
- **WHEN** `uv run pytest tests/unit/testing/test_instantiate.py` calls `instantiate(buck, vout=volt("3.3").pct(3))`
- **THEN** `net("dut/VOUT")` exists, `ref("dut/U1")` is the regulator, and no file outside the temporary folder was written

### Requirement: Test design lifecycle
`TestDesign` SHALL be a context manager. `close()`, leaving the context and the object's finalizer MUST remove the temporary folder, and MUST NOT remove a `workdir` the caller gave.

#### Scenario: Folder removed
- **WHEN** `uv run pytest tests/unit/testing/test_load.py -k lifecycle` leaves a `with load(...)` block, and closes a design loaded with `workdir=tmp_path`
- **THEN** the temporary folder no longer exists, and `tmp_path` still holds the build

### Requirement: Build failures fail the test
A failed build in `load` or `assert_render` SHALL raise `TestingError`, a subclass of `AssertionError`, whose message holds the `code`, `message`, `where` and `hint` of the error object on stderr.

#### Scenario: A failing script fails the test
- **GIVEN** a script that raises `ValueError` at line 7
- **WHEN** `uv run pytest tests/unit/testing/test_load.py -k failing` loads it
- **THEN** `TestingError` is raised, it is an `AssertionError`, and its message holds `FEN-3004` and `:line:7`

### Requirement: Net and part queries
`TestDesign.net(name)` SHALL return `NetView(name, id, netclass, role, voltage, pins)`, with `pins` the sorted `REF-PIN` texts, `role` the net's role kind or `None`, and `voltage` the rail's range or `None`. `TestDesign.ref(ref)` SHALL return `PartView(ref, id, value, footprint, device, pins)`, whose item and attribute access by pin name or number give `PinView(where, id, net)`. Every `id` MUST be the model id.

#### Scenario: Views of the example
- **WHEN** `uv run pytest tests/unit/testing/test_queries.py -k views` reads `net("3V3")` and `ref("U1").VDD`
- **THEN** the net's pins hold `C5-1` and `U1-4`, the pin's `net` is `3V3`, and the ids are those `fenolite.dsl.KEYS` derives

### Requirement: Unknown names in queries
`net`, `ref` and pin access SHALL raise `TestingError` for an unknown name, naming the three closest known names.

#### Scenario: Unknown names
- **WHEN** `net("3V4")`, `ref("U9")` and `ref("U1").VDDX` are called on the loaded example
- **THEN** each raises `TestingError`, the first naming `3V3` among the closest names

### Requirement: Connection queries
`TestDesign.connected(a, b, *, copper=False)` SHALL return whether `a` and `b`, each a `PinView`, a `REF-PIN` text or a `NetView`, are on one circuit net; with `copper=True`, whether copper of the board joins their pads, measured by `analysis.connectivity` on the board-frame pads.

#### Scenario: Pins on one net, not yet routed
- **GIVEN** the loaded example, where `U1` pin `VDD` and `C5` pin `1` are on `3V3` and no track is routed
- **WHEN** `uv run pytest tests/unit/testing/test_queries.py -k connected` runs
- **THEN** `connected(d.ref("U1").VDD, "C5-1")` is true and the same call with `copper=True` is false

### Requirement: Findings without a tool
`TestDesign.findings(pattern="*", *, stages=None, severity=None)` SHALL run `fenolite check` on the built folder through `fenolite.api.run`, with the stages of `STAGE_ORDER` not in `ORACLE_STAGES` or with `stages`, and SHALL return the issues whose code matches the glob and whose severity equals `severity` when given, each as `Finding(code, severity, message, where, subjects)`, with the check's evidence on the tuple.

#### Scenario: Circuit findings in a test
- **GIVEN** an authored script whose 10 µF capacitor `C1` is rated 10 V on the rail `V12`, under `design.contracts(unknown="warning")` (c0253)
- **WHEN** `uv run pytest tests/unit/testing/test_findings.py -k circuit` calls `findings("circuit.*", severity="warning")` while the rail's voltage is unstated, then loads the script with a 12 V rig
- **THEN** one finding is returned, its subjects name the capacitor and the net `V12`; the second load raises `TestingError` naming `circuit.rating-voltage at C1`, because a rating error stops the build; and no subprocess ran

### Requirement: Oracle stages refused in tests
`findings` SHALL raise `TestingError` before any stage runs when `stages` names a stage of `ORACLE_STAGES`, naming that stage and `fenolite check`.

#### Scenario: Oracle stage refused
- **WHEN** `uv run pytest tests/unit/testing/test_findings.py -k oracle` calls `findings(stages=("drc.kicad",))`
- **THEN** `TestingError` is raised naming `drc.kicad` and `fenolite check`

### Requirement: Golden renders
`fenolite.testing.assert_render(path, golden, *, net=(), region=None, layers=None, seed=0, timestamp=...)` SHALL build the script as `load` does, draw it with the function of `fenolite render --net/--region`, and compare the bytes with the file `golden`, returning `None` when they are equal. It MUST NOT write `golden` or any file outside its temporary folder.

#### Scenario: Same bytes, same verdict
- **GIVEN** `examples/testing/golden/gnd.svg` written by `fenolite render examples/testing/design.py --net GND -o examples/testing/golden --confirm`
- **WHEN** `uv run pytest tests/unit/testing/test_golden.py -k same` calls `assert_render` on the unchanged script twice
- **THEN** both calls return `None` and the golden file's digest is unchanged

### Requirement: Golden render differences
When the bytes differ, or `golden` is missing, `assert_render` SHALL raise `AssertionError` with the counts of added, removed and changed elements, at most twenty diff lines keyed by `class`, `data-item` and `data-layer` and sorted by key, and the `fenolite render` command line that regenerates the file through `--dry-run` and `--confirm --plan`.

#### Scenario: A moved track fails the golden test
- **GIVEN** the golden file of "Same bytes, same verdict" and a copy of the script whose one `GND` track ends 1 mm shorter
- **WHEN** `uv run pytest tests/unit/testing/test_golden.py -k moved` calls `assert_render` on the copy
- **THEN** `AssertionError` is raised with `1 changed`, the line of that track and a line starting with `fenolite render`, and the golden file is unchanged
