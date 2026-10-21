import type { PriceSeriesPoint } from "../api/types";

export interface ChartBox {
  width: number;
  height: number;
  padding: { top: number; right: number; bottom: number; left: number };
}

export interface StepChart {
  path: string;
  minPrice: number;
  maxPrice: number;
  xOf: (iso: string) => number;
  yOf: (price: number) => number;
}

/**
 * Price history only records changes, so the line is a step function:
 * each price holds until the next point, and the last one holds until windowEnd.
 */
export function buildStepChart(
  series: PriceSeriesPoint[],
  windowStart: string,
  windowEnd: string,
  box: ChartBox,
): StepChart | null {
  if (series.length === 0) {
    return null;
  }
  const start = new Date(windowStart).getTime();
  const end = new Date(windowEnd).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return null;
  }

  const prices = series.map((point) => point.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const span = maxPrice - minPrice || Math.max(maxPrice * 0.02, 1);
  const yMin = minPrice - span * 0.1;
  const yMax = maxPrice + span * 0.1;

  const innerWidth = box.width - box.padding.left - box.padding.right;
  const innerHeight = box.height - box.padding.top - box.padding.bottom;
  const clampTime = (time: number) => Math.min(Math.max(time, start), end);
  const xOf = (iso: string) =>
    box.padding.left + ((clampTime(new Date(iso).getTime()) - start) / (end - start)) * innerWidth;
  const yOf = (price: number) => box.padding.top + (1 - (price - yMin) / (yMax - yMin)) * innerHeight;

  const fmt = (value: number) => value.toFixed(1);
  const first = series[0];
  const commands = [`M ${fmt(xOf(first.crawled_at))} ${fmt(yOf(first.price))}`];
  for (const point of series.slice(1)) {
    commands.push(`H ${fmt(xOf(point.crawled_at))}`, `V ${fmt(yOf(point.price))}`);
  }
  commands.push(`H ${fmt(box.padding.left + innerWidth)}`);

  return { path: commands.join(" "), minPrice, maxPrice, xOf, yOf };
}
