"""Price alert runner orchestration tests — FakeFirestore only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pricebrain_app.config.settings import clear_settings_cache, get_settings
from pricebrain_app.crawler.notification_adapter import FakeNotificationAdapter, FailingNotificationAdapter
from pricebrain_app.crawler.notification_dispatcher import NotificationDispatcher
from pricebrain_app.crawler.notification_models import NotificationChannel, NotificationSendStatus
from pricebrain_app.crawler.price_alert_models import AlertEvaluationOutcome, PriceAlertType
from pricebrain_app.crawler.price_alert_repository import PriceAlertRepository
from pricebrain_app.crawler.price_alert_runner import AlertRunnerShutdown, PriceAlertRunner
from pricebrain_app.crawler.price_alert_service import PriceAlertService
from pricebrain_app.crawler.price_operations_view import PriceOperationsView
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import run_price_alert_runner
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
TARGET_ID = "ssg_1000832367906"
TARGET_B = "ssg_2222222222222"
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")


@pytest.fixture
def runner_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def alert_repo(runner_db: FakeFirestoreClient) -> PriceAlertRepository:
    return PriceAlertRepository(runner_db)


@pytest.fixture
def target_repo(runner_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(runner_db)


@pytest.fixture
def price_view(runner_db: FakeFirestoreClient, target_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(target_repo, runner_db)


def _service(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    *,
    fake: FakeNotificationAdapter | None = None,
    failing: bool = False,
    notifications_enabled: bool = True,
) -> PriceAlertService:
    adapter = FailingNotificationAdapter() if failing else (fake or FakeNotificationAdapter())
    return PriceAlertService(
        alert_repo,
        price_view,
        notification_dispatcher=NotificationDispatcher({NotificationChannel.FAKE: adapter}),
        default_channel=NotificationChannel.FAKE,
        notifications_enabled_override=notifications_enabled,
    )


def _runner(service: PriceAlertService, *, shutdown: AlertRunnerShutdown | None = None) -> PriceAlertRunner:
    return PriceAlertRunner(service, shutdown=shutdown or AlertRunnerShutdown())


def _seed_target(repo: CrawlTargetRepository, *, url: str = PRODUCT_URL, name: str = "GPU") -> None:
    repo.merge_catalog(
        mall_id="ssg",
        product_url=url,
        product_name=name,
        category="gpu",
        tags=["zotac"],
        priority=100,
        now=NOW,
    )


def _seed_listing(db: FakeFirestoreClient, *, current: int, previous: int | None = None) -> None:
    db.collection(c.LISTINGS).document(LISTING_ID).set(
        {
            "normalized_product_name": "ZOTAC RTX 5080",
            "current_price": current,
            "crawled_at": NOW,
        }
    )
    db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document("1").set(
        {
            "price": current,
            "previous_price": previous,
            "price_change": (current - previous) if previous is not None else None,
            "crawled_at": NOW,
        }
    )


def test_a_zero_enabled_alerts(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
) -> None:
    result = _runner(_service(alert_repo, price_view)).run_once(now=NOW)
    assert result.total_alerts == 0
    assert result.evaluated == 0


def test_b_single_alert_success(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    fake = FakeNotificationAdapter()
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    result = _runner(_service(alert_repo, price_view, fake=fake)).run_once(now=NOW)
    assert result.triggered == 1
    assert result.notification_sent == 1
    assert len(fake.sent_events) == 1


def test_c_multiple_alerts_processed(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_target(target_repo, url="https://www.ssg.com/item/itemView.ssg?itemId=2222222222222", name="GPU2")
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    alert_repo.create(
        target_id=TARGET_B,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    result = _runner(_service(alert_repo, price_view)).run_once(now=NOW)
    assert result.total_alerts == 2
    assert result.evaluated == 2
    assert result.triggered == 1
    assert result.invalid == 1


def test_d_alert_evaluation_failure_isolation(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_target(target_repo)
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    alert_repo.create(
        target_id=TARGET_B,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )

    original_get = price_view.get_current_price

    def flaky_get(target_id: str):
        if target_id == TARGET_B:
            raise RuntimeError("malformed alert target")
        return original_get(target_id)

    monkeypatch.setattr(price_view, "get_current_price", flaky_get)
    result = _runner(_service(alert_repo, price_view)).run_once(now=NOW)
    assert result.triggered == 1
    assert result.evaluated == 2


def test_e_notification_failure_isolation(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    result = _runner(_service(alert_repo, price_view, failing=True)).run_once(now=NOW)
    assert result.triggered == 1
    assert result.notification_failed == 1


def test_f_dry_run_does_not_mutate_or_notify(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    alert = alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    fake = FakeNotificationAdapter()
    result = _runner(_service(alert_repo, price_view, fake=fake)).run_once(dry_run=True, now=NOW)
    saved = alert_repo.get(alert.alert_id)
    assert result.dry_run is True
    assert result.triggered == 1
    assert result.notification_sent == 0
    assert fake.sent_events == []
    assert saved is not None
    assert saved.last_triggered_at is None
    assert saved.last_observed_price is None


def test_g_once_cli(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_target(target_repo)
    service = _service(alert_repo, price_view)
    runner = _runner(service)
    monkeypatch.setattr(run_price_alert_runner, "build_price_alert_runner", lambda **kwargs: runner)
    assert run_price_alert_runner.main(["--once", "--dry-run"]) == 0


def test_h_max_alerts(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
) -> None:
    _seed_target(target_repo)
    for index in range(3):
        alert_repo.create(
            target_id=f"ssg_{1000000000000 + index}",
            mall_id="ssg",
            alert_type=PriceAlertType.PRICE_BELOW,
            threshold=1_500_000,
            now=NOW,
        )
    result = _runner(_service(alert_repo, price_view)).run_once(max_alerts=2, now=NOW)
    assert result.total_alerts == 2


def test_i_shutdown_stops_before_next_cycle(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
) -> None:
    shutdown = AlertRunnerShutdown()
    runner = _runner(_service(alert_repo, price_view), shutdown=shutdown)
    cycles: list[int] = []

    def sleep_and_stop(seconds: float) -> None:
        cycles.append(1)
        shutdown.request_stop()

    runner._sleep_func = sleep_and_stop
    result = runner.run_forever(interval_seconds=1.0)
    assert len(cycles) == 1
    assert result.total_alerts == 0


def test_j_run_forever_executes_at_least_one_cycle(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
) -> None:
    shutdown = AlertRunnerShutdown()
    runner = _runner(_service(alert_repo, price_view), shutdown=shutdown)
    runner._sleep_func = lambda _seconds: shutdown.request_stop()
    result = runner.run_forever(interval_seconds=0.01)
    assert result.evaluated == 0


def test_k_duplicate_policy_regression(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    runner = _runner(_service(alert_repo, price_view))
    first = runner.run_once(now=NOW)
    second = runner.run_once(now=NOW)
    assert first.triggered == 1
    assert second.skipped == 1


def test_l_security_json_has_no_api_key(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    runner = _runner(_service(alert_repo, price_view))
    monkeypatch.setattr(run_price_alert_runner, "build_price_alert_runner", lambda **kwargs: runner)
    run_price_alert_runner.main(["--once", "--json"])
    text = capsys.readouterr().out
    assert TEST_INGEST_API_KEY not in text
    assert "Authorization" not in text


def test_m_env_isolation_for_runner_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRICEBRAIN_ALERT_RUNNER_INTERVAL", raising=False)
    clear_settings_cache()
    assert get_settings().pricebrain_alert_runner_interval_seconds == 60.0
    monkeypatch.setenv("PRICEBRAIN_ALERT_RUNNER_INTERVAL", "120")
    clear_settings_cache()
    assert get_settings().pricebrain_alert_runner_interval_seconds == 120.0


def test_n_malformed_alert_does_not_stop_cycle(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    target_repo: CrawlTargetRepository,
    runner_db: FakeFirestoreClient,
) -> None:
    _seed_target(target_repo)
    _seed_listing(runner_db, current=1_490_000, previous=1_599_000)
    alert_repo.create(
        target_id=TARGET_ID,
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    alert_repo.create(
        target_id="ssg_missing_target",
        mall_id="ssg",
        alert_type=PriceAlertType.PRICE_BELOW,
        threshold=1_500_000,
        now=NOW,
    )
    result = _runner(_service(alert_repo, price_view)).run_once(now=NOW)
    assert result.total_alerts == 2
    assert result.triggered == 1
    assert result.invalid == 1


def test_runner_once_json_cli(
    alert_repo: PriceAlertRepository,
    price_view: PriceOperationsView,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = _runner(_service(alert_repo, price_view))
    monkeypatch.setattr(run_price_alert_runner, "build_price_alert_runner", lambda **kwargs: runner)
    exit_code = run_price_alert_runner.main(["--once", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "total_alerts" in payload
