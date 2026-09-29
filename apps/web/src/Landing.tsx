import { useEffect, useState } from "react";
import { enterDemo, publicGet, type Info } from "./api";
import { LABEL, REQUIREMENTS } from "./requirements";
import Threads from "./Threads";

export default function Landing({ go }: { go: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState<Info | null>(null);
  const [up, setUp] = useState<boolean | null>(null);
  useEffect(() => {
    publicGet<Info>("/api/v1/system/info").then((i) => { setInfo(i); setUp(true); }, () => setUp(false));
  }, []);
  const start = async () => {
    setBusy(true); setError("");
    try { await enterDemo(); go(); } catch (e) { setError((e as Error).message); setBusy(false); }
  };
  const live = REQUIREMENTS.filter((r) => r.status === "live").length;
  return (
    <>
      <div className="wrap">
        <section className="hero">
          <div>
            <h1>Find the IP behind the <mark>wallet</mark>.</h1>
            <p className="lede">
              An offline platform that joins Bitcoin network traffic to blockchain data, then hands investigators
              a ranked list of leads, each one with its evidence and its reasons.
            </p>
            <div className="cta">
              <button className="btn primary" onClick={start} disabled={busy}>{busy ? "Opening…" : "Open the live demo"}</button>
              <span className="note">No sign-up. Synthetic data only.</span>
            </div>
            {error && <p className="err" role="alert">{error}</p>}
            {up === false && <p className="err" role="alert">The demo server is waking up. Try again in a few seconds.</p>}
          </div>
          <Threads />
        </section>
        <section className="stats" aria-label="Results on the test world">
          <div className="stat"><b>40%</b><span>origin IP found first try (chance: 4.5%)</span></div>
          <div className="stat"><b>52%</b><span>origin IP in the top 3 candidates</span></div>
          <div className="stat"><b>100%</b><span>wallet clusters pure against hidden truth</span></div>
          <div className="stat"><b>{live} of 20</b><span>requirements live, the rest shown honestly below</span></div>
        </section>
        <section id="board">
          <h2 className="section-title">Every requirement, and where to see it</h2>
          <p className="note">Status is what runs today. Nothing here is a mock-up.</p>
          <div className="board">
            {REQUIREMENTS.map((r) => (
              <article className="req" key={r.id}>
                <header><span className="id">R-{r.id}</span><span className={`st ${r.status}`}>{LABEL[r.status]}</span></header>
                <h3>{r.title}</h3>
                <p>{r.how}</p>
                {r.link && <a href={r.link} onClick={r.link === "#/console" ? () => void enterDemo().catch(() => undefined) : undefined}>{r.link === "#/console" ? "See it in the demo" : "See the code"}</a>}
              </article>
            ))}
          </div>
        </section>
      </div>
      <footer>
        <div className="wrap">
          SIH 2026 · Problem statement SIH26146 · Synthetic data, no real traffic.{" "}
          {info && <>Server {info.mode} mode, offline guard {info.offline_guard.active ? "on" : "off"}.</>}
        </div>
      </footer>
    </>
  );
}
