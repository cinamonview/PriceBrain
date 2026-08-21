# Crawler Operational Verification Gate

PriceBrain crawler worker가 로컬 `.env`와 무관하게 반복 실행 가능한지 검증하는 Gate입니다.
테스트는 `FakeFirestore`와 mocked HTTP만 사용하며, 실제 SSG/Firestore production에는 요청하지 않습니다.

## 자동 검증

```bash
pytest -q pricebrain_app/tests/test_crawler_operational_smoke.py
pytest -q
```

운영 Gate가 검증하는 항목:

| Gate | 내용 |
|------|------|
| A | due target claim → crawl → 저장 → lease 해제 |
| B | active lease 시 두 번째 worker skip, ingest 미실행 |
| C | 만료 lease reclaim |
| D | 403 / parse / timeout 격리, cycle 계속 |
| E | ingest 500 격리, lease 해제, 다음 target 처리 |
| F | graceful shutdown — shutdown 후 신규 claim 중단 |
| CLI | `--help`, `--once` (due 없음) exit 0 |

## 로컬 수동 검증 (production Firestore)

SSG가 403을 반환해도 worker는 `HTTP_ERROR` / `SSG_ACCESS_DENIED`로 기록하고 **exit 0**으로 종료하는 것이 정상입니다.
403 우회 코드(User-Agent 위장, CAPTCHA 우회 등)는 추가하지 않습니다.

### 1. FastAPI 실행

```bash
uvicorn pricebrain_app.main:app --reload
```

### 2. Target 등록

```bash
python -m pricebrain_app.scripts.register_crawl_target \
  --mall ssg \
  --url "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906" \
  --interval 3600
```

### 3. Worker 1회 실행

```bash
python -m pricebrain_app.scripts.run_crawler_worker --once
```

예상 출력 (due target 없을 때):

```text
total: 0
claimed=0 skipped=0
```

exit code: `0`

### 4. Ingest 포함

```bash
python -m pricebrain_app.scripts.run_crawler_worker --once --ingest
```

FastAPI ingest API와 `.env`의 `PRICEBRAIN_INGEST_API_KEY`가 설정되어 있어야 ingest가 성공합니다.

## 아키텍처 (회귀 방지)

```text
Crawler
  ↓
IngestClient
  ↓
FastAPI
  ↓
Pipeline
  ↓
Repository
  ↓
Firestore
```

## 보안 체크리스트

- API key 하드코딩 금지
- Authorization / Bearer / API key / credentials path 로그 금지
- URL query parameter masking 정책 유지
