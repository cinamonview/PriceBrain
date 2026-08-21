# 12. 배포 및 운영 계획서

**프로젝트명:** PriceBrain (프라이스브레인)  
**문서 번호:** 12  
**문서명:** 배포 및 운영 계획서  
**Version:** 1.1  
**갱신일:** 2026-08-20 (Phase 3 — 10·13 정합)  
**Schema SSOT:** `docs/05_FIREBASE_DATA_STRUCTURE.md`  
**Runtime SSOT:** `docs/13_SERVICE_AND_RUNTIME_ARCHITECTURE.md`  
**초기 Firebase 설정:** `docs/10_Deployment_and_Operations_Guide.md` (본 문서와 중복 시 10 우선)  
**작성 목적:** 개발 완료 후 실제 서비스 환경에 배포하고 안정적으로 운영하기 위한 기준 및 절차 정의

---

# 1. 문서 개요

## 1.1 목적

본 문서는 프로젝트의 개발이 완료된 이후 실제 사용자에게 서비스를 제공하기 위한 배포 및 운영 방법을 정의한다.

본 문서에서는 다음 항목을 다룬다.

- 웹 서비스 배포 구조
- Firebase 서비스 구성
- 환경 설정
- 데이터 및 보안 관리
- 배포 절차
- 운영 및 유지보수
- 오류 및 장애 대응
- 성능 관리
- 비용 관리
- 향후 확장 계획

본 프로젝트는 Firebase를 핵심 백엔드 인프라로 활용하는 것을 기준으로 한다.

---

# 2. 전체 시스템 배포 구조

## 2.1 기본 구조

프로젝트의 기본적인 서비스 구조는 다음과 같다.

```text
                    사용자
                      │
                      ▼
               ┌─────────────┐
               │ Next.js     │
               │ Firebase    │
               │ Hosting     │
               └──────┬──────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
     Authentication  Firestore   Storage
     (Phase 2+)     (catalog)   (선택)
          │           │
          │     Client SDK read (catalog)
          │           │
          └───────────┼───────────┐
                      │           │
                      ▼           ▼
               FastAPI (local MVP  AI API
                or Cloud Run)     (Phase 4+)
                      │
                      ▼
               Admin SDK write
               (09 Repository)
                      │
                      ▼
               listings · products
               · price_history · crawl_*
```

Runtime read/write: **13 §4** (= **09 §2**, **10 §10.5.1**)

## 2.2 주요 구성 요소

| 구성 요소 | 역할 |
|-----------|------|
| Firebase Hosting | Next.js 배포 |
| Firebase Authentication | 사용자 인증 (Phase 2+) |
| Cloud Firestore | catalog·가격·이력 (**05** Schema) |
| Firebase Storage | 이미지·파일 (선택) |
| **FastAPI** | catalog write, crawl ingest (**09**) |
| **Cloud Run** | FastAPI 운영 배포 (선택) |
| AI API | AI 분석 (Phase 4+) |
| GitHub | 소스·CI/CD |

## 3. Firebase 구성
3.1 Firebase Hosting

Firebase Hosting은 프로젝트의 웹 페이지를 실제 인터넷 환경에 배포하기 위해 사용한다.

주요 역할은 다음과 같다.

HTML 제공
CSS 제공
JavaScript 제공
이미지 및 정적 리소스 제공
HTTPS 지원
사용자 접속 처리

개발 환경에서 정상적으로 동작하는 것을 확인한 후 Firebase Hosting을 통해 운영 환경에 배포한다.

3.2 Firebase Authentication

사용자 인증이 필요한 경우 Firebase Authentication을 사용한다.

지원 가능한 인증 방식은 프로젝트 요구사항에 따라 선택한다.

예:

이메일 / 비밀번호
Google 로그인
기타 OAuth 인증

인증 시스템을 사용하는 경우 사용자에게 필요한 최소한의 정보만 수집한다.

### 3.3 Cloud Firestore

Cloud Firestore는 PriceBrain **유일 공식 Database**이다.

**Collection·Field·Rules·Index SSOT:** `docs/05_FIREBASE_DATA_STRUCTURE.md`

MVP catalog (개념):

```text
products                    ← Canonical Product
listings
listings/{id}/price_history
gpu_vendors · gpu_models · malls · sellers · …
crawl_jobs · crawl_logs · validation_logs
```

`canonical_products` Collection **사용 안 함**.

Phase 2+ user data: `users/{uid}`, `users/{uid}/favorites`

초기 Firebase·Emulator 설정: **10** 참조.

3.4 Firebase Storage

이미지 및 파일 업로드 기능이 필요한 경우 Firebase Storage를 사용한다.

예:

storage
 ├── users/
 │    └── userId/
 │         └── profile/
 │
 └── uploads/
      └── userId/
           └── files/

파일 접근 권한은 사용자 인증 상태 및 파일 소유권에 따라 제한한다.

### 3.5 FastAPI / Cloud Run (Backend write)

catalog write·크롤 결과·price_history append는 **FastAPI + Admin SDK** (**09**, **13**).

| 환경 | Backend |
|------|---------|
| 로컬 MVP | FastAPI + Emulator / dev Firestore |
| 운영 (선택) | Cloud Run + FastAPI |

Cloud Functions는 이벤트·경량 트리거 **선택** 사항. 크롤·ingest SSOT는 FastAPI.

API Key·service account는 클라이언트에 포함하지 않는다 (**project.mdc §13**).

4. 환경 구성
4.1 개발 환경

개발 단계에서는 로컬 환경을 사용한다.

예:

개발 PC
 ├── VS Code
 ├── Node.js
 ├── Firebase CLI
 └── 프로젝트 소스 코드

개발 중에는 Firebase Emulator Suite를 활용하여 실제 서비스에 영향을 주지 않고 기능을 테스트하는 것을 권장한다.

4.2 테스트 환경

주요 기능을 개발한 이후 실제 배포 전에 테스트 환경에서 다음 항목을 확인한다.

회원가입
로그인
로그아웃
데이터 저장
데이터 조회
데이터 수정
데이터 삭제
파일 업로드
권한 검사
오류 처리
모바일 화면
다양한 브라우저
4.3 운영 환경

운영 환경에서는 실제 사용자가 접근하는 Firebase 프로젝트를 사용한다.

운영 환경에서는 다음 사항을 반드시 확인한다.

Firebase Security Rules
Authentication 설정
Firestore 권한
Storage 권한
API Key 관리
도메인 설정
오류 모니터링
사용량 및 비용
5. 환경변수 및 비밀정보 관리
5.1 기본 원칙

다음과 같은 민감한 정보는 소스 코드에 직접 작성하지 않는다.

API Key
Secret Key
Access Token
Database Credential
OAuth Secret

예를 들어 다음과 같은 방식은 사용하지 않는다.

const API_KEY = "실제_API_KEY";

대신 환경변수 또는 Firebase에서 제공하는 안전한 설정 방식을 사용한다.

5.2 GitHub 관리

다음 파일이나 정보는 GitHub에 공개하지 않는다.

.env
.env.local
serviceAccountKey.json
private key
secret key
access token

.gitignore에 민감한 파일을 등록한다.

예:

.env
.env.local
*.key
serviceAccountKey.json
## 6. Firebase Security Rules

Rules **전문 SSOT:** `docs/05_FIREBASE_DATA_STRUCTURE.md` §6

| 데이터 | Client read | Client write |
|--------|-------------|--------------|
| catalog (`products`, `listings`, …) | allow | **deny** |
| `price_history` | allow | **deny** (Admin append) |
| `crawl_*` | deny | deny |
| `users/{uid}` | owner | owner (Phase 2+) |

테스트 시나리오: **11 §9**. Emulator: **10**.

### 6.1 기본 원칙

Firebase Security Rules는 프로젝트의 데이터 접근 권한을 제어하는 핵심 보안 요소이다.

개발 초기에는 편의를 위해 지나치게 넓은 권한을 설정할 수 있지만 운영 환경에서는 반드시 최소 권한 원칙을 적용한다.

6.2 사용자 데이터 접근

사용자 개인 데이터는 해당 사용자만 접근할 수 있도록 설정한다.

개념적인 구조는 다음과 같다.

사용자 A
   │
   ├── 자신의 데이터 → 접근 가능
   │
   └── 사용자 B 데이터 → 접근 불가
6.3 관리자 권한

관리자 기능이 존재하는 경우 일반 사용자와 관리자의 권한을 분리한다.

예:

일반 사용자
 ├── 자신의 정보 조회
 ├── 자신의 정보 수정
 └── 일반 서비스 이용


관리자
 ├── 사용자 관리
 ├── 콘텐츠 관리
 ├── 데이터 관리
 └── 시스템 관리

관리자 권한은 일반 사용자에게 부여하지 않는다.

7. 배포 절차
7.1 배포 전 확인

배포 전에 다음 항목을 확인한다.

□ 코드 오류 확인
□ 콘솔 오류 확인
□ 로그인 기능 확인
□ 데이터 저장 확인
□ 데이터 조회 확인
□ 권한 확인
□ 모바일 화면 확인
□ 이미지 및 파일 업로드 확인
□ API 연결 확인
□ Security Rules 확인
□ 환경변수 확인
7.2 GitHub Commit

기능 개발이 완료되면 변경 사항을 GitHub에 저장한다.

예:

git add .
git commit -m "feat: 서비스 기능 업데이트"
git push

커밋 메시지는 기능별로 명확하게 작성한다.

예:

feat: 로그인 기능 추가
feat: 게시글 작성 기능 추가
fix: 모바일 화면 오류 수정
fix: firestore 권한 오류 수정
refactor: 사용자 데이터 처리 구조 개선
8. Firebase 배포

Firebase CLI가 설치되어 있고 프로젝트가 연결되어 있다는 것을 전제로 한다.

기본적인 배포 과정은 다음과 같다.

firebase login

프로젝트 초기 설정:

firebase init

필요한 Firebase 서비스를 선택한다.

예:

Hosting
Firestore
Functions
Storage

배포:

firebase deploy

특정 서비스만 배포할 경우 프로젝트 설정에 따라 필요한 서비스만 선택하여 배포할 수 있다.

예:

firebase deploy --only hosting
9. 도메인 연결

운영 서비스의 신뢰성과 접근성을 높이기 위해 필요할 경우 사용자 정의 도메인을 연결한다.

예:

https://www.example.com

도메인 연결 후 다음 항목을 확인한다.

□ DNS 설정
□ HTTPS 적용
□ 인증서 정상 발급
□ www / non-www 처리
□ 모바일 접속
□ 새로고침 정상 동작
10. 운영 및 유지보수
10.1 정기 점검

운영 서비스는 정기적으로 상태를 점검한다.

기본 점검 항목
□ 사이트 접속 여부
□ 로그인 정상 여부
□ 데이터 조회 정상 여부
□ 데이터 저장 정상 여부
□ 파일 업로드 정상 여부
□ API 정상 여부
□ Firebase 오류 로그
□ 사용량
□ 비용
10.2 오류 모니터링

오류가 발생하면 다음 정보를 확인한다.

발생 시간
오류 종류
사용자 행동
발생 페이지
브라우저
오류 메시지
서버 로그
Firebase 로그

오류를 재현할 수 있도록 가능한 한 구체적인 정보를 기록한다.

11. 데이터 백업 및 복구

중요한 데이터는 정기적인 백업을 고려한다.

특히 다음 데이터는 중요하게 관리한다.

사용자 데이터
서비스 핵심 데이터
관리자 데이터
업로드 파일
중요 설정 정보

데이터 손실에 대비하여 복구 방법을 사전에 정의한다.

12. 성능 관리
12.1 웹 성능

웹 페이지의 불필요한 리소스 사용을 줄인다.

예:

이미지 용량 최적화
JavaScript 최소화
CSS 정리
사용하지 않는 라이브러리 제거
Lazy Loading 적용
캐싱 활용
12.2 Firestore 사용량

Firestore는 데이터 조회 횟수에 따라 사용량과 비용이 발생할 수 있으므로 불필요한 반복 조회를 줄인다.

예:

잘못된 방식
→ 페이지가 열릴 때마다 동일한 데이터를 반복 조회


개선 방식
→ 필요한 경우에만 조회
→ 캐시 활용
→ 필요한 데이터만 조회
12.3 이미지 및 파일

대용량 파일을 그대로 업로드하지 않도록 한다.

필요한 경우:

이미지 리사이징
이미지 압축
파일 크기 제한
파일 형식 제한

등을 적용한다.

13. 비용 관리

Firebase 및 외부 API는 사용량에 따라 비용이 발생할 수 있으므로 운영 단계에서는 비용을 지속적으로 확인한다.

주요 확인 항목:

Firestore 읽기 / 쓰기
Storage 사용량
Hosting 트래픽
Cloud Run / FastAPI 실행량
외부 API 사용량
AI API 사용량

특히 AI API를 사용하는 기능의 경우 사용자 요청이 반복적으로 발생하지 않도록 적절한 제한 및 캐싱 전략을 고려한다.

14. 보안 관리
14.1 사용자 인증

사용자 인증이 필요한 기능은 반드시 인증 상태를 확인한다.

로그인 사용자
      │
      ▼
인증 상태 확인
      │
 ┌────┴────┐
 ▼         ▼
인증됨     인증 안 됨
 │         │
 ▼         ▼
서비스 이용  로그인 페이지
14.2 입력값 검증

사용자가 입력하는 데이터는 항상 검증한다.

예:

문자열 길이
숫자 범위
파일 형식
파일 크기
필수 입력값
잘못된 문자

클라이언트 검증만으로 충분하다고 판단하지 않고 서버 측에서도 필요한 검증을 수행한다.

14.3 XSS 및 악성 입력 방지

사용자가 입력한 HTML 또는 Script가 그대로 실행되지 않도록 한다.

특히 게시글, 댓글, 프로필 정보 등 사용자 입력을 화면에 출력하는 기능은 주의한다.

15. 장애 대응
15.1 장애 발생 시 기본 절차
장애 발생
   │
   ▼
문제 확인
   │
   ▼
영향 범위 확인
   │
   ▼
로그 확인
   │
   ▼
원인 분석
   │
   ▼
수정
   │
   ▼
테스트
   │
   ▼
재배포
   │
   ▼
정상 여부 확인
15.2 긴급 장애

서비스 전체가 이용되지 않는 심각한 장애의 경우 다음 순서로 대응한다.

장애 원인 파악
영향 범위 확인
최근 배포 내용 확인
문제가 발생한 코드 또는 설정 확인
필요한 경우 이전 버전으로 복구
문제 수정
테스트
재배포
정상 여부 확인
16. 버전 관리

GitHub를 이용하여 프로젝트의 소스 코드를 관리한다.

브랜치 전략은 프로젝트 규모에 따라 조정할 수 있다.

기본적으로 다음과 같은 구조를 사용할 수 있다.

main
 │
 ├── develop
 │
 ├── feature/login
 │
 ├── feature/user-profile
 │
 └── fix/firestore-rule

운영 배포는 검증된 코드만 main 브랜치에 반영하도록 한다.

17. 배포 전 최종 체크리스트
기능
□ 메인 페이지 정상 작동
□ 회원가입 정상 작동
□ 로그인 정상 작동
□ 로그아웃 정상 작동
□ 주요 서비스 기능 정상 작동
□ 데이터 저장 정상 작동
□ 데이터 조회 정상 작동
□ 데이터 수정 정상 작동
□ 데이터 삭제 정상 작동
Firebase
□ Authentication 설정 완료
□ Firestore 설정 완료
□ Storage 설정 완료
□ Security Rules 적용
□ FastAPI / Cloud Run (Backend write) 설정
□ Firebase Hosting 설정
보안
□ API Key 노출 여부 확인
□ Secret Key 노출 여부 확인
□ .env 파일 GitHub 제외
□ Firestore Rules 확인
□ Storage Rules 확인
□ 관리자 권한 확인
□ 사용자 권한 확인
UI / UX
□ PC 화면 확인
□ 태블릿 화면 확인
□ 모바일 화면 확인
□ 주요 브라우저 확인
□ 오류 메시지 확인
□ 로딩 상태 확인
□ 빈 데이터 상태 확인
운영
□ 로그 확인
□ 비용 확인
□ 사용량 확인
□ 백업 정책 확인
□ 장애 대응 방법 확인
18. 프로젝트 완료 기준

프로젝트는 다음 조건을 만족하는 경우 1차 개발 완료로 판단한다.

필수 조건
1. 핵심 기능 구현 완료
2. Firebase 연동 완료
3. 데이터 저장 및 조회 정상
4. 사용자 인증 정상
5. Security Rules 적용
6. 주요 오류 수정 완료
7. 운영 환경 배포 완료
8. 모바일 환경 확인 완료
9. 기본적인 오류 대응 체계 확보
19. 향후 확장 계획

프로젝트가 안정적으로 운영된 이후 다음 기능을 추가할 수 있다.

19.1 관리자 페이지
사용자 관리
데이터 관리
콘텐츠 관리
통계 확인
서비스 상태 확인
19.2 AI 기능 확대

AI를 활용하여 다음과 같은 기능을 추가할 수 있다.

AI 검색
AI 추천
AI 챗봇
AI 데이터 분석
AI 자동 분류
AI 콘텐츠 생성

AI 기능을 추가할 경우 API 비용과 응답 속도, 개인정보 보호 문제를 함께 고려한다.

19.3 데이터 분석

서비스 이용 데이터를 기반으로 다음과 같은 분석 기능을 추가할 수 있다.

사용자 수
일간 방문자
페이지 조회
기능별 사용량
검색 데이터
사용자 행동 분석
19.4 모바일 서비스

웹 서비스가 안정화된 이후 필요성에 따라 모바일 앱으로 확장할 수 있다.

예:

Web
 │
 ├── PC
 ├── Tablet
 └── Mobile
       │
       ▼
   Mobile App
20. 장기적인 운영 방향

프로젝트는 단순히 웹사이트를 한 번 배포하는 것으로 종료하지 않는다.

다음과 같은 지속적인 개선 과정을 목표로 한다.

개발
 ↓
테스트
 ↓
배포
 ↓
사용자 이용
 ↓
데이터 수집
 ↓
문제 분석
 ↓
기능 개선
 ↓
재배포
 ↓
사용자 이용
 ↓
반복

이를 통해 서비스의 안정성과 사용자 경험을 지속적으로 개선한다.

## 21. PriceBrain 문서 구조

```text
docs/
├── 001-flowchart.md
├── 01_PRD_PriceBrain.md
├── 02_GPU_Data_Model.md
├── 03_DATA_SOURCE_RESEARCH.md
├── 04_DATABASE_DESIGN.md
├── 05_FIREBASE_DATA_STRUCTURE.md    ← Schema SSOT
├── 06_DATA_SOURCE_AND_CRAWLING_ARCHITECTURE.md
├── 06-1_DATA_SOURCE_VALIDATION.md
├── 07_CRAWLING_IMPLEMENTATION_DESIGN.md
├── 08_DATA_PIPELINE_AND_NORMALIZATION.md
├── 09_FIREBASE_IMPLEMENTATION.md
├── 10_Deployment_and_Operations_Guide.md
├── 11_Testing_and_Quality_Assurance_Guide.md
├── 12_Deployment_and_Operation_Plan.md   ← 본 문서
└── 13_SERVICE_AND_RUNTIME_ARCHITECTURE.md  ← Runtime SSOT
```

인덱스·Gate: **001-flowchart.md**

## 22. 최종 결론

PriceBrain 운영 환경은 **Firebase Hosting + Firestore + Rules**와 **FastAPI + Admin SDK(09)** 로 구성한다.

- Catalog **read:** Next.js Client SDK (**13**)
- Catalog **write / crawl:** FastAPI Admin SDK (**09**)
- Schema / Rules: **05**

GitHub·CI/CD·비용·장애 대응은 본 문서(12) 기준. Firebase **초기 설정**은 **10** 참조.

## 23. PriceBrain 문서화 완료 기준

```text
01 PRD → 02 Domain → 04 Principles → 05 Schema SSOT
        ↓
06 / 06-1 → 07 → 08 → 09
        ↓
13 Runtime → 10 Deploy Guide → 11 Testing → 12 Operation (본 문서)
        ↓
001 Index / Gate A~D
        ↓
     실제 개발 (pricebrain_app)
```

12번은 **운영·배포·비용** 실행 기준. Emulator·SDK 초기 설정은 **10**.