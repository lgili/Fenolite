# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Help pages read into a command matrix (capability kicad-oracle, "Subcommand matrix from help text";
change c0013). Pages are authored for these tests; no ``kicad-cli`` runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.helpmatrix import (
    MATRIX,
    HelpPage,
    command_matrix,
    parse_help,
    probe_id,
    row_key,
)


def test_group_page() -> None:
    page = parse_help("Usage: kicad-cli pcb [--help] {drc,export,upgrade}\n\nOptional arguments:\n")
    assert page == HelpPage(frozenset({"drc", "export", "upgrade"}), frozenset({"--help"}))


def test_leaf_page() -> None:
    page = parse_help("Usage: kicad-cli pcb drc [--help] [--format VAR] [--severity-all] INPUT_FILE\n")
    assert page is not None
    assert page.options == {"--help", "--format", "--severity-all"}
    assert page.subcommands == frozenset()


def test_repeatable_option_and_short_prefix() -> None:
    page = parse_help("Usage: drc [--define-var KEY=VALUE]... [--output OUTPUT_FILE] INPUT_FILE")
    assert page is not None
    assert page.options == {"--define-var", "--output"}


def test_page_without_a_usage_line() -> None:
    assert parse_help("Error: unknown command") is None
    assert parse_help("") is None


def test_row_key_and_probe_id() -> None:
    assert row_key(("pcb", "drc")) == "pcb drc"
    assert row_key(("pcb", "drc"), "--refill-zones") == "pcb drc --refill-zones"
    assert probe_id(("pcb", "drc"), "--refill-zones") == "check-help-pcb-drc-refill-zones"
    assert probe_id(("pcb", "export", "ipcd356")) == "check-help-pcb-export-ipcd356"


def test_matrix_is_closed() -> None:
    commands = [" ".join(e.command) for e in MATRIX]
    assert len(commands) == len(set(commands)) == 21
    for added in ("pcb export step", "pcb export pdf", "pcb export dxf", "sch export pdf"):  # c0116
        assert added in commands
    assert MATRIX[0].command == ("pcb", "drc")
    assert MATRIX[0].options == (
        "--format",
        "--severity-all",
        "--schematic-parity",
        "--refill-zones",
        "--save-board",
    )


class _FakeCli(KicadCli):
    """Serves authored help pages by command words; records the pages it was asked for."""

    def __init__(self, pages: Mapping[tuple[str, ...], str], version: str = "10.0.6") -> None:
        super().__init__(Path("kicad-cli"))
        self.pages = pages
        self.asked: list[tuple[str, ...]] = []
        self._version = version

    def run(
        self, args: Sequence[str], *, files: Mapping[str, Path], env: Mapping[str, str] | None = None
    ) -> CliRun:
        words = tuple(args[:-1])
        assert args[-1] == "--help" and not files
        self.asked.append(words)
        text = self.pages.get(words)
        if text is None:
            return CliRun("exit", 1, "", "Error: unknown command", {})
        return CliRun("exit", 0, text, "", {})


TEN = {
    (): "Usage: kicad-cli [--version] [--help] {fp,jobset,pcb,sch,sym,version}",
    ("pcb",): "Usage: kicad-cli pcb [--help] {drc,export,import,render,upgrade}",
    (
        "pcb",
        "export",
    ): "Usage: pcb export [--help] {drill,dxf,gerbers,ipc2581,ipcd356,odb,pdf,pos,stats,step,svg}",
    ("pcb", "drc"): "Usage: pcb drc [--help] [--format FORMAT] [--schematic-parity] [--severity-all] "
    "[--refill-zones] [--save-board] INPUT_FILE",
    ("fp",): "Usage: kicad-cli fp [--help] {export,upgrade}",
    ("sym",): "Usage: kicad-cli sym [--help] {export,upgrade}",
    ("sch",): "Usage: kicad-cli sch [--help] {erc,export,upgrade}",
    ("sch", "export"): "Usage: sch export [--help] {netlist,pdf}",
    ("jobset",): "Usage: kicad-cli jobset [--help] {run}",
}


def test_matrix_from_pages() -> None:
    cli = _FakeCli(TEN)
    matrix = command_matrix(cli)
    assert matrix.version == "10.0.6"
    assert matrix.unparsed == ()
    assert all(matrix.rows.values())
    assert len(matrix.rows) == 21 + 5  # every command and every pcb drc option
    for row in ("pcb export step", "pcb export pdf", "pcb export dxf", "sch export pdf"):
        assert matrix.rows[row] is True
    assert len(cli.asked) == 9


def test_absent_parent_gives_absent_rows_without_a_run() -> None:
    pages = {k: v for k, v in TEN.items() if k[:1] != ("jobset",)}
    pages[()] = "Usage: kicad-cli [--version] [--help] {fp,pcb,sch,sym,version}"
    cli = _FakeCli(pages)
    matrix = command_matrix(cli)
    assert matrix.rows["jobset run"] is False
    assert ("jobset",) not in cli.asked


def test_absent_command_gives_absent_options() -> None:
    pages = dict(TEN)
    pages[("pcb",)] = "Usage: pcb [--help] {export,render}"
    matrix = command_matrix(_FakeCli(pages))
    assert matrix.rows["pcb drc"] is False
    assert matrix.rows["pcb drc --format"] is False
    assert matrix.rows["pcb upgrade"] is False


def test_unparsed_page_leaves_its_rows_out() -> None:
    pages = dict(TEN)
    pages[("pcb", "export")] = "no usage here"
    matrix = command_matrix(_FakeCli(pages))
    assert matrix.unparsed == ("kicad-cli pcb export --help",)
    assert "pcb export svg" not in matrix.rows
    assert matrix.rows["pcb drc --save-board"] is True
