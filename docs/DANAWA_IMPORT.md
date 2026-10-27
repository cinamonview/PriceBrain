# Danawa CSV Backfill

`sammy310/Danawa-Crawler`(MIT)가 매일 공개하는 `crawl_data/VGA.csv`를 읽어 가격 이력을 채웁니다. 다나와에는 요청을 보내지 않고 디스크의 CSV만 읽습니다.

CSV 형식: `Id`(다나와 pcode), `Name`, 이후 열은 KST 수집 시각별 최저가입니다. 숫자가 아닌 칸(`일시품절`, `가격비교예정`)은 가격 없음으로 처리합니다.

## 동작

각 행은 크롤러가 수집한 listing과 같은 경로(`run_pipeline` → `persist_validated_product`)를 지나므로 GPU 마스터와 identity review 게이트가 그대로 적용됩니다. 게이트가 거절한 행은 강제로 넣지 않고 사유별로 보고합니다.

1. 모든 행의 최신 가격을 한 배치로 검사해 통과한 행을 고릅니다 (같은 canonical id를 공유하는 행은 이 단계에서 걸러집니다).
2. 통과한 행만 가격이 바뀐 시점을 오래된 순서로 저장합니다. `listings/DANAWA_{pcode}`와 `price_history`가 만들어지고 `current_price`는 마지막 가격이 됩니다.

## 실행

```bash
# 1) 에뮬레이터 실행 + 환경 변수 (README 참고), GPU 마스터 시드
python -m pricebrain_app.scripts.seed_gpu_master

# 2) 아무것도 쓰지 않고 결과만 확인
python -m pricebrain_app.scripts.import_danawa_csv --csv path/to/VGA.csv --dry-run

# 3) 실제 저장
python -m pricebrain_app.scripts.import_danawa_csv --csv path/to/VGA.csv
```

`FIRESTORE_EMULATOR_HOST`가 없으면 쓰기를 거부합니다 (`--dry-run` 제외). 실제 Firestore에 쓰려면 `--allow-production`을 명시해야 합니다.

## 2026-10-26 CSV 기준 dry-run 결과 (980행)

| 결과 | 행 수 | 원인 |
| --- | ---: | --- |
| 통과 | 110 | |
| `identity_review_blocked` | 376 | canonical id(`브랜드-모델-변형-VRAM`)가 같은 상품이 여러 pcode로 존재 (판매 대행사별 pcode, 스틸레전드/CHALLENGER 등 변형) |
| `pipeline_invalid:gpu` | 201 | 브랜드(AFOX, FORSA 등) 또는 모델이 파서/마스터에 없음 |
| `not_gpu` | 95 | 그래픽카드가 아닌 상품 |
| `unknown_gpu_model:*` | 약 170 | RTX 5050, RX 9060 XT, RX 9070 XT, RTX 30/40 시리즈 등이 GPU 마스터에 없음 |
| `no_price` | 14 | 가격이 한 번도 없음 |

통과율을 높이려면 GPU 마스터에 모델을 추가하거나, 다나와 pcode를 identity에 반영하는 정책 결정이 필요합니다.
