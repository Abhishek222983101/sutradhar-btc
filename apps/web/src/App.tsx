import { lazy, Suspense, useEffect } from "react";
import Academy from "./Academy";
import Cases from "./Cases";
import Console from "./Console";
import Govern from "./Govern";
import Guide from "./Guide";
import { t, useLang } from "./i18n";
import Landing from "./Landing";
import { go, useRoute } from "./router";
import { ErrorBoundary } from "./ui";
import ScenarioStudio from "./ScenarioStudio";
import { GuideDock, Header, WakeBanner } from "./Shell";
import System from "./System";
import Verify from "./Verify";
import { probe } from "./wake";

const HowItWorks = lazy(() => import("./HowItWorks"));

export default function App() {
  const route = useRoute();
  const [lang, setLang] = useLang();
  useEffect(() => { void probe().catch(() => undefined); }, []);
  useEffect(() => { window.scrollTo({ top: 0 }); document.title = `${t(lang, TITLES[route.page])} · Sutradhar`; }, [route.page, lang]);

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <Header lang={lang} setLang={setLang} />
      <WakeBanner />
      <main id="main">
        <ErrorBoundary key={route.page}>
        {route.page === "home" && <Landing go={() => go("console")} />}
        {route.page === "guide" && <Guide />}
        {route.page === "console" && <Console route={route} lang={lang} />}
        {route.page === "cases" && <Cases runId="run_hero" lang={lang} />}
        {route.page === "verify" && <Verify />}
        {route.page === "govern" && <Govern lang={lang} />}
        {route.page === "system" && <System />}
        {route.page === "how" && <Suspense fallback={<div className="wrap empty">Loading…</div>}><HowItWorks /></Suspense>}
        {route.page === "academy" && <Academy lang={lang} />}
        {route.page === "scenarios" && <ScenarioStudio lang={lang} />}
        </ErrorBoundary>
      </main>
      <GuideDock />
    </>
  );
}

const TITLES = {
  home: "Requirements", guide: "Judge guide", console: "Console", cases: "Cases", verify: "Verify", govern: "Govern",
  system: "System", how: "How it works", academy: "Academy", scenarios: "Scenario Studio",
} as const;
