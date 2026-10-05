import { useEffect, useMemo, useRef, useState } from "react";
import { api, apiBlob, type Lead } from "./api";
import { bytes, readZip, sha256Hex, text, writeZip } from "./zip";
import { Callout, HowTo, PageHeader } from "./ui";

type Verdict = {
  ok: boolean; files_checked: number; sha256_mismatches: string[]; manifest_present: boolean; seal_valid: boolean;
  missing_files: string[]; unlisted_files: string[]; reason: string; case_id: string | null; title: string | null; generated_at: string | null;
};
type Attempt = { id: number; what: string; verdict: Verdict };

async function buildSamplePack(): Promise<Blob> {
  const leads = await api<{ items: Lead[] }>("/api/v1/runs/run_hero/leads?limit=1");
  const json = { "Content-Type": "application/json" };
  const c = await api<{ id: string }>("/api/v1/cases", { method: "POST", headers: json, body: JSON.stringify({ title: "Verification demo case" }) });
  await api(`/api/v1/cases/${c.id}/items`, { method: "POST", headers: json, body: JSON.stringify({ item_kind: "lead", ref: leads.items[0].id, run_id: "run_hero" }) });
  await api(`/api/v1/cases/${c.id}/notes`, { method: "POST", headers: json, body: JSON.stringify({ body_md: "Taint path checked: three hops from the seed wallet, high confidence." }) });
  const ex = await api<{ id: string; status: string }>(`/api/v1/cases/${c.id}/exports`, { method: "POST", headers: json, body: JSON.stringify({ kind: "evidence_pack" }) });
  if (ex.status !== "ready") throw new Error("the export did not finish");
  return apiBlob(`/api/v1/exports/${ex.id}/download`);
}

const verify = (blob: Blob) => {
  const form = new FormData();
  form.append("file", blob, "evidence-pack.zip");
  return api<Verdict>("/api/v1/verify", { method: "POST", body: form });
};

export default function Verify() {
  const [pack, setPack] = useState<Blob | null>(null);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const n = useRef(0);

  const record = (what: string, verdict: Verdict) => setAttempts((a) => [{ id: ++n.current, what, verdict }, ...a]);
  const run = async (label: string, job: () => Promise<void>) => {
    setBusy(label); setError("");
    try { await job(); } catch (e) { setError((e as Error).message); }
    setBusy("");
  };

  const build = () => run("build", async () => {
    const blob = await buildSamplePack();
    setPack(blob);
    record("The pack exactly as the server issued it", await verify(blob));
  });

  const edited = async (forgeManifest: boolean) => {
    if (!pack) return;
    const files = await readZip(pack);
    const notes = files.get("notes.md");
    if (!notes) throw new Error("this pack has no notes.md to edit");
    const forged = bytes(`${text(notes)}\n\nEdited after export.`);
    files.set("notes.md", forged);
    if (forgeManifest) {
      const manifest = JSON.parse(text(files.get("manifest.json")!)) as { files: Record<string, { sha256: string; bytes: number }> };
      manifest.files["notes.md"] = { sha256: await sha256Hex(forged), bytes: forged.length };
      files.set("manifest.json", bytes(JSON.stringify(manifest, null, 2)));
    }
    record(
      forgeManifest ? "notes.md edited AND its hash rewritten in the manifest to match" : "notes.md edited, manifest left alone",
      await verify(writeZip(files)),
    );
  };

  const onDrop = (file: File | undefined) => {
    if (!file) return;
    void run("drop", async () => record(`Your file: ${file.name}`, await verify(file)));
  };

  const download = useMemo(() => (pack ? URL.createObjectURL(pack) : null), [pack]);
  useEffect(() => () => { if (download) URL.revokeObjectURL(download); }, [download]);

  return (
    <div className="wrap page">
      <PageHeader
        kicker="Evidence integrity"
        title="Prove an evidence pack was not tampered with"
        lede="An investigator hands a case to someone else. How does the recipient know no file was changed on the way? Every pack is sealed: each file's SHA-256 is written into the manifest, and the manifest carries an HMAC from the server that issued it."
      />
      <HowTo page="verify" />

      <div className="two-col">
        <div className="panel">
          <h2>Try it</h2>
          <div className="body">
            <button className="btn primary" onClick={() => void build()} disabled={busy !== ""}>{busy === "build" ? "Building and verifying…" : "1. Build a sample pack and verify it"}</button>
            <p className="note">Creates a case from a real lead, exports the evidence pack through the same code path an analyst uses, downloads it and checks it.</p>
            <button className="btn" onClick={() => void run("e1", () => edited(false))} disabled={!pack || busy !== ""}>2. Edit a file, then verify</button>
            <p className="note">Rewrites <span className="mono">notes.md</span> inside the zip (in your browser, like an attacker would) and verifies the result: the file hash no longer matches.</p>
            <button className="btn" onClick={() => void run("e2", () => edited(true))} disabled={!pack || busy !== ""}>3. Edit the file and forge its hash, then verify</button>
            <p className="note">The smarter attacker also fixes the hash in the manifest. The hashes now agree, but the seal does not.</p>
            {download && <a className="chip" href={download} download="evidence-pack.zip" style={{ justifySelf: "start" }}>Download the original pack to try your own edits</a>}
            {error && <p className="err" role="alert">{error}</p>}
          </div>
        </div>
        <div className="panel">
          <h2>Or check a pack you already have</h2>
          <div className="body">
            <label
              className={`dropzone${over ? " over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setOver(true); }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); onDrop(e.dataTransfer.files[0]); }}
            >
              <b>Drop an evidence pack (.zip) here</b>
              <span className="note">The zip you get from Cases → Export → Evidence pack. Nothing is stored except an audit-log entry.</span>
              <input type="file" accept=".zip,application/zip" onChange={(e) => onDrop(e.target.files?.[0])} />
            </label>
            <Callout tone="info" title="Why two layers">
              A hash list alone proves the files match the manifest, but whoever edits a file can edit the manifest too. The HMAC seal is keyed with a secret only the server holds, so a doctored manifest cannot be re-sealed.
            </Callout>
          </div>
        </div>
      </div>

      <section aria-labelledby="results">
        <h2 id="results" className="section-title">Results</h2>
        {attempts.length === 0 ? (
          <p className="note" style={{ marginTop: 8 }}>No checks yet. Press step 1.</p>
        ) : (
          <div style={{ display: "grid", gap: 14, marginTop: 12 }}>
            {attempts.map((a) => <VerdictCard key={a.id} attempt={a} />)}
          </div>
        )}
      </section>
    </div>
  );
}

function VerdictCard({ attempt }: { attempt: Attempt }) {
  const v = attempt.verdict;
  return (
    <div className={`verdict ${v.ok ? "ok" : "bad"}`} role="status">
      <b>{v.ok ? "VALID" : "FAILED"}</b>
      <span><b>{attempt.what}</b></span>
      <p>{v.reason}</p>
      <dl className="kv">
        <dt>Files checked</dt><dd>{v.files_checked}</dd>
        <dt>Seal</dt><dd>{v.seal_valid ? "valid (issued by this server)" : "does not match"}</dd>
        {v.sha256_mismatches.length > 0 && <><dt>Changed after export</dt><dd className="mono">{v.sha256_mismatches.join(", ")}</dd></>}
        {v.missing_files.length > 0 && <><dt>Missing</dt><dd className="mono">{v.missing_files.join(", ")}</dd></>}
        {v.unlisted_files.length > 0 && <><dt>Not in manifest</dt><dd className="mono">{v.unlisted_files.join(", ")}</dd></>}
        {v.case_id && <><dt>Case</dt><dd className="mono">{v.title} · {v.case_id}</dd></>}
        {v.generated_at && <><dt>Issued</dt><dd className="mono">{v.generated_at}</dd></>}
      </dl>
    </div>
  );
}
