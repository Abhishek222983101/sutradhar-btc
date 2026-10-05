import { useEffect } from "react";
import { CORE_STEPS, STEPS, type Step } from "./guide";
import { go, href } from "./router";
import { toggleDone, update, useProgress } from "./progress";
import { Callout, Inputs, PageHeader } from "./ui";

function StepCard({ step, n, done }: { step: Step; n: number; done: boolean }) {
  return (
    <li className={`step${done ? " done" : ""}`} id={`step-${step.id}`}>
      <div className="num" aria-hidden="true">{done ? "✓" : n}</div>
      <div className="main">
        <div>
          <h3>{step.title}{step.core ? "" : <span className="note"> · optional</span>}</h3>
          <p className="note">{step.summary}</p>
        </div>
        <div className="cols">
          <div>
            <h4>Do this</h4>
            <ol>{step.do.map((d) => <li key={d}>{d}</li>)}</ol>
            {step.inputs && <div style={{ marginTop: 10 }}><h4>Paste or use</h4><Inputs items={step.inputs} /></div>}
          </div>
          <div>
            <h4>You should see</h4>
            <ul>{step.expect.map((e) => <li key={e}>{e}</li>)}</ul>
            <div style={{ marginTop: 10 }}>
              <h4>Requirement it proves</h4>
              <div className="proves">{step.proves.map((r) => <a key={r} className="rid" href={href("home", { req: r.replace("R-", "") })} title="Show this requirement on the board">{r}</a>)}</div>
            </div>
          </div>
        </div>
        <p className="tech"><b>Under the hood:</b> {step.tech}</p>
        <div className="foot">
          <button className="btn" onClick={() => { update({ current: step.id, hidden: false, collapsed: false }); go(step.where.page, step.where.params); }}>Open this step</button>
          <label><input type="checkbox" checked={done} onChange={() => toggleDone(step.id)} />Mark as done</label>
        </div>
      </div>
    </li>
  );
}

export default function Guide() {
  const p = useProgress();
  useEffect(() => { update({ hidden: false }); }, []);
  const coreDone = CORE_STEPS.filter((s) => p.done.includes(s.id)).length;
  const optional = STEPS.filter((s) => !s.core);
  const start = CORE_STEPS.find((s) => !p.done.includes(s.id)) ?? CORE_STEPS[0];
  return (
    <div className="wrap page">
      <PageHeader
        kicker="For evaluators"
        title="Judge guide: test everything in about eight minutes"
        lede="Follow the numbered steps. Each one says where to click, what to paste, what you should see, and which line of the problem statement it proves. A small tour card follows you through the site and moves you on when you press Next."
      />
      <Callout tone="info" title="Before you start">
        All data is synthetic and the hero dataset is the same on every install. If the header says the server is waking, keep going: a labelled saved copy of the demo data shows meanwhile and switches to live on its own in 30–45 seconds. Only Upload, Cases and Verify need the live server.
      </Callout>
      <div className="two-col" style={{ gridTemplateColumns: "1fr auto", alignItems: "center" }}>
        <div>
          <p><b>{coreDone} of {CORE_STEPS.length}</b> core checks done</p>
          <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={CORE_STEPS.length} aria-valuenow={coreDone}><i style={{ width: `${(coreDone / CORE_STEPS.length) * 100}%` }} /></div>
        </div>
        <button className="btn primary" onClick={() => { update({ current: start.id, hidden: false, collapsed: false }); go(start.where.page, start.where.params); }}>
          {coreDone ? "Continue the tour" : "Start the tour"}
        </button>
      </div>

      <section aria-labelledby="core">
        <h2 id="core" className="section-title">The core tour</h2>
        <p className="section-sub">Eight checks that cover ingestion, correlation, explainable ML, risk propagation, evidence integrity and the offline guarantee.</p>
        <ol className="stepper" style={{ listStyle: "none", padding: 0, marginTop: 16 }}>
          {CORE_STEPS.map((s, i) => <StepCard key={s.id} step={s} n={i + 1} done={p.done.includes(s.id)} />)}
        </ol>
      </section>

      <section aria-labelledby="more">
        <h2 id="more" className="section-title">Deeper checks</h2>
        <p className="section-sub">Optional: the focus areas the problem statement names one by one, the case hand-off, the models and the synthetic-data generator.</p>
        <ol className="stepper" style={{ listStyle: "none", padding: 0, marginTop: 16 }}>
          {optional.map((s, i) => <StepCard key={s.id} step={s} n={CORE_STEPS.length + i + 1} done={p.done.includes(s.id)} />)}
        </ol>
      </section>

      <Callout tone="ok" title="Want to run it yourself?">
        Everything here also runs on a laptop with no internet. The System page shows the exact commands; the repository README has the one-page version.
      </Callout>
    </div>
  );
}
