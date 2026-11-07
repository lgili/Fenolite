# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored-only observation, restoration and bounds; the original operation stays in control."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import _buildgeometry as observer
import pytest
from _buildgeometry import METHODS, ROOT, Trace, observe, summary

from fenolite.backends.altium import pour
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.geometry.polygon import Polygon


def enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("FENOLITE_BUILD_BYTE_DIAGNOSTICS", str(tmp_path / "fenolite-byte-diagnostics"))
    return tmp_path / "out"


@pytest.mark.parametrize("invalid", ["private-source", "other-row", "private-context", "edited-source"])
def test_filter_precedes_registration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, invalid: str) -> None:
    out = enabled(monkeypatch, tmp_path)
    originals = {name: getattr(ClipperBackend, name) for name in METHODS}
    if invalid == "private-context":
        (tmp_path / "devices").mkdir()
    if invalid == "edited-source":
        monkeypatch.setitem(observer.SOURCE_FILES, "examples/board_40parts/design.py", "0" * 64)
    with observe(
        "other" if invalid == "other-row" else "board_40parts",
        "altium",
        out,
        tmp_path if invalid == "private-source" else ROOT,
    ) as trace:
        assert trace is None
        assert all(getattr(ClipperBackend, name) is value for name, value in originals.items())
    assert not (tmp_path / "fenolite-byte-diagnostics").exists()


def test_original_exception_restores_methods(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = enabled(monkeypatch, tmp_path)
    originals = {name: getattr(ClipperBackend, name) for name in METHODS}
    exact_original = pour._certified_neck_cut
    with pytest.raises(RuntimeError, match="original producer"):
        with observe("board_40parts", "altium", out, ROOT) as trace:
            assert trace is not None
            raise RuntimeError("original producer")
    assert all(getattr(ClipperBackend, name) is value for name, value in originals.items())
    assert pour._certified_neck_cut is exact_original


def test_exact_final_cut_is_observed_once_and_restored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = enabled(monkeypatch, tmp_path)
    subject = (Polygon(((0, 0), (20, 0), (20, 20), (0, 20))),)
    cut = (Polygon(((0, 0), (2, 0), (0, 2))),)
    calls = []

    def original(subject: Any, cut: Any, tol: int) -> Any:
        calls.append((subject, cut, tol))
        return subject

    monkeypatch.setattr(pour, "_certified_neck_cut", original)
    with observe("board_40parts", "altium", out, ROOT) as trace:
        assert trace is not None
        assert pour._certified_neck_cut(subject, cut, 1) is subject
        assert trace.seen == 1 and trace.errors == 0 and not trace.limited
        assert trace.rows == [
            {
                "index": 0,
                "method": "certified-neck-cut",
                "inputs": [summary(subject), summary(cut)],
                "parameters": {"tol": 1},
                "output": summary(subject),
            }
        ]
    assert len(calls) == 1 and calls[0][0] is subject and calls[0][1] is cut
    assert pour._certified_neck_cut is original


def test_hash_error_never_repeats_or_changes_operation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = enabled(monkeypatch, tmp_path)
    calls = []
    result = object()

    def original(self: Any, polys: Any) -> Any:
        calls.append(polys)
        return result

    def fail(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("private observer detail")

    monkeypatch.setattr(ClipperBackend, "union", original)
    monkeypatch.setattr(observer, "summary", fail)
    operand = ["original operand"]
    with observe("board_40parts", "altium", out, ROOT) as trace:
        assert trace is not None
        assert ClipperBackend.__new__(ClipperBackend).union(operand) is result
        assert trace.errors == 1 and trace.seen == 1 and not trace.rows
    assert calls == [operand] and calls[0] is operand
    assert "private observer detail" not in json.dumps(trace.data())
    assert ClipperBackend.union is original


def test_setup_error_allows_original_body(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = enabled(monkeypatch, tmp_path)

    def fail(*_args: Any) -> bool:
        raise RuntimeError("observer setup")

    monkeypatch.setattr(observer, "authored_source", fail)
    original = ClipperBackend.offset
    with observe("board_40parts", "altium", out, ROOT) as trace:
        assert trace is None and ClipperBackend.offset is original


def test_hash_is_canonical_and_does_not_expose_or_mutate_vertices() -> None:
    a = Polygon(((0, 0), (20, 0), (20, 20), (0, 20)))
    b = Polygon(tuple(reversed(a.outer[1:] + a.outer[:1])))
    before = a.outer
    assert summary(a)["sha256"] == summary(b)["sha256"]
    assert summary(a)["ordered_sha256"] != summary(b)["ordered_sha256"]
    assert a.outer is before
    assert set(summary(a)) == {"sha256", "ordered_sha256", "polygons", "holes", "vertices"}


def test_operation_and_byte_limits_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observer, "MAX_OPS", 1)
    trace = Trace()
    trace.append({"index": 1})
    trace.append({"index": 2})
    assert len(trace.rows) == 1 and trace.limited
    monkeypatch.setattr(observer, "MAX_TRACE_BYTES", 1)
    trace = Trace()
    trace.append({"index": 1})
    assert trace.rows == [] and trace.limited


def test_vertex_limit_precedes_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observer, "MAX_VERTICES", 3)
    with pytest.raises(ValueError, match="vertex limit"):
        summary(Polygon(((0, 0), (20, 0), (20, 20), (0, 20))))
