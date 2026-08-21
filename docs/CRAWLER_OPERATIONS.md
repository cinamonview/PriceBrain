# Crawler Operations & Observability

운영자가 Firestore Console 없이 crawler 상태를 확인하기 위한 **읽기 전용** CLI 계층입니다.

## CLI

### 전체 상태

```bash
python -m pricebrain_app.scripts.crawler_status
python -m pricebrain_app.scripts.crawler_status --json
```

### Target 목록

```bash
python -m pricebrain_app.scripts.list_crawl_targets
python -m pricebrain_app.scripts.list_crawl_targets --mall ssg --due
python -m pricebrain_app.scripts.list_crawl_targets --failed --json
```

### 최근 실패

```bash
python -m pricebrain_app.scripts.list_crawler_failures --limit 20
python -m pricebrain_app.scripts.list_crawler_failures --mall ssg
```

### Target 상세

```bash
python -m pricebrain_app.scripts.show_crawl_target --target-id ssg_1000832367906
python -m pricebrain_app.scripts.show_crawl_target --target-id ssg_1000832367906 --with-price-history
```

### 스케줄

```bash
python -m pricebrain_app.scripts.crawler_schedule
python -m pricebrain_app.scripts.crawler_schedule --json
```

## Observability

- **Structured logs**: Worker/Scheduler가 `target_due`, `target_claimed`, `crawl_success`, `ingest_error`, `lease_released` 등 이벤트를 기록합니다.
- **CrawlerMetrics**: 프로세스 내 메모리 카운터 (`crawler.metrics`) — 향후 Prometheus 등으로 확장 가능
- **Worker health**: 마지막 worker cycle 요약 (`crawler.worker_health`)

## Security

- URL masking: `safe_url_for_log`
- JSON/CLI 출력: API key, credential path redact
- Firestore schema 변경 없음 — `crawler_targets` 읽기 전용 집계

## Tests

```bash
pytest -q pricebrain_app/tests/test_crawler_observability.py
```
