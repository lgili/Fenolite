# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic element diffs; repeated keys retain every shape instead of losing geometry."""

from __future__ import annotations

import difflib
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SvgDiff:
    added: int
    removed: int
    changed: int
    lines: tuple[str, ...]


def _elements(data: bytes) -> tuple[dict[tuple[str, str, str], list[str]], list[str]]:
    items: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    if not data:
        return items, []
    for element in ET.fromstring(data).iter():
        if element.get("data-item"):
            key = (element.get("class", ""), element.get("data-item", ""), element.get("data-layer", ""))
            items[key].append(ET.tostring(element, encoding="unicode").strip())
    unkeyed = [line for line in data.decode("utf-8").splitlines() if "data-item=" not in line]
    return items, unkeyed


def compare(before: bytes, after: bytes) -> SvgDiff:
    old, old_lines = _elements(before)
    new, new_lines = _elements(after)
    added = removed = changed = 0
    lines: list[str] = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key, []), new.get(key, [])
        shared = min(len(a), len(b))
        for left, right in zip(a[:shared], b[:shared], strict=True):
            if left != right:
                changed += 1
                lines += [f"- {left}", f"+ {right}"]
        removed += len(a) - shared
        added += len(b) - shared
        lines += [f"- {line}" for line in a[shared:]]
        lines += [f"+ {line}" for line in b[shared:]]
    if old_lines != new_lines:
        for tag, i, j, k, stop in difflib.SequenceMatcher(
            a=old_lines, b=new_lines, autojunk=False
        ).get_opcodes():
            if tag != "equal":
                if tag == "replace":
                    changed += min(j - i, stop - k)
                added += max(0, (stop - k) - (j - i))
                removed += max(0, (j - i) - (stop - k))
                lines += [f"- {line}" for line in old_lines[i:j]]
                lines += [f"+ {line}" for line in new_lines[k:stop]]
    return SvgDiff(added, removed, changed, tuple(lines[:20]))
