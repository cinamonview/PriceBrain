"""Danawa-Crawler VGA.csv backfill — parsing, gates and price history order."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pricebrain_app.danawa_import import (
    DanawaImportSetupError,
    import_danawa_products,
    parse_danawa_csv,
    parse_price,
)
from pricebrain_app.repository import constants as c
from pricebrain_app.scripts import import_danawa_csv
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

KST = timezone(timedelta(hours=9))
HEADER = "Id,Name,2026-10-01 14:10:23,2026-10-02 14:00:17,2026-10-03 13:42:57,2026-10-04 14:14:29\n"
ZOTAC_5080 = "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"
GIGABYTE_5070 = "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB 피씨디렉트"


def _write_csv(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "VGA.csv"
    path.write_text(HEADER + "".join(f"{row}\n" for row in rows), encoding="utf-8")
    return path


def _price_history_paths(db: FakeFirestoreClient, listing_id: str) -> list[str]:
    prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    return sorted(path for path in db.paths() if path.startswith(prefix))


def test_parse_price_accepts_digits_and_commas_only() -> None:
    assert parse_price('1,234,000') == 1234000
    assert parse_price("") is None
    assert parse_price("일시품절") is None
    assert parse_price("가격비교예정") is None
    assert parse_price("0") is None


def test_parse_keeps_only_price_changes_in_kst(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        f'111,{ZOTAC_5080},"1,500,000","1,500,000",일시품절,"1,480,000"',
        ",ignored row without id,1,1,1,1",
    )
    products = parse_danawa_csv(csv_path)

    assert [p.pcode for p in products] == ["111"]
    assert products[0].observations == (
        (datetime(2026, 10, 1, 14, 10, 23, tzinfo=KST), 1_500_000),
        (datetime(2026, 10, 4, 14, 14, 29, tzinfo=KST), 1_480_000),
    )


def test_parse_rejects_other_csv_layouts(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    path.write_text("name,price\nx,1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_danawa_csv(path)


def test_import_writes_listing_with_chronological_history(
    tmp_path: Path, fake_db: FakeFirestoreClient
) -> None:
    csv_path = _write_csv(
        tmp_path,
        f'111,{ZOTAC_5080},"1,500,000","1,450,000","1,450,000","1,480,000"',
        f'222,{GIGABYTE_5070},"900,000","900,000","900,000","900,000"',
    )

    report = import_danawa_products(fake_db, parse_danawa_csv(csv_path))

    assert report.rows == 2
    assert report.accepted == 2
    assert report.listings_written == 2
    assert report.price_points_written == 4  # 3 changes for 111, 1 for 222
    assert not report.skipped

    listing = fake_db.collection(c.LISTINGS).document("DANAWA_111").get().to_dict()
    assert listing["current_price"] == 1_480_000
    assert listing["product_url"] == "https://prod.danawa.com/info/?pcode=111"
    assert len(_price_history_paths(fake_db, "DANAWA_111")) == 3
    assert len(_price_history_paths(fake_db, "DANAWA_222")) == 1

    history = sorted(
        (
            doc.to_dict()
            for doc in fake_db.collection(c.LISTINGS)
            .document("DANAWA_111")
            .collection(c.PRICE_HISTORY)
            .stream()
        ),
        key=lambda entry: entry["crawled_at"],
    )
    assert [(h["previous_price"], h["price"]) for h in history] == [
        (None, 1_500_000),
        (1_500_000, 1_450_000),
        (1_450_000, 1_480_000),
    ]


def test_import_reports_why_rows_are_skipped(
    tmp_path: Path, fake_db: FakeFirestoreClient
) -> None:
    csv_path = _write_csv(
        tmp_path,
        f'111,{ZOTAC_5080},"1,500,000","1,500,000","1,500,000","1,500,000"',
        '333,MSI 지포스 RTX 3060 벤투스 2X D6 12GB,"400,000","400,000","400,000","400,000"',
        '444,로지텍 무선 마우스 G304,"40,000","40,000","40,000","40,000"',
        "555,ZOTAC GAMING 지포스 RTX 5070 SOLID D7 12GB,일시품절,,,",
    )

    report = import_danawa_products(fake_db, parse_danawa_csv(csv_path))

    assert report.accepted == 1
    assert report.skipped["unknown_gpu_model:rtx_3060"] == 1
    assert report.skipped["not_gpu"] == 1
    assert report.skipped["no_price"] == 1
    assert fake_db.collection(c.LISTINGS).document("DANAWA_333").get().exists is False


def test_import_blocks_products_sharing_one_canonical_identity(
    tmp_path: Path, fake_db: FakeFirestoreClient
) -> None:
    csv_path = _write_csv(
        tmp_path,
        '111,ASUS DUAL 지포스 RTX 5070 OC D7 12GB 대원씨티에스,"900,000","900,000","900,000","900,000"',
        '112,ASUS DUAL 지포스 RTX 5070 OC D7 12GB 코잇,"910,000","910,000","910,000","910,000"',
    )

    report = import_danawa_products(fake_db, parse_danawa_csv(csv_path))

    assert report.accepted == 0
    assert report.skipped["identity_review_blocked"] == 2
    assert not [p for p in fake_db.paths() if p.startswith(f"{c.LISTINGS}/")]


def test_dry_run_writes_nothing(tmp_path: Path, fake_db: FakeFirestoreClient) -> None:
    csv_path = _write_csv(tmp_path, f'111,{ZOTAC_5080},"1,500,000","1,450,000",,')
    before = set(fake_db.paths())

    report = import_danawa_products(fake_db, parse_danawa_csv(csv_path), dry_run=True)

    assert report.accepted == 1
    assert report.listings_written == 0
    assert set(fake_db.paths()) == before


def test_dry_run_requires_seeded_gpu_master(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, f'111,{ZOTAC_5080},"1,500,000",,,')
    with pytest.raises(DanawaImportSetupError):
        import_danawa_products(FakeFirestoreClient(), parse_danawa_csv(csv_path), dry_run=True)


def test_cli_refuses_to_write_without_emulator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    csv_path = _write_csv(tmp_path, f'111,{ZOTAC_5080},"1,500,000",,,')

    assert import_danawa_csv.main(["--csv", str(csv_path)]) == 2
