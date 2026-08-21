# PriceBrain
# Data Source Research

- 문서 버전: v0.2
- 문서 상태: Draft (Firestore SSOT 정렬 — Phase 2)
- **현행 DB:** Cloud Firestore — Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md`
- 프로젝트명: PriceBrain
- 대상 카테고리: GPU / Graphics Card
- 최초 작성일: 2026-08-19

---

# 1. 문서 목적

본 문서는 PriceBrain의 핵심 데이터인

- GPU 기본 정보
- GPU 제품 정보
- 판매처 정보
- 상품 가격
- 가격 이력

을 어떤 데이터 소스에서 확보할 것인지 조사하고
향후 데이터 수집 시스템의 기준을 정의하는 것을 목적으로 한다.

PriceBrain은 단순히 많은 데이터를 수집하는 것을 목표로 하지 않는다.

> 정확하고 지속적으로 수집할 수 있으며
> 출처를 추적할 수 있는 데이터를 확보하는 것을 우선한다.


# 2. 데이터 소스 기본 원칙

PriceBrain은 데이터 수집 시 다음 우선순위를 적용한다.

1. 공식 API
2. 공식 데이터 제공 서비스
3. 공개 데이터
4. 제휴 데이터
5. 이용이 허용된 데이터 수집 방식
6. 정책 및 약관을 확인한 크롤링

데이터 수집 전 각 서비스의

- 이용약관
- robots.txt
- API 정책
- 데이터 이용 정책
- 저작권 정책

등을 확인한다.


# 3. 필요한 데이터 종류

PriceBrain에서 필요한 데이터는 크게 다음과 같이 구분한다.

## 3.1 GPU 기본 정보

예:

- 제조사
- 제품군
- GPU 모델
- 세대
- 아키텍처
- CUDA Core
- Stream Processor
- Tensor Core
- RT Core
- 메모리
- 메모리 타입
- 메모리 버스
- TDP
- 출시일


## 3.2 실제 그래픽카드 제품 정보

예:

- 제조사
- Board Partner
- 제품명
- 모델번호
- Part Number
- SKU
- GPU Model
- VRAM
- 메모리 타입
- 부스트 클럭
- 길이
- 슬롯 수
- 쿨링 방식
- 팬 수
- 전원 커넥터


## 3.3 판매처 정보

예:

- 판매처 이름
- 판매처 URL
- 판매처 상품 ID
- 상품 URL
- 판매 상태


## 3.4 가격 정보

예:

- 상품 가격
- 할인 가격
- 배송비
- 쿠폰
- 카드 할인
- 최종 가격
- 품절 여부
- 수집 시간


## 3.5 가격 이력

예:

- 수집 날짜
- 가격
- 배송비
- 할인
- 최종 가격

가격 이력은 PriceBrain의 핵심 데이터이다.


# 4. 데이터 소스 분류

PriceBrain에서는 데이터 소스를 다음과 같이 분류한다.

```text
A. GPU 제조사 데이터
B. 국내 판매처 데이터
C. 가격 비교 데이터
D. 공개 데이터
E. 향후 제휴 데이터

각 데이터 소스는 별도로 평가한다.

5. GPU 제조사 데이터
5.1 NVIDIA

목적:

GPU Model의 공식 사양 확보

필요 데이터:

GPU 모델
CUDA Core
메모리
메모리 타입
메모리 버스
클럭
전력
권장 PSU
출력 포트
지원 기술
5.2 AMD

목적:

Radeon GPU Model의 공식 사양 확보

필요 데이터:

GPU 모델
Stream Processor
메모리
메모리 타입
메모리 버스
클럭
전력
출력 포트
지원 기술
5.3 원칙

제조사 공식 데이터는 가능한 경우
GPU Model의 기준 데이터로 사용한다.

판매처에서 수집한 정보보다
제조사 공식 정보를 우선한다.

6. Board Partner 데이터

주요 Board Partner 후보:

ASUS
MSI
GIGABYTE
ZOTAC
GALAX
PNY
SAPPHIRE
PowerColor
XFX
ASRock

확보 대상:

제조사
제품명
모델번호
Part Number
GPU Model
VRAM
클럭
크기
전원 커넥터
출력 포트
제품 이미지
7. 국내 판매처 데이터

PriceBrain은 초기에는 국내 시장을 중심으로
가격 비교 시스템을 구축한다.

후보 판매처는 별도 조사를 통해 결정한다.

예상 후보:

대형 온라인 쇼핑몰
오픈마켓
PC 전문 쇼핑몰
가격 비교 서비스
GPU 전문 판매처

단순히 인지도가 높은 사이트라는 이유만으로
수집 대상으로 확정하지 않는다.

8. 판매처 평가 기준

각 판매처는 다음 기준으로 평가한다.

평가 항목	내용
API	공식 API 제공 여부
크롤링	기술적으로 데이터 수집 가능한지
약관	자동 수집 허용 여부
robots.txt	크롤러 접근 정책
가격 데이터	가격 확인 가능 여부
배송비	배송비 확인 가능 여부
상품 ID	고유 상품 ID 존재 여부
SKU	SKU 또는 모델번호 존재 여부
재고	재고 상태 확인 가능 여부
상품 URL	개별 상품 URL 제공 여부
이미지	상품 이미지 제공 여부
안정성	페이지 구조 변경 가능성
수집 빈도	지속적인 수집 가능성
9. 데이터 소스 평가 점수

각 데이터 소스는 다음과 같이 평가한다.

API 제공
★★★★★


데이터 정확성
★★★★★


상품 식별 가능성
★★★★★


가격 데이터 품질
★★★★★


수집 안정성
★★★★★


법적/정책적 안정성
★★★★★

최종 점수는 데이터 수집 전략 결정 시 활용한다.

10. 가격 비교 서비스 데이터

가격 비교 서비스는
여러 판매처의 가격을 한 번에 확인할 수 있다는 장점이 있다.

그러나 다음 사항을 확인해야 한다.

공식 API 제공 여부
데이터 이용 가능 여부
가격 데이터의 출처
상품 식별 방식
가격 업데이트 주기
외부 서비스 이용 제한
11. 오픈마켓 데이터

오픈마켓의 경우 동일 상품이
여러 판매자에 의해 판매될 수 있다.

따라서 다음 데이터를 구분한다.

Market
    ↓
Seller
    ↓
Listing
    ↓
Product
    ↓
Price

예:

오픈마켓
 ├── 판매자 A
 │    └── RTX 5070 Ti
 │
 ├── 판매자 B
 │    └── RTX 5070 Ti
 │
 └── 판매자 C
      └── RTX 5070 Ti

따라서 오픈마켓은 단순한 상품 가격 수집보다
Seller와 Listing 구조를 고려해야 한다.

12. 상품 식별 데이터

PriceBrain에서 가장 중요한 데이터 중 하나는
상품을 정확하게 식별하는 것이다.

가능한 식별 정보의 우선순위:

1. Manufacturer Part Number
2. Manufacturer Product Code
3. SKU
4. Model Number
5. Product ID
6. 브랜드 + 모델명
7. 상품명

상품명만으로 동일 상품을 판단하는 것은 피한다.

13. 상품명 정규화

판매처마다 동일한 상품을
서로 다른 이름으로 표시할 수 있다.

예:

ASUS TUF RTX 5070 Ti OC


ASUS TUF Gaming RTX 5070 Ti OC


ASUS TUF GAMING GeForce RTX5070Ti OC

따라서 수집 단계에서

Raw Product Name
        ↓
Normalization
        ↓
Brand
        ↓
Board Partner
        ↓
GPU Model
        ↓
Model Number
        ↓
SKU

형태로 데이터를 구조화한다.

14. 가격 데이터 수집

가격은 단순히 현재 가격 하나만 저장하지 않는다.

다음 정보를 가능한 경우 저장한다.

product_price
shipping_fee
discount_price
coupon_discount
card_discount
final_price
stock_status
collected_at

특히 collected_at은 필수 데이터로 취급한다.

15. 가격 이력 수집

PriceBrain의 핵심 기능은 가격 이력 분석이다.

따라서 동일 상품의 가격을
시간에 따라 지속적으로 수집한다.

예:

상품 A


08-01  1,049,000
08-03  1,029,000
08-05  999,000
08-07  1,019,000
08-10  1,049,000

이 데이터를 기반으로 가격 변동 그래프를 생성한다.

16. 데이터 수집 주기

초기에는 다음 수집 주기를 검토한다.

1시간
3시간
6시간
12시간
24시간

실제 수집 주기는 다음 요소를 고려하여 결정한다.

판매처 정책
서버 부하
가격 변동성
데이터 중요도
운영 비용
크롤링 안정성
17. 초기 권장 수집 전략

MVP에서는 지나치게 높은 수집 빈도를 사용하지 않는다.

초기에는:

주기적 수집
+
필요한 상품 중심 수집

방식을 우선 검토한다.

예:

전체 상품
→ 하루 1~2회


인기 상품
→ 더 높은 빈도


사용자가 관심 등록한 상품
→ 우선 수집

최종 주기는 실제 데이터 특성을 확인한 후 결정한다.

18. Raw Data 저장

수집한 원본 데이터는 가능한 경우
별도로 보관한다.

예:

Raw HTML
Raw JSON
Raw API Response

이유:

크롤러 오류 분석
데이터 정제 오류 분석
상품 매칭 오류 분석
사이트 구조 변경 대응
데이터 재처리
19. 데이터 처리 Pipeline

전체 데이터 흐름:

Data Source
    ↓
Collector
    ↓
Raw Data
    ↓
Parser
    ↓
Normalizer
    ↓
Validator
    ↓
Product Matcher
    ↓
Database
    ↓
Price Analysis
    ↓
AI Analysis

각 단계는 가능한 경우 독립적으로 구성한다.

20. Collector

Collector는 외부 데이터 소스에서
원본 데이터를 가져오는 역할을 담당한다.

예:

NVIDIA Collector
AMD Collector
Seller A Collector
Seller B Collector

판매처마다 데이터 구조가 다르므로
Collector를 분리할 수 있도록 설계한다.

21. Parser

Parser는 원본 데이터에서 필요한 정보를 추출한다.

예:

Raw HTML
    ↓
상품명
가격
배송비
SKU
상품 URL
재고

Parser는 특정 사이트의 HTML 구조에 의존할 수 있으므로
변경에 대비한다.

22. Normalizer

Normalizer는 서로 다른 형식의 데이터를
PriceBrain의 표준 형식으로 변환한다.

예:

RTX5070Ti
RTX 5070 Ti
GeForce RTX 5070 Ti

↓

RTX 5070 Ti

동일하게 브랜드와 모델명도 정규화한다.

23. Validator

Validator는 수집된 데이터의 품질을 검증한다.

검증 예:

가격 > 0
상품명 존재
URL 존재
판매처 존재
수집 시간 존재

이상 데이터는 별도로 기록한다.

24. Product Matcher

Product Matcher는
수집된 상품이 기존 Product와 동일한 상품인지 판단한다.

예:

수집 상품
ASUS TUF RTX 5070 Ti OC


        ↓


기존 Product 검색


        ↓


Part Number 비교


        ↓


Model Number 비교


        ↓


스펙 비교


        ↓


동일 Product 판단

향후 AI 기반 유사도 분석을 추가할 수 있다.

25. 데이터 중복 처리

동일한 상품이 여러 번 수집될 수 있다.

따라서 다음 키를 우선 활용한다.

manufacturer_part_number
seller_product_id
sku
product_code

가능한 경우 Unique Constraint를 사용한다.

26. 가격 중복 처리

동일한 가격이 반복적으로 수집되는 경우에도
수집 기록 자체가 의미를 가질 수 있다.

예:

10:00 → 1,000,000
11:00 → 1,000,000
12:00 → 1,000,000

초기 MVP에서는 모든 Snapshot을 저장할지,
가격이 변경된 경우만 저장할지는
DB 설계 단계에서 결정한다.

단, 데이터 분석에 필요한 원본 수집 기록은
가능한 경우 보존한다.

27. 품절 상품

품절 상품은 가격 데이터와 구분한다.

예:

stock_status


IN_STOCK
OUT_OF_STOCK
UNKNOWN

품절되었다고 해서
과거 가격 데이터를 삭제하지 않는다.

28. 판매 종료 상품

판매 종료 상품 역시
과거 데이터를 삭제하지 않는다.

Product
    ↓
Listing
    ↓
판매 종료

상태만 변경한다.

29. 데이터 출처 추적

모든 수집 데이터는 가능한 경우
다음 정보를 추적할 수 있어야 한다.

source
source_url
seller
collector
collected_at

데이터 문제가 발생했을 때
원인을 추적할 수 있어야 한다.

30. 데이터 신뢰도

향후 각 데이터에
신뢰도 점수를 부여할 수 있다.

예:

Official API
→ HIGH


Official Website
→ HIGH


Verified Partner
→ HIGH


Price Comparison Source
→ MEDIUM


Unverified Source
→ LOW

실제 점수 체계는 향후 설계한다.

31. 데이터 소스 비교표

실제 조사 결과를 다음 표에 기록한다.

Source	Type	API	Price	SKU	Stock	Shipping	Policy	Stability	Score
Source A									
Source B									
Source C									
32. 데이터 수집 방식 결정 기준

각 데이터 소스에 대해 다음을 확인한 후
수집 방식을 결정한다.

API 존재
    ↓
API 사용 가능
    ↓
API 우선


API 없음
    ↓
공개 데이터 확인
    ↓
제휴 데이터 확인
    ↓
정책 확인
    ↓
허용된 데이터 수집 방식 검토

무조건 크롤링부터 시작하지 않는다.

33. 크롤링 설계 원칙

크롤러는 다음 원칙을 따른다.

원칙 1

사이트별 Collector를 분리한다.

원칙 2

사이트 HTML 구조에 대한 의존성을 최소화한다.

원칙 3

수집 실패를 시스템 전체 장애로 확산시키지 않는다.

원칙 4

재시도 정책을 둔다.

원칙 5

Rate Limit을 준수한다.

원칙 6

robots.txt 및 서비스 정책을 확인한다.

원칙 7

원본 데이터를 가능한 경우 보존한다.

원칙 8

모든 데이터에 수집 시간을 기록한다.

34. MVP 데이터 소스 전략

MVP에서는 처음부터 모든 판매처를 지원하지 않는다.

다음 순서로 진행한다.

1. 데이터 소스 조사
        ↓
2. 가장 안정적인 Source 선정
        ↓
3. 단일 Source Collector 개발
        ↓
4. 데이터 구조 검증
        ↓
5. Product Matching 검증
        ↓
6. 가격 이력 축적
        ↓
7. 추가 Source 확장

이를 통해 초기 개발 복잡도를 낮춘다.

35. 데이터 소스 확장

1차:

Source A

2차:

Source A
Source B

3차:

Source A
Source B
Source C
Source D

판매처를 늘리는 것보다
데이터 품질과 상품 매칭 정확도를 우선한다.

36. 향후 API 연계

가능한 경우 외부 API를 활용한다.

예상 대상:

상품 정보 API
가격 정보 API
검색 API
공공 데이터 API
제조사 데이터
37. 데이터 저장 구조 (현행)

**현행 SSOT:** 수집 → **08 Pipeline** → **09 Repository** → **Cloud Firestore** (**05** Collections).

```text
Raw Data (07 Parser)
    ↓
Processed / Validated (08)
    ↓
Cloud Firestore (products, listings, price_history, …)
```

향후 확장:

```text
Raw Storage (optional)
    ↓
08 Pipeline
    ↓
Cloud Firestore
    ↓
Analytics / AI Layer
```

**조사 이력:** 초기안은 PostgreSQL 적재를 검토 — **Appendix A** (Non-SSOT).

38. 데이터 수집과 분석의 분리

수집 시스템과 분석 시스템은 가능한 경우 분리한다.

Crawler (07)
   ↓
Cloud Firestore (catalog)
   ↓
Analysis

크롤러가 가격 분석까지 직접 수행하지 않는다.

이를 통해 데이터 수집과 분석을 독립적으로 확장할 수 있다.

39. 데이터 소스 조사 결과 기록

각 Source 조사 후 다음 정보를 기록한다.

Source Name
Source URL
Data Type
API Availability
API Documentation
Crawling Availability
Terms of Service
robots.txt
Product Data
Price Data
SKU Data
Shipping Data
Stock Data
Image Data
Update Frequency
Data Quality
Risk
Final Decision

최종적으로:

USE
CONSIDER
REJECT

중 하나로 판단한다.

40. 현재 결정 사항

| 항목 | 결정 |
|------|------|
| 첫 번째 카테고리 | GPU |
| 주요 GPU Vendor | NVIDIA / AMD |
| 초기 시장 | 국내 |
| **현행 Database** | **Cloud Firestore** (**05** Schema SSOT) |
| 데이터 수집 | 단계적 확대 (07→08→09) |
| API | 우선 검토 |
| 크롤링 | 정책 확인 후 검토 |
| Raw Data | 가능한 경우 보존 (`listings.raw_*`) |
| 가격 이력 | `listings/.../price_history` |
| 상품 매칭 | 08 matcher → `products` |
| AI Matching | 향후 |
| 초기 수집 Source 수 | 최소화 |
| 수집 주기 | 조사 후 결정 |
41. 미결정 사항

다음 항목은 실제 조사 후 확정한다.

NVIDIA 데이터 소스
AMD 데이터 소스
Board Partner 데이터 소스
국내 가격 데이터 소스
초기 판매처
가격 비교 데이터 소스
API 사용 여부
크롤링 가능 여부
수집 주기
Raw Data 저장 방식
상품 매칭 알고리즘
가격 Snapshot 저장 정책
42. 다음 단계

본 문서 작성 후 다음 작업을 진행한다.

03_DATA_SOURCE_RESEARCH.md
        ↓
실제 데이터 소스 조사
        ↓
Source 선정
        ↓
데이터 샘플 확보
        ↓
데이터 구조 분석
        ↓
06-1 Collection Mapping Gate (**05**)
        ↓
07 Crawler MVP

---

# Appendix A. Design History — PostgreSQL (조사 후보, Non-SSOT)

초기 v0.1 §37·§42는 Raw → Processed → **PostgreSQL** 및 PostgreSQL Schema·ERD 순서를 **조사 단계 후보**로 기록했다.

| 조사 후보 (과거) | 현행 SSOT |
|------------------|-----------|
| PostgreSQL relational schema | **Cloud Firestore** (**05**) |
| ERD / CREATE TABLE | **05** Collection·Field |
| `canonical_products` (일부 문서) | **`products`** Collection |

PostgreSQL은 **역사적·비교 조사 기록**으로만 유지하며 **현행 구현 DB가 아님**.