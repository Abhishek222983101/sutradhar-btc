"""Repository-level contracts: every package imports, the CLI runs, module boundaries hold (I18)."""

from __future__ import annotations

import importlib
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    "sutradhar_schemas",
    "sutradhar_engine",
    "sutradhar_gen",
    "sutradhar_evals",
    "sutradhar_cli",
    "sutradhar_api",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_packages_importable(name: str) -> None:
    module = importlib.import_module(name)
    assert module.__version__


def test_cli_version() -> None:
    from sutradhar_cli.main import app

    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("sutradhar ")


def test_import_contract() -> None:
    """I18 — the layered import contract in .importlinter must hold."""
    lint_imports = shutil.which("lint-imports")
    assert lint_imports, "import-linter is not installed in the environment"
    proc = subprocess.run(
        [lint_imports, "--config", str(ROOT / ".importlinter")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
