import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PriceAnalysisPage } from "../pages/PriceAnalysisPage";
import { ConnectionProvider } from "../auth/ConnectionContext";

const stats = {
  window_days: 30,
  window_start: "2026-09-20T00:00:00Z",
  window_end: "2026-10-20T00:00:00Z",
  observed_from: "2026-09-20T00:00:00Z",
  coverage_days: 30,
  data_points: 2,
  current_price: 920000,
  min_price: 920000,
  max_price: 1000000,
  average_price: 990000,
  median_price: 1000000,
  price_range: 80000,
  start_price: 1000000,
  price_change: -80000,
  price_change_rate: -8,
  price_percentile: 0,
  diff_from_min: 0,
  diff_from_average_rate: -7.1,
};

function analysis(windowDays: number) {
  return {
    product_id: "P1",
    product_name: "ZOTAC RTX 5080",
    window_days: windowDays,
    generated_at: "2026-10-20T00:00:00Z",
    lowest_listing_id: "SSG_1",
    stats: { ...stats, window_days: windowDays },
    purchase: {
      verdict: "BUY_CONSIDER",
      label: "구매 고려",
      trend: "DOWN",
      trend_change_rate: -8,
      reasons: ["현재 가격은 최근 30일 평균보다 7.1% 낮습니다."],
    },
    listings: [
      {
        listing_id: "SSG_1",
        mall_id: "SSG",
        seller_id: "SSG_HITINFO",
        product_url: "https://www.ssg.com/item/1",
        available: true,
        stats,
      },
      {
        listing_id: "SSG_2",
        mall_id: "SSG",
        seller_id: null,
        product_url: "javascript:alert(1)",
        available: false,
        stats,
      },
    ],
    lowest_price_series: [
      { crawled_at: "2026-09-20T00:00:00Z", price: 1000000 },
      { crawled_at: "2026-10-10T00:00:00Z", price: 920000 },
    ],
  };
}

const getAnalysisProducts = vi.fn(async () => ({
  products: [
    { product_id: "P1", product_name: "ZOTAC RTX 5080" },
    { product_id: "P2", product_name: null },
  ],
}));
const getProductAnalysis = vi.fn(async (_id: string, windowDays: number) => analysis(windowDays));

vi.mock("../auth/AuthContext", async () => {
  const actual = await vi.importActual<typeof import("../auth/AuthContext")>("../auth/AuthContext");
  return {
    ...actual,
    useAuth: () => ({
      user: { uid: "viewer", email: "viewer@example.com", roles: ["OPS_VIEWER"] },
      loading: false,
      configured: true,
      operationsApi: { getAnalysisProducts, getProductAnalysis },
      login: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(async () => "token"),
    }),
  };
});

function renderPage() {
  return render(
    <ConnectionProvider>
      <PriceAnalysisPage />
    </ConnectionProvider>,
  );
}

describe("PriceAnalysisPage", () => {
  afterEach(cleanup);

  it("shows verdict, stats, chart and listings for the first product", async () => {
    renderPage();

    expect(await screen.findByText("구매 고려")).toBeInTheDocument();
    expect(screen.getByText("현재 가격은 최근 30일 평균보다 7.1% 낮습니다.")).toBeInTheDocument();
    expect(screen.getAllByText("920,000원").length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: /최저가 변동 그래프/ })).toBeInTheDocument();
    expect(getProductAnalysis).toHaveBeenCalledWith("P1", 30);

    const link = screen.getByRole("link", { name: "SSG_HITINFO" });
    expect(link).toHaveAttribute("href", "https://www.ssg.com/item/1");
    expect(screen.getByText("품절")).toBeInTheDocument();
    expect(screen.getByText("SSG_2")).not.toHaveAttribute("href");
  });

  it("reloads when the window changes", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("구매 고려");

    await user.selectOptions(screen.getByLabelText("기간 선택"), "90");

    await waitFor(() => expect(getProductAnalysis).toHaveBeenCalledWith("P1", 90));
  });

  it("reloads when another product is picked, falling back to the id as its name", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("구매 고려");

    await user.selectOptions(screen.getByLabelText("상품 선택"), "P2");

    await waitFor(() => expect(getProductAnalysis).toHaveBeenCalledWith("P2", 30));
  });

  it("explains when there are no products", async () => {
    getAnalysisProducts.mockResolvedValueOnce({ products: [] });
    renderPage();

    expect(await screen.findByText("분석할 상품이 아직 없습니다.")).toBeInTheDocument();
  });
});
