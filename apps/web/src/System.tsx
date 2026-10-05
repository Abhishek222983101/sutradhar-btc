import { useEffect, useState } from "react";
import type { Info } from "./api";
import { publicGet } from "./api";
import { useApi } from "./hooks";
import { Callout, CopyChip, HowTo, PageHeader, Skeleton } from "./ui";

type RefData = { datasets: { file: string; source: string; license: string; as_of: string; sha256: string; bytes: number }[]; tampered: string[] };
type AuditVerify = { ok: boolean; entries: number; head: string | null; broken_at: number | null; reason: string | null };

const CMD_SELFTEST = "uv run sutradhar selftest";
const CMD_NONET = "docker build -f deploy/api.Dockerfile -t sutradhar-api . && docker run --rm --network none sutradhar-api sutradhar selftest";
const CMD_STACK = "export JWT_SECRET=$(openssl rand -hex 32) && docker compose -f compose.airgap.yaml up -d --build";

export default function System() {
  const [info, setInfo] = useState<Info | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { publicGet<Info>("/api/v1/system/info").then(setInfo, (e: Error) => setErr(e.message)); }, []);
  const ref = useApi<RefData>("/api/v1/refdata");
  const audit = useApi<AuditVerify>("/api/v1/audit/verify");
  const guardOn = info ? info.offline_guard.active : null;
  const kb = (n: number) => (n > 1_000_000 ? `${(n / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1000))} KB`);

  return (
    <div className="wrap page">
      <PageHeader
        kicker="Requirements R-01, R-16, R-17"
        title="System: proof that it runs offline"
        lede="The problem statement asks for a complete solution that works with no internet. Here is what the running server reports, and how to reproduce the proof on your own machine."
      />
      <HowTo page="system" />

      {err ? <Callout tone="danger" title="Could not read the server status">{err}</Callout> : !info ? <Skeleton lines={3} /> : (
        <div className={`air${guardOn ? "" : " off"}`}>
          <b>{guardOn ? "AIR-GAPPED ✓" : "Guard off"}</b>
          <div>
            <p><b>Outbound network guard: {info.offline_guard.mode}</b> · blocked outbound connection attempts: <b>{info.offline_guard.blocked_attempts}</b></p>
            <p className="note">The application refuses to open a socket to any public address (invariant I1). Nothing in this product downloads data, fonts or scripts at run time.</p>
          </div>
        </div>
      )}

      <Callout tone="info" title="What this live page does and does not show">
        This public demo runs on a hosted server, so the host itself is online. What the page proves is that the <b>application</b> has its outbound guard on and has never needed the internet.
        The stricter proof, the full test-suite running in a container with the network physically disabled, runs in CI on every commit and you can reproduce it below.
      </Callout>

      <div className="two-col">
        <div className="panel">
          <h2>This server</h2>
          <div className="body">
            {info ? (
              <dl className="kv">
                <dt>Mode</dt><dd>{info.mode}</dd>
                <dt>Version</dt><dd className="mono">{info.version}{info.git_sha ? ` · ${info.git_sha}` : ""}</dd>
                <dt>Database</dt><dd>{info.database}</dd>
                <dt>Worker</dt><dd>{info.worker ? (info.worker.running ? "running (embedded)" : "stopped") : "n/a"}</dd>
                {info.limits && <><dt>Upload limit</dt><dd>{info.limits.upload_max_mb} MB{info.limits.upload_max_rows ? `, ${info.limits.upload_max_rows.toLocaleString()} rows` : ""}{info.limits.upload_ttl_min ? `, deleted after ${info.limits.upload_ttl_min} min` : ""}</dd></>}
              </dl>
            ) : <Skeleton lines={4} />}
          </div>
        </div>
        <div className="panel">
          <h2>Audit chain</h2>
          <div className="body">
            {audit.loading ? <Skeleton lines={2} /> : audit.error ? <p className="note">Could not check the chain: {audit.error}</p> : audit.data && (
              <>
                <p><b>{audit.data.ok ? "Intact" : "BROKEN"}</b> · {audit.data.entries} entries, recomputed from scratch just now</p>
                {audit.data.head && <p className="mono note">head {audit.data.head.slice(0, 24)}…</p>}
              </>
            )}
            <p className="small-note">Every action (sign-in, export, verify, decision) is appended to a hash-chained log. Editing or deleting an entry breaks every hash after it.</p>
          </div>
        </div>
      </div>

      <section aria-labelledby="refdata">
        <h2 id="refdata" className="section-title">Bundled reference data</h2>
        <p className="section-sub">The GeoIP databases ship inside the install. Each file has a source, a licence, an as-of date and a checksum that the server re-computes.</p>
        <div className="panel" style={{ marginTop: 12 }}>
          <div className="table-wrap">
            {ref.loading ? <Skeleton lines={3} /> : ref.error ? <p className="note" style={{ padding: 14 }}>{ref.error}</p> : (
              <table className="data-table">
                <thead><tr><th>File</th><th>Source</th><th>Licence</th><th>As of</th><th>Size</th><th>SHA-256</th><th>Check</th></tr></thead>
                <tbody>
                  {ref.data?.datasets.map((d) => (
                    <tr key={d.file}>
                      <td className="num">{d.file}</td>
                      <td className="small-note">{d.source.length > 56 ? `${d.source.slice(0, 56)}…` : d.source}</td>
                      <td className="small-note">{d.license.split("(")[0]}</td>
                      <td>{d.as_of}</td><td>{kb(d.bytes)}</td><td className="num">{d.sha256.slice(0, 12)}…</td>
                      <td><span className={`st ${ref.data?.tampered.includes(d.file) ? "next" : "live"}`}>{ref.data?.tampered.includes(d.file) ? "CHANGED" : "intact"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>

      <section aria-labelledby="repro">
        <h2 id="repro" className="section-title">Reproduce the proof</h2>
        <p className="section-sub">On any Linux machine with the repository checked out. No network is needed after the first build.</p>
        <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
          <div><p className="note">1. Eight end-to-end checks: generate a world, ingest, analyse twice (identical digest), leads, read-only runs, GeoIP, audit chain, offline guard.</p><CopyChip value={CMD_SELFTEST} /></div>
          <div><p className="note">2. The same self-test with the network physically disabled (this is the CI job):</p><CopyChip value={CMD_NONET} /></div>
          <div><p className="note">3. The full offline product (web, API, worker) on one machine:</p><CopyChip value={CMD_STACK} /></div>
        </div>
      </section>
    </div>
  );
}
