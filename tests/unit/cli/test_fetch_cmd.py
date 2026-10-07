# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite fetch``, deferred writes and the two error codes (capability cli-contract, "Fetch command",
"Deferred writes", "Fetch error codes"; capability routing, "Tools folder" and "Freerouting plugin";
change c0078). Hermetic: no test of this file opens a network connection."""

from __future__ import annotations

import dataclasses
import hashlib
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping
from email.message import Message
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _fakefreerouting import create_fake_jar, create_fake_java
from _resources import posix_tools
from _specctra import two_pads

from fenolite import __version__
from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import cmd__echo, fetch
from fenolite.cli.api import PlannedWrite
from fenolite.cli.errors import REGISTRY, CliError
from fenolite.cli.exitcodes import ExitCode
from fenolite.cli.fetch import FetchRow
from fenolite.core.tools import TOOLS_ENV

ROOT = Path(__file__).resolve().parents[3]
JAR = "freerouting-2.4.1.jar"
SMALL = b"a small stand-in for a tool\n"


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every way of this process to the network raises; the list holds what was tried."""
    tried: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        tried.append(repr(args[:2]))
        raise AssertionError(f"a network connection was opened: {args[:2]!r}")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    return tried


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """An empty tools folder of the test; it is not created."""
    folder = tmp_path / "tools-folder"
    monkeypatch.setenv(TOOLS_ENV, str(folder))
    return folder


def _snapshot(folder: Path) -> list[str]:
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def _small_row(monkeypatch: pytest.MonkeyPatch, data: bytes = SMALL) -> FetchRow:
    """The row ``freerouting`` with the size and the digest of ``data`` instead of the jar's."""
    table = dict(fetch.rows())
    row = dataclasses.replace(table["freerouting"], bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    table["freerouting"] = row
    monkeypatch.setattr(fetch, "rows", lambda: table)
    return row


# --- Deferred writes ------------------------------------------------------------------------------


def test_planned_write_shapes() -> None:
    assert PlannedWrite("a", b"x", "text").deferred is False
    assert PlannedWrite("a", b"", "text", source=lambda: b"x", size=1, sha256="0" * 64).deferred is True
    for broken in (
        {"data": b"x", "source": lambda: b"x", "size": 1, "sha256": "0" * 64},  # data and a source
        {"data": b"", "source": lambda: b"x", "size": 1},  # no digest
        {"data": b"", "source": lambda: b"x", "sha256": "0" * 64},  # no size
        {"data": b"x", "size": 1},  # a size without a source
        {"data": b"x", "sha256": "0" * 64},  # a digest without a source
    ):
        with pytest.raises(ValueError):
            PlannedWrite(path="a", kind="text", **broken)  # type: ignore[arg-type]


def test_deferred_dry_run_does_not_call_the_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cmd__echo, "DEFER_CALLS", [])
    declared = {
        "path": "out.txt",
        "kind": "text",
        "bytes": len(cmd__echo.DEFERRED),
        "sha256": hashlib.sha256(cmd__echo.DEFERRED).hexdigest(),
        "overwrite": False,
    }
    code, env, _, _ = run(monkeypatch, tmp_path, "_echo", "--defer", "out.txt", "--dry-run")
    assert code == 0 and env["result"]["plan"] == [declared]
    code, env, error, _ = run(monkeypatch, tmp_path, "_echo", "--defer", "out.txt")
    assert code == 4 and error["code"] == "FEN-4001" and env["result"]["plan"] == [declared]
    assert cmd__echo.DEFER_CALLS == [] and _snapshot(tmp_path) == []


def test_deferred_confirmed_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cmd__echo, "DEFER_CALLS", [])
    code, env, _, _ = run(monkeypatch, tmp_path, "_echo", "--defer", "out.txt", "--confirm")
    assert code == 0 and cmd__echo.DEFER_CALLS == ["out.txt"]
    assert (tmp_path / "out.txt").read_bytes() == cmd__echo.DEFERRED
    written = env["receipt"]["written"]
    assert written == [{"path": "out.txt", "sha256": hashlib.sha256(cmd__echo.DEFERRED).hexdigest()}]
    assert re.fullmatch(r"[0-9a-f]{16}", env["receipt"]["id"])  # the receipt of any write (c0066)


def test_deferred_wrong_bytes_write_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cmd__echo, "DEFER_CALLS", [])
    code, env, error, _ = run(
        monkeypatch, tmp_path, "_echo", "--defer-bad", "out.txt", "--write", "other.txt", "--confirm"
    )
    assert code == 3 and error["code"] == "FEN-3006" and env["ok"] is False and env["receipt"] is None
    expected = hashlib.sha256(cmd__echo.DEFERRED).hexdigest()
    found = hashlib.sha256(cmd__echo.DEFERRED[::-1]).hexdigest()
    assert expected in error["message"] and found in error["message"] and expected != found
    assert cmd__echo.DEFER_CALLS == ["out.txt"] and _snapshot(tmp_path) == []


def test_deferred_plain_write_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A write without a source behaves as before, also beside a deferred one."""
    monkeypatch.setattr(cmd__echo, "DEFER_CALLS", [])
    code, env, _, _ = run(
        monkeypatch, tmp_path, "_echo", "--write", "other.txt", "--defer", "out.txt", "--confirm"
    )
    assert code == 0 and [w["path"] for w in env["receipt"]["written"]] == ["other.txt", "out.txt"]
    assert (tmp_path / "other.txt").read_bytes() == b"echo\n"


def test_deferred_source_error_keeps_its_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def source() -> bytes:
        raise CliError("FEN-6003", "no route to the publisher")

    monkeypatch.setattr(
        cmd__echo, "_deferred", lambda path, _data: PlannedWrite(path, b"", "text", source, 1, "0" * 64)
    )
    code, _, error, _ = run(
        monkeypatch, tmp_path, "_echo", "--defer", "out.txt", "--write", "other.txt", "--confirm"
    )
    assert code == 6 and error["code"] == "FEN-6003" and error["retryable"] is True
    assert _snapshot(tmp_path) == []


# --- Fetch error codes ----------------------------------------------------------------------------


def test_codes_are_registered_and_documented() -> None:
    assert REGISTRY["FEN-6003"].exit_code is ExitCode.TOOL and REGISTRY["FEN-6003"].retryable is True
    assert REGISTRY["FEN-6003"].message == "download failed" and "--from FILE" in REGISTRY["FEN-6003"].hint
    assert REGISTRY["FEN-3006"].exit_code is ExitCode.INPUT and REGISTRY["FEN-3006"].retryable is False
    assert REGISTRY["FEN-3006"].message == "fetched file does not match the pinned size or SHA-256"
    contract = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    assert "| `FEN-6003` |" in contract and "| `FEN-3006` |" in contract
    section = contract[contract.index("\n## fetch\n") :]
    for words in ("**The plan**", "FEN-6003", "FEN-3006", "No other command downloads anything"):
        assert words in section, words
    for key in ("name", "version", "file", "path", "bytes", "sha256", "url", "licence", "origin",
                "installed", "needs", "env"):  # fmt: skip
        assert f"`{key}`" in section, key


def test_codes_are_explained(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "explain", "FEN-6003")
    assert code == 0 and "--from" in str(env["result"])
    code, env, _, _ = run(monkeypatch, tmp_path, "explain", "FEN-3006")
    assert code == 0 and "SHA-256" in str(env["result"])


# --- The table ------------------------------------------------------------------------------------


def _evidence_row(page: str, key: str) -> str:
    """The value cell of the row ``key`` in the table of the gate's jar on the routing evidence page."""
    start = page.index("| file | `freerouting-2.4.1.jar`")
    match = re.search(rf"^\| {re.escape(key)} \| (.*?) \|$", page[start:], re.MULTILINE)
    assert match is not None, key
    return match.group(1)


def test_table_agrees_with_the_evidence_page() -> None:
    page = (ROOT / "docs" / "evidence" / "routing.md").read_text(encoding="utf-8")
    row = fetch.rows()["freerouting"]
    size = re.fullmatch(r"([0-9 ]+) bytes", _evidence_row(page, "size"))
    digest = re.match(r"`([0-9a-f]{64})`", _evidence_row(page, "SHA-256"))
    assert size is not None and digest is not None
    assert row.bytes == int(size.group(1).replace(" ", "")) and row.sha256 == digest.group(1)
    assert (row.version, row.file, row.licence, row.source, row.env) == (
        "2.4.1", JAR, "GPL-3.0", "S-0223", "FENOLITE_FREEROUTING_JAR",
    )  # fmt: skip
    assert row.url == f"https://github.com/freerouting/freerouting/releases/download/v2.4.1/{JAR}"
    assert any("Java 25" in need for need in row.needs)


def table_problems(table: Mapping[str, FetchRow], sources: str) -> list[str]:
    """Why a table may not be shipped: a public row without an ``https`` address or a registered source."""
    registered = set(re.findall(r"^\| (S-\d{4}) \|", sources, re.MULTILINE))
    problems: list[str] = []
    for name, row in table.items():
        if row.hidden:
            continue
        if not row.url.startswith("https://") or "?" in row.url:
            problems.append(f"{name}: the address is not a plain https address")
        if row.source not in registered:
            problems.append(f"{name}: the source {row.source!r} is not registered")
        if not re.fullmatch(r"[0-9a-f]{64}", row.sha256) or row.bytes <= 0:
            problems.append(f"{name}: no size or no SHA-256")
    return problems


def test_table_public_rows_are_https_and_sourced() -> None:
    sources = (ROOT / "docs" / "evidence" / "sources.md").read_text(encoding="utf-8")
    table = fetch.rows()
    assert fetch.public_names() == ("freerouting",) and set(table) == {"freerouting", "_selftest"}
    assert table_problems(table, sources) == []
    row = table["freerouting"]
    bad = {
        "a": dataclasses.replace(row, url="http://example.org/tool.jar"),
        "b": dataclasses.replace(row, source="S-9999"),
        "c": dataclasses.replace(row, url=row.url + "?token=1"),
        "_hidden": dataclasses.replace(row, name="_hidden", url="package:", source=""),
    }
    assert table_problems(bad, sources) == [
        "a: the address is not a plain https address",
        "b: the source 'S-9999' is not registered",
        "c: the address is not a plain https address",
    ]


def test_table_selftest_row_matches_its_packaged_file() -> None:
    row = fetch.rows()["_selftest"]
    data = fetch.read_package(row)
    assert row.hidden and row.packaged and row.file == "fetch-selftest.txt"
    assert fetch.matches(row, data) and not fetch.matches(row, data + b"\n")
    assert b"\r" not in data  # LF in every checkout, so the digest is the same everywhere


# --- The request ----------------------------------------------------------------------------------


class _Response(BytesIO):
    def __enter__(self) -> _Response:
        return self


def test_download_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """One request to the row's address, one added header, a timeout, and at most ``bytes + 1`` read."""
    seen: dict[str, Any] = {}

    class Opener:
        def open(self, request: urllib.request.Request, timeout: float) -> _Response:
            seen.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout,
                        method=request.get_method(), data=request.data)  # fmt: skip
            return _Response(b"x" * 100)

    monkeypatch.setattr(fetch, "_opener", lambda: Opener())
    row = dataclasses.replace(fetch.rows()["freerouting"], bytes=10)
    assert fetch.download(row) == b"x" * 11
    assert seen == {
        "url": row.url,
        "headers": {"User-agent": f"fenolite/{__version__}"},
        "timeout": 60,
        "method": "GET",
        "data": None,
    }


def test_download_refuses_an_address_that_is_not_plain_https(no_network: list[str]) -> None:
    row = fetch.rows()["freerouting"]
    for url in ("http://example.org/tool.jar", "file:///tmp/tool.jar", "package:", row.url + "?a=1"):
        with pytest.raises(ValueError, match="not a plain https address"):
            fetch.download(dataclasses.replace(row, url=url))
    assert no_network == []


def test_download_follows_a_redirect_only_to_https() -> None:
    opener = fetch._opener()  # pyright: ignore[reportPrivateUsage]
    handlers = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert len(handlers) == 1  # the rule replaces the default handler
    request = urllib.request.Request("https://example.org/tool.jar")
    with pytest.raises(urllib.error.URLError, match="not https"):
        handlers[0].redirect_request(request, BytesIO(), 302, "Found", Message(), "http://example.org/x")
    followed = handlers[0].redirect_request(
        request, BytesIO(), 302, "Found", Message(), "https://example.net/tool.jar"
    )
    assert followed is not None and followed.full_url == "https://example.net/tool.jar"


# --- The command ----------------------------------------------------------------------------------


def test_dry_run_of_the_real_row_makes_no_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path, no_network: list[str]
) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--dry-run")
    assert code == 0
    result, row = env["result"], fetch.rows()["freerouting"]
    destination = (tools / "freerouting" / JAR).as_posix()
    assert result["plan"] == [
        {"path": destination, "kind": "tool", "bytes": 64076787, "sha256": row.sha256, "overwrite": False}
    ]
    assert result["path"] == destination and result["licence"] == "GPL-3.0"
    assert result["origin"] == "network" and result["installed"] is False and result["env"] == {}
    assert result["url"] == row.url and result["version"] == "2.4.1" and result["file"] == JAR
    assert any("Java 25" in need for need in result["needs"])
    assert set(result) == {"name", "version", "file", "path", "bytes", "sha256", "url", "licence", "origin",
                           "installed", "needs", "env", "plan"}  # fmt: skip
    assert env["evidence"]["level"] == "UNVERIFIED" and env["receipt"] is None
    assert no_network == [] and not tools.exists()


def test_dry_run_reads_no_from_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path, no_network: list[str]
) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--from", "absent.jar", "--dry-run")
    assert code == 0 and env["result"]["origin"] == "file" and not tools.exists()


def test_confirmation_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path, no_network: list[str]
) -> None:
    code, env, error, _ = run(monkeypatch, tmp_path, "fetch", "freerouting")
    assert code == 4 and error["code"] == "FEN-4001" and env["result"]["plan"]
    assert no_network == [] and not tools.exists()


def test_install_from_a_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path, no_network: list[str]
) -> None:
    row = _small_row(monkeypatch)
    (tmp_path / "copy.jar").write_bytes(SMALL)
    code, env, error, _ = run(
        monkeypatch, tmp_path, "fetch", "freerouting", "--from", "copy.jar", "--confirm"
    )
    assert code == 0, error
    destination = tools / "freerouting" / JAR
    assert destination.read_bytes() == SMALL and env["result"]["origin"] == "file"
    assert env["receipt"]["written"] == [{"path": destination.as_posix(), "sha256": row.sha256}]
    code, env, _, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--from", "copy.jar", "--confirm")
    assert code == 0 and env["result"]["installed"] is True and env["receipt"] is None
    code, env, _, _ = run(monkeypatch, tmp_path, "fetch", "freerouting")  # nothing to confirm either
    assert code == 0 and "plan" not in env["result"] and no_network == []


def test_wrong_file_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path, no_network: list[str]
) -> None:
    row = _small_row(monkeypatch)
    for name, data in (("other.jar", SMALL[::-1]), ("longer.jar", SMALL + b"more")):
        (tmp_path / name).write_bytes(data)
        code, _, error, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--from", name, "--confirm")
        assert code == 3 and error["code"] == "FEN-3006", name
        assert row.sha256 in error["message"] and not tools.exists()
    assert hashlib.sha256(SMALL[::-1]).hexdigest() != row.sha256
    code, _, error, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--from", "other.jar", "--confirm")
    assert hashlib.sha256(SMALL[::-1]).hexdigest() in error["message"]


def test_missing_from_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path) -> None:
    _small_row(monkeypatch)
    code, _, error, _ = run(
        monkeypatch, tmp_path, "fetch", "freerouting", "--from", "absent.jar", "--confirm"
    )
    assert code == 3 and error["code"] == "FEN-3001" and not tools.exists()


def test_network_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path) -> None:
    def fail(_row: FetchRow) -> bytes:
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(fetch, "download", fail)
    code, env, error, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--confirm")
    assert code == 6 and error["code"] == "FEN-6003" and error["retryable"] is True
    assert "--from FILE" in error["hint"] and "no route to host" in error["message"]
    assert fetch.rows()["freerouting"].url in error["message"]
    assert env["ok"] is False and not tools.exists()


def test_network_install_and_a_cut_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path
) -> None:
    """The bytes of the request are installed when they match, and refused with ``FEN-3006`` when they do
    not: the size and the digest decide, whatever the origin."""
    _small_row(monkeypatch)
    monkeypatch.setattr(fetch, "download", lambda _row: SMALL[:-1])
    code, _, error, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--confirm")
    assert code == 3 and error["code"] == "FEN-3006" and not tools.exists()
    monkeypatch.setattr(fetch, "download", lambda _row: SMALL)
    code, env, _, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--confirm")
    assert code == 0 and env["result"]["origin"] == "network"
    assert (tools / "freerouting" / JAR).read_bytes() == SMALL


def test_dir_names_another_folder_and_the_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path, no_network: list[str]
) -> None:
    _small_row(monkeypatch)
    (tmp_path / "copy.jar").write_bytes(SMALL)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "fetch", "freerouting", "--dir", "kept", "--from", "copy.jar", "--confirm"
    )
    assert code == 0 and (tmp_path / "kept" / JAR).read_bytes() == SMALL and not tools.exists()
    assert env["result"]["path"] == f"kept/{JAR}"
    assert env["result"]["env"] == {"FENOLITE_FREEROUTING_JAR": str(tmp_path / "kept" / JAR)}


def test_selftest_row_installs_the_packaged_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_network: list[str]
) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "fetch", "_selftest", "--dir", "tools", "--confirm")
    assert code == 0 and env["result"]["origin"] == "package" and env["result"]["env"] == {}
    assert [w["path"] for w in env["receipt"]["written"]] == ["tools/fetch-selftest.txt"]
    assert (tmp_path / "tools" / "fetch-selftest.txt").read_bytes() == fetch.read_package(
        fetch.rows()["_selftest"]
    )


def test_unknown_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_network: list[str]) -> None:
    for argv in (("fetch", "kicad"), ("fetch",)):
        code, _, error, _ = run(monkeypatch, tmp_path, *argv)
        assert code == 2 and error["code"] == "FEN-2001"
        assert "freerouting" in error["hint"] and "_selftest" not in error["hint"]


def test_relative_folder_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(TOOLS_ENV, "tools")
    code, _, error, _ = run(monkeypatch, tmp_path, "fetch", "freerouting", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001" and TOOLS_ENV in error["message"]
    assert _snapshot(tmp_path) == []


def test_fetch_sends_no_design_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "capabilities", "--no-tools")
    assert code == 0 and env["result"]["sends_data_offsite"] is False
    entry = next(c for c in env["result"]["commands"] if c["name"] == "fetch")
    assert entry["mutates"] is True and entry["hidden"] is False


# --- No connection outside fetch ------------------------------------------------------------------


@posix_tools
def test_no_connection_outside_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tools: Path) -> None:
    """``route``, ``doctor`` and ``capabilities`` exit as they do with every way to the network closed."""
    board = tmp_path / "two_pads.kicad_pcb"
    board.write_text(write_board(two_pads().design, target=10).text, encoding="utf-8")
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(ROOT / "tests/data/specctra/two_pads.ses"))
    monkeypatch.delenv("FAKE_JAVA_MODE", raising=False)
    monkeypatch.delenv("FENOLITE_FREEROUTING_JAR", raising=False)
    jar = str(create_fake_jar(tmp_path))
    commands: tuple[tuple[str, ...], ...] = (
        ("route", board.name, "--router", "freerouting", "--router-path", jar, "--allow-offsite",
         "--out", "routed.kicad_pcb", "--dry-run"),
        ("route", board.name, "--router", "freerouting", "--dry-run"),  # no jar: exit 6, and no request
        ("doctor", "--no-run"),
        ("capabilities", "--no-tools"),
    )  # fmt: skip

    def outcomes() -> list[tuple[int, object, object]]:
        found: list[tuple[int, object, object]] = []
        for argv in commands:
            code, env, error, _ = run(monkeypatch, tmp_path, *argv)
            found.append((code, env.get("result", {}).get("routed"), error.get("code")))
        return found

    before = outcomes()
    assert [code for code, _, _ in before] == [0, 6, 0, 0] and before[0][1] == ["A"]
    tried: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        tried.append(repr(args[:2]))
        raise AssertionError("a network connection was opened")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert outcomes() == before and tried == [] and not tools.exists()
