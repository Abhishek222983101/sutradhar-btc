"""The `sutradhar` command. Every workflow (generate, ingest, run, train, evaluate, serve) lives here."""

from __future__ import annotations

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


if __name__ == "__main__":  # pragma: no cover
    app()
