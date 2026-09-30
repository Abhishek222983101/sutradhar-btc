import { useEffect, useState } from "react";
import { enterDemo, hasSession, publicGet, type Info } from "./api";
import Console from "./Console";
import Landing from "./Landing";

const route = () => (location.hash.startsWith("#/console") ? "console" : "home");

export default function App() {
  const [page, setPage] = useState(route());
  useEffect(() => {
    const on = () => setPage(route());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    if (page !== "console" || hasSession()) return;
    publicGet<Info>("/api/v1/system/info").then((i) => { if (i.mode === "demo") return enterDemo(); location.hash = "#/"; }).catch(() => undefined);
  }, [page]);
  const go = () => { location.hash = "#/console"; };
  return (
    <>
      <header className="top">
        <div className="wrap">
          <a className="brand" href="#/"><b>S</b>Sutradhar</a>
          <span className="tag ok">Runs offline</span>
          <span className="tag warn">Synthetic data</span>
          <nav className="nav">
            <a href="#/">Requirements</a>
            <a className="btn" href="#/console">Console</a>
          </nav>
        </div>
      </header>
      <main>{page === "console" ? <Console home={() => (location.hash = "#/")} /> : <Landing go={go} />}</main>
    </>
  );
}
