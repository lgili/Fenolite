# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Module-local, hash-bound owner measurements; every sheet keeps its strict proof (c0380)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path

import _drawn_corpus as census

from fenolite.backends.kicad.cli import KicadCli

PER_CASE_STORES = ("FENOLITE_STATE_DIR", "FENOLITE_LIBRARY_DIR")


def _environment() -> dict[str, str] | None:
    # Pytest changes these empty locations per case. Nonempty stores could be dependencies:
    # decline reuse instead of assuming their contents or locations are irrelevant.
    for name in PER_CASE_STORES:
        value = os.environ.get(name)
        if not value:
            return None  # An unset override could select a nonempty user/default store.
        path = Path(value)
        try:
            if path.exists() and (not path.is_dir() or any(path.iterdir())):
                return None
        except OSError:
            return None
    return {
        key: value
        for key, value in os.environ.items()
        if key not in (*PER_CASE_STORES, "PYTEST_CURRENT_TEST")
    }


def _snapshot(folder: Path, inputs: Sequence[census.Input]) -> list[tuple[str, str, str, str]]:
    return [
        (i.id, i.relative, i.sha256, hashlib.sha256((folder / i.relative).read_bytes()).hexdigest())
        for i in inputs
    ]


class OwnerMeasurements:
    """Opt-in fixture store, never a persistent cache or a replacement for measure()."""

    def __init__(self) -> None:
        self._reports: dict[tuple[KicadCli, str], dict] = {}

    def measure(
        self,
        folder: Path,
        root_file: str,
        inputs: Sequence[census.Input],
        cli: KicadCli,
        *,
        owner: str,
        manifest_sha256: str,
        ident: str,
        major: int,
        native_version: str,
        code_commit: str = "",
    ) -> dict:
        def signature() -> str | None:
            try:
                files = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
                if files != {i.relative for i in inputs}:
                    return None
                snapshot = _snapshot(folder, inputs)
            except OSError:
                return None
            environment = _environment()
            if environment is None or any(expected != actual for _, _, expected, actual in snapshot):
                return None
            data = {
                "owner": owner,
                "root": root_file,
                "manifest": manifest_sha256,
                "inputs": snapshot,
                "major": major,
                "native_version": native_version,
                "commit": code_commit,
                "cwd": str(Path.cwd()),
                "tool": (str(cli.path), cli.timeout, getattr(cli, "image", None)),
                "environment": environment,
            }
            # Retain only a digest: no source paths, input bytes or inherited environment values.
            return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()

        fingerprint = signature()
        key = (cli, fingerprint) if fingerprint is not None else None
        reused = key is not None and key in self._reports
        if reused:
            report = copy.deepcopy(self._reports[key])
        else:
            report = census.measure(
                folder,
                root_file,
                inputs,
                cli,
                ident=ident,
                major=major,
                native_version=native_version,
                code_commit=code_commit,
            )
            # Recheck every copied byte, including project/libraries, after the whole pipeline.
            # A successful preflight must not seed reuse if inputs/state change during measurement.
            after = signature() if key is not None else None
            if key is not None and after == fingerprint:
                if report.get("status") in {"equal", "refused", "differs"}:
                    self._reports[key] = copy.deepcopy(report)
            elif key is not None:
                report.update(
                    status="invalid-cache",
                    refusal={"stage": "reuse", "code": "measurement-changed"},
                )
                fingerprint = None
        report["id"] = ident
        report["measurement"] = {"owner_id": owner, "fingerprint": fingerprint, "reused": reused}
        return report
