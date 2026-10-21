import { describe, expect, it } from "vitest";
import { buildStepChart } from "../utils/priceChart";
import { formatPercent, formatSignedWon, formatWon, isHttpUrl } from "../utils/priceFormat";

const BOX = { width: 100, height: 100, padding: { top: 0, right: 0, bottom: 0, left: 0 } };
const START = "2026-10-01T00:00:00Z";
const END = "2026-10-11T00:00:00Z";

describe("buildStepChart", () => {
  it("draws horizontal then vertical steps and holds the last price until window end", () => {
    const chart = buildStepChart(
      [
        { crawled_at: START, price: 1000 },
        { crawled_at: "2026-10-06T00:00:00Z", price: 900 },
      ],
      START,
      END,
      BOX,
    );

    expect(chart).not.toBeNull();
    // start at x=0, hold to the 2nd point (day 5 of 10 => x=50), drop, hold to window end.
    expect(chart!.path).toMatch(/^M 0\.0 \d+\.\d H 50\.0 V \d+\.\d H 100\.0$/);
    const startY = Number(chart!.path.split(" ")[2]);
    const droppedY = Number(chart!.path.split(" V ")[1].split(" ")[0]);
    expect(droppedY).toBeGreaterThan(startY); // lower price draws lower on screen
    expect(chart!.minPrice).toBe(900);
    expect(chart!.maxPrice).toBe(1000);
  });

  it("handles a flat series without dividing by zero", () => {
    const chart = buildStepChart([{ crawled_at: START, price: 1000 }], START, END, BOX);

    expect(chart).not.toBeNull();
    expect(chart!.path).not.toContain("NaN");
  });

  it("returns null for empty series or an invalid window", () => {
    expect(buildStepChart([], START, END, BOX)).toBeNull();
    expect(buildStepChart([{ crawled_at: START, price: 1 }], END, START, BOX)).toBeNull();
    expect(buildStepChart([{ crawled_at: START, price: 1 }], "bad", END, BOX)).toBeNull();
  });

  it("clamps points outside the window", () => {
    const chart = buildStepChart([{ crawled_at: "2026-09-01T00:00:00Z", price: 1000 }], START, END, BOX);

    expect(chart!.xOf("2026-09-01T00:00:00Z")).toBe(0);
    expect(chart!.xOf("2026-12-01T00:00:00Z")).toBe(100);
  });
});

describe("price formatting", () => {
  it("formats won, percent and signed values", () => {
    expect(formatWon(1599000)).toBe("1,599,000원");
    expect(formatWon(null)).toBe("-");
    expect(formatPercent(-5.25)).toBe("-5.3%");
    expect(formatPercent(3, { signed: true })).toBe("+3.0%");
    expect(formatSignedWon(-50000)).toBe("-50,000원");
    expect(formatSignedWon(50000)).toBe("+50,000원");
  });

  it("only treats http(s) urls as linkable", () => {
    expect(isHttpUrl("https://www.ssg.com/item/1")).toBe(true);
    expect(isHttpUrl("javascript:alert(1)")).toBe(false);
    expect(isHttpUrl(null)).toBe(false);
  });
});
