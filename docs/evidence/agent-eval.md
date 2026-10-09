# Agent evaluation: recorded runs

What happened when a fresh AI agent was given one task of `tools/agent_eval/tasks/` and the `fenolite`
command line, in an empty folder outside the repository (change c0081). `tools/README.md` says how a
run is started; `tools/agent_eval/run.py --record` appends its row here.

## How to read this page

- **A row is one sample.** An agent does not behave the same way twice: one row says what happened
  once, on one day, with one version of the agent, its model and Fenolite. A claim made from this page
  names the number of rows behind it; `--repeat N` exists to get more than one.
- **The verdict is computed, not judged by a person.** `passed` means that `fenolite check` exited 0 on
  the project the agent left, with `kicad-cli` present, that the nets of the built model are the
  expected groups of `REF-PIN`, that the board fits the task's size and layer count, and that the
  fabrication files exist. `unjudged` means that no `kicad-cli` was found, so KiCad's checks did not run;
  it is never counted as a pass. `failed` is everything else, a run stopped at its time budget included.
- **The tasks prescribe the netlist.** They say which pin joins which. A row therefore says whether the
  agent could use the tool, and nothing about whether it can design a circuit.
- **No row supports a release claim.** The tasks are five small boards, a smoke test of usability.
  Until a release change defines a gate from them, a release record does not cite this page as proof.
- **`calls`** counts the `fenolite` commands the agent ran, **`failed calls`** those that did not exit
  0, and **`first failure`** names the first of them: its number, its command and the error code on
  the last line of its standard error. A call that exits 5 with findings counts as failed here, although
  it is the tool working as intended: read the code.
- **`not isolated`** in the `runner` cell means the agent was started without the flags that keep it
  from loading its user's own settings, memory and skills. Such an agent may remember this repository,
  so its row says less.
- **What a row leaves out.** No path, no prompt and no transcript is kept here. The transcript of a run
  stays in the temporary folder that `--keep` leaves on the machine of the person who ran it.
- **Not sandboxed.** The agent runs as the person who started it, with an empty work folder and a new
  Python environment and nothing more: it can read and write whatever that person can.

## Runs

| date | commit | runner | model | task | verdict | calls | failed calls | minutes | first failure |
|---|---|---|---|---|---|---|---|---|---|

## Findings

One row per distinct first failure of the runs above, with the change that addressed it, or `open`.

| first failure | seen in | what it shows | addressed by |
|---|---|---|---|

## Not measured

- No run with a real agent is recorded yet: the table above is empty, and nothing on this page says
  that an agent can or cannot use Fenolite.
- Whether an agent can design a circuit, choose parts or read a datasheet: the tasks give the netlist.
- Any board beyond the five tasks: more than two copper layers, an external router, a KiCad library,
  an Altium target.
- Any agent, model or version other than those named in a row, and any comparison between them.
- The quality of a passing board beyond what `fenolite check` judges: a layout that passes may still be
  a poor one.
- What a run costs before the first one has reported it.
