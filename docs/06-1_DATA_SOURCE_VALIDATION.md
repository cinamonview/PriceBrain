# PriceBrain
# Data Source Validation

- 문서 버전: v0.2
- 문서 상태: Draft (Firestore Collection Mapping Gate — Phase 2)
- Schema SSOT: `docs/05_FIREBASE_DATA_STRUCTURE.md`
- 프로젝트명: PriceBrain
- 대상 카테고리: GPU / Graphics Card
- 검증 목적: 실제 외부 데이터가 PriceBrain의 데이터 모델 및 크롤링 아키텍처에 적합한지 검증
- 작성일: 2026-08-19

---

# 1. 문서 목적

본 문서는 PriceBrain에서 실제로 사용할 수 있는
외부 데이터 소스를 조사하고 검증하기 위한 문서이다.

06_DATA_SOURCE_AND_CRAWLING_ARCHITECTURE.md에서 정의한
데이터 수집 구조가 실제 데이터 환경에서도
정상적으로 동작할 수 있는지 확인한다.

본 문서는 다음 단계로 넘어가기 **전** Gate C 전 검증이다.

```text
06-1 샘플 데이터 검증
        ↓
05 Collection Mapping Gate (본 문서 §27–§28)
        ↓
07 Crawler MVP (Raw)
        ↓
08 Pipeline → 09 Firestore
```

**현행 DB:** Cloud Firestore (**05**). PostgreSQL/ERD 확정은 **Design History** (Appendix A).

2. 검증의 핵심 질문

본 검증에서는 다음 질문에 답하는 것을 목표로 한다.

1. 실제 GPU 상품 데이터를 수집할 수 있는가?


2. 상품명 정보를 가져올 수 있는가?


3. 제조사 정보를 가져올 수 있는가?


4. GPU 모델 정보를 식별할 수 있는가?


5. VRAM 정보를 가져올 수 있는가?


6. Part Number 또는 SKU를 확보할 수 있는가?


7. 판매 가격을 가져올 수 있는가?


8. 배송비를 확인할 수 있는가?


9. 판매처를 식별할 수 있는가?


10. 재고 여부를 확인할 수 있는가?


11. 상품 URL을 확보할 수 있는가?


12. 동일 상품을 여러 판매처에서 식별할 수 있는가?


13. 가격 이력을 장기적으로 축적할 수 있는가?


14. 현재 **05 Firestore Collection Schema**에 매핑·저장할 수 있는가?
3. 검증 범위

초기 검증 대상은 GPU / Graphics Card로 제한한다.

검증 대상 제품군:

NVIDIA GeForce RTX Series


AMD Radeon RX Series

초기에는 모든 GPU를 조사하지 않는다.

대표적인 제품을 선정하여
데이터 구조를 검증한다.

4. 테스트 상품 선정

초기 테스트 상품은 다음 기준으로 선정한다.

1. 최신 GPU
2. 판매량이 높은 GPU
3. 다양한 제조사 제품이 존재하는 GPU
4. 여러 판매처에서 판매되는 GPU
5. 상품명 표기가 다양한 GPU

예시:

RTX 5090
RTX 5080
RTX 5070 Ti
RTX 5070
RTX 5060 Ti


RX 9070 XT
RX 9070
RX 9060 XT

실제 테스트 상품은
데이터 소스 조사 후 최종 확정한다.

5. 테스트 상품 단위

GPU 제품군과 실제 판매 상품을 구분한다.

예:

GPU Family
    ↓
RTX 5070 Ti


Product
    ↓
ASUS TUF Gaming RTX 5070 Ti OC 16GB


Seller Listing
    ↓
판매처 A에서 판매되는 해당 상품


Price Snapshot
    ↓
2026-08-19 가격

PriceBrain에서는 이 계층 구조를 유지한다.

6. 데이터 소스 분류

검증 대상 데이터 소스는 다음과 같이 분류한다.

A. 가격비교 사이트


B. 대형 온라인 쇼핑몰


C. 오픈마켓


D. PC 전문 쇼핑몰


E. 제조사 공식 사이트


F. 공식 API


G. 기타 공개 데이터

각 데이터 소스의 실제 사용 가능성을 조사한다.

7. 데이터 소스 검증 기준

각 데이터 소스는 다음 항목을 평가한다.

항목	평가 내용
접근 가능성	정상적인 접근이 가능한가
API	공식 API가 존재하는가
상품 검색	키워드 검색이 가능한가
상품 상세	상세 페이지 접근이 가능한가
가격	판매 가격을 확인할 수 있는가
배송비	배송비를 확인할 수 있는가
재고	재고 상태를 확인할 수 있는가
판매처	판매자를 확인할 수 있는가
상품번호	SKU / Product ID 등이 존재하는가
Part Number	제조사 Part Number가 존재하는가
사양	GPU / VRAM 등의 정보를 확인할 수 있는가
URL	상품 URL을 확보할 수 있는가
이미지	상품 이미지 URL을 확보할 수 있는가
동적 렌더링	JavaScript가 필요한가
접근 제한	CAPTCHA / Rate Limit 등이 있는가
robots.txt	크롤링 정책을 확인할 수 있는가
이용약관	자동화 접근 정책을 확인해야 하는가
안정성	페이지 구조가 안정적인가
8. 데이터 소스 평가 점수

데이터 소스 비교를 위해
다음과 같은 점수 체계를 사용한다.

5 = 매우 좋음
4 = 좋음
3 = 보통
2 = 제한적
1 = 매우 제한적
0 = 사용 불가

단순 점수만으로
사용 가능 여부를 결정하지 않는다.

법적 / 정책적 제한이 있는 경우
별도로 기록한다.

9. 핵심 데이터 필드

PriceBrain의 핵심 데이터 필드는 다음과 같다.

source
product_name
brand
gpu_model
vram
memory_type
part_number
sku
seller
price
shipping_fee
discount
stock
product_url
image_url
collected_at

실제 데이터 소스에서
각 필드를 확보할 수 있는지 검증한다.

10. 데이터 확보 가능성 Matrix

각 데이터 소스별로 다음 표를 작성한다.

Field	Source A	Source B	Source C
product_name	TBD	TBD	TBD
brand	TBD	TBD	TBD
gpu_model	TBD	TBD	TBD
vram	TBD	TBD	TBD
memory_type	TBD	TBD	TBD
part_number	TBD	TBD	TBD
sku	TBD	TBD	TBD
seller	TBD	TBD	TBD
price	TBD	TBD	TBD
shipping_fee	TBD	TBD	TBD
discount	TBD	TBD	TBD
stock	TBD	TBD	TBD
product_url	TBD	TBD	TBD
image_url	TBD	TBD	TBD
collected_at	O	O	O

표의 값:

O = 확보 가능
△ = 부분적으로 가능
X = 확보 어려움
TBD = 조사 필요
11. 상품명 검증

동일 상품이 사이트마다
어떻게 표현되는지 조사한다.

예:

ASUS TUF Gaming GeForce RTX 5070 Ti OC 16GB


ASUS TUF RTX5070TI O16G


ASUS TUF Gaming RTX 5070 Ti 16GB OC


TUF-RTX5070TI-O16G

이들이 실제로 동일 상품인지
확인한다.

상품명만으로 판단하지 않는다.

12. 상품 식별자 검증

상품 매칭을 위해
다음 식별자의 존재 여부를 조사한다.

우선순위:

Manufacturer Part Number
↓
Manufacturer Product Code
↓
SKU
↓
Model Number
↓
Product ID
↓
상품명

가능한 경우
제조사 Part Number를
가장 중요한 식별자로 사용한다.

13. Product Matching 검증

실제 여러 사이트의 상품 데이터를 비교하여
동일 상품을 식별할 수 있는지 검증한다.

예:

Source A
ASUS TUF Gaming RTX 5070 Ti OC 16GB


Source B
ASUS TUF RTX5070TI O16G


Source C
TUF-RTX5070TI-O16G

↓

동일 Product

가 가능한지 확인한다.

14. 잘못된 Matching 검증

다음과 같은 상품은
동일 상품으로 잘못 판단하지 않아야 한다.

예:

ASUS TUF RTX 5070 Ti 16GB


ASUS TUF RTX 5070 Ti OC 16GB

또는:

RTX 5070 Ti 16GB


RTX 5070 Ti 12GB

또는:

새 제품


중고 제품

따라서 Product Matching은
단순 상품명 비교만으로 결정하지 않는다.

15. 가격 데이터 검증

가격 필드가 실제로
어떤 형태로 제공되는지 확인한다.

예:

1,099,000원


1099000


₩1,099,000


1,099,000

PriceBrain 내부에서는:

1099000

형태로 정규화한다.

16. 배송비 검증

배송비를 별도로 확인한다.

예:

무료배송
3,000원
5,000원
조건부 무료
판매자 문의

내부 데이터:

shipping_fee

로 정규화한다.

확인할 수 없는 경우
NULL 또는 UNKNOWN을 사용한다.

17. 할인 데이터 검증

가격에 다음 할인 조건이 존재하는지 조사한다.

즉시 할인
쿠폰
카드 할인
회원 할인
앱 할인
적립금

할인 조건이 사용자에게
특정 조건을 요구하는 경우
일반 판매 가격과 분리한다.

18. 최종 구매 가격 검증

PriceBrain은 단순 표시 가격과
실제 구매 가격을 구분할 필요가 있다.

예:

상품 가격
1,099,000원


배송비
0원


쿠폰
-20,000원


카드 할인
-30,000원

이 경우:

표시 가격
1,099,000원


조건부 최종 가격
1,049,000원

으로 구분할 수 있다.

초기 MVP에서는
상품 가격 + 배송비를 우선 사용한다.

19. 재고 데이터 검증

사이트에서 다음 상태를
어떻게 표현하는지 조사한다.

판매중
재고 있음
품절
일시품절
예약판매
판매종료

PriceBrain 내부에서는
가능한 경우 다음과 같이 통일한다.

IN_STOCK
OUT_OF_STOCK
PREORDER
DISCONTINUED
UNKNOWN
20. 판매처 검증

판매처가 다음 중 어디에 해당하는지 확인한다.

공식 판매처
대형 쇼핑몰
전문 쇼핑몰
오픈마켓 판매자
개인 판매자

판매처의 유형도
향후 가격 신뢰도 분석에 활용할 수 있다.

21. URL 검증

각 상품 데이터에는
가능한 경우 원본 URL을 저장한다.

예:

source_url

URL은 다음 목적으로 사용한다.

상품 상세 페이지 이동
데이터 출처 확인
문제 발생 시 원본 검증

URL 구조가 지속적으로 변경되는지도 조사한다.

22. 이미지 데이터 검증

상품 이미지 URL을
확보할 수 있는지 조사한다.

이미지는 초기 MVP에서
필수 데이터로 취급하지 않는다.

다만 Frontend 상품 카드에서
사용할 가능성이 있으므로
확보 가능 여부를 기록한다.

23. 가격 Snapshot 검증

동일 상품을 시간에 따라
여러 번 수집할 수 있는지 검증한다.

예:

2026-08-19 09:00
1,099,000


2026-08-19 13:00
1,089,000


2026-08-19 18:00
1,079,000

이 데이터가 축적되면:

Price Snapshot

으로 저장할 수 있다.

24. 가격변동 그래프 검증

Price Snapshot이 정상적으로 축적되면
다음 데이터를 생성할 수 있어야 한다.

날짜
가격

예:

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

이를 Frontend에서
Line Chart 등으로 시각화한다.

25. 데이터 분석 가능성 검증

수집 데이터만으로
다음 분석이 가능한지 확인한다.

최저가
최고가
평균가
중앙값
가격 변동률
최근 가격 추세
최근 7일 가격
최근 30일 가격
현재 가격의 위치

추후:

가격 예측
구매 적정 시점
가격 하락 가능성

등으로 확장한다.

26. 데이터 품질 검증

수집 데이터에 다음 문제가
발생하는지 확인한다.

상품명 누락
가격 누락
잘못된 가격
중복 상품
중복 판매처
잘못된 URL
품절 상품
잘못된 상품 매칭

문제 데이터를
어떻게 처리할지도 기록한다.

27. 05 Collection Mapping Gate

실제 수집 샘플을 **05 Firestore Collection**에 매핑한다 (**ERD 대체**).

```text
External Sample
      ↓
gpu_models / products / sellers / listings / price_history
```

Gate Pass 조건: **05 §8** 02 엔티티와 충돌 없음, 필수 Field 누락 문서화.

28. Collection Mapping Table (05 SSOT)

| External Field | 05 Collection | 05 Field | Required |
|----------------|---------------|----------|----------|
| brand | `products` | `brand`, `board_partner_id` | O |
| product_name (raw) | `listings` | `raw_product_name` | O |
| normalized name | `products`, `listings` | `normalized_product_name` | O |
| gpu_model | `gpu_models`, `products` | `gpu_model_id` | O |
| vram | `products` | `vram_gb` | O |
| part_number | `products` | `manufacturer_part_number` | △ |
| seller | `sellers` | `seller_name` | O |
| price | `listings` | `current_price` | O |
| price (history) | `listings/.../price_history` | `price` | O (on change) |
| product_url | `listings` | `product_url` | O |
| mall | `listings`, `malls` | `mall_id` | O |
| external product id | `listings` | `external_product_id`, doc ID | O |
| collected_at | `listings`, `price_history` | `crawled_at` | O |

**Canonical Product:** `products` Collection (**`canonical_products` 사용 안 함**).

실제 SSG 샘플 검증 후 누락 Field는 **05** 갱신 Proposal (Phase 1 Gate 이후 변경 절차).

29. NULL 허용 검증

실제 데이터에서
누락이 자주 발생하는 필드는
NULL을 허용할 필요가 있다.

예:

part_number
shipping_fee
discount
memory_type
image_url

반대로 다음은
가능하면 필수로 유지한다.

product_name
seller
price
product_url
collected_at
30. 실제 샘플 데이터 확보

검증을 위해
각 데이터 소스에서
실제 상품 데이터를 확보한다.

최소:

3개 이상의 데이터 소스

각 소스:

5개 이상의 상품

가능하면:

10개 이상의 상품

을 확보한다.

31. 최소 검증 데이터셋

MVP 검증용으로
다음 규모를 권장한다.

3개 데이터 소스
×
10개 GPU 상품
=
30개 상품 데이터

이 정도의 작은 데이터셋으로
먼저 전체 Pipeline을 검증한다.

32. 검증용 CSV

초기에는 **Raw JSON / 06-1 샘플**로 검증하고, Firestore persist는 **09** Emulator 테스트에서 수행한다.

먼저 CSV 형태로
검증 데이터를 관리한다.

예:

validation/
├── raw/
│   ├── source_a.csv
│   ├── source_b.csv
│   └── source_c.csv
│
└── normalized/
    └── gpu_products_validation.csv
33. Raw CSV

Raw CSV는
가능한 한 원본 데이터를 보존한다.

예:

source,original_product_name,original_price,seller,url,collected_at

원본 값은
임의로 수정하지 않는다.

34. Normalized CSV

정규화 데이터:

source,brand,gpu_model,product_name,part_number,seller,price,shipping_fee,stock_status,url,collected_at

형태로 통일한다.

35. 검증용 데이터 예시

예:

source,brand,gpu_model,product_name,part_number,seller,price,shipping_fee,stock_status
source_a,ASUS,RTX 5070 Ti,ASUS TUF RTX 5070 Ti OC,PART001,판매처A,1099000,0,IN_STOCK
source_b,ASUS,RTX 5070 Ti,ASUS TUF RTX5070TI O16G,PART001,판매처B,1129000,3000,IN_STOCK
source_c,ASUS,RTX 5070 Ti,TUF Gaming RTX 5070 Ti OC,PART001,판매처C,1089000,0,IN_STOCK

위 데이터는
구조 예시일 뿐이며
실제 검증 결과로 교체한다.

36. Product Matching 검증 결과

각 상품에 대해
다음 결과를 기록한다.

source_product
matched_product
matching_method
confidence
review_required

예:

Source A
↓
Product #1001
↓
PART NUMBER MATCH
↓
confidence = 1.0
↓
review_required = false
37. Matching 테스트 케이스

최소한 다음 케이스를 테스트한다.

Case 1
완전히 동일한 Part Number


Case 2
상품명만 다른 동일 상품


Case 3
OC 버전과 일반 버전


Case 4
VRAM이 다른 제품


Case 5
중고와 신품


Case 6
병행수입과 공식 유통


Case 7
상품명이 매우 유사하지만 다른 제품
38. 가격 비교 검증

동일 상품으로 매칭된 상품을 대상으로
판매처별 가격을 비교한다.

예:

판매처 A
1,099,000


판매처 B
1,129,000


판매처 C
1,089,000

↓

최저가
1,089,000

단, 배송비와 조건부 할인 등을
함께 고려한다.

39. 최저가 판단 규칙

MVP에서는:

상품 동일성
+
재고
+
상품 가격
+
배송비

를 기준으로
실질적인 최저가를 계산한다.

조건부 할인은
별도의 가격 정보로 표시한다.

40. 데이터 신뢰도 검증

각 데이터 소스의
신뢰도를 평가한다.

예:

공식 API
→ HIGH


공식 판매처
→ HIGH


대형 쇼핑몰
→ HIGH


오픈마켓
→ MEDIUM


불확실한 데이터
→ LOW

이 값은 향후
AI 가격 분석에 활용할 수 있다.

41. 크롤링 가능성 검증

각 사이트에 대해
다음 항목을 조사한다.

robots.txt
이용약관
API
Rate Limit
로그인 필요 여부
CAPTCHA
동적 렌더링
검색 URL
상품 상세 URL

결과:

AVAILABLE
LIMITED
NOT_RECOMMENDED
UNKNOWN

으로 분류한다.

42. 법적 / 정책적 검증

데이터 수집 전에
각 사이트의 정책을 확인한다.

확인 대상:

robots.txt
Terms of Service
API Terms
Data Usage Policy

접근 제한을
우회하지 않는다.

특히:

CAPTCHA 우회
IP 차단 우회
로그인 제한 우회

등은 구현하지 않는다.

43. 동적 데이터 검증

상품 가격이
HTML에 직접 존재하는지 확인한다.

HTML
↓
가격 존재

또는:

HTML
↓
JavaScript
↓
API
↓
가격

구조인지 확인한다.

후자의 경우
내부 API 사용이 허용되는지
별도로 확인한다.

44. 데이터 변경 대응 검증

같은 URL에서
시간이 지나면서
상품 정보 구조가 변경될 수 있는지 확인한다.

예:

상품명 변경
가격 변경
재고 변경
페이지 구조 변경

Collector / Parser를
분리하는 것이 적절한지 검증한다.

45. 검증 성공 조건

다음 조건을 만족하면
데이터 소스를 MVP에 사용할 수 있다고 판단한다.

1. 상품 검색 가능


2. 상품 정보 확보 가능


3. 가격 확보 가능


4. 판매처 식별 가능


5. 상품 URL 확보 가능


6. 동일 상품 식별 가능


7. 가격 Snapshot 저장 가능


8. **05 Firestore Collection** 구조에 매핑 가능


9. 데이터 품질이 허용 수준 이상


10. 정책적 문제가 확인되지 않음
46. 검증 실패 조건

다음 조건에 해당하면
해당 데이터 소스를 MVP에서 제외하거나
사용 방식을 재검토한다.

가격을 안정적으로 확보할 수 없음


상품 식별이 불가능함


자동 접근이 제한됨


데이터 구조가 지나치게 불안정함


필요한 핵심 필드가 지속적으로 누락됨


정책상 자동 수집이 허용되지 않음
47. 최종 데이터 소스 평가표
Source	API	Product	Price	Seller	SKU/PN	Stock	URL	Crawl	Policy	Score	Decision
Source A	TBD	TBD	TBD	TBD	TBD	TBD	O	TBD	TBD	TBD	TBD
Source B	TBD	TBD	TBD	TBD	TBD	TBD	O	TBD	TBD	TBD	TBD
Source C	TBD	TBD	TBD	TBD	TBD	TBD	O	TBD	TBD	TBD	TBD
48. 검증 결과 기록

실제 조사 결과는
다음 형식으로 기록한다.

Source A
사이트:
URL:


API:
YES / NO


상품 검색:
YES / NO


가격:
YES / NO


배송비:
YES / NO


판매처:
YES / NO


SKU:
YES / NO


Part Number:
YES / NO


재고:
YES / NO


동적 렌더링:
YES / NO


robots.txt:
확인 결과


이용약관:
확인 결과


크롤링 가능성:
AVAILABLE / LIMITED / NOT_RECOMMENDED


평가:
★★★★★


결론:
MVP 사용 / 보류 / 제외
49. 검증 결과에 따른 Schema 수정

매핑 Gap 발견 시 **05_FIREBASE_DATA_STRUCTURE.md** (Schema SSOT) 갱신 Proposal. **04** 원칙·**08 §26.1**·**09** 추적표 연쇄 검토.

예:

실제 데이터에서
shipping_fee가 항상 존재
↓
필수 필드 검토


실제 데이터에서
part_number가 자주 누락
↓
NULL 허용


실제 데이터에서
seller가 상품마다 다름
↓
Seller Listing 구조 유지

Collection Mapping은 검증 결과를 반영하여 **05**에서 Final 관리한다.

50. Firestore Schema Gate 조건

```text
실제 데이터 소스 확인
        ↓
샘플 데이터 확보
        ↓
§28 Collection Mapping
        ↓
Product Matching 테스트 (08)
        ↓
가격 / price_history 테스트 (09 Emulator)
        ↓
05 Schema 확정 (변경 시)
        ↓
Gate B Pass → Crawler MVP
```

51. 검증 완료 후 다음 단계

```text
06-1 Validation Pass
        ↓
07 Crawler / Parser (Raw)
        ↓
08 Pipeline
        ↓
09 Firestore Repository
        ↓
11 Rules / CRUD 테스트 (Emulator)
```

순서로 진행한다.

52. 최종 검증 목표

PriceBrain의 데이터 수집 구조는
단순히 "크롤링이 된다"는 것을
목표로 하지 않는다.

최종 목표는:

실제 상품 발견
        ↓
상품 식별
        ↓
판매처 식별
        ↓
가격 수집
        ↓
가격 정규화
        ↓
동일 상품 매칭
        ↓
가격 이력 저장
        ↓
가격 분석
        ↓
가격 시각화
        ↓
AI 구매 타이밍 분석

전체 Pipeline이 실제 데이터로
연결되는 것을 검증하는 것이다.

53. 핵심 원칙

PriceBrain은 수집 가능한 데이터를 기준으로
데이터베이스를 설계한다.

데이터베이스 설계에 맞춰
실제 데이터를 억지로 맞추지 않는다.

54. 개발헌법과의 관계

본 문서는 PriceBrain 개발헌법의
다음 원칙을 따른다.

데이터를 추측하지 않는다.


실제 데이터를 확인한다.


수집할 수 없는 데이터는
필수 데이터로 설계하지 않는다.


검증되지 않은 구조를
최종 아키텍처로 확정하지 않는다.


크롤링 정책을 우회하지 않는다.


원본 데이터와 정규화 데이터를
가능한 한 분리한다.
55. 문서 상태

현재 상태:

DRAFT

실제 데이터 소스 조사를 완료한 후:

DRAFT
↓
VALIDATION
↓
REVIEW
↓
APPROVED

상태로 변경한다.

---

# Appendix A. Design History (Non-SSOT)

### A.1 PostgreSQL / ERD (v0.1)

v0.1은 ERD Mapping Table (relational `products`, `price_snapshots`, `seller_listings` 등) 및 PostgreSQL 구축 Gate를 사용했다.

**현행:** **05 §8** Collection 매핑 + **§28** 본 문서 Gate. persist: **09** Admin SDK.

### A.2 `canonical_products`

과거 ERD/RTDB에서 Canonical node/table명으로 검토. **현행 Collection: `products` only.**