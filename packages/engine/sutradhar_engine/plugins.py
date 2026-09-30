"""Plugin hook: extra pipeline stages from other Python packages.

A package declares stages under the `sutradhar.stages` entry-point group; each entry loads to an object with the
same shape as a core stage (`code`, `name`, `requires`, `produces`, `run(ctx)`). Plugin stage codes must start with
`X` so they can never collide with the core E01-E19 codes. Plugins run after the core analysis stages and before
lead ranking, so they can add tables the ranker (or their own reports) use. Broken plugins are skipped with a log line.
"""

from __future__ import annotations

import logging
import re
from importlib.metadata import entry_points

from sutradhar_engine.runner import Stage

log = logging.getLogger("sutradhar.plugins")
GROUP = "sutradhar.stages"
_CODE = re.compile(r"^X[0-9A-Z]{2,6}$")


def load_plugin_stages() -> list[Stage]:
    stages: list[Stage] = []
    for ep in sorted(entry_points(group=GROUP), key=lambda e: e.name):
        try:
            stage = ep.load()
            stage = stage() if isinstance(stage, type) else stage
            if not (
                _CODE.match(str(stage.code))
                and callable(stage.run)
                and stage.name
                and stage.produces is not None
            ):
                raise ValueError("stage must have an X-prefixed code, name, requires, produces and run()")
        except Exception as exc:
            log.warning("skipping plugin %s: %s", ep.name, exc)
            continue
        stages.append(stage)
    return stages
