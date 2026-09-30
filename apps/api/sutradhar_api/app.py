"""The API application factory. `uvicorn --factory sutradhar_api.app:create_app` or `sutradhar api serve`."""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from sutradhar_api import __version__, migrate, offline_guard, problems
from sutradhar_api.auth.security import hash_password
from sutradhar_api.config import Settings
from sutradhar_api.db import Database, utcnow
from sutradhar_api.jobs.worker import Worker
from sutradhar_api.middleware import BodySizeLimit, RateLimit, SecurityHeaders
from sutradhar_api.models import User
from sutradhar_api.ratelimit import RateLimiter
from sutradhar_api.routes import auth, datasets, jobs, runs, system, triage, watchlists
from sutradhar_schemas.enums import AppMode, Role
from sutradhar_schemas.ids import new_id

log = logging.getLogger("sutradhar.api")
STATIC = Path(__file__).parent / "static"
DEMO_ADMIN_EMAIL = "admin@demo.invalid"
DOCS_TITLE = "Sutradhar API"


def _docs_html() -> str:
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=DOCS_TITLE,
        swagger_js_url="/api/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/api/static/swagger/swagger-ui.css",
        swagger_favicon_url="/api/static/favicon.svg",
        swagger_ui_parameters={"validatorUrl": None, "persistAuthorization": False, "tryItOutEnabled": True},
    ).body.decode()


@cache
def docs_csp() -> str:
    """Swagger's page has one inline bootstrap script; allow exactly that script by its hash."""
    inline = re.findall(r"<script>(.*?)</script>", _docs_html(), flags=re.S)
    hashes = " ".join(
        f"'sha256-{base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()}'" for s in inline
    )
    return (
        f"default-src 'none'; script-src 'self' {hashes}; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    )


def _configure_logging(level: str) -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    root.setLevel(level.upper())


def _seed_demo_admin(db: Database, settings: Settings) -> None:
    if not settings.is_demo or settings.demo_admin_password is None:
        return
    with db.write() as session:
        admin = session.scalar(select(User).where(User.email == DEMO_ADMIN_EMAIL))
        password = hash_password(settings.demo_admin_password.get_secret_value())
        if admin is None:
            session.add(
                User(
                    id=new_id("usr"),
                    email=DEMO_ADMIN_EMAIL,
                    name="Demo administrator",
                    role=Role.ADMIN,
                    password_hash=password,
                    is_active=True,
                    created_at=utcnow(),
                )
            )
        else:
            admin.password_hash = password
        session.commit()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    _configure_logging(settings.log_level)
    offline_guard.install(settings.guard_mode, [*settings.offline_allow_hosts, settings.db_host])
    db = Database(settings.database_url)
    limiter = RateLimiter()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        if db.dialect == "sqlite" or settings.app_mode in (AppMode.DEV, AppMode.DEMO):
            migrate.upgrade(settings.database_url)
        app.state.schema_current = migrate.current_revision(settings.database_url) == migrate.head_revision()
        if not app.state.schema_current:
            log.error("database schema is not at the current revision; run `sutradhar migrate`")
        _seed_demo_admin(db, settings)
        if settings.is_demo:
            from sutradhar_api.demo_seed import seed_hero

            seed_hero(db, settings)
        stop = threading.Event()
        thread = None
        if settings.embedded_worker:
            worker = Worker(settings, db)
            app.state.worker = worker
            thread = threading.Thread(
                target=worker.run_forever, args=(stop,), name="embedded-worker", daemon=True
            )
            thread.start()
        try:
            yield
        finally:
            stop.set()
            if thread is not None:
                thread.join(timeout=15)
            db.dispose()

    app = FastAPI(
        title=DOCS_TITLE,
        version=__version__,
        summary="Offline Bitcoin wire + ledger intelligence (SIH26146).",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.limiter = limiter
    app.state.worker = None
    problems.install(app)
    for router in (
        system.router,
        auth.router,
        datasets.router,
        runs.router,
        jobs.router,
        watchlists.router,
        triage.router,
    ):
        app.include_router(router)
    app.mount("/api/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/api/docs", include_in_schema=False)
    def docs() -> HTMLResponse:
        return HTMLResponse(_docs_html())

    app.add_middleware(
        BodySizeLimit, default_bytes=1024 * 1024, upload_bytes=lambda: settings.upload_cap_bytes
    )
    app.add_middleware(RateLimit, limiter=limiter, per_minute=lambda: settings.rate_limit_per_min)
    if settings.cors_origins or settings.cors_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_origin_regex=settings.cors_origin_regex,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "Last-Event-ID",
                "X-Request-ID",
            ],
            expose_headers=["X-Request-ID", "Retry-After"],
            max_age=600,
        )
    app.add_middleware(SecurityHeaders, hsts=settings.hsts, docs_csp=docs_csp)
    return app
