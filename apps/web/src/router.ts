import { useMemo, useSyncExternalStore } from "react";

// A hash router with query parameters, so every guide step can deep-link to an exact state:
//   #/console?lead=bc1q9506uy&tab=path     #/console?open=ip:40.94.238.111
export type Page = "home" | "guide" | "console" | "cases" | "govern" | "academy" | "scenarios" | "how" | "system" | "verify";

const SLUG: Record<Page, string> = {
  home: "", guide: "guide", console: "console", cases: "cases", govern: "govern", academy: "academy",
  scenarios: "scenarios", how: "how-it-works", system: "system", verify: "verify",
};
const PAGE_OF = Object.fromEntries(Object.entries(SLUG).map(([page, slug]) => [slug, page as Page])) as Record<string, Page>;

export type Params = Record<string, string>;
export type Route = { page: Page; params: Params };

export function parseHash(hash: string): Route {
  const [path, query = ""] = hash.replace(/^#\/?/, "").split("?");
  const params: Params = {};
  new URLSearchParams(query).forEach((v, k) => { params[k] = v; });
  return { page: PAGE_OF[path.replace(/\/$/, "")] ?? "home", params };
}

export function href(page: Page, params: Params = {}): string {
  const q = new URLSearchParams(params).toString();
  return `#/${SLUG[page]}${q ? `?${q}` : ""}`;
}

export function go(page: Page, params: Params = {}) {
  location.hash = href(page, params);
}

function subscribe(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => location.hash, () => "");
  return useMemo(() => parseHash(hash), [hash]);
}

/** Replace one query parameter without adding a history entry (tabs, filters). */
export function setParam(key: string, value: string | null) {
  const { page, params } = parseHash(location.hash);
  const next = { ...params };
  if (value === null) delete next[key]; else next[key] = value;
  history.replaceState(null, "", href(page, next));
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}
