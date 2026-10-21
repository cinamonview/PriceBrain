# Price Analysis (Phase 2)

PRD §11 (데이터 분석), §13 (구매 적정성), §14 (가격 분석 지표)의 첫 구현입니다.
`price_history`와 `listings`를 읽기만 하며 어떤 데이터도 쓰지 않습니다.

## Architecture

```text
GET /analysis/products/{product_id}?window_days=30
      ↓
PriceAnalysisRepository   (listings where product_id == ?, listings/{id}/price_history)
      ↓
analysis/product_analysis (판매처별 통계 + 최저가 시계열)
      ↓
analysis/price_stats      (기간 통계, pure)
analysis/purchase         (구매 적정성 규칙, pure)
```

`pricebrain_app/analysis/`는 순수 계산 모듈입니다. Firestore, repository, crawler, pipeline, api를 import하지 않으며
`test_responsibility_boundaries.py`가 이를 검증합니다.

## 통계 계산 방식

`price_history`는 가격이 바뀔 때만 append됩니다(docs/05 §3.9). 따라서 가격은 계단 함수로 보고 **시간 가중**으로 계산합니다.

- 기간 시작 시점에 적용 중이던 가격(기간 이전 마지막 이력)을 기간 안으로 이어받습니다.
- `average_price`, `median_price`, `price_percentile`은 가격이 유지된 시간 기준입니다.
- `price_percentile`은 현재가보다 낮았던 시간의 비율(%)입니다. 0이면 기간 내 최저 수준입니다.
- `price_change_rate`는 기간 시작가 대비 현재가 변동률(%)입니다.
- `coverage_days`는 첫 관측 시점부터 지금까지의 일수입니다. 이력이 짧으면 작게 나옵니다.
- 미래 시각, 0 이하 가격은 제외합니다. 이력이 비어 있으면 listing의 `current_price`로 대체합니다.
- 기간은 7, 30, 90일만 허용합니다(PRD §11.2).

## 판매처 분석 (PRD §11.3)

상품의 모든 listing에 같은 통계를 계산해 `listings`로 반환합니다. 품절(`UNAVAILABLE`/`availability=false`) listing은
목록에는 남지만 정렬 뒤쪽에 두고, 상품 최저가와 구매 적정성 계산에서는 제외합니다.
상품 최저가 시계열(`lowest_price_series`)은 구매 가능한 listing 중 가장 싼 가격의 변화를 합친 것입니다.

## 구매 적정성 (PRD §13)

설명 가능한 규칙만 사용합니다. 임계값은 `analysis/purchase.py` 상수입니다.

| 판정 | 조건 |
|------|------|
| `BUY_CONSIDER` 구매 고려 | 현재가가 평균보다 3% 이상 낮고 기간 최저가의 3% 이내 |
| `NOT_RECOMMENDED` 구매 비추천 | 현재가가 평균보다 3% 이상 높고 최근 7일 가격이 1% 이상 하락 중 |
| `WAIT` 관망 | 그 외 |
| `INSUFFICIENT_DATA` 데이터 부족 | 이력이 3일 미만 |

각 판정에는 사용자에게 보여줄 `reasons` 문장이 함께 반환됩니다.

## Response (요약)

```json
{
  "product_id": "ZOTAC-RTX5080-SOLIDCORE-16GB",
  "window_days": 30,
  "lowest_listing_id": "SSG_1",
  "stats": {"current_price": 920000, "min_price": 920000, "average_price": 990000, "price_change_rate": -8.0},
  "purchase": {"verdict": "BUY_CONSIDER", "label": "구매 고려", "reasons": ["..."]},
  "listings": [],
  "lowest_price_series": []
}
```

## 아직 하지 않은 것

- 인증: 현재 `/analysis`는 카탈로그 읽기 전용이며 별도 인증이 없습니다. 공개 노출 전에 정책을 정해야 합니다.
- Firestore 인덱스: `listings where product_id ==`는 단일 필드 조회라 추가 인덱스가 필요 없습니다.
- 가격 대비 성능, 변동성(`volatility`), `purchase_score`(PRD §14 향후 항목)와 시각화는 이후 단계입니다.
