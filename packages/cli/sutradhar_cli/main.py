"""The `sutradhar` command. Every workflow (generate, ingest, run, train, evaluate, serve) lives here."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sutradhar_cli import __version__

app = typer.Typer(
    name="sutradhar",
    help="Sutradhar — offline Bitcoin wire + ledger intelligence (SIH26146).",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _root() -> None:
    """Sutradhar — offline Bitcoin wire + ledger intelligence (SIH26146)."""


def _checked_id(value: str, prefix: str) -> str:
    from sutradhar_schemas.ids import check_id

    try:
        return check_id(value, prefix)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def version() -> None:
    """Print the installed Sutradhar version."""
    typer.echo(f"sutradhar {__version__}")


schemas_app = typer.Typer(help="Data contract utilities.", no_args_is_help=True)
app.add_typer(schemas_app, name="schemas")


@schemas_app.command("export")
def schemas_export(
    out: Annotated[Path, typer.Option(help="Where to write the Markdown contract.")] = Path(
        "docs/data-contract.md"
    ),
) -> None:
    """Write the data contract (JSON Schemas + field table) as Markdown."""
    from sutradhar_schemas.docs import render_contract_markdown

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_contract_markdown(), encoding="utf-8")
    typer.echo(f"wrote {out}")


gen_app = typer.Typer(
    help="Generate synthetic worlds (both network and ledger layers, with ground truth).",
    no_args_is_help=True,
)
app.add_typer(gen_app, name="gen")


@gen_app.command("run")
def gen_run(
    scenario: Annotated[str, typer.Option(help="Preset scenario name.")] = "tiny",
    seed: Annotated[int, typer.Option(help="Seed; same scenario + seed gives byte-identical output.")] = 1,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("worlds/tiny"),
) -> None:
    """Generate one world into OUT/data (what the system sees) and OUT/truth (evaluation only)."""
    from sutradhar_gen.config import PRESETS
    from sutradhar_gen.generate import generate

    if scenario not in PRESETS:
        raise typer.BadParameter(f"unknown scenario {scenario!r}; choose from {sorted(PRESETS)}")
    summary = generate(PRESETS[scenario], seed, out)
    counts = summary["counts"]
    typer.echo(
        f"{scenario} (seed {seed}): {counts['txs_exported']} transactions, "
        f"{counts['observations']} observations, {counts['nodes']} nodes -> {out}"
    )


@app.command()
def ingest(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Input files (CSV for now; JSON/NDJSON/XML arrive in P2).", exists=True, dir_okay=False
        ),
    ],
    profile: Annotated[str, typer.Option(help="Built-in mapping profile.")] = "canonical-v1",
    out: Annotated[Path, typer.Option(help="Datasets directory.")] = Path("data/datasets"),
    dataset_id: Annotated[str | None, typer.Option(help="Dataset id (default: new ds_ id).")] = None,
) -> None:
    """Ingest files into an immutable dataset store and print its X-ray."""
    from sutradhar_engine.ingest.builtin_profiles import BUILTIN_PROFILES
    from sutradhar_engine.ingest.pipeline import ingest as run_ingest
    from sutradhar_schemas.ids import new_id

    if profile not in BUILTIN_PROFILES:
        raise typer.BadParameter(f"unknown profile {profile!r}; choose from {sorted(BUILTIN_PROFILES)}")
    ds_id = _checked_id(dataset_id, "ds") if dataset_id else new_id("ds")
    result = run_ingest(files, BUILTIN_PROFILES[profile], out / ds_id, ds_id)
    cap = result.capability
    typer.echo(
        f"{ds_id}: {cap.rows} observations, {cap.txs} transactions, {cap.addresses} addresses, {cap.ips} IPs; "
        f"observation model {cap.network.observation_model}; rejects {cap.quality['rejects']}"
    )


@app.command("run")
def run_cmd(
    dataset: Annotated[
        Path,
        typer.Argument(help="Dataset directory (contains dataset.duckdb).", exists=True, file_okay=False),
    ],
    out: Annotated[Path, typer.Option(help="Runs directory.")] = Path("data/runs"),
    run_id: Annotated[str | None, typer.Option(help="Run id (default: new run_ id).")] = None,
    seed: Annotated[int, typer.Option(help="Engine seed.")] = 2026,
    threads: Annotated[int, typer.Option(help="Worker threads (fixed per run for determinism).")] = 4,
) -> None:
    """Run the engine over a dataset and print the result digest."""
    from sutradhar_engine.pipeline import run_pipeline
    from sutradhar_engine.settings import EngineSettings
    from sutradhar_schemas.ids import new_id

    rid = _checked_id(run_id, "run") if run_id else new_id("run")
    manifest = run_pipeline(dataset, out / rid, rid, settings=EngineSettings(seed=seed, threads=threads))
    leads = manifest.stages.get("E17")
    typer.echo(
        f"{rid}: result digest {manifest.result_digest[:16]}…, leads {leads.rows.get('lead', 0) if leads else 0}"
    )


api_app = typer.Typer(help="The HTTP API.", no_args_is_help=True)
app.add_typer(api_app, name="api")


@api_app.command("serve")
def api_serve(
    host: Annotated[str, typer.Option(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port.")] = 8000,
) -> None:
    """Serve the API (settings come from environment variables, see docs)."""
    import uvicorn

    # Pure-Python loop and HTTP parser: every socket stays behind the offline guard (I1).
    uvicorn.run(
        "sutradhar_api.app:create_app",
        factory=True,
        host=host,
        port=port,
        loop="asyncio",
        http="h11",
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        server_header=False,
        date_header=False,
    )


@api_app.command("openapi")
def api_openapi(
    out: Annotated[Path | None, typer.Option(help="Write here instead of stdout.")] = None,
) -> None:
    """Print the OpenAPI document (the web client is generated from it)."""
    import json

    from sutradhar_api.app import create_app
    from sutradhar_api.config import Settings

    spec = create_app(Settings(embedded_worker=False, offline_guard="warn")).openapi()
    text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    if out is None:
        typer.echo(text, nl=False)
    else:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"wrote {out}")


@app.command()
def migrate() -> None:
    """Bring the app database schema up to date (uses DATABASE_URL or MIGRATION_DATABASE_URL)."""
    import os

    from sutradhar_api import migrate as migrations
    from sutradhar_api.config import Settings

    url = os.environ.get("MIGRATION_DATABASE_URL") or Settings().database_url
    migrations.upgrade(url)
    typer.echo(f"schema at {migrations.current_revision(url)}")


@app.command()
def worker(concurrency: Annotated[int | None, typer.Option(help="Parallel jobs.")] = None) -> None:
    """Run the job worker until interrupted."""
    import signal
    import threading

    from sutradhar_api.config import Settings
    from sutradhar_api.db import Database
    from sutradhar_api.jobs.worker import Worker

    settings = Settings()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    Worker(settings, Database(settings.database_url), concurrency=concurrency).run_forever(stop)


users_app = typer.Typer(help="User accounts.", no_args_is_help=True)
app.add_typer(users_app, name="users")


@users_app.command("create")
def users_create(
    email: Annotated[str, typer.Option(help="Sign-in email.")],
    name: Annotated[str, typer.Option(help="Display name.")],
    role: Annotated[str, typer.Option(help="analyst | lead | admin | auditor")] = "analyst",
) -> None:
    """Create a user and print a generated password once (it is stored only as an argon2id hash)."""
    import secrets

    from sutradhar_api import audit
    from sutradhar_api.auth.security import hash_password
    from sutradhar_api.config import Settings
    from sutradhar_api.db import Database, utcnow
    from sutradhar_api.models import User
    from sutradhar_schemas.ids import new_id

    if role not in ("analyst", "lead", "admin", "auditor"):
        raise typer.BadParameter("role must be analyst, lead, admin or auditor")
    password = secrets.token_urlsafe(18)
    db = Database(Settings().database_url)
    with db.write() as session:
        user = User(
            id=new_id("usr"),
            email=email.strip().lower(),
            name=name.strip(),
            role=role,
            password_hash=hash_password(password),
            is_active=True,
            created_at=utcnow(),
        )
        session.add(user)
        session.flush()
        audit.append(
            session,
            actor_id=None,
            actor_role="system",
            action="user.create",
            target_kind="user",
            target_ref=user.id,
            payload={"role": role, "via": "cli"},
        )
        session.commit()
    typer.echo(f"created {user.id} ({role}); password (shown once): {password}")


audit_app = typer.Typer(help="The audit chain.", no_args_is_help=True)
app.add_typer(audit_app, name="audit")


@audit_app.command("verify")
def audit_verify() -> None:
    """Recompute every audit hash; exit 1 if the chain is broken."""
    from sutradhar_api import audit
    from sutradhar_api.config import Settings
    from sutradhar_api.db import Database

    with Database(Settings().database_url).read() as session:
        result = audit.verify(session)
    if not result.ok:
        typer.echo(f"BROKEN at entry {result.broken_at}: {result.reason}", err=True)
        raise typer.Exit(1)
    typer.echo(f"audit chain OK: {result.entries} entries, head {result.head[:16]}…")


if __name__ == "__main__":  # pragma: no cover
    app()
