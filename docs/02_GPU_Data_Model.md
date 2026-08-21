
---

# ② `02_GPU_Data_Model.md`

그리고 두 번째 파일입니다.

```md
# PriceBrain GPU Data Model

- 문서 버전: v0.2
- 문서 상태: Draft (Firestore SSOT 정렬 — Phase 2)
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md` (Collection 매핑 **05 §8**)
- 프로젝트: PriceBrain
- 대상 카테고리: GPU / Graphics Card
- 최초 작성일: 2026-08-19

---

# 1. 문서 목적

본 문서는 PriceBrain의 첫 번째 상품 카테고리인
GPU / Graphics Card의 데이터 구조를 정의한다.

PriceBrain은 단순히 그래픽카드 상품과 가격을 저장하는 것이 아니라,

> GPU Vendor → GPU Family → GPU Model → Product → Seller → Price → Price History

라는 구조를 기반으로 데이터를 관리한다.

본 문서는 다음 작업의 **도메인 SSOT**로 사용한다.

- GPU 도메인 엔티티·관계
- Firestore Collection 매핑 (**개념** — Field 상세는 **05**)
- 데이터 수집·크롤러·파이프라인 **도메인** 참조
- 가격 분석·API **도메인** 참조

Schema·Rules·Index 상세: **05**. persist: **09**. Runtime: **13**.
- AI 분석


# 2. 핵심 데이터 구조

PriceBrain GPU 데이터의 기본 구조:

```text
GPU Vendor
    ↓
GPU Family
    ↓
GPU Model
    ↓
Product
    ↓
Seller Listing
    ↓
Price Snapshot
    ↓
Price History


Product에는 실제 제조사/보드 파트너 정보가 연결된다.

3. GPU Vendor
3.1 정의

GPU Vendor는 GPU 칩셋 및 GPU 플랫폼을 제공하는 제조사를 의미한다.

MVP에서는 다음 두 업체를 지원한다.

NVIDIA
AMD

향후 필요에 따라 Intel 등을 추가할 수 있다.

4. GPU Family

GPU Family는 GPU Vendor의 제품군을 의미한다.

초기 지원:

NVIDIA
└── GeForce RTX


AMD
└── Radeon RX

향후 세대별 분류가 필요할 경우 Generation을 별도 속성 또는 엔티티로 분리한다.

5. GPU Model

GPU Model은 GPU의 핵심 모델을 의미한다.

예:

RTX 5090
RTX 5080
RTX 5070 Ti
RTX 5070


RX 9070 XT
RX 9070
RX 9060 XT

중요한 원칙:

GPU Model과 실제 판매 Product는 동일한 개념으로 취급하지 않는다.

예:

GPU Model
└── RTX 5070 Ti


Product
├── ASUS TUF Gaming RTX 5070 Ti OC
├── MSI RTX 5070 Ti Gaming Trio
├── GIGABYTE RTX 5070 Ti Gaming OC
└── ZOTAC RTX 5070 Ti
6. GPU Model 데이터

GPU Model에서 관리할 수 있는 주요 데이터:

model_name
vendor
family
generation
architecture
process_node
cuda_cores
stream_processors
tensor_cores
rt_cores
base_clock
boost_clock
memory_type
memory_size
memory_bus_width
memory_bandwidth
tdp
recommended_psu
release_date

모든 GPU에서 모든 정보가 제공되는 것은 아니므로
필요한 경우 NULL을 허용한다.

7. Board Partner
7.1 정의

Board Partner는 GPU 칩을 기반으로 실제 그래픽카드 제품을 제조하는 파트너 제조사를 의미한다.

예:

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
7.2 GPU Vendor와 구분

다음 두 개념을 명확하게 구분한다.

GPU Vendor
= NVIDIA / AMD


Board Partner
= ASUS / MSI / GIGABYTE / SAPPHIRE / PowerColor ...

예:

NVIDIA
└── RTX 5070 Ti
    └── ASUS
        └── 실제 ASUS 제품

또는:

AMD
└── RX 9070 XT
    └── SAPPHIRE
        └── 실제 SAPPHIRE 제품
8. Product
8.1 정의

Product는 실제 소비자가 구매할 수 있는 하나의 그래픽카드 제품을 의미한다.

예:

ASUS TUF Gaming RTX 5070 Ti OC
MSI RTX 5070 Ti Gaming Trio
GIGABYTE RTX 5070 Ti Gaming OC
SAPPHIRE NITRO+ RX 9070 XT
8.2 관계

하나의 GPU Model은 여러 Product를 가질 수 있다.

RTX 5070 Ti
│
├── ASUS Product
├── MSI Product
├── GIGABYTE Product
├── ZOTAC Product
└── PNY Product

관계:

GPU Model 1 : N Product
9. Product SKU

SKU 또는 제조사 제품 번호는 실제 판매 상품을 식별하기 위한 핵심 데이터다.

관리 대상:

sku
model_number
part_number
product_code
manufacturer_product_id

상품명만으로 동일 상품을 판단하지 않는다.

가능한 경우 제조사 Part Number 또는 Model Number를 우선 사용한다.

10. Product Specification

Product별 상세 사양은 GPU Model의 기본 사양과 분리할 수 있다.

예:

length
width
height
slot_count
cooling_type
fan_count
power_connector
power_consumption
recommended_psu
clock_speed
memory_size
memory_type
display_outputs

동일 GPU Model이라도 제조사별 실제 제품의 사양이 다를 수 있으므로
Product Specification을 별도로 관리할 수 있어야 한다.

11. Seller
11.1 정의

Seller는 실제 상품을 판매하는 판매처를 의미한다.

예:

판매처 A
판매처 B
판매처 C

주요 데이터:

seller_id
seller_name
seller_url
seller_type
is_active
11.2 관계

하나의 Product는 여러 Seller에서 판매될 수 있다.

Product
├── Seller A
├── Seller B
├── Seller C
└── Seller D

따라서 Product와 Seller 사이에는
Seller Listing을 사용한다.

12. Seller Listing

Seller Listing은 특정 판매처에서
특정 Product가 판매되고 있는 정보를 의미한다.

예:

Product:
MSI RTX 5070 Ti Gaming Trio


Seller:
판매처 A


Seller Listing:
판매처 A에서 판매 중인 MSI RTX 5070 Ti Gaming Trio

주요 데이터:

listing_id
product_id
seller_id
seller_product_id
product_url
listing_title
current_price
shipping_fee
discount_price
coupon_info
stock_status
collected_at
13. Price Snapshot

Price Snapshot은 특정 시점에 수집한 가격 정보를 의미한다.

예:

상품:
MSI RTX 5070 Ti Gaming Trio


판매처:
판매처 A


수집시간:
2026-08-19 13:30:00


상품가격:
1,049,000원


배송비:
0원

주요 데이터:

snapshot_id
listing_id
product_price
shipping_fee
discount_amount
coupon_discount
final_price
currency
collected_at

Price Snapshot은 가격 이력을 만드는 원천 데이터다.

14. Price History

Price Snapshot이 시간에 따라 축적되면서
가격 이력이 만들어진다.

예:

2026-08-01 → 999,000
2026-08-05 → 1,019,000
2026-08-10 → 1,049,000
2026-08-15 → 1,029,000
2026-08-19 → 1,049,000

이를 이용해:

minimum_price
maximum_price
average_price
median_price
price_change_rate
price_trend

등을 계산한다.

중요:

Price History를 별도의 중복 데이터로 저장할지,
Price Snapshot을 기반으로 조회할지는 DB 설계 단계에서 결정한다.

15. 가격 데이터

PriceBrain은 다음 가격을 구분한다.

product_price
shipping_fee
discount_amount
coupon_discount
final_price

가능한 경우:

실구매 예상가격
=
상품 가격
+
배송비
-
확정적으로 적용 가능한 할인

개인별 카드 할인이나 특정 사용자에게만 적용되는 쿠폰은
일반 가격과 구분한다.

16. 가격 분석

PriceBrain은 현재 가격 자체보다
과거 가격과 비교한 상대적인 위치를 중요하게 취급한다.

기본 지표:

current_price
min_price
max_price
average_price
median_price
recent_min_price
recent_average_price
price_change_rate
price_percentile

기본 분석 기간:

7일
30일
90일

향후:

180일
365일
17. 가격 추세

가격 데이터를 시간 순으로 분석하여
다음 상태를 판단할 수 있다.

UP
DOWN
STABLE
VOLATILE
UNKNOWN

초기에는 규칙 기반 분석을 사용한다.

향후 통계 모델 또는 머신러닝을 검토한다.

18. 상품 식별

상품 식별은 PriceBrain의 핵심 데이터 처리 과정이다.

18.1 우선순위

가능한 경우 다음 순서로 동일 상품을 판단한다.

제조사 Part Number
Manufacturer Product Code
SKU
모델 번호
브랜드 + 모델명
주요 제품 스펙
상품명 유사도
18.2 AI 활용

향후 AI 또는 임베딩 기반 상품 매칭을 사용할 수 있다.

그러나 AI 결과만으로 동일 상품을 확정하지 않는다.

가능한 경우:

규칙 기반 매칭
        +
구조화된 스펙 비교
        +
AI 유사도

를 결합한다.

19. 상품명 정규화

판매처마다 상품명 표현 방식이 다를 수 있다.

예:

ASUS TUF RTX 5070 Ti OC
ASUS TUF Gaming RTX5070Ti OC
ASUS TUF GAMING GeForce RTX 5070 Ti OC

따라서 다음 정규화 과정을 고려한다.

원본 상품명
    ↓
문자 정규화
    ↓
브랜드 추출
    ↓
GPU 모델 추출
    ↓
Board Partner 추출
    ↓
모델 번호 추출
    ↓
주요 스펙 추출
    ↓
표준 Product 생성
20. 데이터 출처

가격 데이터에는 가능한 경우
데이터 출처를 기록한다.

예상 필드:

source
source_url
seller
collected_at

이를 통해 잘못된 데이터가 발견되었을 때
어디에서 수집된 것인지 추적할 수 있어야 한다.

21. 원본 데이터와 정제 데이터

가능한 경우 다음 과정을 따른다.

Raw Data
    ↓
Cleaning
    ↓
Normalization
    ↓
Structured Data
    ↓
Analytics

원본 데이터는 가능한 경우 보존한다.

가공 과정에서 원본 데이터를 직접 덮어쓰지 않는다.

22. 데이터 품질 검증

수집 데이터는 다음 검증을 수행한다.

필수 검증
상품명 존재 여부
판매처 존재 여부
가격이 숫자인지 확인
가격이 0보다 큰지 확인
URL 확인
수집 시간 확인
추가 검증
비정상적으로 높은 가격
비정상적으로 낮은 가격
중복 상품
중복 가격 기록
품절 상품
판매 종료 상품
23. 특수 가격 상황

다음 상태는 일반 가격과 구분한다.

품절
판매 종료
가격 미표시
회원 전용 가격
카드 할인
쿠폰 적용 가격
옵션별 가격
배송비 별도
해외 배송
예약 판매
24. 데이터 시각화

GPU 가격 데이터는 향후 다음과 같이 시각화한다.

가격 변동
Line Chart
판매처 가격 비교
Bar Chart
가격 분포
Histogram
제품 비교
Comparison Chart
25. AI 분석

GPU Data Model은 향후 AI 분석의 기반 데이터가 된다.

AI가 활용할 수 있는 데이터:

현재 가격
과거 가격
평균 가격
최저 가격
가격 변동률
가격 추세
판매처
GPU Model
Board Partner
제품 스펙

이를 기반으로:

가격 상태 분석
가성비 분석
구매 타이밍 분석
상품 비교
가격 하락 가능성 분석

등을 구현할 수 있다.

26. 구매 적정성

초기에는 설명 가능한 규칙 기반 시스템을 사용한다.

예:

BUY

현재 가격이 최근 평균보다 낮고
최근 최저가에 가까운 경우

WAIT

현재 가격이 평균 가격과 비슷한 경우

AVOID

현재 가격이 최근 평균보다 높고
최근 가격이 하락 추세인 경우

실제 점수 계산 방식은
가격 데이터 확보 후 별도 설계한다.

27. 데이터 관계 개념도
GPU Vendor
     │
     └── 1:N
          │
       GPU Family
          │
          └── 1:N
               │
            GPU Model
               │
               └── 1:N
                    │
                  Product
                    │
             ┌──────┴──────┐
             │             │
             ▼             ▼
       Board Partner   Product Spec
             │
             ▼
       Seller Listing
             │
             ▼
       Price Snapshot
             │
             ▼
        Price History
28. 핵심 엔티티 후보

현재 단계의 핵심 엔티티 후보:

GPU Vendor
GPU Family
GPU Model
Board Partner
Product
Product Specification
Seller
Seller Listing
Price Snapshot

향후 추가 가능:

Category
Product Image
Product Attribute
Coupon
Price Analysis
AI Analysis
Price Alert
User
Favorite
29. MVP 데이터 범위

MVP에서는 다음 데이터부터 구현한다.

GPU Vendor
GPU Family
GPU Model
Board Partner
Product
Seller
Seller Listing
Price Snapshot

충분한 가격 데이터가 축적된 이후:

Price Analysis
AI Analysis
Price Alert

등을 추가한다.

30. 다른 카테고리 확장

PriceBrain은 GPU에서 시작하지만
향후 다른 상품 카테고리로 확장할 수 있어야 한다.

예:

GPU
 └── GPU Model
      └── Product
           └── Seller
                └── Price


Monitor
 └── Monitor Model
      └── Product
           └── Seller
                └── Price


Laptop
 └── Laptop Model
      └── Product
           └── Seller
                └── Price

따라서 DB 설계 시 GPU에 지나치게 종속적인 구조는 피한다.

31. 설계 원칙
원칙 1

GPU Model과 실제 Product를 분리한다.

원칙 2

Product와 Seller를 분리한다.

원칙 3

현재 가격과 가격 이력을 분리한다.

원칙 4

상품명만으로 동일 상품을 확정하지 않는다.

원칙 5

가격 데이터에는 수집 시간을 기록한다.

원칙 6

데이터 출처를 추적할 수 있어야 한다.

원칙 7

AI보다 데이터 품질을 우선한다.

원칙 8

분석 결과는 가능한 한 설명 가능해야 한다.

원칙 9

원본 데이터와 정제 데이터를 가능한 경우 분리한다.

원칙 10

향후 다른 상품 카테고리로 확장할 수 있는 구조를 유지한다.

32. 현재 결정 사항
| 항목 | 결정 |
|------|------|
| 첫 번째 카테고리 | GPU / Graphics Card |
| GPU Vendor | NVIDIA / AMD |
| 초기 Family | GeForce RTX / Radeon RX |
| **데이터베이스 (현행)** | **Cloud Firestore** (**05** Schema SSOT) |
| Canonical Product Collection | **`products`** |
| 가격 이력 | `listings/{id}/price_history` |
| 가격 시각화 | 지원 |
| 초기 구매 적정성 | 규칙 기반 |
| AI 가격 분석 | 향후 |
| AI 상품 매칭 | 향후 |
| 다른 카테고리 확장 | 지원 고려 |
33. 미결정 사항

다음 단계에서 결정한다.

실제 데이터 수집 대상
공식 API 사용 가능 여부
크롤링 가능 여부
데이터 수집 주기
GPU 모델 데이터 출처
Product 데이터 출처
상품 이미지 데이터 출처
실제 상품 식별 방법
동일 상품 판별 기준
배송비 처리 방식
할인 가격 처리 방식
품절 상품 처리 방식
가격 분석 알고리즘
구매 점수 계산 방식
Cloud Run 도입 시점 (Backend)
# 34. Firestore Collection 매핑 (05 SSOT 참조)

02 MVP 엔티티 ↔ Firestore (**05 §8** 와 1:1):

| 02 엔티티 | Firestore Collection / Path |
|-----------|----------------------------|
| GPU Vendor | `gpu_vendors` |
| GPU Family | `gpu_families` |
| GPU Model | `gpu_models` |
| Board Partner | `board_partners` |
| **Product (Canonical)** | **`products`** |
| Product Specification | `products` 필드 (MVP embedded) |
| Seller | `sellers` |
| **Seller Listing** | **`listings`** |
| Price Snapshot | `listings/{id}/price_history` (1 doc) |
| Price History | `listings/{id}/price_history` |

Phase 2+: `users/{uid}`, `users/{uid}/favorites`

**`canonical_products` Collection 사용 안 함.**

# 35. 다음 단계

```text
02 GPU Domain (본 문서)
        ↓
03 Data Source Research
        ↓
06 / 06-1 수집·검증
        ↓
05 Firestore Schema (SSOT)
        ↓
07 → 08 → 09 구현
```

데이터 수집 대상은 API·약관·robots.txt 확인 후 결정한다.

---

# Appendix A. Design History (Non-SSOT)

### A.1 PostgreSQL / ERD (v0.1)

v0.1 §34는 PostgreSQL Schema·ERD 순서를 가정. **현행 DB SSOT: Cloud Firestore (`05`).**

### A.2 Price Snapshot vs Price History

02 도메인상 별도 엔티티. Firestore MVP는 **`price_history` subcollection** (**05 §4**).