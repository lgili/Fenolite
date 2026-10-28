# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the MCP server serves: the tools of :mod:`fenolite.mcp.tools` run as the command line, and the guide
resources (capability mcp-server, "Calls run the command line" and "Writes through a reviewed plan"; change
c0195).

Each call runs ``python -m fenolite <command> ... --json`` as a child process in the server's root, in its
own process group, with standard input closed. Its envelope (exit 0 or 5) or its error object (any other
exit) is the result. A call that passes the timeout, or that the client cancels, stops the group (a
terminate, then a kill) and gives ``FEN-1003``, which can be run again; the command line's own signal handling
leaves no partial write. With a progress token the server adds ``--progress`` and reports each record.

A writing tool without ``confirm`` is the dry run. With ``confirm`` it needs ``plan``; the staged plan is read
first and refused unless it is a plan of the same command whose every write lies under the root.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import IO, Any, cast

from fenolite.cli import plans
from fenolite.cli.api import Command
from fenolite.cli.errors import CliError, ErrorInfo
from fenolite.cli.output import canonical_json, to_jsonable
from fenolite.core.state import state_dir
from fenolite.mcp.protocol import Call, UnknownTool
from fenolite.mcp.resources import Resources
from fenolite.mcp.tools import Catalog, InputRefused, Tool

EXIT_KEY = "fenolite/exit"
"""The ``_meta`` key of a tool result that holds the command's exit code."""
IMAGES = 4
IMAGE_BYTES = 6_000_000
"""The images of one reply: at most this many, and this many bytes before base64 (change c0196)."""
GRACE = 5.0
"""Seconds between the terminate and the kill of a stopped call."""
Json = dict[str, Any]


def _result(value: Json, exit_code: int) -> Json:
    """A tool result: ``value`` as structured content and as its canonical JSON text."""
    return {
        "content": [{"type": "text", "text": canonical_json(value)}],
        "structuredContent": value,
        "isError": exit_code not in (0, 5),
        "_meta": {EXIT_KEY: exit_code},
    }


def _error(info: ErrorInfo, exit_code: int) -> Json:
    return _result(cast("Json", to_jsonable(info)), exit_code)


def _refusal(code: str, message: str, *, where: str, hint: str = "") -> Json:
    error = CliError(code, message, where=where, hint=hint or None)
    return _error(error.info(), int(error.exit_code))


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


class FenoliteBackend:
    """The tools and resources of ``fenolite mcp`` for a root folder."""

    def __init__(
        self,
        commands: Mapping[str, Command],
        *,
        root: Path,
        timeout: float,
        read_only: bool = False,
        only: list[str] | None = None,
        allow_edit: bool = False,
        executable: list[str] | None = None,
    ) -> None:
        self.catalog = Catalog(commands, read_only=read_only, only=only, allow_edit=allow_edit)
        self.root, self.timeout = root.resolve(), timeout
        self.guide = Resources(self.capabilities)
        self.executable = executable if executable is not None else [sys.executable, "-m", "fenolite"]

    # ------------------------------------------------------------------ Backend

    def tools(self) -> list[Json]:
        return self.catalog.definitions()

    def resources(self) -> list[Json]:
        return self.guide.list()

    def read(self, uri: str) -> list[Json] | None:
        return self.guide.read(uri)

    def call(self, name: str, arguments: Json, call: Call) -> Json:
        tool = self.catalog.tools.get(name)
        if tool is None:
            raise UnknownTool(name)
        written: Path | None = None
        try:
            if tool.inputs:
                given = self._input_file(tool.inputs, arguments)
                if isinstance(given, dict):
                    return given  # a refusal
                argument, written = given
                return self._call(tool, name, arguments, call, {argument: str(written)})
            return self._call(tool, name, arguments, call, None)
        finally:
            if written is not None:
                written.unlink(missing_ok=True)

    def _input_file(self, inputs: Mapping[str, str], arguments: Json) -> Json | tuple[str, Path]:
        """Write the one input property of ``arguments`` to ``<state>/mcp-inputs/<sha256>``, named by its
        bytes so that a confirmation repeats the dry run's command line; a refusal when there is not exactly
        one, or it is malformed (change c0196, "Script editing tool")."""
        present = [key for key in inputs if arguments.get(key) is not None]
        if len(present) != 1:
            names = " or ".join(repr(key) for key in inputs)
            return _refusal(
                "FEN-2001", f"give exactly one of {names}", where=present[1] if present else "content"
            )
        key = present[0]
        value = arguments[key]
        if key == "content" and isinstance(value, str):
            data, suffix = value.encode("utf-8"), ".txt"
        elif (
            key == "edits"
            and isinstance(value, list)
            and all(
                isinstance(p, dict) and set(cast("Json", p)) == {"old", "new"}
                for p in cast("list[Any]", value)
            )
        ):
            data, suffix = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"), ".json"
        else:
            return _refusal("FEN-2001", f"{key}: a string, or a list of {{old, new}} objects", where=key)
        state = state_dir()
        if state is None:
            return _refusal("FEN-2001", "the state folder is off (FENOLITE_STATE_DIR=off)", where=key)
        folder = state / "mcp-inputs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (hashlib.sha256(data).hexdigest() + suffix)
        path.write_bytes(data)
        return inputs[key], path

    def _call(self, tool: Tool, name: str, arguments: Json, call: Call, given: dict[str, str] | None) -> Json:
        confirm = arguments.get("confirm")
        plan = arguments.get("plan")
        try:
            words = self.catalog.command_line(
                name, arguments, dry_run=tool.mutates and not confirm, given=given
            )
        except InputRefused as refused:
            return _error(refused.error, 2)
        if tool.mutates and confirm:
            if not isinstance(plan, str) or not plan:
                return _refusal(
                    "FEN-2001", "confirm needs the plan a dry run returned", where="plan",
                    hint="call the tool without 'confirm' first, review result.plan, then pass its plan_id",
                )  # fmt: skip
            refused = self._plan_refused(tool.command, plan)
            if refused is not None:
                return refused
            at = words.index("--") if "--" in words else len(words)
            words = [*words[:at], "--confirm", f"--plan={plan}", *words[at:]]
        return self._with_images(self._run(name, words, call))

    # ------------------------------------------------------------------ images

    def _with_images(self, reply: Json) -> Json:
        """``reply`` with the PNG files its envelope plans or wrote as image content, after the envelope's
        text: a dry run's from the staged plan, a confirmed run's from the files under the root (capability
        mcp-server, "Images in replies"). At most :data:`IMAGES` images and :data:`IMAGE_BYTES` bytes."""
        envelope = cast("Json", reply.get("structuredContent") or {})
        if reply.get("isError") or "result" not in envelope:
            return reply
        found = self._pngs(envelope)
        if not found:
            return reply
        items: list[Json] = []
        left: list[str] = []
        total = 0
        for path, read in found:
            data = read()
            if data is None or len(items) == IMAGES or total + len(data) > IMAGE_BYTES:
                left.append(path)
                continue
            total += len(data)
            items.append(
                {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": "image/png"}
            )
        if left:
            note = f"images not sent (at most {IMAGES} and {IMAGE_BYTES} bytes per reply): {', '.join(left)}"
            items.append({"type": "text", "text": note})
        return reply | {"content": [*cast("list[Json]", reply["content"]), *items]}

    def _pngs(self, envelope: Json) -> list[tuple[str, Callable[[], bytes | None]]]:
        """The PNG rows of a reply, each with what reads its bytes (``None`` when they cannot be read)."""
        result = cast("Json", envelope.get("result") or {})
        receipt = cast("Json | None", envelope.get("receipt"))
        if receipt:
            rows = [cast("Json", r) for r in cast("list[Any]", receipt.get("written") or [])]
            return [
                (str(row["path"]), partial(self._read_written, str(row["path"])))
                for row in rows
                if str(row.get("path", "")).lower().endswith(".png")
            ]
        plan_id = result.get("plan_id")
        if not isinstance(plan_id, str):
            return []
        try:
            staged = plans.load(state_dir(), plan_id)
        except plans.DamagedPlan:
            return []
        if staged is None:
            return []
        return [
            (str(row["path"]), partial(self._read_staged, staged, row))
            for row in staged.writes
            if str(row.get("path", "")).lower().endswith(".png")
        ]

    @staticmethod
    def _read_staged(staged: plans.StagedPlan, row: Json) -> bytes | None:
        try:
            return staged.data(row)
        except plans.DamagedPlan:
            return None

    def _read_written(self, path: str) -> bytes | None:
        target = self.root / path
        if not _under(target, self.root) or not target.is_file():
            return None
        return target.read_bytes()

    def capabilities(self) -> str:
        """The JSON text of ``fenolite capabilities --json --no-tools``, run as any call is."""
        reply = self._run("fenolite_capabilities", ["capabilities", "--no-tools"], Call())
        return str(reply["content"][0]["text"])

    # ------------------------------------------------------------------ writes

    def _plan_refused(self, command: str, plan: str) -> Json | None:
        """Why the staged plan ``plan`` may not be confirmed by this server, or ``None``. A plan the store
        does not hold is left to the command line, which refuses it with its own code."""
        try:
            staged = plans.load(state_dir(), plan)
        except plans.DamagedPlan:
            return None
        if staged is None:
            return None
        if staged.command != command:
            return _refusal(
                "FEN-2001", f"plan {plan} is a plan of {staged.command}, not {command}", where="plan"
            )
        base = Path(staged.cwd)
        for row in staged.writes:
            target = base / str(row.get("path", ""))
            if not _under(target, self.root):
                return _refusal(
                    "FEN-2001", f"plan {plan} writes {target}, outside the server's root {self.root}",
                    where="plan", hint="run the write from a server whose --root holds the target",
                )  # fmt: skip
        return None

    # ------------------------------------------------------------------ the child

    def _run(self, name: str, words: list[str], call: Call) -> Json:
        argv = [
            *self.executable,
            *words[:1],
            "--json",
            *(["--progress"] if call.progress else []),
            *words[1:],
        ]
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        child = subprocess.Popen(
            argv, cwd=self.root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=group, start_new_session=os.name != "nt",
        )  # fmt: skip
        out: list[bytes] = []
        errors: list[str] = []
        readers = [
            threading.Thread(target=lambda: out.append(cast("IO[bytes]", child.stdout).read()), daemon=True),
            threading.Thread(target=self._stderr, args=(child, errors, call), daemon=True),
        ]
        for reader in readers:
            reader.start()
        stopped = self._wait(child, call)
        for reader in readers:
            reader.join(GRACE)
        if stopped is not None:
            return _refusal("FEN-1003", stopped, where=name, hint="the call can be run again")
        code = int(child.returncode)
        if code in (0, 5):
            try:
                return _result(cast("Json", json.loads(b"".join(out).decode("utf-8"))), code)
            except ValueError as exc:
                return _refusal("FEN-1001", f"the command's output is not its envelope: {exc}", where=name)
        for line in reversed(errors):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and "code" in value:
                return _result(cast("Json", value), code)
        return _refusal("FEN-1001", f"the command exited {code} without its error object", where=name)

    def _wait(self, child: subprocess.Popen[bytes], call: Call) -> str | None:
        """Wait for ``child``; stop it on cancellation or after the timeout and say why, else ``None``."""
        deadline = time.monotonic() + self.timeout
        while child.poll() is None:
            if call.cancelled.wait(0.05):
                self._stop(child)
                return "the client cancelled the call"
            if time.monotonic() > deadline:
                self._stop(child)
                return f"the call ran longer than {self.timeout:g} s and was stopped"
        return None

    @staticmethod
    def _stop(child: subprocess.Popen[bytes]) -> None:
        if os.name == "nt":
            child.terminate()
        else:
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(GRACE)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                child.kill()
            else:
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()

    @staticmethod
    def _stderr(child: subprocess.Popen[bytes], errors: list[str], call: Call) -> None:
        """Read the child's stderr: progress records become notifications, other lines are kept."""
        count = 0
        for raw in cast("IO[bytes]", child.stderr):
            line = raw.decode("utf-8", "replace").strip()
            try:
                value = json.loads(line)
            except ValueError:
                errors.append(line)
                continue
            record = cast("Json", value).get("progress") if isinstance(value, dict) else None
            if isinstance(record, dict):
                fields = cast("Json", record)
                count += 1
                report = call.progress
                if report is not None:
                    step = fields.get("step") or ""
                    report(
                        count, None, f"{fields.get('command', '')}: {fields.get('event', '')} {step}".strip()
                    )
            else:
                errors.append(line)


__all__ = ["EXIT_KEY", "FenoliteBackend"]
