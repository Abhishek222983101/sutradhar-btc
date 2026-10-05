import { describe, expect, it } from "vitest";
import { href, parseHash } from "./router";

describe("hash router", () => {
  it("round-trips a page with parameters", () => {
    const h = href("console", { lead: "bc1q9506uy", tab: "path" });
    expect(h).toBe("#/console?lead=bc1q9506uy&tab=path");
    expect(parseHash(h)).toEqual({ page: "console", params: { lead: "bc1q9506uy", tab: "path" } });
  });
  it("treats an empty or unknown hash as home", () => {
    expect(parseHash("").page).toBe("home");
    expect(parseHash("#/nope").page).toBe("home");
  });
  it("keeps a colon-separated value intact", () => {
    expect(parseHash(href("console", { open: "ip:40.94.238.111" })).params.open).toBe("ip:40.94.238.111");
  });
  it("names every page", () => {
    for (const p of ["guide", "cases", "verify", "govern", "system", "how", "academy", "scenarios"] as const) {
      expect(parseHash(href(p)).page).toBe(p);
    }
  });
});
