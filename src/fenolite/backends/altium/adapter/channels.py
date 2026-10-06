# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designators of the components of a repeated sheet (capability altium-import, "Channel designators";
change c0083).

A sheet that several sheet symbols name is instantiated once per symbol, and each instance is a channel.
Altium names the components of a channel with the designator format of the project file
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
FALLBACK = "{designator}@{channel}"
_KEYWORD = re.compile("|".join(re.escape(word) for word in KEYWORDS))
_SPLIT = re.compile(r"^(\D*)(.*)$", re.DOTALL)


def room_name(names: Sequence[str], style: int | None, separator: str) -> str | None:
    """The room name of the channel whose sheet symbols from the top are ``names``, or ``None`` for a
    style whose meaning is not recorded."""
    if not names:
        return None
    if style in FLAT_STYLES:
        return names[-1]
    if style in PATH_STYLES:
        return separator.join(names)
    return None


def channel_designator(
    format: str,  # noqa: A002 (the project file's own word)
    designator: str,
    names: Sequence[str],
    *,
    style: int | None = 0,
    separator: str = "_",
) -> str | None:
    """The designator of the component ``designator`` in the channel ``names`` under the designator format
    ``format``, or ``None`` when the format holds a keyword that cannot be resolved for this channel, a
    ``$`` that starts no keyword, or needs a room name the style does not give."""
    if not format or not names or not designator:
        return None
    match = _SPLIT.match(designator)
    assert match is not None
    values = {
        "$Component": designator,
        "$ComponentPrefix": match.group(1),
        "$ComponentIndex": match.group(2),
        "$ChannelPrefix": names[-1],
    }
    if "$RoomName" in format:
        room = room_name(names, style, separator)
        if room is None:
            return None
        values["$RoomName"] = room
    if any(word in format for word in UNRESOLVED) or "$" in _KEYWORD.sub("", format):
        return None
    return _KEYWORD.sub(lambda found: values[found.group(0)], format)


def fallback(designator: str, names: Sequence[str]) -> str:
    """The designator of a channel component whose format cannot be applied."""
    return FALLBACK.format(designator=designator, channel="/".join(names))


__all__ = [
    "FALLBACK",
    "FLAT_STYLES",
    "KEYWORDS",
    "PATH_STYLES",
    "channel_designator",
    "fallback",
    "room_name",
]
