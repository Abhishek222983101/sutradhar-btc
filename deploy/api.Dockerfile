FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*  # LightGBM runtime
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api apps/api
COPY packages packages
RUN uv sync --frozen --no-dev
ENV APP_MODE=demo DATA_DIR=/data DATABASE_URL=sqlite:////data/app.sqlite EMBEDDED_WORKER=true
RUN useradd -m app && mkdir /data && chown app /data
USER app
CMD ["sh", "-c", "exec uvicorn --factory sutradhar_api.app:create_app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*' --no-server-header"]
