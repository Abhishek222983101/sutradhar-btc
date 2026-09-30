import { describe, expect, it } from "vitest";
import { btc, ist, pct, pctPair, short } from "./format";

describe("format", () => {
  it("converts satoshis to BTC without floating-point surprises", () => {
    expect(btc(100_000_000)).toBe("1.0000");
    expect(btc(3_100_000)).toBe("0.0310");
    expect(btc(1)).toBe("0.0000");
  });
  it("rounds percentages", () => {
    expect(pct(0.404)).toBe("40%");
    expect(pct(0.995)).toBe("100%");
    expect(pct(0)).toBe("0%");
  });
  it("shows times in IST with the offset labelled", () => {
    // 2026-08-02T00:00:00Z is 05:30 in India
    expect(ist(Date.UTC(2026, 7, 2) * 1000)).toBe("02 Aug 2026, 05:30:00 IST");
  });
  it("shortens long ids only", () => {
    expect(short("abcdefghijklmnop")).toBe("abcdefghij…");
    expect(short("abc")).toBe("abc");
  });
  it("distinguishes close percentages that would otherwise round to the same value", () => {
    expect(pctPair(0.999, 0.998)).toEqual(["99.9%", "99.8%"]);
    expect(pctPair(0.41, 0.62)).toEqual(["41%", "62%"]);
  });
});
