# PriceBrain

> AI 기반 상품 가격 데이터 수집 · 검증 · 저장 및 가격 이력 관리 플랫폼

PriceBrain은 상품 데이터를 수집하고, Pipeline을 통해 데이터를 검증한 뒤,
Firebase Firestore에 정규화된 형태로 저장하고 가격 변경 이력을 관리하는
Backend 중심의 데이터 처리 프로젝트입니다.

본 프로젝트는 **Crawler → Pipeline → Repository → Firestore** 구조를 중심으로
설계되었으며, FastAPI를 통해 외부 요청을 처리할 수 있도록 구성했습니다.

---

## 📌 Project Overview

PriceBrain의 핵심 목표는 상품 데이터를 안정적으로 수집하고,
검증된 데이터만 저장하며, 가격 변경 이력을 추적할 수 있는
확장 가능한 데이터 처리 시스템을 구축하는 것입니다.

단순 CRUD 형태의 애플리케이션이 아니라 다음과 같은
**책임 분리와 데이터 무결성**을 중심으로 설계했습니다.

```text
Crawler
   │
   ▼
Pipeline
   │
   │ ValidatedProduct
   ▼
Runner / Service
   │
   ▼
Repository
   │
   ▼
Firebase Firestore

외부 HTTP 요청은 FastAPI를 통해 처리합니다.

Client
   │
   ▼
FastAPI
   │
   ▼
Pipeline
   │
   ▼
Repository
   │
   ▼
Firestore
🛠 Tech Stack
Backend
Python
FastAPI
Uvicorn
Pydantic
Database / Cloud
Firebase
Cloud Firestore
Firebase Emulator Suite
Google Cloud Run (Production deployment 준비)
Data Processing
Python Pipeline
Data Validation
Price History Tracking
GPU Master Reference Data
Testing
pytest
Firebase Firestore Emulator
Firebase Rules Unit Testing
Node.js Rules Test Runner
Deployment
GitHub
Docker
Google Cloud Run
Firebase Firestore

현재 프로젝트에서는 Docker / Cloud Run 배포 구조까지 준비했으며,
실제 Production Cloud Run 배포는 별도 환경에서 진행할 예정입니다.

🏗 Architecture

PriceBrain은 각 계층의 책임을 명확하게 분리합니다.

┌──────────────────────────────┐
│           Client             │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│          FastAPI             │
│                              │
│  /health                     │
│  /internal/ingest/listing    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│          Pipeline            │
│                              │
│ Raw Product                  │
│      ↓                       │
│ Validation                   │
│      ↓                       │
│ ValidatedProduct             │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│        Runner / Service      │
│                              │
│ Crawl orchestration          │
│ Validation persistence       │
│ Crawl log persistence        │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         Repository           │
│                              │
│ ListingRepository            │
│ PriceHistoryRepository       │
│ CrawlRepository              │
│ ValidationRepository         │
│ GpuRepository                │
│ ReferenceRepository          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       Firebase Firestore     │
└──────────────────────────────┘
📂 Project Structure
Project-PriceBrain/
│
├── pricebrain_app/
│   │
│   ├── api/
│   │   ├── deps.py
│   │   └── ingest.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   ├── crawler/
│   │
│   ├── pipeline/
│   │
│   ├── repository/
│   │   ├── crawl_repository.py
│   │   ├── gpu_master_seed.py
│   │   ├── gpu_repository.py
│   │   ├── listing_repository.py
│   │   ├── operational_service.py
│   │   ├── price_history_repository.py
│   │   └── reference_repository.py
│   │
│   ├── scripts/
│   │   └── seed_gpu_master.py
│   │
│   ├── tests/
│   │   ├── node/
│   │   ├── fake_firestore.py
│   │   ├── test_repository.py
│   │   ├── test_gpu_master.py
│   │   ├── test_crawl_logs.py
│   │   └── ...
│   │
│   ├── main.py
│   └── runner.py
│
├── docs/
│   └── Project SSOT documents
│
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── firebase.json
├── firestore.rules
├── firestore.indexes.json
├── pytest.ini
├── requirements.txt
├── requirements-prod.txt
└── README.md
🔥 Firestore Data Model

PriceBrain은 Firestore를 중심으로 다음과 같은 Collection을 사용합니다.

Product / Listing
products
└── {product_id}


listings
└── {listing_id}


listings/{listing_id}/price_history
└── {history_id}

가격 변경이 발생하면 기존 Listing의 가격을 단순 overwrite하는 것이 아니라
가격 이력을 별도의 subcollection에 append합니다.

Operational Data
crawl_jobs
crawl_logs
validation_logs
crawl_jobs

크롤링 작업의 lifecycle을 관리합니다.

RUNNING
   ↓
COMPLETED


또는


RUNNING
   ↓
FAILED

주요 필드:

job_id
mall_id
status
keyword
started_at
completed_at
error_message
crawl_logs

개별 crawl job에서 발생한 이벤트를 기록합니다.

지원하는 log level:

INFO
WARN
ERROR

주요 필드:

log_id
job_id
mall_id
level
message
created_at
validation_logs

Pipeline validation 결과 및 실패 정보를 기록합니다.

주요 필드:

log_id
source
status
details
created_at
💰 Price History

PriceBrain에서 중요한 기능 중 하나는
가격 변경 감지와 이력 보존입니다.

가격 저장 시 Listing의 현재 가격만 비교하지 않고,
price_history의 가장 최근 가격을 기준으로 변경 여부를 판단합니다.

첫 수집


100,000
   ↓
price_history


[100,000]

동일 가격 재수집:

100,000
   ↓
100,000


append ❌

가격 변경:

100,000
   ↓
110,000


append ✅


price_history


[100,000]
[110,000]

이를 통해 동일 가격의 중복 history 저장을 방지합니다.

또한 Firestore Emulator에서 발생할 수 있는

100000
100000.0

과 같은 numeric type 차이를 고려하여
KRW 가격 normalization을 적용했습니다.

🖥 GPU Master Reference

GPU 관련 데이터는 Pipeline에서 이름을 다시 추론하지 않고
Master Collection을 기준으로 resolve합니다.

gpu_vendors
      │
      ▼
gpu_families
      │
      ▼
gpu_models


board_partners

예:

NVIDIA
 └── GEFORCE_RTX
       └── rtx_5080
             └── ZOTAC

Pipeline은 이미 결정된 ID를 전달하고,
Repository가 Firestore Master를 조회합니다.

이를 통해 Repository가 상품명 등을 다시 parsing하여
vendor / family를 추론하는 문제를 방지합니다.

🔐 Security

Firestore Client SDK의 직접 write는 허용하지 않고,
Backend의 Firebase Admin SDK를 통한 write path를 사용합니다.

Firestore Rules는 다음과 같은 운영 Collection에 대해
client read/write를 제한합니다.

crawl_jobs
crawl_logs
validation_logs

GPU Master Catalog는 읽기를 허용하고
client write는 제한합니다.

🔑 API Authentication

Production 환경에서 내부 ingest endpoint가
외부에 그대로 노출되는 문제를 방지하기 위해
Bearer API Key 인증을 적용했습니다.

Endpoint:

POST /internal/ingest/listing

Header:

Authorization: Bearer <PRICEBRAIN_INGEST_API_KEY>

환경변수:

PRICEBRAIN_INGEST_API_KEY

인증 동작:

상황	HTTP
API Key 미설정	503
Authorization 없음	401
Bearer 형식 오류	401
잘못된 API Key	401
인증 성공 + 잘못된 Payload	422
인증 성공 + 정상 요청	200

API Key 비교에는 timing-safe comparison을 적용했습니다.

secrets.compare_digest()

/health endpoint는 인증 없이 접근할 수 있습니다.

❤️ Health Check
GET /health

Response:

{
  "status": "ok",
  "service": "pricebrain_app"
}

현재 /health는 애플리케이션의 liveness 확인을 목적으로 하며
Firestore connectivity check는 수행하지 않습니다.

🧪 Testing

PriceBrain은 Firebase Emulator를 활용하여
Production Firestore에 영향을 주지 않고
Repository와 Firestore 연동을 검증합니다.

현재 전체 테스트:

106 passed
1 warning

주요 테스트 영역:

Repository
      ↓
Pipeline
      ↓
Operational persistence
      ↓
Price history
      ↓
GPU master
      ↓
Crawl jobs
      ↓
Crawl logs
      ↓
Validation logs
      ↓
FastAPI
      ↓
Firestore Emulator
      ↓
Firestore Rules
🚦 Gate Progress

프로젝트 개발 과정은 Gate 단위로 검증했습니다.

Gate	내용	상태
C-1	Price History 변경 감지 / dedup	✅ PASS
C-2	Crawl Job / Validation Log persistence	✅ PASS
C-3	GPU Master / Reference Repository	✅ PASS
C-4	Crawl Logs persistence	✅ PASS
D	Production readiness	⚠️ CONDITIONAL READY
D+1-A	Ingest API Authentication	✅ PASS
D+1-B	Cloud Run Production Deploy	⏸ BLOCKED
🚀 Deployment
Local

개발 환경에서는 Firebase Emulator를 사용합니다.

$env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
$env:FIREBASE_PROJECT_ID="demo-pricebrain"

FastAPI 실행:

uvicorn pricebrain_app.main:app --reload
🐳 Docker

Production 실행을 위해 Dockerfile을 준비했습니다.

Python 3.12
     ↓
FastAPI
     ↓
Uvicorn
     ↓
0.0.0.0:${PORT}

Production용 dependency는 별도의

requirements-prod.txt

로 분리했습니다.

☁️ Google Cloud Run

Cloud Run 배포를 고려한 구조를 구성했습니다.

예정 구조:

GitHub
   ↓
Docker Image
   ↓
Artifact Registry
   ↓
Cloud Run
   ↓
FastAPI
   ↓
Firebase Admin SDK
   ↓
Production Firestore

Production 환경에서는 다음과 같은 Secret / Environment Variable을 사용합니다.

FIREBASE_PROJECT_ID
PRICEBRAIN_INGEST_API_KEY
GOOGLE_APPLICATION_CREDENTIALS

다음 환경변수는 Production에서 사용하지 않습니다.

FIRESTORE_EMULATOR_HOST
현재 배포 상태

Cloud Run 실제 Production 배포는 아직 완료되지 않았습니다.

현재는 Dockerfile, Production dependency,
환경변수 설계, API 인증 및 배포 구조까지 준비된 상태입니다.

실제 Cloud Run 배포에는 다음 환경이 필요합니다.

Google Cloud CLI
Docker
Google Cloud authentication
Production project
Artifact Registry
Secret Manager
Cloud Run configuration
📄 GitHub Pages

PriceBrain의 Backend 자체는 GitHub Pages에서 실행할 수 없습니다.

GitHub Pages는 정적 파일을 제공하는 용도이므로:

HTML
CSS
JavaScript

와 같은 정적 Frontend에는 적합하지만

FastAPI
Python
Firebase Admin SDK
Firestore write
Crawler
Pipeline

등의 Backend 실행에는 적합하지 않습니다.

따라서 향후 Frontend가 추가된다면:

GitHub Pages
      │
      │ HTTPS API
      ▼
Cloud Run
      │
      ▼
Firestore

형태로 구성할 수 있습니다.

📌 Current Deployment Strategy

현재 프로젝트에서는 Backend와 Database의 역할을 분리합니다.

                 GitHub
                   │
          Source Code / Docs
                   │
                   ▼
          ┌─────────────────┐
          │    Frontend     │
          │ GitHub Pages    │
          └────────┬────────┘
                   │
                   │ HTTPS
                   ▼
          ┌─────────────────┐
          │     FastAPI     │
          │   Cloud Run     │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │    Firestore    │
          │     Firebase    │
          └─────────────────┘
📚 SSOT Documentation

프로젝트의 설계 및 구현 기준은 docs/ 아래의
SSOT 문서를 기준으로 관리합니다.

주요 영역:

Architecture
Database Schema
Firestore Rules
Repository Design
Pipeline
Crawler
Testing
Deployment

코드 구현 시 SSOT와의 충돌 여부를 먼저 확인하고
필요한 경우 Gate를 통해 변경 범위를 관리합니다.

🧭 Development Principles

PriceBrain은 다음 원칙을 유지합니다.

1. 책임 분리
Crawler
→ Data collection


Pipeline
→ Validation / transformation


Runner / Service
→ Orchestration


Repository
→ Firestore persistence


FastAPI
→ HTTP interface
2. Pipeline의 Firestore 직접 접근 금지

Pipeline은 Firestore를 직접 다루지 않습니다.

Pipeline
    ↓
ValidatedProduct
    ↓
Runner / Service
    ↓
Repository
    ↓
Firestore
3. Repository의 책임

Repository는 Firestore persistence를 담당합니다.

예:

ListingRepository
PriceHistoryRepository
CrawlRepository
ValidationRepository
GpuRepository
ReferenceRepository
4. Production 데이터 보호

Local / Emulator 환경과 Production 환경을 명확하게 분리합니다.

Local
 ↓
Firestore Emulator


Production
 ↓
Production Firestore

Production 데이터에 영향을 줄 수 있는
seed / write 작업은 명시적인 Production 절차를 거칩니다.

⚠️ Known Issues / Future Improvements

현재 다음 항목은 향후 개선 대상으로 남아 있습니다.

Crawl Logs Index

현재 crawl_logs의 job별 조회를 위한
composite index는 SSOT에 정의되어 있지 않습니다.

운영 환경에서 다음과 같은 query가 필요해질 경우:

job_id
+
created_at

SSOT 문서 변경 후 index를 추가할 예정입니다.

Cloud Run ADC

현재 Firebase Admin 인증은
Service Account JSON 경로 방식을 기준으로 합니다.

향후에는 Cloud Run의
Application Default Credentials(ADC)를 활용하는 방식으로
개선할 수 있습니다.

Crawler Production Policy

Production crawler 운영을 위해서는 다음 정책이 추가로 필요합니다.

robots.txt
rate limiting
retry policy
crawl scheduling
crawl timeout
monitoring
🔮 Future Roadmap
Phase 1
├── Core Architecture              ✅
├── Firestore Repository           ✅
├── Validation Pipeline            ✅
├── Price History                  ✅
├── GPU Master                     ✅
├── Crawl Jobs                     ✅
├── Crawl Logs                     ✅
└── Validation Logs                ✅


Phase 2
├── Production Firestore
├── Cloud Run Deployment
├── Monitoring
├── Crawl Scheduler
└── Production Crawler Policy


Phase 3
├── Frontend
├── Dashboard
├── Price Analytics
└── Admin Interface
👨‍💻 Project Status

Current Status

Core Backend                    ✅
Firestore Architecture          ✅
Repository Layer                ✅
Validation Pipeline              ✅
Operational Persistence          ✅
GPU Master                       ✅
Price History                    ✅
FastAPI                          ✅
Ingest Authentication            ✅
Firestore Emulator Testing       ✅
Firestore Rules Testing          ✅
Docker Production Preparation    ✅
Cloud Run Deployment              ⏸
Production Firestore             ⏸
Frontend                          🔜
📜 License

This project is currently developed as a personal / educational project.

License policy may be added when the project is finalized.



### 👍 이 README의 핵심


이번 README는 일부러 **"Cloud Run에 배포 완료했다"라고 거짓말하지 않았습니다.**


현재 정확한 상태는:


> **PriceBrain Backend 개발 및 Production 배포 준비 완료 → 실제 Cloud Run 배포는 아직 미실행**


입니다.


그리고 GitHub에 올렸을 때도 상당히 괜찮습니다.


특히 면접관이 보면:


```text
단순히 FastAPI 하나 만든 프로젝트
          ↓
Firestore 설계
          ↓
Repository Pattern
          ↓
Pipeline / 책임 분리
          ↓
가격 이력 Dedup
          ↓
Operational Log
          ↓
GPU Master
          ↓
Emulator E2E
          ↓
Firestore Rules
          ↓
API Authentication
          ↓
Docker / Cloud Run 준비

라는 개발 과정이 한눈에 보이는 구조가 됩니다.