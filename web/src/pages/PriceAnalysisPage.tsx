import { useEffect, useState } from "react";
import type { ListingPriceAnalysis, ProductPriceAnalysis, PurchaseVerdict } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { QueryState, SectionCard } from "../components/HealthBadge";
import { PriceChart } from "../components/PriceChart";
import { getRefreshIntervalMs, useOperationsQuery } from "../hooks/useOperationsQuery";
import { formatPercent, formatSignedWon, formatWon, isHttpUrl } from "../utils/priceFormat";
import { UI } from "../utils/uiLabels";

const WINDOW_OPTIONS = [7, 30, 90] as const;
const DEFAULT_WINDOW = 30;

const VERDICT_CLASS: Record<PurchaseVerdict, string> = {
  BUY_CONSIDER: "verdict-buy",
  WAIT: "verdict-wait",
  NOT_RECOMMENDED: "verdict-avoid",
  INSUFFICIENT_DATA: "verdict-unknown",
};

function ListingRow({ listing }: { listing: ListingPriceAnalysis }) {
  const { stats } = listing;
  const name = listing.seller_id ?? listing.listing_id;
  return (
    <tr className={listing.available ? undefined : "listing-unavailable"}>
      <td>
        {isHttpUrl(listing.product_url) ? (
          <a href={listing.product_url} target="_blank" rel="noopener noreferrer">
            {name}
          </a>
        ) : (
          name
        )}
        {listing.mall_id ? <span className="muted"> · {listing.mall_id}</span> : null}
      </td>
      <td>{formatWon(stats.current_price)}</td>
      <td>{formatWon(stats.min_price)}</td>
      <td>{formatWon(stats.average_price)}</td>
      <td>{formatPercent(stats.price_change_rate, { signed: true })}</td>
      <td>{listing.available ? "구매 가능" : "품절"}</td>
    </tr>
  );
}

function AnalysisBody({ analysis }: { analysis: ProductPriceAnalysis }) {
  const { stats, purchase } = analysis;
  const days = analysis.window_days;

  return (
    <>
      <section className="section-card verdict-card">
        <header>
          <h3>구매 적정성</h3>
        </header>
        <div className={`verdict-badge ${VERDICT_CLASS[purchase.verdict]}`}>{purchase.label}</div>
        <ul className="reason-list">
          {purchase.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>

      <div className="card-grid">
        <SectionCard title="현재 가격">
          <p className="stat-value">{formatWon(stats.current_price)}</p>
          <p className="muted">
            {days}일 전 대비 {formatSignedWon(stats.price_change)} ({formatPercent(stats.price_change_rate, { signed: true })})
          </p>
        </SectionCard>
        <SectionCard title={`최근 ${days}일 가격`}>
          <ul className="metric-list">
            <li>최저가: {formatWon(stats.min_price)}</li>
            <li>평균가: {formatWon(stats.average_price)}</li>
            <li>중앙값: {formatWon(stats.median_price)}</li>
            <li>최고가: {formatWon(stats.max_price)}</li>
          </ul>
        </SectionCard>
        <SectionCard title="현재 위치">
          <ul className="metric-list">
            <li>최저가와의 차이: {formatWon(stats.diff_from_min)}</li>
            <li>평균 대비: {formatPercent(stats.diff_from_average_rate, { signed: true })}</li>
            <li>더 싼 기간 비율: {formatPercent(stats.price_percentile)}</li>
            <li>가격 이력: {stats.coverage_days}일 / {stats.data_points}건</li>
          </ul>
        </SectionCard>
      </div>

      <SectionCard title="최저가 변동">
        <PriceChart
          series={analysis.lowest_price_series}
          windowStart={stats.window_start}
          windowEnd={stats.window_end}
        />
      </SectionCard>

      <SectionCard title="판매처별 가격">
        {analysis.listings.length === 0 ? (
          <p className="muted">등록된 판매처가 없습니다.</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>판매처</th>
                  <th>현재가</th>
                  <th>최저가</th>
                  <th>평균가</th>
                  <th>변동률</th>
                  <th>상태</th>
                </tr>
              </thead>
              <tbody>
                {analysis.listings.map((listing) => (
                  <ListingRow key={listing.listing_id} listing={listing} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  );
}

function ProductAnalysisView({ productId, windowDays }: { productId: string; windowDays: number }) {
  const { user, operationsApi } = useAuth();
  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled: Boolean(user),
    fetcher: () => operationsApi.getProductAnalysis(productId, windowDays),
    refreshMs: getRefreshIntervalMs(),
  });

  if (status !== "success" || !data) {
    return <QueryState status={status} message={errorMessage} onRetry={() => void refresh()} />;
  }
  return <AnalysisBody analysis={data} />;
}

export function PriceAnalysisPage() {
  const { user, operationsApi } = useAuth();
  const [productId, setProductId] = useState<string | null>(null);
  const [windowDays, setWindowDays] = useState<number>(DEFAULT_WINDOW);
  const { data, status, errorMessage, refresh } = useOperationsQuery({
    enabled: Boolean(user),
    fetcher: operationsApi.getAnalysisProducts,
    refreshMs: 0,
  });

  const products = data?.products ?? [];
  useEffect(() => {
    if (productId === null && products.length > 0) {
      setProductId(products[0].product_id);
    }
  }, [productId, products]);

  if (status !== "success" || !data) {
    return <QueryState status={status} message={errorMessage} onRetry={() => void refresh()} />;
  }

  return (
    <div className="page-stack">
      <div className="page-header">
        <div>
          <h2>{UI.priceAnalysis}</h2>
          <p className="muted">가격 이력으로 현재 가격이 싼지 비싼지 살펴봅니다.</p>
        </div>
        <div className="filters-grid analysis-controls">
          <label>
            상품
            <select
              aria-label="상품 선택"
              value={productId ?? ""}
              onChange={(event) => setProductId(event.target.value)}
              disabled={products.length === 0}
            >
              {products.map((product) => (
                <option key={product.product_id} value={product.product_id}>
                  {product.product_name ?? product.product_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            기간
            <select
              aria-label="기간 선택"
              value={windowDays}
              onChange={(event) => setWindowDays(Number(event.target.value))}
            >
              {WINDOW_OPTIONS.map((days) => (
                <option key={days} value={days}>
                  최근 {days}일
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {products.length === 0 ? (
        <p className="muted">분석할 상품이 아직 없습니다.</p>
      ) : productId ? (
        <ProductAnalysisView key={`${productId}:${windowDays}`} productId={productId} windowDays={windowDays} />
      ) : null}
    </div>
  );
}
