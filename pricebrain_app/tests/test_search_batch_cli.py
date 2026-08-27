"""Search batch CLI tests — V2 Phase 3 production write guard."""

from __future__ import annotations

import pathlib

import pytest

from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.scripts import run_elevenst_search_batch as cli
from pricebrain_app.tests.counting_firestore import CountingFirestoreClient
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURE = (
    pathlib.Path(__file__).parent / "fixtures" / "elevenst" / "search_rtx.json"
)


@pytest.fixture
def counting_db(monkeypatch: pytest.MonkeyPatch) -> CountingFirestoreClient:
    inner = FakeFirestoreClient()
    seed_gpu_master(inner)
    client = CountingFirestoreClient(inner)
    monkeypatch.setattr(cli, "get_firestore_client", lambda: client)
    return client


@pytest.fixture(autouse=True)
def no_emulator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)


def test_query_is_required(counting_db):
    with pytest.raises(SystemExit):
        cli.main(["--limit", "5"])


def test_dry_run_is_the_default(counting_db, capsys):
    assert cli.main(["--query", "RTX 5070", "--fixture", str(FIXTURE)]) == 0
    out = capsys.readouterr().out

    assert "(dry-run)" in out
    assert counting_db.writes == 0


def test_dry_run_writes_nothing_even_with_a_large_limit(counting_db):
    cli.main(["--query", "RTX 5070", "--limit", "50", "--fixture", str(FIXTURE)])
    assert counting_db.writes == 0
    assert counting_db.write_paths == []


def test_persist_without_emulator_or_confirmation_is_refused(counting_db, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--query", "RTX 5070", "--persist", "--fixture", str(FIXTURE)])

    assert excinfo.value.code == 1
    assert "Refusing to persist" in capsys.readouterr().err
    assert counting_db.writes == 0


def test_persist_allowed_against_emulator(counting_db, monkeypatch, capsys):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    assert (
        cli.main(["--query", "RTX 5070", "--limit", "50", "--fixture", str(FIXTURE), "--persist"])
        == 0
    )

    assert "(live)" in capsys.readouterr().out
    assert counting_db.writes > 0


def test_persist_allowed_with_explicit_production_confirmation(counting_db):
    cli.main(
        [
            "--query",
            "RTX 5070",
            "--limit",
            "50",
            "--fixture",
            str(FIXTURE),
            "--persist",
            "--confirm-production",
        ]
    )
    assert counting_db.writes > 0


def test_limit_is_capped_by_the_cli_path(counting_db, capsys):
    cli.main(["--query", "RTX 5070", "--limit", "10000", "--fixture", str(FIXTURE), "--json"])
    out = capsys.readouterr().out

    assert '"requested": 50' in out
    assert '"dry_run": true' in out


def test_json_output_reports_every_bucket(counting_db, capsys):
    cli.main(["--query", "RTX 5070", "--limit", "50", "--fixture", str(FIXTURE), "--json"])
    out = capsys.readouterr().out

    for key in (
        "persisted",
        "persist_candidates",
        "quarantined",
        "validation_failed",
        "irrelevant",
        "failed",
        "unknown_models",
        "search_api_calls",
        "duplicates_skipped",
    ):
        assert f'"{key}"' in out


def test_fixture_mode_makes_no_http_request(counting_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("fixture mode must not build an HTTP client")

    monkeypatch.setattr(cli, "build_http_client", explode)
    assert cli.main(["--query", "RTX 5070", "--fixture", str(FIXTURE)]) == 0
