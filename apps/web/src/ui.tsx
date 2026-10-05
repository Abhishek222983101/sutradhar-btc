import { Component, useCallback, useEffect, useId, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import { PAGE_HELP, type Input } from "./guide";
import type { Page } from "./router";
import { update, useProgress } from "./progress";

/** A value the visitor is meant to paste somewhere: one click copies it. */
export function CopyChip({ value, label, note }: { value: string; label?: string; note?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(async () => {
    try { await navigator.clipboard.writeText(value); } catch {
      const t = document.createElement("textarea"); t.value = value; document.body.appendChild(t); t.select();
      try { document.execCommand("copy"); } finally { t.remove(); }
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }, [value]);
  return (
    <span className="copy-row">
      {label && <span className="copy-label">{label}</span>}
      <button type="button" className="copy-chip" onClick={() => void copy()} aria-label={`Copy ${value}`}>
        <code>{value}</code>
        <span className="copy-state" aria-live="polite">{copied ? "Copied" : "Copy"}</span>
      </button>
      {note && <span className="copy-note">{note}</span>}
    </span>
  );
}

export function Inputs({ items }: { items: Input[] }) {
  return <div className="inputs">{items.map((i) => <CopyChip key={i.value} {...i} />)}</div>;
}

export function Callout({ tone = "info", title, children }: { tone?: "info" | "ok" | "warn" | "danger"; title?: string; children: ReactNode }) {
  return (
    <div className={`callout ${tone}`} role={tone === "danger" ? "alert" : undefined}>
      {title && <b>{title}</b>}
      <div>{children}</div>
    </div>
  );
}

export type TabDef = { id: string; label: string; hint?: string };

/** Accessible tabs: roving focus, arrow keys, Home/End. */
export function Tabs({ tabs, value, onChange, label }: { tabs: TabDef[]; value: string; onChange: (id: string) => void; label: string }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const onKey = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value);
    const to = e.key === "ArrowRight" ? (i + 1) % tabs.length : e.key === "ArrowLeft" ? (i - 1 + tabs.length) % tabs.length : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : -1;
    if (to < 0) return;
    e.preventDefault();
    onChange(tabs[to].id);
    refs.current[tabs[to].id]?.focus();
  };
  return (
    <div className="tabs" role="tablist" aria-label={label} onKeyDown={onKey}>
      {tabs.map((t) => (
        <button key={t.id} ref={(el) => { refs.current[t.id] = el; }} role="tab" id={`tab-${t.id}`} aria-selected={value === t.id}
          aria-controls={`panel-${t.id}`} tabIndex={value === t.id ? 0 : -1} title={t.hint} className="tab" onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  return <div role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} className="tabpanel" tabIndex={0}>{children}</div>;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return <div className="skeleton" aria-hidden="true">{Array.from({ length: lines }, (_, i) => <i key={i} style={{ width: `${88 - ((i * 17) % 40)}%` }} />)}</div>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty-state"><b>{title}</b>{children && <p>{children}</p>}</div>;
}

export function PageHeader({ kicker, title, lede, children }: { kicker?: string; title: string; lede?: ReactNode; children?: ReactNode }) {
  return (
    <header className="page-head">
      {kicker && <p className="kicker">{kicker}</p>}
      <h1>{title}</h1>
      {lede && <p className="lede-s">{lede}</p>}
      {children}
    </header>
  );
}

/** The per-page "how to use this page" panel: open on a first visit, collapsible, remembered. */
export function HowTo({ page }: { page: Page }) {
  const help = PAGE_HELP[page];
  const { helpClosed } = useProgress();
  const id = useId();
  if (!help) return null;
  const closed = helpClosed.includes(page);
  const toggle = () => update({ helpClosed: closed ? helpClosed.filter((p) => p !== page) : [...helpClosed, page] });
  return (
    <section className="howto" aria-labelledby={id}>
      <button className="howto-head" onClick={toggle} aria-expanded={!closed}>
        <span id={id}>{help.title}</span><span aria-hidden="true">{closed ? "Show" : "Hide"}</span>
      </button>
      {!closed && (
        <div className="howto-body">
          <ol>{help.steps.map((s) => <li key={s}>{s}</li>)}</ol>
          {help.inputs && <Inputs items={help.inputs} />}
          {help.tip && <p className="small-note">{help.tip}</p>}
        </div>
      )}
    </section>
  );
}

/** Run an effect once the element scrolls into the viewport (lazy panels). */
export function useOnVisible<T extends Element>(cb: () => void) {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { cb(); return; }
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { cb(); io.disconnect(); } });
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return ref;
}

/** A render error in one page must never blank the whole site: say so, and offer the way out. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: string | null }> {
  state = { failed: null as string | null };
  static getDerivedStateFromError(e: Error) { return { failed: e.message }; }
  componentDidCatch(e: Error, info: ErrorInfo) { console.error("page crashed", e, info.componentStack); }
  render() {
    if (this.state.failed === null) return this.props.children;
    return (
      <div className="wrap page">
        <Callout tone="danger" title="This page hit an unexpected problem">
          Nothing was lost. <button className="chip" onClick={() => this.setState({ failed: null })}>Try again</button>{" "}
          <a href="#/guide">Back to the Judge guide</a>
          <p className="small-note mono">{this.state.failed}</p>
        </Callout>
      </div>
    );
  }
}
