# PriceBrain
# Data Source & Crawling Architecture

- 문서 버전: v0.2
- 문서 상태: Draft (Firestore SSOT 정렬 — Phase 2)
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md`
- Runtime SSOT: `docs/13_SERVICE_AND_RUNTIME_ARCHITECTURE.md`
- 프로젝트명: PriceBrain
- 대상 카테고리: GPU / Graphics Card
- 최초 작성일: 2026-08-19

---

# 1. 문서 목적

본 문서는 PriceBrain의 외부 데이터 수집 및 크롤링 시스템의
전체적인 구조와 개발 원칙을 정의한다.

PriceBrain은 여러 외부 데이터 소스로부터
GPU 상품 및 가격 데이터를 수집하고,

수집된 데이터를 **08 Pipeline**으로 정규화한 뒤 **09 Repository**가 **Cloud Firestore**에 저장한다.

본 문서는 다음 개발 작업의 기준으로 사용한다.

- 데이터 소스 조사
- API 연동
- 웹 크롤링
- 상품 데이터 파싱
- 가격 데이터 수집
- 상품명 정규화
- 상품 매칭
- 데이터 검증
- Cloud Firestore 저장 (**09** Admin SDK)
- 가격 이력 구축
- 가격 분석


# 2. 핵심 목표

PriceBrain의 데이터 수집 시스템의 목표는 다음과 같다.

```text
외부 데이터
    ↓
수집
    ↓
파싱
    ↓
정규화
    ↓
상품 식별
    ↓
중복 검사
    ↓
데이터 검증
    ↓
Cloud Firestore 저장
    ↓
가격 분석

궁극적으로 다음 데이터를 지속적으로 축적한다.

상품 정보
+
판매처 정보
+
현재 가격
+
과거 가격
+
재고 정보
+
할인 정보
+
상품 URL
+
수집 시간

3. 데이터 소스 기본 원칙

PriceBrain은 데이터를 수집할 때
다음 우선순위를 기본 원칙으로 한다.

1. 공식 API
2. 공개 데이터
3. 공식적으로 제공되는 Feed
4. 허용된 웹 데이터
5. 웹 크롤링

API 또는 공식 데이터 제공 방식이 존재하는 경우
가능하면 크롤링보다 API를 우선한다.

4. 데이터 소스 유형

PriceBrain에서 고려하는 데이터 소스는 다음과 같다.

A. 가격비교 사이트
B. 대형 온라인 쇼핑몰
C. 오픈마켓
D. PC 부품 전문 쇼핑몰
E. 제조사 공식 사이트
F. 공개 API
G. 기타 공개 데이터

각 데이터 소스는
동일한 방식으로 처리하지 않는다.

5. 데이터 소스 역할

각 소스의 역할은 다음과 같이 구분한다.

가격비교 사이트

주요 목적:

상품 탐색
판매처 탐색
시장 가격 파악

장점:

다양한 판매처
다양한 상품
가격 비교에 유용

주의:

크롤링 정책
robots.txt
이용약관
요청 빈도
데이터 구조 변경
대형 온라인 쇼핑몰

주요 목적:

상품 정보
실제 판매 가격
배송비
재고
판매자 정보

장점:

실제 구매 가격에 가까움
상품 정보가 비교적 상세함

주의:

동적 렌더링
로그인
CAPTCHA
API 제한
비정상적인 접근 차단
오픈마켓

주요 목적:

판매자별 가격
판매자 정보
재고
상품 옵션

주의:

같은 상품이 여러 판매자에 의해
동시에 판매될 수 있다.

PC 전문 쇼핑몰

GPU 및 PC 부품 데이터 수집에서
중요한 데이터 소스가 될 수 있다.

주요 데이터:

상품명
제조사
GPU 모델
VRAM
가격
재고
배송비
상품 URL
6. 초기 데이터 소스 전략

MVP에서는 모든 쇼핑몰을
한꺼번에 수집하지 않는다.

초기에는 제한된 수의 데이터 소스로
시스템을 검증한다.

권장:

1차
    ↓
소수의 안정적인 데이터 소스


2차
    ↓
추가 판매처


3차
    ↓
오픈마켓


4차
    ↓
더 많은 데이터 소스

이유:

크롤링 시스템은
사이트마다 구조가 다르기 때문이다.

7. 데이터 소스 선정 기준

새로운 데이터 소스를 추가할 때
다음 항목을 평가한다.

평가 항목	설명
데이터 품질	상품 정보의 정확성
가격 정보	실제 판매 가격 확보 가능 여부
상품 식별	SKU / Part Number 존재 여부
데이터 구조	파싱 난이도
동적 렌더링	JavaScript 필요 여부
접근 제한	CAPTCHA / Rate Limit 등
robots.txt	크롤링 정책
이용약관	데이터 수집 허용 여부
안정성	페이지 구조 변경 빈도
수집 빈도	원하는 주기로 수집 가능한지
법적/정책적 위험	서비스 이용에 문제가 없는지
8. 크롤링 기본 원칙

PriceBrain은 무분별한 크롤링을 하지 않는다.

다음 원칙을 따른다.

robots.txt 확인
        ↓
이용약관 확인
        ↓
공식 API 확인
        ↓
허용된 범위 확인
        ↓
요청 빈도 제한
        ↓
필요한 데이터만 수집

과도한 요청을 발생시키지 않는다.

9. 크롤링 데이터 범위

PriceBrain이 수집하는 핵심 데이터:

상품명
브랜드
GPU 모델
제조사
Part Number
SKU
Model Number
VRAM
메모리 타입
가격
배송비
할인
쿠폰
재고
판매자
상품 URL
이미지 URL
수집 시간

모든 사이트에서
모든 필드를 가져올 필요는 없다.

10. Raw Data

외부에서 수집한 원본 데이터는
가능한 경우 원본 상태를 보존한다.

예:

Raw HTML
Raw JSON
API Response

원본 데이터와
정규화 데이터를 분리한다.

Raw Data
    ↓
Parser
    ↓
Normalized Data

원본 데이터는 문제 발생 시
재분석과 디버깅에 활용할 수 있다.

11. 데이터 수집 Pipeline

PriceBrain의 기본 수집 Pipeline:

┌───────────────────────┐
│ External Data Source  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│      Collector        │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│     Raw Response      │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│       Parser          │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│     Normalizer        │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Product Matcher       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│      Validator        │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│      Cloud Firestore       │
└───────────────────────┘
12. Collector

Collector는 외부 데이터 소스로부터
데이터를 가져오는 역할을 담당한다.

예:

collector/
├── source_a.py
├── source_b.py
├── source_c.py
└── base.py

각 데이터 소스의
접근 방법을 분리한다.

13. Collector Interface

각 Collector는 가능한 한
공통적인 인터페이스를 사용한다.

개념:

class BaseCollector:


    def search(self, keyword):
        pass


    def fetch_product(self, url):
        pass


    def collect(self):
        pass

실제 구현에서는
데이터 소스에 따라 필요한 기능만 사용한다.

14. API Collector

공식 API가 제공되는 경우
API Collector를 우선 사용한다.

구조:

API
 ↓
HTTP Request
 ↓
JSON Response
 ↓
Parser
 ↓
Normalizer

웹페이지를 직접 파싱하는 것보다
안정적일 가능성이 높다.

15. HTML Collector

HTML 기반 데이터 소스의 경우:

HTTP Request
 ↓
HTML
 ↓
Parser
 ↓
Data Extraction

구조를 사용한다.

16. Dynamic Web Page

JavaScript로 상품 정보가
동적으로 생성되는 사이트는
별도의 접근 방법이 필요할 수 있다.

예:

Browser Automation
        ↓
Page Render
        ↓
DOM
        ↓
Data Extraction

필요한 경우에만
Browser Automation을 사용한다.

무조건 Selenium 또는 Playwright를 사용하는 것은
지양한다.

17. 요청 빈도 제한

Collector는 데이터 소스별로
요청 빈도를 제한해야 한다.

예:

Request
 ↓
Delay
 ↓
Request
 ↓
Delay

사이트별 정책을 우선한다.

무분별한 병렬 요청을 하지 않는다.

18. Retry 정책

네트워크 오류가 발생할 경우
Retry를 사용할 수 있다.

예:

1차 요청
 ↓ 실패
대기
 ↓
2차 요청
 ↓ 실패
대기
 ↓
3차 요청
 ↓
실패 기록

무한 Retry는 사용하지 않는다.

19. HTTP 상태 코드 처리

예:

200
→ 정상


301 / 302
→ Redirect


404
→ 상품 없음


429
→ 요청 과다


500
→ 서버 오류


503
→ 서비스 이용 불가

특히 429 발생 시
요청 빈도를 낮춘다.

20. Parser

Parser는 Raw Data에서
PriceBrain이 필요한 필드를 추출한다.

예:

Raw Product Name
        ↓
Parser
        ↓
product_name
price
shipping_fee
seller_name
product_url

Parser는
Collector와 분리한다.

21. Normalizer

외부 데이터는
사이트마다 표현 방식이 다를 수 있다.

예:

RTX5070Ti
RTX 5070 Ti
GeForce RTX 5070 Ti
GeForce RTX5070 Ti

PriceBrain에서는
가능한 경우 동일한 기준으로 정규화한다.

22. 상품명 정규화

예:

원본:


ASUS TUF GAMING GeForce RTX 5070 Ti OC 16GB


정규화:


ASUS TUF GAMING RTX 5070 Ti OC 16GB

단, 원본 상품명은
반드시 보존한다.

listing_title

정규화된 이름:

normalized_name

을 별도로 관리한다.

23. GPU Model 정규화

GPU Model은
별도의 정규화 규칙을 사용한다.

예:

RTX 5070 Ti
RTX5070Ti
GeForce RTX 5070 Ti
NVIDIA GeForce RTX5070 Ti

↓

RTX 5070 Ti

이렇게 표준화한다.

24. Brand 정규화

예:

ASUSTeK
ASUS
ASUS Korea

가능한 경우:

ASUS

로 통합한다.

단, 원본 값은 보존한다.

25. 가격 정규화

가격 데이터는
정수 또는 NUMERIC 형태로 변환한다.

예:

"1,299,000원"

↓

1299000

배송비:

"무료배송"

↓

0

가격을 파싱할 수 없는 경우
오류 데이터로 분류한다.

26. 할인 가격

다음 데이터를 가능한 경우 분리한다.

상품 가격
배송비
즉시 할인
쿠폰
카드 할인

최종 가격:

final_price

를 계산한다.

단, 사용자의 조건이 필요한 할인은
별도로 구분한다.

27. 재고 정규화

외부 사이트:

재고 있음
재고없음
품절
일시품절
판매중

PriceBrain:

IN_STOCK
OUT_OF_STOCK
UNKNOWN

등으로 통일한다.

28. Seller 정규화

외부 사이트의 판매처 이름을
표준화한다.

예:

ABC몰
ABC SHOP
ABC 온라인몰

↓

ABC

내부 Seller ID와
연결한다.

29. Product Matching

PriceBrain에서
가장 중요한 데이터 처리 중 하나이다.

목표:

서로 다른 사이트에서 가져온
같은 상품을 하나의 Product로 연결

예:

사이트 A
ASUS TUF RTX 5070 Ti OC


사이트 B
ASUS TUF Gaming RTX5070Ti OC 16GB


사이트 C
TUF-RTX5070TI-O16G

↓

동일 Product 판단

↓

products.id = 1001
30. Product Matching 우선순위

상품 매칭 시 다음 순서를 사용한다.

1. Manufacturer Part Number


2. Manufacturer Product Code


3. SKU


4. Model Number


5. 정확한 상품명


6. 상품명 유사도


7. 상세 사양 비교


8. AI 기반 Matching

가능한 경우
문자열 유사도보다
제품 식별자를 우선한다.

31. AI Product Matching

AI를 이용한 상품 매칭은
후속 기능으로 구현한다.

예:

상품 A
ASUS TUF Gaming RTX 5070 Ti OC 16GB


상품 B
ASUS TUF RTX5070Ti O16G

AI가:

동일 상품 가능성: 98.7%

와 같이 판단할 수 있다.

단, AI 결과만으로
무조건 동일 상품으로 확정하지 않는다.

32. Matching Confidence

상품 매칭 결과에는
신뢰도를 둘 수 있다.

예:

1.00
→ 확실한 동일 상품


0.95
→ 매우 높은 가능성


0.80
→ 검토 필요


0.50
→ 불확실

실제 기준값은
데이터 확보 후 결정한다.

33. 데이터 Validation

저장 전에
데이터를 검증한다.

예:

상품명이 존재하는가?
가격이 숫자인가?
가격이 음수인가?
URL이 존재하는가?
판매처가 존재하는가?
수집 시간이 존재하는가?

Validation 실패 데이터는
DB에 무조건 저장하지 않는다.

34. Validation 결과

데이터 상태:

VALID
INVALID
WARNING

예:

가격 없음
→ WARNING


가격이 음수
→ INVALID


상품명 없음
→ INVALID


배송비 정보 없음
→ WARNING
35. Duplicate 처리

동일한 데이터가
여러 번 수집될 수 있다.

예:

10:00
1,000,000원


10:10
1,000,000원


10:20
1,000,000원

모든 Snapshot을 무조건 저장할지는
추후 결정한다.

초기에는 수집 이력을 우선 보존한다.

36. Price Snapshot 저장 정책

기본적으로:

수집 시간
+
가격
+
재고
+
배송비

를 저장한다.

가격이 변경되지 않았더라도
수집 주기를 기준으로 저장할 수 있다.

향후 데이터 규모가 커지면
가격 변경 시에만 저장하는 방식도 검토한다.

37. 수집 주기

MVP에서는
짧은 주기의 실시간 수집을 목표로 하지 않는다.

초기:

1일 1~4회

정도를 검토한다.

실제 수집 주기는:

데이터 소스 정책
+
서버 비용
+
데이터 중요도
+
가격 변동 빈도

를 기준으로 결정한다.

38. 데이터 수집 우선순위

모든 상품을 동일하게 수집하지 않는다.

예:

인기 GPU
     ↓
높은 수집 빈도


일반 GPU
     ↓
일반 수집 빈도


판매량 낮은 GPU
     ↓
낮은 수집 빈도

향후 동적 수집 정책으로 발전시킨다.

39. 수집 작업 Scheduler

향후 Scheduler를 사용한다.

개념:

Scheduler
    ↓
Collector Queue
    ↓
Collector
    ↓
Parser
    ↓
Database

초기에는 간단한 Scheduler로 시작하고
필요하면 확장한다.

40. Queue

데이터 소스가 증가하면
Queue 기반 수집 구조를 고려한다.

예:

Scheduler
    ↓
Queue
    ↓
Worker 1
Worker 2
Worker 3
    ↓
Database

MVP에서는 필요 이상으로 복잡하게 만들지 않는다.

41. 크롤링 실패 로그

Collector는 실패 정보를 기록한다.

예:

source
url
status_code
error_type
error_message
occurred_at

향후 별도의:

crawl_logs

테이블 또는 로그 시스템을 사용할 수 있다.

42. 데이터 수집 구조

초기 프로젝트 구조:

src/
├── collectors/
│   ├── base.py
│   ├── source_a.py
│   ├── source_b.py
│   └── source_c.py
│
├── parsers/
│   ├── source_a_parser.py
│   ├── source_b_parser.py
│   └── source_c_parser.py
│
├── normalizers/
│   ├── product_normalizer.py
│   ├── price_normalizer.py
│   └── seller_normalizer.py
│
├── matchers/
│   └── product_matcher.py
│
└── validators/
    └── product_validator.py
43. 데이터 처리 계층

각 기능을 분리한다.

Collector
→ 데이터를 가져온다.


Parser
→ 데이터를 추출한다.


Normalizer
→ 데이터를 표준화한다.


Matcher
→ 기존 상품과 연결한다.


Validator
→ 데이터를 검증한다.


Repository
→ DB에 저장한다.

각 계층은
하나의 책임을 갖는다.

44. Repository Layer

DB 접근 코드는
Collector 내부에 작성하지 않는다.

구조:

Collector
    ↓
Parser
    ↓
Normalizer
    ↓
Matcher
    ↓
Validator
    ↓
Repository
    ↓
Cloud Firestore

이렇게 분리한다.

45. Database 저장 순서

데이터 저장 순서:

1. Vendor
2. GPU Family
3. GPU Model
4. Board Partner
5. Product
6. Product Specification
7. Seller
8. Seller Listing
9. Price Snapshot

Foreign Key 관계를
고려하여 저장한다.

46. Transaction

관련 데이터 저장 시
필요한 경우 Transaction을 사용한다.

예:

Product 생성
+
Listing 생성
+
Price Snapshot 생성

중간에 실패하면
전체 작업을 Rollback할 수 있도록 한다.

47. 원본 데이터와 정규화 데이터

다음 원칙을 유지한다.

원본 데이터
=
절대적인 기준


정규화 데이터
=
PriceBrain 내부 사용 기준

예:

listing_title
→ 원본


normalized_name
→ 정규화

원본을 버리지 않는다.

48. 데이터 출처 추적

모든 가격 데이터는
가능한 경우 출처를 추적할 수 있어야 한다.

필수 또는 권장:

source_url
seller_id
collected_at

향후:

source_type
collector_version

등도 고려한다.

49. Collector Version

크롤러가 변경될 수 있으므로
수집 당시 Collector 버전을 기록하는 것을 고려한다.

예:

collector_version = 1.2.0

문제 발생 시
어떤 코드로 수집했는지 추적할 수 있다.

50. 데이터 신뢰도

각 데이터에
신뢰도 개념을 도입할 수 있다.

예:

공식 API
→ HIGH


공식 판매처
→ HIGH


대형 쇼핑몰
→ HIGH


일반 판매자
→ MEDIUM


불확실한 데이터
→ LOW

향후 가격 분석에도 활용할 수 있다.

51. 가격 비교 시 주의사항

단순히 가격이 낮다고
무조건 최저가로 판단하지 않는다.

다음 조건을 고려한다.

상품 동일 여부
+
재고 여부
+
배송비
+
할인 조건
+
판매자
+
정품 여부
+
상품 상태

특히 중고 / 리퍼 / 병행수입 등은
별도의 상태 구분이 필요하다.

52. 상품 상태

향후 다음 상태를 고려한다.

NEW
USED
REFURBISHED
OPEN_BOX
UNKNOWN

MVP에서는
신품 GPU를 우선 대상으로 한다.

53. 병행수입

병행수입 상품은
가격 비교에서 중요한 요소가 될 수 있다.

향후:

import_type

등의 필드를 고려한다.

예:

OFFICIAL
PARALLEL_IMPORT
UNKNOWN

단, MVP에서는
데이터 확보 후 결정한다.

54. 정품 / AS 정보

GPU 구매에서는
가격 외에도 AS 조건이 중요하다.

향후:

warranty_type
warranty_period
service_provider

등을 고려한다.

PriceBrain의
구매 적정성 분석에도 활용할 수 있다.

55. 가격 데이터의 가치

PriceBrain의 가장 중요한 자산은
시간이 지나면서 축적되는
Price Snapshot 데이터이다.

현재 가격
      ↓
1주일
      ↓
1개월
      ↓
3개월
      ↓
6개월
      ↓
1년

데이터가 축적될수록
가격 패턴 분석이 가능해진다.

56. 가격 분석과 연결

수집 데이터:

Price Snapshot

↓

분석:

최저가
최고가
평균가
중앙값
가격 변동률
가격 위치

↓

AI:

BUY
WAIT
AVOID

↓

Frontend:

현재 가격
가격 그래프
가격 분석
구매 추천
57. 가격 변동 그래프 데이터

Frontend에서 필요한 데이터 예:

[
  {
    "date": "2026-08-01",
    "price": 1099000
  },
  {
    "date": "2026-08-05",
    "price": 1079000
  },
  {
    "date": "2026-08-10",
    "price": 1049000
  }
]

이 데이터는:

price_snapshots

에서 생성한다.

58. Crawler와 AI의 역할 분리

AI가 크롤링을 직접 담당하지 않는다.

기본 구조:

Crawler
    ↓
Data
    ↓
Normalizer
    ↓
Database
    ↓
Analysis
    ↓
AI

AI는 주로:

상품 매칭 보조
가격 패턴 분석
구매 시점 분석
자연어 설명

등에 사용한다.

59. AI 분석의 기본 원칙

AI에게 원본 웹페이지 전체를
무분별하게 전달하지 않는다.

필요한 데이터만 정제하여 전달한다.

예:

현재 가격
최근 평균 가격
최근 최저가
최근 최고가
가격 변동률
가격 percentile
재고 상태

이런 구조화된 데이터를 AI에 전달한다.

60. 데이터 품질 우선순위

PriceBrain은 다음 우선순위를 따른다.

정확성
  >
일관성
  >
완전성
  >
수집량

데이터를 많이 모으는 것보다
정확하게 모으는 것을 우선한다.

61. MVP 범위

MVP에서는 다음까지만 구현한다.

1. 제한된 데이터 소스 선정


2. 상품 검색


3. 상품 데이터 수집


4. 가격 수집


5. 판매처 수집


6. 기본 정규화


7. Product Matching


8. Cloud Firestore 저장


9. 최신 가격 조회


10. 가격 이력 조회

다음 기능은 이후 구현한다.

AI Matching
AI Price Prediction
Dynamic Scheduler
Queue
Advanced Monitoring
62. MVP 수집 구조
User
  │
  │ Search
  ▼
Backend
  │
  ▼
Collector
  │
  ├──────────────┐
  ▼              ▼
Source A       Source B
  │              │
  └──────┬───────┘
         ▼
       Parser
         ↓
     Normalizer
         ↓
      Matcher
         ↓
     Validator
         ↓
     Cloud Firestore
         ↓
      Backend
         ↓
      Frontend
63. 향후 확장 구조
                    Scheduler
                        │
                        ▼
                      Queue
                        │
             ┌──────────┼──────────┐
             ▼          ▼          ▼
         Worker 1   Worker 2   Worker 3
             │          │          │
             ▼          ▼          ▼
          Source A   Source B   Source C
             │          │          │
             └──────────┼──────────┘
                        ▼
                     Parser
                        ↓
                   Normalizer
                        ↓
                     Matcher
                        ↓
                    Validator
                        ↓
                   Cloud Firestore
                        ↓
                  Price Analysis
                        ↓
                    AI Analysis
                        ↓
                     API
                        ↓
                    Frontend
64. 법적 / 정책적 원칙

PriceBrain은 데이터 수집 시
각 데이터 소스의 정책을 존중한다.

개발 전에 확인:

robots.txt
이용약관
API 이용약관
데이터 사용 조건
Rate Limit
자동화 접근 정책

허용되지 않은 방식으로
접근 제한을 우회하지 않는다.

예:

CAPTCHA 우회
IP 차단 우회
로그인 제한 우회
기타 접근 제한 우회

등은 구현하지 않는다.

65. 데이터 소스 변경 대응

크롤링 대상 사이트는
HTML 구조가 변경될 수 있다.

따라서:

Collector
Parser
Normalizer

를 분리한다.

사이트 구조 변경 시
전체 시스템을 수정하지 않고
해당 Source Adapter만 수정할 수 있도록 한다.

66. Source Adapter 구조

권장 구조:

src/
└── collectors/
    ├── base.py
    │
    ├── source_a/
    │   ├── collector.py
    │   ├── parser.py
    │   └── normalizer.py
    │
    ├── source_b/
    │   ├── collector.py
    │   ├── parser.py
    │   └── normalizer.py
    │
    └── source_c/
        ├── collector.py
        ├── parser.py
        └── normalizer.py
67. 테스트

각 Collector는
실제 사이트에 매번 요청하지 않고
테스트용 Fixture를 사용할 수 있도록 한다.

예:

tests/
└── fixtures/
    ├── source_a_product.html
    ├── source_b_product.json
    └── source_c_product.html

이를 통해:

Parser Test
Normalizer Test
Matcher Test

를 자동화할 수 있다.

68. 테스트 원칙

크롤링 시스템은
실제 웹사이트에 의존하는 테스트와
로컬 테스트를 분리한다.

Unit Test
→ 로컬 Fixture


Integration Test
→ 실제 데이터 소스


E2E Test
→ 전체 Pipeline

실제 사이트에 대한 테스트 요청은
필요한 경우에만 실행한다.

69. 데이터 소스 조사 결과 기록

각 데이터 소스는 별도의 문서 또는
데이터 소스 목록에 기록한다.

예:

docs/
└── data_sources/
    ├── source_a.md
    ├── source_b.md
    └── source_c.md

각 문서에는:

사이트명
URL
데이터 유형
API 여부
크롤링 가능 여부
robots.txt
이용약관
수집 가능 필드
수집 난이도
주의사항

을 기록한다.

70. Data Source Registry

향후 코드에서도
데이터 소스를 관리할 수 있다.

예:

{
  "source": "source_a",
  "enabled": true,
  "type": "html",
  "priority": 1
}

데이터 소스가 증가하면
설정 기반으로 관리하는 것을 검토한다.

71. 데이터 수집 우선순위

초기 개발 순서:

1. Source 조사


2. 샘플 데이터 확보


3. Parser 구현


4. Normalizer 구현


5. Product Matcher 구현


6. Validator 구현


7. Cloud Firestore 저장


8. 가격 Snapshot 축적


9. API 연결


10. Frontend 연결
72. 개발 시 금지사항

다음과 같은 구현은 피한다.

Crawler 안에서 DB 직접 접근


Parser 안에서 DB 수정


Frontend에서 크롤링


AI가 DB 원본 데이터 직접 수정


사이트별 코드를 하나의 거대한 파일에 작성


크롤링 결과를 검증 없이 DB에 저장

각 기능을 명확하게 분리한다.

73. 핵심 아키텍처 원칙

PriceBrain의 데이터 수집 시스템은:

Source Independent
        +
Modular
        +
Testable
        +
Traceable
        +
Recoverable

구조를 목표로 한다.

74. 최종 데이터 Pipeline
┌─────────────────────┐
│ External Data Source│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      Collector      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     Raw Storage     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│       Parser        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     Normalizer      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Product Matcher    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      Validator      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Repository       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Cloud Firestore       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Price Analysis    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    AI Analysis      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      Backend API    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      Frontend       │
└─────────────────────┘
75. 현재 결정 사항
항목	결정
데이터 대상	GPU / Graphics Card
데이터 수집	API 우선, 허용된 범위의 크롤링
Raw Data	가능한 경우 보존
Parser	Collector와 분리
Normalizer	별도 계층
Product Matching	별도 계층
Validator	DB 저장 전 실행
가격 이력	Price Snapshot
DB	Cloud Firestore (**05** Schema SSOT)
상품 매칭	식별자 우선
AI Matching	후속 기능
Scheduler	MVP 이후
Queue	MVP 이후
Browser Automation	필요한 경우에만
수집 빈도	초기 1~4회/일 검토
데이터 상태	VALID / INVALID / WARNING
원본 상품명	보존
정규화 상품명	별도 저장
76. 미결정 사항

실제 데이터 소스 조사를 통해
다음 사항을 확정한다.

최초 수집 대상 사이트
공식 API 존재 여부
실제 수집 가능 필드
실제 상품 식별자
SKU 구조
Part Number 구조
가격 데이터 구조
배송비 데이터 구조
할인 데이터 구조
재고 데이터 구조
상품명 정규화 규칙
상품 매칭 기준
수집 주기
Raw Data 저장 위치
크롤링 정책
데이터 보존 기간
77. 다음 단계

본 문서 작성 후
실제 데이터 소스에 대한 조사를 진행한다.

다음 작업:

실제 데이터 소스 조사
        ↓
샘플 상품 데이터 확보
        ↓
06-1 Collection Mapping 검증 (**05**)
        ↓
05 Schema / Rules / Index 확정 (변경 시)
        ↓
Firestore Emulator 또는 dev 프로젝트 (**10**)
        ↓
07 Crawler MVP → 08 Pipeline → 09 Repository
        ↓
Seed Data (`gpu_*`, `malls`)

실제 데이터 조사 결과가 **05 Collection Schema**와 다를 경우 **05** 및 **08 §26.1**을 먼저 수정한다.

78. 최종 목표

PriceBrain의 데이터 수집 시스템은
단순한 웹 크롤러가 아니다.

목표는:

웹 데이터 수집
       ↓
정확한 상품 식별
       ↓
판매처 통합
       ↓
시간별 가격 축적
       ↓
가격 데이터 분석
       ↓
AI 기반 구매 판단

까지 연결되는
가격 데이터 플랫폼을 구축하는 것이다.

79. 핵심 문장

PriceBrain은 여러 데이터 소스로부터 상품과 가격 데이터를 수집하고,
이를 표준화하여 동일 상품을 식별한 뒤,
시간에 따른 가격 데이터를 축적하여
사용자에게 가장 합리적인 구매 판단을 제공하는 것을 목표로 한다.

---

# Appendix A. Design History (Non-SSOT)

### A.1 PostgreSQL (초기 v0.1)

v0.1 본문은 수집 데이터를 PostgreSQL에 저장하는 흐름을 가정했다 (ERD, CREATE TABLE, Docker PostgreSQL 설치 등).

**현행 SSOT:** Cloud Firestore + **05** Collection Schema. persist는 **09** Admin SDK.

### A.2 파이프라인 정렬 (Phase 2)

| v0.1 | v0.2 |
|------|------|
| Crawler 내 정규화·DB 저장 혼재 | **07** Raw → **08** Pipeline → **09** Firestore |
| ERD / relational table | **05** Collections (`products`, `listings`, …) |

`canonical_products` table/node는 사용하지 않음. Canonical = **`products`** (**05 §1**).
