import { useEffect, useState } from "react";
import { api } from "./api";
import { btc, ist, pct, short } from "./format";

type Row = Record<string, unknown>;

// Object pages: actor (wallet cluster), address, transaction, IP. One component fetches, then renders per kind
// with the same visual language as the rest of the console — no raw JSON, every field labelled.
export default function Dossier({
  runId,
  kind,
  ref: reference,
  close,
}: {
  runId: string;
  kind: string;
  ref: string;
  close: () => void;
}) {
  const [data, setData] = useState<Row | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    setError("");
    const path =
      kind === "actor" ? `actors/${reference}`
      : kind === "address" ? `addresses/${reference}`
      : kind === "tx" ? `tx/${reference}`
      : `ips/${reference}`;
    void api<Row>(`/api/v1/runs/${runId}/${path}`)
      .then(setData)
      .catch((e) => setError((e as Error).message));
  }, [runId, kind, reference]);

  return (
    <div className="panel">
      <h2>
        {kind[0].toUpperCase() + kind.slice(1)} dossier
        <button className="chip" onClick={close} style={{ float: "right" }}>
          Close
        </button>
      </h2>
      <div className="body">
        {error && <div className="err">{error}</div>}
        {!data && !error && <div className="note">Loading…</div>}
        {data && kind === "actor" && <ActorView d={data} />}
        {data && kind === "address" && <AddressView d={data} />}
        {data && kind === "tx" && <TxView d={data} />}
        {data && kind === "ip" && <IpView d={data} />}
      </div>
    </div>
  );
}

function LeadList({ leads }: { leads: Row[] }) {
  if (!leads.length) return null;
  return (
    <ul className="reasons">
      {leads.map((l) => (
        <li key={l.id as string}>
          <span className={`grade ${l.grade}`} style={{ marginRight: 8 }}>
            {l.grade as string}
          </span>
          {l.title as string}
        </li>
      ))}
    </ul>
  );
}

function ActorView({ d }: { d: Row }) {
  const stats = (d.stats as Row) ?? {};
  const risk = d.risk as Row | null;
  const service = d.service as Row | null;
  const victim = d.victim as Row | null;
  return (
    <>
      <p className="mono note">{short(d.cluster_id as string, 24)}</p>
      <div className="stats" style={{ margin: "8px 0" }}>
        <div className="stat">
          <b>{stats.n_addr as number}</b>
          <span>addresses</span>
        </div>
        <div className="stat">
          <b>{stats.n_tx_sent as number}</b>
          <span>payments sent</span>
        </div>
        <div className="stat">
          <b>{btc(Number(stats.recv_sats ?? 0))}</b>
          <span>BTC received</span>
        </div>
        <div className="stat">
          <b>{stats.n_counterparties as number}</b>
          <span>counterparties</span>
        </div>
      </div>
      {service && (
        <p className="hedge">
          Looks like a {service.kind as string} ({pct(Number(service.score))} match) — an exchange or payment
          service. Risk stops here rather than spreading to its customers.
        </p>
      )}
      {victim && <p className="hedge">Evidence suggests this wallet paid a watchlisted address rather than operating one ({pct(Number(victim.exposure_out))} of its outflow).</p>}
      {risk && Number(risk.taint) > 0 && (
        <p className="note">
          Traced funds: {pct(Number(risk.taint))}, {risk.hops as number} hop(s) from a seed{risk.is_seed ? " (this is a seed wallet)" : ""}.
        </p>
      )}
      {(d.leads as Row[])?.length > 0 && (
        <>
          <h3 style={{ fontSize: 16 }}>Leads on this wallet</h3>
          <LeadList leads={d.leads as Row[]} />
        </>
      )}
      {(d.ips as Row[])?.length > 0 && (
        <>
          <h3 style={{ fontSize: 16 }}>Likely origin IPs</h3>
          <div className="chips">
            {(d.ips as Row[]).slice(0, 6).map((ip) => (
              <span className="chip" key={ip.ip as string}>
                {ip.ip as string} ({ip.n_tx as number} tx)
              </span>
            ))}
          </div>
        </>
      )}
      {(d.partners as Row[])?.length > 0 && (
        <>
          <h3 style={{ fontSize: 16 }}>Value flow partners</h3>
          <ul className="reasons">
            {(d.partners as Row[]).slice(0, 8).map((p, i) => (
              <li key={i}>
                {p.direction === "out" ? "Sends to" : "Receives from"} {short(p.other as string, 12)}
                {p.is_service ? " (service)" : ""}: {btc(Number(p.sats))} BTC over {p.n_tx as number} tx
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function AddressView({ d }: { d: Row }) {
  const received = d.received as Row[];
  const spent = d.spent as Row[];
  const taint = d.taint as Row | null;
  return (
    <>
      <p className="mono note">{d.address as string}</p>
      <p>
        Script type: <b>{d.script_type as string}</b> · part of wallet group{" "}
        <span className="mono">{short(d.cluster_id as string, 14)}</span>
      </p>
      {taint && <p className="hedge">Carries traced funds: {pct(Number(taint.taint))}, {taint.hops as number} hop(s) from a seed.</p>}
      <div className="stats" style={{ margin: "8px 0" }}>
        <div className="stat">
          <b>{received.length}</b>
          <span>payments received</span>
        </div>
        <div className="stat">
          <b>{spent.length}</b>
          <span>payments spent</span>
        </div>
      </div>
    </>
  );
}

function TxView({ d }: { d: Row }) {
  const tx = d.tx as Row;
  const origin = d.origin as Row[];
  return (
    <>
      <p className="mono note">{tx.txid as string}</p>
      <div className="stats" style={{ margin: "8px 0" }}>
        <div className="stat">
          <b>{tx.n_in as number}</b>
          <span>inputs</span>
        </div>
        <div className="stat">
          <b>{tx.n_out as number}</b>
          <span>outputs</span>
        </div>
        <div className="stat">
          <b>{btc(Number(tx.in_sats))}</b>
          <span>BTC moved</span>
        </div>
        <div className="stat">
          <b>{d.sightings as number}</b>
          <span>sensor sightings</span>
        </div>
      </div>
      <p className="note">First seen {ist(Number(tx.first_seen_us))}</p>
      {typeof d.anomaly === "number" && <p className="note">Anomaly score: more unusual than {pct(d.anomaly as number)} of payments in this data.</p>}
      {typeof d.coinjoin_p === "number" && d.coinjoin_p > 0.3 && <p className="hedge">Looks like a CoinJoin-style mix ({pct(d.coinjoin_p as number)} confidence).</p>}
      {d.motif && <p className="note">Motif: {d.motif as string}</p>}
      {origin.length > 0 && (
        <>
          <h3 style={{ fontSize: 16 }}>Candidate origin IPs</h3>
          <ul className="reasons">
            {origin.slice(0, 5).map((o, i) => (
              <li key={i}>
                {o.ip as string} — {pct(Number(o.p))}
                {o.country ? <small> · {o.country as string}{o.asn ? `, AS${o.asn}` : ""}</small> : null}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function IpView({ d }: { d: Row }) {
  const geo = d.geo as Row;
  const seen = d.seen as Row;
  return (
    <>
      <p className="mono note">{geo.ip as string}</p>
      <p>
        Role: <b>{d.role as string}</b>
        {geo.country ? (
          <>
            {" "}
            · {geo.country as string}
            {geo.asn ? `, AS${geo.asn} ${geo.org ?? ""}` : ""}
          </>
        ) : (
          <span className="note"> · not a public, geolocatable address</span>
        )}
      </p>
      <div className="stats" style={{ margin: "8px 0" }}>
        <div className="stat">
          <b>{seen.sightings as number}</b>
          <span>sightings</span>
        </div>
        <div className="stat">
          <b>{seen.txs as number}</b>
          <span>transactions</span>
        </div>
      </div>
      {(d.wallet_groups as Row[])?.length > 0 && (
        <>
          <h3 style={{ fontSize: 16 }}>Wallet groups it likely operates</h3>
          <ul className="reasons">
            {(d.wallet_groups as Row[]).map((w, i) => (
              <li key={i}>
                {short(w.cluster_id as string, 14)} — {w.n_tx as number} transaction(s), {pct(Number(w.mean_p))} average confidence
              </li>
            ))}
          </ul>
        </>
      )}
      {(d.leads as Row[])?.length > 0 && (
        <>
          <h3 style={{ fontSize: 16 }}>Leads on this IP</h3>
          <LeadList leads={d.leads as Row[]} />
        </>
      )}
    </>
  );
}
