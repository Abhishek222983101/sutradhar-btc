import { useEffect, useState } from "react";
import Academy from "./Academy";
import { enterDemo, hasSession, publicGet, type Info } from "./api";
import Cases from "./Cases";
import Console from "./Console";
import Govern from "./Govern";
import Landing from "./Landing";

type Page = "home" | "console" | "cases" | "govern" | "academy";
const route = (): Page => {
  const h = location.hash;
  if (h.startsWith("#/cases")) return "cases";
  if (h.startsWith("#/govern")) return "govern";
  if (h.startsWith("#/academy")) return "academy";
  if (h.startsWith("#/console")) return "console";
  return "home";
};

export default function App() {
  const [page, setPage] = useState(route());
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
          <span className="tag ok">Runs offline</span>
          <span className="tag warn">Synthetic data</span>
          <nav className="nav">
            <a href="#/">Requirements</a>
            <a href="#/console">Console</a>
            <a href="#/cases">Cases</a>
            <a href="#/govern">Govern</a>
            <a href="#/academy">Academy</a>
            <a className="btn" href="#/console">
              Open demo
            </a>
          </nav>
        </div>
      </header>
      <main>
        {page === "console" && <Console home={() => (location.hash = "#/")} />}
        {page === "cases" && <Cases runId="run_hero" />}
        {page === "govern" && <Govern />}
        {page === "academy" && <Academy />}
        {page === "home" && <Landing go={go} />}
      </main>
    </>
  );
}
