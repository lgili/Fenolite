# Tasks of the agent evaluation

Each folder is one task for `tools/agent_eval/run.py` (change c0081): a board stated as a requirement,
and what a correct result holds.

| task | what the agent must do |
|---|---|
| `led-indicator` | write a design script from nothing, place, route with the built-in router, check, export |
| `regulator-zone` | put the supply nets in a net class, pour a ground zone on one layer, fill it, keep the board within a size |
| `custom-footprint` | author a symbol and a footprint from dimensions, for a part the catalog lacks, with one pin on two pads |
| `fix-short` | find the short of a given routed project with `check` and repair it without changing a net |
| `two-sided` | place parts on both sides and join them with scripted copper through a via, under given minimums |

## Where the tasks come from

Every task, prompt, circuit, number and expected result here was written for Fenolite. Nothing comes
from an employer, a private project, a product or any organisation: the circuits are textbook
arrangements of a header, a resistor, a LED, a Zener diode and a capacitor, the part `U1` of
`custom-footprint` is invented, and every size is a round value chosen for the task. Every part of
every solution is an id of Fenolite's built-in catalog or is authored in the solution's script, and
no solution needs an external router or a KiCad library.

## Licence

The tasks are dedicated to the public domain under `CC0-1.0`: the `task.toml` files with their prompts
and expected results, the `commands.txt` files and this page. The Python scripts start with the two
header lines that every `.py` file of the repository carries (`Apache-2.0`).

## The format

```
<name>/
  task.toml             title, prompt, [budget] minutes, [expect], optional prepare
  files/                optional: copied into the work folder before the agent starts
  solution/
    commands.txt        the fenolite lines of a correct run, one per line
    files/              optional: the files a correct run writes
```

- `prompt`: at most 300 words, in plain words. It names every reference of the expected nets and the
  folders to leave. It names no command, no option and no page of the guide: finding them is what a
  run measures.
- `[expect]`: `project` (the folder of the built project), `copper_layers`, `max_size` (two lengths
  with units; the board may lie either way), `outputs` (file patterns, `**` for any depth) and
  `[expect.nets]`, a label for each net with its `REF-PIN` entries. `PIN` is a pin number of the
  part's symbol, not a pad number, and a pin on several pads is listed once. The labels are never
  compared: only the groups are.
- `prepare`: `fenolite` lines that build the starting state in the work folder. No task folder holds a
  built project: `fix-short` holds a script, and its starting project is built by the code under test.

`tools/agent_eval/tasks.py` reads a task and refuses a malformed one; `tests/unit/test_agent_eval.py`
loads them all and builds every solution; `tests/kicad/acceptance/test_eval_solutions.py` replays every
solution on `kicad-cli`.
