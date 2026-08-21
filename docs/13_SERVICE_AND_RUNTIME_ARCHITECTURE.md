# PriceBrain Service and Runtime Architecture

- 문서 버전: v1.0
- 문서 상태: Final
- SSOT 역할: **Runtime read/write 경계**
- 상위 SSOT: `.cursor/rules/project.mdc`
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md` (Collection·Field·Rules·Index — 본 문서에서 정의하지 않음)
- 최초 작성일: 2026-08-20

---

## 1. 문서 목적

본 문서는 PriceBrain의 **런타임 구성요소**, **read/write 경계**, **SDK 선택**을 정의한다.

- Collection·Field·Security Rules·Index의 상세는 **05**를 따른다.
- Crawler·Pipeline·Repository 구현 상세는 **07 · 08 · 09**를 따른다.
- 본 문서는 Schema를 중복 정의하지 않는다.

---

## 2. SSOT 관계

| 계층 | 문서 | 역할 |
|------|------|------|
| L0 | `project.mdc` | 기술 스택·아키텍처 원칙 |
| L1 | `01 PRD` | 제품 목표·MVP |
| L3 | `05 Firestore Data Structure` | Collection Schema SSOT |
| L4 | `07 / 08 / 09` | 수집·가공·저장 구현 |
| **L4** | **본 문서 (13)** | **Runtime read/write SSOT** |

---

## 3. 런타임 구성요소

| 구성요소 | 기술 | 책임 |
|----------|------|------|
| Frontend | Next.js (React, TypeScript, Tailwind) | UI, catalog **read**, Auth 연동 |
| Authentication | Firebase Authentication | 사용자 인증 (Phase 2+) |
| Database | Cloud Firestore | 상품·가격·이력 저장 |
| Backend API | Python FastAPI | catalog **write**, 크롤 결과 반영, AI/batch |
| Admin SDK | Firebase Admin SDK (Python) | 서버 전용 Firestore read/write |
| Client SDK | Firebase JS SDK (Web) | Frontend catalog read, Auth |
| Hosting | Firebase Hosting | Next.js 정적/SSR 배포 |
| Storage | Firebase Storage (선택) | 이미지·원본 파일 (MVP: CDN URL 필드 우선) |
| Crawler | Python (`pricebrain_app`) | 07 설계; write는 FastAPI 경유 |

**원칙:** UI에 크롤링 로직을 넣지 않는다. Client SDK로 catalog **write**를 허용하지 않는다 (Security Rules).

---

## 4. MVP read/write 패턴 (확정)

| 경로 | 패턴 | SDK | Security Rules |
|------|------|-----|----------------|
| Catalog **read** | Next.js `services/*` → Firestore 직접 조회 | **Client SDK** | catalog collections: public read |
| User / **Auth** | Next.js → Firebase Auth | Auth SDK | Auth 정책 |
| Catalog **write** | FastAPI → Repository → Firestore | **Admin SDK** | client write **deny** |
| **Crawler** write | Crawler → FastAPI → Admin SDK | Admin SDK | listings, price_history, crawl_* |
| **Price history append** | 서버만 | Admin SDK | subcollection append only (server) |
| **AI / batch / scheduled crawl** | FastAPI (로컬 MVP) → Cloud Run (운영 선택) | Admin SDK | server only |
| **Hosting** | Firebase Hosting | — | — |
| **Storage** | MVP: doc 필드 URL; 파일 업로드 시 Storage + Rules | Client/Admin | 분리 Rules |

### 4.1 Catalog read (Frontend)

- 검색, 상품 목록, 상품 상세, 가격 비교, 가격 이력 **조회**는 Next.js에서 Firestore Client SDK로 수행한다.
- Backend API를 거치지 않는다 (MVP).
- Rules는 catalog collections에 대해 익명/인증 사용자 read를 허용한다.

### 4.2 Catalog write (Backend)

- listings upsert, price_history append, crawl_jobs / crawl_logs 기록은 **FastAPI + Admin SDK**만 수행한다.
- Frontend Client SDK write는 Rules에서 deny한다.

### 4.3 Crawler 경로

```text
Mall Site
  → Crawler (07) → RawProductData
  → Pipeline (08) → ValidatedProduct
  → FastAPI endpoint
  → Repository (09) → Admin SDK → Firestore
```

- 로컬 MVP: Crawler와 FastAPI를 동일 머신에서 실행 가능.
- 운영: FastAPI(및 Crawler 트리거)를 **Cloud Run**에 배포하는 것을 선택 사항으로 둔다.

### 4.4 Price history

- `listings/{id}/price_history` subcollection은 **변경 시 append only**.
- append는 Admin SDK(서버)만 수행한다.

---

## 5. FastAPI vs Cloud Run

| 단계 | Backend | 비고 |
|------|---------|------|
| **로컬 MVP** | FastAPI 로컬 실행 | Emulator 또는 dev Firestore 프로젝트 |
| **운영 (선택)** | Cloud Run + FastAPI | 스케줄 크롤·AI batch에 적합 |
| **Frontend** | Firebase Hosting | Next.js build/deploy |

FastAPI는 project.mdc §5 Backend SSOT이다. Flask는 사용하지 않는다.

---

## 6. Admin SDK vs Client SDK

| SDK | 사용 주체 | 용도 |
|-----|-----------|------|
| **Client SDK** | Next.js (브라우저) | catalog read, Auth |
| **Admin SDK** | FastAPI, Crawler write path, batch | 모든 write, price_history append, crawl_* |

환경 변수 예시는 `project.mdc` §13을 따른다 (`FIREBASE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` 등).

---

## 7. 컴포넌트 책임 매트릭스

| 영역 | Frontend | FastAPI | Crawler (07) | Pipeline (08) | Repository (09) |
|------|----------|---------|--------------|---------------|-----------------|
| UI / UX | O | — | — | — | — |
| Catalog read | O (Client SDK) | — | — | — | — |
| Auth | O (Auth SDK) | — | — | — | — |
| HTTP API (write) | — | O | — | — | — |
| Mall 수집 | — | — | O | — | — |
| 정제·매칭 | — | — | — | O | — |
| Firestore persist | — | O (via 09) | — | — | O (Admin SDK) |
| AI 분석 (Phase 4+) | 표시 | O (호출·저장) | — | — | O (결과 저장) |

---

## 8. 데이터 흐름 (Runtime)

```text
[사용자]
  ↓
[Next.js / Firebase Hosting]
  ├─ catalog read ──→ Firestore (Client SDK, Rules)
  └─ Auth ──→ Firebase Authentication

[Crawler / Scheduler]
  ↓
[FastAPI] ──→ [Pipeline 08] ──→ [Repository 09]
  ↓
Firestore (Admin SDK)
  listings, price_history, crawl_*
```

가격 분석·시각화·AI 결과 표시는 Frontend read + (필요 시) FastAPI batch write 조합으로 구현한다. 상세 알고리즘은 PRD·08·AI spec을 따른다.

---

## 9. Firebase 서비스 (MVP)

| 서비스 | MVP 사용 |
|--------|----------|
| Cloud Firestore | O (유일 공식 DB) |
| Firebase Authentication | Phase 2+ (설계 반영) |
| Firebase Hosting | O |
| Firebase Storage | 선택 (이미지 원본) |
| Cloud Run | 선택 (운영 Backend) |
| Firebase Emulator Suite | 개발·Gate C 검증 |

---

## 10. project.mdc 정합 체크리스트

| project.mdc 항목 | 본 문서 |
|------------------|---------|
| §5 Backend: Python, FastAPI | §5, §6 |
| §5 Database: Cloud Firestore | §3, §4 |
| §6 Frontend/Backend/Crawler 분리 | §7 |
| §13 env: Firebase credentials | §6 |
| Client catalog write 금지 | §4.2 |

---

## 11. 관련 문서

| 문서 | 관계 |
|------|------|
| `01 PRD` | 제품·Phase |
| `05 Firestore Data Structure` | Schema·Rules·Index |
| `07 Crawling Implementation` | Crawler only |
| `08 Pipeline and Normalization` | Pipeline only |
| `09 Firebase Implementation` | Repository·Admin SDK |
| `10 Deployment Guide` | Emulator·초기 Firebase 설정 |
| `11 Testing Guide` | Rules·CRUD 테스트 |
| `12 Operation Plan` | 운영·배포·비용 |

**09·10 read/write 표는 본 문서 §4와 동일해야 한다.** (Phase 3 정렬 완료 — `09` §2, `10` §10.5.1 참조)

---

## 12. Design History (참고)

초기 PRD·일부 설계 문서는 PostgreSQL 또는 Firebase Realtime Database를 가정했다.
**현행 Runtime SSOT는 Cloud Firestore + FastAPI + Firebase Hosting이다.**
과거 DB 가정은 각 문서 Appendix 또는 Phase 1~2 정렬 시 Design History로만 보존한다.
