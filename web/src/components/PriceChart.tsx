import type { PriceSeriesPoint } from "../api/types";
import { buildStepChart } from "../utils/priceChart";
import { formatShortDate, formatWon } from "../utils/priceFormat";

interface PriceChartProps {
  series: PriceSeriesPoint[];
  windowStart: string;
  windowEnd: string;
}

const BOX = { width: 640, height: 220, padding: { top: 16, right: 16, bottom: 28, left: 16 } };

export function PriceChart({ series, windowStart, windowEnd }: PriceChartProps) {
  const chart = buildStepChart(series, windowStart, windowEnd, BOX);
  if (!chart) {
    return <p className="muted">표시할 가격 이력이 없습니다.</p>;
  }
  const baseline = BOX.height - BOX.padding.bottom;
  const last = series[series.length - 1];

  return (
    <figure className="price-chart">
      <svg
        viewBox={`0 0 ${BOX.width} ${BOX.height}`}
        role="img"
        aria-label={`최저가 변동 그래프, 최저 ${formatWon(chart.minPrice)}, 최고 ${formatWon(chart.maxPrice)}`}
      >
        <line className="price-chart-axis" x1={BOX.padding.left} x2={BOX.width - BOX.padding.right} y1={baseline} y2={baseline} />
        <line
          className="price-chart-guide"
          x1={BOX.padding.left}
          x2={BOX.width - BOX.padding.right}
          y1={chart.yOf(chart.minPrice)}
          y2={chart.yOf(chart.minPrice)}
        />
        <path className="price-chart-line" d={chart.path} />
        <circle className="price-chart-dot" cx={BOX.width - BOX.padding.right} cy={chart.yOf(last.price)} r={4} />
        <text className="price-chart-label" x={BOX.padding.left} y={BOX.height - 8}>
          {formatShortDate(windowStart)}
        </text>
        <text className="price-chart-label" x={BOX.width - BOX.padding.right} y={BOX.height - 8} textAnchor="end">
          {formatShortDate(windowEnd)}
        </text>
      </svg>
      <figcaption className="muted">
        최저 {formatWon(chart.minPrice)} · 최고 {formatWon(chart.maxPrice)}
      </figcaption>
    </figure>
  );
}
