# 09. Firebase Implementation (Firestore Admin SDK)

- Project: PriceBrain
- Document: Firebase Implementation
- Version: 2.0
- Status: Final
- SSOT 역할: **Firestore Repository 구현 설계** (Schema SSOT 아님)
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md`
- DB 원칙: `docs/04_DATABASE_DESIGN.md`
- Runtime SSOT: `docs/13_SERVICE_AND_RUNTIME_ARCHITECTURE.md`
- 작성일: 2026-08-20
- 갱신일: 2026-08-20 (Firestore Admin SDK — Phase 1)

---

## 1. 문서 목적

본 문서는 **05 Schema SSOT**를 Python Backend에서 구현하기 위한 기준을 정의한다.

```text
07 Crawler  →  RawProductData
08 Pipeline  →  ValidatedProduct (dict)
09 Repository  →  Firestore Admin SDK (upsert + price_history append)
```

**본 문서가 정의하는 것**

- Firebase Admin SDK 초기화
- Repository Layer 구조·메서드
- **05 ↔ 09 Collection/Field/Path 추적표**
- `firestore.rules`, `firestore.indexes.json` 구현 파일 위치
- Runtime read/write (**13**과 동일)

**본 문서가 정의하지 않는 것**

- Collection·Field·Rules·Index 상세 → **05** (별도 Schema SSOT 금지)
- HTML 파싱·Normalization → **07**, **08**
- Frontend Firestore Client SDK → **13**, Frontend 코드

---

## 2. Runtime read/write (13 정합)

| 경로 | 구현 | SDK |
|------|------|-----|
| Catalog **read** | Next.js `services/*` | Firestore **Client SDK** |
| Catalog **write** | FastAPI → `repository/*` | **Admin SDK** |
| price_history **append** | `PriceHistoryRepository` | **Admin SDK** |
| crawl_* / validation_logs | `CrawlRepository`, `ValidationRepository` | **Admin SDK** |
| Auth | Next.js | Firebase Auth SDK |

**폐기:** Web → Flask → Repository only read 패턴. Flask → **FastAPI**.

Backend 패키지명: `pricebrain_app` — **project.mdc**

---

## 3. Firebase 서비스 구성

| 서비스 | 용도 |
|--------|------|
| **Cloud Firestore** | catalog·listings·price_history·crawl·validation |
| **Firebase Storage** | 이미지·raw 파일 (선택) |
| **Firebase Admin SDK (Python)** | 서버 write/read |

Realtime Database는 **사용하지 않는다.**

---

## 4. 구현 파일 (05 동기화)

| 파일 | SSOT | 설명 |
|------|------|------|
| `firestore.rules` | **05 §6** | Security Rules 전문 |
| `firestore.indexes.json` | **05 §7** | Composite Index |
| `.env` | project.mdc §13 | `FIREBASE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |

권장 경로 (코드 scaffold):

```text
pricebrain_app/
├── firebase/
│   ├── admin.py          # Admin SDK init
│   └── config.py
├── repository/
│   ├── base.py
│   ├── product_repository.py      # products
│   ├── listing_repository.py      # listings
│   ├── price_history_repository.py
│   ├── seller_repository.py
│   ├── gpu_repository.py          # vendors, families, models, board_partners
│   ├── mall_repository.py
│   ├── crawl_repository.py
│   └── validation_repository.py
├── api/                   # FastAPI routes
│   └── ingest.py
└── runner.py              # 07→08→09 orchestration
```

Rules·Index 파일 변경 시 **05 먼저** 갱신 후 본 파일·실제 JSON 동기화.

---

## 5. Admin SDK 초기화

```python
# pricebrain_app/firebase/admin.py
import firebase_admin
from firebase_admin import credentials, firestore

def get_firestore_client():
    if not firebase_admin._apps:
        cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
        firebase_admin.initialize_app(cred, {
            "projectId": os.environ["FIREBASE_PROJECT_ID"],
        })
    return firestore.client()
```

- `.env` / service account JSON은 Git에 커밋하지 않는다 — **project.mdc §13**
- 로컬: Firestore Emulator (`FIRESTORE_EMULATOR_HOST`) — Gate C

---

## 6. Repository Layer

### 6.1 책임

| Repository | Collection / Path | 주요 메서드 |
|------------|-------------------|-------------|
| `GpuRepository` | `gpu_vendors`, `gpu_families`, `gpu_models`, `board_partners` | `seed_*`, `get_model` |
| `ProductRepository` | `products` | `upsert_product`, `get_by_canonical_id` |
| `ListingRepository` | `listings` | `upsert_listing`, `get_by_mall_product` |
| `PriceHistoryRepository` | `listings/{id}/price_history` | `append_if_changed` |
| `SellerRepository` | `sellers` | `upsert_seller` |
| `MallRepository` | `malls` | `seed_malls` |
| `CrawlRepository` | `crawl_jobs`, `crawl_logs` | `create_job`, `log` |
| `ValidationRepository` | `validation_logs` | `log_validation` |

### 6.2 Persist 흐름 (ValidatedProduct → Firestore)

```python
def save_validated_product(db, data: dict) -> None:
    # 1. Resolve / upsert seller, product (products Collection)
    product_id = product_repo.upsert_from_validated(db, data)
    # 2. Upsert listing
    listing_id = listing_repo.upsert_from_validated(db, data, product_id)
    # 3. Append price_history if current_price changed
    price_history_repo.append_if_changed(db, listing_id, data["price"], data["crawled_at"])
```

- `products` = Canonical Product (**`canonical_products` Collection 사용 금지**)
- Listing Document ID: `{mall}_{external_product_id}` — **05 §2**

### 6.3 price_history append 규칙

```python
def append_if_changed(self, db, listing_id: str, new_price: int, crawled_at) -> bool:
    listing_ref = db.collection("listings").document(listing_id)
    prev = listing_ref.get().to_dict()
    if prev and prev.get("current_price") == new_price:
        return False
    history_id = str(int(crawled_at.timestamp() * 1000))
    listing_ref.collection("price_history").document(history_id).set({
        "price": new_price,
        "crawled_at": crawled_at,
        "previous_price": prev.get("current_price") if prev else None,
        "price_change": (new_price - prev["current_price"]) if prev else None,
    })
    listing_ref.update({"current_price": new_price, "crawled_at": crawled_at, "updated_at": SERVER_TIMESTAMP})
    return True
```

---

## 7. Firebase Storage (선택)

MVP: `listings.image_url`, `products.image_url`에 CDN URL.

Storage upload 시:

```text
products/{canonical_product_id}/main.jpg
```

Storage Rules는 Firestore와 별도. Admin SDK 또는 signed URL upload.

---

## 8. FastAPI 연동

```python
# pricebrain_app/api/ingest.py
@router.post("/internal/ingest/listing")
def ingest_listing(payload: ValidatedProductDTO, db=Depends(get_firestore_client)):
    save_validated_product(db, payload.dict())
    return {"status": "ok"}
```

- Crawler → Pipeline → **POST FastAPI** → Repository (로컬 MVP)
- 운영: Cloud Run 배포 선택 — **13 §5**

---

## 9. 05 ↔ 09 Collection / Field / Path 추적표

Schema 정의 SSOT: **05**. 본 표는 **구현 매핑** 추적용.

| 05 Collection / Path | 05 Document ID | 09 Repository | 09 Module / Method | 05 Field § |
|----------------------|----------------|---------------|-------------------|------------|
| `gpu_vendors` | code | `GpuRepository` | `seed_vendors()` | §3.1 |
| `gpu_families` | code | `GpuRepository` | `seed_families()` | §3.2 |
| `gpu_models` | slug | `GpuRepository` | `upsert_model()` | §3.3 |
| `board_partners` | slug | `GpuRepository` | `seed_partners()` | §3.4 |
| **`products`** | canonical slug | **`ProductRepository`** | **`upsert_product()`** | **§3.5** |
| `malls` | code | `MallRepository` | `seed_malls()` | §3.6 |
| `sellers` | slug | `SellerRepository` | `upsert_seller()` | §3.7 |
| **`listings`** | `{mall}_{external_id}` | **`ListingRepository`** | **`upsert_listing()`** | **§3.8** |
| `listings/{id}/price_history` | `{crawled_at_ms}` | `PriceHistoryRepository` | `append_if_changed()` | §3.9 |
| `crawl_jobs` | job_id | `CrawlRepository` | `create_job()`, `complete_job()` | §3.10 |
| `crawl_logs` | log_id | `CrawlRepository` | `log()` | §3.11 |
| `validation_logs` | log_id | `ValidationRepository` | `log_validation()` | §3.12 |
| `users/{uid}` | uid | (Phase 2+) | — | §3.13 |
| `users/{uid}/favorites` | product_id | (Phase 2+) | — | §3.14 |

### 9.1 ValidatedProduct (08 §26) → Firestore Path

| 08 Field | 05 Collection.Field | 09 Write |
|----------|---------------------|----------|
| `brand` | `products.brand` | `ProductRepository` |
| `gpu_model` | `products.gpu_model_id` (resolve slug) | `ProductRepository` + `GpuRepository` |
| `vram_gb` | `products.vram_gb` | `ProductRepository` |
| `manufacturer_part_number` | `products.manufacturer_part_number` | `ProductRepository` |
| `normalized_product_name` | `products.normalized_product_name`, `listings.normalized_product_name` | both repos |
| `mall` | `listings.mall_id`, `sellers.mall_id` | `ListingRepository`, `SellerRepository` |
| `product_id` | `listings.external_product_id`, doc ID suffix | `ListingRepository` |
| `raw_product_name` | `listings.raw_product_name` | `ListingRepository` |
| `price` | `listings.current_price`, `price_history.price` | `ListingRepository`, `PriceHistoryRepository` |
| `seller` | `sellers.*` → `listings.seller_id` | `SellerRepository` |
| `product_url` | `listings.product_url` | `ListingRepository` |
| `image_url` | `listings.image_url`, `products.image_url` | both repos |
| `crawled_at` | `listings.crawled_at`, `price_history.crawled_at` | both repos |

상세 매핑: **08 §26.1**

---

## 10. Security Rules·Index 구현

- Rules 원문: **05 §6** → `firestore.rules` (동일 내용)
- Index: **05 §7** → `firestore.indexes.json`
- 배포: `firebase deploy --only firestore:rules,firestore:indexes`

**09는 Rules를 재정의하지 않는다.** 변경은 05 → rules 파일 → 11 테스트 순.

---

## 11. 에러 처리·트랜잭션

| 상황 | 처리 |
|------|------|
| Listing upsert + history append | Batch write 또는 transaction |
| 중복 crawl | 동일 `listing_id` + 동일 price → history skip |
| missing `product_id` ref | `ValidationRepository` log + skip write |
| Admin credential failure | fail fast, no silent fallback |

---

## 12. 테스트 기준

| 항목 | 기준 |
|------|------|
| Unit | Repository mock Firestore client |
| Integration | Emulator + Admin SDK CRUD — **11 §8** |
| Rules | Client SDK deny write tests — **11 §9** (05 §6 참조) |
| Index | 쿼리 §5 패턴 Emulator에서 실행 — **11** |

---

## 13. 구현 체크리스트

- [ ] Admin SDK init + env
- [ ] `ProductRepository` → `products` (not `canonical_products`)
- [ ] `ListingRepository` → doc ID `{mall}_{external_product_id}`
- [ ] `PriceHistoryRepository` → subcollection append
- [ ] `firestore.rules` = 05 §6
- [ ] `firestore.indexes.json` = 05 §7
- [ ] FastAPI ingest endpoint
- [ ] 05 ↔ 09 추적표 §9와 코드 1:1

---

## 14. 관련 문서

| 문서 | 관계 |
|------|------|
| `05_FIREBASE_DATA_STRUCTURE.md` | **Schema SSOT** |
| `08_DATA_PIPELINE_AND_NORMALIZATION.md` | ValidatedProduct |
| `11_Testing_and_Quality_Assurance_Guide.md` | Rules·CRUD 테스트 |
| `13_SERVICE_AND_RUNTIME_ARCHITECTURE.md` | read/write |

---

## Appendix A. Design History

### A.1 v1.0 (RTDB + Flask)

v1.0은 Firebase Realtime Database + `canonical_products/` node + Flask Backend를 가정했다.

| v1.0 | v2.0 |
|------|------|
| Realtime Database | Cloud Firestore |
| `canonical_products` node | **`products` Collection** |
| Flask | **FastAPI** |
| Web read via API only | catalog read: Client SDK (**13**) |

과거 RTDB Repository 코드·node path는 Appendix 참고용이며 구현하지 않는다.
