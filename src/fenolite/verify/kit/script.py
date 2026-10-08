# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit script: one DelphiScript file that a user starts from inside Altium (capability
altium-verification, "Kit script"; ``docs/altium-kit.md``, "The script").

The text is generated from the steps marked ``scripted``, so the script and the checklist cannot differ.
It is authored for Fenolite: every routine, method and keyword it uses is listed in ``SCRIPT_CALLS`` or
``KEYWORDS`` with the public page of Altium's documentation that names it (``docs/evidence/sources.md``),
and nothing of it comes from an example, a forum or a vendor sample. A call that no public page documents
is not used: its step stays manual (``NOT_SCRIPTED``).

Nothing in Fenolite starts Altium or this script. The script was never run: ``H-A-KIT-SCRIPT`` is
``INFERRED`` until a kit run with it is recorded.

Stdlib only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from fenolite.verify.kit.steps import STEPS, Step

SCRIPT_NAME = "kit_script.pas"
"""The script's path in a kit."""
PROCEDURE = "FenoliteKitRun"
"""The procedure the user runs from Altium's script menu."""
LOG = "results/script.log"
"""The log the script appends to: one line per scripted step, ``<id> done`` or ``<id> error: <text>``."""
DONE = "done"
END_OF_MESSAGES = "end of messages"
"""The last line of a ``messages.txt`` that the script wrote."""

SCRIPT_CALLS: Mapping[str, str] = MappingProxyType(
    {
        "GetWorkspace": "S-0503",
        "DM_FocusedProject": "S-0503",
        "DM_MessagesManager": "S-0503",
        "ClearMessages": "S-0503",
        "MessagesCount": "S-0503",
        "Messages": "S-0503",
        "MsgClass": "S-0503",
        "Text": "S-0503",
        "Source": "S-0503",
        "DM_Compile": "S-0504",
        "DM_ProjectFileName": "S-0504",
        "DM_ProjectFullPath": "S-0504",
        "AssignFile": "S-0501",
        "Append": "S-0501",
        "Rewrite": "S-0501",
        "Writeln": "S-0501",
        "CloseFile": "S-0501",
        "Copy": "S-0501",
        "Length": "S-0501",
        "UpperCase": "S-0501",
    }
)
"""Every routine, method and property the script uses → the id of the public source that names it."""
SOURCE_PAGES: Mapping[str, str] = MappingProxyType(
    {
        "S-0501": "altium-designer/scripting/delphiscript/functions",
        "S-0502": "altium-designer/delphiscript-keywords",
        "S-0503": "altium-dxp-developer/workspace-manager-api",
        "S-0504": "altium-dxp-developer/iproject-interface",
    }
)
"""Source id → the page of Altium's public documentation, under ``www.altium.com/documentation/``."""
READ_AS = (
    "read as rendered on 2026-10-06; no page states the version of Altium Designer it describes; "
    "first run on Altium Designer 26"
)
"""How every page of ``SOURCE_PAGES`` was read: through a text rendering of the page, not the page
itself. A name or a signature of ``SCRIPT_CALLS`` may therefore differ from Altium's; compiling the
script in Altium's script editor is the first step of a run that uses it. It also says which version the
pages are for, and where the script runs first (``PAGE_VERSIONS``, ``FIRST_RUN_ON``)."""
FIRST_RUN_ON = "Altium Designer 26"
"""The version of the first run of the kit, the maintainer's. The pages were not read for it."""
PAGE_VERSIONS: Mapping[str, str] = MappingProxyType(
    {
        "S-0501": "Altium Designer documentation; the address names no version",
        "S-0502": "Altium Designer documentation; the address names no version",
        "S-0503": "Altium DXP Developer documentation; no version of Altium Designer is stated",
        "S-0504": "Altium DXP Developer documentation; no version of Altium Designer is stated",
    }
)
"""Source id → which documentation the page belongs to and what it says of its version, as registered in
``docs/evidence/sources.md`` on 2026-10-06 (the pages were not read again). None is stated to describe
``FIRST_RUN_ON``: a name or a signature may have changed since the page was written."""
KEYWORDS: frozenset[str] = frozenset(
    {
        "Function", "Procedure", "Var", "Begin", "End", "If", "Then", "Else", "While", "Do", "And", "Not",
        "Try", "Except", "Nil", "Result",
    }
)  # fmt: skip
"""The DelphiScript keywords the script uses, all named by the keywords page (S-0502)."""
KEYWORD_SOURCE = "S-0502"
LOCAL_NAMES: frozenset[str] = frozenset(
    {
        PROCEDURE, "KitRoot", "LogLine", "CompileAndExport", "ProjectPath", "Root", "Line", "Project",
        "Sample", "StepId", "Manager", "Item", "Name", "Seen", "F", "I",
    }
)  # fmt: skip
"""The names the script declares itself."""
NOT_SCRIPTED: Mapping[str, str] = MappingProxyType(
    {
        "opening a project": "the reference pages give two forms of `DM_OpenProject` (one and two "
        "arguments), and a person must see whether a repair prompt appears; the script works on the "
        "project that has the focus",
        "saving a document under its result name": "the page of `IServerDocument` (S-0505) describes "
        "`DoSafeChangeFileNameAndSave` only as a test of whether the save is possible, and `DoFileSave` "
        "as a save in place in a format whose names it does not list for current versions; no page says "
        "that either writes the file under a new name",
        "the rule check report, Repour All and the containers of the output job": "the page of the server "
        "processes (S-0506) names no process for them, and the rule check opens a dialog",
        "the change order and Update From Libraries": "both open dialogs that a person reads",
    }
)
"""What the design asked the script to do and it does not, with the reason; these steps stay manual."""

_HEAD = """\
{ Fenolite, Altium verification kit: the kit script.                         }
{ Generated by "fenolite kit build" from the kit's steps; authored for       }
{ Fenolite (Apache-2.0). It writes only under the kit's folder results.      }
{ Use: open a sample project of the kit, focus it, then File, Run Script and }
{ choose FenoliteKitRun. Run it once for each sample project.                }
{ The names and signatures of its calls were read from a text rendering of  }
{ the pages of Altium's public documentation on 2026-10-06, not from the    }
{ pages themselves, and the script has not run in Altium. Before the first  }
{ use: open it in the script editor and compile it; if a line is refused,   }
{ report that line and do the scripted steps by hand.                       }
{ No page that was read states the version of Altium Designer it describes; }
{ the first run of this script is on Altium Designer 26.                    }

Function KitRoot(ProjectPath);
Var
    I, Seen;
Begin
    Result := '';
    I := Length(ProjectPath);
    Seen := 0;
    While (I > 0) And (Seen < 2) Do
    Begin
        If Copy(ProjectPath, I, 1) = '\\' Then Seen := Seen + 1;
        If Seen < 2 Then I := I - 1;
    End;
    If Seen = 2 Then Result := Copy(ProjectPath, 1, I);
End;

Procedure LogLine(Root, Line);
Var
    F;
Begin
    AssignFile(F, Root + 'results\\script.log');
    Try
        Append(F);
    Except
        Rewrite(F);
    End;
    Writeln(F, Line);
    CloseFile(F);
End;

Procedure CompileAndExport(Project, Root, Sample, StepId);
Var
    Manager, Item, F, I;
Begin
    Try
        Manager := GetWorkspace.DM_MessagesManager;
        Manager.ClearMessages;
        Project.DM_Compile;
        AssignFile(F, Root + 'results\\' + Sample + '\\messages.txt');
        Rewrite(F);
        I := 0;
        While I < Manager.MessagesCount Do
        Begin
            Item := Manager.Messages(I);
            Writeln(F, '[' + Item.MsgClass + '] ' + Item.Text + ' (' + Item.Source + ')');
            I := I + 1;
        End;
        Writeln(F, '%(end)s');
        CloseFile(F);
        LogLine(Root, StepId + ' %(done)s');
    Except
        LogLine(Root, StepId + ' error: the project was not compiled or its messages were not written');
    End;
End;

Procedure %(procedure)s;
Var
    Project, Name, Root;
Begin
    Project := GetWorkspace.DM_FocusedProject;
    If Not (Project = Nil) Then
    Begin
        Name := UpperCase(Project.DM_ProjectFileName);
        Root := KitRoot(Project.DM_ProjectFullPath);
"""
_BLOCK = """\
        { %(id)s }
        If Name = '%(project)s' Then CompileAndExport(Project, Root, '%(sample)s', '%(id)s');
"""
_TAIL = """\
    End;
End;
"""
BLOCK_MARK = re.compile(r"^\s*\{ (K[1-9]\.[1-9][0-9]?) \}\s*$", re.MULTILINE)
_COMMENT = re.compile(r"\{[^}]*\}")
_STRING = re.compile(r"'[^']*'")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def scripted_steps(steps: Sequence[Step] = STEPS) -> tuple[Step, ...]:
    """The steps the script performs, in step order."""
    return tuple(step for step in steps if step.scripted)


def script_text(steps: Sequence[Step] = STEPS) -> str:
    """The kit script for ``steps``: one block per scripted step, in step order, with CR LF line ends and
    7-bit ASCII only. ``ValueError`` for a scripted step that is not a compile step of a sample project."""
    blocks: list[str] = []
    for step in scripted_steps(steps):
        if step.kind != "file" or step.checks != ("messages",) or not step.document.endswith(".PrjPcb"):
            raise ValueError(f"{step.id}: only a compile step of a sample project can be scripted")
        if step.result != f"{step.sample}/messages.txt":
            raise ValueError(f"{step.id}: a scripted step writes results/<sample>/messages.txt")
        project = step.document.rsplit("/", 1)[-1].upper()
        blocks.append(_BLOCK % {"id": step.id, "project": project, "sample": step.sample})
    head = _HEAD % {"end": END_OF_MESSAGES, "done": DONE, "procedure": PROCEDURE}
    text = head + "".join(blocks) + _TAIL
    text.encode("ascii")
    return text.replace("\n", "\r\n")


def block_ids(text: str) -> tuple[str, ...]:
    """The step ids of the blocks of a script text, in order."""
    return tuple(BLOCK_MARK.findall(text.replace("\r\n", "\n")))


def used_names(text: str) -> frozenset[str]:
    """Every name the script text uses outside its comments and string literals."""
    bare = _STRING.sub("''", _COMMENT.sub(" ", text))
    return frozenset(_NAME.findall(bare))


def undocumented_names(text: str) -> tuple[str, ...]:
    """The names of ``text`` that are neither a listed call, nor a listed keyword, nor a name the script
    declares: sorted, and empty for a script that uses documented calls only."""
    known = {name.casefold() for name in (*SCRIPT_CALLS, *KEYWORDS, *LOCAL_NAMES)}
    return tuple(sorted(name for name in used_names(text) if name.casefold() not in known))


def log_outcomes(text: str) -> dict[str, str]:
    """Step id → ``done`` or the error text, from the lines of a ``script.log``; the last line of a step
    wins, and a line of another form is ignored."""
    outcomes: dict[str, str] = {}
    for line in text.splitlines():
        ident, _, rest = line.strip().partition(" ")
        if re.fullmatch(r"K[1-9]\.[1-9][0-9]?", ident) and rest:
            outcomes[ident] = rest
    return outcomes


__all__ = [
    "DONE",
    "FIRST_RUN_ON",
    "END_OF_MESSAGES",
    "KEYWORDS",
    "KEYWORD_SOURCE",
    "LOCAL_NAMES",
    "LOG",
    "NOT_SCRIPTED",
    "PAGE_VERSIONS",
    "PROCEDURE",
    "READ_AS",
    "SCRIPT_CALLS",
    "SCRIPT_NAME",
    "SOURCE_PAGES",
    "block_ids",
    "log_outcomes",
    "script_text",
    "scripted_steps",
    "undocumented_names",
    "used_names",
]
