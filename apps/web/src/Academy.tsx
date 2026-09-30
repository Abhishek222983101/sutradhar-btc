import { useEffect, useState } from "react";
import { api } from "./api";

type Question = { id: string; text: string; options: string[]; kind: string };
type Challenge = { id: string; title: string; time_limit_s: number; questions: Question[] };

export default function Academy() {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [started, setStarted] = useState<number | null>(null);
  const [result, setResult] = useState<{ score: number } | null>(null);
  useEffect(() => { void api<Challenge[]>("/api/v1/academy/challenges").then((c) => setChallenge(c[0])); }, []);
  const submit = async () => {
    if (!challenge || started === null) return;
    const r = await api<{ score: number }>(`/api/v1/academy/challenges/${challenge.id}/attempts`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers, duration_s: Math.round((Date.now() - started) / 1000) }),
    });
    setResult(r);
  };
  if (!challenge) return <div className="wrap empty">Loading…</div>;
  return (
    <div className="wrap">
      <h2 className="section-title">Academy: {challenge.title}</h2>
      <p className="note">{challenge.time_limit_s / 60} minute limit. Try it after exploring the console.</p>
      {!started && <button className="btn primary" onClick={() => setStarted(Date.now())}>Start</button>}
      {started && !result && (
        <div className="panel"><div className="body">
          {challenge.questions.map((q) => (
            <div key={q.id} style={{ marginBottom: 16 }}>
              <p><b>{q.text}</b></p>
              {q.options.map((o) => (
                <label key={o} style={{ display: "block", padding: 4 }}>
                  <input type="radio" name={q.id} checked={answers[q.id] === o} onChange={() => setAnswers((a) => ({ ...a, [q.id]: o }))} /> {o}
                </label>
              ))}
            </div>
          ))}
          <button className="btn primary" onClick={() => void submit()}>Submit</button>
        </div></div>
      )}
      {result && <p className="big-p">Score: {Math.round(result.score * 100)}%</p>}
    </div>
  );
}
