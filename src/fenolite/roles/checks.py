# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The phase-0 role checks: the measures of ``roles.measure`` judged against the role limits (change c0222;
capability net-roles, "Hot and gate loop checks", "Kelvin attachment", "Kelvin pair and switching
distance", "Current capacity of role copper", "Returns and high voltage" and "Finding severities";
``docs/roles.md``, "Checks").

Each finding names its limit (key, value and origin: ``profile`` with its source id, ``override`` or
``requirements``). A finding against a profile default is a ``warning``; one against the user's limit on a
confirmed or declared role is an ``error`` (``codes.severity``). The analyses' findings against derived rows
never appear: ``analysis.path-exceeded``, ``analysis.neck-narrow``, ``analysis.return-split`` and
``analysis.sense-shared`` are replaced by the ``roles.*`` findings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any

from fenolite.core.errors import Issue
from fenolite.core.requirement_table import Bound, RequirementRow, Side, Source
from fenolite.model.rules import RoleSet
from fenolite.roles import profile
from fenolite.roles.codes import issue, severity
from fenolite.roles.measure import CURRENT_KINDS, Measure, Measured, RoleBoard

HYPOTHESES = {
    "loop": ("H-G-ROLE-LOOP-RATIO",),
    "kelvin": ("H-G-ROLE-KELVIN-PAIR",),
    "attachment": ("H-G-ROLE-KELVIN-EDGE",),
    "gate_return": ("H-G-ROLE-KELVIN-EDGE",),
    "near": ("H-G-ROLE-NEAR-SW",),
    "path": ("H-G-ROLE-CURRENT",),
    "neck": ("H-G-ROLE-CURRENT",),
}
"""The role hypotheses that each kind of measure relies on (``docs/hypotheses.md``)."""


def _places(value: int, scale: int, places: int) -> str:
    """``value / scale`` with ``places`` decimals, rounded half up, computed exactly."""
    step = Fraction(1, 10**places)
    whole = Fraction(value, scale) / step
    rounded = int(whole + Fraction(1, 2)) if whole >= 0 else -int(-whole + Fraction(1, 2))
    sign = "-" if rounded < 0 else ""
    digits = str(abs(rounded)).rjust(places + 1, "0")
    return f"{sign}{digits[:-places]}.{digits[-places:]}"


def mm(value: int) -> str:
    """Nanometres as millimetres with up to three decimals."""
    return _places(value, 1_000_000, 3).rstrip("0").rstrip(".")


def mm2(value: int) -> str:
    """Square nanometres as square millimetres with two decimals."""
    return _places(value, profile.MM2, 2)


def _origin(roles: RoleSet, kind: str, name: str) -> str:
    groups: Sequence[Any] = {"hot": roles.loops, "gate": roles.gates, "kelvin": roles.kelvins}[kind]
    return next((group.origin for group in groups if group.name == name), "inferred")


def _net_source(roles: RoleSet, net: str | None) -> str:
    role = roles.role_of(net) if net is not None else None
    return role.source if role is not None else "inferred"


def _user(limit: profile.Limit) -> bool:
    return limit.origin in ("override", "requirements")


def _loop(board: RoleBoard, measure: Measure) -> list[Issue]:
    values = measure.values
    kind, name, roles = values["group"], measure.subject, board.roles
    origin = _origin(roles, kind, name)
    pads = ", ".join(values["pads"])
    what = {"hot": "hot loop", "gate": "gate loop", "kelvin": "Kelvin pair"}[kind]
    if values["open"]:
        legs = "; ".join(f"{start} to {end}" for start, end in values["open"])
        return [
            issue(
                "roles.loop-open",
                f"the {what} {name}: no copper joins {legs} on the board, so the loop is not routed there "
                "and its area is not judged",
                where=name,
                hint="route the connection, or refill the zones whose fill is missing",
            )
        ]
    area, bound, ratio = values["area_nm2"], values["bound_nm2"], values["ratio_permille"]
    if area is None:
        return []
    net = values["net"]
    group_kind = {"hot": "switch_node", "gate": "gate", "kelvin": "kelvin"}[kind]
    floor = profile.resolve("loop_bound_floor_nm2", roles.limits, net=net, kind=group_kind)
    reasons: list[tuple[str, profile.Limit]] = []
    if kind in ("hot", "gate"):
        largest = profile.resolve(
            "loop_max" if kind == "hot" else "gate_max", roles.limits, net=net, kind=group_kind
        )
        if largest.value is not None and area > largest.value:
            reasons.append((f"above the {mm2(largest.value)} mm² of {largest.text()}", largest))
    key = {"hot": "loop_ratio_max", "gate": "gate_ratio_max", "kelvin": "pair_ratio_max"}[kind]
    most = profile.resolve(key, roles.limits, net=net, kind=group_kind)
    judged = bound is not None and floor.value is not None and bound >= floor.value and ratio is not None
    if kind == "kelvin":
        flag = profile.resolve("kelvin_pair", roles.limits, net=net, kind=group_kind)
        judged = judged and bool(flag.value)
    if judged and most.value is not None and ratio is not None and bound is not None and ratio > most.value:
        reasons.append((f"{ratio}‰ of its placement bound of {mm2(bound)} mm², above {most.text()}", most))
    if not reasons:
        return []
    code = {"hot": "roles.loop-area", "gate": "roles.gate-loop", "kelvin": "roles.kelvin-apart"}[kind]
    limit = next((found for _, found in reasons if _user(found)), reasons[0][1])
    level = severity(code, source=origin, limit_source=limit.origin)
    text = f"the {what} {name} through {pads} encloses {mm2(area)} mm², " + " and ".join(
        r for r, _ in reasons
    )
    if kind == "kelvin":
        longest = max(values["legs"], key=lambda leg: leg[3])
        text += f"; its longest leg, {longest[0]} to {longest[1]}, is {mm(longest[3])} mm"
    hints = {
        "hot": "place the capacitor across the switches and keep the return under the supply",
        "gate": "place the driver at the switch and run the return beside or under the gate trace",
        "kelvin": "run the two sense lines as a coupled pair from the shunt to the amplifier",
    }
    return [issue(code, text, severity=level, where=name, hint=hints[kind])]


def _attachments(board: RoleBoard, done: Measured) -> list[Issue]:
    found: list[Issue] = []
    for pair, attachments in done.attachments:
        for attachment in attachments:
            net = attachment.net
            if attachment.shared:
                level = severity("roles.kelvin-shared", source=pair.origin, limit_source="rule")
                found.append(
                    issue(
                        "roles.kelvin-shared",
                        f"the sense branch of the Kelvin pair {pair.name} to {attachment.pad} reaches power "
                        f"copper before the pad: {', '.join(attachment.shared)} (S-0850)",
                        severity=level,
                        where=f"{pair.name}:{attachment.pad}",
                        hint="start the sense line on the shunt's own pad, on its inner half, apart from "
                        "the pour",
                    )
                )
                continue
            if not attachment.reached:
                if attachment.net is not None:
                    found.append(
                        issue(
                            "roles.loop-open",
                            f"the sense branch of the Kelvin pair {pair.name} has no copper path to "
                            f"{attachment.pad}",
                            where=f"{pair.name}:{attachment.pad}",
                            hint="route the sense line from the receiver to the shunt's pad",
                        )
                    )
                continue
            flag = profile.resolve("kelvin_inner_edge", board.roles.limits, net=net, kind="kelvin")
            outer = [t for t in attachment.offsets if t < 0]
            if outer and flag.value:
                level = severity("roles.kelvin-outer", source=pair.origin, limit_source="rule")
                found.append(
                    issue(
                        "roles.kelvin-outer",
                        f"the sense line of the Kelvin pair {pair.name} attaches to {attachment.pad} on the "
                        f"outer half of the pad, t = {mm(min(outer))} mm from its centre toward the other "
                        "sense pad; "
                        f"{flag.text()}",
                        severity=level,
                        where=f"{pair.name}:{attachment.pad}",
                        hint="start the sense line on the inner half of the pad, toward the other sense pad",
                    )
                )
    for gate, attachment in done.returns:
        if attachment.shared:
            level = severity("roles.gate-return-shared", source=gate.origin, limit_source="rule")
            found.append(
                issue(
                    "roles.gate-return-shared",
                    f"the return of the gate loop {gate.name} reaches the power source copper before its "
                    f"source pad {gate.source}: {', '.join(attachment.shared)} (S-0852, S-0853)",
                    severity=level,
                    where=gate.name,
                    hint="take the gate return from the source pad (or the Kelvin-source pad) itself",
                )
            )
    return found


def _element(board: RoleBoard, measure: Measure) -> list[Issue]:
    values = measure.values
    net = measure.subject
    source = _net_source(board.roles, net)
    milliamps = values["milliamps"]
    element, where = values["element"], values["where"]
    fill = element == "fill"
    carries_all = values["series"] and (not fill or (values["two_ports"] and values["hull_free"]))
    rule = values["method"] == "rule-of-thumb"
    code = {"track": "roles.width-current", "arc": "roles.width-current", "fill": "roles.section-current",
            "via-group": "roles.via-current"}[element]  # fmt: skip
    have: str
    if rule:
        if element in ("track", "arc"):
            if values["width"] is None or values["width"] >= values["required_width"]:
                return []
            have = f"{mm(values['width'])} mm wide, below the {mm(values['required_width'])} mm"
        elif fill:
            if values["section"] is None or values["section"] >= values["required_width"]:
                return []
            have = (
                f"its narrowest section is {mm(values['section'])} mm, below the "
                f"{mm(values['required_width'])} mm"
            )
        else:
            if (
                values["vias"] is None
                or values["required_vias"] is None
                or values["vias"] >= values["required_vias"]
            ):
                return []
            have = f"{values['vias']} via(s), below the {values['required_vias']} vias"
        limit_text = values["width_limit"] if element != "via-group" else values["via_limit"]
        user = "(override" in limit_text
        method = f"that the rule of thumb asks for {milliamps} mA ({limit_text})"
    else:
        capacity = values["capacity_ma"]
        if capacity is None:
            return []
        share = values["share_ma"]
        if share is not None and not carries_all:
            if share <= capacity:
                return []
            have = f"its share {share} mA is above its {capacity} mA"
        elif capacity >= milliamps:
            return []
        else:
            have = (
                f"it carries {capacity} mA at a rise of {values['temp_rise_mk']} mK, below the {milliamps} mA"
            )
        size = values["width"] if element in ("track", "arc") else values["section"] if fill else None
        if size is not None:
            have = f"{mm(size)} mm {'wide' if not fill else 'at its narrowest section'}: {have}"
        user = True
        method = "by the capacity fit of S-0269"
    level = severity(code, source=source, limit_source="override" if user else "profile")
    text = f"{element} {where} of the {net} role on {values['layer']}: {have} {method}"
    if not carries_all and values["share_ma"] is None:
        text += "; its share of the current is not computed, so the measure does not decide"
        level = "warning"
    hint = "widen the copper, or add vias at the layer change"
    if rule and milliamps > 1000:
        hint += "; above 1 A give a temperature rise (--temp-rise) to judge by the fit of S-0269"
    return [issue(code, text, severity=level, where=where, hint=hint)]


def _neck(board: RoleBoard, measure: Measure) -> list[Issue]:
    values = measure.values
    net = measure.subject
    source = _net_source(board.roles, net)
    limit_text = values["width_limit"]
    level = severity(
        "roles.section-current",
        source=source,
        limit_source="override" if "(override" in limit_text else "profile",
    )
    x, y = values["at"]
    return [
        issue(
            "roles.section-current",
            f"a {values['shape']} of the pour of the {net} role on {values['layer']} at ({mm(x)}, {mm(y)}) "
            f"mm is {mm(values['width'])} mm wide, below the {mm(values['required_width'])} mm that the "
            f"rule of thumb asks for {values['milliamps']} mA ({limit_text})",
            severity=level,
            where=f"{net}@{values['layer']}",
            hint="widen the pour there, or move what narrows it",
        )
    ]


def _near_reasons(board: RoleBoard, measure: Measure) -> list[str]:
    values = measure.values
    limit = profile.resolve("switching_distance_nm", board.roles.limits, net=values["net"], kind="kelvin")
    gap, over, broadside = values["gap"], values["over_fill"], values["broadside"]
    reasons: list[str] = []
    if gap is not None and limit.value is not None and gap < limit.value:
        reasons.append(f"{mm(gap)} mm from it on {values['layer']}, nearer than {limit.text()}")
    if over:
        reasons.append(f"{mm(over)} mm over its fill on a neighbouring layer")
    if broadside:
        reasons.append(f"{mm(broadside)} mm broadside over its tracks on a neighbouring layer")
    return reasons


def _near(board: RoleBoard, measures: Sequence[Measure]) -> list[Issue]:
    """One ``roles.near-switching`` per victim and switch node: the two branches of a Kelvin pair
    (``pair:pad``) are one victim, the pair."""
    groups: dict[tuple[str, str], list[Measure]] = {}
    for measure in measures:
        values = measure.values
        victim = measure.subject.split(":")[0] if values["victim"] == "kelvin" else measure.subject
        groups.setdefault((victim, values["node"]), []).append(measure)
    found: list[Issue] = []
    for (victim, node), held in groups.items():
        parts: list[str] = []
        scores: list[str] = []
        for measure in held:
            reasons = _near_reasons(board, measure)
            if not reasons:
                continue
            label = measure.subject.split(":")[1] if ":" in measure.subject else ""
            parts.append((f"{label} " if label and len(held) > 1 else "") + ", ".join(reasons))
            if measure.values["score"] is not None:
                scores.append(str(measure.values["score"]))
        if not parts:
            continue
        kind = held[0].values["victim"]
        score = f" (coupling score {max(scores, key=int)}, which judges nothing)" if scores else ""
        found.append(
            issue(
                "roles.near-switching",
                f"the {kind} copper {victim} runs near the switch node {node}: " + "; ".join(parts) + score,
                where=f"{victim}~{node}",
                hint="move the sensitive copper away from the switch node, or put ground copper between them",
            )
        )
    return found


def _returns(measure: Measure) -> list[Issue]:
    found: list[Issue] = []
    for span in measure.values["splits"]:
        x0, y0 = span["start"]
        x1, y1 = span["end"]
        found.append(
            issue(
                "roles.return-gap",
                f"the {measure.subject} net crosses a gap of its ground on {span['layer']} for "
                f"{mm(span['length'])} mm, "
                f"from ({mm(x0)}, {mm(y0)}) mm to ({mm(x1)}, {mm(y1)}) mm, on {span['where']}",
                where=f"{measure.subject}@{span['where']}",
                hint="route the net over unbroken ground, or close the gap under it",
            )
        )
    return found


def judge(board: RoleBoard, done: Measured) -> list[Issue]:
    """The findings of the measures of ``board``."""
    found: list[Issue] = []
    for measure in done.measures:
        match measure.kind:
            case "loop":
                found += _loop(board, measure)
            case "path":
                found += _element(board, measure)
            case "neck":
                pass  # judged below, once the sections of the paths are known
            case "near":
                pass  # judged together below, one finding per victim and node
            case "return":
                found += _returns(measure)
            case "distance" if measure.values["rows"] == 0:
                found.append(
                    issue(
                        "roles.limit-missing",
                        f"the high-voltage net {measure.subject} has no distance requirement: Fenolite "
                        "ships no creepage or clearance table, so its distances are not judged",
                        where=measure.subject,
                        hint="add [[distance]] rows (or a [[step]] table) for the working voltage: creepage "
                        "by RMS "
                        "working voltage, pollution degree and material group, clearance by transients, "
                        "pollution degree and altitude (S-0854)",
                    )
                )
            case "sense" if measure.values["shared"]:
                shared = ", ".join(
                    f"{kind} {where} of {net}" for kind, where, net in measure.values["shared"]
                )
                pair = next(
                    (
                        pair
                        for pair in board.roles.kelvins
                        if measure.subject in {_pad_net(board, p) for p in pair.element}
                    ),
                    None,
                )
                origin = pair.origin if pair is not None else "inferred"
                found.append(
                    issue(
                        "roles.kelvin-shared",
                        f"the sense net {measure.subject} touches the copper of another net: {shared} "
                        "(S-0850)",
                        severity=severity("roles.kelvin-shared", source=origin, limit_source="rule"),
                        where=measure.subject,
                        hint="a sense net meets its element only at its pads, through a net tie",
                    )
                )
            case _:
                pass
    narrow = {
        zone
        for measure, issues in ((m, _element(board, m)) for m in done.measures if m.kind == "path")
        if issues and measure.values["element"] == "fill"
        for zone in measure.values.get("zones", ())
    }
    for measure in done.measures:
        if measure.kind == "neck" and not set(measure.values.get("zones", ())) & narrow:
            found += _neck(board, measure)  # a fill already judged narrow by its section is not repeated
    found += _near(board, [measure for measure in done.measures if measure.kind == "near"])
    found += _attachments(board, done)
    for role in board.roles.nets:
        if role.kind in CURRENT_KINDS and role.milliamps is None:
            found.append(
                issue(
                    "roles.current-missing",
                    f"the {role.kind} role of {role.net} has no current, so its copper is not judged for "
                    "current; "
                    "Fenolite assumes none",
                    where=role.net,
                    hint="give it with --current NET=AMPS, a [[current]] row or design.net_role(..., "
                    "current=...)",
                )
            )
    return found


def _pad_net(board: RoleBoard, pad: str) -> str | None:
    return next((record.net for record in board.pads if f"{record.ref}-{record.number}" == pad), None)


def hypotheses(done: Measured) -> tuple[str, ...]:
    """The role hypotheses that the measures taken rely on."""
    found: set[str] = {"H-G-ROLE-INFER"}
    for measure in done.measures:
        kind = (
            "kelvin" if measure.kind == "loop" and measure.values.get("group") == "kelvin" else measure.kind
        )
        found.update(HYPOTHESES.get(kind, ()))
    return tuple(sorted(found))


def summary(issues: Sequence[Issue], done: Measured, roles: RoleSet) -> Mapping[str, object]:
    codes: dict[str, int] = {}
    for found in issues:
        codes[found.code] = codes.get(found.code, 0) + 1
    sources: dict[str, int] = {}
    for role in roles.nets:
        sources[role.source] = sources.get(role.source, 0) + 1
    return {
        "measures": len(done.measures),
        "analyses": sorted(done.analyses),
        "codes": dict(sorted(codes.items())),
        "roles": dict(sorted(sources.items())),
    }


# ----------------------------------------------------------------- requirement rows (change c0253)

NM2_TO_M2 = Fraction(1, 10**18)
NM_TO_M = Fraction(1, 10**9)


def _limit_side(limit: profile.Limit, unit: str, value: Fraction, text: str) -> Side:
    """The limit side of a role row: a profile default is ``policy`` with its key and source id, an override
    is the user's (basis ``role_limits``), and a requirements limit the user's (basis
    ``requirements.toml``)."""
    source: Source = "policy" if limit.origin == "profile" else "user"
    basis = {
        "profile": f"{limit.key} (profile, {limit.source})",
        "override": "role_limits",
        "requirements": "requirements.toml",
    }.get(limit.origin, limit.origin)
    label = profile.DEFAULTS[limit.key].label if limit.origin == "profile" else "INFERRED"
    return Side(Bound(unit, None, value), text, source, basis, label or "INFERRED", "requirement")


def _loop_rows(board: RoleBoard, measure: Measure) -> list[RequirementRow]:
    values = measure.values
    kind, name, roles = values["group"], measure.subject, board.roles
    area, bound, ratio = values["area_nm2"], values["bound_nm2"], values["ratio_permille"]
    if values["open"] or area is None:
        return []
    net = values["net"]
    group_kind = {"hot": "switch_node", "gate": "gate", "kelvin": "kelvin"}[kind]
    code = {"hot": "roles.loop-area", "gate": "roles.gate-loop", "kelvin": "roles.kelvin-apart"}[kind]
    what = {"hot": "loop", "gate": "gate loop", "kelvin": "Kelvin pair"}[kind]
    entities = tuple(values["pads"])
    rows: list[RequirementRow] = []
    origin = _origin(roles, kind, name)
    if kind in ("hot", "gate"):
        key = "loop_max" if kind == "hot" else "gate_max"
        largest = profile.resolve(key, roles.limits, net=net, kind=group_kind)
        if largest.value is not None:
            failed = area > largest.value
            rows.append(
                RequirementRow(
                    f"{code}:{name}:{key}",
                    code,
                    f"{what} {name}",
                    "area",
                    "square_metre",
                    Side(
                        Bound("square_metre", None, area * NM2_TO_M2),
                        f"{mm2(area)} mm²",
                        "role",
                        f"{origin} {what} {name}",
                    ),
                    _limit_side(
                        largest, "square_metre", largest.value * NM2_TO_M2, f"{mm2(largest.value)} mm²"
                    ),
                    "fail" if failed else "pass",
                    severity(code, source=origin, limit_source=largest.origin) if failed else None,
                    entities,
                )
            )
    key = {"hot": "loop_ratio_max", "gate": "gate_ratio_max", "kelvin": "pair_ratio_max"}[kind]
    most = profile.resolve(key, roles.limits, net=net, kind=group_kind)
    floor = profile.resolve("loop_bound_floor_nm2", roles.limits, net=net, kind=group_kind)
    judged = bound is not None and floor.value is not None and bound >= floor.value and ratio is not None
    if judged and most.value is not None and ratio is not None:
        failed = ratio > most.value
        rows.append(
            RequirementRow(
                f"{code}:{name}:{key}",
                code,
                f"{what} {name}",
                "area ratio",
                "ratio",
                Side(
                    Bound("ratio", None, Fraction(ratio, 1000)),
                    f"{ratio}‰ of {mm2(bound or 0)} mm²",
                    "role",
                    f"{origin} {what} {name}",
                ),
                _limit_side(most, "ratio", Fraction(most.value, 1000), f"{most.value}‰"),
                "fail" if failed else "pass",
                severity(code, source=origin, limit_source=most.origin) if failed else None,
                entities,
            )
        )
    return rows


def _path_rows(board: RoleBoard, measure: Measure) -> list[RequirementRow]:
    """The width a power path's track or fill needs by the rule of thumb, against what it has."""
    values = measure.values
    element = values["element"]
    if values["method"] != "rule-of-thumb" or element not in ("track", "arc", "fill"):
        return []
    width = values["width"] if element != "fill" else values["section"]
    required = values["required_width"]
    if width is None or required is None:
        return []
    net = measure.subject
    code = "roles.width-current" if element != "fill" else "roles.section-current"
    limit = profile.resolve("width_per_amp_nm", board.roles.limits, net=net, kind=None)
    failed = width < required
    source = _net_source(board.roles, net)
    side = _limit_side(limit, "metre", required * NM_TO_M, f"{mm(required)} mm for {values['milliamps']} mA")
    side = Side(
        Bound("metre", required * NM_TO_M, None), side.text, side.source, side.basis, side.evidence, side.kind
    )
    return [
        RequirementRow(
            f"{code}:{values['where']}",
            code,
            f"{element} {values['where']} of {net}",
            "width",
            "metre",
            Side(
                Bound("metre", width * NM_TO_M, width * NM_TO_M),
                f"{mm(width)} mm",
                "role",
                f"{source} role of {net}",
            ),
            side,
            "fail" if failed else "pass",
            severity(code, source=source, limit_source=limit.origin) if failed else None,
            (net,),
        )
    ]


def rows(board: RoleBoard, done: Measured) -> list[RequirementRow]:
    """The requirement rows of the measures of ``board`` judged against a limit (change c0253): each loop's
    area against ``loop_max``/``gate_max`` and its ratio against its ratio limit, and each power path's width
    by the rule of thumb. The findings and their messages are ``judge``'s, unchanged."""
    found: list[RequirementRow] = []
    for measure in done.measures:
        if measure.kind == "loop":
            found += _loop_rows(board, measure)
        elif measure.kind == "path":
            found += _path_rows(board, measure)
    return found


__all__ = ["HYPOTHESES", "hypotheses", "judge", "mm", "mm2", "rows", "summary"]
