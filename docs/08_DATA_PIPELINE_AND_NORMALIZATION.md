# 08. Data Pipeline & Normalization

Project: PriceBrain  
Document: Data Pipeline & Normalization  
Version: 1.0  
Status: Final  
작성일: 2026-08-19

---

## 1. 문서 목적

본 문서는 PriceBrain 크롤링 시스템에서 수집된 원본 상품 데이터를 실제 서비스에서 사용할 수 있는 표준 데이터로 변환하기 위한 Data Pipeline 및 Normalization 설계를 정의한다.

07번 문서에서는 쇼핑몰에서 상품 데이터를 수집하는 Crawling Implementation을 정의하였다.

본 문서는 그 다음 단계인 다음 과정을 구체적으로 정의한다.

```text
Raw Crawling Data
        ↓
Data Cleaning
        ↓
Data Normalization
        ↓
GPU Information Extraction
        ↓
Product Identity 생성
        ↓
Duplicate Detection
        ↓
Data Validation
        ↓
Canonical Product
        ↓
Database 저장

본 문서의 최종 목표는 서로 다른 쇼핑몰에서 수집된 동일 상품을 하나의 표준 상품으로 통합하고, 가격 비교 및 가격 분석에 사용할 수 있는 데이터 구조를 만드는 것이다.

2. Data Pipeline Overview

PriceBrain의 전체 데이터 처리 흐름은 다음과 같다.

                  Shopping Mall
                       │
                       ↓
                 Web Crawler
                       │
                       ↓
               Raw Product Data
                       │
                       ↓
                Data Cleaning
                       │
                       ↓
              Data Normalization
                       │
                       ↓
             GPU Information Parser
                       │
                       ↓
              Product Identification
                       │
                       ↓
              Duplicate Detection
                       │
                       ↓
                 Data Validation
                       │
                       ↓
             Canonical Product Data
                       │
              ┌────────┴────────┐
              ↓                 ↓
        Product Table      Price History
              │                 │
              └────────┬────────┘
                       ↓
                    Database

각 단계는 독립적인 책임을 가지도록 구성한다.

3. Raw Data와 Normalized Data 분리

PriceBrain은 원본 데이터와 정규화된 데이터를 분리하여 관리한다.

3.1 Raw Data

크롤러가 쇼핑몰에서 직접 수집한 데이터를 의미한다.

예:

raw_product_name
raw_price
raw_seller
raw_url
raw_image_url
mall
product_id
crawled_at

Raw Data는 향후 Parser 또는 Normalizer가 개선될 경우 다시 처리할 수 있도록 가능한 한 보존한다.

3.2 Normalized Data

Raw Data를 가공하여 PriceBrain 내부 표준 형식으로 변환한 데이터이다.

예:

product_name
brand
gpu_series
gpu_model
vram_gb
manufacturer_part_number
price
seller
mall
product_url
image_url
4. 데이터 처리 원칙

PriceBrain의 데이터 Pipeline은 다음 원칙을 따른다.

원칙 1. 원본 보존

정규화 이전의 원본 데이터를 가능한 한 유지한다.

원칙 2. 정규화 데이터 분리

원본 데이터에 직접 덮어쓰지 않고 별도의 Normalized Field를 사용한다.

원칙 3. 단계별 검증

각 단계에서 데이터 오류를 확인한다.

원칙 4. 쇼핑몰 독립성

정규화 로직은 특정 쇼핑몰의 HTML 구조에 의존하지 않도록 한다.

원칙 5. 재처리 가능성

Normalization 규칙이 변경되더라도 Raw Data를 이용하여 다시 처리할 수 있어야 한다.

5. Data Cleaning

Data Cleaning은 크롤링 과정에서 수집된 데이터를 정규화하기 전에 기본적인 오류를 제거하는 단계이다.

주요 대상은 다음과 같다.

불필요한 공백
HTML Entity
특수문자
잘못된 가격 형식
빈 문자열
잘못된 URL
중복 공백

예:

"  ZOTAC GAMING RTX 5080 16GB  "

↓

"ZOTAC GAMING RTX 5080 16GB"
6. 상품명 Cleaning

상품명은 쇼핑몰마다 표현 방식이 다르므로 기본적인 문자열 정리를 수행한다.

예:

[특가] ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB!!!

기본 Cleaning:

ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB

단, 할인 문구나 판매 문구를 무조건 삭제하지 않는다.

원본 상품명은 반드시 보존한다.

7. Price Normalization

쇼핑몰의 가격 표현은 서로 다를 수 있다.

예:

2,429,000원
2429000
₩2,429,000
2.429.000

PriceBrain 내부에서는 다음과 같이 통일한다.

Integer

예:

2,429,000원
        ↓
2429000

가격에는 문자열이나 통화기호를 저장하지 않는다.

7.1 가격 Validation

가격은 다음 조건을 검사한다.

price > 0

비정상적인 가격:

0
-100
None
문자열만 존재

등은 정상 데이터로 저장하지 않는다.

또한 비정상적으로 높은 가격이 발견되는 경우 Validation 또는 Anomaly Detection 대상으로 분류한다.

8. Seller Normalization

판매처 역시 쇼핑몰마다 표현 방식이 다를 수 있다.

예:

히트정보
HIT정보
히트 정보
HIT INFORMATION

원본 판매처 이름은 보존하고 필요한 경우 표준 판매처명을 별도로 생성한다.

raw_seller
normalized_seller

예:

raw_seller:
히트정보


normalized_seller:
히트정보

향후 판매처 관리 시스템이 구축되면 Seller ID를 추가한다.

9. Mall Normalization

쇼핑몰 이름 역시 표준화한다.

예:

SSG
신세계몰
쓱닷컴

↓

SSG

예상 내부 코드:

SSG
ELEVENST
COUPANG
GMARKET
AUCTION

쇼핑몰명은 문자열로만 관리하기보다 향후 Mall Master Table과 연결할 수 있도록 설계한다.

10. URL Normalization

상품 URL은 동일 상품이라도 Tracking Parameter가 포함될 수 있다.

예:

https://www.ssg.com/item/itemView.ssg?
itemId=1000832367906
&siteNo=6001
&salestrNo=6005
&click=itemMidArea02

가격 비교에 필요하지 않은 Tracking Parameter는 가능한 경우 제거한다.

그러나 상품 식별에 필요한 Parameter는 유지한다.

URL 처리 시 다음을 확인한다.

HTTP / HTTPS
Domain
Path
Product ID
필수 Query Parameter
Tracking Parameter
11. Image URL Normalization

대표 이미지 URL은 상품 대표 이미지를 기준으로 저장한다.

예:

https://sitem.ssgcdn.com/06/79/36/item/1000832367906_i1_500.jpg

가능한 경우 다음 정보를 관리한다.

image_url
image_width
image_height

이미지는 PriceBrain 서버에 직접 저장하지 않고 초기 MVP에서는 원본 CDN URL을 저장하는 방식을 우선한다.

12. GPU Information Extraction

PriceBrain의 핵심 기능 중 하나는 상품명에서 GPU 정보를 추출하는 것이다.

예:

HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB

↓

brand:
ZOTAC


gpu_series:
RTX


gpu_model:
RTX 5080


vram_gb:
16
13. GPU Brand 추출

주요 제조사 및 브랜드 Dictionary를 사용한다.

예:

ZOTAC
ASUS
MSI
GIGABYTE
GALAX
PALIT
PNY
COLORFUL
INNO3D
GAINWARD
SAPPHIRE
XFX
ASROCK

상품명에 포함된 브랜드 정보를 기준으로 1차 추출한다.

가능한 경우 제조사 정보 또는 상세 페이지의 구조화 데이터를 이용하여 보완한다.

14. GPU Chip / Series 추출

GPU Series는 다음과 같은 패턴을 우선 지원한다.

NVIDIA:

RTX
GTX

AMD:

RX
Radeon

Intel:

Arc

예:

RTX 5080
RTX 5070 Ti
RTX 5060
RX 9070 XT
Arc B580
15. GPU Model Normalization

동일 GPU가 서로 다른 표현으로 나타날 수 있다.

예:

RTX5080
RTX 5080
GeForce RTX 5080
지포스 RTX 5080

이를 내부 표준 형태로 변환한다.

RTX 5080

예:

GeForce RTX 5080
        ↓
RTX 5080

제조사 브랜드는 별도의 Field로 유지한다.

16. VRAM Normalization

VRAM 역시 상품명에 다양한 형태로 표시될 수 있다.

예:

16GB
16 G
16G
16기가
16GB GDDR7

PriceBrain에서는 가능한 경우 다음 형태로 통일한다.

vram_gb = 16

메모리 규격은 별도의 Field로 관리할 수 있다.

예:

vram_gb
memory_type
17. Manufacturer Part Number

가능한 경우 제조사 Part Number를 수집한다.

예:

ZT-B50800D-10P

Manufacturer Part Number는 동일 상품 판별에서 매우 높은 신뢰도를 가지는 식별자로 사용한다.

우선순위:

Manufacturer Part Number
        ↓
Product Model Number
        ↓
Normalized Product Name
        ↓
상품명 기반 추론
18. Product Identity

PriceBrain에서 가장 중요한 데이터 처리 중 하나는 동일 제품을 하나의 상품으로 통합하는 것이다.

예:

ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB


ZOTAC GAMING RTX 5080 SOLID CORE OC 16GB


ZOTAC RTX5080 SOLID CORE OC D7 16GB

위 상품들은 실제 동일 제품일 가능성이 있다.

따라서 상품명을 단순 비교하지 않는다.

19. Canonical Product

PriceBrain 내부에서 실제 동일 상품을 표현하는 표준 상품을 Canonical Product라고 정의한다.

예:

canonical_product_id


ZOTAC-RTX5080-SOLIDCORE-16GB

실제 구현에서는 제조사 Part Number가 존재하는 경우 이를 우선 사용한다.

예:

Manufacturer Part Number
        ↓
Canonical Product ID
20. Product Matching 전략

상품 매칭은 단계적으로 수행한다.

Level 1

Manufacturer Part Number 비교

동일 → 동일 상품
Level 2

Manufacturer Model Number 비교

동일 → 동일 상품 가능성 높음
Level 3

구조화된 GPU 정보 비교

Brand
GPU Model
VRAM
Memory Type
Model Name
Level 4

Normalized Product Name 비교

Level 5

AI / Similarity Matching

향후 머신러닝 또는 LLM 기반 상품 매칭을 적용할 수 있다.

21. Duplicate Detection

중복 상품은 두 가지 관점으로 관리한다.

동일 쇼핑몰 내부 중복
mall
+
product_id
여러 쇼핑몰의 동일 제품
canonical_product_id

예:

SSG
product_id = 1000832367906


11번가
product_id = 123456789


canonical_product_id
=
ZOTAC-RTX5080-SOLIDCORE-16GB
22. Data Validation

Normalization이 끝난 데이터는 DB 저장 전에 Validation을 수행한다.

필수 검증 항목:

상품 ID 존재 여부
상품명 존재 여부
가격 정상 여부
쇼핑몰 존재 여부
상품 URL 정상 여부
GPU 상품 여부
Canonical Product 생성 가능 여부

Validation 결과는 다음과 같이 분류할 수 있다.

VALID
INVALID
WARNING
23. Validation Rule 예시

예:

product_id == None
→ INVALID


product_name == None
→ INVALID


price <= 0
→ INVALID


product_url == None
→ INVALID


GPU Keyword 미검출
→ WARNING 또는 FILTERED


canonical_product_id 생성 실패
→ WARNING

모든 실패 데이터를 즉시 삭제하지 않는다.

원인 분석을 위해 실패 데이터 또는 Validation Log를 별도로 기록할 수 있도록 한다.

24. GPU Product Filtering

PriceBrain은 모든 상품을 DB에 저장하지 않고 GPU 관련 상품을 우선적으로 처리한다.

1차 Keyword:

RTX
GTX
RX
Radeon
GeForce
Arc

2차 검증:

GPU Brand Dictionary
+
GPU Model Dictionary
+
Product Information

이를 통해 다음과 같은 비-GPU 상품을 제거한다.

RTX 노트북
RTX 관련 케이블
RTX 장식품
RTX 게임
RTX 호환 부품

단순 Keyword Filtering만으로 GPU 여부를 확정하지 않는다.

25. Raw → Normalized 데이터 예시

Raw Data:

mall:
SSG


product_id:
1000832367906


product_name:
HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB


price:
2,429,000원


seller:
히트정보

Normalized Data:

mall:
SSG


product_id:
1000832367906


brand:
ZOTAC


gpu_series:
RTX


gpu_model:
RTX 5080


vram_gb:
16


product_name:
HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB


normalized_product_name:
ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB


price:
2429000


seller:
히트정보
26. Data Processing Object

애플리케이션 내부에서는 다음과 같은 구조를 기본 데이터 객체로 사용할 수 있다.

{
    "mall": "SSG",
    "product_id": "1000832367906",
    "raw_product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
    "normalized_product_name": "ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB",
    "brand": "ZOTAC",
    "gpu_series": "RTX",
    "gpu_model": "RTX 5080",
    "vram_gb": 16,
    "manufacturer_part_number": None,
    "price": 2429000,
    "seller": "히트정보",
    "product_url": "...",
    "image_url": "...",
    "crawled_at": "2026-08-19T10:00:00"
}
```

이 객체는 **08 Pipeline 출력**이며, Firestore persist는 **09 Repository**가 담당한다 (본 문서에 Repository 구현 없음).

### 26.1 Processing Object ↔ 05 Field 매핑표 (SSOT)

Pipeline `ValidatedProduct` dict 필드 → Firestore 저장 위치. Schema 상세·Type: **05 §3**.

| 08 Processing Object Field | 05 Collection | 05 Field | Transform / 비고 |
|----------------------------|---------------|----------|------------------|
| `mall` | `listings`, `sellers` | `mall_id` | code (`SSG`) — **05 §3.6** malls seed |
| `product_id` | `listings` | `external_product_id` | 쇼핑몰 ID; doc ID = `{mall_id}_{product_id}` |
| `raw_product_name` | `listings` | `raw_product_name` | 원본 보존 — **04 §5.1** |
| `normalized_product_name` | `products`, `listings` | `normalized_product_name` | denorm on listing |
| `brand` | `products` | `brand` | Board Partner명 |
| `brand` | `products` | `board_partner_id` | slug resolve → `board_partners` |
| `gpu_series` | `gpu_models` | `gpu_series` | matcher가 model doc resolve |
| `gpu_model` | `products` | `gpu_model_id` | slug (`rtx_5080`) → **05 §3.3** |
| `gpu_model` | `gpu_models` | `gpu_model` | display field on model doc |
| `vram_gb` | `products` | `vram_gb` | number |
| `manufacturer_part_number` | `products` | `manufacturer_part_number` | nullable; canonical ID 우선순위 **05 §2.1** |
| `price` | `listings` | `current_price` | KRW integer |
| `price` | `listings/{id}/price_history` | `price` | append when changed — **09** |
| `seller` | `sellers` | `seller_name`, `normalized_seller_name` | upsert → `listings.seller_id` |
| `product_url` | `listings` | `product_url` | |
| `image_url` | `listings`, `products` | `image_url` | MVP CDN URL |
| `crawled_at` | `listings` | `crawled_at`, `updated_at` | timestamp |
| `crawled_at` | `listings/{id}/price_history` | `crawled_at` | doc ID `{crawled_at_ms}` |
| (derived) | `products` | `canonical_product_id` | Document ID — matcher/validator |
| (derived) | `listings` | `product_id` | → `products` Document ID |
| (derived) | `listings` | `status`, `availability` | default `AVAILABLE` / `true` |

**Canonical Product Collection:** `products` (**`canonical_products` 사용 안 함**)

**Persist 구현:** `docs/09_FIREBASE_IMPLEMENTATION.md` §6, §9

27. Pipeline Module 구조

예상 프로젝트 구조:

Backend package root — **project.mdc**, **09 §4**

pricebrain_app/
│
├── crawler/
│   ├── base.py
│   ├── ssg.py
│   ├── elevenst.py
│   └── coupang.py
│
├── pipeline/
│   ├── cleaner.py
│   ├── normalizer.py
│   ├── gpu_parser.py
│   ├── product_matcher.py
│   └── validator.py
│
├── repository/                   # 09 SSOT (08 범위 외)
│   ├── product_repository.py
│   └── price_repository.py
│
├── models/
│   ├── product.py
│   └── price_history.py
│
└── crawler.py

각 모듈은 하나의 명확한 책임을 가진다.

28. Pipeline 실행 구조

전체 Pipeline은 다음과 같이 실행한다.

raw_data = crawler.search(keyword)


clean_data = cleaner.clean(raw_data)


normalized_data = normalizer.normalize(clean_data)


gpu_data = gpu_parser.parse(normalized_data)


matched_data = product_matcher.match(gpu_data)


validated_data = validator.validate(matched_data)

# 08 종료 — ValidatedProduct 출력. Firestore persist는 09 Repository (§29).

Parser와 Database 로직은 직접 연결하지 않는다.

29. Persistence 경계 (09 Repository)

Pipeline(08) 출력 `ValidatedProduct`의 **Firestore persist**는 **09 Repository + Admin SDK** SSOT이다. 본 문서(08)에 Repository **구현**을 두지 않는다.

```text
08 Pipeline  →  ValidatedProduct (dict)   # §26, §26.1
                    ↓
09 Repository  →  Cloud Firestore           # upsert products, listings
                    ↓
                 append price_history (on change)
```

| 역할 | SSOT |
|------|------|
| Processing Object·Field 매핑 | **08 §26.1** → **05** |
| Collection·Field·Rules | **05** |
| Repository 메서드·추적표 | **09 §6, §9** |
| Runtime read/write | **13** |

30. Price History 처리

가격 이력은 **`listings/{id}/price_history`** subcollection (**05 §4**). top-level `price_history` Collection 없음.

- 현재 가격: `listings.current_price`
- 변경 시: **09** `PriceHistoryRepository.append_if_changed` (Admin SDK only)

예시 시계열 (개념):

```text
2026-08-19 10:00  2,429,000
2026-08-19 14:00  2,399,000
2026-08-20 10:00  2,379,000
```

31. 가격 변경 감지

**08 Pipeline** 또는 **09 Repository**에서 `previous_price` 대비 `current_price` 비교.

- `price_change`, `previous_price` 필드: **05 §3.9**
- append skip when unchanged: **09 §6.3**

향후: 가격 하락 알림, 변동 그래프, 추세 분석 (Frontend read **05** + **13**).

32. Data Quality 관리

Pipeline 품질 지표 (08 책임):

- Validation Success Rate (**08 validator**)
- GPU 판별·Canonical Matching 성공률 (**08 matcher**)
- 중복률

Crawl 성공률·HTTP 오류: **07** + **09** `crawl_logs`.

33. Error Handling

Pipeline(08)에서 Parser(07)가 넘긴 Raw 단위로 오류 격리 — 하나의 상품 실패가 전체 Job을 중단하지 않음.

- Parser 오류: **07** retry / crawl_log
- Validation 실패: **08** → **09** `validation_logs`

34. Reprocessing

Raw 필드(`raw_product_name` 등, **05 listings**) 보존 시 **08 Pipeline**만 재실행 가능. **07** re-crawl 불필요.

```text
Firestore raw fields  →  New 08 Pipeline  →  09 upsert
```

35. AI 기반 Normalization 확장

Rule-based MVP: **08** `normalizer`, `gpu_parser`, `product_matcher` (**08 §35**).

AI 확장도 **08 Pipeline** 내부. **09**는 결과 dict persist만.

36. Data Pipeline과 Database의 관계

08은 **Database Schema SSOT가 아님**. Schema: **05**. 원칙: **04**.

```text
06  Crawling Architecture
07  Crawler / Parser / Raw
08  Pipeline & Normalization    ← 본 문서
09  Repository (Admin SDK)      ← persist SSOT
05  Firestore Collection Schema
```

| 계층 | 역할 |
|------|------|
| 07 | 수집 |
| 08 | 가공 |
| 09 | 저장 |

Canonical Product Collection: **`products`** (`canonical_products` 사용 안 함).

37. MVP 구현 범위

초기 MVP에서는 다음 기능만 우선 구현한다.

필수
SSG 데이터 수집
상품명 Cleaning
가격 Normalization
GPU Keyword Filtering
GPU Model 추출
Brand 추출
VRAM 추출
상품 URL 정규화
Canonical Product ID 생성
Validation
DB 저장
Price History 저장
후순위
11번가
쿠팡
G마켓
AI Product Matching
AI 상품명 정규화
가격 이상 탐지
자동 재처리
고급 데이터 품질 분석
38. MVP Processing Flow

초기 구현에서는 다음 Pipeline을 목표로 한다.

SSG Search
    ↓
Crawler
    ↓
Raw Product
    ↓
Cleaning
    ↓
Price Normalization
    ↓
GPU Filtering
    ↓
GPU Information Extraction
    ↓
Canonical Product ID
    ↓
Validation
    ↓
Product 저장
    ↓
Price History 저장

이 Pipeline이 안정적으로 동작한 이후 11번가 및 기타 쇼핑몰을 추가한다.

39. 향후 확장 Pipeline

장기적으로 다음 구조로 확장한다.

Multiple Shopping Malls
        ↓
Unified Raw Data
        ↓
Cleaning
        ↓
Normalization
        ↓
GPU Product Classification
        ↓
Entity Resolution
        ↓
Canonical Product
        ↓
Price History
        ↓
Price Analytics
        ↓
AI Price Prediction

최종적으로 PriceBrain은 단순한 크롤링 시스템이 아니라 GPU 상품 정보를 통합하는 Data Platform으로 발전한다.

40. 핵심 설계 원칙

PriceBrain Data Pipeline은 다음 원칙을 따른다.

1. Raw Data 보존

원본 데이터를 최대한 유지한다.

2. Normalization 분리

원본과 정규화 데이터를 분리한다.

3. Rule-Based First

초기에는 복잡한 AI보다 Regex, Dictionary, Keyword 기반으로 구현한다.

4. 단계별 Validation

각 Pipeline 단계에서 데이터를 검증한다.

5. Product와 Price 분리

상품 정보와 가격 이력을 서로 다른 데이터 구조로 관리한다.

6. 쇼핑몰 독립성

Normalization 로직은 특정 쇼핑몰의 HTML 구조에 의존하지 않는다.

7. 재처리 가능성

Raw Data를 이용해 새로운 정규화 규칙을 적용할 수 있어야 한다.

8. AI 확장성

향후 AI 기반 Product Matching 및 가격 분석을 적용할 수 있도록 구조를 설계한다.

41. 전체 Architecture

PriceBrain의 데이터 처리 Architecture는 다음과 같다.

                  Shopping Malls
                 /      |       \
              SSG    11번가     쿠팡
                \       |       /
                 \      |      /
                  Crawling Layer
                         ↓
                    Raw Product
                         ↓
                   Cleaning Layer
                         ↓
                 Normalization Layer
                         ↓
                GPU Parser / Filter
                         ↓
                Product Matching
                         ↓
                    Validation
                         ↓
                 Canonical Product
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
        Product Data          Price History
              │                     │
              └──────────┬──────────┘
                         ↓
                      Database
                         ↓
                    PriceBrain API
                         ↓
                  Web Application
42. 결론

08번에서는 PriceBrain에서 수집된 Raw Product Data를 실제 가격 비교 서비스에서 사용할 수 있는 표준 데이터로 변환하기 위한 Data Pipeline과 Normalization 구조를 정의하였다.

핵심적으로 다음 구조를 채택한다.

Raw Data
   ↓
Cleaning
   ↓
Normalization
   ↓
GPU Information Extraction
   ↓
Product Matching
   ↓
Validation
   ↓
Canonical Product
   ↓
Database

초기 MVP에서는 Rule-Based 방식의 데이터 정규화를 우선 적용하고, 이후 AI 기반 상품명 정규화 및 동일 상품 자동 매칭으로 확장한다.

또한 Raw Data를 보존함으로써 정규화 규칙이 변경되더라도 기존 데이터를 재처리할 수 있도록 설계한다.

07번에서 정의한 Crawling Layer와 09번에서 정의할 Database Layer 사이에 Data Pipeline Layer를 두어 각 계층의 책임을 명확하게 분리한다.

최종적으로 PriceBrain은 다음과 같은 데이터 흐름을 갖는 것을 목표로 한다.

수집
 ↓
정제
 ↓
정규화
 ↓
상품 식별
 ↓
검증
 ↓
저장
 ↓
가격 이력
 ↓
가격 분석
 ↓
AI 가격 예측

이를 통해 다양한 쇼핑몰에서 수집되는 서로 다른 형태의 GPU 상품 데이터를 하나의 표준화된 PriceBrain 데이터셋으로 통합할 수 있다.