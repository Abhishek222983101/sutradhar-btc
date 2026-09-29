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


if __name__ == "__main__":  # pragma: no cover
    app()
