# 05. Firebase Data Structure (Firestore Schema SSOT)

- Project: PriceBrain
- Document: Firebase Data Structure
- Version: 2.0
- Status: Final
- SSOT 역할: **Cloud Firestore Collection / Field / Rules / Index / 02 매핑**
- DB 원칙 SSOT: `docs/04_DATABASE_DESIGN.md`
- Runtime SSOT: `docs/13_SERVICE_AND_RUNTIME_ARCHITECTURE.md`
- 작성일: 2026-08-20
- 갱신일: 2026-08-20 (Firestore SSOT Final — Phase 1)

---

## 1. Collection 목록

| Collection / Path | Document ID | 02 도메인 | MVP | 비고 |
|-------------------|-------------|-----------|-----|------|
| `gpu_vendors` | code (`NVIDIA`) | GPU Vendor | O | Seed |
| `gpu_families` | code (`GEFORCE_RTX`) | GPU Family | O | FK: `vendor_id` |
| `gpu_models` | slug (`rtx_5080`) | GPU Model | O | FK: `family_id` |
| `board_partners` | slug (`ZOTAC`) | Board Partner | O | Seed |
| `products` | canonical slug | **Product (Canonical)** | O | **`products` = Canonical Product** |
| `malls` | code (`SSG`) | (인프라) | O | Seed |
| `sellers` | slug | Seller | O | FK: `mall_id` |
| `listings` | `{mall_code}_{external_product_id}` | **Seller Listing** | O | FK: `product_id` |
| `listings/{id}/price_history` | `{crawled_at_ms}` | **Price History** | O | subcollection, append on change |
| `crawl_jobs` | `job_id` | — | O | Admin only |
| `crawl_logs` | `log_id` | — | O | Admin only |
| `validation_logs` | `log_id` | — | O | Admin only |
| `pending_gpu_models` | slug (`rtx_4070`) | **Pending GPU Model (미승인)** | O | Admin only, `gpu_models`와 분리 |
| `users/{uid}` | Firebase Auth `uid` | User | Phase 2+ | owner read/write |
| `users/{uid}/favorites` | `product_id` | Favorite | Phase 2+ | owner read/write |

**폐기:** `canonical_products` Collection — **현행 Schema에서 사용하지 않음.** Canonical Product는 `products`이다.

**Price Snapshot (02):** 별도 top-level Collection 없음. 스냅샷은 `price_history` Document 1건으로 표현.

---

## 2. Document ID 규칙

| Collection | 규칙 | 예 |
|------------|------|-----|
| `gpu_vendors` | 대문자 vendor code | `NVIDIA` |
| `gpu_families` | 대문자 snake code | `GEFORCE_RTX` |
| `gpu_models` | 소문자 slug | `rtx_5080` |
| `board_partners` | 대문자 slug | `ZOTAC` |
| `products` | `canonical_product_id` slug | `ZOTAC-RTX5080-SOLIDCORE-16GB` |
| `malls` | 쇼핑몰 code | `SSG` |
| `sellers` | `{mall_code}_{normalized_seller_slug}` | `SSG_HITINFO` |
| `listings` | `{mall_code}_{external_product_id}` | `SSG_1000832367906` |
| `price_history` | Unix ms string of `crawled_at` | `1724047200000` |
| `crawl_jobs` | UUID 또는 `{mall}_{timestamp}` | `SSG_20260820_001` |
| `crawl_logs` | auto ID 또는 UUID | — |
| `validation_logs` | auto ID 또는 UUID | — |
| `pending_gpu_models` | 소문자 slug (`gpu_models`와 동일 규칙) | `rtx_4070` |

### 2.1 canonical_product_id 생성 우선순위

1. `manufacturer_part_number` 기반 slug
2. Manufacturer model number
3. `brand` + `gpu_model` + `vram_gb` + normalized model token
4. `normalized_product_name` hash/slug (최후)

---

## 3. Field / Type (Collection별)

### 3.1 `gpu_vendors`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `code` | string | O | Document ID와 동일 |
| `name` | string | O | 표시명 |
| `active` | boolean | O | |
| `created_at` | timestamp | O | |

### 3.2 `gpu_families`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `code` | string | O | Document ID |
| `name` | string | O | |
| `vendor_id` | string | O | → `gpu_vendors` |
| `active` | boolean | O | |
| `created_at` | timestamp | O | |

### 3.3 `gpu_models`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `slug` | string | O | Document ID |
| `gpu_series` | string | O | 예: `RTX` |
| `gpu_model` | string | O | 예: `RTX 5080` |
| `vendor_id` | string | O | → `gpu_vendors` |
| `family_id` | string | O | → `gpu_families` |
| `architecture` | string | | 예: `Blackwell` |
| `vram_gb` | number | O | |
| `active` | boolean | O | |
| `created_at` | timestamp | O | |

### 3.4 `board_partners`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `slug` | string | O | Document ID |
| `name` | string | O | |
| `display_name` | string | O | |
| `active` | boolean | O | |
| `created_at` | timestamp | O | |

### 3.5 `products` (Canonical Product)

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `canonical_product_id` | string | O | Document ID와 동일 |
| `brand` | string | O | Board Partner 브랜드 |
| `board_partner_id` | string | O | → `board_partners` |
| `gpu_model_id` | string | O | → `gpu_models` |
| `normalized_product_name` | string | O | |
| `vram_gb` | number | O | |
| `manufacturer_part_number` | string | | nullable |
| `image_url` | string | | CDN 또는 Storage URL |
| `active` | boolean | O | |
| `created_at` | timestamp | O | |
| `updated_at` | timestamp | O | |

**Product Specification (02):** MVP는 `products` Document 필드로 통합. 별도 Collection은 Phase 2+ 검토.

### 3.6 `malls`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `code` | string | O | Document ID |
| `name` | string | O | |
| `display_name` | string | O | |
| `active` | boolean | O | MVP: `SSG` only |
| `created_at` | timestamp | O | |

### 3.7 `sellers`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `slug` | string | O | Document ID |
| `seller_name` | string | O | raw 표시명 |
| `normalized_seller_name` | string | O | |
| `mall_id` | string | O | → `malls` |
| `active` | boolean | O | |
| `created_at` | timestamp | O | |

### 3.8 `listings` (Seller Listing)

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `product_id` | string | O | → `products` Document ID |
| `mall_id` | string | O | → `malls` |
| `external_product_id` | string | O | 쇼핑몰 상품 ID |
| `seller_id` | string | O | → `sellers` |
| `raw_product_name` | string | O | 크롤 원본 |
| `normalized_product_name` | string | O | 조회 denorm |
| `current_price` | number | O | 현재 가격 (원) |
| `product_url` | string | O | |
| `image_url` | string | | |
| `availability` | boolean | O | |
| `status` | string | O | `AVAILABLE` \| `UNAVAILABLE` |
| `crawled_at` | timestamp | O | 마지막 수집 시각 |
| `updated_at` | timestamp | O | |

### 3.9 `listings/{id}/price_history`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `price` | number | O | 해당 시점 가격 |
| `crawled_at` | timestamp | O | |
| `previous_price` | number | | 변경 시 이전 가격 |
| `price_change` | number | | `price - previous_price` |

append 조건: `current_price` 변경 시에만 Admin SDK로 추가 — **13**, **09**

### 3.10 `crawl_jobs`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `job_id` | string | O | Document ID |
| `mall_id` | string | O | |
| `status` | string | O | `PENDING` \| `RUNNING` \| `COMPLETED` \| `FAILED` |
| `keyword` | string | | |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `error_message` | string | | |

### 3.11 `crawl_logs`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `log_id` | string | O | Document ID |
| `job_id` | string | O | → `crawl_jobs` |
| `mall_id` | string | O | |
| `level` | string | O | `INFO` \| `WARN` \| `ERROR` |
| `message` | string | O | |
| `created_at` | timestamp | O | |

### 3.12 `validation_logs`

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `log_id` | string | O | Document ID |
| `source` | string | O | 예: `pipeline`, `ssg_validation` |
| `status` | string | O | `PASS` \| `FAIL` |
| `details` | map | | |
| `created_at` | timestamp | O | |

### 3.12.1 `pending_gpu_models`

Parser가 생성했지만 `gpu_models` Master에 없는 GPU model의 **격리(quarantine) 영역**.
정상 상품으로 저장하지도, 422로 폐기하지도 않기 위한 검토 대기 entity.

**경계:** `gpu_models` = 승인된 canonical reference / `pending_gpu_models` = 미승인 발견 모델.
**자동 승격 없음** — 이 Collection의 문서가 `gpu_models`로 자동 등록되는 경로는 존재하지 않는다.

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `gpu_model_id` | string | O | Document ID. `gpu_models` slug 규칙과 동일 (`rtx_4070`) |
| `display_name` | string | | Parser가 추출한 표시명 (`RTX 4070`) |
| `gpu_series` | string | | `RTX` \| `GTX` \| `RX` \| `Arc` |
| `detected_by` | string | O | 발견 지점 (`pipeline.gpu_parser`) |
| `first_seen_at` | timestamp | O | 최초 발견. 재발견 시 변경되지 않음 |
| `last_seen_at` | timestamp | O | 최근 발견 |
| `seen_count` | number | O | 동일 canonical slug 누적 발견 횟수 |
| `source_malls` | array\<string\> | O | canonical 소문자 `mall_id` (`["elevenst", "ssg"]`) |
| `example_product_names` | array\<string\> | O | 검토용 예시. 최대 5건 |
| `example_product_urls` | array\<string\> | O | 검토용 예시. 최대 5건. tracking param 제거된 정규화 URL |
| `status` | string | O | `PENDING_REVIEW` \| `APPROVED` \| `REJECTED`. 재발견 시 보존됨 |

`vendor_id` / `family_id`는 **저장하지 않는다.** Parser가 추론할 수 없고, Master reference data를
추측으로 채우면 안 되기 때문이다 (§3.3). 승인 시 사람이 지정한다.

`seller` / `seller_id` / `price`는 저장하지 않는다. GPU model 승인 판단에 불필요하다.

### 3.13 `users/{uid}` (Phase 2+)

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `email` | string | | |
| `display_name` | string | | |
| `role` | string | | `user` \| `admin` |
| `created_at` | timestamp | O | |

### 3.14 `users/{uid}/favorites/{product_id}` (Phase 2+)

| Field | Type | Required | 설명 |
|-------|------|----------|------|
| `product_id` | string | O | → `products` |
| `created_at` | timestamp | O | |

---

## 4. Subcollection: price_history

```text
listings/{listingId}/
    └── price_history/{crawled_at_ms}
            ├── price
            ├── crawled_at
            ├── previous_price (optional)
            └── price_change (optional)
```

- top-level `price_history` Collection **없음** (RTDB 잔재 폐기)
- Client SDK: read allow (catalog)
- Client SDK: write **deny**
- Admin SDK: append on price change only

---

## 5. Query 패턴

| Use case | Collection | Query | Index |
|----------|------------|-------|-------|
| GPU 모델 목록 | `gpu_models` | `where active == true` | 단일 field |
| Canonical Product by GPU | `products` | `where gpu_model_id == ?` | §7 |
| Product search (MVP) | `products` | prefix / client filter on `normalized_product_name` | §7 |
| Mall별 listing | `listings` | `where mall_id == ?` | §7 |
| Product별 최저가 listing | `listings` | `where product_id == ? orderBy current_price asc limit 1` | §7 |
| Product별 전체 listing | `listings` | `where product_id == ?` | §7 |
| Listing 가격 이력 차트 | `listings/{id}/price_history` | `orderBy crawled_at asc` | subcollection |
| Mall별 최근 crawl job | `crawl_jobs` | `where mall_id == ? orderBy started_at desc limit N` | §7 (composite) |
| 전체 최근 crawl job | `crawl_jobs` | `orderBy started_at desc limit N` | single-field (`started_at`; Firestore automatic) |

---

## 6. Security Rules (SSOT)

구현 파일: `firestore.rules` (Repository root — **09 §4**)

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // --- Catalog: public read, client write deny (MVP) ---
    match /gpu_vendors/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /gpu_families/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /gpu_models/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /board_partners/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /products/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /malls/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /sellers/{docId} {
      allow read: if true;
      allow write: if false;
    }
    match /listings/{listingId} {
      allow read: if true;
      allow write: if false;

      match /price_history/{historyId} {
        allow read: if true;
        allow write: if false;
      }
    }

    // --- Operational logs: client deny ---
    match /crawl_jobs/{docId} {
      allow read, write: if false;
    }
    match /crawl_logs/{docId} {
      allow read, write: if false;
    }
    match /validation_logs/{docId} {
      allow read, write: if false;
    }
    // Unapproved GPU models awaiting review — never client-visible, Admin SDK only.
    match /pending_gpu_models/{docId} {
      allow read, write: if false;
    }

    // --- User data (Phase 2+) ---
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;

      match /favorites/{productId} {
        allow read, write: if request.auth != null && request.auth.uid == userId;
      }
    }
  }
}
```

**Admin SDK**는 Security Rules를 우회한다. catalog write·price_history append·crawl_* write는 **FastAPI + Admin SDK**만 — **13**

**11** 테스트는 본 §6 Rules를 **참조**하며 Rules 전문을 복제하지 않는다.

---

## 7. Firestore Index (`firestore.indexes.json` SSOT)

구현 파일: `firestore.indexes.json` (**09 §4**)

```json
{
  "indexes": [
    {
      "collectionGroup": "listings",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "product_id", "order": "ASCENDING" },
        { "fieldPath": "current_price", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "listings",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "mall_id", "order": "ASCENDING" },
        { "fieldPath": "current_price", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "listings",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "product_id", "order": "ASCENDING" },
        { "fieldPath": "mall_id", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "products",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "gpu_model_id", "order": "ASCENDING" },
        { "fieldPath": "brand", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "products",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "active", "order": "ASCENDING" },
        { "fieldPath": "normalized_product_name", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "price_history",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "crawled_at", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "crawl_jobs",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "mall_id", "order": "ASCENDING" },
        { "fieldPath": "started_at", "order": "DESCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

`crawl_jobs` composite index는 **Mall별** 쿼리(`where mall_id == ? orderBy started_at desc`) 전용 (**§5**). 전역 `orderBy started_at desc`는 composite 불필요 — Firestore automatic single-field index.

---

## 8. 02 GPU Data Model ↔ Collection 매핑

| 02 엔티티 (§28 MVP) | Firestore Collection / Path | Document ID | 비고 |
|---------------------|----------------------------|-------------|------|
| GPU Vendor | `gpu_vendors` | code | Seed |
| GPU Family | `gpu_families` | code | |
| GPU Model | `gpu_models` | slug | |
| Board Partner | `board_partners` | slug | Product.brand |
| **Product** | **`products`** | canonical slug | **Canonical Product** |
| Product Specification | `products` 필드 | — | MVP embedded |
| Seller | `sellers` | slug | |
| **Seller Listing** | **`listings`** | `{mall}_{external_id}` | |
| Price Snapshot | `listings/{id}/price_history` | `{crawled_at_ms}` | 1 snapshot = 1 doc |
| Price History | `listings/{id}/price_history` | (시계열) | subcollection |
| User (Phase 2+) | `users/{uid}` | uid | Auth |
| Favorite (Phase 2+) | `users/{uid}/favorites` | product_id | |

**향후 (02 §28):** Price Analysis, AI Analysis, Price Alert — MVP Collection 없음; Phase 4+ 별도 설계.

---

## 9. 예시 Document (SSG RTX 5080)

### `products/ZOTAC-RTX5080-SOLIDCORE-16GB`

```json
{
  "canonical_product_id": "ZOTAC-RTX5080-SOLIDCORE-16GB",
  "brand": "ZOTAC",
  "board_partner_id": "ZOTAC",
  "gpu_model_id": "rtx_5080",
  "normalized_product_name": "ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB",
  "vram_gb": 16,
  "manufacturer_part_number": "ZT-B50800D-10P",
  "image_url": "https://...",
  "active": true,
  "created_at": "2026-08-20T10:00:00Z",
  "updated_at": "2026-08-20T10:00:00Z"
}
```

### `listings/SSG_1000832367906`

```json
{
  "product_id": "ZOTAC-RTX5080-SOLIDCORE-16GB",
  "mall_id": "SSG",
  "external_product_id": "1000832367906",
  "seller_id": "SSG_HITINFO",
  "raw_product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
  "normalized_product_name": "ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB",
  "current_price": 2429000,
  "product_url": "https://...",
  "image_url": "https://...",
  "availability": true,
  "status": "AVAILABLE",
  "crawled_at": "2026-08-20T10:00:00Z",
  "updated_at": "2026-08-20T10:00:00Z"
}
```

---

## 10. Firebase Storage 경로 (참고)

MVP: listing/product Document의 `image_url`에 쇼핑몰 CDN URL 저장.

Storage 사용 시:

```text
products/{canonical_product_id}/main.jpg
raw/{mall_code}/{yyyy-mm-dd}/{crawl_id}.json
```

Storage Rules는 Firestore Rules와 **별도** 관리 — **09 §7**

---

## 11. 관련 문서

| 문서 | 관계 |
|------|------|
| `04_DATABASE_DESIGN.md` | 원칙·정책 (Schema X) |
| `08_DATA_PIPELINE_AND_NORMALIZATION.md` | §26.1 Processing Object ↔ Field |
| `09_FIREBASE_IMPLEMENTATION.md` | Admin SDK·추적표·rules/index 파일 |
| `11_Testing_and_Quality_Assurance_Guide.md` | §6 Rules 테스트 |
| `13_SERVICE_AND_RUNTIME_ARCHITECTURE.md` | read/write |

---

## Appendix A. Design History

### A.1 PostgreSQL

초기 PRD·02는 PostgreSQL ERD를 가정. 관계형 테이블 `products`, `listings`, `price_history` 개념은 Firestore Collection으로 **이전**되었으나 RDB FK·JOIN 패턴은 사용하지 않는다.

### A.2 Firebase Realtime Database (v1.0)

v1.0 본 문서는 RTDB root `pricebrain/` node 구조였다:

- top-level `price_history/{listing_id}` — **폐기** → subcollection
- `canonical_products` node — **폐기** → `products` Collection
- `gpu_models` only (vendor/family 분리 없음) — **확장** → `gpu_vendors`, `gpu_families`, `board_partners`

### A.3 v2.0 확정

| v1.0 (RTDB) | v2.0 (Firestore) |
|-------------|------------------|
| `canonical_products` | **`products`** |
| `price_history` (top-level) | `listings/{id}/price_history` |
| Realtime Database | **Cloud Firestore** |
| Web → API → DB only read | catalog read: Client SDK (**13**) |

`canonical_products` 문자열은 Appendix에서만 유지한다.
