import { useEffect } from "react";
import { CORE_STEPS, type Step } from "./guide";
import { go, href, type Page, type Route, useRoute } from "./router";
import { update, useProgress } from "./progress";
import { retry, useWake } from "./wake";
import { t, type Lang } from "./i18n";
import { Inputs } from "./ui";

const NAV: { page: Page; label: string }[] = [
  { page: "console", label: "Console" },
  { page: "cases", label: "Cases" },
  { page: "verify", label: "Verify" },
  { page: "govern", label: "Govern" },
  { page: "system", label: "System" },
  { page: "how", label: "How it works" },
];
const MORE: { page: Page; label: string }[] = [
  { page: "academy", label: "Academy" },
  { page: "scenarios", label: "Scenario Studio" },
  { page: "home", label: "Requirements" },
];

export function StatusPill() {
  const w = useWake();
  const label = w.state === "ready" ? "Server live" : w.state === "down" ? "Server unreachable" : w.state === "waking" ? `Waking server ${w.elapsed}s` : "Connecting";
  return <span className={`pill ${w.state}`} role="status"><i />{label}</span>;
}

export function WakeBanner() {
  const w = useWake();
  if (w.state === "ready" || w.state === "checking") return null;
  const down = w.state === "down";
  return (
    <div className={`wake${down ? " down" : ""}`} role="status" aria-live="polite">
      <div className="wrap">
        {down ? (
          <>
            <b>The demo server did not answer.</b>
            <p className="note">It runs on a free host that can take a minute to restart. <button className="chip" onClick={retry}>Try again</button></p>
          </>
        ) : (
          <>
            <b>Waking the demo server… {w.elapsed}s</b>
            <p className="note">It runs on a free host that sleeps when idle and needs 30–45 seconds to start. Nothing is broken: this page continues on its own.</p>
            <div className="meter" aria-hidden="true"><i /></div>
          </>
        )}
      </div>
    </div>
  );
}

export function Header({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const route = useRoute();
  return (
    <header className="top">
      <div className="wrap">
        <a className="brand" href={href("home")}><b>S</b>Sutradhar</a>
        <StatusPill />
        <nav className="nav" aria-label="Main">
          <a className="nav-guide" href={href("guide")} aria-current={route.page === "guide" ? "page" : undefined}>{t(lang, "Judge guide")}</a>
          {NAV.map((n) => <a key={n.page} href={href(n.page)} aria-current={route.page === n.page ? "page" : undefined}>{t(lang, n.label)}</a>)}
          <details className="more">
            <summary>{t(lang, "More")}</summary>
            <div className="more-menu">
              {MORE.map((n) => <a key={n.page} href={href(n.page)} aria-current={route.page === n.page ? "page" : undefined}>{t(lang, n.label)}</a>)}
            </div>
          </details>
          <button className="lang-toggle" aria-pressed={lang === "hi"} title="Hindi chrome text: machine-translated, not yet native-reviewed" onClick={() => setLang(lang === "en" ? "hi" : "en")}>
            {lang === "en" ? "हिं" : "EN"}
          </button>
        </nav>
      </div>
    </header>
  );
}

const samePlace = (step: Step, route: Route) =>
  step.where.page === route.page && Object.entries(step.where.params ?? {}).every(([k, v]) => route.params[k] === v);

/** The floating coach: one step at a time, what to click, what to paste, what you should see. */
export function GuideDock() {
  const route = useRoute();
  const p = useProgress();
  const i = Math.max(0, CORE_STEPS.findIndex((s) => s.id === p.current));
  const step = CORE_STEPS[i];
  const finished = CORE_STEPS.every((s) => p.done.includes(s.id));
  useEffect(() => { if (!CORE_STEPS.some((s) => s.id === p.current)) update({ current: CORE_STEPS[0].id }); }, [p.current]);
  // Landing on a step's exact page (by following a link) moves the tour card to that step.
  useEffect(() => {
    const here = CORE_STEPS.filter((s) => Object.keys(s.where.params ?? {}).length > 0 && samePlace(s, route));
    if (here.length && !here.some((s) => s.id === p.current)) update({ current: here[0].id });
  }, [route, p.current]);
  if (route.page === "guide" || route.page === "home" || p.hidden) return null;
  if (p.collapsed) {
    return (
      <div className="dock mini">
        <button className="dock-mini" onClick={() => update({ collapsed: false })} aria-label="Open the guided tour">
          <b>Guided tour</b><span className="rid" style={{ color: "var(--ink)" }}>{p.done.filter((d) => CORE_STEPS.some((s) => s.id === d)).length}/{CORE_STEPS.length}</span>
        </button>
      </div>
    );
  }
  const next = (from: number) => {
    const n = CORE_STEPS[from + 1];
    if (!n) { update({ done: Array.from(new Set([...p.done, step.id])) }); return; }
    update({ done: Array.from(new Set([...p.done, step.id])), current: n.id });
    go(n.where.page, n.where.params);
  };
  return (
    <aside className="dock" aria-label="Guided tour">
      <div className="dock-head">
        <b>{finished ? "Tour complete" : `Guided tour · step ${i + 1} of ${CORE_STEPS.length}`}</b>
        <button onClick={() => update({ collapsed: true })}>Minimise</button>
        <button onClick={() => update({ hidden: true })} aria-label="Close the guided tour">Close</button>
      </div>
      {finished ? (
        <div className="dock-body">
          <h3>You have seen every core check.</h3>
          <p className="note">The Judge guide has {`the optional deeper checks`}: peeling chains, merge suggestions, case exports, models and the scenario studio.</p>
          <div className="dock-foot">
            <a className="btn" href={href("guide")}>Open the Judge guide</a>
            <button className="chip" onClick={() => { update({ done: [], current: CORE_STEPS[0].id }); go(CORE_STEPS[0].where.page, CORE_STEPS[0].where.params); }}>Restart tour</button>
          </div>
        </div>
      ) : (
        <div className="dock-body">
          <h3>{step.title}</h3>
          <ol>{step.do.map((d) => <li key={d}>{d}</li>)}</ol>
          {step.inputs && <Inputs items={step.inputs} />}
          <p className="small-note"><b>You should see:</b> {step.expect[0]}</p>
          <div className="dock-foot">
            {!samePlace(step, route) && <a className="btn" href={href(step.where.page, step.where.params)}>Take me there</a>}
            {i > 0 && <button className="chip" onClick={() => { const prev = CORE_STEPS[i - 1]; update({ current: prev.id }); go(prev.where.page, prev.where.params); }}>Back</button>}
            <button className="chip" onClick={() => next(i)}>{i === CORE_STEPS.length - 1 ? "Finish" : "Done, next step"}</button>
          </div>
        </div>
      )}
    </aside>
  );
}
