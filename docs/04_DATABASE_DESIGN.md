# 04. Database Design

- Project: PriceBrain
- Document: Database Design
- Version: 2.0
- Status: Final
- SSOT 역할: **Firestore 설계 원칙·저장 정책** (Schema SSOT 아님)
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md`
- Runtime SSOT: `docs/13_SERVICE_AND_RUNTIME_ARCHITECTURE.md`
- 작성일: 2026-08-20
- 갱신일: 2026-08-20 (Firestore SSOT 정렬 — Phase 1)

---

## 1. 문서 목적

본 문서는 PriceBrain의 **데이터 저장 원칙·정책·아키텍처 관점**을 정의한다.

PriceBrain은 여러 쇼핑몰에서 GPU 상품 및 가격 데이터를 수집하고, 정규화하여 가격 비교·가격 이력 분석·향후 AI 분석에 활용한다.

**본 문서가 정의하는 것**

- 공식 Database 선택 (Cloud Firestore)
- 데이터 저장·업데이트 **원칙**
- 원본/정규화/이력 분리 **정책**
- Repository 계층 **개념** (구현은 09)
- Firebase Storage와 Firestore **역할 분리**
- Schema·Rules·Index **참조 관계**

**본 문서가 정의하지 않는 것**

- Collection·Field·Type 상세 → **05**
- Security Rules 전문 → **05 §6**
- Firestore Index 목록 → **05 §7**
- Python Repository 구현 → **09**
- Runtime read/write 경계 → **13**

---

## 2. Database 선택

PriceBrain의 **유일 공식 Database**는 **Cloud Firestore**이다.

| 서비스 | 역할 |
|--------|------|
| **Cloud Firestore** | 구조화된 catalog·가격·이력·크롤·검증 데이터 |
| **Firebase Storage** | 상품 이미지·Raw 파일 (선택, MVP는 CDN URL 우선) |
| **Firebase Authentication** | 사용자 인증 (Phase 2+) |
| **Firebase Hosting** | Next.js Frontend 배포 |

PostgreSQL, Firebase Realtime Database는 **현행 설계에서 사용하지 않는다.** (Design History: Appendix A)

---

## 3. SSOT 관계

```text
project.mdc (헌법)
    ↓
04 Database Design (원칙·정책) ──→ 05 Firestore Schema (Collection/Field/Rules/Index)
    ↓                                      ↓
13 Runtime (read/write)              09 Repository 구현
    ↓
08 Pipeline (Processing Object) ──→ 05 Field 매핑 (§26)
```

| 질문 | SSOT |
|------|------|
| 어떤 Collection이 있는가? | **05 §1** |
| Field·Type·Document ID는? | **05 §2–§4** |
| Security Rules·Index는? | **05 §6–§7** |
| 02 도메인 ↔ Firestore 매핑은? | **05 §8** |
| Frontend read / Backend write는? | **13** |
| Admin SDK Repository 코드 구조는? | **09** |

---

## 4. Firestore 아키텍처 (개념)

```text
                    PriceBrain
                        │
            ┌───────────┴───────────┐
            ↓                       ↓
     Cloud Firestore          Firebase Storage
            │                       │
   catalog collections          images/
   listings + price_history      raw/ (선택)
   crawl_* / validation_logs
```

**Catalog read:** Next.js → Firestore Client SDK (Security Rules) — **13**  
**Catalog write:** FastAPI → Admin SDK → Repository (09) — **13**

Collection 목록·경로·필드는 **05 §1**을 따른다. 본 절에 중복 기술하지 않는다.

---

## 5. 데이터 저장 원칙

### 5.1 원본 데이터 보존

크롤링 원본 필드(`raw_product_name`, `raw_price` 등)는 정규화 결과와 **분리 보존**한다.
Normalization 규칙 변경 시 재처리 가능해야 한다.

### 5.2 정규화 데이터 분리

Raw → Normalized → Validated 단계는 **08 Pipeline** 책임이다.
Firestore 저장 시 raw·normalized 필드 구분은 **05 listings/products Field**를 따른다.

### 5.3 Canonical Product와 Listing 분리

| 개념 | Collection | 의미 |
|------|------------|------|
| **Product (Canonical)** | `products` | "무슨 제품인가" |
| **Seller Listing** | `listings` | "어느 쇼핑몰·판매처에서 얼마에 판매되는가" |

`canonical_products` Collection은 **사용하지 않는다.** Canonical Product는 **`products`** Collection이다.

### 5.4 가격 이력 분리

- 현재 가격: `listings.current_price`
- 이력: `listings/{id}/price_history` subcollection
- **변경 시 append only**; 서버(Admin SDK)만 write — **13**

상세 Field·append 정책: **05 §4, §5**

### 5.5 파일과 구조화 데이터 분리

이미지 파일은 Storage(또는 외부 CDN URL)에 두고, Firestore Document에는 **URL/경로만** 저장한다.

### 5.6 참조 무결성

Firestore는 RDB FK 제약이 없다. **Repository(09)** 및 **Pipeline Validator(08)**에서 참조(`product_id`, `gpu_model_id` 등)를 검증한다.

### 5.7 중복 저장 (Denormalization)

조회 성능을 위해 `listings`에 `normalized_product_name` 등을 중복 저장할 수 있다.
허용 필드·동기화 정책은 **05 Field 표** 및 **09 upsert** 로직을 따른다.

### 5.8 판매 종료 처리

Listing Document를 물리 삭제하지 않고 `availability`/`status`로 표시한다.
Canonical Product·기존 price_history는 유지한다.

---

## 6. Document ID·식별자 원칙

Document ID 규칙·slug 생성 우선순위는 **05 §2** SSOT이다.

개념만 요약:

| 식별자 | 용도 |
|--------|------|
| `external_product_id` | 쇼핑몰 내부 상품 ID |
| `canonical_product_id` / `products` Document ID | PriceBrain 통합 제품 slug |
| `listings` Document ID | `{mall_code}_{external_product_id}` |

---

## 7. Query·Index 원칙

- Firestore 쿼리 제약(복합 필터·정렬)을 고려해 Collection을 설계한다 — 상세 Query 패턴: **05 §5**
- Index 정의는 **05 §7**과 `firestore.indexes.json` **1:1**
- Index 없이 운영 쿼리를 추가하지 않는다 — **project.mdc §17**

---

## 8. Security·접근 원칙

| 경로 | 원칙 |
|------|------|
| Catalog read | Client SDK, Rules public read |
| Catalog write | Admin SDK only, client write deny |
| price_history append | Admin SDK only |
| crawl_* / validation_logs | Admin SDK only, client 접근 deny |
| users / favorites | Auth + owner-only (Phase 2+) |

Rules 전문: **05 §6** (본 문서에 복제하지 않음)

테스트 시나리오: **11 §9** (05 Rules 참조)

---

## 9. Repository 계층 (개념)

Pipeline(08) 출력 → **Repository(09)** → Firestore Admin SDK.

```text
08 Pipeline  →  ValidatedProduct (dict)
                    ↓
09 Repository  →  upsert products / listings
                    ↓
                 append price_history (on change)
```

- Repository **구현**·메서드·추적표: **09**
- Processing Object ↔ Field 매핑: **08 §26.1**, **05**

Parser·Normalizer가 Firestore SDK를 직접 호출하지 않는다 — **project.mdc §6**

---

## 10. Crawling·Pipeline·Storage 연계

| 단계 | 문서 | Firestore 접근 |
|------|------|----------------|
| Crawl·Parse | 07 | 없음 (Raw만) |
| Normalize·Validate | 08 | 없음 |
| Persist | 09 | Admin SDK write |

크롤 로그·검증 로그 Collection: **05 §1** (`crawl_jobs`, `crawl_logs`, `validation_logs`)

---

## 11. MVP 데이터 범위

MVP catalog Collection (Seed + crawl write):

- `gpu_vendors`, `gpu_families`, `gpu_models`, `board_partners`
- `products`, `malls`, `sellers`, `listings`, `listings/.../price_history`
- `crawl_jobs`, `crawl_logs`, `validation_logs`

Phase 2+: `users/{uid}`, `users/{uid}/favorites`

상세 목록: **05 §1**

---

## 12. 변경 관리

Firestore Schema·Rules·Index 변경 시:

1. **05** 갱신 (Schema SSOT)
2. **09** Repository·추적표 갱신
3. **11** Rules 테스트 시나리오 갱신
4. `firestore.rules`, `firestore.indexes.json` 동기화
5. **project.mdc §17** 변경 절차 준수

---

## 13. 관련 문서

| 문서 | 역할 |
|------|------|
| `02_GPU_Data_Model.md` | 도메인 엔티티 |
| `05_FIREBASE_DATA_STRUCTURE.md` | **Schema SSOT** |
| `08_DATA_PIPELINE_AND_NORMALIZATION.md` | Pipeline·Processing Object |
| `09_FIREBASE_IMPLEMENTATION.md` | Repository·Admin SDK |
| `11_Testing_and_Quality_Assurance_Guide.md` | Rules·CRUD 테스트 |
| `13_SERVICE_AND_RUNTIME_ARCHITECTURE.md` | Runtime 경계 |

---

## Appendix A. Design History

### A.1 PostgreSQL (초기 PRD·02)

초기 PRD·GPU Data Model은 PostgreSQL + ERD를 가정했다.
관계형 정규화·FK 중심 설계였으나, **현행 SSOT는 Cloud Firestore**이다.

### A.2 Firebase Realtime Database (04 v1.0·05 v1.0·09 v1.0)

학습 맥락에서 RTDB + `canonical_products` node 구조를 검토했다.
RTDB flat node·`price_history` top-level 구조는 **Firestore Collection/subcollection으로 대체**되었다.

### A.3 현행 확정 (v2.0)

| 항목 | 확정 |
|------|------|
| Database | Cloud Firestore |
| Canonical Product | `products` Collection |
| Price History | `listings/{id}/price_history` |
| Schema SSOT | `05_FIREBASE_DATA_STRUCTURE.md` v2.0 |

과거 RTDB node명(`canonical_products` 등)은 Appendix에서만 참고한다.
