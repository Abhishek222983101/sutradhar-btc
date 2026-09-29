"""The job subprocess (`python -m sutradhar_api.jobs.child`). Heavy work (ingest, engine runs) runs here, in a
fresh interpreter with the offline guard installed and no secrets in its environment, touching only the data
directory. It never opens the app database: progress and the result travel back to the worker as JSON lines,
and the worker records them transactionally.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from sutradhar_api import offline_guard

Progress = Callable[[str, float, str], None]
log = logging.getLogger("sutradhar.job")


def inside(root: Path, relative: str) -> Path:
    """Resolve a payload path and refuse anything that escapes the data directory."""
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise PermissionError("path escapes the data directory")
    return path


def _ingest(payload: dict[str, Any], data_dir: Path, _threads: int, progress: Progress) -> dict[str, Any]:
    from sutradhar_engine.ingest.builtin_profiles import BUILTIN_PROFILES
    from sutradhar_engine.ingest.pipeline import ingest

    profile = BUILTIN_PROFILES[payload["profile"]]
    files = [inside(data_dir, f) for f in payload["files"]]
    out = inside(data_dir, f"datasets/{payload['dataset_id']}")
    result = ingest(files, profile, out, payload["dataset_id"], progress)
    return {
        "manifest": result.manifest.model_dump(mode="json"),
        "capability": result.capability.model_dump(mode="json"),
    }


def _run(payload: dict[str, Any], data_dir: Path, _threads: int, progress: Progress) -> dict[str, Any]:
    from sutradhar_engine.pipeline import run_pipeline
    from sutradhar_engine.settings import EngineSettings

    settings = EngineSettings(**payload["config"])  # recorded at run creation: re-runs reproduce it (I4)
    manifest = run_pipeline(
        inside(data_dir, f"datasets/{payload['dataset_id']}"),
        inside(data_dir, f"runs/{payload['run_id']}"),
        payload["run_id"],
        settings=settings,
        progress=progress,
    )
    return {"manifest": manifest.model_dump(mode="json")}


TASKS: dict[str, Callable[[dict[str, Any], Path, int, Progress], dict[str, Any]]] = {
    "ingest": _ingest,
    "run": _run,
}


def _emit(channel: TextIO, message: dict[str, Any]) -> None:
    channel.write(json.dumps(message, separators=(",", ":")) + "\n")
    channel.flush()


def main() -> None:
    """Protocol: one JSON request on stdin; JSON lines on the original stdout ({"t": "progress"|"result"|"error"}).
    Anything a library prints goes to stderr, so it can never corrupt the protocol."""
    channel = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    request = json.loads(sys.stdin.read())
    config = request["config"]
    offline_guard.install(config["guard_mode"], config.get("allow_hosts", ()))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    data_dir = Path(config["data_dir"]).resolve()

    def progress(stage: str, pct: float, message: str) -> None:
        _emit(
            channel, {"t": "progress", "stage": stage, "pct": round(float(pct), 4), "message": message[:200]}
        )

    try:
        result = TASKS[request["kind"]](request["payload"], data_dir, int(config.get("threads", 4)), progress)
        _emit(channel, {"t": "result", "result": result})
    except Exception as exc:
        log.error("job %s failed:\n%s", request["kind"], traceback.format_exc())
        message = f"{type(exc).__name__}: {exc}".replace(str(data_dir), "<data>")[:500]
        _emit(channel, {"t": "error", "error": message})
        raise SystemExit(1) from None
    finally:
        channel.close()


if __name__ == "__main__":
    main()
