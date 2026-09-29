"""Repository hygiene checks that belong to the security gate."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TRACKED = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.duckdb", "*.sqlite", "id_rsa*"]
ALLOWED = {".env.example"}


def _tracked_files() -> list[str]:
    proc = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line for line in proc.stdout.splitlines() if line]


@pytest.mark.security
def test_no_secrets_or_data_files_tracked() -> None:
    offenders = [
        path
        for path in _tracked_files()
        if Path(path).name not in ALLOWED
        and any(fnmatch.fnmatch(Path(path).name, pattern) for pattern in FORBIDDEN_TRACKED)
    ]
    assert offenders == [], f"secret or data files are tracked by git: {offenders}"


@pytest.mark.security
def test_gitignore_covers_runtime_data_and_secrets() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (".env", "/data/", "/worlds/", "*.duckdb", "*.sqlite", ".vercel/"):
        assert entry in gitignore, f".gitignore must exclude {entry}"
