# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Identity drafts, grammar suggestions and exact replay without retained offers or a second call."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.cli import cmd_pick
from fenolite.cli.api import Result
from fenolite.core.state import STATE_ENV
from fenolite.pick.grammar.schema import read_family
from fenolite.pick.propose import SupplierLookup
from fenolite.pick.query import parse_query
from fenolite.pick.rows import folder_rows
from fenolite.suppliers.policy import SourcePolicy
from fenolite.suppliers.rows import Candidate, proposal_row
from tests.unit.cli._checkcli import run

ROOT = Path(__file__).resolve().parents[3]
MPN = "EX03R104KAT"
QUERY = "capacitor(100nF, rating>=25V)"
TIMESTAMP = "2026-11-01T00:00:00+00:00"


def test_decoded_and_unknown_identity_drafts(policy: SourcePolicy, tmp_path: Path) -> None:
    family = read_family(ROOT / "examples/families/devices/example_mlcc.toml")
    candidate = Candidate(
        MPN,
        "Example Passive",
        "https://example.invalid/authored.pdf",
        {"rating": "999V"},
        {"stock": 12345, "price": "AUTHORED-PRICE"},
    )
    known, issues = proposal_row(candidate, policy, query=QUERY, timestamp=TIMESTAMP, families=(family,))
    data = tomllib.loads(known.text)
    assert data["schema"] == "fenolite.supplier-proposal.v0" and data["evidence"] == "UNVERIFIED"
    assert data["provenance"]["attribution"] == policy.attribution
    assert data["provenance"]["decoded_by"] == "Example:EX_MLCC 1.0.0"
    suggestion = tomllib.loads(data["decoded"]["device_toml"])
    assert "25" in str(suggestion["ratings"])
    assert known.display["offer"] == candidate.offer and known.display["reported"] == candidate.reported
    assert "AUTHORED-PRICE" not in known.text and "999V" not in known.text and "12345" not in known.text
    assert "offer" not in known.persisted and "reported" not in known.persisted
    assert {i.code for i in issues} == {"supplier.proposed", "supplier.unmapped"}
    (tmp_path / known.file).write_text(known.text)
    assert folder_rows(tmp_path, "devices/proposed") == ()
    unknown, issues = proposal_row(
        Candidate("AUTHORED-UNKNOWN"), policy, query=QUERY, timestamp=TIMESTAMP, families=(family,)
    )
    assert "decoded" not in tomllib.loads(unknown.text) and unknown.display["complete"] is False
    assert "supplier.row-incomplete" in {i.code for i in issues}


def test_persist_permission_is_explicit(policy: SourcePolicy) -> None:
    with pytest.raises(ValueError, match="does not permit"):
        proposal_row(Candidate(MPN), replace(policy, persist=()), query=QUERY, timestamp=TIMESTAMP)
    draft, _ = proposal_row(
        Candidate(MPN, "display only", "https://example.invalid/a"),
        replace(policy, persist=("mpn",)),
        query=QUERY,
        timestamp=TIMESTAMP,
    )
    assert "manufacturer" not in tomllib.loads(draft.text) and "datasheet" not in tomllib.loads(draft.text)


def test_confirm_replays_exact_bytes_without_offers_or_lookup(
    policy: SourcePolicy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state))
    design = tmp_path / "design.py"
    design.write_text("raise RuntimeError('PRIVATE-DESIGN-MUST-NOT-RUN')")
    candidate = Candidate(
        MPN,
        "Example Passive",
        "https://example.invalid/authored.pdf",
        {"parameter": "AUTHORED-REPORTED"},
        {"stock": 7654321, "price": "AUTHORED-OFFER"},
    )
    draft, issues = proposal_row(candidate, policy, query=parse_query(QUERY).text(), timestamp=TIMESTAMP)

    class AuthoredSupplier:
        proposal_api = "fenolite.supplier-lookup.v0"
        sends_data_offsite = True
        calls = 0

        def lookup(self, query: object, **kwargs: object) -> SupplierLookup:
            self.calls += 1
            return SupplierLookup((draft,), issues, policy.sends)

    plugin = AuthoredSupplier()
    monkeypatch.setattr(cmd_pick, "suppliers", lambda: {"authored": object()})
    monkeypatch.setattr(cmd_pick, "load_supplier", lambda name: plugin)
    args = (
        "pick",
        ".",
        "--propose",
        QUERY,
        "--supplier",
        "authored",
        "--allow-offsite",
        "--timeout",
        "5",
        "--limit",
        "1",
        "--timestamp",
        TIMESTAMP,
    )
    code, envelope, error, raw = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, error
    assert plugin.calls == 1 and "AUTHORED-OFFER" in raw and "AUTHORED-REPORTED" in raw
    assert not (tmp_path / "devices").exists()
    stored = b"".join(p.read_bytes() for p in state.rglob("*") if p.is_file())
    assert b"AUTHORED-OFFER" not in stored and b"AUTHORED-REPORTED" not in stored and b"7654321" not in stored
    assert b"PRIVATE-DESIGN-MUST-NOT-RUN" not in stored

    def forbidden(name: str) -> None:
        raise AssertionError("confirm must not load a supplier or make another request")

    monkeypatch.setattr(cmd_pick, "load_supplier", forbidden)
    code, confirmed, error, raw = run(
        monkeypatch, tmp_path, *args, "--confirm", "--plan", envelope["result"]["plan_id"]
    )
    assert code == 0 and plugin.calls == 1, error
    output = tmp_path / "devices/proposed" / draft.file
    assert output.read_bytes() == draft.text.encode()
    assert confirmed["receipt"]["written"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert "AUTHORED-OFFER" not in raw and "AUTHORED-REPORTED" not in raw
    assert "offer" not in confirmed["result"]["proposals"][0]
    assert not list(tmp_path.rglob("*.lock"))


@pytest.mark.parametrize(
    "saved", [{"new": 1}, {"x": 2}, {"x": True}, {"plan": []}, {"receipt": {}}, {"x": [1, 2]}]
)
def test_staged_filter_cannot_add_change_or_forge_metadata(saved: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Result(result={"x": 1}, staged_result=saved)


def test_staged_filter_removes_only_nested_data() -> None:
    Result(
        result={"rows": [{"identity": "a", "offer": "temporary"}]},
        staged_result={"rows": [{"identity": "a"}]},
    )
    with pytest.raises(ValueError):
        Result(result={"rows": [{"x": 1}]}, staged_result={"rows": []})


def test_canary_credentials_absent_from_reply_store_replay_and_written_bytes(
    policy: SourcePolicy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fenolite.suppliers import http
    from fenolite.suppliers.mouser import Mouser
    from tests.unit.suppliers.conftest import FakeTransport, response

    secret = "AUTHORED-lookup-secret+canary"
    monkeypatch.setenv("FENOLITE_MOUSER_API_KEY", secret)
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state))
    (tmp_path / "design.py").write_text("raise RuntimeError('secret-board')")
    plugin = Mouser()
    plugin.policy = policy
    transport = FakeTransport(
        response(
            {
                "SearchResults": {
                    "Parts": [
                        {
                            "ManufacturerPartNumber": MPN,
                            "Manufacturer": "Example Passive " + secret,
                            "DataSheetUrl": "https://example.invalid/authored.pdf",
                            "Availability": "AUTHORED-OFFER " + secret,
                        }
                    ]
                }
            }
        )
    )
    monkeypatch.setattr(http, "UrllibTransport", lambda: transport)
    monkeypatch.setattr(cmd_pick, "suppliers", lambda: {"mouser": object()})
    monkeypatch.setattr(cmd_pick, "load_supplier", lambda name: plugin)
    args = (
        "pick",
        ".",
        "--propose",
        QUERY,
        "--supplier",
        "mouser",
        "--allow-offsite",
        "--timestamp",
        TIMESTAMP,
    )
    code, envelope, error, raw = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and "AUTHORED-OFFER" in raw and secret not in raw, error
    stored = b"".join(p.read_bytes() for p in state.rglob("*") if p.is_file())
    assert secret.encode() not in stored and b"AUTHORED-OFFER" not in stored
    assert len(transport.requests) == 1 and b"secret-board" not in transport.requests[0].body
    plan = envelope["result"]["plan_id"]

    def forbidden(name: str) -> None:
        raise AssertionError("confirmation must not load provider")

    monkeypatch.setattr(cmd_pick, "load_supplier", forbidden)
    code, confirmed, error, raw = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan)
    assert code == 0 and len(transport.requests) == 1, error
    assert secret not in raw and "AUTHORED-OFFER" not in raw
    written = confirmed["receipt"]["written"][0]
    data = (tmp_path / written["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == written["sha256"]
    assert secret.encode() not in data and b"AUTHORED-OFFER" not in data

    # The text view carries attribution too, after the same redaction path.
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from fenolite.cli.main import main

    transport.responses.append(
        response(
            {
                "SearchResults": {
                    "Parts": [
                        {
                            "ManufacturerPartNumber": MPN,
                            "Manufacturer": "Example Passive " + secret,
                        }
                    ]
                }
            }
        )
    )
    monkeypatch.setattr(cmd_pick, "load_supplier", lambda name: plugin)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main([*args, "--dry-run", "--text"])
    assert code == 0 and policy.attribution in out.getvalue()
    assert secret not in out.getvalue() + err.getvalue()
    text = out.getvalue()
    assert "plan_id" in text and "sha256" in text and "devices/proposed/" in text and "sends" in text


@pytest.mark.parametrize(
    "encoded",
    [
        "AUTHORED%2bCANARY%2fcredential",
        "AUTHORED%2BCANARY%2fcredential",
        "AUTHORED%2bCANARY%2Fcredential",
    ],
)
def test_percent_escape_case_redacted_before_cache_plan_and_confirm(
    encoded: str,
    policy: SourcePolicy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    from fenolite.suppliers import http
    from fenolite.suppliers.cache import ProcessCache
    from fenolite.suppliers.mouser import Mouser
    from tests.unit.suppliers.conftest import FakeClock, FakeTransport, response

    secret = "AUTHORED+CANARY/credential"
    monkeypatch.setenv("FENOLITE_MOUSER_API_KEY", secret)
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_ENV, str(state))
    (tmp_path / "design.py").write_text("raise RuntimeError('must not execute')")
    body = {
        "SearchResults": {
            "Parts": [
                {
                    "ManufacturerPartNumber": MPN,
                    "Manufacturer": "Example " + encoded,
                    "DataSheetUrl": "https://example.invalid/" + encoded,
                    "ProductAttributes": [{"AttributeName": "Authored", "AttributeValue": encoded}],
                    "Availability": encoded,
                    "PriceBreaks": [{"Quantity": 1, "Price": encoded, "Currency": "USD"}],
                }
            ]
        }
    }
    transport = FakeTransport(response(body))
    plugin = Mouser()
    plugin.policy = policy
    plugin.cache = ProcessCache(policy, FakeClock())
    lookup = plugin.lookup(parse_query(QUERY), timestamp=TIMESTAMP, transport=transport)
    draft = lookup.drafts[0]
    views = [
        draft.text,
        json.dumps(dict(draft.display)),
        json.dumps(dict(draft.persisted)),
        repr(plugin.cache._items),
    ]
    assert all(encoded not in view and secret not in view for view in views)
    assert draft.persisted["datasheet"] == "https://example.invalid/***"
    assert "***" in views[-1] and "ProductAttributes" in views[-1] and "PriceBreaks" in views[-1]
    monkeypatch.setattr(http, "UrllibTransport", lambda: transport)
    monkeypatch.setattr(cmd_pick, "suppliers", lambda: {"mouser": object()})
    monkeypatch.setattr(cmd_pick, "load_supplier", lambda name: plugin)
    args = (
        "pick",
        ".",
        "--propose",
        QUERY,
        "--supplier",
        "mouser",
        "--allow-offsite",
        "--timestamp",
        TIMESTAMP,
    )
    code, envelope, error, raw = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and len(transport.requests) == 1, error
    stored = b"".join(p.read_bytes() for p in state.rglob("*") if p.is_file())
    assert encoded not in raw and secret not in raw
    assert encoded.encode() not in stored and secret.encode() not in stored

    def forbidden(name: str) -> None:
        raise AssertionError("confirmation must not load supplier")

    monkeypatch.setattr(cmd_pick, "load_supplier", forbidden)
    code, confirmed, error, raw = run(
        monkeypatch, tmp_path, *args, "--confirm", "--plan", envelope["result"]["plan_id"]
    )
    assert code == 0 and len(transport.requests) == 1, error
    assert encoded not in raw and secret not in raw
    written = confirmed["receipt"]["written"][0]
    actual = (tmp_path / written["path"]).read_bytes()
    assert actual == draft.text.encode() and hashlib.sha256(actual).hexdigest() == written["sha256"]
    assert encoded.encode() not in actual and secret.encode() not in actual
