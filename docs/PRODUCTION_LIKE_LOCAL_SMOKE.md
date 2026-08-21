# Production-like Local Smoke Test

## 목적

PriceBrain Crawler 운영 경로를 **실제 Firebase Firestore**와 **실제 Worker**로 검증합니다.

```text
crawler_targets → CrawlerWorker → try_claim → SSGCrawler → CrawlerResult
  → (optional) IngestClient → FastAPI → Pipeline → Repository → Firestore
```

pytest는 FakeFirestore/Mock HTTP만 사용합니다. 실제 Firebase는 이 CLI로 **수동** 검증합니다.

---

## 사전 준비

1. `.env`에 Firebase 설정이 있어야 합니다.

   * `FIREBASE_PROJECT_ID=pricebrain-2fd0f`
   * `GOOGLE_APPLICATION_CREDENTIALS=...` (서비스 계정 JSON 경로)

2. (ingest 검증 시) FastAPI 실행:

```bash
uvicorn pricebrain_app.main:app --reload
```

3. crawl target 등록:

```bash
python -m pricebrain_app.scripts.register_crawl_target \
  --mall ssg \
  --url "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906" \
  --interval 3600
```

---

## Dry-run (기본 — ingest 없음)

```bash
python -m pricebrain_app.scripts.run_crawler_production_smoke \
  --target-id ssg_1000832367906
```

* **한 target만** 실행합니다.
* crawl + Firestore target 상태 업데이트는 수행합니다.
* **`--ingest` 없으면** `POST /internal/ingest/listing`을 호출하지 않습니다.

---

## Firestore 검증 (Console)

Firebase Console → Firestore → `crawler_targets/{target_id}`

확인 필드:

* `last_status`
* `last_error_code`
* `last_crawled_at`
* `next_crawl_at`
* `crawl_status` (idle)
* `lease_owner` / `lease_until` (null)

CLI에서 before/after snapshot:

```bash
python -m pricebrain_app.scripts.run_crawler_production_smoke \
  --target-id ssg_1000832367906 \
  --verify-firestore
```

---

## Ingest 포함

```bash
python -m pricebrain_app.scripts.run_crawler_production_smoke \
  --target-id ssg_1000832367906 \
  --ingest \
  --verify-firestore \
  --verify-product \
  --verify-listing \
  --verify-price-history
```

FastAPI가 실행 중이고 `PRICEBRAIN_INGEST_API_KEY`가 설정되어 있어야 합니다.

ingest 성공 시 `products/`, `listings/`, `price_history/` 존재 여부를 추가로 확인합니다.

**SSG가 403이면 ingest/entity 검증은 수행되지 않으며** `SSG_ACCESS_DENIED`로 기록되는 것이 정상입니다.

---

## Production E2E 자동 테스트

전체 ingest → Firestore 무결성 시나리오(A–F)는 pytest로 검증합니다.

```bash
pytest -q pricebrain_app/tests/test_production_e2e_ingest.py
```

---

## JSON 출력

```bash
python -m pricebrain_app.scripts.run_crawler_production_smoke \
  --target-id ssg_1000832367906 \
  --json
```

민감정보(API key, credential path, Authorization)는 출력되지 않습니다.

---

## SSG 403 해석

실제 SSG가 HTTP 403을 반환하는 경우 **코드 결함이 아닙니다**.

```text
HTTP 403
  → CrawlerResult HTTP_ERROR / SSG_ACCESS_DENIED
  → crawler_targets.last_status 업데이트
  → lease 해제
  → Smoke CLI exit 0
```

403 우회(User-Agent 위장, CAPTCHA 우회 등)는 추가하지 않습니다.

---

## Exit code

| Code | 의미 |
|------|------|
| 0 | Smoke 완료 (SUCCESS 또는 예상 가능한 HTTP_ERROR/403 포함) |
| 1 | 설정/대상 오류 (target 없음, disabled 등) |
| 2 | 운영 skip (다른 worker active lease) |

---

## 자동 테스트

```bash
pytest -q pricebrain_app/tests/test_production_smoke.py
```

가격 이력 dedup/append regression은 기존 `test_reingest_price_history.py`, `test_crawler_ingest_e2e.py`가 담당합니다.

---

## 관련 문서

* [CRAWLER_OPERATIONAL_GATE.md](./CRAWLER_OPERATIONAL_GATE.md) — FakeFirestore 기반 운영 Gate
