# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designators of the components of a repeated sheet (capability altium-import, "Channel designators";
change c0083).

A sheet that several sheet symbols name is instantiated once per symbol, and a sheet symbol whose
designator is ``Repeat(NAME, first, last)`` once per index; each instance is a channel. Altium names the
components of a channel with the designator format of the project file
(``ChannelDesignatorFormatString``), a text with keywords, and the room naming style
(``ChannelRoomNamingStyle``) that decides what ``$RoomName`` stands for. The facts and their labels are in
``docs/formats/altium/connectivity.md``, "Channels". A format or a style outside those facts is never
guessed: the component then gets ``<designator>@<channel>``, a form no Altium format produces.
"""

# evidence: see import_evidence

from __future__ import annotations

import re
from collections.abc import Sequence

FLAT_STYLES: frozenset[int] = frozenset({0, 1})
"""Room naming styles without the path: the room of a channel is named by its own sheet symbol."""
PATH_STYLES: frozenset[int] = frozenset({2, 3, 4})
"""Room naming styles that join the sheet symbols of the path with the level separator."""
NUMERIC_STYLES: frozenset[int] = frozenset({0, 2})
"""Styles that write the index of a ``Repeat`` channel as a number (``CH1``)."""
ALPHA_STYLES: frozenset[int] = frozenset({1, 3})
"""Styles that write the index of a ``Repeat`` channel as a letter (``CHA``). The fifth style mixes both
in a way no source states: a ``Repeat`` channel under it is not named."""
KEYWORDS: tuple[str, ...] = (
    "$ComponentPrefix",
    "$ComponentIndex",
    "$Component",
    "$RoomName",
    "$ChannelPrefix",
    "$ChannelIndex",
    "$ChannelAlpha",
)
"""The keywords of a designator format, the longer first so that ``$Component`` does not eat a longer one."""
UNRESOLVED: frozenset[str] = frozenset({"$ChannelIndex", "$ChannelAlpha"})
"""Keywords that need the index of a ``Repeat`` statement, which a plain sheet symbol does not have."""
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
FALLBACK = "{designator}@{channel}"
_KEYWORD = re.compile("|".join(re.escape(word) for word in KEYWORDS))
_SPLIT = re.compile(r"^(\D*)(.*)$", re.DOTALL)


def channel_alpha(index: int | None) -> str | None:
    """The channel index as a letter, ``A`` for 1 to ``Z`` for 26; ``None`` for no index and for an index
    outside that range, which no source gives a letter."""
    if index is None or not 1 <= index <= len(ALPHABET):
        return None
    return ALPHABET[index - 1]


def _level(name: str, index: int | None, style: int | None) -> str | None:
    """One sheet symbol of a room name: its designator, or the channel identifier with the index."""
    if index is None:
        return name
    if style in NUMERIC_STYLES:
        return f"{name}{index}"
    letter = channel_alpha(index) if style in ALPHA_STYLES else None
    return None if letter is None else f"{name}{letter}"


def room_name(
    names: Sequence[str], style: int | None, separator: str, indexes: Sequence[int | None] | None = None
) -> str | None:
    """The room name of the channel whose sheet symbols from the top are ``names``, or ``None`` for a
    style whose meaning is not recorded. ``indexes`` holds, per sheet symbol, the channel index of its
    ``Repeat`` statement or ``None``; a flat style under a ``Repeat`` statement higher up would name two
    rooms alike, so it gives ``None`` there."""
    if not names:
        return None
    found = tuple(indexes) if indexes is not None else (None,) * len(names)
    if len(found) != len(names):
        return None
    if style in FLAT_STYLES:
        if any(index is not None for index in found[:-1]):
            return None
        return _level(names[-1], found[-1], style)
    if style in PATH_STYLES:
        levels: list[str] = []
        for name, index in zip(names, found, strict=True):
            level = _level(name, index, style)
            if level is None:
                return None
            levels.append(level)
        return separator.join(levels)
    return None


def channel_designator(
    format: str,  # noqa: A002 (the project file's own word)
    designator: str,
    names: Sequence[str],
    *,
    style: int | None = 0,
    separator: str = "_",
    indexes: Sequence[int | None] | None = None,
) -> str | None:
    """The designator of the component ``designator`` in the channel ``names`` under the designator format
    ``format``, or ``None`` when the format holds a keyword that cannot be resolved for this channel, a
    ``$`` that starts no keyword, or needs a room name the style does not give. ``names`` are the
    designators of the sheet symbols from the top, for a ``Repeat`` statement its channel identifier, and
    ``indexes`` the channel index of each (``None`` for a plain sheet symbol and when left out). A format
    that would give the channels of one ``Repeat`` statement one designator gives ``None``."""
    if not format or not names or not designator:
        return None
    match = _SPLIT.match(designator)
    assert match is not None
    index = indexes[-1] if indexes else None
    values = {
        "$Component": designator,
        "$ComponentPrefix": match.group(1),
        "$ComponentIndex": match.group(2),
        "$ChannelPrefix": names[-1],
    }
    if "$RoomName" in format:
        room = room_name(names, style, separator, indexes)
        if room is None:
            return None
        values["$RoomName"] = room
    if "$ChannelIndex" in format:
        if index is None:
            return None
        values["$ChannelIndex"] = str(index)
    if "$ChannelAlpha" in format:
        letter = channel_alpha(index)
        if letter is None:
            return None
        values["$ChannelAlpha"] = letter
    if "$" in _KEYWORD.sub("", format):
        return None
    if index is not None and not any(word in format for word in ("$RoomName", *sorted(UNRESOLVED))):
        return None  # nothing of the format tells the channels of one Repeat statement apart
    return _KEYWORD.sub(lambda found: values[found.group(0)], format)


def fallback(designator: str, names: Sequence[str]) -> str:
    """The designator of a channel component whose format cannot be applied."""
    return FALLBACK.format(designator=designator, channel="/".join(names))


__all__ = [
    "ALPHA_STYLES",
    "FALLBACK",
    "FLAT_STYLES",
    "KEYWORDS",
    "NUMERIC_STYLES",
    "PATH_STYLES",
    "channel_alpha",
    "channel_designator",
    "fallback",
    "room_name",
]
