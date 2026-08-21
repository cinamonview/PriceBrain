============================================================
10. Firebase 구현 및 프로젝트 초기 설정
============================================================

- Project: PriceBrain
- Document: Deployment and Operations Guide
- Version: 1.1
- Status: Final
- 갱신일: 2026-08-20 (Phase 3 — Runtime 13 정합)
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md`
- Runtime SSOT: `docs/13_SERVICE_AND_RUNTIME_ARCHITECTURE.md`
- Repository 구현: `docs/09_FIREBASE_IMPLEMENTATION.md`
- 운영·비용 상세: `docs/12_Deployment_and_Operation_Plan.md` (중복 시 12 우선)

문서 목적
------------------------------------------------------------

본 문서는 PriceBrain 설계 문서(04·**05**·09·**13** 등)를 바탕으로
Firebase 개발 환경·Emulator·Frontend SDK 초기 설정을 정의한다.

**Runtime read/write SSOT는 13.** 본 문서는 13 §4와 **동일한 방향**을 따른다.

- **Catalog read:** Next.js → Firestore **Client SDK** (Security Rules)
- **Catalog write / crawl / price_history:** **FastAPI** → **Admin SDK** (09 Repository)
- **Python 크롤러(07→08→09)는 유지** — Firebase만으로 대체하지 않음

Firebase는 다음 기능을 중심으로 사용한다.

- Firebase Authentication
- Cloud Firestore
- Firebase Storage
- Firebase Hosting
- Firebase Security Rules
- Firebase SDK


------------------------------------------------------------
10.1 Firebase 도입 목적
------------------------------------------------------------

본 프로젝트에서는 별도의 백엔드 서버를 직접 구축하고 운영하는
부담을 줄이고, 인증·데이터 저장·파일 저장·배포 등의 기능을
Firebase를 통해 통합 관리한다.

기존 구조에서 직접 관리해야 했던 다음 요소들을 Firebase 서비스로
대체한다.

기존 방식
    ↓
별도 Backend Server
별도 Database
별도 Authentication
별도 File Storage
별도 Server Deployment

변경 방식 (PriceBrain MVP)
    ↓
Firebase Hosting + Auth + Firestore + Storage + Rules
    +
FastAPI (로컬 MVP) / Cloud Run (운영 선택) + Admin SDK
    ↓
07 Crawler → 08 Pipeline → 09 Repository → Firestore


------------------------------------------------------------
10.2 Firebase 프로젝트 생성
------------------------------------------------------------

Firebase Console에서 프로젝트를 생성한다.

프로젝트 생성 시 프로젝트 이름은 실제 서비스 이름과 동일하거나
개발 프로젝트임을 구분할 수 있는 이름을 사용한다.

예시:

project-name
project-name-dev
project-name-production


Firebase 프로젝트 생성 후 다음 기능을 활성화한다.

[필수]

1. Authentication
2. Cloud Firestore

[필요 시 사용]

3. Storage
4. Hosting


------------------------------------------------------------
10.3 Firebase Authentication 설정
------------------------------------------------------------

사용자 인증은 Firebase Authentication을 사용한다.

기본적으로 다음 인증 방식을 고려한다.

- Email / Password
- Google 로그인
- 필요 시 추가 OAuth 로그인

초기 개발 단계에서는 Email / Password 인증을 우선 구현한다.

인증 흐름은 다음과 같다.

사용자
  ↓
회원가입
  ↓
Firebase Authentication
  ↓
계정 생성
  ↓
로그인
  ↓
Firebase 인증 토큰 발급
  ↓
서비스 이용


로그인 상태는 Firebase Authentication의 인증 상태를 기준으로
판단한다.

클라이언트에서는 현재 로그인한 사용자의 UID를 확인하여
사용자별 데이터를 구분한다.


------------------------------------------------------------
10.4 사용자 데이터 구조
------------------------------------------------------------

Firebase Authentication에는 기본적인 인증 정보가 저장되고,
서비스에서 필요한 추가 사용자 정보는 Firestore에 저장한다.

예시 구조:

users
 └── {uid}
      ├── email
      ├── displayName
      ├── photoURL
      ├── role
      ├── createdAt
      └── updatedAt


각 사용자는 Firebase Authentication에서 발급되는 UID를
고유 식별자로 사용한다.

예:

users
 ├── abc123
 ├── def456
 └── ghi789


UID를 기준으로 사용자 데이터를 연결한다.


------------------------------------------------------------
10.5 Cloud Firestore 설정
------------------------------------------------------------

서비스에서 사용하는 catalog·가격·크롤 데이터는 **Cloud Firestore**에 저장한다.

Firestore는 Collection과 Document 구조를 사용한다.

**Collection·Field·Rules·Index SSOT:** `docs/05_FIREBASE_DATA_STRUCTURE.md`

MVP catalog 예 (상세는 05 §1):

```text
products          ← Canonical Product (canonical_products 사용 안 함)
listings
listings/{id}/price_history
gpu_vendors, gpu_models, malls, sellers, …
crawl_jobs, crawl_logs, validation_logs
users/{uid}       ← Phase 2+
```

본 문서에 Field 표를 **복제하지 않는다.**


------------------------------------------------------------
10.5.1 Runtime read/write (13 SSOT — 09와 동일)
------------------------------------------------------------

| 경로 | 구현 | SDK |
|------|------|-----|
| Catalog **read** | Next.js `services/*` | Firestore **Client SDK** |
| Catalog **write** | FastAPI → 09 Repository | **Admin SDK** |
| price_history append | FastAPI / 09 | **Admin SDK** |
| crawl_* | FastAPI / 09 | **Admin SDK** |
| Auth | Next.js | Firebase Auth SDK |

Frontend Client SDK로 catalog **write 금지** (Rules). Rules 원문: **05 §6**.


------------------------------------------------------------
10.6 Firestore 데이터 설계 원칙
------------------------------------------------------------

Firestore에서는 관계형 데이터베이스와 동일한 방식으로 테이블을
설계하지 않는다.

따라서 기존 SQL 데이터베이스의 테이블 구조를 그대로 옮기기보다는
서비스에서 실제로 데이터를 조회하는 방법을 먼저 고려한다.

주요 원칙은 다음과 같다.

1. 자주 함께 조회되는 데이터는 가까운 구조로 배치한다.

2. 사용자별 데이터는 사용자 UID를 기준으로 관리한다.

3. 복잡한 JOIN을 최대한 피한다.

4. 필요한 경우 데이터를 중복 저장하는 것을 허용한다.

5. 검색 및 정렬에 필요한 필드는 사전에 고려한다.

6. Firestore Query의 제한사항을 고려하여 Collection을 설계한다 — Index: **05 §7**.


------------------------------------------------------------
10.6.1 Schema 변경

Collection·Rules·Index 변경 시 **05** 먼저 갱신 → `firestore.rules` / `firestore.indexes.json` → **09**·**11** 동기화.


------------------------------------------------------------
10.7 Firestore Timestamp 사용
------------------------------------------------------------

생성일과 수정일 등의 날짜 정보는 문자열보다는 Firebase
Timestamp를 사용하는 것을 기본으로 한다.

예:

createdAt
updatedAt

데이터 저장 시 서버 시간을 사용하는 것을 권장한다.

예시 개념:

createdAt = serverTimestamp()
updatedAt = serverTimestamp()


이를 통해 클라이언트의 잘못된 시간 설정으로 인해 발생하는
시간 데이터 오류를 줄인다.


------------------------------------------------------------
10.8 Firebase Storage 설정
------------------------------------------------------------

사용자가 업로드하는 이미지 또는 파일이 필요한 경우
Firebase Storage를 사용한다.

예시:

Storage
│
├── users/
│   └── {uid}/
│
├── images/
│
└── uploads/


사용자별 파일은 가능하면 UID를 기준으로 구분한다.

예:

users/{uid}/profile/profile.jpg

users/{uid}/images/image001.jpg


Storage에는 실제 파일을 저장하고 Firestore에는 필요한 경우
파일의 URL 또는 Storage 경로를 저장한다.


------------------------------------------------------------
10.9 Firebase Security Rules
------------------------------------------------------------

Firebase Security Rules는 **05 §6** SSOT. 본 절은 원칙만 기술한다.

`firestore.rules` 파일 내용은 **05와 1:1** 유지. 테스트: **11 §9**.

개발 초기 단계에서 모든 사용자가 모든 데이터를 읽고 쓸 수 있도록
설정하는 것은 금지한다.

기본적인 원칙은 다음과 같다.

1. 로그인하지 않은 사용자의 쓰기 작업을 제한한다.

2. 사용자는 자신의 데이터를 수정할 수 있도록 한다.

3. 다른 사용자의 개인정보에 접근하지 못하도록 한다.

4. 관리자 기능은 별도의 권한을 확인한다.

5. Storage 역시 사용자별 접근 권한을 제한한다.


예시 개념:

사용자 A
    ↓
자신의 데이터
    → 읽기/쓰기 허용

사용자 A
    ↓
사용자 B의 개인정보
    → 접근 거부


------------------------------------------------------------
10.10 관리자 권한
------------------------------------------------------------

서비스에 관리자 기능이 필요한 경우 일반 사용자와 관리자 권한을
분리한다.

예시:

role
 ├── user
 └── admin


관리자 여부에 따라 다음 기능의 접근을 제한할 수 있다.

- 사용자 관리
- 게시물 관리
- 신고 관리
- 데이터 수정
- 서비스 통계
- 관리자 전용 페이지


관리자 권한은 단순히 프론트엔드에서 버튼을 숨기는 방식으로
처리해서는 안 된다.

실제 데이터 접근 단계에서도 Security Rules 등을 통해 권한을
검증해야 한다.


------------------------------------------------------------
10.11 Firebase SDK 설치
------------------------------------------------------------

프론트엔드 프로젝트에서 Firebase SDK를 설치한다.

예시:

npm install firebase


프로젝트 내부에 Firebase 초기화 파일을 별도로 구성한다.

예:

src/
├── firebase/
│   ├── config.js
│   ├── auth.js
│   ├── firestore.js
│   └── storage.js
│
├── components/
├── pages/
├── services/
└── utils/


Firebase 관련 코드를 여러 페이지에 직접 작성하지 않고
Firebase 관련 기능을 별도의 모듈로 분리한다.


------------------------------------------------------------
10.12 Firebase 초기화
------------------------------------------------------------

Firebase 설정 정보는 프로젝트의 환경변수를 통해 관리한다.

예:

VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_PROJECT_ID
VITE_FIREBASE_STORAGE_BUCKET
VITE_FIREBASE_MESSAGING_SENDER_ID
VITE_FIREBASE_APP_ID


실제 API Key 등의 설정값은 소스 코드에 직접 하드코딩하지 않는다.

환경변수 파일을 사용하여 개발 환경과 배포 환경을 분리한다.


------------------------------------------------------------
10.13 환경변수 관리
------------------------------------------------------------

개발 환경에서는 .env 파일을 사용할 수 있다.

예:

.env

VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...


환경변수 파일에 포함되는 민감한 정보가 있는 경우
GitHub 등의 공개 저장소에 그대로 업로드하지 않도록 주의한다.

.gitignore에 다음과 같은 파일을 등록한다.

.env
.env.local
.env.*.local


------------------------------------------------------------
10.14 Firebase 설정 모듈
------------------------------------------------------------

Firebase 초기화 코드는 하나의 파일에서 관리하는 것을 기본으로 한다.

예:

src/firebase/config.js

역할:

1. Firebase App 초기화
2. Authentication 초기화
3. Firestore 초기화
4. Storage 초기화


다른 파일에서는 초기화 코드를 다시 작성하지 않고
Firebase 모듈에서 생성된 객체를 가져와 사용한다.


------------------------------------------------------------
10.15 서비스 계층 구성
------------------------------------------------------------

Firestore와 직접 통신하는 코드를 UI 컴포넌트에
직접 작성하지 않는 것을 권장한다.

예:

src/
├── components/
├── pages/
├── services/
│   ├── authService.js
│   ├── userService.js
│   └── dataService.js
│
├── firebase/
└── utils/


예를 들어 회원가입 기능은 다음과 같은 흐름으로 구성한다.

회원가입 페이지
    ↓
authService
    ↓
Firebase Authentication
    ↓
사용자 계정 생성
    ↓
Firestore users 생성
    ↓
완료


이러한 구조를 사용하면 나중에 Firebase 기능을 수정하거나
교체할 때 UI 코드에 미치는 영향을 줄일 수 있다.


------------------------------------------------------------
10.16 인증 상태 관리
------------------------------------------------------------

애플리케이션에서는 사용자의 로그인 상태를 지속적으로 확인해야 한다.

Firebase Authentication의 인증 상태 변경 이벤트를 사용하여
현재 사용자의 로그인 상태를 관리한다.

기본 상태:

- 로그인하지 않음
- 로그인 중
- 로그인 완료
- 로그아웃


로그인된 사용자의 UID를 기준으로 사용자별 데이터를 조회한다.


------------------------------------------------------------
10.17 라우팅 및 접근 제한
------------------------------------------------------------

로그인이 필요한 페이지와 누구나 접근 가능한 페이지를 구분한다.

예:

공개 페이지

/
├── 로그인
├── 회원가입
├── 서비스 소개
└── 검색


로그인 필요 페이지

/dashboard
/profile
/my-data
/settings


관리자 전용 페이지

/admin
/admin/users
/admin/reports


로그인이 필요한 페이지에 비로그인 사용자가 접근할 경우
로그인 페이지로 이동하도록 처리한다.


------------------------------------------------------------
10.18 Firebase Hosting
------------------------------------------------------------

서비스 배포가 필요한 경우 Firebase Hosting을 사용할 수 있다.

개발 완료 후 다음과 같은 배포 흐름을 구성한다.

로컬 개발
    ↓
Git
    ↓
GitHub
    ↓
Build
    ↓
Firebase Hosting
    ↓
서비스 공개


배포 전 다음 사항을 확인한다.

- Production 환경변수
- Firebase Security Rules
- Firestore 데이터
- Authentication 설정
- Storage Rules
- 오류 로그
- 모바일 화면
- 주요 기능


------------------------------------------------------------
10.19 개발 환경과 운영 환경 분리
------------------------------------------------------------

가능하다면 개발 환경과 실제 운영 환경을 분리한다.

예:

Firebase Development Project
        ↓
개발 및 테스트

Firebase Production Project
        ↓
실제 서비스


이를 통해 개발 과정에서 실제 서비스 데이터가 손상되는
문제를 방지한다.


------------------------------------------------------------
10.20 GitHub 연동
------------------------------------------------------------

소스 코드는 Git을 사용하여 버전 관리한다.

기본 구조:

Local
  ↓
Git
  ↓
GitHub
  ↓
Firebase Deployment


GitHub Repository에는 다음과 같은 파일이 포함될 수 있다.

src/
public/
package.json
package-lock.json
README.md
.gitignore


다음과 같은 파일은 공개 Repository에 포함하지 않는다.

.env
서비스 계정 키
개인 인증 정보
비밀번호
기타 민감한 정보


------------------------------------------------------------
10.21 초기 개발 체크리스트
------------------------------------------------------------

Firebase 프로젝트 생성
[ ] Firebase 프로젝트 생성

Authentication
[ ] Authentication 활성화
[ ] Email/Password 활성화
[ ] 필요한 OAuth 로그인 설정

Firestore
[ ] Firestore 생성
[ ] **05** Schema·Rules·Index 확정
[ ] `firestore.rules` / `firestore.indexes.json` 배포
[ ] Emulator에서 **11 §9** Rules 테스트

Storage
[ ] Storage 활성화
[ ] 파일 저장 구조 결정
[ ] Storage Security Rules 설정

Security
[ ] Firestore Security Rules 작성
[ ] Storage Security Rules 작성
[ ] 관리자 권한 정책 작성

Frontend
[ ] Firebase SDK 설치
[ ] Firebase 초기화
[ ] 환경변수 설정
[ ] Firebase 서비스 모듈 분리

Version Control
[ ] Git 초기화
[ ] GitHub Repository 생성
[ ] .gitignore 작성
[ ] 환경변수 파일 제외

Deployment
[ ] Firebase Hosting 설정
[ ] Build 테스트
[ ] 배포 테스트


------------------------------------------------------------
10.22 개발 순서
------------------------------------------------------------

실제 개발은 다음 순서로 진행한다.

STEP 1
Firebase 프로젝트 생성

        ↓

STEP 2
Firebase Authentication 설정

        ↓

STEP 3
Firestore 생성 + **05** Schema / Rules / Index 적용

        ↓

STEP 4
Firebase Emulator Suite (Gate C)

        ↓

STEP 5
Firebase SDK 설치 (Frontend Client SDK)

        ↓

STEP 6
Firebase 초기화 (`src/firebase/`)

        ↓

STEP 7
Catalog read — Client SDK + `services/*` (**13**)

        ↓

STEP 8
FastAPI + Admin SDK + 09 Repository (catalog write, crawl)

        ↓

STEP 9
Authentication (Phase 2+)

        ↓

STEP 10
Storage (선택)

        ↓

STEP 11
Security Rules (**05 §6**) + **11** 테스트

        ↓

STEP 12
전체 기능 테스트

        ↓

STEP 13
Firebase Hosting 배포


------------------------------------------------------------
10.23 다음 단계
------------------------------------------------------------

10번 문서까지 완료하면 Firebase를 사용한 실제 개발 환경을
구성할 수 있는 기본적인 설계가 완료된다.

다음 문서부터는 실제 서비스 기능을 하나씩 구현한다.

다음 단계에서는 우선 프로젝트의 전체 개발 환경과 폴더 구조를
실제로 생성하고 Firebase SDK를 연결한다.

이후 다음 기능을 순차적으로 구현한다.

1. 프로젝트 초기화
2. Firebase 연결
3. Authentication
4. 사용자 관리
5. Firestore 데이터 처리
6. 핵심 서비스 기능
7. Storage
8. 관리자 기능
9. Security Rules
10. 테스트
11. 배포


------------------------------------------------------------
10.24 중요 원칙
------------------------------------------------------------

본 프로젝트는 Firebase Hosting·Auth·Firestore·Rules와
**FastAPI + Admin SDK(09)** 를 함께 사용한다.

Frontend:

UI → Service Layer → Firebase Client SDK → Firestore (catalog **read**)

Backend (crawl / write):

07→08→09 → FastAPI → Admin SDK → Firestore (**write**)

Runtime SSOT: **13**. Schema SSOT: **05**.


============================================================
문서 끝
============================================================