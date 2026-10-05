import { useEffect, useState } from "react";
import { enterDemo, publicGet, type Eval, type Info } from "./api";
import { CORE_STEPS } from "./guide";
import Login from "./Login";
import { update } from "./progress";
import { LABEL, REQUIREMENTS } from "./requirements";
import { go, href, useRoute } from "./router";
import Threads from "./Threads";
import { Callout } from "./ui";

const pc = (v: number) => `${Math.round(v * 1000) / 10}%`;

export default function Landing({ go: toConsole }: { go: () => void }) {
  const route = useRoute();
  const [busy, setBusy] = useState<"tour" | "console" | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState<Info | null>(null);
  const [ev, setEv] = useState<Eval | null>(null);
  const highlighted = route.params.req;

  useEffect(() => {
    publicGet<Info>("/api/v1/system/info").then(setInfo, () => undefined);
    publicGet<Eval>("/api/v1/eval").then(setEv, () => undefined);
  }, []);
  useEffect(() => {
    if (!highlighted) return;
    document.getElementById(`req-${highlighted}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [highlighted, info]);

  const begin = async (target: "tour" | "console") => {
    setBusy(target); setError("");
    try {
      await enterDemo();
      if (target === "tour") {
        update({ current: CORE_STEPS[0].id, hidden: false, collapsed: false, done: [] });
        go("guide");
      } else toConsole();
    } catch (e) { setError((e as Error).message); setBusy(null); }
  };
  const live = REQUIREMENTS.filter((r) => r.status === "live").length;

  return (
    <>
      <div className="wrap stack">
        <section className="hero">
          <div>
            <p className="kicker">Smart India Hackathon 2026 · SIH26146 · NTRO</p>
            <h1>Find the IP behind the <mark>wallet</mark>.</h1>
            <p className="lede">
              An offline platform that joins Bitcoin network traffic to blockchain data, then hands investigators a ranked list of
              leads, each one with its evidence, its reasons and what would clear it.
            </p>
            <div className="cta">
              {info && info.mode !== "demo" ? <Login done={toConsole} /> : (
                <>
                  <button className="btn primary" onClick={() => void begin("tour")} disabled={busy !== null}>{busy === "tour" ? "Opening…" : "Start the 8-minute tour"}</button>
                  <button className="btn" onClick={() => void begin("console")} disabled={busy !== null}>{busy === "console" ? "Opening…" : "Open the console"}</button>
                </>
              )}
            </div>
            <p className="note" style={{ marginTop: 12 }}>No sign-up. Synthetic data only. After a quiet spell the free server needs up to 45 seconds to wake; the header says when.</p>
            {error && <p className="err" role="alert">{error}</p>}
          </div>
          <Threads />
        </section>

        <section aria-labelledby="how3">
          <h2 id="how3" className="sr-only">How to evaluate</h2>
          <ol className="flow3" style={{ padding: 0, margin: 0 }}>
            <li><b>Follow the guide</b><p>The Judge guide lists every check in order, with the exact text to paste and what you should see.</p></li>
            <li><b>Click what it says</b><p>A small tour card follows you through the site and moves on when you press Next. Nothing to set up.</p></li>
            <li><b>Compare with the problem statement</b><p>Every step names the requirement it proves. The board below links each of the 20 to a live page.</p></li>
          </ol>
        </section>

        <section className="stats" aria-label="Results on the test worlds">
          <div className="stat"><b>{ev ? pc(ev.origin_top1_mean) : "…"}</b><span>origin IP found first try (random guess: {ev ? pc(ev.origin_random_baseline_mean) : "…"})</span></div>
          <div className="stat"><b>{ev ? pc(ev.origin_top3_mean) : "…"}</b><span>origin IP in the top 3 candidates</span></div>
          <div className="stat"><b>{ev ? pc(ev.wallet_cluster_purity_mean) : "…"}</b><span>wallet clusters pure against hidden truth</span></div>
          <div className="stat"><b>{live} of 20</b><span>requirements live and linked to a working page</span></div>
        </section>
        {ev && <p className="note" style={{ marginTop: -24 }}>Measured on {ev.seeds.length} freshly generated worlds ({ev.observable_transactions_total} observable transactions) with hidden ground truth; reproduce with <span className="mono">sutradhar evals report</span>.</p>}

        <section id="board">
          <h2 className="section-title">The problem statement, line by line</h2>
          <p className="section-sub">Each card is one requirement. Status is what runs today, and the link opens the page that proves it.</p>
          <div className="board" style={{ marginTop: 16 }}>
            {REQUIREMENTS.map((r) => (
              <article className="req" id={`req-${r.id}`} key={r.id} style={highlighted === r.id ? { outline: "4px solid var(--navy)", outlineOffset: 3 } : undefined}>
                <header><span className="id">R-{r.id}</span><span className={`st ${r.status}`}>{LABEL[r.status]}</span></header>
                <h3>{r.title}</h3>
                <p>{r.how}</p>
                {r.to && (r.external
                  ? <a href={r.to} target="_blank" rel="noreferrer">{r.cta} ↗</a>
                  : <a href={r.to}>{r.cta} →</a>)}
              </article>
            ))}
          </div>
        </section>

        <Callout tone="info" title="New here?">
          Open the <a href={href("guide")}>Judge guide</a>. It is written for someone seeing the project for the first time and takes about eight minutes.
        </Callout>
      </div>
      <footer>
        <div className="wrap">
          SIH 2026 · Problem statement SIH26146 · Synthetic data, no real traffic.{" "}
          {info && <>Server in {info.mode} mode, offline guard {info.offline_guard.active ? "on" : "off"}.</>}
        </div>
      </footer>
    </>
  );
}
