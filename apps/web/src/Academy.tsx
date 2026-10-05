import { useState } from "react";
import { api } from "./api";
import { useApi } from "./hooks";
import { t, type Lang } from "./i18n";
import { Callout, HowTo, PageHeader, Skeleton } from "./ui";

type Question = { id: string; text: string; options: string[]; kind: string };
type Challenge = { id: string; title: string; time_limit_s: number; questions: Question[] };

export default function Academy({ lang = "en" }: { lang?: Lang } = {}) {
  const list = useApi<Challenge[]>("/api/v1/academy/challenges");
  const challenge = list.data?.[0] ?? null;
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [started, setStarted] = useState<number | null>(null);
  const [result, setResult] = useState<{ score: number } | null>(null);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!challenge || started === null) return;
    setError("");
    try {
      setResult(await api<{ score: number }>(`/api/v1/academy/challenges/${challenge.id}/attempts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers, duration_s: Math.round((Date.now() - started) / 1000) }),
      }));
    } catch (e) { setError((e as Error).message); }
  };
  const reset = () => { setAnswers({}); setResult(null); setStarted(null); };
  const answered = Object.keys(answers).length;

  return (
    <div className="wrap page">
      <PageHeader kicker="Optional · judge challenge" title={challenge ? `Academy: ${challenge.title}` : "Academy"}
        lede={challenge ? `A ${Math.round(challenge.time_limit_s / 60)}-minute check on how the system reasons. Scoring happens on the server, which never sends the answers to your browser.` : undefined} />
      <HowTo page="academy" />
      {list.loading && <Skeleton lines={4} />}
      {list.error && <Callout tone="danger" title="Could not load the challenge">{list.error} <button className="chip" onClick={list.reload}>Try again</button></Callout>}
      {challenge && !started && !result && <div><button className="btn primary" onClick={() => setStarted(Date.now())}>{t(lang, "Start")}</button></div>}

      {challenge && started && !result && (
        <div className="panel" style={{ maxWidth: 760 }}>
          <h2>{t(lang, "Questions")} <span className="note" style={{ fontWeight: 400 }}>({answered} of {challenge.questions.length} answered)</span></h2>
          <div className="body">
            {challenge.questions.map((q, i) => (
              <fieldset key={q.id}>
                <legend>{i + 1}. {q.text}</legend>
                {q.options.map((o) => (
                  <label key={o} style={{ display: "block", padding: "5px 0", cursor: "pointer" }}>
                    <input type="radio" name={q.id} checked={answers[q.id] === o} onChange={() => setAnswers((a) => ({ ...a, [q.id]: o }))} />{o}
                  </label>
                ))}
              </fieldset>
            ))}
            {error && <p className="err" role="alert">{error}</p>}
            <div><button className="btn primary" onClick={() => void submit()} disabled={answered < challenge.questions.length}>{t(lang, "Submit")}</button></div>
          </div>
        </div>
      )}

      {result && (
        <div className="panel" style={{ maxWidth: 520 }}>
          <h2>{t(lang, "Result")}</h2>
          <div className="body">
            <div className="big-p">{Math.round(result.score * 100)}%</div>
            <p className="note">Try again, or open the Console and look closer at any lead you were unsure about.</p>
            <div><button className="chip" onClick={reset}>Try again</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
