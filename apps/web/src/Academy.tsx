import { useEffect, useState } from "react";
import { api } from "./api";

type Question = { id: string; text: string; options: string[]; kind: string };
type Challenge = { id: string; title: string; time_limit_s: number; questions: Question[] };

export default function Academy() {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [started, setStarted] = useState<number | null>(null);
  const [result, setResult] = useState<{ score: number } | null>(null);
  useEffect(() => {
    void api<Challenge[]>("/api/v1/academy/challenges").then((c) => setChallenge(c[0]));
  }, []);
  const submit = async () => {
    if (!challenge || started === null) return;
    const r = await api<{ score: number }>(`/api/v1/academy/challenges/${challenge.id}/attempts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers, duration_s: Math.round((Date.now() - started) / 1000) }),
    });
    setResult(r);
  };
  if (!challenge) return <div className="wrap empty">Loading…</div>;
  const answered = Object.keys(answers).length;

  return (
    <div className="wrap">
      <section style={{ paddingTop: 32, maxWidth: 720 }}>
        <h2 className="section-title">Academy: {challenge.title}</h2>
        <p className="note">
          A {Math.round(challenge.time_limit_s / 60)}-minute check on how the system reasons — try it after exploring the
          console. Nothing here reveals real answers to the client; scoring happens on the server.
        </p>
        {!started && (
          <button className="btn primary" onClick={() => setStarted(Date.now())}>
            Start
          </button>
        )}
      </section>

      {started && !result && (
        <div className="panel" style={{ maxWidth: 720, marginTop: 20 }}>
          <h2>
            Questions <span className="note" style={{ fontWeight: 400 }}>({answered} of {challenge.questions.length} answered)</span>
          </h2>
          <div className="body">
            {challenge.questions.map((q, i) => (
              <fieldset key={q.id} style={{ border: "none", padding: 0, marginBottom: 18 }}>
                <legend style={{ fontWeight: 800, marginBottom: 8, padding: 0 }}>
                  {i + 1}. {q.text}
                </legend>
                {q.options.map((o) => (
                  <label key={o} style={{ display: "block", padding: "5px 0", cursor: "pointer" }}>
                    <input type="radio" name={q.id} checked={answers[q.id] === o} onChange={() => setAnswers((a) => ({ ...a, [q.id]: o }))} /> {o}
                  </label>
                ))}
              </fieldset>
            ))}
            <button className="btn primary" onClick={() => void submit()} disabled={answered < challenge.questions.length}>
              Submit
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="panel" style={{ maxWidth: 720, marginTop: 20 }}>
          <h2>Result</h2>
          <div className="body">
            <div className="big-p">{Math.round(result.score * 100)}%</div>
            <p className="note">Try again, or head back to the console to look closer at any lead you weren't sure about.</p>
          </div>
        </div>
      )}
    </div>
  );
}
