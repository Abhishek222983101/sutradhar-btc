"""Deployment configuration from environment variables (blueprint §12.3, §17.2).

Environment variables configure the deployment (mode, URLs, secrets, paths). Analysis thresholds live in the
`settings` table, never here. A secret never has a default outside dev.
"""

from __future__ import annotations

import secrets
from functools import cached_property
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from sutradhar_api import __version__
from sutradhar_schemas.enums import AppMode

GuardMode = Literal["on", "warn", "off"]
_MIN_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_file=None)

    app_mode: AppMode = AppMode.DEV
    database_url: str = "sqlite:///./data/app.sqlite"
    data_dir: Path = Path("data")
    jwt_secret: SecretStr | None = None
    jwt_access_ttl_min: int = Field(default=20, ge=1, le=120)
    jwt_refresh_ttl_h: int = Field(default=12, ge=1, le=24 * 14)
    offline_guard: GuardMode | None = None
    offline_allow_hosts: Annotated[list[str], NoDecode] = Field(default_factory=list)
    engine_threads: int = Field(default=4, ge=1, le=64)
    worker_concurrency: int = Field(default=1, ge=1, le=16)
    embedded_worker: bool = True
    job_timeout_s: int = Field(default=3600, ge=10)
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cors_origin_regex: str | None = None
    demo_admin_password: SecretStr | None = None
    upload_max_mb: int = Field(default=2048, ge=1)
    demo_upload_max_mb: int = Field(default=25, ge=1)
    demo_upload_max_rows: int = Field(default=200_000, ge=1)
    demo_upload_ttl_min: int = Field(default=60, ge=1)
    rate_limit_per_min: int = Field(default=300, ge=1)
    hsts: bool = False
    git_sha: str = "dev"
    log_level: Literal["debug", "info", "warning", "error"] = "info"

    @field_validator("offline_allow_hosts", "cors_origins", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _check_secrets(self) -> Settings:
        if self.app_mode != AppMode.DEV:
            if (
                self.jwt_secret is None
                or len(self.jwt_secret.get_secret_value().encode()) < _MIN_SECRET_BYTES
            ):
                raise ValueError(
                    f"JWT_SECRET must be set to at least {_MIN_SECRET_BYTES} bytes outside dev mode"
                )
            if self.offline_guard == "off":
                raise ValueError("OFFLINE_GUARD cannot be off outside dev mode (invariant I1)")
        for origin in self.cors_origins:
            if origin == "*" or not origin.startswith(("https://", "http://localhost", "http://127.0.0.1")):
                raise ValueError(f"CORS origin {origin!r} must be an explicit https origin (or localhost)")
        return self

    @property
    def version(self) -> str:
        return __version__

    @property
    def guard_mode(self) -> GuardMode:
        if self.offline_guard is not None:
            return self.offline_guard
        return "warn" if self.app_mode == AppMode.DEV else "on"

    @property
    def is_demo(self) -> bool:
        return self.app_mode == AppMode.DEMO

    @cached_property
    def signing_key(self) -> str:
        """The JWT key. In dev without JWT_SECRET, a per-process random key (tokens die on restart)."""
        if self.jwt_secret is not None:
            return self.jwt_secret.get_secret_value()
        return secrets.token_urlsafe(48)

    @property
    def db_host(self) -> str | None:
        return urlsplit(self.database_url).hostname

    @property
    def upload_cap_bytes(self) -> int:
        return (self.demo_upload_max_mb if self.is_demo else self.upload_max_mb) * 1024 * 1024
