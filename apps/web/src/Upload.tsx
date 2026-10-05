import { useState } from "react";
import { api } from "./api";

type Job = { status: string; error?: string; result?: unknown };

async function poll(id: string): Promise<Job> {
  for (let i = 0; i < 240; i++) {
    const j = await api<Job>(`/api/v1/jobs/${id}`);
    if (["succeeded", "failed", "cancelled"].includes(j.status)) return j;
    await new Promise((r) => setTimeout(r, 750));
  }
  throw new Error("timed out waiting for the job");
}

const SAMPLES = [["CSV", "csv"], ["JSON", "json"], ["XML", "xml"]] as const;

/** Ingest in the browser: pick a file, watch it be read, normalised and analysed, then the console switches to it. */
export default function Upload({ onDone }: { onDone: (datasetId: string, runId: string) => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (file: File) => {
    setBusy(true); setMsg("Uploading…");
    try {
      const form = new FormData(); form.append("files", file);
      const res = await api<{ dataset: { id: string }; job: { id: string } }>("/api/v1/datasets", { method: "POST", body: form });
      setMsg("Reading and normalising…");
      const job = await poll(res.job.id);
      if (job.status !== "succeeded") throw new Error(job.error ?? "ingest failed");
      const r = job.result as { rows: number; transactions: number; rejects: number; observation_model: string };
      setMsg(`Loaded ${r.rows} rows, ${r.transactions} transactions, ${r.rejects} rejected, observation model: ${r.observation_model}. Running the analysis…`);
      const run = await api<{ job: { id: string }; run: { id: string } }>("/api/v1/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: res.dataset.id }) });
      const done = await poll(run.job.id);
      if (done.status !== "succeeded") throw new Error(done.error ?? "analysis failed");
      setMsg(`Done: ${(done.result as { leads: number }).leads} leads found in your upload. The console now shows it. It is deleted after 60 minutes.`);
      onDone(res.dataset.id, run.run.id);
    } catch (e) { setMsg((e as Error).message); }
    setBusy(false);
  };
  return (
    <div className="upload" id="section-upload">
      <div className="note">
        <b>No file handy?</b> Download a small synthetic world in any format, then drop it below:{" "}
        {SAMPLES.map(([label, ext], i) => (
          <span key={ext}>{i > 0 && " · "}<a href={`/samples/sutradhar-sample.${ext}`} download>{label}</a></span>
        ))}
      </div>
      <label className="drop">
        <b>Try your own file</b><br /><span className="note">CSV, JSON, NDJSON or XML in the canonical layout, up to 25 MB.</span>
        <input type="file" accept=".csv,.tsv,.txt,.json,.ndjson,.jsonl,.xml" disabled={busy} style={{ display: "block", margin: "8px auto 0" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void send(f); }} />
      </label>
      {msg && <div className="note" role="status" aria-live="polite">{msg}</div>}
    </div>
  );
}
