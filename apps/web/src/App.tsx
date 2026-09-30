import { useEffect, useState } from "react";
import Academy from "./Academy";
import { enterDemo, hasSession, publicGet, type Info } from "./api";
import Cases from "./Cases";
import Console from "./Console";
import Govern from "./Govern";
import { t, useLang } from "./i18n";
import Landing from "./Landing";
import ScenarioStudio from "./ScenarioStudio";

type Page = "home" | "console" | "cases" | "govern" | "academy" | "scenarios";
const route = (): Page => {
  const h = location.hash;
  if (h.startsWith("#/cases")) return "cases";
  if (h.startsWith("#/govern")) return "govern";
  if (h.startsWith("#/academy")) return "academy";
  if (h.startsWith("#/scenarios")) return "scenarios";
  if (h.startsWith("#/console")) return "console";
  return "home";
};

export default function App() {
  const [page, setPage] = useState(route());
  const [lang, setLang] = useLang();
  useEffect(() => {
    const on = () => setPage(route());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    if (page === "home" || hasSession()) return;
    publicGet<Info>("/api/v1/system/info")
      .then((i) => {
        if (i.mode === "demo") return enterDemo();
        location.hash = "#/";
      })
      .catch(() => undefined);
  }, [page]);
  const go = () => {
    location.hash = "#/console";
  };
  return (
    <>
      <header className="top">
        <div className="wrap">
          <a className="brand" href="#/">
            <b>S</b>Sutradhar
          </a>
          <span className="tag ok">{t(lang, "Runs offline")}</span>
          <span className="tag warn">{t(lang, "Synthetic data")}</span>
          <nav className="nav">
            <a href="#/">{t(lang, "Requirements")}</a>
            <a href="#/console">{t(lang, "Console")}</a>
            <a href="#/cases">{t(lang, "Cases")}</a>
            <a href="#/govern">{t(lang, "Govern")}</a>
            <a href="#/academy">{t(lang, "Academy")}</a>
            <a href="#/scenarios">{t(lang, "Scenario Studio")}</a>
            <a className="btn" href="#/console">
              {t(lang, "Open demo")}
            </a>
            <button
              className="lang-toggle"
              aria-pressed={lang === "hi"}
              title="हिन्दी में चरण-सूची — machine-translated chrome text, not yet native-reviewed"
              onClick={() => setLang(lang === "en" ? "hi" : "en")}
            >
              {lang === "en" ? "हिं" : "EN"}
            </button>
          </nav>
        </div>
      </header>
      <main>
        {page === "console" && <Console home={() => (location.hash = "#/")} lang={lang} />}
        {page === "cases" && <Cases runId="run_hero" lang={lang} />}
        {page === "govern" && <Govern lang={lang} />}
        {page === "academy" && <Academy lang={lang} />}
        {page === "scenarios" && <ScenarioStudio lang={lang} />}
        {page === "home" && <Landing go={go} />}
      </main>
    </>
  );
}
