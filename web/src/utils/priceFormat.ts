/** 가격 분석 화면 표시용 포맷터 */

export function formatWon(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

export function formatPercent(value: number | null | undefined, options: { signed?: boolean } = {}): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const sign = options.signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatSignedWon(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatWon(value)}`;
}

export function formatShortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return `${date.getUTCMonth() + 1}/${date.getUTCDate()}`;
}

export function isHttpUrl(value: string | null | undefined): value is string {
  if (!value) {
    return false;
  }
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
