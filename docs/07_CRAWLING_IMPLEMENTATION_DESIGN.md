# 07. Crawling Implementation Design

**Project:** PriceBrain  
**Document:** Crawling Implementation Design  
**Version:** 1.1  
**Status:** Final  
**SSOT:** Crawler / Mall Adapter / Parser / **RawProductData** (Normalizer·Validator·Repository는 **08·09**)  
**Schema 참조:** `docs/05_FIREBASE_DATA_STRUCTURE.md`  
**작성일:** 2026-08-19  
**갱신일:** 2026-08-20 (Phase 2 — 07·08·09 책임 분리)

---

# 1. 문서 목적

본 문서는 PriceBrain의 상품 가격 데이터 수집 시스템을 실제로 구현하기 위한 기술 설계를 정의한다.

06번 문서에서 정의한 데이터 소스 및 크롤링 아키텍처를 기반으로 실제 크롤러가 다음 작업을 수행할 수 있도록 구체적인 구현 방법과 처리 기준을 정의한다.

- 쇼핑몰 상품 검색 결과 수집
- 상품 기본 정보 추출 (Raw)
- 가격·판매처·URL·이미지 URL 추출 (Raw)
- **RawProductData** dict 출력
- 크롤링 실패 처리·재시도·로그 (crawl_* 생성은 **09** persist)
- 요청 제한 및 동적 페이지 대응
- 향후 쇼핑몰 Adapter 확장

**본 문서 범위 외 (08·09):** 상품명/가격 정규화, GPU 매칭, Validation, Canonical Product ID 생성, Repository, Firestore 저장, price_history append — `docs/08`, `docs/09`, `docs/13` 참조.

본 문서의 최종 목표는 개발자가 본 문서를 기준으로 실제 크롤러의 주요 모듈을 구현할 수 있는 수준의 구체적인 설계 기준을 제공하는 것이다.

---

# 2. 전체 Crawling Pipeline

### 2.1 Diagram A — 07 scope (본 문서 SSOT)

```text
[검색 키워드]
      ↓
[Mall Adapter / Crawler]
      ↓
[HTTP Request / Browser]
      ↓
[HTML / JSON Response]
      ↓
[Parser]
      ↓
[RawProductData]   ← 07 종료 지점
```

### 2.2 Diagram B — 전체 파이프라인 (참조, 구현 SSOT: 08·09·13)

```text
RawProductData
      ↓
[08 Pipeline: cleaner → normalizer → gpu_parser → matcher → validator]
      ↓
[ValidatedProduct]
      ↓
[09 Repository + Admin SDK]
      ↓
[Cloud Firestore: products, listings, price_history, crawl_*]
```

각 단계는 가능한 한 독립적으로 구성한다. 쇼핑몰 HTML 변경 시 **해당 Mall Adapter·Parser만** 수정한다.

**07 금지:** Parser/Crawler가 Firestore·Repository·Normalizer를 직접 호출하지 않는다.

07 내부 계층:

```text
Crawler (Adapter)
   ↓
Parser
   ↓
RawProductData
```
3. Crawling 대상 데이터

PriceBrain은 GPU 가격 비교를 목적으로 하기 때문에 다음과 같은 데이터를 기본 수집 대상으로 정의한다.

필드	설명	필수
product_id	쇼핑몰 내부 상품 ID	O
product_name	원본 상품명 (raw)	O
brand	Parser가 추출 가능한 경우	△
model_name	원본 문자열 (GPU 모델 추정)	△
price	쇼핑몰 표시 가격 (raw string 또는 int)	O
seller	판매처	O
mall	쇼핑몰	O
product_url	상품 상세 URL	O
image_url	대표 이미지 URL	△
availability	판매 가능 여부	△
shipping_fee	배송비	△
crawled_at	수집 시각	O

원본 데이터는 가능한 한 그대로 보존한다. `normalized_product_name` 등 정규화 필드는 **08 Pipeline**에서 생성한다 (**08 §26**, **05** Field 매핑).

4. GPU 정보 추출 (Parser Raw)

> **책임:** GPU brand/model/VRAM **정규화·매칭**은 **08** (`gpu_parser`, `product_matcher`). 07 Parser는 HTML/JSON에서 **raw 문자열**만 추출한다.

쇼핑몰 상품명에는 GPU 제조사, GPU 시리즈, 모델, VRAM 등의 정보가 포함되는 경우가 많다.

예:

ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB

다음과 같이 **08에서 정규화 가능한** 예시 (07 출력은 raw `product_name`):

brand      = ZOTAC   ← 08
gpu_series = RTX     ← 08
gpu_model  = RTX 5080 ← 08
vram       = 16GB    ← 08

그러나 쇼핑몰마다 상품명 규칙이 다르기 때문에 상품명 문자열만으로 모든 정보를 확정해서는 안 된다.

가능한 경우 다음 순서로 정보를 보완한다.

상품명
  ↓
상품 상세 페이지
  ↓
구조화 데이터(JSON-LD)
  ↓
제조사 / 모델 정보
  ↓
GPU Product Dictionary

원본 상품명(`product_name`)은 Parser가 보존한다. 정규화 결과 필드는 **08**에서 `raw_product_name` / `normalized_product_name`으로 분리 (**08 §26.1**).

5. 쇼핑몰 Adapter 구조

PriceBrain은 쇼핑몰마다 서로 다른 HTML 구조와 데이터 표현 방식을 사용하기 때문에 쇼핑몰별 Adapter 구조를 적용한다.

예상 구조:

crawler/
├── base.py
├── ssg.py
├── elevenst.py
├── coupang.py
└── parser/
    ├── product.py
    └── price.py

기본 인터페이스는 다음과 같은 형태를 가진다.

class MallCrawler:


    def search(self, keyword):
        pass


    def parse_products(self, response):
        pass


    def parse_product(self, response):
        pass

각 쇼핑몰은 공통 인터페이스를 구현한다.

예:

MallCrawler
     │
     ├── SSGCrawler
     ├── ElevenStCrawler
     ├── CoupangCrawler
     └── GmarketCrawler

이 구조를 통해 특정 쇼핑몰의 HTML 구조가 변경되더라도 다른 쇼핑몰의 크롤러에는 영향을 주지 않도록 한다.

6. SSG 크롤링 구현 기준

SSG의 실제 상품 HTML을 분석한 결과 상품 목록에서 상당한 정보를 직접 추출할 수 있다.

예시 상품:

HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB

HTML에는 다음과 같은 데이터가 존재한다.

<div class="ssgitem_unit unit_list ty_img"
     data-react-unit-id="1000832367906"
     data-react-unit-price="2429000">

따라서 다음과 같이 데이터를 추출할 수 있다.

PriceBrain 필드	HTML 위치
product_id	data-react-unit-id
price	data-react-unit-price
product_name	.ssgitem_tit_name
seller	.ssgitem_tit_brand
product_url	.ssgitem_info[href]
image_url	.ssgitem_thmb_img[src]

실제 분석된 상품의 예시는 다음과 같다.

product_id = 1000832367906
price      = 2,429,000
seller     = 히트정보

이 데이터는 2026-08-19 기준 실제 SSG 상품 HTML 구조를 분석하여 확인한 것이다.

실제 운영 크롤러에서는 HTML 구조 변경에 대비한 **Parser 수준** 예외 처리(필수 필드 누락·HTTP 오류)를 추가한다. 비즈니스 Validation은 **08 validator** (**08 §22–§23**).

7. SSG 상품 Parser 구현 예시

Python의 BeautifulSoup을 사용하는 경우 다음과 같은 형태로 구현할 수 있다.

from bs4 import BeautifulSoup




def parse_ssg_product(html):


    soup = BeautifulSoup(html, "html.parser")


    unit = soup.select_one(".ssgitem_unit")


    if not unit:
        return None


    product_id = unit.get("data-react-unit-id")
    price = unit.get("data-react-unit-price")


    name_tag = unit.select_one(".ssgitem_tit_name")
    seller_tag = unit.select_one(".ssgitem_tit_brand")
    link_tag = unit.select_one(".ssgitem_info")
    image_tag = unit.select_one(".ssgitem_thmb_img")


    return {
        "product_id": product_id,
        "price": int(price) if price else None,
        "product_name": name_tag.get_text(strip=True)
            if name_tag else None,
        "seller": seller_tag.get_text(strip=True)
            if seller_tag else None,
        "product_url": link_tag.get("href")
            if link_tag else None,
        "image_url": image_tag.get("src")
            if image_tag else None,
    }

위 코드는 설계 검증용 예시이며 실제 운영 환경에서는 다음 항목을 추가한다.

URL 정규화
가격 Validation
필수 필드 검사
HTTP 오류 처리
Parser 오류 처리
Logging
Retry 처리
8. 가격 데이터 (Parser Raw)

> **책임:** 가격 **정규화·Validation**은 **08** (`normalizer`, `validator`). 07 Parser는 쇼핑몰 표시값을 추출한다.

쇼핑몰에서 가격은 다양한 형태로 제공될 수 있다.

예:

2,429,000원
2429000
₩2,429,000
2.429.000

PriceBrain 내부 Integer 통일은 **08 normalize_price**. Parser는 `data-react-unit-price` 등 **raw 값**을 반환할 수 있다.

예시 (08 참고 — 07 코드에 포함하지 않음):

import re




def normalize_price(value):


    if value is None:
        return None


    value = str(value)


    numbers = re.sub(r"[^0-9]", "", value)


    if not numbers:
        return None


    return int(numbers)

가격 Validation(0, 음수, 비정상 큰 값)은 **08 validator** (**08 §22–§23**).

9. 상품명 (Raw vs Normalized — 08)

> **책임:** 상품명 Cleaning/Normalization은 **08 normalizer**. 07 Parser는 `product_name` (raw)만 출력.

상품명은 쇼핑몰마다 표현 방식이 다르기 때문에 Parser는 원본을 `product_name`으로 보존한다.

예:

[특가] ZOTAC GAMING RTX 5080 SOLID CORE OC 16GB

`raw_product_name` / `normalized_product_name` 분리 및 AI 확장은 **08 §6, §35** 참조.

10. Product Identity

가격 비교에서 가장 중요한 문제 중 하나는 동일 상품을 판별하는 것이다.

예:

ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB


ZOTAC RTX5080 SOLID CORE OC 16GB


ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC 16GB

위 세 상품은 실제로 동일 제품일 가능성이 있다.

따라서 단순히 product_name만으로 중복을 판단하지 않는다.

향후 **08 product_matcher**가 `canonical_product_id`를 생성하고 **05 `products`** Document ID로 저장한다 (**05 §2.1**, **09**). 07은 쇼핑몰 `product_id`만 추출한다.

가능한 경우 제조사 Part Number 또는 Manufacturer Model Number를 가장 높은 신뢰도의 식별자로 사용한다.

11. 중복 데이터 처리

동일 상품이 여러 쇼핑몰 또는 여러 판매처에서 발견될 수 있다.

따라서 다음 식별자를 구분한다.

product_id

쇼핑몰 내부에서 사용하는 상품 식별자이다.

SSG product_id
1000832367906
canonical_product_id

PriceBrain 통합 제품 slug. Firestore **`products`** Collection Document ID (**`canonical_products` Collection 사용 안 함** — **05 §1**).

예:

ZOTAC-RTX5080-SOLIDCORE-16GB

예시:

SSG product_id
1000832367906


11번가 product_id
123456789


canonical_product_id
ZOTAC-RTX5080-SOLIDCORE-16GB

이 구조를 통해 여러 쇼핑몰의 동일 제품 가격을 하나의 상품으로 비교할 수 있다.

12. 가격 이력 수집

PriceBrain의 핵심 기능 중 하나는 현재 가격뿐 아니라 가격 변화 추적이다.

따라서 상품 테이블과 가격 이력 테이블을 분리한다.

Product
    │
    ├── Price History
    ├── Price History
    └── Price History

예:

수집 시각	쇼핑몰	가격
2026-08-19 10:00	SSG	2,429,000
2026-08-19 14:00	SSG	2,399,000
2026-08-20 10:00	SSG	2,379,000

이를 통해 향후 다음 기능을 구현할 수 있다.

현재 최저가
평균 가격
가격 변동
가격 하락
가격 상승
가격 추세
가격 알림
가격 예측
13. HTTP Request 정책

크롤러는 대상 사이트에 과도한 요청을 보내지 않도록 한다.

기본 원칙:

Request
   ↓
Delay
   ↓
Request
   ↓
Delay

권장 사항:

요청 간 최소 지연시간 적용
Timeout 설정
Retry 횟수 제한
HTTP 오류 처리
HTTP 상태 코드 기록
적절한 User-Agent 사용
robots.txt 확인
서비스 이용약관 확인
사이트가 허용하는 범위 내에서 수집

운영 환경에서는 대상 사이트의 정책을 우선적으로 고려한다.

14. Retry 정책

네트워크 오류가 발생했다고 무한 재시도해서는 안 된다.

PriceBrain은 Exponential Backoff 방식을 기본 정책으로 사용한다.

예:

1차 요청 실패
      ↓
1초 대기
      ↓
2차 요청
      ↓
실패
      ↓
2초 대기
      ↓
3차 요청
      ↓
실패
      ↓
4초 대기
      ↓
최종 실패 기록

기본 대기시간 예시는 다음과 같다.

1초
2초
4초
8초

단, 최대 재시도 횟수와 최대 대기시간을 제한한다.

또한 모든 HTTP 오류를 무조건 Retry하지 않는다.

예를 들어 일시적인 네트워크 오류와 영구적인 접근 거부 오류를 구분하여 처리한다.

15. 실패 데이터 관리

크롤링 실패는 별도로 기록한다.

예:

crawl_log

필드 예시:

필드	설명
crawl_id	크롤링 작업 ID
mall	쇼핑몰
target_url	요청 URL
status	성공/실패
http_status	HTTP 상태 코드
error_type	오류 종류
error_message	오류 메시지
created_at	발생 시각

이를 통해 특정 쇼핑몰에서 갑자기 크롤링 성공률이 떨어지는 문제를 확인할 수 있다.

향후 모니터링 시스템과 연결하여 다음과 같은 기능으로 확장할 수 있다.

크롤링 성공률 감소
        ↓
오류 증가 감지
        ↓
관리자 알림
16. Parser 수준 검사 (07) vs Validation (08)

Parser가 필드를 추출했다고 **Firestore에 저장하지 않는다.** 저장은 **09 Repository** (Admin SDK).

| 단계 | 책임 | 문서 |
|------|------|------|
| HTTP/Parser 오류, 필수 raw 필드 누락 | 07 | 본 절 |
| 가격·GPU·매칭 Validation | **08 validator** | **08 §22–§23** |
| Firestore upsert / price_history | **09** | **09 §6** |

07 Parser에서 즉시 확인할 항목 (raw):

- `product_id` 존재
- `product_name` 존재
- `price` 추출 가능 (null이면 RawProductData에 포함하되 downstream 08에서 reject)

비즈니스 Validation (0, -100, GPU 비상품 등)은 **08**에서 수행한다. 실패 시 **09** `validation_logs` / `crawl_logs` (**05 §3.11–§3.12**).

17. GPU 상품 필터링 (08 연계)

1차 키워드 필터는 **07 Crawler search** 또는 **08 gpu_parser**에서 적용 가능. GPU 확정·오수집 방지 로직 SSOT: **08 §24**.

18. 동적 페이지 대응

쇼핑몰에 따라 상품 정보가 JavaScript 실행 이후 생성될 수 있다.

이 경우 단순 HTTP Request만으로 데이터를 얻지 못할 수 있다.

PriceBrain은 다음과 같은 단계적 접근을 사용한다.

Level 1
HTTP Request
+
HTML Parser
      ↓ 실패
Level 2
내부 JSON / API 응답 분석
      ↓ 실패
Level 3
Playwright / Browser Automation

가능하면 브라우저 자동화보다 HTML 또는 공식·공개 API 기반 수집을 우선한다.

브라우저 자동화는 다음과 같은 비용이 발생하기 때문이다.

서버 리소스 증가
실행 속도 저하
유지보수 비용 증가
브라우저 환경 변화에 따른 오류
차단 가능성 증가

따라서 Browser Automation은 필요한 쇼핑몰에 한해 제한적으로 사용한다.

19. Scheduler

크롤러는 정기적으로 실행할 수 있어야 한다.

예:

매시간
   ↓
GPU 상품 검색
   ↓
RawProductData 수집
   ↓
(08 Pipeline → 09 → Firestore)

초기 개발 단계에서는 수동 실행으로 시작한다.

python crawler.py

운영 단계에서는 다음 기술을 검토한다.

Cron
Celery
APScheduler
Cloud Scheduler

초기 MVP에서는 Scheduler 자체보다 안정적인 수집 파이프라인 완성에 우선순위를 둔다.

20. Crawling Architecture

```text
                    PriceBrain
                        │
                 Crawl Scheduler
                        │
           ┌────────────┼────────────┐
           ↓            ↓            ↓
     SSG Adapter  11번가 Adapter  쿠팡 Adapter
           │            │            │
         Parser       Parser       Parser
           │            │            │
           └────────────┼────────────┘
                        ↓
                 RawProductData
                        ↓
              [08 Pipeline — ref]
                        ↓
              [09 Repository — ref]
                        ↓
                 Cloud Firestore
```

각 **Adapter·Parser**는 독립 책임. Normalizer / Validator / Repository는 **07에 두지 않는다**.

21. 초기 구현 범위

프로젝트 초기 버전에서는 모든 쇼핑몰을 동시에 구현하지 않는다.

Phase 1 — SSG
검색 → Parser → **RawProductData** (07 완료)
→ 08 Pipeline → 09 Firestore (ref)
Phase 2 — 11번가
SSG
+
11번가

동일 상품 연결(`products` Document ID)은 **08 matcher + 09** (**05**). 07은 mall별 `product_id` 추출만.

Phase 3 — 다중 쇼핑몰
SSG
11번가
쿠팡
G마켓
옥션
기타 쇼핑몰

쇼핑몰 추가는 각각 독립적인 Adapter를 구현하는 방식으로 진행한다.

22. MVP 목표

07번 구현 설계의 MVP 목표는 다음과 같다.

GPU 상품 검색어로 SSG(등)에서 **RawProductData**를 안정적으로 수집하는 Crawler·Parser를 구축한다. 정규화·저장·가격 이력은 **08·09** (**13**).

MVP **07** 완료 기준:

- 상품명·가격·상품 ID·URL·이미지 URL·판매처 **raw 추출**
- RawProductData dict 스키마 (**08 §26** 입력과 호환)
- Retry·crawl_log 이벤트 생성 (persist **09**)

MVP **전체** (07+08+09): Canonical matching, Firestore 저장, price_history — **08·09** 문서 참조.

다음 기능은 MVP 이후 확장한다.

다중 쇼핑몰
자동 스케줄링
고급 모니터링
가격 알림
가격 예측
23. 향후 확장

PriceBrain은 단순한 가격 수집을 넘어 가격 분석 및 AI 기반 의사결정 시스템으로 확장할 수 있다.

가격 수집
   ↓
가격 분석
   ↓
가격 추세 분석
   ↓
적정 가격 예측
   ↓
가격 하락 알림
   ↓
구매 추천

장기적으로 AI를 이용하여 다음 기능을 구현할 수 있다.

상품명 자동 정규화
동일 제품 자동 매칭
비정상 가격 탐지
가격 변동 예측
최적 구매 시점 예측
상품별 적정 가격 산출
가격 변동 원인 분석
24. 핵심 설계 원칙

PriceBrain Crawling System은 다음 원칙을 따른다.

24.1 쇼핑몰별 Adapter 분리

특정 쇼핑몰의 HTML 변경이 다른 쇼핑몰에 영향을 주지 않도록 한다.

SSG 변경
 ↓
SSG Adapter만 수정
24.2 원본 데이터 보존

정규화하기 전 원본 상품명과 수집 원본 데이터를 가능한 한 보존한다.

이를 통해 정규화 규칙이 변경되더라도 기존 데이터를 다시 처리할 수 있도록 한다.

24.3 상품과 가격 이력 분리

상품 정보와 가격 변화를 서로 다른 데이터 구조로 관리한다.

Product
   │
   └── Price History
24.4 Parser와 DB 로직 분리

HTML Parser가 Firestore·Repository를 직접 호출하지 않는다.

```text
Crawler → Parser → RawProductData → (08 → 09 → Firestore)
```
24.5 확장 가능한 구조

초기에는 SSG 하나만 구현하더라도 향후 새로운 쇼핑몰 Adapter를 추가할 수 있도록 설계한다.

MallCrawler
    ├── SSGCrawler
    ├── ElevenStCrawler
    ├── CoupangCrawler
    └── GmarketCrawler
24.6 수집 정책 준수

크롤링 구현 시 다음을 고려한다.

robots.txt
서비스 이용약관
공개 API 정책
요청 빈도 제한
서버 부하
개인정보 및 민감정보 수집 여부

허용되는 범위 내에서 필요한 최소한의 데이터를 수집한다.

25. 구현 권장 프로젝트 구조 (07 scope)

`pricebrain_app/` — **project.mdc**

```text
pricebrain_app/
│
├── crawler/                    # 07 SSOT
│   ├── base.py
│   ├── malls/
│   │   ├── ssg.py
│   │   ├── elevenst.py
│   │   └── coupang.py
│   ├── parser/
│   │   ├── product.py
│   │   └── price.py
│   ├── retry.py
│   └── scheduler.py
│
├── pipeline/                   # 08 — 본 문서 범위 외
│   ├── cleaner.py
│   ├── normalizer.py
│   ├── gpu_parser.py
│   ├── product_matcher.py
│   └── validator.py
│
├── repository/                 # 09 — 본 문서 범위 외
│   └── ...
│
├── runner.py                   # 07→08→09 orchestration
│
└── tests/
    ├── test_ssg_parser.py
    └── test_ssg_crawler.py
```

**07 금지:** `crawler/normalizer/`, `crawler/validator.py`, `crawler/` 내 Repository·Firestore SDK.

Schema·Collection: **05**. DB 원칙: **04**. Persist: **09**.

26. 구현 완료 기준 (07 Crawler / Parser)

- SSG 검색 결과에서 GPU 상품 HTML/JSON을 수집한다.
- `product_id`, `product_name`, `price`, `seller`, `product_url`, `image_url`을 **RawProductData**로 출력한다.
- Parser가 Firestore·Repository·normalizer를 import하지 않는다.
- 네트워크 오류 시 Retry·Backoff가 동작한다.
- 크롤 실패 이벤트가 crawl_log 형식으로 기록 가능하다 (**09** persist).
- 새 Mall Adapter 추가 시 기존 Parser 변경 최소화.

**08·09 완료 기준** (정규화, Validation, `products`/`listings` upsert, price_history): **08 §26**, **09 §13** 참조.
27. 결론

07은 **Crawler / Mall Adapter / Parser / RawProductData**까지의 SSOT이다.

```text
Crawler → Parser → RawProductData
        → 08 Pipeline → 09 Repository → Cloud Firestore
```

쇼핑몰별 HTML 차이는 Adapter로 분리하고, mall `product_id`와 **`products` Document ID** (`canonical_product_id`)는 **08·05·09**에서 처리한다.

초기 MVP **07**: SSG raw 수집. 전체 E2E는 **runner.py**가 08·09를 연결 (**13**).

### 상품 상태 및 미발견 처리

크롤링 과정에서 특정 상품이 검색 결과 또는 상품 페이지에서
발견되지 않았다고 해서 즉시 해당 상품을 삭제하지 않는다.

상품 미발견은 일시적인 품절, 검색 노출 변경, 쇼핑몰 페이지 변경,
크롤링 오류 등 다양한 원인으로 발생할 수 있기 때문이다.

따라서 다음과 같은 상태를 관리한다.

ACTIVE
OUT_OF_STOCK
UNAVAILABLE
DISCONTINUED
UNKNOWN

또한 `last_seen_at`을 저장하여 해당 상품이 마지막으로
정상적으로 확인된 시점을 기록한다.

상품이 일정 기간 동안 반복적으로 발견되지 않는 경우에만
UNAVAILABLE 또는 DISCONTINUED 상태로 변경한다.

이를 통해 일시적인 크롤링 실패나 검색 결과 변경으로 인해
기존 상품 데이터가 잘못 삭제되는 문제를 방지한다.